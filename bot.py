"""Small-group Kocc Barma-inspired discussion bot; Python 3.10+, stdlib only."""
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
CONVERSATION_BANK = json.loads((ROOT / "conversation-bank.json").read_text(encoding="utf-8"))
STATE_PATH = Path(os.getenv("BOT_STATE_FILE", str(ROOT / "state.json")))
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BOT_USERNAME = "@koccbarmafallbot"
# Minsk uses UTC+03:00 year-round; this avoids a separate Windows tzdata dependency.
TZ = timezone(timedelta(hours=3), "Europe/Minsk")
SEND_AT = os.getenv("MORNING_TIME", "09:00")
POLL_AT = os.getenv("POLL_TIME", "18:00")
THRESHOLD = int(os.getenv("REPLY_EVERY", "40"))
AUTO_REPLY_CHANCE = float(os.getenv("AUTO_REPLY_CHANCE", "0.22"))
AUTO_REPLY_COOLDOWN_SECONDS = int(os.getenv("AUTO_REPLY_COOLDOWN_SECONDS", "1800"))
AUTO_REPLY_DAILY_MAX = int(os.getenv("AUTO_REPLY_DAILY_MAX", "4"))
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
    except urllib.error.HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
            detail = error_body.get("description", f"HTTP {exc.code}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = f"HTTP {exc.code}"
        raise RuntimeError(f"Telegram {method} failed: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Telegram API request failed ({method})") from exc
    if not result.get("ok"):
        # Telegram's description helps diagnose cases such as two pollers
        # competing for getUpdates. It contains no bot token or message text.
        raise RuntimeError(f"Telegram {method} failed: {result.get('description', 'unknown API error')}")
    return result["result"]


def load_state():
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        state = {"message_count": 0, "last_morning_date": None, "last_poll_date": None,
                 "last_quote_id": None, "offset": 0, "recent_messages": []}
    state.setdefault("recent_messages", [])
    state.setdefault("auto_reply_count", 0)
    state.setdefault("auto_reply_date", None)
    state.setdefault("last_auto_reply_at", 0)
    state.setdefault("mentioned_usernames", [])
    state.setdefault("mentioned_usernames_date", None)
    return state


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


def choose_local_text(group, topic):
    entries = CONVERSATION_BANK[group]
    return random.choice(entries.get(topic, entries.get("default", [])))


def choose_member_to_invite(state, current_username=None):
    today = datetime.now(TZ).date().isoformat()
    if state.get("mentioned_usernames_date") != today:
        state["mentioned_usernames_date"] = today
        state["mentioned_usernames"] = []
    already_asked = {name.casefold() for name in state.get("mentioned_usernames", [])}
    current_username = (current_username or "").casefold()
    candidates = []
    for item in reversed(state.get("recent_messages", [])[-10:]):
        username = (item.get("username") or "").strip().lstrip("@").casefold()
        if username and username != current_username and username not in already_asked:
            candidates.append(username)
    if not candidates:
        return None
    chosen = random.choice(list(dict.fromkeys(candidates)))
    state.setdefault("mentioned_usernames", []).append(chosen)
    return "@" + chosen


def radical_question(recent, state, current_username=None):
    context = "\n".join(x.get("text", "") for x in recent[-5:])
    question = choose_local_text("questions", message_topic(context))
    member = choose_member_to_invite(state, current_username)
    if member:
        return f"{member}, калі зручна, як ты гэта бачыш?\n{question}"
    return question


def maybe_auto_reply(message, state):
    text = (message.get("text") or message.get("caption") or "").strip()
    if len(text) < 28 or text.startswith("/") or is_mention(message):
        return False
    today = datetime.now(TZ).date().isoformat()
    if state.get("auto_reply_date") != today:
        state["auto_reply_date"] = today
        state["auto_reply_count"] = 0
    if state.get("auto_reply_count", 0) >= AUTO_REPLY_DAILY_MAX:
        return False
    now = time.time()
    if now - state.get("last_auto_reply_at", 0) < AUTO_REPLY_COOLDOWN_SECONDS:
        return False
    topic = message_topic(text)
    question_like = "?" in text or any(word in text.casefold() for word in ("думаю", "лічу", "чаму", "як вы", "што калі"))
    if topic == "default" and not question_like:
        return False
    chance = min(0.45, AUTO_REPLY_CHANCE + (0.12 if question_like else 0))
    if random.random() > chance:
        return False
    response = choose_local_text("responses", topic)
    sender_username = message.get("from", {}).get("username")
    if random.random() < 0.30:
        member = choose_member_to_invite(state, sender_username)
        if member:
            response = f"{member}, калі зручна, што ты думаеш?\n{response}"
    try:
        api("sendMessage", {
            "chat_id": CHAT_ID,
            "text": response,
            "reply_to_message_id": message["message_id"],
            "allow_sending_without_reply": True,
        })
    except RuntimeError as exc:
        print(f"Could not send local discussion reply: {exc}", flush=True)
        return False
    state["auto_reply_count"] = state.get("auto_reply_count", 0) + 1
    state["last_auto_reply_at"] = now
    save_state(state)
    print("Sent an occasional local discussion reply.", flush=True)
    return True


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
        body = radical_question(state.get("recent_messages", []), state, message.get("from", {}).get("username"))
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
        print("OpenAI mention reply failed; using a brief fallback response.", flush=True)
        return "Не атрымалася сфармаваць адказ зараз. Паспрабуйце пазначыць мяне яшчэ раз пазней."


def due_time(now):
    hour, minute = map(int, SEND_AT.split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def due_poll_time(now):
    hour, minute = map(int, POLL_AT.split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def send_morning(state):
    quote = choose_quote()
    story = random.choice(CONVERSATION_BANK["stories"])
    body = f"Кароткая байка:\n{story}\n\nСённяшняя прымаўка:\n{quote_text(quote)}"
    api("sendMessage", {"chat_id": CHAT_ID, "text": body})
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
    print("Bot polling started; credentials and message text are not logged.", flush=True)
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
        except RuntimeError as exc:
            print(f"Telegram polling problem: {exc}", flush=True)
            time.sleep(min(5, max(0, deadline - time.monotonic())) if deadline else 5)
            continue
        print(f"Telegram returned {len(updates)} update(s).", flush=True)
        for update in updates:
            state["offset"] = update["update_id"] + 1
            message = update.get("message", {})
            chat = message.get("chat", {})
            if str(chat.get("id")) != str(CHAT_ID):
                print("Ignoring update from a different chat.", flush=True)
                save_state(state)
                continue
            if message.get("from", {}).get("is_bot"):
                save_state(state)
                continue
            mention_detected = is_mention(message)
            print(f"Target-group message received; mention_detected={mention_detected}.", flush=True)
            if mention_detected:
                print("Target-group mention detected; preparing a reply.", flush=True)
            sender = message.get("from", {})
            sender_name = " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")])) or "Удзельнік"
            message_text = message.get("text") or message.get("caption") or "[медыя або паведамленне без тэксту]"
            state.setdefault("recent_messages", []).append({
                "sender": sender_name,
                "username": sender.get("username"),
                "text": message_text[:500],
            })
            state["recent_messages"] = state["recent_messages"][-10:]
            if (message.get("text") or "").startswith("/") and send_quick_command(message, state):
                state["message_count"] = state.get("message_count", 0) + 1
                save_state(state)
                continue
            if mention_detected:
                answer = inspired_reply(state["recent_messages"])
                try:
                    api("sendMessage", {
                        "chat_id": CHAT_ID,
                        "text": answer,
                        "reply_to_message_id": message["message_id"],
                        "allow_sending_without_reply": True,
                    })
                    print("Mention reply sent.", flush=True)
                except RuntimeError as exc:
                    print(f"Could not send mention reply: {exc}", flush=True)
            auto_replied = False if mention_detected else maybe_auto_reply(message, state)
            state["message_count"] = state.get("message_count", 0) + 1
            if state["message_count"] % THRESHOLD == 0 and not mention_detected and not auto_replied:
                payload = {
                    "chat_id": CHAT_ID,
                    "text": radical_question(state.get("recent_messages", []), state, sender.get("username")),
                    "reply_to_message_id": message["message_id"],
                    "allow_sending_without_reply": True,
                }
                try:
                    api("sendMessage", payload)
                    print("Fortieth-message question sent.", flush=True)
                except RuntimeError as exc:
                    print(f"Could not send fortieth-message question: {exc}", flush=True)
            save_state(state)
    save_state(state)
    print("Bot run finished; state saved.", flush=True)


if __name__ == "__main__":
    main()

