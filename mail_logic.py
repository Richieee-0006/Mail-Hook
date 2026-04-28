import json
import os
from datetime import datetime
import httpx

HISTORY_FILE = "history.json"
FILTERS_FILE = "filters.json"

def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)

async def process_email_webhook(data, config):
    from_addr = data.get("from", "Neznámý")
    subject = data.get("subject", "Bez předmětu")
    body = data.get("body", "")
    date = data.get("date", datetime.now().isoformat())
    role_id = data.get("roleId")
    is_test = data.get("isTest", False)

    # Chytré rozdělení CZ/EN
    sections = []
    en_markers = ["English version below", "--- English version", "English version:", "---"]
    
    split_index = -1
    for marker in en_markers:
        idx = body.find(marker)
        if idx != -1:
            split_index = idx
            break
    
    if split_index != -1:
        sections.append(body[:split_index].strip())
        sections.append(body[split_index:].strip())
    else:
        max_len = 3800
        for i in range(0, len(body), max_len):
            sections.append(body[i:i+max_len])

    embeds = []
    for i, content in enumerate(sections):
        embed = {
            "title": subject[:256] if i == 0 else f"{subject[:240]} (pokr.)",
            "description": content[:4096],
            "color": 3447003,
            "timestamp": date
        }
        if i == 0:
            embed["fields"] = [{"name": "Od", "value": from_addr[:1024], "inline": True}]
        if i == len(sections) - 1:
            embed["footer"] = {"text": "Přišlo e-mailem"}
        embeds.append(embed)

    cid = config["DISCORD_TEST_CHANNEL_ID"] if is_test else config["DISCORD_CHANNEL_ID"]
    payload = {"username": "EmailBot", "embeds": embeds[:10]}
    if role_id:
        payload["content"] = f"<@&{role_id}>"
        payload["allowed_mentions"] = {"roles": [role_id]}

    status = "ok"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://discord.com/api/v10/channels/{cid}/messages",
            headers={"Authorization": f"Bot {config['DISCORD_BOT_TOKEN']}"},
            json=payload
        )
        if not r.is_success:
            status = f"error: {r.status_code}"

    history = load_json(HISTORY_FILE, [])
    history.append({
        "sender": from_addr,
        "subject": subject,
        "status": "ok" if status == "ok" else "error",
        "timestamp": date
    })
    save_json(HISTORY_FILE, history[-100:])
    return {"ok": True}
