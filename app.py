import os
import httpx
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

from mail_logic import process_email_webhook, load_json, save_json, HISTORY_FILE, FILTERS_FILE
from auth_logic import require_auth, verify_session, check_password, create_session_token, SESSION_COOKIE, SESSION_MAX_AGE

app = FastAPI(title="Mail-Hook Admin Panel", docs_url=None, redoc_url=None)

# Configuration
DISCORD_CONFIG = {
    "DISCORD_BOT_TOKEN": os.environ.get("DISCORD_BOT_TOKEN"),
    "DISCORD_CHANNEL_ID": os.environ.get("DISCORD_CHANNEL_ID"),
    "DISCORD_TEST_CHANNEL_ID": os.environ.get("DISCORD_TEST_CHANNEL_ID")
}
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")

PANEL_HTML = """<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mail-Hook Admin</title>
  <style>
    :root {
      --bg:#0f1114; --surface:#1a1d21; --surface2:#2c2f33; --border:#3a3f44;
      --accent:#5865F2; --danger:#ed4245; --success:#57f287; --muted:#72767d;
      --text:#dcddde; --text-bright:#ffffff; --radius:12px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family:'Inter','Segoe UI',sans-serif; background:var(--bg); color:var(--text); padding:1rem; display:flex; justify-content:center; }
    
    #login-section, #admin-panel { display:none; width:100%; max-width:700px; margin-top:5vh; animation: fadeIn 0.4s ease; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

    #login-section { text-align:center; background:var(--surface); padding:3rem 2rem; border-radius:var(--radius); border:1px solid var(--border); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    
    .card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:1.5rem; margin-bottom:1rem; }
    h1, h2, h3 { color:var(--text-bright); margin-bottom:1rem; letter-spacing: -0.02em; }
    
    .tabs { display:flex; gap:.75rem; margin-bottom:1.5rem; background:var(--surface); padding: 5px; border-radius: var(--radius); border: 1px solid var(--border); }
    .tab-btn { flex:1; padding:.75rem; background:transparent; color:var(--muted); border:none; border-radius:calc(var(--radius) - 6px); cursor:pointer; font-weight:600; transition: all 0.2s; }
    .tab-btn.active { background:var(--surface2); color:white; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
    
    .tab-content { display:none; flex-direction:column; gap:1.2rem; }
    .tab-content.active { display:flex; }
    
    input, select, textarea { width:100%; padding:.8rem 1rem; background:var(--bg); border:1px solid var(--border); border-radius:8px; color:white; margin-bottom:1rem; outline:none; transition: border-color 0.2s; }
    input:focus { border-color: var(--accent); }

    .btn { padding:.8rem 1.5rem; border:none; border-radius:8px; font-weight:700; cursor:pointer; transition: transform 0.1s, filter 0.2s; display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; }
    .btn:active { transform: scale(0.98); }
    .btn-primary { background:var(--accent); color:white; width:100%; }
    .btn-secondary { background:var(--surface2); color:white; border:1px solid var(--border); }
    .btn-danger { background: rgba(237, 66, 69, 0.1); color: var(--danger); border: 1px solid var(--danger); }
    .btn-danger:hover { background: var(--danger); color: white; }
    
    .status-bar { padding:.8rem; border-radius:8px; font-size:.9rem; display:none; margin-top:1rem; font-weight: 500; }
    .status-bar.show { display:block; }
    .status-bar.success { background:rgba(87, 242, 135, 0.1); color:var(--success); border: 1px solid var(--success); }
    .status-bar.error { background:rgba(237, 66, 69, 0.1); color:var(--danger); border: 1px solid var(--danger); }
    
    .history-item { background:var(--bg); padding:1rem; border-radius:8px; border:1px solid var(--border); margin-bottom:.75rem; display: flex; justify-content: space-between; align-items: center; }
    .history-info b { color: var(--text-bright); display: block; margin-bottom: 2px; }
    .history-info small { color: var(--muted); }
    .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 800; text-transform: uppercase; }
    .badge-ok { background: rgba(87, 242, 135, 0.1); color: var(--success); }
    .badge-error { background: rgba(237, 66, 69, 0.1); color: var(--danger); }

    .filter-tag { display:inline-flex; align-items: center; background:var(--surface2); padding:.4rem .7rem; border-radius:6px; margin:0 .5rem .5rem 0; font-size:.85rem; border: 1px solid var(--border); }
    .filter-tag button { background:none; border:none; color:var(--muted); margin-left:.6rem; cursor:pointer; font-size: 1.1rem; line-height: 1; }
    .filter-tag button:hover { color: var(--danger); }
  </style>
</head>
<body>
<div id="login-section">
  <div style="font-size: 3rem; margin-bottom: 1rem;">📬</div>
  <h1>Mail-Hook Gateway</h1>
  <p style="color: var(--muted); margin-bottom: 2rem;">Zabezpečený přístup k administraci botů</p>
  <input type="password" id="password" placeholder="Zadejte přístupové heslo" onkeydown="if(event.key==='Enter')handleLogin()">
  <button class="btn btn-primary" onclick="handleLogin()">Přihlásit se</button>
  <div id="login-status" class="status-bar"></div>
</div>

<div id="admin-panel">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2rem;">
    <div>
      <h2 style="margin-bottom: 0;">Dashboard</h2>
      <p style="color: var(--muted); font-size: 0.9rem;">Správa e-mailového forwardingu</p>
    </div>
    <button class="btn btn-secondary" onclick="logout()" style="padding:.5rem 1rem">Odhlásit</button>
  </div>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('history',this)">📜 Historie</button>
    <button class="tab-btn" onclick="switchTab('filters',this)">🛡️ Filtry</button>
    <button class="tab-btn" onclick="switchTab('avatar',this)">🖼️ Avatar</button>
    <button class="tab-btn" onclick="switchTab('messages',this)">💬 Zprávy</button>
  </div>

  <!-- Historie -->
  <div id="tab-history" class="tab-content active">
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <h3>Poslední aktivita</h3>
        <button class="btn btn-secondary" onclick="loadHistory()" style="padding: 4px 8px; font-size: 0.8rem;">Obnovit</button>
      </div>
      <div id="history-list"></div>
    </div>
  </div>
  
  <!-- Filtry -->
  <div id="tab-filters" class="tab-content">
    <div class="card">
      <h3>Blokovaní odesílatelé</h3>
      <p style="font-size:.85rem;color:var(--muted);margin-bottom:1rem">E-maily z těchto adres budou ignorovány.</p>
      <div style="display:flex;gap:.5rem"><input id="sender-input" placeholder="např. spam@seznam.cz" style="margin-bottom:0"><button class="btn btn-secondary" onclick="addFilter('senders')">Přidat</button></div>
      <div id="senders-list" style="margin-top:1rem"></div>
    </div>
    <div class="card">
      <h3>Zakázaná slova</h3>
      <p style="font-size:.85rem;color:var(--muted);margin-bottom:1rem">Maily obsahující tato klíčová slova v předmětu nebudou doručeny.</p>
      <div style="display:flex;gap:.5rem"><input id="keyword-input" placeholder="např. nabídka, sleva" style="margin-bottom:0"><button class="btn btn-secondary" onclick="addFilter('keywords')">Přidat</button></div>
      <div id="keywords-list" style="margin-top:1rem"></div>
    </div>
    <button class="btn btn-primary" onclick="saveSettings()">Uložit konfiguraci filtrů</button>
    <div id="filters-status" class="status-bar"></div>
  </div>

  <!-- Avatar -->
  <div id="tab-avatar" class="tab-content">
    <div class="card" style="text-align:center">
      <h3>Profilový obrázek bota</h3>
      <div style="margin: 2rem 0;">
        <img id="current-pfp-img" src="" style="width:120px;height:120px;border-radius:50%;border: 3px solid var(--border); padding: 5px; background: var(--bg);">
      </div>
      <div style="display:flex;gap:.5rem;justify-content:center">
        <button class="btn btn-secondary" onclick="fetchCurrentPfp()">Aktualizovat náhled</button>
      </div>
      <div id="avatar-status" class="status-bar"></div>
    </div>
  </div>

  <!-- Zprávy -->
  <div id="tab-messages" class="tab-content">
    <div class="card">
      <h3>Manuální odeslání zprávy</h3>
      <label style="font-size: 0.85rem; color: var(--muted); display: block; margin-bottom: 0.5rem;">Cílový kanál</label>
      <select id="send-dest">
        <option value="live">Produkční server (#emaily)</option>
        <option value="test">Testovací server (dev)</option>
      </select>
      <label style="font-size: 0.85rem; color: var(--muted); display: block; margin-bottom: 0.5rem;">Obsah zprávy</label>
      <textarea id="send-content" rows="5" placeholder="Napište text zprávy..."></textarea>
      <button class="btn btn-primary" onclick="sendMessage()">Odeslat do Discordu</button>
      <div id="send-status" class="status-bar"></div>
    </div>
  </div>
</div>

<script>
  let settings = { senders: [], keywords: [] };
  function showStatus(id, msg, type) { 
    const el=document.getElementById(id); 
    el.textContent=msg; 
    el.className='status-bar show '+type; 
    setTimeout(()=>el.classList.remove('show'),3000); 
  }

  async function handleLogin() {
    const r = await fetch('/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:document.getElementById('password').value})});
    if(r.ok) { 
      document.getElementById('login-section').style.display='none'; 
      document.getElementById('admin-panel').style.display='block'; 
      loadHistory(); 
    } else showStatus('login-status', 'Neplatné heslo', 'error');
  }
  async function logout() { await fetch('/auth/logout', {method:'POST'}); location.reload(); }

  function switchTab(name, btn) {
    document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    document.getElementById('tab-'+name).classList.add('active'); 
    btn.classList.add('active');
    if(name==='history') loadHistory(); 
    if(name==='filters') loadSettings(); 
    if(name==='avatar') fetchCurrentPfp();
  }

  async function loadSettings() { const r=await fetch('/api/settings'); if(r.ok){ settings=await r.json(); renderFilters(); } }
  function renderFilters() {
    document.getElementById('senders-list').innerHTML = settings.senders.map(s=>`<span class="filter-tag">${s}<button onclick="removeFilter('senders','${s}')">×</button></span>`).join('');
    document.getElementById('keywords-list').innerHTML = settings.keywords.map(k=>`<span class="filter-tag">${k}<button onclick="removeFilter('keywords','${k}')">×</button></span>`).join('');
  }
  function addFilter(t){ const i=document.getElementById(t==='senders'?'sender-input':'keyword-input'); const v=i.value.trim().toLowerCase(); if(v && !settings[t].includes(v)){ settings[t].push(v); i.value=''; renderFilters(); } }
  function removeFilter(t,v){ settings[t]=settings[t].filter(x=>x!==v); renderFilters(); }
  async function saveSettings(){ const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)}); if(r.ok) showStatus('filters-status','Konfigurace uložena','success'); }

  async function loadHistory() {
    const r=await fetch('/api/history'); 
    if(r.ok){ 
      const d=await r.json(); 
      document.getElementById('history-list').innerHTML = d.map(i=>`
        <div class="history-item">
          <div class="history-info">
            <b>${i.sender}</b>
            <small>${i.subject}</small>
          </div>
          <span class="badge ${i.status==='ok'?'badge-ok':'badge-error'}">${i.status==='ok'?'Doručeno':'Blokováno'}</span>
        </div>`).join(''); 
    }
  }

  async function fetchCurrentPfp() { 
    const r=await fetch('/api/get-current-pfp'); 
    if(r.ok){ 
      const d=await r.json(); 
      if(d.url) document.getElementById('current-pfp-img').src=d.url; 
    } 
  }
  
  async function sendMessage() {
    const dest=document.getElementById('send-dest').value; 
    const content=document.getElementById('send-content').value; 
    if(!content) return;
    showStatus('send-status','Odesílám...','info');
    const r=await fetch('/api/send-message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({destination:dest, content})});
    if(r.ok){ 
      showStatus('send-status','Zpráva byla odeslána','success'); 
      document.getElementById('send-content').value=''; 
    } else showStatus('send-status','Chyba při odesílání','error');
  }

  (async () => { 
    const r=await fetch('/auth/check'); 
    if(r.ok){ document.getElementById('admin-panel').style.display='block'; loadHistory(); } 
    else document.getElementById('login-section').style.display='block'; 
  })();
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def root(): return PANEL_HTML

@app.get("/auth/check")
async def check_auth(request: Request):
    if not verify_session(request): raise HTTPException(status_code=401)
    return {"ok": True}

@app.post("/auth/login")
async def login(request: Request, response: Response):
    body = await request.json()
    if check_password(body.get("password", "")):
        token = create_session_token()
        response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=True, samesite="lax", max_age=SESSION_MAX_AGE)
        return {"ok": True}
    raise HTTPException(status_code=401)

@app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}

@app.get("/api/settings")
async def get_settings(_: None = Depends(require_auth)): return load_json(FILTERS_FILE, {"senders":[], "keywords":[]})

@app.post("/api/settings")
async def post_settings(request: Request, _: None = Depends(require_auth)):
    save_json(FILTERS_FILE, await request.json())
    return {"ok": True}

@app.get("/api/history")
async def get_history(_: None = Depends(require_auth)): return load_json(HISTORY_FILE, [])[::-1]

@app.get("/api/get-current-pfp")
async def get_current_pfp(_: None = Depends(require_auth)):
    async with httpx.AsyncClient() as client:
        r = await client.get("https://discord.com/api/v10/users/@me", headers={"Authorization": f"Bot {DISCORD_CONFIG['DISCORD_BOT_TOKEN']}"})
        if r.is_success:
            d = r.json()
            return {"url": f"https://cdn.discordapp.com/avatars/{d['id']}/{d['avatar']}.png?size=256"}
    return {"url": ""}

@app.post("/api/send-message")
async def send_message(request: Request, _: None = Depends(require_auth)):
    data = await request.json()
    cid = DISCORD_CONFIG["DISCORD_TEST_CHANNEL_ID"] if data.get("destination") == "test" else DISCORD_CONFIG["DISCORD_CHANNEL_ID"]
    async with httpx.AsyncClient() as client:
        r = await client.post(f"https://discord.com/api/v10/channels/{cid}/messages", headers={"Authorization": f"Bot {DISCORD_CONFIG['DISCORD_BOT_TOKEN']}"}, json={"content": data.get("content")})
        return JSONResponse(content=r.json(), status_code=r.status_code)

@app.post("/api/webhook")
async def email_webhook(request: Request):
    if request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=401)
    return await process_email_webhook(await request.json(), DISCORD_CONFIG)
