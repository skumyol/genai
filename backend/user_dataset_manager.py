import os
import shutil
from datetime import datetime
from typing import Tuple


BASE_DIR = os.path.dirname(__file__)
# Centralized main dataset (no per-user DBs)
BASE_DB = os.path.join(BASE_DIR, 'databases', 'maingamedata.db')
USERS_DIR = os.path.join(BASE_DIR, 'users')


def get_user_dir(user_id: str) -> str:
    return os.path.join(USERS_DIR, str(user_id))


def get_user_db_path(user_id: str) -> str:
    # Centralized DB path shared across users
    return BASE_DB


def init_user_dataset(user_id: str) -> Tuple[str, bool]:
    """No-op: centralized DB is used for all users.

    Returns (db_path, created=False)
    """
    os.makedirs(os.path.dirname(BASE_DB), exist_ok=True)
    return BASE_DB, False


def switch_memory_agent_to_user(memory_agent, user_id: str) -> str:
    """No-op: centralized DB is used for all users; returns main DB path."""
    return BASE_DB
