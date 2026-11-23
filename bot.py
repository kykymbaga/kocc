"""Small-group Kocc Barma quote bot. Python 3.10+, standard library only."""
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = json.loads((ROOT / "corpus.json").read_text(encoding="utf-8"))
STATE_PATH = Path(os.getenv("BOT_STATE_FILE", str(ROOT / "state.json")))
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BOT_USERNAME = "@koccbarmafallbot"
TARGET_USERNAME = "@StAnastasiaSt"
# Minsk uses UTC+03:00 year-round; this avoids a separate Windows tzdata dependency.
TZ = timezone(timedelta(hours=3), "Europe/Minsk")
SEND_AT = os.getenv("MORNING_TIME", "09:00")
POLL_AT = os.getenv("POLL_TIME", "18:00")
THRESHOLD = int(os.getenv("REPLY_EVERY", "40"))
BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

# Only translations with an editorial gloss are eligible. The small keyword
# map provides a transparent, deterministic thematic match, not AI moderation.
ELIGIBLE_IDS = {2, 3, 5, 9, 12, 13, 18, 27}
QUOTES = [q for q in CORPUS if q["id"] in ELIGIBLE_IDS and q["belarusian"]]
TOPICS = {
    "friendship": ("сябар", "сяброў", "дружб", "friend", "ami", "друг", "друж"),
    "leadership": ("улада", "улад", "лідар", "кіраў", "кароль", "government", "power", "roi", "leader"),
    "justice": ("справяд", "права", "суд", "justice", "правосуд", "раўнапраў"),
    "community": ("суполь", "народ", "краін", "грамад", "community", "people", "country"),
    "faith": ("вера", "рэлігі", "бог", "faith", "religion", "god"),
    "intolerance": ("цярпім", "талеран", "нецярп", "hate", "intoler", "разлад"),
}
TOPIC_QUOTES = {
    "friendship": (5,), "leadership": (3, 9), "justice": (18, 27),
    "community": (3, 9, 13), "faith": (13, 18), "intolerance": (12,),
}
POLL_QUESTIONS = [
    ("Якое пытанне, звязанае з Коцем Бармам, сёння найважнейшае?", [
        "Ці можа ўлада быць сваяком?", "Хто мае права раіць уладзе?",
        "Што робіць супольнасць моцнай?", "Калі парадак становіцца несправядлівасцю?",
    ]),
    ("Якая думка Коц Бармы найбольш патрэбная нашаму часу?", [
        "Улада павінна чуць людзей", "Супольнасць патрабуе ўзаемнай падтрымкі",
        "Вопыт старэйшых важны", "Ніводная традыцыя не павінна быць па-за крытыкай",
    ]),
    ("Што варта зрабіць, калі ўсе бачаць несправядлівасць, але маўчаць?", [
        "Назваць яе ўголас", "Аб’яднацца з іншымі", "Паставіць уладзе пытанне", "Не пагаджацца з маўчаннем",
    ]),
    ("Хто павінен вырашаць, што лічыць справядлівым для супольнасці?", [
        "Тыя, каго закранае рашэнне", "Абраныя прадстаўнікі", "Усе праз адкрытую размову", "Ніхто не павінен мець апошняга слова",
    ]),
]
FALLBACK_QUESTIONS = {
    "justice": "калі ўсе прызнаюць несправядлівасць, але ніхто не рызыкуе назваць яе, што насамрэч падтрымлівае гэты парадак?",
    "leadership": "каму служыць гэтае правіла — людзям ці тым, хто атрымаў права яго вызначаць?",
    "community": "хто застаецца па-за нашым «мы», калі мы гаворым ад імя ўсёй супольнасці?",
    "intolerance": "якую думку мы забараняем сабе нават абмеркаваць, і каму выгадна гэтае маўчанне?",
    "default": "што мы называем непазбежным толькі таму, што баімся разам змяніць гэта?",
}


def api(method, payload=None, timeout=40):
    body = urllib.parse.urlencode(payload or {}).encode()
    req = urllib.request.Request(BASE_URL + method, data=body)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Telegram API request failed ({method})") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API returned an error for {method}")
    return result["result"]


def load_state():
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state.setdefault("recent_messages", [])
        return state
    except FileNotFoundError:
        return {"message_count": 0, "last_morning_date": None, "last_quote_id": None, "offset": 0, "recent_messages": []}


def save_state(state):
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)


