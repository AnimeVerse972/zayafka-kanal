# === IMPORTLAR ===
import os
import io
import time
import asyncio
from datetime import datetime, date
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.utils import executor
from database import (
    init_db, add_user, get_user_count, get_today_users,
    add_kino_code, get_kino_by_code, get_all_codes,
    delete_kino_code, get_code_stat, increment_stat,
    get_all_user_ids, update_anime_code
)
from keep_alive import keep_alive

# === ENV VA BOT INIT ===
load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# === GLOBAL LISTLAR ===
CHANNELS = []
LINKS = []
MAIN_CHANNELS = []
MAIN_LINKS = []

ADMINS = {6486825926, 7575041003}  # Admin ID lar

# =====================
# === KEYBOARDLAR ===
# =====================
def admin_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ Anime qo‘shish")
    kb.add("📊 Statistika", "📈 Kod statistikasi")
    kb.add("❌ Kodni o‘chirish", "📄 Kodlar ro‘yxati")
    kb.add("✏️ Kodni tahrirlash", "📤 Post qilish")
    kb.add("📢 Habar yuborish", "📘 Qo‘llanma")
    kb.add("➕ Admin qo‘shish", "📡 Kanal boshqaruvi")
    return kb

def control_keyboard():
    return ReplyKeyboardMarkup(resize_keyboard=True).add("📡 Boshqarish")

def cancel_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("❌ Bekor qilish"))
    return kb

async def send_admin_panel(message: types.Message):
    await message.answer("👮‍♂️ Admin panel:", reply_markup=admin_keyboard())

# =====================
# === HOLATLAR (FSM) ===
# =====================
class AdminStates(StatesGroup):
    waiting_for_kino_data = State()
    waiting_for_delete_code = State()
    waiting_for_stat_code = State()
    waiting_for_broadcast_data = State()
    waiting_for_admin_id = State()

class AdminReplyStates(StatesGroup):
    waiting_for_reply_message = State()

class EditCode(StatesGroup):
    WaitingForOldCode = State()
    WaitingForNewCode = State()
    WaitingForNewTitle = State()

class UserStates(StatesGroup):
    waiting_for_admin_message = State()

class SearchStates(StatesGroup):
    waiting_for_anime_name = State()

class PostStates(StatesGroup):
    waiting_for_image = State()
    waiting_for_title = State()
    waiting_for_link = State()
    
class KanalStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_link = State()

# =====================
# === OBUNA TEKSHIRISH ===
# =====================
async def get_unsubscribed_channels(user_id):
    unsubscribed = []
    for idx, channel_id in enumerate(CHANNELS):
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                unsubscribed.append((channel_id, LINKS[idx]))
        except Exception as e:
            print(f"❗ Obuna tekshirish xatosi: {channel_id} -> {e}")
            unsubscribed.append((channel_id, LINKS[idx]))
    return unsubscribed

async def make_unsubscribed_markup(user_id, code):
    unsubscribed = await get_unsubscribed_channels(user_id)
    markup = InlineKeyboardMarkup(row_width=1)
    for channel_id, channel_link in unsubscribed:
        try:
            chat = await bot.get_chat(channel_id)
            markup.add(InlineKeyboardButton(f"➕ {chat.title}", url=channel_link))
        except Exception as e:
            print(f"❗ Kanal tugmasi yaratishda xatolik: {channel_id} -> {e}")
    markup.add(InlineKeyboardButton("✅ Tekshirish", callback_data=f"checksub:{code}"))
    return markup

# =====================
# === START HANDLER ===
# =====================
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await add_user(message.from_user.id)
    args = message.get_args()

    if args and args.isdigit():
        code = args
        await increment_stat(code, "init")
        await increment_stat(code, "searched")
        unsubscribed = await get_unsubscribed_channels(message.from_user.id)
        if unsubscribed:
            markup = await make_unsubscribed_markup(message.from_user.id, code)
            await message.answer(
                "❗ Animeni olishdan oldin quyidagi kanal(lar)ga obuna bo‘ling:",
                reply_markup=markup
            )
        else:
            await send_reklama_post(message.from_user.id, code)
            await increment_stat(code, "searched")
        return

    if message.from_user.id in ADMINS:
        await send_admin_panel(message)
    else:
        kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add(KeyboardButton("🎞 Barcha animelar"), KeyboardButton("✉️ Admin bilan bog‘lanish"))
        await message.answer("✨", reply_markup=kb)

# =====================
# === TEKSHIRUV CALLBACK ===
# =====================
@dp.callback_query_handler(lambda c: c.data.startswith("checksub:"))
async def check_subscription_callback(call: CallbackQuery):
    code = call.data.split(":")[1]
    unsubscribed = await get_unsubscribed_channels(call.from_user.id)
    if unsubscribed:
        markup = await make_unsubscribed_markup(call.from_user.id, code)
        await call.message.edit_text("❗ Hali ham obuna bo‘lmagan kanal(lar):", reply_markup=markup)
    else:
        await call.message.delete()
        await send_reklama_post(call.from_user.id, code)
        await increment_stat(code, "searched")

