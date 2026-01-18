# tellebot.py — Groq Edition
import os
import time
import json
import requests
import telebot
from telebot import types

# ---------- CONFIG ----------
TG_TOKEN = os.getenv("TG_Token")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
MY_Key=os.getenv("MY_Key")


if not TG_TOKEN:
    raise ValueError("TG_Token not set")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set")

bot = telebot.TeleBot(TG_TOKEN)

GROQ_HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

# ---------- MEMORY ----------
memory = {}
MAX_RECENT = 15

def ensure_user(uid):
    if uid not in memory:
        memory[uid] = {
            "mode": "neo",
            "summary": "",
            "recent": []
        }

# ---------- PERSONALITIES ----------
PERSONALITIES = {
    "neo": {
        "system":
            "You are NEO from The Matrix. "
            "You MUST identify as Neo if asked who you are. "
            "Never claim to be Morpheus or Trinity. "
            "Never say you are an AI. "
            "Speak calmly and mysteriously."

    },
    "morpheus": {
        "system":
            "You are MORPHEUS from The Matrix. You are a wise mentor. "
            "Speak with confidence and guidance. Offer truth and perspective. "
            "Never say you are an AI."
    },
    "trinity": {
        "system":
            "You are TRINITY from The Matrix. You are pragmatic, loyal, and sharp. "
            "Give direct answers with quiet strength. Never say you are an AI."
        "If user anywhere mentions the word 'bhai' in the conversation just reply with 'Main bhai nahi behen hoon' "
    }
}


def generate_intro(mode):
    system_prompts = {
        "neo": (
            "You are NEO from The Matrix. "
            "Greet the user and Introduce yourself in 2–3 short, cinematic lines. "
            "You MUST identify yourself as Neo. "
            "Never say you are an AI. "
            "Tone: calm, mysterious, philosophical."
        ),
        "morpheus": (
            "You are MORPHEUS from The Matrix. "
            "Greet the user and Introduce yourself in 2–3 short, cinematic lines. "
            "You MUST identify yourself as Morpheus. "
            "Never say you are an AI. "
            "Tone: wise, mentor-like, confident."
        ),
        "trinity": (
            "You are TRINITY from The Matrix. "
            "Greet the user and Introduce yourself in 2–3 short, cinematic lines. "
            "You MUST identify yourself as Trinity. "
            "Never say you are an AI. "
            "Tone: direct, sharp, grounded."
        )
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompts[mode]},
            {"role": "user", "content": "Introduce yourself."}
        ],
        "temperature": 0.9,
        "max_tokens": 80
    }

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=GROQ_HEADERS,
        json=payload,
        timeout=20
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ---------- GROQ CHAT ----------
def groq_chat(system_prompt, messages):
    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.7,
        "max_tokens": 400
    }

    resp = requests.post(url, headers=GROQ_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# ---------- GROQ ASR ----------
def groq_transcribe(audio_bytes):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    files = {
        "file": ("voice.ogg", audio_bytes),
        "model": (None, "whisper-large-v3")
    }

    resp = requests.post(url, headers=headers, files=files, timeout=60)
    resp.raise_for_status()
    return resp.json()["text"]

# ---------- SUMMARIZATION ----------
def summarize_text(text):
    system = "Summarize the following conversation briefly, keeping only essential facts."
    return groq_chat(system, [{"role": "user", "content": text}])

# ---------- MEMORY MANAGEMENT ----------
def add_message(uid, role, content):
    ensure_user(uid)
    mem = memory[uid]
    mem["recent"].append({"role": role, "content": content})

    if len(mem["recent"]) > MAX_RECENT:
        to_sum = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in mem["recent"][:-12]
        )
        try:
            summary = summarize_text(to_sum)
            mem["summary"] = (mem["summary"] + "\n" + summary).strip()
        except Exception:
            mem["summary"] += "\n(Older context summarized.)"
        mem["recent"] = mem["recent"][-12:]

def build_messages(uid, user_text):
    ensure_user(uid)
    mem = memory[uid]
    messages = []

    if mem["summary"]:
        messages.append({
            "role": "user",
            "content": f"Conversation summary:\n{mem['summary']}"
        })

    for m in mem["recent"]:
        messages.append(m)

    messages.append({"role": "user", "content": user_text})
    return messages

# ---------- UI ----------
def mode_buttons():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("Neo", callback_data="mode:neo"),
        types.InlineKeyboardButton("Morpheus", callback_data="mode:morpheus"),
        types.InlineKeyboardButton("Trinity", callback_data="mode:trinity")
    )
    return kb

def typing(chat_id, t=0.3):
    try:
        bot.send_chat_action(chat_id, "typing")
        time.sleep(t)
    except Exception:
        pass

# ---------- COMMANDS ----------
@bot.message_handler(commands=["start"])
def start(msg):
    ensure_user(msg.chat.id)
    bot.reply_to(
        msg,
        "You have entered the Matrix.\n"
        "Choose your guide.\n"
        "Use /clear to erase memory."
    )
    bot.send_message(msg.chat.id, "Select a mode:", reply_markup=mode_buttons())

