import os
import sqlite3
import random
import string
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Set BOT_TOKEN environment variable")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB = "detective_v2.db"

CASES = {
    "museum": {
        "title": "Тайна ночного музея",
        "victim": "Директор музея",
        "culprit": "охранник",
        "suspects": ["охранник", "куратор", "уборщица"],
        "clues": [
            "Камеры отключились ровно в 23:40.",
            "На полу найдена грязь с обуви охранника.",
            "В журнале охраны есть исправленная запись.",
            "Куратор утверждает, что был дома, но его машина стояла у музея."
        ],
        "interrogations": {
            "охранник": "Я ничего не видел. Хотя странно, что вы спрашиваете именно меня...",
            "куратор": "Я ушёл раньше. Проверьте записи, если не верите.",
            "уборщица": "Я слышала шаги возле зала, но никого не видела."
        }
    },
    "hotel": {
        "title": "Последний номер",
        "victim": "Постоялец номера 307",
        "culprit": "администратор",
        "suspects": ["администратор", "повар", "портье"],
        "clues": [
            "Ключ от номера был использован после полуночи.",
            "Портье видел администратора на третьем этаже.",
            "В журнале заселения есть подозрительная запись.",
            "Администратор соврал о своём местонахождении."
        ],
        "interrogations": {
            "администратор": "Я всю ночь был за стойкой. Других подробностей не будет.",
            "повар": "Я закончил смену до полуночи.",
            "портье": "Я видел человека возле номера 307."
        }
    },
    "train": {
        "title": "Убийство в экспрессе",
        "victim": "Пассажир первого вагона",
        "culprit": "проводник",
        "suspects": ["проводник", "пассажир", "начальник поезда"],
        "clues": [
            "Поезд не делал остановок в течение ночи.",
            "Купе открывали служебным ключом.",
            "На столе обнаружен билет проводника.",
            "Проводник сообщил неверное время обхода."
        ],
        "interrogations": {
            "проводник": "Я обходил вагоны. Ничего необычного.",
            "пассажир": "Я почти всю ночь спал.",
            "начальник поезда": "Я отвечаю за весь состав, но в купе не заходил."
        }
    },
    "island": {
        "title": "Тень на острове",
        "victim": "Владелец виллы",
        "culprit": "садовник",
        "suspects": ["садовник", "повар", "гость"],
        "clues": [
            "На берегу найдены свежие следы.",
            "Дверь виллы открывали изнутри.",
            "На одежде садовника обнаружена земля из теплицы.",
            "Садовник знал о тайном выходе."
        ],
        "interrogations": {
            "садовник": "Я весь вечер ухаживал за растениями.",
            "повар": "Я готовил ужин и никуда не уходил.",
            "гость": "Я приехал только накануне."
        }
    },
    "bank": {
        "title": "Ограбление века",
        "victim": "Банковское хранилище",
        "culprit": "кассир",
        "suspects": ["кассир", "директор", "инкассатор"],
        "clues": [
            "Сигнализация была отключена изнутри.",
            "Код доступа вводили вручную.",
            "Время отключения совпадает со сменой кассира.",
            "Кассир пытался скрыть свой график."
        ],
        "interrogations": {
            "кассир": "Я просто выполнял свою работу.",
            "директор": "У меня есть алиби. Проверяйте.",
            "инкассатор": "Я приехал по расписанию."
        }
    }
}


