#!/usr/bin/env python3
"""
Discord Quest List Viewer

A comprehensive tool for fetching Discord quests and sending them as webhooks.
Features include quest tracking, duplicate prevention, and beautiful Discord embeds.
"""

import os
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any

import pytz
import requests
from dotenv import load_dotenv

# Import our SQLite database functions
from seen_quests import (
    add_seen_quest as db_add_seen_quest,
    get_seen_quests as db_get_seen_quests,
    get_seen_quests_with_datetime as db_get_seen_quests_with_datetime,
    cleanup_old_quests as db_cleanup_old_quests,
    reset_seen_quests as db_reset_seen_quests,
    sync_quests_with_api as db_sync_quests_with_api
)

# Load environment variables
load_dotenv()

# Configuration constants
DISCORD_AUTHORIZATION: str = os.getenv('DISCORD_AUTHORIZATION', '')
TOKEN_JWT: str = os.getenv('TOKEN_JWT', '')
WEBHOOK_URL: str = os.getenv('WEBHOOK_URL', '')
WEBHOOK_URL_ALERT: str = os.getenv('WEBHOOK_URL_ALERT', '')

# File paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_QUESTS_FILE: str = os.path.join(SCRIPT_DIR, "db", "seen_quests.db")

# API configuration
DISCORD_API_BASE_URL: str = "https://discord.com/api/v9"
QUESTS_ENDPOINT: str = f"{DISCORD_API_BASE_URL}/quests/@me"
QUEST_PAGE_BASE_URL: str = "https://discord.com/quests"

# Image dimensions
IMAGE_WIDTH: int = 1320
IMAGE_HEIGHT: int = 350
THUMBNAIL_WIDTH: int = 300
THUMBNAIL_HEIGHT: int = 300

# Discord embed colors
EMBED_COLOR: int = 0x00b0f4
TEST_EMBED_COLOR: int = 0x00ff00

def get_random_embed_color() -> int:
    """
    Generate a random color for Discord embeds.
    
    Returns:
        Random color as integer (0xRRGGBB format).
    """
    # Generate random RGB values
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    
    # Convert to hex format
    return (r << 16) | (g << 8) | b

# Rate limiting
WEBHOOK_DELAY_SECONDS: float = 1.0

# Task emoji mapping
TASK_EMOJI_MAP: Dict[str, str] = {
    'WATCH_VIDEO': '📺',
    'PLAY_ON_DESKTOP': '🖥️',
    'STREAM_ON_DESKTOP': '📡',
    'PLAY_ACTIVITY': '🎮',
    'WATCH_VIDEO_ON_MOBILE': '📱'
}

