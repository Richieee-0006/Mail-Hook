# Mail-Hook

FastAPI gateway that receives UJEP institutional emails, filters them, and forwards them to Discord. Includes a web dashboard for message history, filter rules, and bot configuration.

## Features

- Isolates Czech and English sections and splits long emails into Discord-sized embeds.
- Web dashboard for checking delivery history, editing sender/keyword filters, and updating bot settings.
- Session authentication using `bcrypt` password hashes and `itsdangerous` signed tokens.
- Optional Cloudflare Worker proxy (`worker.js`) for request validation in front of the origin server.

## Tech Stack

- **Backend:** FastAPI, HTTPX (Python 3.10+)
- **Security:** `itsdangerous`, `bcrypt`
- **Frontend:** HTML5, CSS3
- **Edge & Mail:** Cloudflare Workers (`worker.js`), Google Apps Script

## Installation and Deployment

1. Clone the repository.
2. Copy `env.example` to `.env` and fill in your secrets and webhook URLs.
3. Install dependencies: `pip install -r requirements.txt`.
4. Start the server using Gunicorn and Uvicorn workers as configured in `deploy.sh`.
5. Deploy `worker.js` to Cloudflare Workers to route incoming webhooks.

## Files

- `app.py`: FastAPI entrypoint and admin UI routes.
- `mail_logic.py`: Email parsing, filtering, and Discord webhook delivery.
- `auth_logic.py`: Password verification and session handling.
- `worker.js`: Cloudflare Worker proxy script.

## License

MIT License.
