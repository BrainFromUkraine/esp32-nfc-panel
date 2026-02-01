# ui_html.py
# UI builder for ESP32 NFC web panel
# - colored badge for GRANTED/DENIED
# - toast notifications (top)
# - History (client-side for now; device-side later)

def html_escape(s):
    s = str(s if s is not None else "")
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;").replace("'", "&#39;")
    return s


def build_login_html():
    """Build a custom login page"""
    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Login - ESP32 NFC</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin:0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height:100vh;
      display:flex;
      align-items:center;
      justify-content:center;
      padding:20px;
    }
    .login-card {
      background: rgba(255,255,255,0.95);
      border-radius: 24px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
      padding: 40px 32px;
      max-width: 400px;
      width: 100%;
      backdrop-filter: blur(10px);
    }
    .logo-area {
      text-align:center;
      margin-bottom:32px;
    }
    .logo {
      width:80px;
      height:80px;
      margin:0 auto 16px;
      border-radius:20px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      box-shadow: 0 8px 24px rgba(102,126,234,0.4);
    }
    h1 {
      margin:0 0 8px;
      font-size:24px;
      color:#1a202c;
    }
    .subtitle {
      color:#718096;
      font-size:14px;
    }
    .form-group {
      margin-bottom:20px;
    }
    label {
      display:block;
      margin-bottom:8px;
      color:#4a5568;
      font-size:14px;
      font-weight:600;
    }
    input {
      width:100%;
      padding:14px 16px;
      border-radius:12px;
      border:2px solid #e2e8f0;
      background:#fff;
      font-size:15px;
      transition: all 0.2s;
      outline:none;
    }
    input:focus {
      border-color:#667eea;
      box-shadow: 0 0 0 3px rgba(102,126,234,0.1);
    }
    button {
      width:100%;
      padding:14px 16px;
      border-radius:12px;
      border:none;
      background: linear-gradient(135deg, #667eea, #764ba2);
      color:#fff;
      font-size:16px;
      font-weight:700;
      cursor:pointer;
      transition: transform 0.2s, box-shadow 0.2s;
      margin-top:8px;
    }
    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(102,126,234,0.4);
    }
    button:active {
      transform: translateY(0);
    }
    .error {
      background:#fee;
      border:1px solid #fcc;
      color:#c33;
      padding:12px;
      border-radius:8px;
      margin-bottom:16px;
      font-size:14px;
      display:none;
    }
    .error.show {
      display:block;
    }
  </style>
</head>
<body>
  <div class="login-card">
    <div class="logo-area">
      <div class="logo"></div>
      <h1>ESP32 NFC Panel</h1>
      <div class="subtitle">Please sign in to continue</div>
    </div>
    
    <div id="error" class="error"></div>
    
    <form id="loginForm" onsubmit="return handleLogin(event)">
      <div class="form-group">
        <label for="username">Username</label>
        <input type="text" id="username" name="username" required autocomplete="username" autofocus/>
      </div>
      
      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" required autocomplete="current-password"/>
      </div>
      
      <button type="submit">Sign In</button>
    </form>
  </div>

  <script>
    function showError(msg){
      const el = document.getElementById('error');
      el.textContent = msg;
      el.classList.add('show');
    }
    
    function handleLogin(e){
      e.preventDefault();
      const username = document.getElementById('username').value;
      const password = document.getElementById('password').value;
      
      fetch('/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: username, password: password})
      })
      .then(r => {
        if(r.redirected || r.status === 302){
          window.location.href = '/';
          return null;
        }
        return r.json();
      })
      .then(data => {
        if(data && !data.ok){
          showError(data.msg || 'Invalid credentials');
        } else if(!data){
          // Redirect happened
          window.location.href = '/';
        }
      })
      .catch(err => {
        showError('Login failed. Please try again.');
      });
      
      return false;
    }
  </script>
