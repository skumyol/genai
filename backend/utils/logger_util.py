"""
Utility for creating and configuring rotating file loggers.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

def setup_rotating_logger(name: str, log_file: str, max_bytes: int = 1024 * 1024, backup_count: int = 3, force: bool = False):
    """
    Sets up a rotating file logger.

    Args:
        name (str): The name of the logger.
        log_file (str): The path to the log file.
        max_bytes (int): The maximum size of the log file in bytes before rotation.
        backup_count (int): The number of backup log files to keep.
        force (bool): If True, will add file handler even if logger has existing handlers
    """
    # Ensure the directory for the log file exists
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Only skip if not forcing and already has handlers
    if not force and logger.hasHandlers():
        return logger

    # Remove existing handlers if forcing
    if force:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    # Create a rotating file handler
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )

    # Create a formatter and set it for the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    return logger
