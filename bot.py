import asyncio, os, random, secrets, string
from datetime import datetime, timezone
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN")
DB = os.getenv("DATABASE_PATH", "/app/detective.db")
if not TOKEN:
    raise RuntimeError("Set BOT_TOKEN environment variable")
dp = Dispatcher()

CASES = [
 {"title":"Дело №014: Последний поезд","intro":"В 23:40 из закрытого вагона исчезла папка с секретными документами. В вагоне были проводник, журналист и инженер.","clues":[("Билет","На полу билет, проколотый компостером в 22:55 — после отправления поезда."),("Окно","На защёлке окна свежая царапина, хотя окно якобы не открывали."),("Журнал","Инженер сказал, что чинил свет, но журнал показывает: электричество не отключалось.")],"suspects":["Проводник","Журналист","Инженер"],"answer":2,"explain":"Инженер солгал о ремонте света и воспользовался техническим люком."},
 {"title":"Дело №027: Часы без времени","intro":"Из кабинета коллекционера пропали старинные часы. Сигнализация не сработала. В комнате нашли мокрый след и записку с цифрой 17.","clues":[("След","След ведёт от окна к сейфу, но возле окна пол совершенно сухой."),("Записка","Цифра 17 написана зеркально."),("Механизм","Смотритель знал, что механизм часов сняли накануне.")],"suspects":["Коллекционер","Смотритель","Гость"],"answer":1,"explain":"Смотритель знал о снятом механизме и инсценировал остановку часов."}
]
PUZZLES=[("Чем больше из неё берут, тем больше она становится?","яма"),("Я всегда впереди тебя, но увидеть меня нельзя. Что это?","будущее"),("Что можно сломать, даже не прикасаясь?","обещание")]
MISSIONS=["Придумай алиби для вымышленного подозреваемого за 60 секунд.","Зашифруй фразу сдвигом букв на 3 позиции.","Задай напарнику вопрос, на который нельзя ответить «да» или «нет».","Найди сегодня три детали вокруг, которые обычно не замечаешь."]
ANSWERS={}

