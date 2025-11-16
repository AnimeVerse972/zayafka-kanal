# === IMPORTLAR ===
from aiogram.dispatcher.filters import Text
import io
import os
import asyncio
import time
import logging
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
from keep_alive import keep_alive
from database import (
    init_db,
    add_user,
    get_user_count,
    add_kino_code,
    get_kino_by_code,
    get_all_codes,
    delete_kino_code,
    get_code_stat,
    increment_stat,
    get_all_user_ids,
    update_anime_code,
    get_today_users
)

# === YUKLAMALAR ===
load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
CHANNELS = [-1002605246586]
LINKS = ["https://t.me/AniVerseClip"]
MAIN_CHANNELS = []
MAIN_LINKS = []
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = {6486825926, 7575041003}

# === KEYBOARDS ===
def admin_keyboard():
    """Asosiy admin paneli — 'Boshqarish' tugmasi MAVJUD EMAS"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ Anime qo‘shish")
    kb.add("📊 Statistika", "📈 Kod statistikasi")
    kb.add("❌ Kodni o‘chirish", "📄 Kodlar ro‘yxati")
    kb.add("✏️ Kodni tahrirlash", "📤 Post qilish")
    kb.add("📢 Habar yuborish", "📘 Qo‘llanma")
    kb.add("➕ Admin qo‘shish", "📡 Kanal boshqaruvi")
    return kb

def control_keyboard():
    """Faol jarayonlarda foydalaniladigan 'Boshqarish' tugmasi"""
    return ReplyKeyboardMarkup(resize_keyboard=True).add("📡 Boshqarish")

async def send_admin_panel(message: types.Message):
    await message.answer("👮‍♂️ Admin panel:", reply_markup=admin_keyboard())

# === HOLATLAR ===
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
    waiting_for_code = State() 
    waiting_for_image = State()
    waiting_for_title = State()
    waiting_for_link = State()
    waiting_for_button_text = State() 
    
class KanalStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_link = State()


# === OBUNA TEKSHIRISH ===
async def get_unsubscribed_channels(user_id):
    unsubscribed = []
    for idx, channel_id in enumerate(CHANNELS):
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                unsubscribed.append((channel_id, LINKS[idx]))
        except Exception as e:
            print(f"❗ Obuna tekshirishda xatolik: {channel_id} -> {e}")
            unsubscribed.append((channel_id, LINKS[idx]))
    return unsubscribed


# === OBUNA BO‘LMAGANLAR MARKUP ===
async def make_unsubscribed_markup(user_id, code):
    unsubscribed = await get_unsubscribed_channels(user_id)
    markup = InlineKeyboardMarkup(row_width=1)

    for channel_id, channel_link in unsubscribed:
        try:
            chat = await bot.get_chat(channel_id)
            markup.add(
                InlineKeyboardButton(f"➕ {chat.title}", url=channel_link)
            )
        except Exception as e:
            print(f"❗ Kanal tugmasini yaratishda xatolik: {channel_id} -> {e}")

    # Tekshirish tugmasi
    markup.add(InlineKeyboardButton("✅ Tekshirish", callback_data=f"checksub:{code}"))
    return markup


# === /start HANDLER ===
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


# === TEKSHIRUV CALLBACK ===
@dp.callback_query_handler(lambda c: c.data.startswith("checksub:"))
async def check_subscription_callback(call: CallbackQuery):
    code = call.data.split(":")[1]
    unsubscribed = await get_unsubscribed_channels(call.from_user.id)

    if unsubscribed:
        markup = InlineKeyboardMarkup(row_width=1)
        for channel_id, channel_link in unsubscribed:
            try:
                chat = await bot.get_chat(channel_id)
                markup.add(
                    InlineKeyboardButton(f"➕ {chat.title}", url=channel_link)
                )
            except Exception as e:
                print(f"❗ Kanal tugmasini qayta yaratishda xatolik: {channel_id} -> {e}")

        markup.add(InlineKeyboardButton("✅ Yana tekshirish", callback_data=f"checksub:{code}"))
        await call.message.edit_text("❗ Hali ham obuna bo‘lmagan kanal(lar):", reply_markup=markup)
    else:
        await call.message.delete()
        await send_reklama_post(call.from_user.id, code)
        await increment_stat(code, "searched")


# === Barcha animelar ===
@dp.message_handler(lambda m: m.text == "🎞 Barcha animelar")
async def show_all_animes(message: types.Message):
    kodlar = await get_all_codes()
    if not kodlar:
        await message.answer("⛔️ Hozircha animelar yoʻq.")
        return

    kodlar = sorted(kodlar, key=lambda x: int(x["code"]))

    # 100 tadan bo‘lib yuborish
    chunk_size = 100
    for i in range(0, len(kodlar), chunk_size):
        chunk = kodlar[i:i + chunk_size]

        text = "📄 *Barcha animelar:*\n\n"
        for row in chunk:
            text += f"`{row['code']}` – *{row['title']}*\n"

        await message.answer(text, parse_mode="Markdown")


# === Admin bilan bog‘lanish (foydalanuvchi qismi) ===
def cancel_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("❌ Bekor qilish"))
    return kb


# === Admin bilan bog‘lanish (foydalanuvchi qismi) ===
@dp.message_handler(lambda m: m.text == "✉️ Admin bilan bog‘lanish")
async def contact_admin(message: types.Message):
    await UserStates.waiting_for_admin_message.set()
    await message.answer(
        "✍️ Adminlarga yubormoqchi bo‘lgan xabaringizni yozing.\n\n❌ Bekor qilish tugmasini bosing agar ortga qaytmoqchi bo‘lsangiz.",
        reply_markup=cancel_keyboard()
    )


@dp.message_handler(state=UserStates.waiting_for_admin_message)
async def forward_to_admins(message: types.Message, state: FSMContext):
    # Bekor qilish tugmasi bosilganda
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
async def start_admin_reply(callback: CallbackQuery, state: FSMContext):
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
    
# === Kanal boshqaruvi menyusi ===
@dp.message_handler(lambda m: m.text == "📡 Kanal boshqaruvi", user_id=ADMINS)
async def kanal_boshqaruvi(message: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔗 Majburiy obuna", callback_data="channel_type:sub"),
        InlineKeyboardButton("📌 Asosiy kanallar", callback_data="channel_type:main")
    )
    await message.answer("📡 Qaysi kanal turini boshqarasiz?", reply_markup=kb)


# === Kanal turi tanlanadi ===
@dp.callback_query_handler(lambda c: c.data.startswith("channel_type:"), user_id=ADMINS)
async def select_channel_type(callback: types.CallbackQuery, state: FSMContext):
    ctype = callback.data.split(":")[1]
    await state.update_data(channel_type=ctype)

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ Kanal qo‘shish", callback_data="action:add"),
        InlineKeyboardButton("📋 Kanal ro‘yxati", callback_data="action:list")
    )
    kb.add(
        InlineKeyboardButton("❌ Kanal o‘chirish", callback_data="action:delete"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="action:back")
    )

    text = "📡 Majburiy obuna kanallari menyusi:" if ctype == "sub" else "📌 Asosiy kanallar menyusi:"
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# === Actionlarni boshqarish ===
@dp.callback_query_handler(lambda c: c.data.startswith("action:"), user_id=ADMINS)
async def channel_actions(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    data = await state.get_data()
    ctype = data.get("channel_type")

    if not ctype:
        await callback.answer("❗ Avval kanal turini tanlang.")
        return

    # ➕ Kanal qo‘shish
    if action == "add":
        await KanalStates.waiting_for_channel_id.set()
        await callback.message.answer("🆔 Kanal ID yuboring (masalan: -1001234567890):")

    # 📋 Kanal ro‘yxati
    elif action == "list":
        if ctype == "sub":
            channels = list(zip(CHANNELS, LINKS))
            title = "📋 Majburiy obuna kanallari:\n\n"
        else:
            channels = list(zip(MAIN_CHANNELS, MAIN_LINKS))
            title = "📌 Asosiy kanallar:\n\n"

        if not channels:
            await callback.message.answer("📭 Hali kanal yo‘q.")
        else:
            text = title + "\n".join(
                f"{i}. 🆔 {cid}\n   🔗 {link}" for i, (cid, link) in enumerate(channels, 1)
            )
            await callback.message.answer(text)

    # ❌ Kanal o‘chirish
    elif action == "delete":
        if ctype == "sub":
            channels = list(zip(CHANNELS, LINKS))
            prefix = "del_sub"
        else:
            channels = list(zip(MAIN_CHANNELS, MAIN_LINKS))
            prefix = "del_main"

        if not channels:
            await callback.message.answer("📭 Hali kanal yo‘q.")
            return

        kb = InlineKeyboardMarkup()
        for cid, link in channels:
            kb.add(InlineKeyboardButton(f"O‘chirish: {cid}", callback_data=f"{prefix}:{cid}"))
        await callback.message.answer("❌ Qaysi kanalni o‘chirmoqchisiz?", reply_markup=kb)

    # ⬅️ Orqaga
    elif action == "back":
        await kanal_boshqaruvi(callback.message)

    await callback.answer()


# === 1. Kanal ID qabul qilish ===
@dp.message_handler(state=KanalStates.waiting_for_channel_id, user_id=ADMINS)
async def add_channel_id(message: types.Message, state: FSMContext):
    try:
        channel_id = int(message.text.strip())
        await state.update_data(channel_id=channel_id)
        await KanalStates.waiting_for_channel_link.set()
        await message.answer("🔗 Endi kanal linkini yuboring (masalan: https://t.me/+invitehash):")
    except ValueError:
        await message.answer("❗ Faqat sonlardan iborat ID yuboring (masalan: -1001234567890).")


# === 2. Kanal linkini qabul qilish va saqlash ===
@dp.message_handler(state=KanalStates.waiting_for_channel_link, user_id=ADMINS)
async def add_channel_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ctype = data.get("channel_type")
    channel_id = data.get("channel_id")
    channel_link = message.text.strip()

    if not channel_link.startswith("http"):
        await message.answer("❗ To‘liq link yuboring (masalan: https://t.me/...)")
        return

    if ctype == "sub":
        if channel_id in CHANNELS:
            await message.answer("ℹ️ Bu kanal allaqachon qo‘shilgan.")
        else:
            CHANNELS.append(channel_id)
            LINKS.append(channel_link)
            await message.answer(f"✅ Kanal qo‘shildi!\n🆔 {channel_id}\n🔗 {channel_link}")
    else:
        if channel_id in MAIN_CHANNELS:
            await message.answer("ℹ️ Bu kanal allaqachon qo‘shilgan.")
        else:
            MAIN_CHANNELS.append(channel_id)
            MAIN_LINKS.append(channel_link)
            await message.answer(f"✅ Asosiy kanal qo‘shildi!\n🆔 {channel_id}\n🔗 {channel_link}")

    await state.finish()


# === Kanalni o‘chirish ===
@dp.callback_query_handler(lambda c: c.data.startswith("del_"), user_id=ADMINS)
async def delete_channel(callback: types.CallbackQuery):
    action, cid = callback.data.split(":")
    cid = int(cid)

    if action == "del_sub":
        if cid in CHANNELS:
            idx = CHANNELS.index(cid)
            CHANNELS.pop(idx)
            LINKS.pop(idx)
            await callback.message.answer(f"❌ Kanal o‘chirildi!\n🆔 {cid}")
    elif action == "del_main":
        if cid in MAIN_CHANNELS:
            idx = MAIN_CHANNELS.index(cid)
            MAIN_CHANNELS.pop(idx)
            MAIN_LINKS.pop(idx)
            await callback.message.answer(f"❌ Asosiy kanal o‘chirildi!\n🆔 {cid}")

    await callback.answer("O‘chirildi ✅")

# === Admin qo'shish ===
@dp.message_handler(lambda m: m.text == "➕ Admin qo‘shish", user_id=ADMINS)
async def add_admin_start(message: types.Message):
    await AdminStates.waiting_for_admin_id.set()
    await message.answer("🆔 Yangi adminning Telegram ID raqamini yuboring.", reply_markup=control_keyboard())

@dp.message_handler(state=AdminStates.waiting_for_admin_id, user_id=ADMINS)
async def add_admin_process(message: types.Message, state: FSMContext):
    if message.text == "📡 Boshqarish":
        await state.finish()
        await send_admin_panel(message)
        return

    await state.finish()
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❗ Faqat raqam yuboring (Telegram user ID).", reply_markup=control_keyboard())
        return

    new_admin_id = int(text)
    if new_admin_id in ADMINS:
        await message.answer("ℹ️ Bu foydalanuvchi allaqachon admin.", reply_markup=control_keyboard())
        return

    ADMINS.add(new_admin_id)
    await message.answer(f"✅ <code>{new_admin_id}</code> admin sifatida qo‘shildi.", parse_mode="HTML", reply_markup=control_keyboard())
    try:
        await bot.send_message(new_admin_id, "✅ Siz botga admin sifatida qo‘shildingiz.")
    except:
        pass


# === Kod statistikasi ===
@dp.message_handler(lambda m: m.text == "📈 Kod statistikasi", user_id=ADMINS)
async def ask_stat_code(message: types.Message):
    await AdminStates.waiting_for_stat_code.set()
    await message.answer("📥 Kod raqamini yuboring:", reply_markup=control_keyboard())


@dp.message_handler(state=AdminStates.waiting_for_stat_code)
async def show_code_stat(message: types.Message, state: FSMContext):
    if message.text == "📡 Boshqarish":
        await state.finish()
        await send_admin_panel(message)
        return

    code = message.text.strip()
    if not code:
        await message.answer("❗ Kod yuboring.", reply_markup=control_keyboard())
        return

    stat = await get_code_stat(code)
    await state.finish()  # faqat oxirida tugatamiz

    if not stat:
        await message.answer("❗ Bunday kod statistikasi topilmadi.", reply_markup=control_keyboard())
        await send_admin_panel(message)
        return

    await message.answer(
        f"📊 <b>{code} statistikasi:</b>\n"
        f"🔍 Qidirilgan: <b>{stat['searched']}</b>\n",
        parse_mode="HTML"
    )

    # Statistikani ko‘rsatib bo‘lgach, admin panel qaytadi
    await send_admin_panel(message)


# === Kodni tahrirlash ===
@dp.message_handler(lambda m: m.text == "✏️ Kodni tahrirlash", user_id=ADMINS)
async def edit_code_start(message: types.Message):
    await EditCode.WaitingForOldCode.set()
    await message.answer("Qaysi kodni tahrirlashni xohlaysiz? (eski kodni yuboring)", reply_markup=control_keyboard())

@dp.message_handler(state=EditCode.WaitingForOldCode, user_id=ADMINS)
async def get_old_code(message: types.Message, state: FSMContext):
    if message.text == "📡 Boshqarish":
        await state.finish()
        await send_admin_panel(message)
        return

    code = message.text.strip()
    post = await get_kino_by_code(code)
    if not post:
        await message.answer("❌ Bunday kod topilmadi. Qaytadan urinib ko‘ring.", reply_markup=control_keyboard())
        return
    await state.update_data(old_code=code)
    await message.answer(f"🔎 Kod: {code}\n📌 Nomi: {post['title']}\n\nYangi kodni yuboring:", reply_markup=control_keyboard())
    await EditCode.WaitingForNewCode.set()

@dp.message_handler(state=EditCode.WaitingForNewCode, user_id=ADMINS)
async def get_new_code(message: types.Message, state: FSMContext):
    if message.text == "📡 Boshqarish":
        await state.finish()
        await send_admin_panel(message)
        return

    await state.update_data(new_code=message.text.strip())
    await message.answer("Yangi nomini yuboring:", reply_markup=control_keyboard())
    await EditCode.WaitingForNewTitle.set()

@dp.message_handler(state=EditCode.WaitingForNewTitle, user_id=ADMINS)
async def get_new_title(message: types.Message, state: FSMContext):
    if message.text == "📡 Boshqarish":
        await state.finish()
        await send_admin_panel(message)
        return

    data = await state.get_data()
    try:
        await update_anime_code(data['old_code'], data['new_code'], message.text.strip())
        await message.answer("✅ Kod va nom muvaffaqiyatli tahrirlandi.", reply_markup=admin_keyboard())
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi:\n{e}", reply_markup=admin_keyboard())
    finally:
        await state.finish()


# === Kodni o'chirish ===
@dp.message_handler(lambda m: m.text == "❌ Kodni o‘chirish", user_id=ADMINS)
async def ask_delete_code(message: types.Message):
    await AdminStates.waiting_for_delete_code.set()
    await message.answer("🗑 Qaysi kodni o‘chirmoqchisiz? Kodni yuboring.", reply_markup=control_keyboard())

@dp.message_handler(state=AdminStates.waiting_for_delete_code)
async def delete_code_handler(message: types.Message, state: FSMContext):
    if message.text == "📡 Boshqarish":
        await state.finish()
        await send_admin_panel(message)
        return

    await state.finish()
    code = message.text.strip()
    if not code.isdigit():
        await message.answer("❗ Noto‘g‘ri format. Kod raqamini yuboring.", reply_markup=control_keyboard())
        return
    deleted = await delete_kino_code(code)
    if deleted:
        await message.answer(f"✅ Kod {code} o‘chirildi.", reply_markup=admin_keyboard())
    else:
        await message.answer("❌ Kod topilmadi yoki o‘chirib bo‘lmadi.", reply_markup=admin_keyboard())


@dp.message_handler(lambda m: m.text == "📤 Post qilish" and m.from_user.id in ADMINS)
async def start_post_process(message: types.Message):
    await PostStates.waiting_for_code.set()
    await message.answer(
        "🔢 Qaysi anime KODini kanalga yubormoqchisiz?\nMasalan: `147`",
        reply_markup=control_keyboard()
    )


@dp.message_handler(state=PostStates.waiting_for_code)
async def process_post_code(message: types.Message, state: FSMContext):
    text = message.text.strip()

    # Admin panelga qaytish
    if text == "📡 Boshqarish":
        await state.finish()
        await send_admin_panel(message)
        return

    if not text.isdigit():
        await message.answer("❌ Kod faqat raqam bo‘lishi kerak!")
        return

    code = text

    # === BAZADAN ANIQLASH ===
    kino = await get_kino_by_code(code)

    if not kino:
        await message.answer("❌ Bunday kod topilmadi!")
        return

    channel = kino["channel"]            # server channel
    message_id = kino["message_id"] - 1  # avval +1 qilingan, endi -1 qilib olib qo‘yamiz
    title = kino["title"]

    download_btn = InlineKeyboardMarkup().add(
        InlineKeyboardButton(
            "✨Yuklab olish✨",
            url=f"https://t.me/{BOT_USERNAME}?start={code}"
        )
    )

    successful = 0
    failed = 0

    # === KANALLARGA YUBORISH ===
    for ch in MAIN_CHANNELS:
        try:
            await bot.copy_message(
                chat_id=ch,
                from_chat_id=channel,
                message_id=message_id,
                reply_markup=download_btn
            )
            successful += 1
        except:
            failed += 1

    # Yakuniy javob
    await message.answer(
        f"📤 *Post yuborildi!*\n\n"
        f"🎬 Anime: *{title}*\n"
        f"🔢 Kod: `{code}`\n\n"
        f"✅ Yuborildi: {successful}\n"
        f"❌ Xato: {failed}",
        parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )

    await state.finish()
    
# === Anime qo'shish ===
@dp.message_handler(lambda m: m.text == "➕ Anime qo‘shish", user_id=ADMINS)
async def add_start(message: types.Message):
    await AdminStates.waiting_for_kino_data.set()
    await message.answer("📝 Format: `KOD @kanal REKLAMA_ID POST_SONI ANIME_NOMI`\nMasalan: `91 @MyKino 4 12 naruto`", parse_mode="Markdown", reply_markup=control_keyboard())

@dp.message_handler(state=AdminStates.waiting_for_kino_data)
async def add_kino_handler(message: types.Message, state: FSMContext):
    if message.text == "📡 Boshqarish":
        await state.finish()
        await send_admin_panel(message)
        return

    rows = message.text.strip().split("\n")
    successful = 0
    failed = 0
    for row in rows:
        parts = row.strip().split()
        if len(parts) < 5:
            failed += 1
            continue
        code, server_channel, reklama_id, post_count = parts[:4]
        title = " ".join(parts[4:])
        if not (code.isdigit() and reklama_id.isdigit() and post_count.isdigit()):
            failed += 1
            continue
        reklama_id = int(reklama_id)
        post_count = int(post_count)
        await add_kino_code(code, server_channel, reklama_id + 1, post_count, title)
        download_btn = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✨Yuklab olish✨", url=f"https://t.me/{BOT_USERNAME}?start={code}")
        )
        for ch in MAIN_CHANNELS:
            try:
                await bot.copy_message(ch, server_channel, reklama_id, reply_markup=download_btn)
                successful += 1
            except:
                failed += 1

    await message.answer(f"✅ Yangi kodlar qo‘shildi:\n\n✅ Muvaffaqiyatli: {successful}\n❌ Xatolik: {failed}", reply_markup=admin_keyboard())
    await state.finish()


# === Kodlar ro'yxati ===
@dp.message_handler(lambda m: m.text == "📄 Kodlar ro‘yxati")
async def show_all_animes(message: types.Message):
    kodlar = await get_all_codes()
    if not kodlar:
        await message.answer("Ba'zada hech qanday kodlar yo'q!")
        return
    kodlar = sorted(kodlar, key=lambda x: int(x["code"]))
    chunk_size = 100
    for i in range(0, len(kodlar), chunk_size):
        chunk = kodlar[i:i + chunk_size]
        text = "📄 *Barcha animelar:*\n\n"
        for row in chunk:
            text += f"`{row['code']}` – *{row['title']}*\n"
        await message.answer(text, parse_mode="Markdown")


# === Statistika ===
@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    from database import db_pool
    async with db_pool.acquire() as conn:
        start = time.perf_counter()
        await conn.fetch("SELECT 1;")
        ping = (time.perf_counter() - start) * 1000
    kodlar = await get_all_codes()
    foydalanuvchilar = await get_user_count()
    today_users = await get_today_users()
    text = (
        f"💡 O'rtacha yuklanish: {ping:.2f} ms\n\n"
        f"👥 Foydalanuvchilar: {foydalanuvchilar} ta\n\n"
        f"📂 Barcha yuklangan animelar: {len(kodlar)} ta\n\n"
        f"📅 Bugun qo'shilgan foydalanuvchilar: {today_users} ta"
    )
    await message.answer(text, reply_markup=admin_keyboard())


# === Orqaga tugmasi ===
@dp.message_handler(lambda m: m.text == "⬅️ Orqaga", user_id=ADMINS)
async def back_to_admin_menu(message: types.Message):
    await send_admin_panel(message)


# === Qo'llanma ===
@dp.message_handler(lambda m: m.text == "📘 Qo‘llanma")
async def qollanma(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📥 1. Anime qo‘shish", callback_data="help_add"),
        InlineKeyboardButton("📡 2. Kanal yaratish", callback_data="help_channel"),
        InlineKeyboardButton("🆔 3. Reklama ID olish", callback_data="help_id"),
        InlineKeyboardButton("🔁 4. Kod ishlashi", callback_data="help_code"),
        InlineKeyboardButton("❓ 5. Savol-javob", callback_data="help_faq")
    )
    await message.answer("📘 Qanday yordam kerak?", reply_markup=kb)


# === Qo'llanma sahifalari ===
HELP_TEXTS = {
    "help_add": ("📥 *Anime qo‘shish*\n\n`KOD @kanal REKLAMA_ID POST_SONI ANIME_NOMI`\n\nMisol: `91 @MyKino 4 12 Naruto`\n\n• *Kod* – foydalanuvchi yozadigan raqam\n• *@kanal* – server kanal username\n• *REKLAMA_ID* – post ID raqami (raqam)\n• *POST_SONI* – nechta qism borligi\n• *ANIME_NOMI* – ko‘rsatiladigan sarlavha\n\n📩 Endi formatda xabar yuboring:"),
    "help_channel": ("📡 *Kanal yaratish*\n\n1. 2 ta kanal yarating:\n   • *Server kanal* – post saqlanadi\n   • *Reklama kanal* – bot ulashadi\n\n2. Har ikkasiga botni admin qiling\n\n3. Kanalni public (@username) qiling"),
    "help_id": ("🆔 *Reklama ID olish*\n\n1. Server kanalga post joylang\n\n2. Post ustiga bosing → *Share* → *Copy link*\n\n3. Link oxiridagi sonni oling\n\nMisol: `t.me/MyKino/4` → ID = `4`"),
    "help_code": ("🔁 *Kod ishlashi*\n\n1. Foydalanuvchi kod yozadi (masalan: `91`)\n\n2. Obuna tekshiriladi → reklama post yuboriladi\n\n3. Tugmalar orqali qismlarni ochadi"),
    "help_faq": ("❓ *Tez-tez so‘raladigan savollar*\n\n• *Kodni qanday ulashaman?*\n  `https://t.me/{BOT_USERNAME}?start=91`\n\n• *Har safar yangi kanal kerakmi?*\n  – Yo‘q, bitta server kanal yetarli\n\n• *Kodni tahrirlash/o‘chirish mumkinmi?*\n  – Ha, admin menyuda ✏️ / ❌ tugmalari bor")
}

@dp.callback_query_handler(lambda c: c.data.startswith("help_"))
async def show_help_page(callback: types.CallbackQuery):
    key = callback.data
    text = HELP_TEXTS.get(key, "❌ Ma'lumot topilmadi.")
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Ortga", callback_data="back_help"))
    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    except:
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
        await callback.message.delete()
    finally:
        await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "back_help")
async def back_to_qollanma(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📥 1. Anime qo‘shish", callback_data="help_add"),
        InlineKeyboardButton("📡 2. Kanal yaratish", callback_data="help_channel"),
        InlineKeyboardButton("🆔 3. Reklama ID olish", callback_data="help_id"),
        InlineKeyboardButton("🔁 4. Kod ishlashi", callback_data="help_code"),
        InlineKeyboardButton("❓ 5. Savol-javob", callback_data="help_faq")
    )
    try:
        await callback.message.edit_text("📘 Qanday yordam kerak?", reply_markup=kb)
    except:
        await callback.message.answer("📘 Qanday yordam kerak?", reply_markup=kb)
        await callback.message.delete()
    finally:
        await callback.answer()

# --------- Safe edit helper ---------
async def safe_edit_status(old_msg: types.Message, text: str, reply_markup=None):
    for attempt in range(3):
        try:
            return await old_msg.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            err = str(e).lower()
            if "message is not modified" in err:
                return old_msg
            await asyncio.sleep(1 + attempt)
    try:
        new_msg = await old_msg.answer(text, reply_markup=reply_markup)
        try:
            await old_msg.delete()
        except Exception:
            pass
        return new_msg
    except Exception:
        return old_msg

# --------- Send forward with retry ---------
async def send_broadcast_with_retry(user_id: int, channel_username: str, msg_id: int, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            await bot.forward_message(user_id, channel_username, msg_id)
            return True
        except RetryAfter as e:
            wait_time = e.timeout
            logging.warning(f"[FLOOD WAIT] {wait_time}s | user_id={user_id}")
            await asyncio.sleep(wait_time)
            continue
        except (BotBlocked, ChatNotFound, UserDeactivated):
            return False
        except TelegramAPIError as e:
            logging.error(f"Telegram API Error: {e}")
            await asyncio.sleep(1)
            continue
        except Exception as e:
            logging.error(f"Unknown error sending to {user_id}: {e}")
            await asyncio.sleep(1)
            continue
    return False

# --------- Handler: boshlash (savol berish) ---------
@dp.message_handler(Text(equals="📢 Habar yuborish"), user_id=ADMINS)
async def ask_broadcast_info(message: types.Message):
    await AdminStates.waiting_for_broadcast_data.set()
    await message.answer(
        "📨 Habar yuborish uchun format:\n`@kanal xabar_id`\n\nMasalan: `@mychannel 123`",
        parse_mode="Markdown",
        reply_markup=control_keyboard()
    )

# --------- Handler: yuborish jarayoni ---------
@dp.message_handler(state=AdminStates.waiting_for_broadcast_data)
async def send_forward_only(message: types.Message, state: FSMContext):
    # Boshqaruvga qaytish tugmasi
    if message.text == "📡 Boshqarish":
        await state.finish()
        await message.answer("🏠 Bosh menyu", reply_markup=admin_keyboard())
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer(
            "❗ Format noto'g'ri. Masalan: `@kanalim 123`",
            parse_mode="Markdown",
            reply_markup=control_keyboard()
        )
        return

    channel_username, msg_id = parts
    if not msg_id.isdigit():
        await message.answer("❗ Xabar ID raqam bo'lishi kerak.", reply_markup=control_keyboard())
        return

    msg_id = int(msg_id)

    # Admin uchun test forward
    try:
        await bot.forward_message(message.from_user.id, channel_username, msg_id)
    except Exception as e:
        await message.answer(f"❌ Kanal yoki xabar topilmadi (test forward muvaffaqiyatsiz):\n{e}",
                             reply_markup=control_keyboard())
        return

    users = await get_all_user_ids()
    total_users = len(users)
    await state.finish()

    if total_users == 0:
        await message.answer("❌ Foydalanuvchilar topilmadi!", reply_markup=admin_keyboard())
        return

    # Boshlang'ich status xabari
    status_text = (
        f"📤 Yuborilmoqda...\n\n"
        f"👥 Jami: {total_users}\n"
        f"✅ Yuborildi: 0\n"
        f"❌ Xatolik: 0\n"
        f"⏳ Kutilmoqda: {total_users}"
    )
    status_msg = await message.answer(status_text, reply_markup=admin_keyboard())

    success = 0
    fail = 0
    update_every = 5       # har 5ta foydalanuvchida yangilansin
    per_user_sleep = 0.05
    batch_sleep = 1.0

    processed = 0
    for user_id in users:
        if user_id == message.from_user.id:
            continue

        processed += 1
        ok = await send_broadcast_with_retry(user_id, channel_username, msg_id)

        if ok:
            success += 1
        else:
            fail += 1

        await asyncio.sleep(per_user_sleep)

        # Status yangilash
        if processed % update_every == 0 or processed == total_users:
            remaining = total_users - processed
            new_text = (
                f"📤 Yuborilmoqda...\n\n"
                f"👥 Jami: {total_users}\n"
                f"✅ Yuborildi: {success}\n"
                f"❌ Xatolik: {fail}\n"
                f"⏳ Kutilmoqda: {remaining}"
            )
            status_msg = await safe_edit_status(status_msg, new_text, reply_markup=admin_keyboard())
            await asyncio.sleep(batch_sleep)

    # Yakuniy natija
    success_rate = (success / total_users * 100) if total_users else 0
    final_text = (
        f"✅ Yuborish yakunlandi!\n\n"
        f"👥 Jami: {total_users}\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Xatolik: {fail}\n\n"
        f"📊 Muvaffaqiyat: {success_rate:.1f}%"
    )
    try:
        await status_msg.edit_text(final_text, reply_markup=admin_keyboard())
    except Exception:
        pass

# === Kodni qidirish (raqam) ===
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


# === Reklama post yuborish ===
async def send_reklama_post(user_id, code):
    data = await get_kino_by_code(code)
    if not data:
        await bot.send_message(user_id, "❌ Kod topilmadi.")
        return

    channel, reklama_id, post_count = data["channel"], data["message_id"], data["post_count"]

    # Endi faqat bitta tugma bo'ladi: "✨Yuklab olish"
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✨Tomosha qilish✨", callback_data=f"download:{code}")
    )

    try:
        await bot.copy_message(user_id, channel, reklama_id - 1, reply_markup=keyboard)
    except:
        await bot.send_message(user_id, "❌ Reklama postni yuborib bo‘lmadi.")


# === Yuklab olish tugmasi bosilganda ===
@dp.callback_query_handler(lambda c: c.data.startswith("download:"))
async def download_all(callback: types.CallbackQuery):
    code = callback.data.split(":")[1]
    result = await get_kino_by_code(code)
    if not result:
        await callback.message.answer("❌ Kod topilmadi.")
        return

    channel, base_id, post_count = result["channel"], result["message_id"], result["post_count"]

    await callback.answer("⏳ Yuklanmoqda, biroz kuting...")

    # Hamma qismlarni ketma-ket yuborish
    for i in range(post_count):
        try:
            await bot.copy_message(callback.from_user.id, channel, base_id + i)
            await asyncio.sleep(0.1)  # flood control uchun sekin yuborish
        except:
            pass

# === START ===
async def on_startup(dp):
    await init_db()
    print("✅ PostgreSQL bazaga ulandi!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False, on_startup=on_startup)