def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            case_key TEXT,
            clue_index INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS members (
            room_id INTEGER,
            user_id INTEGER,
            chat_id INTEGER,
            username TEXT,
            xp INTEGER DEFAULT 0,
            UNIQUE(room_id, user_id)
        )
    """)
    con.commit()
    con.close()


def active_room(user_id):
    con = db()
    result = con.execute("""
        SELECT r.id, r.code, r.case_key, r.clue_index
        FROM rooms r
        JOIN members m ON m.room_id = r.id
        WHERE m.user_id = ? AND r.status = 'active'
        ORDER BY r.id DESC LIMIT 1
    """, (user_id,)).fetchone()
    con.close()
    return result


def add_xp(user_id, room_id, amount):
    con = db()
    con.execute(
        "UPDATE members SET xp = xp + ? WHERE user_id = ? AND room_id = ?",
        (amount, user_id, room_id)
    )
    con.commit()
    con.close()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🕵️ **ДЕТЕКТИВ**\n\n"
        "Добро пожаловать в мир расследований!\n\n"
        "Команды:\n"
        "/new — создать расследование\n"
        "/join КОД — присоединиться к другу\n"
        "/cases — список расследований\n"
        "/clue — получить улику\n"
        "/suspects — подозреваемые\n"
        "/interrogate имя — допросить подозреваемого\n"
        "/accuse имя — обвинить преступника\n"
        "/say текст — написать напарнику\n"
        "/level — твой уровень\n"
        "/rules — правила игры",
        parse_mode="Markdown"
    )


@dp.message(Command("new"))
async def new_game(message: Message):
    case_key = random.choice(list(CASES.keys()))
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    con = db()
    cur = con.execute(
        "INSERT INTO rooms (code, case_key) VALUES (?, ?)",
        (code, case_key)
    )
    room_id = cur.lastrowid
    con.execute(
        "INSERT INTO members (room_id, user_id, chat_id, username) VALUES (?, ?, ?, ?)",
        (room_id, message.from_user.id, message.chat.id,
         message.from_user.username or message.from_user.first_name)
    )
    con.commit()
    con.close()

    case = CASES[case_key]
    await message.answer(
        f"🔎 **Расследование началось!**\n\n"
        f"Дело: {case['title']}\n"
        f"Потерпевший: {case['victim']}\n\n"
        f"Код комнаты: `{code}`\n"
        f"Отправь другу: `/join {code}`\n\n"
        "Когда будете готовы, используйте /clue.",
        parse_mode="Markdown"
    )


@dp.message(Command("join"))
async def join_game(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажи код: /join ABC123")
        return

    code = args[1].strip().upper()
    con = db()
    room = con.execute(
        "SELECT id FROM rooms WHERE code = ? AND status = 'active'",
        (code,)
    ).fetchone()

    if not room:
        con.close()
        await message.answer("Комната не найдена.")
        return

    room_id = room[0]
    count = con.execute(
        "SELECT COUNT(*) FROM members WHERE room_id = ?",
        (room_id,)
    ).fetchone()[0]

    if count >= 2:
        con.close()
        await message.answer("В этой комнате уже два сыщика.")
        return

    con.execute(
        "INSERT OR IGNORE INTO members (room_id, user_id, chat_id, username) VALUES (?, ?, ?, ?)",
        (room_id, message.from_user.id, message.chat.id,
         message.from_user.username or message.from_user.first_name)
    )
    con.commit()
    con.close()

    await message.answer("🤝 Ты присоединился к расследованию! Используй /clue.")


@dp.message(Command("cases"))
async def cases(message: Message):
    text = "📚 **Доступные расследования:**\n\n"
    for case in CASES.values():
        text += f"🔎 {case['title']}\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("clue"))
async def clue(message: Message):
    room = active_room(message.from_user.id)
    if not room:
        await message.answer("Сначала создай дело: /new")
        return

    room_id, code, case_key, index = room
    clues = CASES[case_key]["clues"]

    if index >= len(clues):
        await message.answer("Все улики уже найдены. Пора сопоставлять факты!")
        return

    await message.answer(
        f"🧩 **Улика №{index + 1}**\n\n{clues[index]}"
    )

    con = db()
    con.execute(
        "UPDATE rooms SET clue_index = clue_index + 1 WHERE id = ?",
        (room_id,)
    )
    con.commit()
    con.close()
    add_xp(message.from_user.id, room_id, 10)


@dp.message(Command("suspects"))
async def suspects(message: Message):
    room = active_room(message.from_user.id)
    if not room:
        await message.answer("Сначала создай дело: /new")
        return

    case = CASES[room[2]]
    text = "🕵️ **Подозреваемые:**\n\n"
    text += "\n".join("• " + name for name in case["suspects"])
    text += "\n\nДля допроса: `/interrogate имя`"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("interrogate"))
async def interrogate(message: Message):
    room = active_room(message.from_user.id)
    if not room:
        await message.answer("Сначала создай дело: /new")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Напиши имя: /interrogate охранник")
        return

    name = args[1].strip().lower()
    case = CASES[room[2]]
    answers = case["interrogations"]

    if name not in answers:
        await message.answer("Такого подозреваемого нет. Используй /suspects.")
        return

    await message.answer(
        f"🎙 **Допрос: {name}**\n\n{answers[name]}"
    )
    add_xp(message.from_user.id, room[0], 5)


@dp.message(Command("accuse"))
async def accuse(message: Message):
    room = active_room(message.from_user.id)
    if not room:
        await message.answer("Сначала создай дело: /new")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Напиши имя подозреваемого: /accuse охранник")
        return

    name = args[1].strip().lower()
    case = CASES[room[2]]

    if name == case["culprit"]:
        await message.answer(
            f"🎉 **ДЕЛО РАСКРЫТО!**\n\n"
            f"Преступник: {case['culprit']}.\n"
            "Отличная работа, детектив!",
            parse_mode="Markdown"
        )
        con = db()
        con.execute(
            "UPDATE rooms SET status = 'finished' WHERE id = ?",
            (room[0],)
        )
        con.commit()
        con.close()
        add_xp(message.from_user.id, room[0], 100)
    else:
        await message.answer(
            "❌ Неверное обвинение. Не торопись, проверь улики ещё раз."
        )


@dp.message(Command("say"))
async def say(message: Message):
    room = active_room(message.from_user.id)
    if not room:
        await message.answer("Сначала создай дело: /new")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Напиши сообщение: /say Я нашёл улику!")
        return

    con = db()
    partner = con.execute(
        "SELECT chat_id FROM members WHERE room_id = ? AND user_id != ?",
        (room[0], message.from_user.id)
    ).fetchone()
    con.close()

    if not partner:
        await message.answer("Пока в комнате нет напарника.")
        return

    try:
        await bot.send_message(
            partner[0],
            f"📨 Сообщение от напарника:\n{args[1]}"
        )
        await message.answer("Сообщение отправлено!")
    except Exception:
        await message.answer(
            "Не получилось отправить сообщение. Напарник должен сначала нажать /start у бота."
        )


@dp.message(Command("level"))
async def level(message: Message):
    con = db()
    result = con.execute(
        "SELECT SUM(xp) FROM members WHERE user_id = ?",
        (message.from_user.id,)
    ).fetchone()
    con.close()

    xp = result[0] or 0
    lvl = xp // 100 + 1

    await message.answer(
        f"🏆 Твой опыт: {xp} XP\n"
        f"⭐ Уровень сыщика: {lvl}"
    )


@dp.message(Command("rules"))
async def rules(message: Message):
    await message.answer(
        "📜 **Правила:**\n\n"
        "1. Создай комнату через /new.\n"
        "2. Пригласи друга командой /join КОД.\n"
        "3. Изучайте улики через /clue.\n"
        "4. Допрашивайте подозреваемых.\n"
        "5. Обсуждайте версии через /say.\n"
        "6. Когда будете уверены — обвиняйте преступника.\n\n"
        "За расследования начисляется XP!"
    )


async def main():
    init_db()
    print("Detective bot started")
    await dp.start_polling(bot)


# ===== ТАЙНОЕ ГОЛОСОВАНИЕ =====

@dp.message(Command("vote"))
async def start_vote(message: Message):
    room = active_room(message.from_user.id)

    if not room:
        await message.answer("Сначала создайте расследование через /new")
        return

    room_id, code, case_key, index = room
    case = CASES[case_key]

    con = db()    con.execute("""
        CREATE TABLE IF NOT EXISTS detective_vote_results (
            room_id INTEGER PRIMARY KEY
        )
    """)
    con.commit()
    con.execute("""
        CREATE TABLE IF NOT EXISTS detective_votes (
            room_id INTEGER,
            user_id INTEGER,
            suspect TEXT,
            PRIMARY KEY (room_id, user_id)
        )
    """)
    con.commit()
    con.close()

    builder = InlineKeyboardBuilder()

    for suspect in case["suspects"]:
        builder.button(
            text="🕵️ " + suspect.title(),
            callback_data=f"vote:{room_id}:{suspect}"
        )

    builder.adjust(1)

    await message.answer(
        "🗳 ТАЙНОЕ ГОЛОСОВАНИЕ\n\n"
        "Кто, по-твоему, виновен?\n"
        "Выбери подозреваемого. Твой выбор не увидит напарник.",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("vote:"))
async def process_vote(callback: CallbackQuery):
    _, room_id, suspect = callback.data.split(":", 2)
    room_id = int(room_id)

    con = db()    finished = con.execute(
        "SELECT 1 FROM detective_vote_results WHERE room_id = ?",
        (room_id,)
    ).fetchone()

    if finished:
        con.close()
        await callback.answer("Голосование уже завершено!", show_alert=True)
        return

    member = con.execute(
        "SELECT 1 FROM members WHERE room_id = ? AND user_id = ?",
        (room_id, callback.from_user.id)
    ).fetchone()

    if not member:
        con.close()
        await callback.answer("Ты не участник этого расследования!", show_alert=True)
        return

    con.execute("""
        INSERT INTO detective_votes (room_id, user_id, suspect)
        VALUES (?, ?, ?)
        ON CONFLICT(room_id, user_id)
        DO UPDATE SET suspect = excluded.suspect
    """, (room_id, callback.from_user.id, suspect))

    votes = con.execute(
        "SELECT user_id, suspect FROM detective_votes WHERE room_id = ?",
        (room_id,)
    ).fetchall()

    con.commit()
    con.close()

    await callback.answer("Твой голос принят!")

    if len(votes) < 2:
        return

    con = db()
    case_row = con.execute(
        "SELECT case_key FROM rooms WHERE id = ?",
        (room_id,)
    ).fetchone()
    con.close()

    if not case_row:
        return
    con = db()
    inserted = con.execute(
    "INSERT OR IGNORE INTO detective_vote_results (room_id) VALUES (?)",
    (room_id,)
    ).rowcount
    con.commit()
    con.close()

    if inserted == 0:
    await callback.answer("Голосование уже завершено!", show_alert=True)
    return
    culprit = CASES[case_row[0]]["culprit"]

    correct = sum(1 for _, choice in votes if choice == culprit)

    result = (
        "🎬 ИТОГИ ГОЛОСОВАНИЯ\n\n"
        + "\n".join(
            f"Сыщик {i + 1}: {choice.title()}"
            for i, (_, choice) in enumerate(votes)
        )
        + f"\n\n🔎 Настоящий преступник: {culprit.title()}"
        + f"\n\nПравильных голосов: {correct} из 2."
    )

    for user_id, choice in votes:
        if choice == culprit:
            add_xp(user_id, room_id, 50)

    await callback.message.answer(result) if __name__ == "__main__":
    asyncio.run(main())
