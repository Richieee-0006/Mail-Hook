#!/usr/bin/env bash
# deploy.sh – jednorázový setup na Ubuntu serveru
# Spusť jako root nebo sudo

set -euo pipefail

APP_DIR="/opt/discord-panel"
LOG_DIR="/var/log/discord-panel"

echo "==> Vytváření adresářů..."
mkdir -p "$APP_DIR" "$LOG_DIR"
chown www-data:www-data "$LOG_DIR"

echo "==> Kopírování souborů..."
cp app.py requirements.txt "$APP_DIR/"

echo "==> Vytváření virtualenv a instalace závislostí..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo ""
echo "==> Vytvoř .env soubor:"
echo "    cp .env.example $APP_DIR/.env"
echo "    nano $APP_DIR/.env"
echo ""
echo "    Vygeneruj APP_SECRET:"
echo "    python3 -c \"import secrets; print(secrets.token_hex(32))\""
echo ""
echo "    Vygeneruj HASHED_PASSWORD:"
echo "    python3 -c \"import bcrypt; print(bcrypt.hashpw(b'tvojeHeslo', bcrypt.gensalt()).decode())\""
echo ""
echo "==> Zkopíruj systemd service:"
echo "    cp discord-panel.service /etc/systemd/system/"
echo "    systemctl daemon-reload"
echo "    systemctl enable --now discord-panel"
echo ""
echo "==> Zkopíruj nginx config:"
echo "    cp nginx-discord-panel.conf /etc/nginx/sites-available/discord-panel"
echo "    ln -s /etc/nginx/sites-available/discord-panel /etc/nginx/sites-enabled/"
echo ""
echo "==> SSL certifikát (Let's Encrypt):"
echo "    certbot --nginx -d panel.rutterle.eu"
echo ""
echo "==> Nastav Cloudflare Worker env proměnné (dashboard nebo wrangler):"
echo "    INTERNAL_TOKEN  – stejná hodnota jako v .env"
echo "    WEBHOOK_SECRET  – nový secret pro mailbot"
echo ""
echo "==> Hotovo! Panel bude na https://panel.rutterle.eu"