# Configure logging
def setup_logging() -> logging.Logger:
    """
    Set up logging configuration.
    
    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger('discord_quests')
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger

# Initialize logger
logger = setup_logging()

def _parse_webhook_urls(raw_urls: str) -> List[str]:
    """
    Parse a comma- or semicolon-separated list of webhook URLs.
    Whitespace is trimmed and empty entries are removed.
    """
    if not raw_urls:
        return []
    # Accept commas or semicolons as separators
    normalized = raw_urls.replace(';', ',')
    return [u.strip() for u in normalized.split(',') if u.strip()]

class DiscordWebhookAlertHandler(logging.Handler):
    """
    Logging handler that forwards ERROR+ logs to a Discord webhook.
    Uses WEBHOOK_URL_ALERT, falling back to WEBHOOK_URL.
    """
    def emit(self, record: logging.LogRecord) -> None:
        try:
            targets = _parse_webhook_urls(WEBHOOK_URL_ALERT) or _parse_webhook_urls(WEBHOOK_URL)
            if not targets:
                return
            message = self.format(record)
            for target in targets:
                requests.post(target, json={"content": f"🚨 {message}"})
        except Exception:
            # Never raise from logging
            pass

# Attach alert handler for error monitoring if a webhook is configured
if WEBHOOK_URL_ALERT or WEBHOOK_URL:
    _alert_handler = DiscordWebhookAlertHandler()
    _alert_handler.setLevel(logging.ERROR)
    _alert_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(_alert_handler)

def _send_alert(message: str) -> None:
    """
    Send a plain text alert message to the configured Discord webhook.

    Args:
        message: The message content to send.
    """
    try:
        targets = _parse_webhook_urls(WEBHOOK_URL_ALERT) or _parse_webhook_urls(WEBHOOK_URL)
        if not targets:
            logger.warning(f"Alert not sent (missing WEBHOOK_URL_ALERT/WEBHOOK_URL): {message}")
            return
        for target in targets:
            requests.post(target, json={"content": message})
    except Exception as e:
        logger.error(f"Failed to send alert webhook: {str(e)}")

def _preflight_check_tokens() -> None:
    """
    Validate that required tokens are present; alert if missing.
    """
    issues = []
    if not DISCORD_AUTHORIZATION:
        issues.append("DISCORD_AUTHORIZATION is empty")
    if not TOKEN_JWT:
        issues.append("TOKEN_JWT is empty")
    if issues:
        msg = "⚠️ Token misconfiguration detected: " + "; ".join(issues) + ". Please update your .env."
        logger.error(msg)
        _send_alert(msg)

def load_seen_quests() -> Set[str]:
    """
    Load the list of seen quest IDs from database.
    
    Returns:
        Set[str]: Set of quest IDs that have been seen before.
    """
    try:
        logger.debug(f"Loading seen quests from database at: {SEEN_QUESTS_FILE}")
        
        # Get current seen quests
        seen_quests = db_get_seen_quests()
        logger.debug(f"Loaded {len(seen_quests)} seen quests from database")
        return seen_quests
        
    except Exception as e:
        logger.error(f"Error loading seen quests: {str(e)}")
        return set()

# Database-focused quest tracking system

def save_seen_quests_with_datetime(seen_quests: Set[str]) -> None:
    """
    Save seen quests with datetime tracking to database.
    
    Args:
        seen_quests: Set of quest IDs to save.
    """
    try:
        if not seen_quests:
            return
        
        # Add each quest to the database
        for quest_id in seen_quests:
            db_add_seen_quest(quest_id)
        
        logger.debug(f"Saved {len(seen_quests)} seen quests to database")
    except Exception as e:
        logger.error(f"Error saving seen quests: {str(e)}")

def save_seen_quests(seen_quests: Set[str]) -> None:
    """
    Save the list of seen quest IDs to file (legacy function for compatibility).
    
    Args:
        seen_quests: Set of quest IDs to save.
    """
    save_seen_quests_with_datetime(seen_quests)

def add_seen_quest(quest_id: str, seen_quests: Set[str]) -> None:
    """
    Add a quest ID to the seen quests set and save to database.
    
    Args:
        quest_id: The quest ID to add.
        seen_quests: The set of seen quest IDs to update.
    """
    seen_quests.add(quest_id)
    db_add_seen_quest(quest_id)

def get_new_quests(quests_data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    Get only new quests that haven't been seen before.
    Syncs database with current API response to remove quests no longer available.
    
    Args:
        quests_data: List of quest data from Discord API.
        
    Returns:
        Tuple containing:
            - List of new quests that haven't been seen
            - Set of all seen quest IDs (including newly added ones)
    """
    # Extract current quest IDs from API response
    current_quest_ids = {quest['config']['id'] for quest in quests_data}
    
    # Get seen quests BEFORE syncing to properly detect new quests
    seen_quests = load_seen_quests()
    new_quests = []
    
    # Check for new quests first
    for quest in quests_data:
        quest_id = quest['config']['id']
        if quest_id not in seen_quests:
            new_quests.append(quest)
            seen_quests.add(quest_id)
            # Add to database immediately
            db_add_seen_quest(quest_id)
    
    # Sync database with current API response AFTER detecting new quests
    db_sync_quests_with_api(current_quest_ids)
    
    return new_quests, seen_quests


def get_quest_id(data_config: Dict[str, Any]) -> str:
    """Extract quest ID from quest configuration."""
    return data_config['id']

def get_quest_start_date(data_config: Dict[str, Any]) -> str:
    """
    Extract and format quest start date in Vietnam timezone.
    
    Args:
        data_config: Quest configuration data.
        
    Returns:
        Formatted start date string in DD-MM-YYYY HH:MM format.
    """
    start_date = data_config['starts_at']
    dt_utc = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    dt_vietnam = dt_utc.astimezone(vietnam_tz)
    return dt_vietnam.strftime('%d-%m-%Y %H:%M')