async def init_db():
 async with aiosqlite.connect(DB) as db:
  await db.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,xp INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS rooms(code TEXT PRIMARY KEY,owner INTEGER,case_idx INTEGER DEFAULT 0,clues TEXT DEFAULT '',status TEXT DEFAULT 'open');
  CREATE TABLE IF NOT EXISTS members(room TEXT,user_id INTEGER,UNIQUE(room,user_id));""")
  await db.commit()

async def ensure_user(u):
 async with aiosqlite.connect(DB) as db:
  await db.execute("INSERT OR IGNORE INTO users(id,name) VALUES(?,?)",(u.id,u.full_name))
  await db.execute("UPDATE users SET name=? WHERE id=?",(u.full_name,u.id)); await db.commit()

async def get_room(uid):
 async with aiosqlite.connect(DB) as db:
  cur=await db.execute("SELECT room FROM members WHERE user_id=?",(uid,)); r=await cur.fetchone()
  return r[0] if r else None

async def room_members(code):
 async with aiosqlite.connect(DB) as db:
  cur=await db.execute("SELECT user_id FROM members WHERE room=?",(code,))
  return [x[0] for x in await cur.fetchall()]

def menu():
 b=InlineKeyboardBuilder()
 for label,data in [("🕵️ Создать комнату","create"),("🔐 Ввести код","join"),("📁 Начать расследование","case"),("🧩 Загадка","puzzle"),("🎯 Тайное задание","mission"),("🏆 Мой профиль","profile")]:
  b.button(text=label,callback_data=data)
 b.adjust(1); return b.as_markup()

@dp.message(CommandStart())
async def start(m:Message):
 await ensure_user(m.from_user)
 await m.answer(f"🕵️ <b>ДЕТЕКТИВ — секретное агентство</b>\\nПривет, {m.from_user.first_name}! Создай комнату и пригласи друга. Общение — через /say текст.",reply_markup=menu(),parse_mode="HTML")

@dp.callback_query(F.data=="create")
async def create(c:CallbackQuery):
 await ensure_user(c.from_user)
 if await get_room(c.from_user.id):
  await c.message.answer("Ты уже в комнате. Для выхода используй /leave.")
 else:
  code=''.join(random.choices(string.ascii_uppercase+string.digits,k=6))
  async with aiosqlite.connect(DB) as db:
   await db.execute("INSERT INTO rooms(code,owner) VALUES(?,?)",(code,c.from_user.id))
   await db.execute("INSERT INTO members(room,user_id) VALUES(?,?)",(code,c.from_user.id)); await db.commit()
  await c.message.answer(f"Комната создана! Отправь другу код: <code>{code}</code>",parse_mode="HTML")
 await c.answer()

@dp.callback_query(F.data=="join")
async def join_hint(c:CallbackQuery):
 await c.message.answer("Введи команду: /join ABC123 — подставь код комнаты друга.")
 await c.answer()

@dp.message(Command("join"))
async def join(m:Message):
 await ensure_user(m.from_user)
 p=m.text.split(maxsplit=1)
 if len(p)<2: return await m.answer("Формат: /join ABC123")
 if await get_room(m.from_user.id): return await m.answer("Сначала выйди из текущей комнаты: /leave")
 code=p[1].strip().upper()
 async with aiosqlite.connect(DB) as db:
  cur=await db.execute("SELECT COUNT(*) FROM members WHERE room=? AND user_id IN (SELECT owner FROM rooms WHERE code=?)",(code,code))
  exists=await db.execute("SELECT 1 FROM rooms WHERE code=? AND status='open'",(code,))
  if not await exists.fetchone(): return await m.answer("Комната не найдена.")
  cur=await db.execute("SELECT COUNT(*) FROM members WHERE room=?",(code,))
  if (await cur.fetchone())[0]>=2: return await m.answer("Комната уже заполнена.")
  await db.execute("INSERT INTO members(room,user_id) VALUES(?,?)",(code,m.from_user.id)); await db.commit()
 await m.answer(f"Ты в комнате {code}! Пиши другу через /say текст.")
 for uid in await room_members(code):
  if uid!=m.from_user.id:
   try: await m.bot.send_message(uid,f"🟢 {m.from_user.full_name} присоединился к комнате.")
   except Exception: pass

@dp.message(Command("leave"))
async def leave(m:Message):
 code=await get_room(m.from_user.id)
 if not code: return await m.answer("Ты не в комнате.")
 async with aiosqlite.connect(DB) as db:
  await db.execute("DELETE FROM members WHERE room=? AND user_id=?",(code,m.from_user.id)); await db.commit()
 await m.answer("Ты вышел из комнаты.")

@dp.message(Command("say"))
async def say(m:Message):
 code=await get_room(m.from_user.id)
 if not code: return await m.answer("Сначала создай комнату или войди: /join КОД")
 body=m.text.partition(" ")[2].strip()
 if not body: return await m.answer("Пример: /say Привет, напарник!")
 for uid in await room_members(code):
  if uid!=m.from_user.id:
   try: await m.bot.send_message(uid,f"💬 <b>{m.from_user.full_name}</b>:\\n{body}",parse_mode="HTML")
   except Exception: pass
 await m.answer("Сообщение отправлено напарнику.")

async def begin_case(m,bot,user_id):
 code=await get_room(user_id)
 if not code: return await m.answer("Сначала создай комнату и пригласи друга.")
 async with aiosqlite.connect(DB) as db:
  await db.execute("UPDATE rooms SET case_idx=0,clues='' WHERE code=?",(code,)); await db.commit()
 case=CASES[0]; msg=f"📁 <b>{case['title']}</b>\\n{case['intro']}\\n\\nОткрывайте улики: /clue"
 for uid in await room_members(code):
  try: await bot.send_message(uid,msg,parse_mode="HTML")
  except Exception: pass

@dp.callback_query(F.data=="case")
async def case_button(c:CallbackQuery):
 await begin_case(c.message,c.bot,c.from_user.id); await c.answer()

@dp.message(Command("case"))
async def case_command(m:Message):
 await begin_case(m,m.bot,m.from_user.id)

@dp.message(Command("clue"))
async def clue(m:Message):
 code=await get_room(m.from_user.id)
 if not code: return await m.answer("Сначала войди в комнату.")
 async with aiosqlite.connect(DB) as db:
  cur=await db.execute("SELECT case_idx,clues FROM rooms WHERE code=?",(code,)); row=await cur.fetchone()
  if not row: return
  idx,seen=row; case=CASES[idx]; used=[int(x) for x in seen.split(",") if x]
  nxt=next((i for i in range(len(case["clues"])) if i not in used),None)
  if nxt is None: return await m.answer("Улики закончились. Обсудите версию и используйте /accuse 1, 2 или 3.")
  used.append(nxt); await db.execute("UPDATE rooms SET clues=? WHERE code=?",(",".join(map(str,used)),code)); await db.commit()
 label,detail=case["clues"][nxt]
 for uid in await room_members(code):
  try: await m.bot.send_message(uid,f"🔎 <b>{label}</b>\\n{detail}",parse_mode="HTML")
  except Exception: pass

@dp.message(Command("accuse"))
async def accuse(m:Message):
 code=await get_room(m.from_user.id)
 if not code: return await m.answer("Сначала войди в комнату.")
 p=m.text.split()
 if len(p)!=2 or p[1] not in ("1","2","3"): return await m.answer("Формат: /accuse 1 (или 2, 3)")
 case=CASES[0]; choice=int(p[1])-1
 if choice==case["answer"]:
  async with aiosqlite.connect(DB) as db:
   await db.execute("UPDATE users SET xp=xp+100 WHERE id IN (SELECT user_id FROM members WHERE room=?)",(code,)); await db.commit()
  result=f"✅ Верно! Виновен: {case['suspects'][case['answer']]}.\\n{case['explain']}\\n+100 XP каждому."
 else: result=f"❌ Не угадали: {case['suspects'][choice]}. Соберите больше улик и попробуйте снова."
 for uid in await room_members(code):
  try: await m.bot.send_message(uid,result)
  except Exception: pass

@dp.callback_query(F.data=="puzzle")
@dp.message(Command("puzzle"))
async def puzzle(e):
 m=e.message if isinstance(e,CallbackQuery) else e
 q,a=random.choice(PUZZLES); ANSWERS[m.chat.id]=a
 await m.answer(f"🧩 <b>Загадка</b>\\n{q}\\nОтвет отправь командой /answer текст",parse_mode="HTML")
 if isinstance(e,CallbackQuery): await e.answer()

@dp.message(Command("answer"))
async def answer(m:Message):
 expected=ANSWERS.get(m.chat.id); guess=m.text.partition(" ")[2].strip().lower()
 if not expected: return await m.answer("Сначала запусти /puzzle")
 if guess==expected:
  await ensure_user(m.from_user)
  async with aiosqlite.connect(DB) as db:
   await db.execute("UPDATE users SET xp=xp+25 WHERE id=?",(m.from_user.id,)); await db.commit()
  ANSWERS.pop(m.chat.id,None); await m.answer("🎉 Верно! +25 XP.")
 else: await m.answer("Пока неверно. Попробуй ещё.")

@dp.callback_query(F.data=="mission")
async def mission(c:CallbackQuery):
 await c.message.answer("🎯 <b>Тайное задание</b>\\n"+random.choice(MISSIONS),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="profile")
async def profile(c:CallbackQuery):
 await ensure_user(c.from_user)
 async with aiosqlite.connect(DB) as db:
  cur=await db.execute("SELECT xp FROM users WHERE id=?",(c.from_user.id,)); xp=(await cur.fetchone())[0]
 await c.message.answer(f"🪪 <b>Досье агента</b>\\nОпыт: {xp} XP\\nУровень: {1+xp//100}",parse_mode="HTML"); await c.answer()

@dp.message()
async def fallback(m:Message):
 await m.answer("Команды: /case /clue /accuse 1 /puzzle /answer текст /say текст /leave")

async def main():
 await init_db()
 async with Bot(TOKEN) as bot:
  await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
