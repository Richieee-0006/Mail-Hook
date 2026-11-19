import re
import os
import json
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import httpx

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
HISTORY_FILE = str(BASE_DIR / "history.json")
FILTERS_FILE = str(BASE_DIR / "filters.json")
PERSONAL_FILTER_TERMS = [
    term.strip().lower()
    for term in os.environ.get("PERSONAL_FILTER_TERMS", "").split(",")
    if term.strip()
]


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean_body(text: str) -> str:
    """Čištění textu zprávy (normalizace prázdných řádků, mezer a tabulátorů)."""
    text = text.replace("\r", "")
    text = re.sub(r"\t+", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    cleaned_lines = [l for l in lines if l]
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


async def process_email_webhook(data: Dict[str, Any], config: Dict[str, Any]):
    from_addr = data.get("from", "Neznámý")
    subject = data.get("subject", "Bez předmětu")
    raw_body = data.get("body", "")
    date = data.get("date", datetime.now().isoformat())
    role_id = data.get("roleId")
    is_test = data.get("isTest", False)

    body_lower = raw_body.lower()
    subject_lower = subject.lower()
    from_lower = from_addr.lower()

    # 1. FILTR: Osobní e-maily (volitelné přes PERSONAL_FILTER_TERMS v .env)
    if PERSONAL_FILTER_TERMS and any(
        term in body_lower or term in from_lower for term in PERSONAL_FILTER_TERMS
    ):
        print(f"Osobní e-mail přeskočen: {subject}")
        return {"ok": True, "skipped": "personal_email"}

    # Načtení filtrů a pravidel obfuskace
    filters = load_json(FILTERS_FILE, {"senders": [], "keywords": [], "obfuscations": []})

    # 2. BLOKACE: Podle blokovaného odesílatele
    for blocked_sender in filters.get("senders", []):
        bs = blocked_sender.strip().lower()
        if bs and bs in from_lower:
            print(f"E-mail zablokován podle odesílatele ({bs}): {from_addr}")
            history = load_json(HISTORY_FILE, [])
            history.append({
                "sender": from_addr,
                "subject": subject,
                "status": f"blocked: {bs}",
                "timestamp": date,
            })
            save_json(HISTORY_FILE, history[-100:])
            return {"ok": True, "skipped": "blocked_sender", "rule": bs}

    # 3. BLOKACE: Podle zakázaných klíčových slov
    for kw in filters.get("keywords", []):
        kw_clean = kw.strip().lower()
        if kw_clean and (kw_clean in subject_lower or kw_clean in body_lower):
            print(f"E-mail zablokován podle klíčového slova ({kw_clean}): {subject}")
            history = load_json(HISTORY_FILE, [])
            history.append({
                "sender": from_addr,
                "subject": subject,
                "status": f"blocked: {kw_clean}",
                "timestamp": date,
            })
            save_json(HISTORY_FILE, history[-100:])
            return {"ok": True, "skipped": "blocked_keyword", "rule": kw_clean}

    body = raw_body

    # 4. ÚPRAVA: Zapsáno hodnocení předmětu
    if "zapsáno hodnocení předmětu" in body_lower:
        lines = body.split("\n")
        for line_idx, line in enumerate(lines):
            if "zapsáno hodnocení předmětu" in line.lower():
                for k in range(line_idx, -1, -1):
                    if any(kw_item in lines[k] for kw_item in ("Zápočet/zkouška", "Udělil", "Datum")):
                        continue
                    lines[k] = ""
        body = "\n".join(lines)

    # 5. ODSTRANĚNÍ PATIČEK IS/STAG (robustní regex)
    body = re.sub(r"Tento e-mail.*IS/STAG.*", "", body, flags=re.IGNORECASE)

    # 6. OBFUSKACE (CENZURA TEXTU): dynamická pravidla z filters.json
    obfuscations = filters.get("obfuscations", [])

    for obf in obfuscations:
        pat = obf.get("pattern", "").strip()
        rep = obf["replacement"] if "replacement" in obf else "***"
        if not pat:
            continue

        is_regex = bool(obf.get("is_regex", False))
        if pat.startswith("regex:"):
            is_regex = True
            pat = pat[6:].strip()
        elif pat.startswith("r:"):
            is_regex = True
            pat = pat[2:].strip()

        try:
            if is_regex:
                body = re.sub(pat, rep, body, flags=re.IGNORECASE)
                subject = re.sub(pat, rep, subject, flags=re.IGNORECASE)
            else:
                body = re.sub(re.escape(pat), rep, body, flags=re.IGNORECASE)
                subject = re.sub(re.escape(pat), rep, subject, flags=re.IGNORECASE)
        except Exception as e:
            logger.warning(f"Chyba pri aplikaci obfuskace '{pat}': {e}")

    # 7. ČIŠTĚNÍ TEXTU A MEZER
    body = clean_body(body)

    # 8. OŘÍZNUTÍ DÉLKY TEXTU
    if len(body) > 3900:
        body = body[:3900] + "\n\n`... (Zpráva byla zkrácena) ...`"

    # 9. PŘÍLOHY (Max 20 MB celkem)
    MAX_TOTAL_BYTES = 20 * 1024 * 1024
    total_attachment_bytes = 0
    files = []
    skipped_attachments = []

    attachments_data = data.get("attachments", [])
    for idx, att in enumerate(attachments_data):
        try:
            raw_b64 = att.get("data", "")
            file_bytes = base64.b64decode(raw_b64)
            att_size = len(file_bytes)
            filename = att.get("name", f"attachment_{idx}")
            content_type = att.get("contentType", "application/octet-stream")

            if total_attachment_bytes + att_size <= MAX_TOTAL_BYTES:
                total_attachment_bytes += att_size
                files.append((f"files[{idx}]", (filename, file_bytes, content_type)))
            else:
                skipped_attachments.append(filename)
        except Exception as e:
            print(f"Chyba při dekódování přílohy {idx}: {e}")

    # 10. CHYTRÉ ROZDĚLENÍ CZ / EN EMBEDS
    sections = []
    en_markers = ["---- ENGLISH ----"]

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
        for i in range(0, max(1, len(body)), max_len):
            sections.append(body[i : i + max_len])

    embeds = []
    for i, content in enumerate(sections):
        embed = {
            "title": subject[:256] if i == 0 else f"{subject[:240]} (pokr.)",
            "description": content[:4096],
            "color": 3447003,
            "timestamp": date,
        }
        if i == 0:
            embed["fields"] = [
                {"name": "Od", "value": from_addr[:1024], "inline": True}
            ]
        if i == len(sections) - 1:
            if skipped_attachments:
                embed["footer"] = {"text": f"Přeskočeno (velikost): {', '.join(skipped_attachments)}"}
            else:
                embed["footer"] = {"text": "Přišlo e-mailem"}
        embeds.append(embed)

    cid = config["DISCORD_TEST_CHANNEL_ID"] if is_test else config["DISCORD_CHANNEL_ID"]
    payload = {"username": "EmailBot", "embeds": embeds[:10]}
    if role_id:
        payload["content"] = f"<@&{role_id}> od: {from_addr}"
        payload["allowed_mentions"] = {"roles": [role_id]}

    status = "ok"
    async with httpx.AsyncClient(timeout=20.0) as client:
        if files:
            r = await client.post(
                f"https://discord.com/api/v10/channels/{cid}/messages",
                headers={"Authorization": f"Bot {config['DISCORD_BOT_TOKEN']}"},
                data={"payload_json": json.dumps(payload)},
                files=files,
            )
        else:
            r = await client.post(
                f"https://discord.com/api/v10/channels/{cid}/messages",
                headers={"Authorization": f"Bot {config['DISCORD_BOT_TOKEN']}"},
                json=payload,
            )
        if not r.is_success:
            status = f"error: {r.status_code}"

    history = load_json(HISTORY_FILE, [])
    history.append(
        {
            "sender": from_addr,
            "subject": subject,
            "status": "ok" if status == "ok" else "error",
            "timestamp": date,
        }
    )
    save_json(HISTORY_FILE, history[-100:])
    return {"ok": True, "status": status}
