"""Utility functions for Telegram to Obsidian Converter"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from config import (
    CHUNK_SIZE,
    INVALID_FILENAME_CHARS,
    MAX_FILENAME_LEN,
    MD_ESCAPE_CHARS,
)


def sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters and limiting length."""
    if not name or not isinstance(name, str):
        name = "unknown"
    
    # Remove invalid characters
    name = re.sub(INVALID_FILENAME_CHARS, '_', name)
    
    # Limit length
    name = name[:MAX_FILENAME_LEN]
    
    # Remove trailing dots and spaces (Windows compatibility)
    name = name.rstrip('. ')
    
    return name if name else "unnamed"


def escape_md(text: str) -> str:
    """Escape Markdown special characters in text."""
    if not text or not isinstance(text, str):
        return ""
    
    return re.sub(MD_ESCAPE_CHARS, r'\\\1', text)


def hash_file(path: Path) -> Optional[str]:
    """Calculate MD5 hash of a file."""
    try:
        h = hashlib.md5()
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logging.error(f"Failed to hash file {path}: {e}")
        return None


def setup_logger(verbose: bool, log_file: Optional[str] = None) -> None:
    """Configure logging with optional file output."""
    from config import LOG_FORMAT, LOG_DATE_FORMAT
    
    level = logging.DEBUG if verbose else logging.INFO
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    console_handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logging.warning(f"Failed to create log file: {e}")