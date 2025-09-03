import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

# 🔑 Firebase ulash
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://YOUR_PROJECT_ID-default-rtdb.REGION.firebasedatabase.app/"
})

# ============================
# === USERS FUNKSIYALARI ===
# ============================

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
    ref = db.reference(f"users/{user_id}")
    return ref.get()

async def get_all_users():
    """Barcha userlarni olish"""
    ref = db.reference("users")
    data = ref.get()
    return list(data.values()) if data else []

async def delete_user(user_id: int):
    """Userni o‘chirish"""
    ref = db.reference(f"users/{user_id}")
    ref.delete()

# ============================
# === KODLAR (kino_codes) ===
# ============================

async def add_kino_code(code, server_channel, reklama_id, post_count, title):
    """Yangi kod qo‘shish"""
    ref = db.reference("codes")
    ref.child(str(code)).set({
        "code": code,
        "channel": server_channel,
        "message_id": reklama_id,
        "count": post_count,
        "title": title,
        "stat": {"searched": 0, "viewed": 0}
    })

async def get_kino_by_code(code: str):
    """Kod bo‘yicha kino olish"""
    ref = db.reference(f"codes/{code}")
    return ref.get()

async def get_all_codes():
    """Barcha kodlarni olish"""
    ref = db.reference("codes")
    data = ref.get()
    return list(data.values()) if data else []

async def delete_kino_code(code: str):
    """Kod o‘chirish"""
    ref = db.reference(f"codes/{code}")
    ref.delete()

async def update_kino_field(code: str, field: str, value):
    """Kod ichidagi maydonni yangilash"""
    ref = db.reference(f"codes/{code}/{field}")
    ref.set(value)

# ============================
# === STATISTIKA FUNKSIYALARI ===
# ============================

async def increment_stat(code: str, stat_type: str):
    """Statistika qo‘shish (searched yoki viewed)"""
    ref = db.reference(f"codes/{code}/stat/{stat_type}")
    current = ref.get() or 0
    ref.set(current + 1)

async def get_stats(code: str):
    """Kod statistikasi"""
    ref = db.reference(f"codes/{code}/stat")
    return ref.get() or {}

async def reset_stats(code: str):
    """Kod statistikasini reset qilish"""
    ref = db.reference(f"codes/{code}/stat")
    ref.set({"searched": 0, "viewed": 0})

# ============================
# === ADMINLAR FUNKSIYALARI ===
# ============================

async def add_admin(admin_id: int):
    """Admin qo‘shish"""
    ref = db.reference("admins")
    ref.child(str(admin_id)).set({"id": admin_id})

async def get_admins():
    """Barcha adminlarni olish"""
    ref = db.reference("admins")
    data = ref.get()
    return [int(x["id"]) for x in data.values()] if data else []

async def delete_admin(admin_id: int):
    """Admin o‘chirish"""
    ref = db.reference(f"admins/{admin_id}")
    ref.delete()
