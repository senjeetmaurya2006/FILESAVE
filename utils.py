
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple

CATEGORIES = {
    'photo': 'Images',
    'image': 'Images',
    'video': 'Videos',
    'animation': 'Videos',
    'audio': 'Audio',
    'voice': 'Audio',
    'document': 'Documents',
    'sticker': 'Other',
}

ZIP_MIME_TYPES = {'application/zip', 'application/x-zip-compressed'}

def gen_code(length: int = 6) -> str:
    # Alphanumeric code for better uniqueness
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def now_str() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def parse_expiry(value: str) -> Optional[str]:
    """Parse human duration like '24h', '7d', '30m', 'never'. Return datetime string or None.
    If value == 'delete', returns the string 'delete' to signal deletion.
    """
    v = (value or '').strip().lower()
    if v in ('none', 'never', 'nil', 'null', ''):
        return None
    if v == 'delete':
        return 'delete'
    try:
        if v.endswith('h'):
            hours = int(v[:-1])
            dt = datetime.now() + timedelta(hours=hours)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        elif v.endswith('d'):
            days = int(v[:-1])
            dt = datetime.now() + timedelta(days=days)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        elif v.endswith('m'):
            minutes = int(v[:-1])
            dt = datetime.now() + timedelta(minutes=minutes)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Fallback: treat as minutes if numeric
            minutes = int(v)
            dt = datetime.now() + timedelta(minutes=minutes)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return None

def detect_category(file_type: str, mime_type: Optional[str], file_name: Optional[str]) -> str:
    ft = (file_type or '').lower()
    if ft in CATEGORIES:
        cat = CATEGORIES[ft]
    else:
        cat = 'Other'

    # Special case: zip
    if mime_type and mime_type.lower() in ZIP_MIME_TYPES:
        return 'Zip'
    if file_name and file_name.lower().endswith('.zip'):
        return 'Zip'
    return cat

def format_entry_line(code: str, entry: dict) -> str:
    exp = entry.get('expires_at') or 'never'
    cat = entry.get('category') or 'Other'
    name = entry.get('file_name') or ''
    return f"{code} | {entry.get('file_type')} | {cat} | exp: {exp} | {name}"
