"""Configuration constants for Telegram to Obsidian Converter"""

# File handling
MAX_FILENAME_LEN = 80
MAX_SEARCH_INDEX_SAMPLE = 1000

# Media types
MEDIA_KEYS = ['photo', 'video', 'voice', 'sticker', 'audio', 'file', 'document']

# Logging
LOG_FORMAT = "[%(levelname)s] %(asctime)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Cache
CACHE_MAX_SIZE = 10000
CHUNK_SIZE = 8192

# Markdown special characters to escape
MD_ESCAPE_CHARS = r'([\\#*_()|\[\]])'

# Invalid filename characters
INVALID_FILENAME_CHARS = r'[\/*?:"<>|]'

# Time format
TIME_FORMAT = "%H:%M"
DATE_FORMAT = "%Y-%m-%d"

# Default values
DEFAULT_CHAT_NAME = "unknown"
DEFAULT_SENDER = "Unknown"
DEFAULT_TIME = "??:??"