def choose_quote(text="", exclude=None):
    text = text.casefold()
    ids = []
    for topic, words in TOPICS.items():
        if any(word in text for word in words):
            ids.extend(TOPIC_QUOTES[topic])
    candidates = [q for q in QUOTES if (not ids or q["id"] in ids) and q["id"] != exclude]
    if not candidates:
        candidates = [q for q in QUOTES if q["id"] != exclude]
    if not candidates:
        candidates = QUOTES
    # Rotation makes repeated fallback quotes less likely and survives restarts.
    previous = load_state().get("last_quote_id")
    quote = next((q for q in candidates if q["id"] > (previous or 0)), candidates[0])
    state = load_state()
    state["last_quote_id"] = quote["id"]
    save_state(state)
    return quote


def quote_text(quote):
    text = quote["belarusian"]
    # Telegram still displays the bot account as sender; this 20% variation
    # only withholds the in-message attribution/signature.
    if random.random() >= 0.20:
        text += "\n\n— Коц Барма (вольны пераклад паводле гістарычнай запісы)"
    return text


def maybe_kocc_signature(text):
    if random.random() >= 0.20:
        return text + "\n\n— пытанне ў духу Коц Бармы"
    return text


def message_topic(text):
    text = text.casefold()
    for topic, words in TOPICS.items():
        if any(word in text for word in words):
            return topic
    return "default"


def radical_question(recent):
    context = "\n".join(f"{x.get('sender','Удзельнік')}: {x.get('text','')[:400]}" for x in recent[-5:])
    question = None
    if OPENAI_API_KEY:
        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": (
                    "Write one concise question in Belarusian, directly addressing @StAnastasiaSt. "
                    "Use the last five group messages as context. Make the question intellectually "
                    "radical and unsettling in a Kocc Barma-inspired public-wisdom style: expose an "
                    "assumption, power relation, or accepted rule that deserves scrutiny. Be respectful; "
                    "no personal insult, threat, or call for violence. Do not invent or quote Kocc Barma. "
                    "Return only the question, no preamble."
                )},
                {"role": "user", "content": "Апошнія паведамленні:\n" + context},
            ],
            "max_tokens": 100,
            "temperature": 0.9,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                answer = json.loads(response.read().decode("utf-8"))
            question = answer["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
            question = None
    if not question:
        question = FALLBACK_QUESTIONS[message_topic(context)]
    # Ensure the named questioner is directly addressed without depending on
    # the model to preserve the exact Telegram username.
    question = question.replace(TARGET_USERNAME, "").strip(" \n—,:;")
    return maybe_kocc_signature(f"{TARGET_USERNAME}, {question}")


def send_opinion_poll(state):
    poll = random.choice(POLL_QUESTIONS)
    api("sendPoll", {
        "chat_id": CHAT_ID,
        "question": poll[0],
        "options": json.dumps([{"text": option} for option in poll[1]], ensure_ascii=False),
        "is_anonymous": "true",
        "allows_multiple_answers": "false",
    })
    state["last_poll_date"] = datetime.now(TZ).date().isoformat()
    save_state(state)


def send_quick_command(message, state):
    text = (message.get("text") or "").casefold().split()[0]
    if text.startswith("/wisdom"):
        q = choose_quote()
        body = quote_text(q)
    elif text.startswith("/question") or text.startswith("/counter"):
        body = radical_question(state.get("recent_messages", []))
    elif text.startswith("/poll"):
        send_opinion_poll(state)
        return True
    else:
        return False
    api("sendMessage", {"chat_id": CHAT_ID, "text": body, "reply_to_message_id": message["message_id"]})
    return True


def is_mention(message):
    text = (message.get("text") or message.get("caption") or "").casefold()
    if "@koccbarmafallbot" in text:
        return True
    return any(
        entity.get("type") == "mention" and "@koccbarmafallbot" in text[
            entity.get("offset", 0):entity.get("offset", 0) + entity.get("length", 0)
        ].casefold()
        for entity in message.get("entities", []) + message.get("caption_entities", [])
    )


def inspired_reply(recent):
    if not OPENAI_API_KEY:
        context = "\n".join(entry.get("text", "") for entry in recent[-5:])
        return maybe_kocc_signature(FALLBACK_QUESTIONS[message_topic(context)])
    conversation = "\n".join(
        f"{entry.get('sender', 'Удзельнік')}: {entry.get('text', '')[:500]}"
        for entry in recent[-5:]
    )
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": (
                "Write in Belarusian. You are a contemporary assistant offering a brief, thoughtful, "
                "aphoristic response inspired by the themes and public-wisdom tradition associated "
                "with Kocc Barma Fall. Read the last five group messages and respond to their actual "
                "topic. Keep it to 1-3 short sentences, humane, sharp, and useful. Do not claim to be "
                "Kocc Barma, do not invent or attribute historical quotations to him, and do not "
                "endorse sexism, hierarchy, or violence. If the messages are unclear, ask one concise "
                "question."
            )},
            {"role": "user", "content": "Апошнія паведамленні групы:\n" + conversation},
        ],
        "max_tokens": 140,
        "temperature": 0.8,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return "Не атрымалася сфармаваць адказ зараз. Паспрабуйце пазначыць мяне яшчэ раз пазней."


