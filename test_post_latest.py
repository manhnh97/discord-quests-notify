#!/usr/bin/env python3
"""
Quick test script: fetch the latest quest and post it to all WEBHOOK_URLs.

Usage:
    python3 test_post_latest.py

Notes:
    - Uses helpers from main.py and respects multi-URL WEBHOOK_URL parsing.
    - Requires WEBHOOK_URL in your .env (comma/semicolon separated allowed).
"""

import os
import sys
from typing import Optional, List

from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

# Import from main module
from main import (
    request_quests,
    create_quest_embed,
    send_webhook,
    _parse_webhook_urls,
    WEBHOOK_URL,
)


def post_latest(webhook_urls: Optional[List[str]] = None) -> int:
    """
    Fetch latest quest and post to the provided webhook URLs.

    Returns process exit code (0 on success, 1 on failure/no data).
    """
    urls = webhook_urls if webhook_urls is not None else _parse_webhook_urls(WEBHOOK_URL)
    if not urls:
        print("No webhook URL provided. Set WEBHOOK_URL in .env")
        return 1

    data = request_quests()
    if not data or 'quests' not in data or not data['quests']:
        print("No quests data available")
        return 1

    # Sort quests by start date desc
    sorted_quests = sorted(data["quests"], key=lambda q: q['config']['starts_at'], reverse=True)
    latest = sorted_quests[0]
    embed = create_quest_embed(latest)

    failures = 0
    for url in urls:
        try:
            resp = send_webhook(url, embed)
            if resp.status_code != 204:
                print(f"Send failed to {url[:50]}... Status: {resp.status_code}")
                failures += 1
            else:
                print(f"Sent to {url[:50]}... OK")
        except Exception as e:
            print(f"Error sending to {url[:50]}...: {e}")
            failures += 1

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(post_latest())