def get_quest_end_date(data_config: Dict[str, Any]) -> str:
    """
    Extract and format quest end date in Vietnam timezone.
    
    Args:
        data_config: Quest configuration data.
        
    Returns:
        Formatted end date string in DD-MM-YYYY HH:MM format.
    """
    end_date = data_config['expires_at']
    dt_utc = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    dt_vietnam = dt_utc.astimezone(vietnam_tz)
    return dt_vietnam.strftime('%d-%m-%Y %H:%M')

def get_quest_name(data_config: Dict[str, Any]) -> str:
    """Extract quest name from quest configuration."""
    return data_config['messages']['quest_name']

def get_quest_game_title(data_config: Dict[str, Any]) -> str:
    """Extract game title from quest configuration."""
    return data_config['messages']['game_title']

def get_quest_game_publisher(data_config: Dict[str, Any]) -> str:
    """Extract game publisher from quest configuration."""
    return data_config['messages']['game_publisher']

def get_quest_tasks(data_config: Dict[str, Any]) -> List[str]:
    """
    Extract and format quest tasks from quest configuration.
    
    Args:
        data_config: Quest configuration data.
        
    Returns:
        List of formatted task strings with emojis and durations.
    """
    data_config_tasks = data_config['task_config']['tasks']
    tasks = []
    
    for task_key, task_data in data_config_tasks.items():
        event_name = task_data['event_name']
        target_seconds = task_data['target']
        
        # Get emoji for this task type
        emoji = TASK_EMOJI_MAP.get(event_name, '📋')
        
        # Format the task title
        task_title = event_name.replace('_', ' ').title()
        
        # Format time - show seconds if less than 60, otherwise show minutes
        time_str = _format_duration(target_seconds)
        
        # Create the formatted task string
        task_string = f"{emoji} {task_title} For {time_str}"
        tasks.append(task_string)
    
    return tasks

def _format_duration(seconds: int) -> str:
    """
    Format duration from seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds.
        
    Returns:
        Formatted duration string.
    """
    if seconds < 60:
        return f"{seconds} seconds"
    
    target_minutes = seconds / 60
    if target_minutes == int(target_minutes):
        return f"{int(target_minutes)} minutes"
    
    return f"{target_minutes:.1f} minutes"

def get_quest_rewards(data_config: Dict[str, Any]) -> List[str]:
    """
    Extract quest rewards from quest configuration.
    
    Args:
        data_config: Quest configuration data.
        
    Returns:
        List of reward names.
    """
    data_config_rewards = data_config['rewards_config']['rewards']
    return [reward['messages']['name'] for reward in data_config_rewards]

def get_quest_thumbnail_image_url(data_config: Dict[str, Any]) -> Optional[str]:
    """
    Extract quest thumbnail image URL from quest configuration.
    
    Args:
        data_config: Quest configuration data.
        
    Returns:
        Thumbnail image URL if available, None otherwise.
    """
    rewards = data_config['rewards_config']['rewards']
    if not rewards:
        return None
    
    return rewards[0].get("asset")

def get_quest_image_url(data_config: Dict[str, Any]) -> str:
    """Extract quest image URL from quest configuration."""
    return data_config['assets']['hero']

