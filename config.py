"""Configuration constants for Telegram to Obsidian Converter"""

# File handling
MAX_FILENAME_LEN = 80
MAX_SEARCH_INDEX_SAMPLE = 1000
MAX_MESSAGE_LEN = 10000  # Обрезать слишком длинные сообщения

# Media types
MEDIA_KEYS = ['photo', 'video', 'voice', 'sticker', 'audio', 'file', 'document']
MEDIA_EXTENSIONS = {'.jpg', '.png', '.mp4', '.mp3', '.ogg', '.webp', '.gif', '.pdf'}

# Logging
LOG_FORMAT = "[%(levelname)s] %(asctime)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Cache
CACHE_MAX_SIZE = 10000
CHUNK_SIZE = 8192

# Markdown special characters to escape
MD_ESCAPE_CHARS = r'([\\#*_()|\[\]'])'

# Invalid filename characters
INVALID_FILENAME_CHARS = r'[\\/*?:"<>|]'

# Reserved Windows filenames
RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}

# Excluded directories for media indexing
EXCLUDED_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', '.idea', '.vscode'}

# Time format
TIME_FORMAT = "%H:%M"
DATE_FORMAT = "%Y-%m-%d"

# Default values
DEFAULT_CHAT_NAME = "unknown"
DEFAULT_SENDER = "Unknown"
DEFAULT_TIME = "??:??"