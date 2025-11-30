
"""
Configuration for the Telegram File Saver Bot
- Keep secrets out of source control. You can override these via environment variables.
- STORAGE_CHAT_ID: Your private storage supergroup/channel ID. For channels/supergroups, it usually starts with -100...
"""
import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

TOKEN = os.getenv('BOT_TOKEN', '7777682673:AAHW4eHWndoPGS0kuz6sqNvBJ_Gw3IV1tfE')
BOT_USERNAME = os.getenv('BOT_USERNAME', 'mypersonalgyan_bot')
# If your storage is a supergroup/channel, ensure the -100 prefix.
STORAGE_CHAT_ID = int(os.getenv('STORAGE_CHAT_ID', '-1003421567383'))

# Owner/Admins
OWNER_ID = int(os.getenv('OWNER_ID', '1972024725'))
ADMIN_USER_IDS = set([OWNER_ID])

# Rate limit: max files per window
RATE_LIMIT_MAX_FILES = int(os.getenv('RATE_LIMIT_MAX_FILES', '3'))
RATE_LIMIT_WINDOW_SEC = int(os.getenv('RATE_LIMIT_WINDOW_SEC', '10'))

# Expiry check interval (seconds)
EXPIRE_CHECK_INTERVAL_SEC = int(os.getenv('EXPIRE_CHECK_INTERVAL_SEC', '600'))  # 10 minutes

# Database path
DB_JSON_PATH = os.getenv('DB_JSON_PATH', 'db.json')

# Optional: turn on verbose logging
DEBUG = os.getenv('DEBUG', '0') == '1'
