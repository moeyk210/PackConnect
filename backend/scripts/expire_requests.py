"""Optional scheduled maintenance: python backend/scripts/expire_requests.py."""

import sys
from pathlib import Path

# Direct runs put only scripts/ on the path; backend modules live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import get_db
from features.lifecycle import expire_requests

if __name__ == "__main__":
    with get_db() as db:
        count = expire_requests(db)
    print(f"Expired {count} unanswered requests.")
