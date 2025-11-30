
import re
import time
import threading
from collections import deque, defaultdict
from typing import Optional

import telebot
from telebot import apihelper

from config import TOKEN, BOT_USERNAME, STORAGE_CHAT_ID, ADMIN_USER_IDS, OWNER_ID, RATE_LIMIT_MAX_FILES, RATE_LIMIT_WINDOW_SEC, EXPIRE_CHECK_INTERVAL_SEC, DB_JSON_PATH, DEBUG
from database import Database
from utils import gen_code, now_str, parse_expiry, detect_category, format_entry_line

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db = Database(DB_JSON_PATH)

# Rate limiter: user_id -> deque of timestamps
rate_buckets = defaultdict(lambda: deque(maxlen=RATE_LIMIT_MAX_FILES))

GET_CMD_REGEX = re.compile(r'^/get_([a-zA-Z0-9]+)$')

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

def send_error(chat_id: int, text: str = '❌ Error: File not found or expired.'):
    try:
        bot.send_message(chat_id, text)
    except Exception:
        pass

def deep_link_for(code: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=get_{code}"

def save_file_entry(user_id: int, file_type: str, file_id: str, storage_message_id: int, mime_type: Optional[str] = None, file_name: Optional[str] = None, caption: Optional[str] = None) -> str:
    # ensure unique code
    code = gen_code()
    while db.has_code(code):
        code = gen_code()
    entry = {
        'file_id': file_id,
        'file_type': file_type,
        'uploader': user_id,
        'uploaded_at': now_str(),
        'expires_at': None,
        'storage_message_id': storage_message_id,
        'category': detect_category(file_type, mime_type, file_name),
        'locked_to': None,
        'file_name': file_name,
        'caption': caption,
        'mime_type': mime_type,
    }
    db.put_code(code, entry)
    db.inc_upload(user_id, 1)
    return code

def try_send_by_file_id(chat_id: int, entry: dict) -> bool:
    ft = entry.get('file_type')
    fid = entry.get('file_id')
    cap = entry.get('caption')
    try:
        if ft == 'photo':
            bot.send_photo(chat_id, fid, caption=cap)
        elif ft == 'video':
            bot.send_video(chat_id, fid, caption=cap)
        elif ft == 'document':
            bot.send_document(chat_id, fid, caption=cap)
        elif ft == 'audio':
            bot.send_audio(chat_id, fid, caption=cap)
        elif ft == 'voice':
            bot.send_voice(chat_id, fid, caption=cap)
        elif ft == 'animation':
            bot.send_animation(chat_id, fid, caption=cap)
        elif ft == 'sticker':
            bot.send_sticker(chat_id, fid)
        else:
            # Fallback
            bot.send_document(chat_id, fid, caption=cap)
        return True
    except apihelper.ApiTelegramException:
        return False
    except Exception:
        return False

def send_from_storage(chat_id: int, entry: dict) -> bool:
    try:
        smid = entry.get('storage_message_id')
        bot.copy_message(chat_id, STORAGE_CHAT_ID, smid)
        return True
    except apihelper.ApiTelegramException:
        return False
    except Exception:
        return False

def handle_retrieval(message, code: str):
    entry = db.get_code(code)
    if not entry:
        send_error(message.chat.id)
        return

    # Expiry check
    if db.is_expired(entry):
        send_error(message.chat.id)
        return

    # Lock check
    locked_to = entry.get('locked_to')
    if locked_to and (message.from_user is None or message.from_user.id != locked_to):
        bot.send_message(message.chat.id, '🔒 This file is locked to its owner and cannot be retrieved by you.')
        return

    ok = try_send_by_file_id(message.chat.id, entry)
    if not ok:
        # Fallback to copy from storage
        ok = send_from_storage(message.chat.id, entry)
    if ok:
        db.inc_retrieved(message.from_user.id if message.from_user else 0, 1)
    else:
        send_error(message.chat.id, '❌ Error: File could not be sent. It may be corrupted or unavailable.')

# --- Command Handlers ---
@bot.message_handler(commands=['start'])
def on_start(message):
    text = (message.text or '')
    # Deep-link payload: '/start get_<code>' or '/start get_<code>'
    m = re.search(r'get_([a-zA-Z0-9]+)', text)
    if m:
        code = m.group(1)
        handle_retrieval(message, code)
        return
    bot.send_message(message.chat.id,
        """
<b>Welcome!</b>
Send me any file/media (photo, video, audio, document, zip, pdf, etc.) and I'll save it securely.
I'll reply with a unique code and a retrieval link.

Retrieve: <code>/get_&lt;code&gt;</code> or tap the link I provide.

Useful commands:
• /my_files — list your files
• /list images|videos|audio|documents|zip|other — list by category
• /list user &lt;user_id&gt; — list files by user
• /search &lt;keyword&gt; — search by type/name/caption
• /lock_code &lt;code&gt; — lock a code to your account
• /rename_code &lt;old&gt; &lt;new&gt; — rename your code
• /expire &lt;code&gt; &lt;duration|never|delete&gt; — set expiry (e.g., 24h, 7d)

Admin only:
• /all_files_count, /all_users_count
• /delete_code &lt;code&gt;
• /delete_user &lt;user_id&gt;
• /storage_clean
• /broadcast &lt;text&gt;
        """
    )

@bot.message_handler(func=lambda m: bool(GET_CMD_REGEX.match(m.text or '')))
def on_get_code_style(message):
    code = GET_CMD_REGEX.match(message.text).group(1)
    handle_retrieval(message, code)

@bot.message_handler(commands=['get'])
def on_get(message):
    parts = (message.text or '').strip().split()
    if len(parts) >= 2:
        code = parts[1]
        handle_retrieval(message, code)
    else:
        send_error(message.chat.id, 'Usage: /get <code> or /get_<code>')

@bot.message_handler(commands=['my_files'])
def on_my_files(message):
    uid = message.from_user.id
    items = db.list_by_user(uid, limit=50)
    if not items:
        bot.send_message(message.chat.id, 'You have not uploaded any files yet.')
        return
    lines = [format_entry_line(it['code'], it) for it in items]
    bot.send_message(message.chat.id, '<b>Your files:</b>\n' + '\n'.join(lines[:100]))

@bot.message_handler(commands=['list'])
def on_list(message):
    parts = (message.text or '').strip().lower().split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Usage: /list images|videos|audio|documents|zip|other OR /list user <user_id>')
        return
    if parts[1] == 'user' and len(parts) >= 3:
        try:
            uid = int(parts[2])
        except Exception:
            send_error(message.chat.id, 'Invalid user id.')
            return
        items = db.list_by_user(uid)
    else:
        cat_map = {
            'images': 'Images', 'videos': 'Videos', 'audio': 'Audio',
            'documents': 'Documents', 'zip': 'Zip', 'other': 'Other'
        }
        category = cat_map.get(parts[1])
        if not category:
            bot.send_message(message.chat.id, 'Unknown category. Try: images, videos, audio, documents, zip, other')
            return
        items = db.list_by_category(category)

    if not items:
        bot.send_message(message.chat.id, 'No files found.')
    else:
        lines = [format_entry_line(it['code'], it) for it in items]
        bot.send_message(message.chat.id, '<b>List:</b>\n' + '\n'.join(lines[:100]))

@bot.message_handler(commands=['search'])
def on_search(message):
    parts = (message.text or '').strip().split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Usage: /search <keyword>')
        return
    items = db.search_codes(parts[1])
    if not items:
        bot.send_message(message.chat.id, 'No results.')
        return
    lines = [format_entry_line(it['code'], it) for it in items]
    bot.send_message(message.chat.id, '<b>Results:</b>\n' + '\n'.join(lines[:100]))

@bot.message_handler(commands=['lock_code'])
def on_lock_code(message):
    parts = (message.text or '').strip().split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Usage: /lock_code <code>')
        return
    code = parts[1]
    entry = db.get_code(code)
    if not entry:
        send_error(message.chat.id)
        return
    if entry.get('uploader') != message.from_user.id and not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, 'Only the uploader or admin can lock this code.')
        return
    db.update_code(code, {'locked_to': message.from_user.id})
    bot.send_message(message.chat.id, f'🔒 Code <code>{code}</code> locked to you.')

