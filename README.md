# Mail-Hook

Mail-Hook is a high-performance, modular FastAPI gateway designed to intercept, process, and forward university or institutional emails to Discord. It provides a centralized administration interface for managing message processing, content filtering, and system configuration.

## Key Functionality

*   **Intelligent Payload Processing:** Automated detection and isolation of multilingual content (CZ/EN) or segmentation of long-form messages into Discord-compliant embeds.
*   **Administrative Interface:** A secure, responsive web dashboard for monitoring message history, managing filter rules, and configuring bot identity.
*   **Security Architecture:** Implementation of session-based authentication utilizing bcrypt password hashing and URLSafeTimedSerialization for secure token management.
*   **Edge Proxy Integration:** Designed to operate behind a Cloudflare Worker proxy for enhanced network isolation and request validation.
*   **Advanced Filtering Engine:** Real-time exclusion of unauthorized senders and keyword-based message rejection.

## Technical Specifications

*   **Backend Framework:** FastAPI (Asynchronous Python)
*   **Communication:** HTTPX (Async HTTP Client)
*   **Security:** itsdangerous (Session signing), bcrypt (Password hashing)
*   **Frontend:** Standard-compliant HTML5/CSS3 (Modernized dark interface)
*   **Infrastructure:** Cloudflare Workers (JavaScript Proxy), Google Apps Script (Email Monitoring)

## Deployment and Installation

1.  **Repository Initialization:** Clone the project to your local or production environment.
2.  **Environment Configuration:** Copy `env.example` to `.env` and populate with necessary API keys and secrets.
3.  **Dependency Management:** Install required Python packages: `pip install -r requirements.txt`.
4.  **Process Management:** Deploy using Gunicorn with Uvicorn workers as specified in `deploy.sh`.
5.  **Edge Setup:** Publish the Cloudflare Worker script located in `worker.js` to handle incoming webhooks.

## System Architecture

*   `app.py`: Primary application entry point and administrative UI.
*   `mail_logic.py`: Core processing engine for email parsing and Discord integration.
*   `auth_logic.py`: Authentication middleware and session management.
*   `worker.js`: Cloudflare-specific proxy logic for secure request tunneling.

## License

This project is licensed under the MIT License.
