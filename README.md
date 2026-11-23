# Kocc Barma proverb database and Telegram bot

This folder contains a source-oriented database of the **57 numbered sayings** in the historical collection *La sagesse de Ncothie Barma*, plus a small Telegram bot that posts a Belarusian rendering each morning and replies to each 40th new group message.

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

## Bot setup

Python 3.10 or later; no third-party packages. The installed bot is `@koccbarmafallbot`, configured for the group whose chat ID is set in `run-bot.ps1`. The bot uses Telegram long polling, so do not configure a webhook for it.

PowerShell example (the token remains in the current shell's environment):

```powershell
$env:TELEGRAM_BOT_TOKEN = "YOUR_TOKEN"
$env:TELEGRAM_CHAT_ID = "-1001234567890"
$env:BOT_TIMEZONE = "Europe/Minsk"
$env:MORNING_TIME = "09:00"
python .\bot.py
```

The morning post is sent once per day at 09:00 Europe/Minsk. A native opinion poll is posted Sundays at 18:00. The counter persists in `state.json` and counts new non-bot messages in the configured group; every 40th message gets a short, radical question directly addressing `@StAnastasiaSt`. On `@koccbarmafallbot` mention, the bot uses the last five messages as context and responds in Belarusian in a Kocc-inspired voice, without claiming to be him or inventing historical quotations. OpenAI API use requires a separate API key and may incur charges; without a key, a local keyword-based fallback is used. When the key is configured, only the last five message texts/captions (up to 500 characters each) are sent to OpenAI. `DISCARD_BACKLOG=true` skips queued messages from before startup. One in five generated quote messages omits the in-message attribution; Telegram still shows the bot account as sender.

## GitHub Actions hosting

The repository includes `.github/workflows/kocc-barma.yml`. It runs the bot for 210 seconds every five minutes, restores/saves the message counter and Telegram update offset through GitHub Actions cache, and exits before the runner's five-minute job limit. This keeps the bot running without a local computer, but replies can take several minutes and GitHub may delay scheduled runs. The workflow must be on the repository's default branch to receive scheduled events.

Add these repository secrets under **Settings → Secrets and variables → Actions**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY` (optional; without it, mention replies use the local fallback)

The workflow refers to secrets by name only. Do not paste credentials into the source, workflow, README, or commit history. Since the Telegram token was shared in chat, rotate it with BotFather before saving the replacement as a GitHub secret. To start after setting secrets, use **Actions → Kocc Barma Telegram bot → Run workflow**. Scheduled runs then start automatically every five minutes. OpenAI use can incur API charges.

GitHub-hosted runners are ephemeral, so the bot's state is kept in Actions cache rather than committed to the repository. If the cache is cleared, the counter and recent-message context restart from zero.

For local Windows operation, `set-secrets.ps1` stores the Telegram secret encrypted with the current Windows account's DPAPI; `install-startup.ps1` creates a hidden logon shortcut. Run the PowerShell scripts from this folder. To enable mention-based analysis locally, run `set-openai-key.ps1` in a local terminal and then `restart-bot.ps1`. The key is encrypted for this Windows account. The bot must be an administrator or have group privacy disabled (the bot's privacy setting is also adjustable through Telegram's `setMySettings` API) so Telegram delivers ordinary group messages; without this, the 40-message count and context window cannot work.

To change topics or eligible quotations, edit `TOPICS`, `TOPIC_QUOTES`, and `ELIGIBLE_IDS` in `bot.py`. Before launch, have a Wolof speaker validate the translations and a community/cultural reviewer approve the selected sayings.

