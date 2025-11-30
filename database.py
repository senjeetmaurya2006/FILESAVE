
import json
import os
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime

class Database:
    """JSON-backed database with a future-friendly interface that can be
    swapped to SQLite without changing bot logic.
    Schema (JSON):
    {
      "codes": {
        "12837": {
          "file_id": "...",
          "file_type": "photo",
          "uploader": 12345566,
          "uploaded_at": "2025-11-29 12:30",
          "expires_at": null,
          "storage_message_id": 123,
          "category": "Images",
          "locked_to": null,
          "file_name": null,
          "caption": null,
          "mime_type": null
        }
      },
      "users": {
        "12345566": {
          "uploads": 55,
          "retrieved": 210
        }
      }
    }
    """

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self.data = {"codes": {}, "users": {}}
        self._load()

    def _load(self):
        with self._lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, 'r', encoding='utf-8') as f:
                        self.data = json.load(f)
                except Exception:
                    # If corrupt, back it up and start fresh
                    try:
                        os.rename(self.path, self.path + '.corrupt.bak')
                    except Exception:
                        pass
                    self.data = {"codes": {}, "users": {}}
                    self._save()
            else:
                self._save()

    def _save(self):
        with self._lock:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)

    # --- Code entries ---
    def has_code(self, code: str) -> bool:
        with self._lock:
            return code in self.data["codes"]

    def put_code(self, code: str, entry: Dict[str, Any]):
        with self._lock:
            self.data["codes"][code] = entry
            self._save()

    def get_code(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.data["codes"].get(code)

    def update_code(self, code: str, patch: Dict[str, Any]):
        with self._lock:
            if code in self.data["codes"]:
                self.data["codes"][code].update(patch)
                self._save()

    def delete_code(self, code: str):
        with self._lock:
            if code in self.data["codes"]:
                del self.data["codes"][code]
                self._save()

    def rename_code(self, old: str, new: str) -> bool:
        with self._lock:
            if old in self.data["codes"] and new not in self.data["codes"]:
                self.data["codes"][new] = self.data["codes"].pop(old)
                self._save()
                return True
            return False

    def list_by_category(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                {"code": c, **e} for c, e in self.data["codes"].items()
                if e.get("category") == category
            ]
            results.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
            return results[:limit]

    def list_by_user(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                {"code": c, **e} for c, e in self.data["codes"].items()
                if e.get("uploader") == user_id
            ]
            results.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
            return results[:limit]

    def search_codes(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        q = query.lower()
        with self._lock:
            results = []
            for c, e in self.data["codes"].items():
                hay = ' '.join([
                    c,
                    e.get("file_type") or '',
                    e.get("file_name") or '',
                    e.get("caption") or '',
                    e.get("mime_type") or '',
                ]).lower()
                if q in hay:
                    z = {"code": c, **e}
                    results.append(z)
            results.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
            return results[:limit]

    # --- Users ---
    def ensure_user(self, user_id: int):
        uid = str(user_id)
        with self._lock:
            if uid not in self.data["users"]:
                self.data["users"][uid] = {"uploads": 0, "retrieved": 0}
                self._save()

    def inc_upload(self, user_id: int, by: int = 1):
        uid = str(user_id)
        with self._lock:
            self.ensure_user(user_id)
            self.data["users"][uid]["uploads"] += by
            self._save()

    def inc_retrieved(self, user_id: int, by: int = 1):
        uid = str(user_id)
        with self._lock:
            self.ensure_user(user_id)
            self.data["users"][uid]["retrieved"] += by
            self._save()

    def delete_user(self, user_id: int):
        uid = str(user_id)
        with self._lock:
            if uid in self.data["users"]:
                del self.data["users"][uid]
                self._save()

    def all_users(self) -> List[int]:
        with self._lock:
            return [int(uid) for uid in self.data["users"].keys()]

    def counts(self):
        with self._lock:
            return len(self.data["codes"]), len(self.data["users"])  # files, users

    # Utility
    def is_expired(self, entry: Dict[str, Any]) -> bool:
        exp = entry.get("expires_at")
        if not exp:
            return False
        try:
            dt = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S")
            return dt <= datetime.now()
        except Exception:
            return False

import json
import os
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime

class Database:
    """JSON-backed database with a future-friendly interface that can be
    swapped to SQLite without changing bot logic.
    Schema (JSON):
    {
      "codes": {
        "12837": {
          "file_id": "...",
          "file_type": "photo",
          "uploader": 12345566,
          "uploaded_at": "2025-11-29 12:30",
          "expires_at": null,
          "storage_message_id": 123,
          "category": "Images",
          "locked_to": null,
          "file_name": null,
          "caption": null,
          "mime_type": null
        }
      },
      "users": {
        "12345566": {
          "uploads": 55,
          "retrieved": 210
        }
      }
    }
    """

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self.data = {"codes": {}, "users": {}}
        self._load()

    def _load(self):
        with self._lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, 'r', encoding='utf-8') as f:
                        self.data = json.load(f)
                except Exception:
                    # If corrupt, back it up and start fresh
                    try:
                        os.rename(self.path, self.path + '.corrupt.bak')
                    except Exception:
                        pass
                    self.data = {"codes": {}, "users": {}}
                    self._save()
            else:
                self._save()

    def _save(self):
        with self._lock:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)

    # --- Code entries ---
    def has_code(self, code: str) -> bool:
        with self._lock:
            return code in self.data["codes"]

    def put_code(self, code: str, entry: Dict[str, Any]):
        with self._lock:
            self.data["codes"][code] = entry
            self._save()

    def get_code(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.data["codes"].get(code)

    def update_code(self, code: str, patch: Dict[str, Any]):
        with self._lock:
            if code in self.data["codes"]:
                self.data["codes"][code].update(patch)
                self._save()

    def delete_code(self, code: str):
        with self._lock:
            if code in self.data["codes"]:
                del self.data["codes"][code]
                self._save()

    def rename_code(self, old: str, new: str) -> bool:
        with self._lock:
            if old in self.data["codes"] and new not in self.data["codes"]:
                self.data["codes"][new] = self.data["codes"].pop(old)
                self._save()
                return True
            return False

    def list_by_category(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                {"code": c, **e} for c, e in self.data["codes"].items()
                if e.get("category") == category
            ]
            results.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
            return results[:limit]

    def list_by_user(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                {"code": c, **e} for c, e in self.data["codes"].items()
                if e.get("uploader") == user_id
            ]
            results.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
            return results[:limit]

    def search_codes(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        q = query.lower()
        with self._lock:
            results = []
            for c, e in self.data["codes"].items():
                hay = ' '.join([
                    c,
                    e.get("file_type") or '',
                    e.get("file_name") or '',
                    e.get("caption") or '',
                    e.get("mime_type") or '',
                ]).lower()
                if q in hay:
                    z = {"code": c, **e}
                    results.append(z)
            results.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
            return results[:limit]

    # --- Users ---
    def ensure_user(self, user_id: int):
        uid = str(user_id)
        with self._lock:
            if uid not in self.data["users"]:
                self.data["users"][uid] = {"uploads": 0, "retrieved": 0}
                self._save()

    def inc_upload(self, user_id: int, by: int = 1):
        uid = str(user_id)
        with self._lock:
            self.ensure_user(user_id)
            self.data["users"][uid]["uploads"] += by
            self._save()

    def inc_retrieved(self, user_id: int, by: int = 1):
        uid = str(user_id)
        with self._lock:
            self.ensure_user(user_id)
            self.data["users"][uid]["retrieved"] += by
            self._save()

    def delete_user(self, user_id: int):
        uid = str(user_id)
        with self._lock:
            if uid in self.data["users"]:
                del self.data["users"][uid]
                self._save()

    def all_users(self) -> List[int]:
        with self._lock:
            return [int(uid) for uid in self.data["users"].keys()]

    def counts(self):
        with self._lock:
            return len(self.data["codes"]), len(self.data["users"])  # files, users

    # Utility
    def is_expired(self, entry: Dict[str, Any]) -> bool:
        exp = entry.get("expires_at")
        if not exp:
            return False
        try:
            dt = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S")
            return dt <= datetime.now()
        except Exception:
            return False
