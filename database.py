import os
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
from dotenv import load_dotenv

# === .env dan ma'lumotlarni yuklash ===
load_dotenv()

FIREBASE_KEY = os.getenv("FIREBASE_KEY")  # firebase service account key json fayli
FIREBASE_URL = os.getenv("FIREBASE_URL")  # firebase database url

# Firebasega ulanish
cred = credentials.Certificate(FIREBASE_KEY)
firebase_admin.initialize_app(cred, {
    "databaseURL": FIREBASE_URL
})

# === USERS ===
async def add_user(user_id: int):
    """Yangi user qo‘shish"""
    ref = db.reference("users")
    if not ref.child(str(user_id)).get():
        ref.child(str(user_id)).set({
            "id": user_id,
            "joined_at": datetime.now().isoformat()
        })

async def get_user(user_id: int):
    """Bitta userni olish"""
    return db.reference(f"users/{user_id}").get()

async def get_all_users():
    """Barcha userlarni olish"""
    data = db.reference("users").get()
    return list(data.values()) if data else []

# === CODES ===
async def add_kino_code(code: str, server_channel: str, reklama_id: int, post_count: int, title: str):
    """Yangi kod qo‘shish"""
    db.reference("codes").child(str(code)).set({
        "code": code,
        "channel": server_channel,
        "message_id": reklama_id,
        "count": post_count,
        "title": title,
        "stat": {"searched": 0, "viewed": 0}
    })

async def get_kino_by_code(code: str):
    """Kod bo‘yicha kino olish"""
    return db.reference(f"codes/{code}").get()

async def get_all_codes():
    """Barcha kodlarni olish"""
    data = db.reference("codes").get()
    return list(data.values()) if data else []

async def delete_code(code: str):
    """Kod o‘chirish"""
    db.reference(f"codes/{code}").delete()

# === STATS ===
async def increment_stat(code: str, stat_type: str):
    """
    Statistika qo‘shish
    stat_type: "searched" yoki "viewed"
    """
    ref = db.reference(f"codes/{code}/stat/{stat_type}")
    current = ref.get() or 0
    ref.set(current + 1)

async def get_stats(code: str):
    """Kod statistikasi"""
    return db.reference(f"codes/{code}/stat").get() or {}

# === ADMINS ===
async def add_admin(admin_id: int):
    """Admin qo‘shish"""
    db.reference("admins").child(str(admin_id)).set({"id": admin_id})

async def get_admins():
    """Barcha adminlarni olish"""
    data = db.reference("admins").get()
    return [int(x["id"]) for x in data.values()] if data else []

async def delete_admin(admin_id: int):
    """Admin o‘chirish"""
    db.reference(f"admins/{admin_id}").delete()
