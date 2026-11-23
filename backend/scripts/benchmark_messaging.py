"""Measure chat delivery latency against a running PackConnect backend.

Never point this at a shared or live database: it registers two fictional
accounts, opens an advice request, and sends messages. Use --serve-local with
a local database (see docs/REALTIME_MESSAGING.md):

    python backend/scripts/benchmark_messaging.py --serve-local postgresql://...@127.0.0.1:55432/packconnect_bench

--serve-local starts the backend inside this process on a free port chosen by
the operating system, so requests cannot reach another server that happens to
be running (on Windows, two servers can bind port 5000 at once).

--mode poll reproduces the pre-real-time frontend chat loop: the receiver
requests GET /api/requests/<id>/messages?after_id=<cursor>, waits for the
response, then schedules the next request 3 seconds later. It is also today's
fallback while the socket is down.

--mode push is the real-time path: the receiver keeps a Socket.IO connection
(authenticated by its session cookie) and makes no HTTP requests while waiting.
Push mode needs the dev-only client: pip install -r backend/requirements-dev.txt

Latency is the time from just before the sender's POST to the moment the
receiver has the message (poll response or pushed chat_message event).
"""

import argparse
import json
import logging
import os
import random
import secrets
import statistics
import sys
import threading
import time
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from uuid import uuid4

from psycopg.conninfo import conninfo_to_dict

POLL_DELAY_SECONDS = 3.0  # Messaging.jsx: setTimeout(poll, 3000)


class Client:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.requests_made = 0

    def cookie_header(self):
        return "; ".join(f"{cookie.name}={cookie.value}" for cookie in self.jar)

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        self.requests_made += 1
        with self.opener.open(request, timeout=15) as response:
            return json.loads(response.read())


def serve_local(database_url):
    if conninfo_to_dict(database_url).get("host") not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("--serve-local requires a local PostgreSQL host; never use the shared Supabase URL.")
    # Set before importing app: load_dotenv never overrides existing variables,
    # so backend/.env cannot redirect the benchmark to Supabase.
    os.environ.update(SUPABASE_DB_URL=database_url, SUPABASE_URL="", SUPABASE_SECRET_KEY="",
                      FLASK_SECRET_KEY=secrets.token_hex(32))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import app as portal
    from werkzeug.serving import make_server

    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # keep per-request lines out of results
    server = make_server("127.0.0.1", 0, portal.app, threaded=True)  # port 0: OS picks a free port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}"


def percentile(values, fraction):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def open_conversation(base_url):
    tag = uuid4().hex[:10]
    password = "benchmark password " + tag
    sender, receiver = Client(base_url), Client(base_url)
    ids = []
    for client, name, advise in ((sender, "Bench Sender", False), (receiver, "Bench Advisor", True)):
        email = f"bench-{name.split()[1].lower()}-{tag}@example.edu"
        student = client.call("POST", "/api/auth/register", {
            "name": name, "email": email, "password": password, "program": "Computer Science",
            "year": "Senior", "willing_to_advise": advise, "completed_courses": ["CSC 510"],
        })["student"]
        client.call("POST", "/api/auth/login", {"email": email, "password": password})
        ids.append(student["id"])
    request_id = sender.call("POST", "/api/requests", {
        "recipient_id": ids[1], "course_code": "CSC 510", "advice_topic": "Benchmark",
        "message": "Latency benchmark conversation.",
    })["request"]["id"]
    receiver.call("PATCH", f"/api/requests/{request_id}", {"status": "accepted"})
    return sender, receiver, request_id


def send_messages(sender, request_id, count, seed, sent_at):
    rng = random.Random(seed)
    for number in range(count):
        # Random gaps spread sends uniformly across the poll cycle.
        time.sleep(rng.uniform(0.5, 3.5))
        body = f"benchmark message {number}"
        sent_at[body] = time.perf_counter()
        sender.call("POST", f"/api/requests/{request_id}/messages", {"body": body})


def wait_for(received_at, count):
    deadline = time.perf_counter() + POLL_DELAY_SECONDS * 3
    while len(received_at) < count and time.perf_counter() < deadline:
        time.sleep(0.05)


def measure_push(base_url, count, seed):
    import socketio  # dev-only dependency (backend/requirements-dev.txt)

    sender, receiver, request_id = open_conversation(base_url)
    sent_at, received_at = {}, {}
    cookie = receiver.cookie_header()
    client = socketio.Client(reconnection=False)

    @client.on("chat_message")
    def on_message(data):
        if data["request_id"] == request_id:
            received_at[data["message"]["body"]] = time.perf_counter()

    client.connect(base_url, headers={"Cookie": cookie}, transports=["websocket"], wait_timeout=10)
    receiver.requests_made = 0
    started = time.perf_counter()
    try:
        send_messages(sender, request_id, count, seed, sent_at)
        wait_for(received_at, count)
    finally:
        client.disconnect()
    elapsed_minutes = (time.perf_counter() - started) / 60
    latencies = [(received_at[body] - sent_at[body]) * 1000 for body in sent_at if body in received_at]
    return latencies, count - len(latencies), receiver.requests_made / elapsed_minutes


def measure_polling(base_url, count, seed):
    sender, receiver, request_id = open_conversation(base_url)
    sent_at, received_at = {}, {}
    done = threading.Event()
    path = f"/api/requests/{request_id}/messages?after_id="
    cursor = receiver.call("GET", path + "0")["messages"]
    cursor = cursor[-1]["id"] if cursor else 0
    receiver.requests_made = 0

    def poll():
        nonlocal cursor
        while not done.is_set():
            data = receiver.call("GET", path + str(cursor))
            arrived = time.perf_counter()
            for message in data["messages"]:
                received_at[message["body"]] = arrived
                cursor = message["id"]
            if not data["has_more"]:
                done.wait(POLL_DELAY_SECONDS)

    started = time.perf_counter()
    thread = threading.Thread(target=poll, daemon=True)
    thread.start()
    send_messages(sender, request_id, count, seed, sent_at)
    wait_for(received_at, count)
    done.set()
    thread.join(timeout=15)
    elapsed_minutes = (time.perf_counter() - started) / 60
    latencies = [(received_at[body] - sent_at[body]) * 1000 for body in sent_at if body in received_at]
    return latencies, count - len(latencies), receiver.requests_made / elapsed_minutes


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--serve-local", metavar="DATABASE_URL",
                        help="run the backend in-process against this local database")
    target.add_argument("--base-url", help="an already running backend you know uses a local database")
    parser.add_argument("--mode", choices=("poll", "push"), default="poll")
    parser.add_argument("--messages", type=int, default=30)
    parser.add_argument("--seed", type=int, default=510)
    args = parser.parse_args()
    base_url = serve_local(args.serve_local) if args.serve_local else args.base_url
    print(f"Target: {base_url}")
    measure = measure_push if args.mode == "push" else measure_polling
    latencies, missing, chat_rate = measure(base_url, args.messages, args.seed)
    if not latencies:
        raise SystemExit("No messages were received.")
    print("Mode: " + ("push (Socket.IO, no polling)" if args.mode == "push"
                      else "polling (3 s chat loop: pre-real-time / fallback)"))
    print(f"Messages received: {len(latencies)}/{args.messages} (missing {missing})")
    print(f"Latency p50: {statistics.median(latencies):.0f} ms")
    print(f"Latency p95: {percentile(latencies, 0.95):.0f} ms")
    print(f"Latency max: {max(latencies):.0f} ms")
    print(f"Receiver chat requests/min: {chat_rate:.1f}")


if __name__ == "__main__":
    main()
