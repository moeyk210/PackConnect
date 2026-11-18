"""Measure chat delivery latency against a running PackConnect backend.

Never point this at a shared or live database: it registers two fictional
accounts, opens an advice request, and sends messages. Use a local database
(see docs/REALTIME_MESSAGING.md).

    python backend/scripts/benchmark_messaging.py --messages 30

Polling mode reproduces the current frontend chat loop (Messaging.jsx): the
receiver requests GET /api/requests/<id>/messages?after_id=<cursor>, waits for
the response, then schedules the next request 3 seconds later. Latency is the
time from just before the sender's POST to the moment the receiver's response
containing that message arrives.
"""

import argparse
import json
import random
import statistics
import threading
import time
import urllib.request
from http.cookiejar import CookieJar
from uuid import uuid4

POLL_DELAY_SECONDS = 3.0  # Messaging.jsx: setTimeout(poll, 3000)


class Client:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.requests_made = 0

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        self.requests_made += 1
        with self.opener.open(request, timeout=15) as response:
            return json.loads(response.read())


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
    rng = random.Random(seed)
    for number in range(count):
        # Random gaps spread sends uniformly across the poll cycle.
        time.sleep(rng.uniform(0.5, 3.5))
        body = f"benchmark message {number}"
        sent_at[body] = time.perf_counter()
        sender.call("POST", f"/api/requests/{request_id}/messages", {"body": body})
    deadline = time.perf_counter() + POLL_DELAY_SECONDS * 3
    while len(received_at) < count and time.perf_counter() < deadline:
        time.sleep(0.05)
    done.set()
    thread.join(timeout=15)
    elapsed_minutes = (time.perf_counter() - started) / 60
    latencies = [(received_at[body] - sent_at[body]) * 1000 for body in sent_at if body in received_at]
    return latencies, count - len(latencies), receiver.requests_made / elapsed_minutes


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--messages", type=int, default=30)
    parser.add_argument("--seed", type=int, default=510)
    args = parser.parse_args()
    latencies, missing, chat_rate = measure_polling(args.base_url, args.messages, args.seed)
    if not latencies:
        raise SystemExit("No messages were received.")
    print("Mode: polling (current frontend chat loop)")
    print(f"Messages received: {len(latencies)}/{args.messages} (missing {missing})")
    print(f"Latency p50: {statistics.median(latencies):.0f} ms")
    print(f"Latency p95: {percentile(latencies, 0.95):.0f} ms")
    print(f"Latency max: {max(latencies):.0f} ms")
    print(f"Receiver chat requests/min: {chat_rate:.1f}")


if __name__ == "__main__":
    main()