@bot.message_handler(commands=['rename_code'])
def on_rename_code(message):
    parts = (message.text or '').strip().split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, 'Usage: /rename_code <old> <new>')
        return
    old, new = parts[1], parts[2]
    entry = db.get_code(old)
    if not entry:
        send_error(message.chat.id)
        return
    if db.has_code(new):
        bot.send_message(message.chat.id, 'New code already exists. Choose a different code.')
        return
    if entry.get('uploader') != message.from_user.id and not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, 'Only the uploader or admin can rename this code.')
        return
    ok = db.rename_code(old, new)
    if ok:
        bot.send_message(message.chat.id, f'✅ Renamed <code>{old}</code> → <code>{new}</code>')
    else:
        send_error(message.chat.id, 'Could not rename code.')

@bot.message_handler(commands=['expire'])
def on_expire(message):
    # /expire <code> <duration|never|delete>
    parts = (message.text or '').strip().split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, 'Usage: /expire <code> <24h|7d|30m|never|delete>')
        return
    code, val = parts[1], parts[2]
    entry = db.get_code(code)
    if not entry:
        send_error(message.chat.id)
        return
    # Only uploader or admin can expire
    if entry.get('uploader') != message.from_user.id and not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, 'Only the uploader or admin can set expiry for this code.')
        return
    dt = parse_expiry(val)
    if dt == 'delete':
        # delete now and remove from storage
        try:
            bot.delete_message(STORAGE_CHAT_ID, entry.get('storage_message_id'))
        except Exception:
            pass
        db.delete_code(code)
        bot.send_message(message.chat.id, f'🗑️ Deleted code <code>{code}</code> and removed from storage.')
        return
    if dt is None:
        db.update_code(code, {'expires_at': None})
        bot.send_message(message.chat.id, f'⏳ Expiry for <code>{code}</code> set to never.')
    else:
        db.update_code(code, {'expires_at': dt})
        bot.send_message(message.chat.id, f'⏳ Expiry for <code>{code}</code> set to {dt}.')