def due_time(now):
    hour, minute = map(int, SEND_AT.split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def due_poll_time(now):
    hour, minute = map(int, POLL_AT.split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def send_morning(state):
    quote = choose_quote()
    api("sendMessage", {"chat_id": CHAT_ID, "text": quote_text(quote)})
    state["last_morning_date"] = datetime.now(TZ).date().isoformat()
    save_state(state)


def start_offset(state):
    # By default, ignore queued messages from before bot startup.
    if state.get("offset", 0) == 0 and os.getenv("DISCARD_BACKLOG", "true").lower() == "true":
        backlog = api("getUpdates", {"timeout": 0, "allowed_updates": json.dumps(["message"])})
        if backlog:
            state["offset"] = max(u["update_id"] for u in backlog) + 1
            save_state(state)


def main():
    state = load_state()
    start_offset(state)
    max_seconds = int(os.getenv("BOT_MAX_SECONDS", "0"))
    deadline = time.monotonic() + max_seconds if max_seconds > 0 else None
    print("Bot is running; token is not logged.")
    while deadline is None or time.monotonic() < deadline:
        now = datetime.now(TZ)
        today = now.date().isoformat()
        if now >= due_time(now) and state.get("last_morning_date") != today:
            try:
                send_morning(state)
            except RuntimeError:
                time.sleep(min(5, max(0, deadline - time.monotonic())) if deadline else 5)
                continue
        if now.weekday() == 6 and now >= due_poll_time(now) and state.get("last_poll_date") != today:
            try:
                send_opinion_poll(state)
            except RuntimeError:
                time.sleep(min(5, max(0, deadline - time.monotonic())) if deadline else 5)
                continue
        remaining = (deadline - time.monotonic()) if deadline else 30
        if remaining < 3:
            break
        poll_timeout = min(20, max(1, int(remaining - 2))) if deadline else 30
        try:
            updates = api("getUpdates", {
                "offset": state.get("offset", 0), "timeout": poll_timeout,
                "allowed_updates": json.dumps(["message"]),
            }, timeout=poll_timeout + 8)
        except RuntimeError:
            time.sleep(min(5, max(0, deadline - time.monotonic())) if deadline else 5)
            continue
        for update in updates:
            state["offset"] = update["update_id"] + 1
            message = update.get("message", {})
            chat = message.get("chat", {})
            if str(chat.get("id")) != str(CHAT_ID) or message.get("from", {}).get("is_bot"):
                save_state(state)
                continue
            sender = message.get("from", {})
            sender_name = " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")])) or "Удзельнік"
            message_text = message.get("text") or message.get("caption") or "[медыя або паведамленне без тэксту]"
            state.setdefault("recent_messages", []).append({"sender": sender_name, "text": message_text[:500]})
            state["recent_messages"] = state["recent_messages"][-5:]
            if (message.get("text") or "").startswith("/") and send_quick_command(message, state):
                state["message_count"] = state.get("message_count", 0) + 1
                save_state(state)
                continue
            if is_mention(message):
                answer = inspired_reply(state["recent_messages"])
                try:
                    api("sendMessage", {
                        "chat_id": CHAT_ID,
                        "text": answer,
                        "reply_to_message_id": message["message_id"],
                        "allow_sending_without_reply": True,
                    })
                except RuntimeError:
                    pass
            state["message_count"] = state.get("message_count", 0) + 1
            if state["message_count"] % THRESHOLD == 0:
                payload = {
                    "chat_id": CHAT_ID,
                    "text": radical_question(state.get("recent_messages", [])),
                    "reply_to_message_id": message["message_id"],
                    "allow_sending_without_reply": True,
                }
                try:
                    api("sendMessage", payload)
                except RuntimeError:
                    pass
            save_state(state)
    save_state(state)
    print("Bot run finished; state saved.")


if __name__ == "__main__":
    main()