</body>
</html>
"""
    return html


def build_index_html(last_fw, last_uid, last_access, last_name, cards):
    # cards: [{"uid":"15 D6 ...", "name":"..."}, ...]
    # --- UPDATED: render actions (edit/delete) but keep original UI intact ---
    uids_li = "".join([
        "<li class='uid-item'>"
        "  <span class='uid-text'>{}</span>"
        "  <span class='uid-actions'>"
        "    <button class='iconBtn' title='Edit' onclick='pickUid({}, {})'>✎</button>"
        "    <button class='iconBtn danger' title='Delete' onclick='delUid({})'>✖</button>"
        "  </span>"
        "</li>".format(
            html_escape(c["uid"] + (" — " + c["name"] if c.get("name") else "")),
            ujson_safe(html_escape(c.get("uid", ""))),
            ujson_safe(html_escape(c.get("name", ""))),
            ujson_safe(html_escape(c.get("uid", ""))),
        )
        for c in (cards or [])
    ])

    # status class
    acc = (last_access or "").upper()
    acc_class = "pill-neutral"
    if acc == "GRANTED":
        acc_class = "pill-good"
    elif acc == "DENIED":
        acc_class = "pill-bad"

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>ESP32 NFC</title>
  <style>
    :root {
      --bg: #ffffff;
      --bg2: #f5f7fb;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: rgba(15, 23, 42, 0.12);
      --shadow: 0 10px 30px rgba(2, 6, 23, 0.06);
      --btn: #ffffff;
      --btnText: #0f172a;
      --btnBorder: rgba(15, 23, 42, 0.18);

      --accent: #2563eb;
      --good: #16a34a;
      --bad: #dc2626;
      --warn: #f59e0b;

      --codeBg: rgba(2, 6, 23, 0.06);
      --focus: rgba(37, 99, 235, 0.25);
    }

    [data-theme="dark"] {
      --bg: #0b1220;
      --bg2: #0a152b;
      --card: rgba(255,255,255,0.06);
      --text: #e5e7eb;
      --muted: #a1a1aa;
      --border: rgba(255,255,255,0.12);
      --shadow: 0 16px 45px rgba(0,0,0,0.35);

      --btn: rgba(255,255,255,0.06);
      --btnText: #e5e7eb;
      --btnBorder: rgba(255,255,255,0.16);

      --codeBg: rgba(255,255,255,0.08);
      --focus: rgba(37, 99, 235, 0.35);
    }

    [data-theme="blue"] {
      --bg: #061425;
      --bg2: #071a2f;
      --card: rgba(255,255,255,0.06);
      --text: #e6eefc;
      --muted: #a7b4cc;
      --border: rgba(255,255,255,0.14);
      --shadow: 0 16px 45px rgba(0,0,0,0.38);

      --accent: #38bdf8;
      --btn: rgba(255,255,255,0.06);
      --btnText: #e6eefc;
      --btnBorder: rgba(255,255,255,0.18);

      --codeBg: rgba(255,255,255,0.08);
      --focus: rgba(56, 189, 248, 0.28);
    }

    * { box-sizing: border-box; }
    body {
      margin:0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: var(--text);
      background: linear-gradient(180deg, var(--bg), var(--bg2));
      min-height:100vh;
    }
    .wrap { max-width: 1020px; margin: 0 auto; padding: 18px 14px 28px; }
    .topbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom: 14px; }
    .brand { display:flex; align-items:center; gap:10px; }
    .logo { width:42px; height:42px; border-radius:14px;
      background: linear-gradient(135deg, var(--accent), rgba(34,197,94,0.8));
      box-shadow: var(--shadow);
    }
    h1 { font-size:18px; margin:0; }
    .subtitle { font-size:12px; color:var(--muted); margin-top:2px; }

    .grid { display:grid; grid-template-columns:1fr; gap:12px; }
    @media (min-width: 900px) { .grid { grid-template-columns:1.15fr 1fr; align-items:start; } }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 14px;
      margin-top: 12px;
      backdrop-filter: blur(10px);
    }

    .kv { display:grid; grid-template-columns:120px 1fr; gap:8px 10px; align-items:center; margin-top:6px; }
    .k { color: var(--muted); font-size: 12px; }
    .v { display:flex; gap:8px; align-items:center; flex-wrap:wrap; font-size:14px; }

    code {
      background: var(--codeBg);
      padding: 4px 8px;
      border-radius: 10px;
      border: 1px solid var(--border);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Courier New", monospace;
      font-size: 12px;
    }

    .pill {
      display:inline-flex; align-items:center; gap:6px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.2px;
      user-select:none;
    }
    .dot { width:8px; height:8px; border-radius: 999px; background: var(--muted); }
    .pill-good { border-color: rgba(22,163,74,0.35); }
    .pill-good .dot { background: var(--good); }
    .pill-bad { border-color: rgba(220,38,38,0.35); }
    .pill-bad .dot { background: var(--bad); }
    .pill-neutral { border-color: rgba(100,116,139,0.28); }
    .pill-neutral .dot { background: var(--muted); }

    .actions { display:grid; grid-template-columns:1fr; gap:10px; margin-top:12px; }
    .rowBtns { display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-start; }

    input {
      width:100%;
      padding: 12px 12px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.65);
      color: var(--text);
      outline: none;
    }
    [data-theme="dark"] input, [data-theme="blue"] input { background: rgba(255,255,255,0.06); }

    button {
      padding: 11px 12px;
      border-radius: 14px;
      border: 1px solid var(--btnBorder);
      background: var(--btn);
      color: var(--btnText);
      cursor: pointer;
      user-select: none;
    }
    button.primary { border-color: rgba(37,99,235,0.35); }
    button.danger  { border-color: rgba(220,38,38,0.35); }

    .uids { margin:12px 0 0; padding:0; list-style:none; display:grid; gap:8px; }
    .uid-item {
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.55);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Courier New", monospace;
      font-size: 13px;

      /* --- UPDATED: keep look, add layout for icons --- */
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:10px;
    }
    [data-theme="dark"] .uid-item, [data-theme="blue"] .uid-item { background: rgba(255,255,255,0.05); }

    .uid-text{ overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }
    .uid-actions{ display:flex; gap:6px; flex: 0 0 auto; }

    /* small icon buttons - do NOT touch global button styles */
    .iconBtn{
      width:34px;
      height:30px;
      padding:0;
      border-radius: 10px;
      border: 1px solid var(--btnBorder);
      background: rgba(255,255,255,0.40);
      color: var(--btnText);
      cursor:pointer;
      line-height:30px;
      text-align:center;
      font-weight: 900;
      user-select:none;
    }
    [data-theme="dark"] .iconBtn, [data-theme="blue"] .iconBtn { background: rgba(255,255,255,0.06); }
    .iconBtn:hover{ border-color: rgba(37,99,235,0.35); }
    .iconBtn.danger:hover{ border-color: rgba(220,38,38,0.55); }

    .themeBox {
      display:flex; align-items:center; gap:10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.55);
      padding: 8px 10px;
      border-radius: 999px;
    }
    [data-theme="dark"] .themeBox, [data-theme="blue"] .themeBox { background: rgba(255,255,255,0.06); }
    .themeLabel { color: var(--muted); font-size: 12px; }
    select {
      border-radius: 999px;
      border: 1px solid var(--border);
      padding: 8px 10px;
      background: rgba(255,255,255,0.65);
      color: var(--text);
      outline: none;
    }
    [data-theme="dark"] select, [data-theme="blue"] select { background: rgba(255,255,255,0.06); }

    /* Toast */
    .toastWrap{
      position: fixed;
      right: 14px;
      top: 14px;
      display: grid;
      gap: 10px;
      z-index: 9999;
    }
    .toast{
      position: relative;
      overflow: hidden;
      min-width: 260px;
      max-width: 360px;
      padding: 12px 12px 12px 36px; /* leave space for status dot */
      border-radius: 16px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.85);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
      animation: pop 140ms ease-out;
    }
    [data-theme="dark"] .toast, [data-theme="blue"] .toast { background: rgba(10, 20, 40, 0.78); }

    /* left accent bar */
    .toast::before{
      content:'';
      position:absolute;
      left:0;
      top:0;
      bottom:0;
      width:4px;
      background: var(--border);
    }

    /* status circle */
    .toast::after{
      content:'';
      position:absolute;
      left:14px;
      top:50%;
      width:10px;
      height:10px;
      border-radius:50%;
      transform: translateY(-50%);
      background: var(--muted);
    }

    .toastTop{ display:flex; align-items:center; justify-content:space-between; gap:10px; }
    .toastTitle{ font-weight: 900; letter-spacing:0.2px; }
    .toastMsg{ font-size: 12px; color: var(--muted); margin-top:4px; }

    /* GRANTED */
    .toastGood{ border-color: rgba(22,163,74,0.55); }
    .toastGood::before{ background: var(--good); }
    .toastGood::after{
      background: var(--good);
      box-shadow: 0 0 0 0 rgba(22,163,74,0.7);
      animation: pulseGood 1.4s infinite;
    }

    /* DENIED */
    .toastBad{ border-color: rgba(220,38,38,0.55); }
    .toastBad::before{ background: var(--bad); }
    .toastBad::after{
      background: var(--bad);
      box-shadow: 0 0 0 0 rgba(220,38,38,0.7);
      animation: pulseBad 1.4s infinite;
    }

    /* Neutral */
    .toastNeutral{ border-color: rgba(100,116,139,0.28); }
    .toastNeutral::before{ background: rgba(100,116,139,0.40); }
    .toastNeutral::after{ background: var(--muted); }

    @keyframes pop { from{ transform: translateY(-8px); opacity:0.0; } to{ transform:none; opacity:1; } }

    @keyframes pulseGood{
      0%   { box-shadow: 0 0 0 0 rgba(22,163,74,0.7); }
      70%  { box-shadow: 0 0 0 8px rgba(22,163,74,0.0); }
      100% { box-shadow: 0 0 0 0 rgba(22,163,74,0.0); }
    }
    @keyframes pulseBad{
      0%   { box-shadow: 0 0 0 0 rgba(220,38,38,0.7); }
      70%  { box-shadow: 0 0 0 8px rgba(220,38,38,0.0); }
      100% { box-shadow: 0 0 0 0 rgba(220,38,38,0.0); }
    }

    /* History table */
    table{ width:100%; border-collapse: collapse; }
    th, td{ padding: 10px 10px; border-bottom: 1px solid var(--border); font-size: 13px; }
    th{ text-align:left; color: var(--muted); font-size: 12px; }
    .miniPill{
      display:inline-flex; align-items:center; gap:6px;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      font-weight: 800;
      font-size: 11px;
      user-select:none;
      white-space:nowrap;
    }
    .miniGood{ border-color: rgba(22,163,74,0.35); }
    .miniGood .dot{ background: var(--good); }
    .miniBad{ border-color: rgba(220,38,38,0.35); }
    .miniBad .dot{ background: var(--bad); }
  </style>
</head>

<body>
<div class="wrap">

  <div class="topbar">
    <div class="brand">
      <div class="logo"></div>
      <div>
        <h1>ESP32 NFC Panel</h1>
        <div class="subtitle">Live статус через SSE • /events</div>
      </div>
    </div>

    <div style="display:flex; align-items:center; gap:10px;">
      <div class="themeBox">
        <span class="themeLabel">Theme</span>
        <select id="themeSel" onchange="setTheme(this.value)">
          <option value="light">Light</option>
          <option value="dark">Dark</option>
          <option value="blue">Dark Blue</option>
        </select>
      </div>
      <button onclick="logout()" title="Logout" style="padding:10px 16px;">Logout</button>
    </div>
  </div>

  <div class="grid">

    <div class="card">
      <div class="kv">
        <div class="k">Firmware</div>
        <div class="v"><code id="fw">__FW__</code></div>

        <div class="k">Last UID</div>
        <div class="v"><code id="uid">__UID__</code></div>

        <div class="k">Name</div>
        <div class="v"><code id="name">__NAME__</code></div>

        <div class="k">Access</div>
        <div class="v">
          <span id="accPill" class="pill __ACC_CLASS__"><span class="dot"></span><span id="accTxt">__ACC__</span></span>
        </div>

        <div class="k">Time</div>
        <div class="v"><code id="ts">—</code></div>
      </div>
    </div>

    <div class="card">
      <div style="font-weight:900; margin-bottom:8px;">Manage UIDs</div>

      <div class="actions">
        <div>
          <input id="token_in" type="password" placeholder="Admin Token" autocomplete="off"/>
          <div style="height:8px;"></div>
          <input id="uid_in" placeholder="UID: напр 15 D6 14 06 або 15:D6:14:06" autocomplete="off"/>
          <div style="height:8px;"></div>
          <input id="name_in" placeholder="Name: напр Оля / Склад / Майстер-ключ" autocomplete="off"/>
        </div>

        <div class="rowBtns">
          <button class="primary" onclick="addUid()">Add</button>
          <button onclick="rmUid()">Remove</button>
          <button class="primary" onclick="addLastUid()">Add LAST UID</button>
          <button class="primary" onclick="setName()">Set Name</button>
          <button class="danger" onclick="clrUid()">Clear</button>
        </div>
      </div>

      <ul id="uids" class="uids">__UIDS__</ul>
    </div>

  </div>

  <div class="card">
    <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:8px;">
      <div style="font-weight:900;">History (last 20)</div>
      <button onclick="clearHistory()">Clear history</button>
    </div>
    <div style="overflow:auto;">
      <table>
        <thead>
          <tr>
            <th style="min-width:90px;">Time</th>
            <th style="min-width:210px;">UID</th>
            <th style="min-width:140px;">Name</th>
            <th style="min-width:110px;">Access</th>
          </tr>
        </thead>
        <tbody id="histBody">
          <tr><td colspan="4" style="color:var(--muted);">Waiting for first tap…</td></tr>
        </tbody>
      </table>
    </div>
  </div>

</div>

<div class="toastWrap" id="toastWrap"></div>

<script>
  function api(path, data){
    const token = (document.getElementById('token_in')?.value || '').trim();
    const headers = {"Content-Type":"application/json"};
    if(token) headers["X-Admin-Token"] = token;
    
    const body = data || {};
    if(token) body.token = token;
    
    return fetch(path, {
      method:"POST",
      headers: headers,
      body:JSON.stringify(body)
    }).then(r=>r.json()).then(r=>{
      if(!r.ok && r.msg && r.msg.toLowerCase().includes('unauthorized')){
        toast('AUTH REQUIRED', 'Please enter admin token', 'bad');
      }
      return r;
    });
  }

  // Toast
  function toast(title, msg, kind){
    const wrap = document.getElementById('toastWrap');
    const el = document.createElement('div');
    el.className = 'toast ' + (kind==='good'?'toastGood':(kind==='bad'?'toastBad':'toastNeutral'));
    el.innerHTML = `
      <div class="toastTop">
        <div class="toastTitle">${escapeHtml(title||'Info')}</div>
        <div style="opacity:0.7; font-size:12px;">${new Date().toLocaleTimeString()}</div>
      </div>
      <div class="toastMsg">${escapeHtml(msg||'')}</div>
    `;
    wrap.appendChild(el);
    setTimeout(()=>{ try{ el.remove(); }catch(e){} }, 2400);
  }

  function escapeHtml(s){
    s = (s==null)?'':String(s);
    return s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  }

  function refreshList(){
    api('/api/uids/list',{}).then(r=>{
      const ul = document.getElementById('uids');
      if(!ul) return;
      ul.innerHTML = '';
      (r.cards||[]).forEach(c=>{
        const li = document.createElement('li');
        li.className = 'uid-item';

        const left = document.createElement('span');
        left.className = 'uid-text';
        left.textContent = c.uid + (c.name ? (' — ' + c.name) : '');

        const acts = document.createElement('span');
        acts.className = 'uid-actions';

        const bEdit = document.createElement('button');
        bEdit.className = 'iconBtn';
        bEdit.title = 'Edit';
        bEdit.textContent = '✎';
        bEdit.onclick = ()=>pickUid(c.uid||'', c.name||'');

        const bDel = document.createElement('button');
        bDel.className = 'iconBtn danger';
        bDel.title = 'Delete';
        bDel.textContent = '✖';
        bDel.onclick = ()=>delUid(c.uid||'');

        acts.appendChild(bEdit);
        acts.appendChild(bDel);

        li.appendChild(left);
        li.appendChild(acts);
        ul.appendChild(li);
      });
    }).catch(_=>{});
  }

  function addUid(){
    const uid = (document.getElementById('uid_in').value||'');
    const name = (document.getElementById('name_in').value||'');
    api('/api/uids/add', {uid_hex: uid, name: name}).then(r=>{
      document.getElementById('uid_in').value='';
      document.getElementById('name_in').value='';
      refreshList();
      toast(r.ok ? 'OK' : 'ERR', r.msg || 'Add', r.ok ? 'good' : 'bad');
    }).catch(_=>{ toast('ERR','API error','bad'); });
  }

  function rmUid(){
    const uid = (document.getElementById('uid_in').value||'');
    api('/api/uids/remove', {uid_hex: uid}).then(r=>{
      document.getElementById('uid_in').value='';
      refreshList();
      toast(r.ok ? 'OK' : 'ERR', r.msg || 'Remove', r.ok ? 'good' : 'bad');
    }).catch(_=>{ toast('ERR','API error','bad'); });
  }

  function addLastUid(){
    api('/api/uids/add_last', {}).then(r=>{
      refreshList();
      toast(r.ok ? 'OK' : 'ERR', r.msg || 'Add last', r.ok ? 'good' : 'bad');
    }).catch(_=>{ toast('ERR','API error','bad'); });
  }

  function setName(){
    const uid = (document.getElementById('uid_in').value||'');
    const name = (document.getElementById('name_in').value||'');
    api('/api/uids/set_name', {uid_hex: uid, name: name}).then(r=>{
      refreshList();
      toast(r.ok ? 'OK' : 'ERR', r.msg || 'Set name', r.ok ? 'good' : 'bad');
    }).catch(_=>{ toast('ERR','API error','bad'); });
  }

  function clrUid(){
    api('/api/uids/clear', {}).then(r=>{
      refreshList();
      toast(r.ok ? 'OK' : 'ERR', r.msg || 'Clear', r.ok ? 'good' : 'bad');
    }).catch(_=>{ toast('ERR','API error','bad'); });
  }

  // --- NEW: edit & delete helpers (do not change existing logic) ---
  function pickUid(uid, name){
    const u = document.getElementById('uid_in');
    const n = document.getElementById('name_in');
    if(u) u.value = uid || '';
    if(n) n.value = name || '';
    toast('OK', 'Filled fields from list', 'neutral');
  }

  function delUid(uid){
    if(!uid) return;
    api('/api/uids/remove', {uid_hex: uid}).then(r=>{
      refreshList();
      toast(r.ok ? 'OK' : 'ERR', r.msg || 'Delete', r.ok ? 'good' : 'bad');
    }).catch(_=>{ toast('ERR','API error','bad'); });
  }

  // Theme
  function setTheme(t){
    document.documentElement.setAttribute('data-theme', t);
    try{ localStorage.setItem('esp_theme', t); }catch(e){}
    const sel = document.getElementById('themeSel');
    if(sel && sel.value !== t) sel.value = t;
  }
  (function(){
    let t = 'light';
    try{ t = localStorage.getItem('esp_theme') || 'light'; }catch(e){}
    setTheme(t);
  })();

  // Token persistence
  (function(){
    const tokenInput = document.getElementById('token_in');
    if(tokenInput){
      try{
        const saved = localStorage.getItem('esp_admin_token');
        if(saved) tokenInput.value = saved;
      }catch(e){}
      
      tokenInput.addEventListener('input', function(){
        try{
          localStorage.setItem('esp_admin_token', this.value);
        }catch(e){}
      });
    }
  })();

  // History (client-side buffer)
  const HISTORY_MAX = 20;
  let hist = [];

  function fmtTime(ts){
    try{
      if(!ts) return new Date().toLocaleTimeString();
      if(typeof ts === 'number') return new Date(ts).toLocaleTimeString();
      const d = new Date(ts);
      if(!isNaN(d.getTime())) return d.toLocaleTimeString();
      return String(ts);
    }catch(e){
      return new Date().toLocaleTimeString();
    }
  }

  function addHistoryRow(item){
    hist.unshift(item);
    if(hist.length > HISTORY_MAX) hist = hist.slice(0, HISTORY_MAX);
    renderHistory();
  }

  function renderHistory(){
    const tb = document.getElementById('histBody');
    if(!tb) return;
    tb.innerHTML = '';
    if(hist.length === 0){
      tb.innerHTML = `<tr><td colspan="4" style="color:var(--muted);">Waiting for first tap…</td></tr>`;
      return;
    }
    hist.forEach(x=>{
      const isGood = (String(x.access||'').toUpperCase() === 'GRANTED');
      const pill = `<span class="miniPill ${isGood?'miniGood':'miniBad'}"><span class="dot"></span>${escapeHtml(x.access||'')}</span>`;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${escapeHtml(fmtTime(x.ts))}</td>
        <td><code>${escapeHtml(x.uid||'')}</code></td>
        <td>${escapeHtml(x.name||'')}</td>
        <td>${pill}</td>
      `;
      tb.appendChild(tr);
    });
  }

  function clearHistory(){
    hist = [];
    renderHistory();
    toast('OK','History cleared','neutral');
  }

  function setAccessPill(access){
    const pill = document.getElementById('accPill');
    const txt  = document.getElementById('accTxt');
    if(!pill || !txt) return;

    const a = String(access||'').toUpperCase();
    pill.classList.remove('pill-good','pill-bad','pill-neutral');
    if(a === 'GRANTED') pill.classList.add('pill-good');
    else if(a === 'DENIED') pill.classList.add('pill-bad');
    else pill.classList.add('pill-neutral');

    txt.innerText = access || '';
  }

  // Logout
  function logout(){
    window.location.href = '/logout';
  }

  // SSE
  let lastEventId = null;
  const es = new EventSource('/events');
  es.addEventListener('update', (e)=>{
    const d = JSON.parse(e.data);

    document.getElementById('fw').innerText = d.fw || '';
    document.getElementById('uid').innerText = d.uid || '';
    document.getElementById('name').innerText = (d.name || '');
    setAccessPill(d.access || '');

    const ts = d.ts || new Date().toISOString();
    document.getElementById('ts').innerText = fmtTime(ts);

    if(d.id != null && d.id !== lastEventId){
      if(lastEventId !== null){
        const a = String(d.access||'').toUpperCase();
        if(a === 'GRANTED') toast('GRANTED', (d.uid||'') + (d.name?(' — '+d.name):''), 'good');
        else if(a === 'DENIED') toast('DENIED', (d.uid||'') + (d.name?(' — '+d.name):''), 'bad');
      }
      lastEventId = d.id;
    }

    if(d.uid){
      addHistoryRow({ ts: ts, uid: d.uid, name: (d.name||''), access: (d.access||'') });
    }
  });

</script>

</body>
</html>
"""

    html = html.replace("__FW__", html_escape(last_fw))
    html = html.replace("__UID__", html_escape(last_uid))
    html = html.replace("__ACC__", html_escape(last_access))
    html = html.replace("__NAME__", html_escape(last_name))
    html = html.replace("__UIDS__", uids_li)
    html = html.replace("__ACC_CLASS__", acc_class)
    return html


# --- helper: safe JS string literal (no extra imports, minimal) ---
def ujson_safe(s):
    # returns JS string literal in double quotes, already escaped
    # example: "EA 98 CF 06"
    s = str(s if s is not None else "")
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\r", "\\r")
    return '"' + s + '"'