@bot.message_handler(commands=['all_files_count'])
def on_files_count(message):
    if not is_admin(message.from_user.id):
        return
    files, users = db.counts()
    bot.send_message(message.chat.id, f'Total files: <b>{files}</b>')

@bot.message_handler(commands=['all_users_count'])
def on_users_count(message):
    if not is_admin(message.from_user.id):
        return
    files, users = db.counts()
    bot.send_message(message.chat.id, f'Total users: <b>{users}</b>')

@bot.message_handler(commands=['delete_code'])
def on_delete_code(message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or '').strip().split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Usage: /delete_code <code>')
        return
    code = parts[1]
    entry = db.get_code(code)
    if not entry:
        send_error(message.chat.id)
        return
    try:
        bot.delete_message(STORAGE_CHAT_ID, entry.get('storage_message_id'))
    except Exception:
        pass
    db.delete_code(code)
    bot.send_message(message.chat.id, f'Deleted code <code>{code}</code>.')

@bot.message_handler(commands=['delete_user'])
def on_delete_user(message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or '').strip().split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Usage: /delete_user <user_id>')
        return
    try:
        uid = int(parts[1])
    except Exception:
        send_error(message.chat.id, 'Invalid user id.')
        return
    db.delete_user(uid)
    bot.send_message(message.chat.id, f'Deleted user <code>{uid}</code> stats. (Files remain)')

@bot.message_handler(commands=['storage_clean'])
def on_storage_clean(message):
    if not is_admin(message.from_user.id):
        return
    # Remove expired files and delete from storage
    removed = 0
    # Create a copy of codes list to avoid mutation during iteration
    codes_snapshot = list(db.data.get('codes', {}).keys())
    for code in codes_snapshot:
        entry = db.get_code(code)
        if entry and db.is_expired(entry):
            try:
                bot.delete_message(STORAGE_CHAT_ID, entry.get('storage_message_id'))
            except Exception:
                pass
            db.delete_code(code)
            removed += 1
    bot.send_message(message.chat.id, f'Cleaned expired files: <b>{removed}</b>')

@bot.message_handler(commands=['broadcast'])
def on_broadcast(message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or '').strip().split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Usage: /broadcast <message>')
        return
    text = parts[1]
    sent = 0
    for uid in db.all_users():
        try:
            bot.send_message(uid, text)
            sent += 1
            time.sleep(0.03)  # small delay to reduce flood risk
        except Exception:
            pass
    bot.send_message(message.chat.id, f'Broadcast sent to <b>{sent}</b> users.')

