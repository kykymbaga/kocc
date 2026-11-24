# Kocc Barma proverb database and Telegram bot

This folder contains a source-oriented database of the **57 numbered sayings** in the historical collection *La sagesse de Ncothie Barma*, plus a Telegram bot with Belarusian quotes and occasional discussion replies.

## What the corpus is (and is not)

The underlying text is a nineteenth-century Wolof manuscript published by C. Becker and M. Mbodj in *Chants Wolof et la sagesse de Ncothie Barma* (CNRS, 2000; earlier version 1978). The editors say the manuscript is preserved as Bibliothèque Sainte-Geneviève MS 3428 and present 57 sayings described as a short selection of sayings familiar in Kajoor. Their introduction says sayings 1–17 match Abbé Boilat's 1858 list, with five later overlaps (51, 52, 54, 55, 56), while the manuscript's precise compilation history remains uncertain. This is therefore the largest discrete, source-checked list located for this project, not proof that it is the largest collection ever recorded or an authorial manuscript by Kocc Barma himself.

The Wolof forms in `corpus.json` follow the editors' historical transcription and include OCR artifacts. They are not normalized modern Wolof. The Belarusian fields are filled only where the edition offers a usable French gloss/commentary; some are explicitly provisional. Null means “needs review by a Wolof speaker/editor,” not “no meaning.” Several sayings and nineteenth-century commentary are sexist, hierarchical, or otherwise unsuitable for automatic quotation. The bot's eligible set omits the most problematic lines, but its current eight-message pool still needs review by a Wolof-speaking cultural editor before public launch.

`internet-supplement.json` adds 20 sayings found in online Wolof proverb collections and cultural resources. These are deliberately labeled **general Wolof proverbs**, not additional Kocc Barma sayings: the large online collection *Wisdom of the Wolof Sages* includes some Kocc-attributed sayings, but most entries are not attributed to him. The widely circulated “Nit nitay garabam” is included as a general proverb; one contemporary profile attributes it to Kocc, but that attribution is not established by the 57-item historical collection. Treat all Belarusian text here as draft translation pending review by a Wolof speaker.

## Sources

- Becker, C. and M. Mbodj, *Chants Wolof et la sagesse de Ncothie Barma* (CNRS, 2000): [digitized scholarly edition](https://core.ac.uk/download/pdf/14511454.pdf).
- Abbé David Boilat, *Grammaire de la langue woloffe* (1858), “Maximes de Kothie Barma,” pp. 372–385: [Internet Archive scan](https://archive.org/details/grammairedelalan00boil).
- Boilat, *Esquisses sénégalaises* (1853), “Conversations spirituelles des Wolofs,” pp. 345–357: [Google Books record and scan](https://books.google.com/books?id=YDY6AQAAMAAJ).
- Richard Shawyer, *Wisdom of the Wolof Sages: A Collection of Proverbs from Senegal* (2009), an online compilation with over 700 numbered sayings, Wolof text, English translations, and notes: [PDF](https://www.wolofresources.org/language/download/proverbs.pdf).
- Souleymane Bachir Diagne on “Nit nitay garabam” and its wordplay variant: [Palais de Tokyo essay](https://palaisdetokyo.com/en/ressource/ubuntu-nite-et-humanisme/).

The manuscript/oral material is old, but this modern edition may have its own rights. Check the edition's reuse terms before redistributing the complete transcription. These Belarusian renderings are new, provisional translations of short sayings and not a substitute for rights clearance for a commercial book edition.

## Running Kocc

`bot.py` runs @koccbarmafallbot in the Telegram group selected by `TELEGRAM_CHAT_ID`. It uses long polling. Keep one poller for this token and remove any Telegram webhook before starting. Group administrator status or disabled group privacy lets Telegram deliver ordinary messages.

The chat bot runs on Python 3.10 or later. For example, from PowerShell:

```powershell
$env:TELEGRAM_BOT_TOKEN = "YOUR_TOKEN"
$env:TELEGRAM_CHAT_ID = "-1001234567890"
python .\bot.py
```

All times below use Minsk time (UTC+3). A delayed runner catches up once for the current local date.

| When | What Kocc sends |
| --- | --- |
| 09:00 daily | A short original fable with a historical proverb on the same theme |
| 20:30 daily | A standalone fable from the rotating story collection |
| Sunday at 18:00 | An anonymous-vote opinion poll |
| On request | `/story`, `/wisdom`, `/question`, `/counter`, or `/poll` |

Use `/story friendship` or reply to a message with `/story` to pick a theme. The stories and responses in `conversation-bank.json` are contemporary Belarusian writing. Historical translations come from `corpus.json` and retain their source number. Scheduled stories rotate through the collection. Topic requests give preference to the least recently used stories for that theme.

Mention Kocc or reply to one of his messages for a contextual answer. He uses up to five excerpts, including the message being replied to, and gives the newest speaker priority. With `OPENAI_API_KEY` set, direct questions use OpenAI and may incur charges. Local replies work without a key and cover all six themes. Occasional discussion replies are capped at four a day with a 30-minute cooldown. Every 40th human message may prompt a question.

### Speaking under the group name

Kocc reads his existing **Remain Anonymous** administrator setting at startup. With it enabled, Telegram controls the group sender identity. Kocc identifies himself in roughly four out of five text posts and leaves the other posts unsigned. The workflow logs whether Telegram returned the group as sender, without printing chat messages or identifiers. A custom administrator title can also appear beside a message. [Telegram administrator rights](https://core.telegram.org/api/rights#anonymous-admins)

### Native Telegram Stories

To publish the evening fable as a 24-hour photo Story, connect the intended Telegram Business account to Kocc, grant **Manage Stories**, and set the repository secret `TELEGRAM_BUSINESS_CONNECTION_ID` to that connection's ID. Telegram supplies the ID in the `business_connection.id` update when a connection is created or changed. The workflow installs Pillow when the secret is present. For local native publishing, install it with `python -m pip install Pillow`. The bot uploads a fresh 1080 × 1920 card with the story as its caption. Group stories also work independently when the account connection is absent or unavailable. [Telegram Story publishing](https://core.telegram.org/bots/api#poststory)

## GitHub Actions

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the repository's Actions secrets. `OPENAI_API_KEY` and `TELEGRAM_BUSINESS_CONNECTION_ID` are optional. The workflow runs on `main`. Changes to the bot, content, or workflow start it automatically. **Actions → Kocc Barma Telegram bot → Run workflow** starts it manually.

The schedule requests a run every five minutes, starting at two minutes past the hour. GitHub can delay or drop scheduled events. Each scheduled job starts three consecutive 255-second polling sessions to cover more of the gap before the next event. Updates to `main` and manual starts run one session. All triggers share a concurrency group so only one runner polls Telegram at a time. [GitHub schedule events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

The workflow imports the previous state cache on first upgrade. New caches encrypt the offset, recent context, and daily delivery records with the Telegram bot token. After rotating the token, clear the old `kocc-private-v1-` and legacy `kocc-state-` caches before starting fresh. Clearing state loses the current day's delivery records. Locally, `BOT_STATE_FILE` selects the state file and `DISCARD_BACKLOG=true` skips pending updates on a fresh start.

Edit `MORNING_TIME`, `STORY_TIME`, or `POLL_TIME` in the workflow to change delivery times. `TOPICS`, `TOPIC_QUOTES`, and `ELIGIBLE_IDS` in `bot.py` control the thematic matches and eligible historical translations.