def create_quest_embed(quest_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a Discord embed for a quest in the new format.
    
    Args:
        quest_data: Quest data from Discord API.
        
    Returns:
        Formatted Discord embed dictionary.
    """
    data_config = quest_data['config']
    
    # Extract quest information
    quest_id = get_quest_id(data_config)
    quest_name = get_quest_name(data_config)
    quest_game_title = get_quest_game_title(data_config)
    quest_game_publisher = get_quest_game_publisher(data_config)
    quest_start_date = get_quest_start_date(data_config)
    quest_end_date = get_quest_end_date(data_config)
    quest_tasks = get_quest_tasks(data_config)
    quest_rewards = get_quest_rewards(data_config)
    quest_image_url = get_quest_image_url(data_config)
    quest_thumbnail_image_url = get_quest_thumbnail_image_url(data_config)
    
    # Build image URLs
    image_url = None
    thumbnail_url = None
    
    if quest_image_url:
        image_url = _build_image_url(quest_id, quest_image_url, IMAGE_WIDTH, IMAGE_HEIGHT)
    
    if quest_thumbnail_image_url:
        thumbnail_url = _build_image_url(quest_id, quest_thumbnail_image_url, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
    else:
        # Default thumbnail
        thumbnail_url = f"https://cdn.discordapp.com/assets/content/fb761d9c206f93cd8c4e7301798abe3f623039a4054f2e7accd019e1bb059fc8.webm?format=webp&width={THUMBNAIL_WIDTH}&height={THUMBNAIL_HEIGHT}"
    
    # Create the embed in new format
    embed = {
        "id": 824735312,
        "description": (f"Name: **{quest_name}**\n"
                        f"Publisher: **{quest_game_publisher}**"),
        "fields": [
            {
                "id": 714402766,
                "name": "📆 Starts",
                "value": quest_start_date,
                "inline": True
            },
            {
                "id": 779733495,
                "name": "🗓️ Expires",
                "value": quest_end_date,
                "inline": True
            }
        ],
        "title": quest_game_title,
        "url": f"{QUEST_PAGE_BASE_URL}/{quest_id}",
        "color": get_random_embed_color(),
        "footer": {
            "text": f"ID: {quest_id}"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Add thumbnail if available
    if thumbnail_url:
        embed["thumbnail"] = {
            "url": thumbnail_url
        }
    
    # Add image if available
    if image_url:
        embed["image"] = {
            "url": image_url
        }
    
    # Add tasks if available
    if quest_tasks:
        embed["fields"].append({
            "id": 982926433,
            "name": "📝 Tasks",
            "value": "\n\t".join(quest_tasks),
            "inline": False
        })
    
    # Add rewards if available
    if quest_rewards:
        embed["fields"].append({
            "id": 642050575,
            "name": "🎁 Rewards",
            "value": "\n\t".join(quest_rewards),
            "inline": False
        })
    
    # Add quest link field
    embed["fields"].append({
        "id": 192090086,
        "name": "🔍 View Quest",
        "value": f"[Click here to view quest]({QUEST_PAGE_BASE_URL}/{quest_id})",
        "inline": False
    })
    
    return embed

def _build_image_url(quest_id: str, image_path: str, width: int, height: int) -> str:
    """
    Build Discord CDN image URL with specified dimensions.
    
    Args:
        quest_id: Quest ID for the image path.
        image_path: Relative image path.
        width: Image width.
        height: Image height.
        
    Returns:
        Complete Discord CDN image URL.
    """
    return f"https://cdn.discordapp.com/quests/{quest_id}/{image_path}?format=webp&width={width}&height={height}"

def get_all_quest_embeds() -> List[Dict[str, Any]]:
    """
    Get all quests and return them as Discord embeds in the new format.
    
    Returns:
        List of Discord embed dictionaries for all quests.
    """
    logger.info("Fetching Discord quests for embed generation")
    data = request_quests()
    
    # Check if we have quests data
    if not data or 'quests' not in data or not data['quests']:
        logger.warning("No quests data available for embed generation")
        return []
    
    # Sort quests by start_date (most recent first)
    sorted_quests = sorted(data["quests"], key=lambda quest: quest['config']['starts_at'], reverse=True)
    
    logger.info(f"Generated {len(sorted_quests)} quest embeds")
    return [create_quest_embed(quest) for quest in sorted_quests]

def send_discord_message(webhook_url: str, content: str, embed: Dict[str, Any]) -> requests.Response:
    """
    Send a Discord webhook with an embed in the new format.
    
    Args:
        webhook_url: Discord webhook URL.
        content: Message content.
        embed: Discord embed dictionary to send.
        
    Returns:
        HTTP response from Discord API.
    """
    webhook_data = {
        "content": content,
        "tts": False,
        "embeds": [embed],
        "components": [],
        "actions": {},
        "flags": 0
    }
    
    return requests.post(webhook_url, json=webhook_data)



def send_all_quests_webhook(webhook_url: Optional[str] = None, new_only: bool = True) -> None:
    """
    Send quests as Discord webhooks.
    
    Args:
        webhook_url: Discord webhook URL. Uses WEBHOOK_URL from env if not provided.
        new_only: If True, only send new quests. If False, send all quests.
    """
    if not webhook_url:
        # If not provided, use the list from env
        urls = _parse_webhook_urls(WEBHOOK_URL)
    else:
        urls = [webhook_url]
    if not urls:
        logger.error("No webhook URL provided. Set WEBHOOK_URL in .env file or pass as parameter.")
        return
    
    logger.info("Starting webhook sending process")
    data = request_quests()
    
    # Check if we have quests data
    if not data or 'quests' not in data or not data['quests']:
        logger.warning("No quests data available for webhook sending")
        return
    
    # Sort quests by start_date (most recent first)
    sorted_quests = sorted(data["quests"], key=lambda quest: quest['config']['starts_at'], reverse=True)
    
    if new_only:
        # Get only new quests
        new_quests, _ = get_new_quests(sorted_quests)
        quests_to_send = new_quests
    else:
        quests_to_send = sorted_quests
        logger.info(f"Found {len(sorted_quests)} quests (sending all)")
    
    if not quests_to_send:
        logger.info("No new quests to send!")
        return
    
    for url in urls:
        logger.info(f"Sending webhooks to: {url[:50]}...")
        _send_quests_batch(url, quests_to_send)

def _send_quests_batch(webhook_url: str, quests: List[Dict[str, Any]]) -> None:
    """
    Send a batch of quests as webhooks with rate limiting.
    
    Args:
        webhook_url: Discord webhook URL.
        quests: List of quest data to send.
    """
    successful_sends = 0
    failed_sends = 0
    
    for i, quest in enumerate(quests, 1):
        try:
            content = f"🎉 New Quest Available! 🎉"
            embed = create_quest_embed(quest)
            quest_id = get_quest_id(quest['config'])
            quest_name = get_quest_name(quest['config'])
            
            response = send_discord_message(webhook_url, content, embed)

            if response.status_code == 204:
                successful_sends += 1
                logger.info(f"Quest #{i} sent successfully: {quest_name} (ID: {quest_id})")
            else:
                failed_sends += 1
                logger.error(f"Quest #{i} failed to send. Status: {response.status_code}")
                
        except Exception as e:
            failed_sends += 1
            logger.error(f"Error sending quest #{i}: {str(e)}")
        
        # Rate limiting delay
        time.sleep(WEBHOOK_DELAY_SECONDS)
    
    logger.info(f"Webhook sending completed! Sent {successful_sends} quests successfully, {failed_sends} failed")

def send_single_quest_webhook(quest_id: str, webhook_url: Optional[str] = None) -> None:
    """
    Send a specific quest as a Discord webhook by quest ID.
    
    Args:
        quest_id: Quest ID to send.
        webhook_url: Discord webhook URL. Uses WEBHOOK_URL from env if not provided.
    """
    if not webhook_url:
        webhook_url = WEBHOOK_URL
    
    if not webhook_url:
        logger.error("No webhook URL provided. Set WEBHOOK_URL in .env file or pass as parameter.")
        return
    
    logger.info(f"Fetching quest with ID: {quest_id}")
    data = request_quests()
    
    # Check if we have quests data
    if not data or 'quests' not in data or not data['quests']:
        logger.warning("No quests data available")
        return
    
    # Find the quest by ID
    quest = None
    for q in data["quests"]:
        if q['config']['id'] == quest_id:
            quest = q
            break
    
    if not quest:
        logger.error(f"Quest with ID '{quest_id}' not found.")
        return
    
    try:
        embed = create_quest_embed(quest)
        content = f"🎉 New Quest Available! 🎉"
        response = send_discord_message(webhook_url, content, embed)
        
        if response.status_code == 204:
            quest_name = get_quest_name(quest['config'])
            logger.info(f"Quest sent successfully: {quest_name}")
        else:
            logger.error(f"Quest failed to send. Status: {response.status_code}")
            logger.debug(f"Response: {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending quest: {str(e)}")

def request_quests() -> Dict[str, Any]:
    """
    Fetch quests from Discord API.
    
    Returns:
        Dictionary containing quests data or empty quests list on error.
    """
    headers = _build_discord_headers()
    
    try:
        logger.info("Fetching quests from Discord API")
        response = requests.get(QUESTS_ENDPOINT, headers=headers)
        if response.status_code in (401, 403):
            # Unauthorized or Forbidden -> likely expired/invalid tokens
            problem = "expired" if (DISCORD_AUTHORIZATION or TOKEN_JWT) else "missing"
            alert = (
                f"❌ Discord API auth error ({response.status_code}). Tokens may be {problem}.\n"
                f"Please refresh DISCORD_AUTHORIZATION and TOKEN_JWT in .env."
            )
            logger.error(alert)
            _send_alert(alert)
            return {'quests': []}
        response.raise_for_status()
        
        data = response.json()
        
        # Log response structure
        logger.debug(f"API Response Status: {response.status_code}")
        logger.debug(f"Response Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # Check if quests key exists
        if 'quests' not in data:
            logger.warning(f"No 'quests' key found in response. Available keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            return {'quests': []}
        
        quest_count = len(data.get('quests', []))
        logger.info(f"Successfully fetched {quest_count} quests from Discord API")
        return data

    except requests.exceptions.RequestException as e:
        # Detect common auth-related errors in the exception message
        msg = str(e)
        if any(code in msg for code in ["401", "403", "Unauthorized", "Forbidden"]):
            alert = (
                "❌ Discord API request failed due to authentication (401/403). "
                "Please refresh DISCORD_AUTHORIZATION and TOKEN_JWT."
            )
            logger.error(alert)
            _send_alert(alert)
        else:
            logger.error(f"Request failed: {msg}")
        return {'quests': []}
    except Exception as e:
        logger.error(f"Error parsing response: {str(e)}")
        return {'quests': []}

def _build_discord_headers() -> Dict[str, str]:
    """
    Build headers for Discord API requests.
    
    Returns:
        Dictionary of HTTP headers.
    """
    return {
        'authorization': DISCORD_AUTHORIZATION,
        'referer': 'https://discord.com/discovery/quests',
        'accept': 'application/json',
        'accept-language': 'en-US',
        'x-discord-locale': 'en-US',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9209 Chrome/134.0.6998.205 Electron/35.3.0 Safari/537.36',
        'x-super-properties': TOKEN_JWT,
    }

def main() -> None:
    """
    Main function to fetch and process quests using database tracking.
    """
    logger.debug(f"Script directory: {SCRIPT_DIR}")
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"Database path: {SEEN_QUESTS_FILE}")
    _preflight_check_tokens()
    
    quests = request_quests()
    
    # Check if we have quests data
    if not quests or 'quests' not in quests or not quests['quests']:
        logger.warning("No quests data available or empty quests list")
        return
    
    # Sort quests by start_date (most recent first)
    sorted_quests = sorted(quests["quests"], key=lambda quest: quest['config']['starts_at'], reverse=True)

    return sorted_quests

def cleanup_old_quests() -> None:
    """
    Manually sync quest entries with current API response.
    Removes quests that are no longer available from the API.
    """
    try:
        logger.info("Starting manual sync with current API response...")
        
        # Get current quests from API
        quests = request_quests()
        if not quests or 'quests' not in quests or not quests['quests']:
            logger.warning("No quests data available for sync")
            return
        
        # Extract current quest IDs
        current_quest_ids = {quest['config']['id'] for quest in quests['quests']}
        
        # Sync database with current API response
        db_sync_quests_with_api(current_quest_ids)
        
        # Get final count
        seen_quests = load_seen_quests()
        logger.info(f"Sync completed. {len(seen_quests)} quest entries remain.")
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}")

def reset_seen_quests() -> None:
    """
    Reset the seen quests database (mark all quests as new).
    """
    try:
        db_reset_seen_quests()
        logger.info("Seen quests database reset successfully!")
    except Exception as e:
        logger.error(f"Error resetting seen quests: {str(e)}")

def show_seen_quests() -> None:
    """
    Display the list of seen quest IDs with datetime information.
    """
    try:
        quests_with_datetime = db_get_seen_quests_with_datetime()
        if quests_with_datetime:
            logger.info(f"Previously seen quests ({len(quests_with_datetime)}):")
            for quest_id, seen_at in quests_with_datetime:
                logger.info(f"  - {quest_id} (seen: {seen_at})")
        else:
            logger.info("No quests have been seen yet.")
    except Exception as e:
        logger.error(f"Error displaying seen quests: {str(e)}")



if __name__ == "__main__":
    try:
        # Show seen quests info
        # show_seen_quests()
        
        # Send webhooks if URL is provided
        if WEBHOOK_URL:
            send_all_quests_webhook()
    except KeyboardInterrupt:
        logger.info("Program interrupted by user.")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        logger.info("Goodbye!")