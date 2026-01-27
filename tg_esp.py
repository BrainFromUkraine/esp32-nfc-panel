# tg_esp.py
import time
import gc
import usocket
import ujson

# SSL compatibility: some builds provide ssl (no ussl alias)
try:
    import ssl as ussl
except ImportError:
    import ussl

_STATE_FILE = "tg_state.json"

# IMPORTANT:
# Do NOT hardcode real token here.
# Set it from app.py via configure().
_bot_token = ""
_admin_chat_id = 0
_poll_every_ms = 1500
_last_poll_ms = 0


def configure(bot_token: str, admin_chat_id: int, poll_every_ms: int = 1500):
    global _bot_token, _admin_chat_id, _poll_every_ms
    _bot_token = (bot_token or "").strip()
    _admin_chat_id = int(admin_chat_id) if admin_chat_id is not None else 0
    _poll_every_ms = int(poll_every_ms) if poll_every_ms else 1500


def _load_json(path: str, default):
    try:
        with open(path, "r") as f:
            return ujson.load(f)
    except Exception:
        return default


def _save_json(path: str, obj):
    try:
        with open(path, "w") as f:
            ujson.dump(obj, f)
    except Exception:
        pass


def _urlencode(s: str) -> str:
    if s is None:
        return ""
    out = []
    for ch in str(s):
        o = ord(ch)
        if (48 <= o <= 57) or (65 <= o <= 90) or (97 <= o <= 122) or ch in "-_.~":
            out.append(ch)
        elif ch == " ":
            out.append("%20")
        else:
            out.append("%{:02X}".format(o & 0xFF))
    return "".join(out)


def _tls_wrap(sock, host: str):
    # Some ports accept server_hostname; keep safe fallback.
    try:
        return ussl.wrap_socket(sock, server_hostname=host)
    except TypeError:
        return ussl.wrap_socket(sock)


def _https_get_find_ok(host: str, path: str, timeout=8) -> bool:
    """
    Streaming read: doesn't store full response.
    Returns True if '"ok":true' seen in stream.
    """
    gc.collect()
    ai = usocket.getaddrinfo(host, 443, 0, usocket.SOCK_STREAM)[0][-1]
    s = usocket.socket()
    s.settimeout(timeout)
    s.connect(ai)

    gc.collect()
    ss = _tls_wrap(s, host)

    req = "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\nUser-Agent: esp32\r\n\r\n".format(path, host)
    ss.write(req.encode())

    needle1 = b'"ok":true'
    needle2 = b'"ok": true'
    buf = b""
    ok = False

    while True:
        try:
            chunk = ss.read(256)
        except Exception:
            break
        if not chunk:
            break

        buf = (buf + chunk)[-512:]
        if (needle1 in buf) or (needle2 in buf):
            ok = True
            break

    try:
        ss.close()
    except Exception:
        pass
    try:
        s.close()
    except Exception:
        pass

    gc.collect()
    return ok


def _https_get_small(host: str, path: str, timeout=8, max_bytes=3500) -> str:
    """
    Returns response string but capped. Used for getUpdates.
    """
    gc.collect()
    ai = usocket.getaddrinfo(host, 443, 0, usocket.SOCK_STREAM)[0][-1]
    s = usocket.socket()
    s.settimeout(timeout)
    s.connect(ai)

    gc.collect()
    ss = _tls_wrap(s, host)

    req = "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\nUser-Agent: esp32\r\n\r\n".format(path, host)
    ss.write(req.encode())

    data = b""
    while True:
        try:
            chunk = ss.read(256)
        except Exception:
            break
        if not chunk:
            break
        data += chunk
        if len(data) >= max_bytes:
            break

    try:
        ss.close()
    except Exception:
        pass
    try:
        s.close()
    except Exception:
        pass

    gc.collect()
    try:
        return data.decode()
    except Exception:
        return ""


def send_text(text: str) -> bool:
    if not _bot_token or not _admin_chat_id:
        return False
    host = "api.telegram.org"
    t = _urlencode(text)
    path = "/bot{}/sendMessage?chat_id={}&text={}&disable_web_page_preview=1".format(
        _bot_token, _admin_chat_id, t
    )
    try:
        return _https_get_find_ok(host, path)
    except Exception:
        return False


def normalize_uid(uid_hex: str):
    if not uid_hex:
        return None
    s = uid_hex.strip().replace(":", " ").replace("-", " ")
    s = " ".join(s.split())
    if not s:
        return None

    if " " not in s:
        if len(s) % 2 != 0:
            return None
        parts = [s[i:i + 2] for i in range(0, len(s), 2)]
    else:
        parts = s.split(" ")

    out = []
    for p in parts:
        if len(p) != 2:
            return None
        try:
            v = int(p, 16)
        except Exception:
            return None
        out.append("{:02X}".format(v))
    return " ".join(out) if out else None


def _load_state():
    return _load_json(_STATE_FILE, {"offset": 0})


def _save_state(st):
    _save_json(_STATE_FILE, st)


def _extract_updates_minimal(resp: str):
    out = []
    if not resp:
        return out

    p = resp.find("\r\n\r\n")
    body = resp[p + 4:] if p >= 0 else resp

    idx = 0
    while True:
        u = body.find("\"update_id\":", idx)
        if u < 0:
            break
        u2 = body.find(",", u)
        if u2 < 0:
            break
        try:
            update_id = int(body[u + 12:u2].strip())
        except Exception:
            idx = u2 + 1
            continue

        c = body.find("\"chat\":", u2)
        if c < 0:
            idx = u2 + 1
            continue
        cid_key = body.find("\"id\":", c)
        if cid_key < 0:
            idx = u2 + 1
            continue
        cid_end = body.find(",", cid_key)
        if cid_end < 0:
            idx = u2 + 1
            continue
        try:
            chat_id = int(body[cid_key + 5:cid_end].strip())
        except Exception:
            idx = cid_end + 1
            continue

        tkey = body.find("\"text\":", cid_end)
        if tkey < 0:
            idx = cid_end + 1
            continue
        q1 = body.find("\"", tkey + 7)
        if q1 < 0:
            idx = tkey + 7
            continue
        q2 = body.find("\"", q1 + 1)
        if q2 < 0:
            idx = q1 + 1
            continue
        text = body[q1 + 1:q2]

        out.append((update_id, chat_id, text))
        idx = q2 + 1
        if len(out) >= 2:
            break
    return out


def tick(on_command_cb):
    global _last_poll_ms

    if not _bot_token or not _admin_chat_id:
        return

    now = time.ticks_ms()
    if time.ticks_diff(now, _last_poll_ms) < _poll_every_ms:
        return
    _last_poll_ms = now

    st = _load_state()
    offset = int(st.get("offset", 0))

    host = "api.telegram.org"
    path = "/bot{}/getUpdates?timeout=0&offset={}&limit=2".format(_bot_token, offset)

    try:
        resp = _https_get_small(host, path)
    except Exception:
        return

    items = _extract_updates_minimal(resp)
    if not items:
        return

    max_update = offset
    for update_id, chat_id, text in items:
        if update_id >= max_update:
            max_update = update_id + 1

        if int(chat_id) != int(_admin_chat_id):
            continue

        ans = on_command_cb(text)
        if ans:
            send_text(ans)

    st["offset"] = max_update
    _save_state(st)


def notify_uid(uid_hex: str, access: str, device_name: str = "ESP32"):
    nu = normalize_uid(uid_hex)
    if not nu:
        return
    txt = "NFC TAP\nDEV: {}\nUID: {}\nACCESS: {}\n/add_last".format(device_name, nu, access)
    send_text(txt)