# Mail-Hook Gateway

FastAPI gateway that filters and forwards UJEP institutional emails to Discord.

## Key Features
- **Content Processing:** Isolates CZ/EN sections and splits long emails into Discord embeds.
- **Admin Dashboard:** Web UI for viewing message history, managing filter rules, and configuring the bot.
- **Edge Proxy:** Runs behind a Cloudflare Worker for request validation and network isolation.
- **Sender & Keyword Filtering:** Drops unauthorized senders and rejected keywords before forwarding.

## Tech Stack
- **Backend:** FastAPI, Python 3.10+, HTTPX
- **Infrastructure:** Cloudflare Workers, Google Apps Script
- **Security:** `bcrypt`, `itsdangerous`
- **Frontend:** HTML5, CSS3
