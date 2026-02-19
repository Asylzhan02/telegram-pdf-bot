import os, json
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DB_FILE = "db.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "weekly_file_id": None,
            "issues": {}
        }
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

DB = load_db()

PENDING = {}
WAIT_WEEKLY = False
WAIT_ISSUE_LABEL = None

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗞 Осы апта газеті", callback_data="buy_weekly")],
        [InlineKeyboardButton(text="🗂 Архив (өткен апталар)", callback_data="archive")],
        [InlineKeyboardButton(text="💬 Байланыс", callback_data="contact")]
    ])

def issues_keyboard():
    issues = list(DB.get("issues", {}).keys())
    if not issues:
        return None
    issues = issues[::-1]
    kb = []
    for label in issues[:15]:
        kb.append([InlineKeyboardButton(text=label, callback_data=f"buy_issue:{label}")])
    kb.append([InlineKeyboardButton(text="⬅️ Артқа", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

KASPI_TEXT = (
    "💳 Төлем жасау:\n"
    "1) Kaspi арқылы төлеңіз.\n"
    "2) Төлем жасаған соң чек/скринді осы чатқа жіберіңіз.\n\n"
    "Таңдағаныңыз: {label}"
)

CONTACT_TEXT = "Редакциямен байланыс: осында телефон немесе WhatsApp жазыңыз"

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Сәлем! Газетті таңдаңыз 👇", reply_markup=main_menu())

@dp.callback_query(F.data == "back")
async def back(cb: CallbackQuery):
    await cb.message.answer("Басты меню 👇", reply_markup=main_menu())
    await cb.answer()

@dp.callback_query(F.data == "contact")
async def contact(cb: CallbackQuery):
    await cb.message.answer(CONTACT_TEXT)
    await cb.answer()

@dp.callback_query(F.data == "archive")
async def archive(cb: CallbackQuery):
    kb = issues_keyboard()
    if not kb:
        await cb.message.answer("Архив әзірше бос.")
    else:
        await cb.message.answer("Архивтен таңдаңыз 👇", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "buy_weekly")
async def buy_weekly(cb: CallbackQuery):
    PENDING[cb.from_user.id] = {"type": "weekly", "label": "Осы апта газеті"}
    await cb.message.answer(KASPI_TEXT.format(label="Осы апта газеті"))
    await cb.answer()

@dp.callback_query(F.data.startswith("buy_issue:"))
async def buy_issue(cb: CallbackQuery):
    label = cb.data.split("buy_issue:", 1)[1]
    PENDING[cb.from_user.id] = {"type": "issue", "label": label}
    await cb.message.answer(KASPI_TEXT.format(label=label))
    await cb.answer()

@dp.message(F.text == "/setweekly")
async def setweekly(message: Message):
    global WAIT_WEEKLY
    if message.from_user.id != ADMIN_ID:
        return
    WAIT_WEEKLY = True
    await message.answer("Осы аптаның PDF файлын жіберіңіз.")

@dp.message(F.text.startswith("/addissue"))
async def addissue(message: Message):
    global WAIT_ISSUE_LABEL
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer("Қолдану: /addissue №7 — 16.02.2026")
        return
    WAIT_ISSUE_LABEL = parts[1].strip()
    await message.answer(f"{WAIT_ISSUE_LABEL} үшін PDF жіберіңіз.")

@dp.message(F.document)
async def documents(message: Message):
    global WAIT_WEEKLY, WAIT_ISSUE_LABEL, DB

    if message.from_user.id == ADMIN_ID and WAIT_WEEKLY:
        DB["weekly_file_id"] = message.document.file_id
        save_db(DB)
        WAIT_WEEKLY = False
        await message.answer("Апталық PDF жаңартылды!")
        return

    if message.from_user.id == ADMIN_ID and WAIT_ISSUE_LABEL:
        DB["issues"][WAIT_ISSUE_LABEL] = message.document.file_id
        save_db(DB)
        await message.answer("Архивке қосылды!")
        WAIT_ISSUE_LABEL = None
        return

    user_id = message.from_user.id
    selected = PENDING.get(user_id)
    if not selected:
        await message.answer("Алдымен /start арқылы таңдаңыз.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Растау", callback_data=f"ok:{user_id}"),
            InlineKeyboardButton(text="❌ Бас тарту", callback_data=f"no:{user_id}")
        ]
    ])

    caption = f"Төлем чегі келді\nUser ID: {user_id}\nТаңдауы: {selected['label']}"

    await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption, reply_markup=kb)
    await message.answer("Чек қабылданды. Тексерілген соң PDF жіберіледі.")

@dp.callback_query(F.data.startswith("ok:"))
async def approve(cb: CallbackQuery):
    user_id = int(cb.data.split(":")[1])
    selected = PENDING.get(user_id)

    if selected["type"] == "weekly":
        file_id = DB.get("weekly_file_id")
    else:
        file_id = DB["issues"].get(selected["label"])

    await bot.send_document(user_id, file_id)
    await cb.message.edit_caption(cb.message.caption + "\nРАСТАЛДЫ")
    await cb.answer("Жіберілді")

@dp.callback_query(F.data.startswith("no:"))
async def reject(cb: CallbackQuery):
    user_id = int(cb.data.split(":")[1])
    await bot.send_message(user_id, "Төлем расталмады.")
    await cb.message.edit_caption(cb.message.caption + "\nБАС ТАРТЫЛДЫ")
    await cb.answer("Бас тартылды")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
  
