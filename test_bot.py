import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-10042")
import bot


class BotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.enter_patch(patch.object(bot, "STATE_PATH", Path(temp.name) / "state.json"))
        self.enter_patch(patch.object(bot, "OPENAI_API_KEY", ""))
        self.enter_patch(patch.object(bot, "STORY_CONNECTION", ""))
        self.api = self.enter_patch(patch.object(bot, "api"))
        self.api.return_value = {"chat": {"id": -42}, "sender_chat": {"id": -42}, "message_id": 7}
        self.state = bot.load_state()

    def enter_patch(self, item):
        self.addCleanup(item.stop)
        return item.start()

    def test_direct_reply_uses_recent_topic_and_all_offline_banks(self):
        for topic, stems in bot.TOPICS.items():
            recent = [{"text": "community"}, {"text": stems[0]}, {"text": "А чаму?"}]
            first = bot.inspired_reply(recent, self.state)
            self.assertIn(first, bot.CONVERSATION_BANK["responses"][topic])
            self.assertNotEqual(first, bot.inspired_reply(recent, self.state))
        self.assertEqual(bot.message_topic("This family is waiting"), "default")

    def test_anonymous_parent_reply_and_named_command(self):
        self.state.update(anonymous_admin=True, recent_messages=[{"text": "/story"}])
        for roll, signed in [(0.15, False), (0.9, True)]:
            msg = {"text": "/story@koccbarmafallbot", "message_id": 1,
                   "reply_to_message": {"text": "friendship"}, "is_topic_message": True, "message_thread_id": 33}
            with patch.object(bot.random, "random", return_value=roll):
                self.assertTrue(bot.send_quick_command(msg, self.state))
            payload = self.api.call_args.args[1]
            self.assertEqual(payload["text"].endswith(bot.BOT_USERNAME), signed)
            self.assertEqual(payload["message_thread_id"], 33)
            title = payload["text"].splitlines()[0]
            self.assertTrue(any(s["title"] == title and s["topic"] == "friendship" for s in bot.CONVERSATION_BANK["stories"]))
        self.assertTrue(bot.is_addressed({"text": "Якім чынам?", "reply_to_message": {"message_id": 7}}, self.state))
        self.assertFalse(bot.is_addressed({"text": "@koccbarmafallbot_test"}, self.state))
        self.assertFalse(bot.send_quick_command({"text": "/story@anotherbot"}, self.state))

    def test_end_of_story_cycle_survives_restart(self):
        titles = []
        for _ in bot.CONVERSATION_BANK["stories"]:
            story = bot.choose_story(self.state)
            titles.append(story["title"])
            bot.remember_story(self.state, story)
            bot.save_state(self.state)
            self.state = bot.load_state()
        self.assertEqual(len(set(titles)), len(titles))
        self.assertEqual(bot.choose_story(self.state)["title"], titles[0])

    def test_quote_rotation_uses_live_state(self):
        first = bot.choose_quote(self.state, "leadership")
        bot.save_state(self.state)
        self.assertNotEqual(bot.choose_quote(bot.load_state(), "leadership")["id"], first["id"])
        self.assertIn(str(first["id"]), bot.quote_text(first))

    def test_story_upload_retry_does_not_repost_to_chat(self):
        now = datetime(2026, 11, 24, 21, tzinfo=bot.TZ)
        self.state["last_morning_date"] = now.date().isoformat()
        self.api.side_effect = [self.api.return_value, RuntimeError("temporary upload error"), {"id": 8}]
        renderer = Mock()
        renderer.render_card.return_value = b"card"
        with patch.object(bot, "STORY_CONNECTION", "demo"), patch.dict("sys.modules", story_card=renderer):
            bot.scheduled_posts(self.state, now.replace(hour=20, minute=29))
            self.api.assert_not_called()
            bot.scheduled_posts(self.state, now)
            bot.scheduled_posts(bot.load_state(), now)
            bot.scheduled_posts(bot.load_state(), now.replace(minute=16))
            bot.scheduled_posts(bot.load_state(), now.replace(minute=17))
        self.assertEqual([c.args[0] for c in self.api.call_args_list], ["sendMessage", "postStory", "postStory"])
        self.assertEqual(bot.load_state()["last_native_date"], "2026-11-24")

    def test_provider_failure_uses_topic_reply(self):
        with patch.object(bot, "OPENAI_API_KEY", "test"), patch("urllib.request.urlopen", side_effect=TimeoutError):
            answer = bot.inspired_reply([{"text": "Вера і сумнеў"}], self.state)
        self.assertIn(answer, bot.CONVERSATION_BANK["responses"]["faith"])


class StoryUploadTests(unittest.TestCase):
    def test_telegram_receives_a_new_multipart_photo(self):
        photo = b"\xff\xd8demo\xff\xd9"
        with patch("urllib.request.urlopen") as http:
            http.return_value.__enter__.return_value.read.return_value = b'{"ok":true,"result":{"id":1}}'
            bot.api("postStory", {"content": json.dumps({"type": "photo", "photo": "attach://card"})}, photo=photo)
            req = http.call_args.args[0]
        parts = BytesParser(policy=default).parsebytes(
            f"Content-Type: {req.get_header('Content-type')}\r\n\r\n".encode() + req.data)
        field, upload = parts.iter_parts()
        self.assertEqual(json.loads(field.get_payload())["photo"], "attach://card")
        self.assertEqual(upload.get_param("name", header="Content-Disposition"), "card")
        self.assertEqual(upload.get_content_type(), "image/jpeg")
        self.assertEqual(upload.get_payload(decode=True), photo)

    def test_every_native_card_meets_telegram_photo_limits(self):
        try:
            from PIL import Image
            from story_card import render_card
        except ImportError:
            self.skipTest("Install Pillow to test native cards")
        for story in bot.CONVERSATION_BANK["stories"]:
            data = render_card(story)
            with Image.open(io.BytesIO(data)) as card:
                self.assertEqual((card.format, card.size), ("JPEG", (1080, 1920)))
            self.assertLess(len(data), 10_000_000)


if __name__ == "__main__":
    unittest.main()
