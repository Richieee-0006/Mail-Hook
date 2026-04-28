# 📬 Mail-Hook

A professional, secure, and modular FastAPI gateway for forwarding university (or any) emails to Discord with a centralized management panel.

## ✨ Features
- **Smart Splitting:** Automatically detects CZ/EN versions or splits long emails into multiple Discord embeds.
- **Admin Panel:** Modern UI to manage message history, filter settings, and bot profile.
- **Security:** Session-based authentication using `bcrypt` and `URLSafeTimedSerializer`.
- **Cloudflare Worker Proxy:** Includes a proxy script for network isolation and secure forwarding.
- **Filtering:** Block senders or specific keywords directly from the UI.

## 🛠 Tech Stack
- **Backend:** Python (FastAPI, HTTPX, SlowAPI)
- **Frontend:** Vanilla HTML5/CSS3 (Modern Dark UI)
- **Proxy:** Cloudflare Workers (JavaScript)
- **Automation:** Google Apps Script

## 🚀 Setup
1. Clone the repository.
2. Copy `env.example` to `.env` and fill in your credentials.
3. Install dependencies: `pip install -r requirements.txt`.
4. Deploy using `gunicorn` (see `deploy.sh`).
5. Deploy the Cloudflare Worker located in `worker.js`.

## 📦 Project Structure
- `app.py`: Main FastAPI application & UI.
- `mail_logic.py`: Email processing & Discord logic.
- `auth_logic.py`: Security & Authentication.
- `worker.js`: Cloudflare Worker proxy code.

## 📄 License
MIT