# --- Media/File Handlers with Anti-Spam ---
def check_rate_limit(user_id: int) -> bool:
    dq = rate_buckets[user_id]
    now = time.time()
    # purge old entries beyond window
    while dq and (now - dq[0] > RATE_LIMIT_WINDOW_SEC):
        dq.popleft()
    if len(dq) >= RATE_LIMIT_MAX_FILES:
        return False
    dq.append(now)
    return True

def process_incoming_file(message, file_type: str):
    uid = message.from_user.id if message.from_user else 0
    if not check_rate_limit(uid):
        bot.send_message(message.chat.id, '⚠️ Slow down! You are sending too fast.')
        return

    # Copy to storage group/channel
    try:
        copied = bot.copy_message(STORAGE_CHAT_ID, message.chat.id, message.message_id)
        storage_message_id = copied.message_id if hasattr(copied, 'message_id') else copied
    except Exception as e:
        send_error(message.chat.id, '❌ Error: Could not save to storage group. Make sure the bot is admin there.')
        return

    # Extract file_id and extra
    file_id = None
    mime_type = None
    file_name = None
    caption = message.caption

    if file_type == 'photo' and message.photo:
        # choose largest
        photo = max(message.photo, key=lambda p: p.file_size or 0)
        file_id = photo.file_id
    elif file_type == 'video' and message.video:
        file_id = message.video.file_id
        mime_type = message.video.mime_type
    elif file_type == 'document' and message.document:
        file_id = message.document.file_id
        mime_type = message.document.mime_type
        file_name = message.document.file_name
    elif file_type == 'audio' and message.audio:
        file_id = message.audio.file_id
        mime_type = message.audio.mime_type
        file_name = message.audio.file_name
    elif file_type == 'voice' and message.voice:
        file_id = message.voice.file_id
        mime_type = None
    elif file_type == 'animation' and message.animation:
        file_id = message.animation.file_id
        mime_type = message.animation.mime_type
    elif file_type == 'sticker' and message.sticker:
        file_id = message.sticker.file_id
    else:
        # fallback: treat as document
        if message.document:
            file_id = message.document.file_id
            mime_type = message.document.mime_type
            file_name = message.document.file_name
            file_type = 'document'

    if not file_id:
        send_error(message.chat.id, '❌ Error: Could not capture file_id.')
        return

    code = save_file_entry(uid, file_type, file_id, storage_message_id, mime_type, file_name, caption)
    link = deep_link_for(code)
    bot.send_message(message.chat.id, f'✅ Saved!\nCode: <code>{code}</code>\nRetrieve: <code>/get_{code}</code>\nLink: {link}')

# Register media handlers
@bot.message_handler(content_types=['photo'])
def on_photo(message):
    process_incoming_file(message, 'photo')

@bot.message_handler(content_types=['video'])
def on_video(message):
    process_incoming_file(message, 'video')

@bot.message_handler(content_types=['document'])
def on_document(message):
    process_incoming_file(message, 'document')

@bot.message_handler(content_types=['audio'])
def on_audio(message):
    process_incoming_file(message, 'audio')

@bot.message_handler(content_types=['voice'])
def on_voice(message):
    process_incoming_file(message, 'voice')

@bot.message_handler(content_types=['animation'])
def on_animation(message):
    process_incoming_file(message, 'animation')

@bot.message_handler(content_types=['sticker'])
def on_sticker(message):
    process_incoming_file(message, 'sticker')

# --- Background expiry checker ---
def expiry_worker():
    while True:
        try:
            # Snapshot codes to avoid dict change during iteration
            codes = list(db.data.get('codes', {}).keys())
            for code in codes:
                entry = db.get_code(code)
                if not entry:
                    continue
                if db.is_expired(entry):
                    try:
                        bot.delete_message(STORAGE_CHAT_ID, entry.get('storage_message_id'))
                    except Exception:
                        pass
                    db.delete_code(code)
            if DEBUG:
                print('[ExpiryWorker] Sweep complete')
        except Exception as e:
            if DEBUG:
                print('[ExpiryWorker] Exception', e)
        time.sleep(EXPIRE_CHECK_INTERVAL_SEC)

threading.Thread(target=expiry_worker, daemon=True).start()

if __name__ == '__main__':
    print('Bot starting...')
    bot.infinity_polling(skip_pending=True, timeout=60)