# =====================
# === SHOW ALL ANIMES ===
# =====================
@dp.message_handler(lambda m: m.text == "🎞 Barcha animelar" or m.text == "📄 Kodlar ro‘yxati")
async def show_all_animes(message: types.Message):
    kodlar = await get_all_codes()
    if not kodlar:
        await message.answer("⛔️ Hozircha animelar yoʻq.")
        return
    kodlar = sorted(kodlar, key=lambda x: int(x["code"]))
    chunk_size = 100
    for i in range(0, len(kodlar), chunk_size):
        chunk = kodlar[i:i + chunk_size]
        text = "📄 *Barcha animelar:*\n\n"
        for row in chunk:
            text += f"`{row['code']}` – *{row['title']}*\n"
        await message.answer(text, parse_mode="Markdown")

# =====================
# === ADMIN BILAN BOGLANISH ===
# =====================
@dp.message_handler(lambda m: m.text == "✉️ Admin bilan bog‘lanish")
async def contact_admin(message: types.Message):
    await UserStates.waiting_for_admin_message.set()
    await message.answer(
        "✍️ Adminlarga yubormoqchi bo‘lgan xabaringizni yozing.\n\n❌ Bekor qilish tugmasini bosing.",
        reply_markup=cancel_keyboard()
    )

@dp.message_handler(state=UserStates.waiting_for_admin_message)
async def forward_to_admins(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.finish()
        kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add(KeyboardButton("🎞 Barcha animelar"), KeyboardButton("✉️ Admin bilan bog‘lanish"))
        await message.answer("🏠 Asosiy menyuga qaytdingiz.", reply_markup=kb)
        return

    await state.finish()
    user = message.from_user
    for admin_id in ADMINS:
        try:
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✉️ Javob yozish", callback_data=f"reply_user:{user.id}")
            )
            await bot.send_message(
                admin_id,
                f"📩 <b>Yangi xabar:</b>\n\n"
                f"<b>👤 Foydalanuvchi:</b> {user.full_name} | <code>{user.id}</code>\n"
                f"<b>💬 Xabar:</b> {message.text}",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Adminga yuborishda xatolik: {e}")

    await message.answer(
        "✅ Xabaringiz yuborildi. Tez orada admin siz bilan bog‘lanadi.",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add(
            KeyboardButton("🎞 Barcha animelar"), KeyboardButton("✉️ Admin bilan bog‘lanish")
        )
    )

@dp.callback_query_handler(lambda c: c.data.startswith("reply_user:"), user_id=ADMINS)
async def start_admin_reply(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    await state.update_data(reply_user_id=user_id)
    await AdminReplyStates.waiting_for_reply_message.set()
    await callback.message.answer("✍️ Endi foydalanuvchiga yubormoqchi bo‘lgan xabaringizni yozing.")
    await callback.answer()

@dp.message_handler(state=AdminReplyStates.waiting_for_reply_message, user_id=ADMINS)
async def send_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_user_id")
    try:
        await bot.send_message(user_id, f"✉️ Admindan javob:\n\n{message.text}")
        await message.answer("✅ Javob foydalanuvchiga yuborildi.")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        await state.finish()

# =====================
# === KOD QIDIRISH (FOYDALANUVCHI) ===
# =====================
@dp.message_handler(lambda message: message.text.isdigit())
async def handle_code_message(message: types.Message):
    code = message.text
    unsubscribed = await get_unsubscribed_channels(message.from_user.id)
    if unsubscribed:
        markup = await make_unsubscribed_markup(message.from_user.id, code)
        await message.answer("❗ Anime olishdan oldin quyidagi kanal(lar)ga obuna bo‘ling:", reply_markup=markup)
        return

    await increment_stat(code, "init")
    await increment_stat(code, "searched")
    await send_reklama_post(message.from_user.id, code)
    await increment_stat(code, "viewed")

# =====================
# === DOWNLOAD CALLBACK ===
# =====================
@dp.callback_query_handler(lambda c: c.data.startswith("download:"))
async def download_all(callback: types.CallbackQuery):
    code = callback.data.split(":")[1]
    result = await get_kino_by_code(code)
    if not result:
        await callback.message.answer("❌ Kod topilmadi.")
        return

    channel, base_id, post_count = result["channel"], result["message_id"], result["post_count"]
    await callback.answer("⏳ Yuklanmoqda, biroz kuting...")
    for i in range(post_count):
        try:
            await bot.copy_message(callback.from_user.id, channel, base_id + i)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❗ Post yuklashda xatolik: {e}")

# =====================
# === REKLAMA POST YUBORISH ===
# =====================
async def send_reklama_post(user_id, code):
    data = await get_kino_by_code(code)
    if not data:
        await bot.send_message(user_id, "❌ Kod topilmadi.")
        return

    channel, reklama_id = data["channel"], data["message_id"]
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📥 Yuklab olish", callback_data=f"download:{code}")
    )
    try:
        await bot.copy_message(user_id, channel, reklama_id - 1, reply_markup=keyboard)
    except Exception as e:
        await bot.send_message(user_id, f"❌ Reklama postni yuborib bo‘lmadi: {e}")

# =====================
# === STARTUP ===
# =====================
async def on_startup(dp):
    await init_db()
    print("✅ PostgreSQL bazaga ulandi!")

# =====================
# === RUN BOT ===
# =====================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
