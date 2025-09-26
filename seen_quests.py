import sqlite3
import time
import os
from typing import Set, List, Tuple
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'seen_quests.db')

def get_connection():
    """Get a database connection."""
    # Ensure the db directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.execute('''
    CREATE TABLE IF NOT EXISTS seen_quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quest_id TEXT NOT NULL UNIQUE,
        seen_at TEXT NOT NULL
    )
    ''')
    return conn

def add_seen_quest(quest_id: str) -> None:
    """Add a quest ID to the seen quests database."""
    conn = get_connection()
    try:
        conn.execute('INSERT OR REPLACE INTO seen_quests (quest_id, seen_at) VALUES (?, ?)', 
                    (quest_id, datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()

def get_seen_quests() -> Set[str]:
    """Get all seen quest IDs as a set."""
    conn = get_connection()
    try:
        cursor = conn.execute('SELECT quest_id FROM seen_quests')
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()

def get_seen_quests_with_datetime() -> List[Tuple[str, str]]:
    """Get all seen quest IDs with their datetime as a list of tuples."""
    conn = get_connection()
    try:
        cursor = conn.execute('SELECT quest_id, seen_at FROM seen_quests ORDER BY seen_at DESC')
        return cursor.fetchall()
    finally:
        conn.close()

def cleanup_old_quests(days: int = 180) -> None:
    """Remove quest entries older than specified days."""
    conn = get_connection()
    try:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = conn.execute('DELETE FROM seen_quests WHERE seen_at < ?', (cutoff_date,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def reset_seen_quests() -> None:
    """Remove all seen quest entries."""
    conn = get_connection()
    try:
        conn.execute('DELETE FROM seen_quests')
        conn.commit()
    finally:
        conn.close()

# Migration function removed - database is now the primary storage

def sync_quests_with_api(current_quest_ids: Set[str]) -> None:
    """
    Sync the database with current quest IDs from API.
    Remove quest IDs that are no longer in the API response.
    
    Args:
        current_quest_ids: Set of quest IDs currently available from API.
    """
    conn = get_connection()
    try:
        # Get all quest IDs currently in database
        cursor = conn.execute('SELECT quest_id FROM seen_quests')
        db_quest_ids = {row[0] for row in cursor.fetchall()}
        
        # Find quest IDs to remove (in database but not in API)
        quests_to_remove = db_quest_ids - current_quest_ids
        
        # Remove quests that are no longer in API
        if quests_to_remove:
            placeholders = ','.join('?' * len(quests_to_remove))
            conn.execute(f'DELETE FROM seen_quests WHERE quest_id IN ({placeholders})', 
                        list(quests_to_remove))
            conn.commit()
            print(f"Removed {len(quests_to_remove)} quest IDs that are no longer in API")
        
        # Add new quest IDs from API (if any)
        new_quest_ids = current_quest_ids - db_quest_ids
        for quest_id in new_quest_ids:
            conn.execute('INSERT OR REPLACE INTO seen_quests (quest_id, seen_at) VALUES (?, ?)', 
                        (quest_id, datetime.now().isoformat()))
        
        if new_quest_ids:
            conn.commit()
            print(f"Added {len(new_quest_ids)} new quest IDs from API")
            
    finally:
        conn.close()