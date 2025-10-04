#!/usr/bin/env python3
"""
Test script for Discord quest posting functionality.

Usage:
    python3 test_post_latest.py                    # Test with webhook sending
    python3 test_post_latest.py --fetch-only        # Test quest fetching only (no webhooks)

Features:
    - Fetches latest quest from Discord API
    - Creates Discord embed with quest details
    - Sends to configured webhook URLs
    - Supports multiple webhook URLs (comma/semicolon separated)
    - Detailed logging and error reporting
    - Safe testing mode without webhook sending

Requirements:
    - WEBHOOK_URL in .env file (for webhook testing)
    - DISCORD_AUTHORIZATION and TOKEN_JWT in .env file
    - All dependencies from requirements.txt installed
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
    send_discord_message,
    _parse_webhook_urls,
    get_quest_id,
    get_quest_name,
)

# Import environment variable
WEBHOOK_URL_TEST = os.getenv('WEBHOOK_URL_TEST', '')


def post_latest(webhook_urls: Optional[List[str]] = None) -> int:
    """
    Fetch latest quest and post to the provided webhook URLs.

    Returns process exit code (0 on success, 1 on failure/no data).
    """
    print("🧪 Testing Quest Posting")
    print("=" * 50)
    
    urls = webhook_urls if webhook_urls is not None else _parse_webhook_urls(WEBHOOK_URL_TEST)
    if not urls:
        print("❌ No webhook URL provided. Set WEBHOOK_URL in .env")
        return 1
    
    print(f"✅ Found {len(urls)} webhook URL(s)")
    for i, url in enumerate(urls, 1):
        print(f"  {i}. {url[:50]}...")

    print("\n📡 Fetching quests from Discord API...")
    data = request_quests()
    if not data or 'quests' not in data or not data['quests']:
        print("❌ No quests data available")
        return 1
    
    print(f"✅ Found {len(data['quests'])} quests")

    # Sort quests by start date desc
    sorted_quests = sorted(data["quests"], key=lambda q: q['config']['starts_at'], reverse=True)
    latest = sorted_quests[0]
    
    # Get quest details for logging
    quest_id = get_quest_id(latest['config'])
    quest_name = get_quest_name(latest['config'])
    
    print(f"\n🎯 Latest quest: {quest_name}")
    print(f"   ID: {quest_id}")
    
    print("\n📝 Creating Discord embed...")
    embed = create_quest_embed(latest)
    content = "🎉 New Quest Available! 🎉"
    print("✅ Embed created successfully")

    print(f"\n🚀 Sending to {len(urls)} webhook(s)...")
    failures = 0
    for i, url in enumerate(urls, 1):
        try:
            print(f"  Sending to webhook {i}/{len(urls)}...")
            resp = send_discord_message(url, content, embed)
            if resp.status_code != 204:
                print(f"  ❌ Send failed to {url[:50]}... Status: {resp.status_code}")
                failures += 1
            else:
                print(f"  ✅ Sent to {url[:50]}... OK")
        except Exception as e:
            print(f"  ❌ Error sending to {url[:50]}...: {e}")
            failures += 1

    print(f"\n📊 Results: {len(urls) - failures}/{len(urls)} webhooks sent successfully")
    return 0 if failures == 0 else 1


def test_quest_fetch_only() -> int:
    """
    Test quest fetching and embed creation without sending webhooks.
    
    Returns process exit code (0 on success, 1 on failure/no data).
    """
    print("🧪 Testing Quest Fetching (No Webhook)")
    print("=" * 50)
    
    print("📡 Fetching quests from Discord API...")
    data = request_quests()
    if not data or 'quests' not in data or not data['quests']:
        print("❌ No quests data available")
        return 1
    
    print(f"✅ Found {len(data['quests'])} quests")
    
    # Sort quests by start date desc
    sorted_quests = sorted(data["quests"], key=lambda q: q['config']['starts_at'], reverse=True)
    
    print("\n📋 Available Quests:")
    for i, quest in enumerate(sorted_quests[:5], 1):  # Show first 5 quests
        quest_id = get_quest_id(quest['config'])
        quest_name = get_quest_name(quest['config'])
        print(f"  {i}. {quest_name} (ID: {quest_id})")
    
    # Test embed creation with the latest quest
    latest = sorted_quests[0]
    quest_id = get_quest_id(latest['config'])
    quest_name = get_quest_name(latest['config'])
    
    print(f"\n🎯 Testing embed creation for: {quest_name}")
    try:
        embed = create_quest_embed(latest)
        print("✅ Embed created successfully")
        print(f"   Title: {embed['title']}")
        print(f"   Fields: {len(embed['fields'])}")
        print(f"   Description: {embed['description'][:50]}...")
        return 0
    except Exception as e:
        print(f"❌ Embed creation failed: {e}")
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Discord quest posting')
    parser.add_argument('--fetch-only', action='store_true', 
                       help='Only test quest fetching and embed creation (no webhooks)')
    
    args = parser.parse_args()
    
    if args.fetch_only:
        sys.exit(test_quest_fetch_only())
    else:
        sys.exit(post_latest())