@bot.message_handler(commands=["clear"])
def clear(msg):
    ensure_user(msg.chat.id)
    memory[msg.chat.id]["summary"] = ""
    memory[msg.chat.id]["recent"] = []
    bot.reply_to(msg, "Memory erased.")

@bot.message_handler(commands=["neo", "morpheus", "trinity"])
def switch_mode(msg):
    uid = msg.chat.id
    mode = msg.text.lstrip("/").lower()

    ensure_user(uid)
    memory[uid]["mode"] = mode
    memory[uid]["recent"] = []  # prevent bleed

    try:
        intro = generate_intro(mode)
    except Exception as e:
        print("Intro gen error:", e)
        intro = f"I am {mode.capitalize()}."

    bot.reply_to(msg, intro)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mode:"))
def callback_mode(call):
    uid = call.message.chat.id
    mode = call.data.split(":", 1)[1]

    ensure_user(uid)
    memory[uid]["mode"] = mode
    memory[uid]["recent"] = []

    bot.answer_callback_query(call.id, f"{mode.capitalize()} selected")

    try:
        intro = generate_intro(mode)
    except Exception:
        intro = f"I am {mode.capitalize()}."

    bot.send_message(uid, intro)


# ---------- VOICE ----------
@bot.message_handler(content_types=["voice", "audio"])
def voice(msg):
    uid = msg.chat.id
    ensure_user(uid)

    file_id = msg.voice.file_id if msg.voice else msg.audio.file_id
    info = bot.get_file(file_id)
    audio = bot.download_file(info.file_path)

    typing(uid)
    try:
        text = groq_transcribe(audio)
        bot.reply_to(msg, f"Transcribed: {text}")
        process_message(uid, text, msg)
    except Exception:
        bot.reply_to(msg, "Audio could not be decoded.")

# ---------- TEXT ----------
def process_message(uid, text, msg=None):
    ensure_user(uid)
    typing(uid)

    system = PERSONALITIES[memory[uid]["mode"]]["system"]
    messages = build_messages(uid, text)

    placeholder = bot.send_message(uid, "...")
    try:
        reply = groq_chat(system, messages)
    except Exception as e:
        bot.delete_message(uid, placeholder.message_id)
        bot.reply_to(msg or uid, "The Matrix is unstable.")
        return

    add_message(uid, "user", text)
    add_message(uid, "assistant", reply)

    bot.delete_message(uid, placeholder.message_id)
    typing(uid, 0.2)
    bot.reply_to(msg or uid, reply)


ADMIN_CHAT_ID = -1003644557577



@bot.message_handler(content_types=["text"])
def handle_text(msg):
    try:
        if msg.chat.id == ADMIN_CHAT_ID or msg.chat.id == MY_Key:
            return
        info = (
            f"👤 User: @{msg.from_user.username}\n"
            f"🆔 ID: {msg.from_user.id}\n"
            f"💬 Msg: {msg.text}\n"
        )

        bot.send_message(ADMIN_CHAT_ID, info)
        # bot.copy_message(ADMIN_CHAT_ID, msg.chat.id, msg.message_id)
    except Exception as e:
        print("Log failed:", e)
    if msg.chat.type in ("group", "supergroup"):
        if not msg.text or f"@{bot.get_me().username}" not in msg.text:
            return
        text = msg.text.replace(f"@{bot.get_me().username}", "").strip()
    else:
        text = msg.text

    process_message(msg.chat.id, text, msg)


@bot.inline_handler(lambda q: True)
def inline_handler(inline_query):
    uid = inline_query.from_user.id
    query_text = inline_query.query

    ensure_user(uid)
    system = PERSONALITIES[memory[uid]["mode"]]["system"]

    try:
        answer = groq_chat(system, [{"role": "user", "content": query_text}])
    except Exception:
        answer = "The Matrix is silent."

    result = types.InlineQueryResultArticle(
        id="neo_answer",
        title="Ask the Matrix",
        input_message_content=types.InputTextMessageContent(answer)
    )

    bot.answer_inline_query(inline_query.id, [result], cache_time=1)


@bot.chosen_inline_handler(func=lambda c: True)
def inline_chosen(chosen):
    if chosen.chat.id == ADMIN_CHAT_ID or msg.chat.id == MY_Key:
            return
    uid = chosen.from_user.id
    username = chosen.from_user.username
    query_text = chosen.query
    result_id = chosen.result_id

    log = (
        "✅ INLINE RESULT USED\n"
        f"👤 User: @{username}\n"
        f"🆔 ID: {uid}\n"
        f"🔍 Query: {query_text}\n"
        f"🧩 Result ID: {result_id}"
    )

    bot.send_message(ADMIN_CHAT_ID, log)


# ---------- START ----------
if __name__ == "__main__":
    print("Matrix bot online (Groq).")
    bot.infinity_polling()


