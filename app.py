# app.py
import ui_html
import time
import socket
import ujson
import network
import wifi_prov
import neopixel
from machine import Pin, I2C
from pn532 import PN532_I2C
import encrypt

# -----------------------
# SETTINGS
# -----------------------
I2C_ID = 0
I2C_SCL = 8
I2C_SDA = 9
I2C_FREQ = 20000
PN532_ADDR = 0x24

# LED on Freenove is WS2812 on GPIO48 (NOT a simple LED).
LED_PIN = 48

DEBUG_ERRORS = True




# -----------------------
# TELEGRAM (ESP32 автономно)
# -----------------------
encrypt.encrypt_existing_file()
settings = encrypt.load_config()

TG_ENABLED = settings.get("TG_ENABLED")
TG_BOT_TOKEN = settings.get("TG_BOT_TOKEN")
TG_ADMIN_CHAT_ID = settings.get("TG_ADMIN_CHAT_ID")
TG_DEVICE_NAME = settings.get("TG_DEVICE_NAME")
TG_POLL_EVERY_MS = settings.get("TG_POLL_EVERY_MS")
TG_NOTIFY_ON_TAP = settings.get("TG_NOTIFY_ON_TAP")

# ✅ Freenove BOOT button is GPIO0
BTN_PIN = 0
BTN_ACTIVE_LOW = True

PRESS_WINDOW_MS = 30000
PRESS_TARGET = 7
DEBOUNCE_MS = 180
HOLD_CLEAR_MS = 10000

NFC_POLL_TIMEOUT_MS = 80
NFC_LOOP_SLEEP_MS = 25

LOG_BTN = True
LOG_PORTAL = True

UIDS_FILE = "uids.json"
DEFAULT_UIDS_HEX = []

ALLOWED_UIDS = set()
ALLOWED_UIDS_HEX = set()

# ✅ NEW: Names storage
UID_NAME_BY_HEX = {}   # "15 D6 14 06" -> "John"
DEFAULT_CARDS = []     # optional: [{"uid":"..","name":".."}]

LAST_UID_HEX = ""
LAST_ACCESS = ""
LAST_FW = ""
LAST_NAME = ""
EVENT_ID = 0


# -----------------------
# TIME / LOG
# -----------------------
def now_ms():
    return time.ticks_ms()


def ms_diff(a, b):
    return time.ticks_diff(a, b)


def op_ms(t0):
    return ms_diff(time.ticks_ms(), t0)


def log(*args):
    try:
        print(*args)
    except:
        pass


def op_log(name, ms, extra=""):
    try:
        print("[OP]", name, ms, extra)
    except:
        pass


# -----------------------
# WS2812 (NeoPixel) helpers
# -----------------------
def _np_off(np):
    try:
        if np and hasattr(np, "write"):
            np[0] = (0, 0, 0)
            np.write()
    except:
        pass


def _np_set(np, color):
    try:
        if np and hasattr(np, "write"):
            np[0] = color
            np.write()
    except:
        pass


def breathe(np, color=(0, 60, 0), duration_ms=500, steps=18):
    if np is None or (not hasattr(np, "write")):
        return
    try:
        half_steps = max(6, steps)
        delay = max(8, duration_ms // (half_steps * 2))
        r0, g0, b0 = color

        for i in range(half_steps + 1):
            k = i / half_steps
            np[0] = (int(r0 * k), int(g0 * k), int(b0 * k))
            np.write()
            time.sleep_ms(delay)

        for i in range(half_steps, -1, -1):
            k = i / half_steps
            np[0] = (int(r0 * k), int(g0 * k), int(b0 * k))
            np.write()
            time.sleep_ms(delay)

        _np_off(np)
    except:
        _np_off(np)


def fast_blink(np, color=(60, 0, 0), times=4, on_ms=60, off_ms=60):
    if np is None:
        return
    try:
        for _ in range(times):
            _np_set(np, color)
            time.sleep_ms(on_ms)
            _np_off(np)
            time.sleep_ms(off_ms)
    except:
        _np_off(np)


def blink(led, times=1, on_ms=150, off_ms=150, color=(40, 40, 40)):
    if led is None:
        return
    try:
        if hasattr(led, "write"):
            for _ in range(times):
                led[0] = color
                led.write()
                time.sleep_ms(on_ms)
                led[0] = (0, 0, 0)
                led.write()
                time.sleep_ms(off_ms)
        else:
            for _ in range(times):
                led.value(1)
                time.sleep_ms(on_ms)
                led.value(0)
                time.sleep_ms(off_ms)
    except:
        pass


# -----------------------
# UID utils + storage
# -----------------------
def uid_bytes_to_hex(uid_bytes: bytes):
    return " ".join(["{:02X}".format(b) for b in uid_bytes])


def uid_hex_to_bytes(uid_hex: str):
    try:
        if not uid_hex:
            return None
        s = uid_hex.strip()
        if not s:
            return None

        cleaned = []
        for ch in s:
            o = ord(ch)
            is_hex = (48 <= o <= 57) or (65 <= o <= 70) or (97 <= o <= 102)
            cleaned.append(ch if is_hex else " ")

        s = "".join(cleaned)
        s = " ".join(s.split())
        if not s:
            return None

        parts = s.split(" ")

        if len(parts) == 1 and len(parts[0]) > 2:
            raw = parts[0]
            if len(raw) % 2 != 0:
                return None
            parts = [raw[i:i+2] for i in range(0, len(raw), 2)]

        data = bytes([int(p, 16) for p in parts if p])
        return data if len(data) > 0 else None
    except:
        return None


def _sync_hex_set_from_bytes():
    global ALLOWED_UIDS_HEX
    ALLOWED_UIDS_HEX = set([uid_bytes_to_hex(u) for u in ALLOWED_UIDS])


def uids_list_cards():
    _sync_hex_set_from_bytes()
    out = []
    for hx in sorted(list(ALLOWED_UIDS_HEX)):
        out.append({"uid": hx, "name": UID_NAME_BY_HEX.get(hx, "")})
    return out


def uids_list_hex():
    return [c["uid"] for c in uids_list_cards()]


def _load_uids_file_or_init():
    global ALLOWED_UIDS, ALLOWED_UIDS_HEX, UID_NAME_BY_HEX
    UID_NAME_BY_HEX = {}
    try:
        with open(UIDS_FILE, "r") as f:
            j = ujson.load(f)

        tmp = set()

        # NEW format
        if "cards" in j and isinstance(j.get("cards"), list):
            for item in j.get("cards", []):
                hx = (item.get("uid") or "").strip()
                nm = (item.get("name") or "").strip()
                b = uid_hex_to_bytes(hx)
                if b:
                    tmp.add(b)
                    UID_NAME_BY_HEX[uid_bytes_to_hex(b)] = nm or ""
            ALLOWED_UIDS = tmp
            _sync_hex_set_from_bytes()
            log("UIDS", "loaded cards:", len(ALLOWED_UIDS))
            return True

        # OLD format compatibility: {"uids":[...]}
        uids = j.get("uids", [])
        for hx in uids:
            b = uid_hex_to_bytes(hx)
            if b:
                tmp.add(b)
        ALLOWED_UIDS = tmp
        _sync_hex_set_from_bytes()

        for hx in list(ALLOWED_UIDS_HEX):
            UID_NAME_BY_HEX[hx] = ""

        log("UIDS", "loaded (old format):", len(ALLOWED_UIDS))
        _save_uids_file()
        return True

    except Exception as e:
        log("UIDS", "no file -> init default:", e)

    tmp = set()

    for hx in DEFAULT_UIDS_HEX:
        b = uid_hex_to_bytes(hx)
        if b:
            tmp.add(b)
            UID_NAME_BY_HEX[uid_bytes_to_hex(b)] = ""

    for item in DEFAULT_CARDS:
        hx = (item.get("uid") or "").strip()
        nm = (item.get("name") or "").strip()
        b = uid_hex_to_bytes(hx)
        if b:
            tmp.add(b)
            UID_NAME_BY_HEX[uid_bytes_to_hex(b)] = nm or ""

    ALLOWED_UIDS = tmp
    _sync_hex_set_from_bytes()
    _save_uids_file()
    log("UIDS", "initialized:", len(ALLOWED_UIDS))
    return True


def _save_uids_file():
    try:
        _sync_hex_set_from_bytes()
        cards = []
        for hx in sorted(list(ALLOWED_UIDS_HEX)):
            cards.append({"uid": hx, "name": UID_NAME_BY_HEX.get(hx, "")})
        with open(UIDS_FILE, "w") as f:
            ujson.dump({"cards": cards}, f)
        return True
    except Exception as e:
        log("UIDS", "save error:", e)
        return False


def uids_add(uid_hex: str, name: str = ""):
    global ALLOWED_UIDS
    b = uid_hex_to_bytes(uid_hex)
    if not b:
        return False, "Bad UID format"
    hx = uid_bytes_to_hex(b)

    if b in ALLOWED_UIDS:
        if name is not None and str(name).strip() != "":
            UID_NAME_BY_HEX[hx] = str(name).strip()
            _save_uids_file()
            return True, "Name updated: {} -> {}".format(hx, UID_NAME_BY_HEX[hx])
        return True, "Already exists"

    ALLOWED_UIDS.add(b)
    UID_NAME_BY_HEX[hx] = (str(name).strip() if name else "")
    ok = _save_uids_file()
    return bool(ok), "Added: {}".format(hx)


def uids_remove(uid_hex: str):
    global ALLOWED_UIDS
    b = uid_hex_to_bytes(uid_hex)
    if not b:
        return False, "Bad UID format"
    hx = uid_bytes_to_hex(b)
    if b not in ALLOWED_UIDS:
        return False, "Not found"

    ALLOWED_UIDS.remove(b)
    try:
        if hx in UID_NAME_BY_HEX:
            del UID_NAME_BY_HEX[hx]
    except:
        pass

    ok = _save_uids_file()
    return bool(ok), "Removed: {}".format(hx)


def uids_set_name(uid_hex: str, name: str):
    b = uid_hex_to_bytes(uid_hex)
    if not b:
        return False, "Bad UID format"
    hx = uid_bytes_to_hex(b)
    if b not in ALLOWED_UIDS:
        return False, "Not found"

    UID_NAME_BY_HEX[hx] = (str(name).strip() if name else "")
    ok = _save_uids_file()
    return bool(ok), "Renamed: {} -> {}".format(hx, UID_NAME_BY_HEX[hx])


def uids_clear_all():
    global ALLOWED_UIDS, UID_NAME_BY_HEX
    ALLOWED_UIDS = set()
    UID_NAME_BY_HEX = {}
    ok = _save_uids_file()
    return bool(ok)


# -----------------------
# HTTP helpers
# -----------------------
def _read_http_request(cl):
    try:
        cl.settimeout(1.0)
        data = cl.recv(2048)
        if not data:
            return None

        t0 = time.ticks_ms()
        while (b"\r\n\r\n" not in data) and (time.ticks_diff(time.ticks_ms(), t0) < 250):
            try:
                more = cl.recv(2048)
                if not more:
                    break
                data += more
            except:
                break

        head, body = (data.split(b"\r\n\r\n", 1) + [b""])[:2]
        lines = head.split(b"\r\n")
        if not lines:
            return None

        req_line = lines[0].decode()
        method, path, _ = req_line.split(" ", 2)

        headers = {}
        for ln in lines[1:]:
            if b":" in ln:
                k, v = ln.split(b":", 1)
                headers[k.strip().lower().decode()] = v.strip().decode()

        cl_len = int(headers.get("content-length", "0") or "0")
        if cl_len > len(body):
            need = cl_len - len(body)
            while need > 0:
                chunk = cl.recv(min(2048, need))
                if not chunk:
                    break
                body += chunk
                need -= len(chunk)

        return method, path, headers, body
    except Exception as e:
        if DEBUG_ERRORS and getattr(e, "errno", None) != 116:
            log("HTTP", "read error:", e)
        return None


def _http_send(cl, status="200 OK", ctype="text/plain; charset=utf-8", body=""):
    try:
        body_b = body.encode() if isinstance(body, str) else body
        hdr = "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n".format(
            status, ctype, len(body_b)
        )
        cl.send(hdr.encode() + body_b)
    except:
        pass


def _json_response(cl, obj, status="200 OK"):
    _http_send(cl, status=status, ctype="application/json", body=ujson.dumps(obj))


def _sse_headers():
    return (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/event-stream\r\n"
        "Cache-Control: no-cache\r\n"
        "Connection: keep-alive\r\n\r\n"
    )


def _sse_event(event_id, fw, uid_hex, access, uids=None, ok=None, msg=None, src=None, cards=None, name=None):
    if uids is None:
        uids = []
    if cards is None:
        cards = []
    payload = {"id": event_id, "fw": fw, "uid": uid_hex, "access": access, "uids": uids, "cards": cards}
    if name is not None:
        payload["name"] = name
    if src is not None:
        payload["src"] = src
    if ok is not None:
        payload["ok"] = bool(ok)
    if msg is not None:
        payload["msg"] = msg
    return "event: update\ndata: {}\n\n".format(ujson.dumps(payload))


# -----------------------
# WEB SERVER + PORTAL
# -----------------------
def _start_web_server():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(2)
    s.setblocking(False)
    log("PORT80", "listening on :80")
    return s


def _sta_mode_restore():
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    except:
        pass


def _enter_wifi_setup_and_return(srv, sse_client):
    if LOG_PORTAL:
        log("PORTAL", "enter provisioning (closing app server)")

    if srv:
        try:
            srv.close()
        except:
            pass
        srv = None

    try:
        if sse_client:
            sse_client.close()
    except:
        pass
    sse_client = None

    op_t0 = time.ticks_ms()
    try:
        wifi_prov.provisioning_portal(loop_forever=False)
    except Exception as e:
        log("PORTAL", "error:", e)
    op_dt = op_ms(op_t0)
    op_log("PORTAL_SESSION", op_dt)

    _sta_mode_restore()

    if LOG_PORTAL:
        log("PORTAL", "returned from portal, restarting app web server")

    time.sleep_ms(200)
    try:
        srv = _start_web_server()
    except Exception as e:
        log("PORT80", "cannot start app server:", e)
        srv = None

    return srv, sse_client


# ---- Telegram wrapper: do not crash if tg_esp/SSL missing ----
try:
    import tg_esp
except Exception as e:
    tg_esp = None
    TG_ENABLED = False
    log("TG", "disabled (tg_esp import failed):", e)


# -----------------------
# MAIN APP LOOP
# -----------------------
def run():
    global LAST_UID_HEX, LAST_ACCESS, LAST_FW, LAST_NAME, EVENT_ID

    log("APP", "run() start")
    _load_uids_file_or_init()

    tg_ready = False
    tg_online_sent = False
    tg_last_try_ms = 0

    if TG_ENABLED and tg_esp and TG_BOT_TOKEN and TG_BOT_TOKEN != "PUT_YOUR_NEW_TOKEN_HERE":
        try:
            tg_esp.configure(TG_BOT_TOKEN, TG_ADMIN_CHAT_ID, TG_POLL_EVERY_MS)
            tg_ready = True
        except Exception as e:
            tg_ready = False
            if DEBUG_ERRORS:
                log("TG", "configure fail:", e)

    # LED
    led = None
    if LED_PIN is not None:
        try:
            led = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), 1)
            led[0] = (0, 0, 0)
            led.write()
        except Exception as e:
            led = None
            if DEBUG_ERRORS:
                log("LED", "init fail:", e)

    # Button
    btn = Pin(BTN_PIN, Pin.IN, Pin.PULL_UP)

    press_count = 0
    window_start = 0
    last_irq_ms = 0
    request_portal = False
    portal_pending = False
    tap_op_start = 0

    hold_start = 0
    was_down = False

    def btn_is_down():
        return (btn.value() == 0) if BTN_ACTIVE_LOW else (btn.value() == 1)

    def _irq_handler(pin):
        nonlocal press_count, window_start, last_irq_ms, request_portal, portal_pending, tap_op_start
        if portal_pending:
            return

        t = now_ms()
        if ms_diff(t, last_irq_ms) < DEBOUNCE_MS:
            return
        last_irq_ms = t

        if press_count == 0:
            window_start = t
            tap_op_start = t
            if LOG_BTN:
                log("BTN", "window start")

        if ms_diff(t, window_start) > PRESS_WINDOW_MS:
            press_count = 0
            window_start = t
            tap_op_start = t
            if LOG_BTN:
                log("BTN", "window expired -> reset")
                log("BTN", "window start")

        press_count += 1
        if LOG_BTN:
            left = PRESS_WINDOW_MS - ms_diff(t, window_start)
            log("BTN", "tap", press_count, "/", PRESS_TARGET, "window_left_ms=", max(0, left))

        if press_count >= PRESS_TARGET:
            press_count = 0
            window_start = 0
            request_portal = True
            portal_pending = True
            if LOG_BTN:
                log("BTN", "7x -> REQUEST portal")

            dt = ms_diff(t, tap_op_start) if tap_op_start else 0
            op_log("BTN_7TAP", dt, "request portal")
            tap_op_start = 0

    btn.irq(trigger=Pin.IRQ_FALLING, handler=_irq_handler)

    # NFC init
    i2c = I2C(I2C_ID, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)
    nfc = PN532_I2C(i2c, addr=PN532_ADDR)
    time.sleep(0.3)

    fw = nfc.get_firmware_version()
    LAST_FW = fw
    log("NFC", "FW:", fw)
    nfc.sam_config()
    log("NFC", "SAM OK")

    # Web server
    srv = _start_web_server()
    sse_client = None

    def _tg_handle_cmd(text: str):
        nonlocal sse_client
        global EVENT_ID

        t = (text or "").strip()
        if t in ("/start", "/help"):
            return "ESP32 NFC bot\n/last\n/add_last\n/help"

        if t == "/last":
            return "LAST UID: {}\nName: {}\nAccess: {}".format(
                LAST_UID_HEX or "-", LAST_NAME or "-", LAST_ACCESS or "-"
            )

        if t == "/add_last":
            if not LAST_UID_HEX:
                return "No LAST UID (tap a card first)"

            ok, msg = uids_add(LAST_UID_HEX)

            if ok and led is not None:
                blink(led, times=2, on_ms=90, off_ms=60, color=(60, 35, 0))

            EVENT_ID += 1
            if sse_client:
                try:
                    sse_client.send(_sse_event(
                        EVENT_ID, LAST_FW, LAST_UID_HEX, LAST_ACCESS,
                        uids_list_hex(), ok=ok, msg=msg, src="tg",
                        cards=uids_list_cards(), name=LAST_NAME
                    ).encode())
                except:
                    try:
                        sse_client.close()
                    except:
                        pass
                    sse_client = None
                    log("SSE", "client disconnected")

            return ("OK: " if ok else "ERR: ") + msg

        return None

    last_uid = None
    last_time = 0

    while True:
        try:
            # ---- Button hold detection ----
            down = btn_is_down()
            if LOG_BTN and down and not was_down:
                log("BTN", "DOWN (hold start)")
                hold_start = now_ms()

            if down:
                if hold_start and ms_diff(now_ms(), hold_start) >= HOLD_CLEAR_MS:
                    log("BTN", "HOLD 10s -> clear wifi.json + portal")
                    op_t0 = time.ticks_ms()
                    try:
                        ok = wifi_prov.clear_cfg()
                    except:
                        ok = False
                    op_dt = op_ms(op_t0)
                    log("BTN", "wifi.json cleared:", ok)
                    op_log("BTN_HOLD_CLEAR", op_dt, "ok={}".format(ok))
                    hold_start = 0
                    request_portal = True
                    portal_pending = True
            else:
                if LOG_BTN and (not down) and was_down:
                    log("BTN", "UP")
                hold_start = 0
            was_down = down

            # ---- Portal request ----
            if request_portal:
                request_portal = False
                btn.irq(handler=None)
                srv, sse_client = _enter_wifi_setup_and_return(srv, sse_client)
                time.sleep_ms(200)
                portal_pending = False
                btn.irq(trigger=Pin.IRQ_FALLING, handler=_irq_handler)

            # ---- HTTP accept ----
            if srv:
                try:
                    cl, _ = srv.accept()
                except OSError:
                    cl = None

                if cl:
                    req = _read_http_request(cl)
                    if not req:
                        try:
                            cl.close()
                        except:
                            pass
                    else:
                        method, path, headers, body = req

                        if method == "GET" and (path == "/" or path.startswith("/?")):
                            _http_send(
                                cl,
                                status="200 OK",
                                ctype="text/html; charset=utf-8",
                                body=ui_html.build_index_html(
                                    LAST_FW,
                                    LAST_UID_HEX,
                                    LAST_ACCESS,
                                    LAST_NAME,
                                    uids_list_cards()
                                )
                            )
                            try:
                                cl.close()
                            except:
                                pass

                        elif method == "GET" and path.startswith("/events"):
                            try:
                                cl.send(_sse_headers().encode())
                                cl.send(_sse_event(
                                    EVENT_ID, LAST_FW, LAST_UID_HEX, LAST_ACCESS,
                                    uids_list_hex(), src="init",
                                    cards=uids_list_cards(), name=LAST_NAME
                                ).encode())
                                try:
                                    if sse_client:
                                        sse_client.close()
                                except:
                                    pass
                                sse_client = cl
                                log("SSE", "client connected")
                            except:
                                try:
                                    cl.close()
                                except:
                                    pass

                        elif method == "POST" and path == "/api/uids/list":
                            _json_response(cl, {"ok": True, "cards": uids_list_cards()})
                            try:
                                cl.close()
                            except:
                                pass

                        elif method == "POST" and path == "/api/uids/add_last":
                            if not LAST_UID_HEX:
                                ok = False
                                msg = "No LAST UID (tap a card first)"
                            else:
                                ok, msg = uids_add(LAST_UID_HEX)

                            if ok and led is not None:
                                blink(led, times=2, on_ms=90, off_ms=60, color=(60, 35, 0))

                            _json_response(cl, {
                                "ok": bool(ok),
                                "msg": msg,
                                "count": len(ALLOWED_UIDS),
                                "cards": uids_list_cards()
                            })
                            try:
                                cl.close()
                            except:
                                pass

                        elif method == "POST" and path == "/api/uids/add":
                            try:
                                j = ujson.loads(body.decode() if body else "{}")
                            except:
                                j = {}
                            ok, msg = uids_add(j.get("uid_hex", ""), j.get("name", ""))

                            _json_response(cl, {
                                "ok": bool(ok),
                                "msg": msg,
                                "count": len(ALLOWED_UIDS),
                                "cards": uids_list_cards()
                            })
                            try:
                                cl.close()
                            except:
                                pass

                        elif method == "POST" and path == "/api/uids/remove":
                            try:
                                j = ujson.loads(body.decode() if body else "{}")
                            except:
                                j = {}
                            ok, msg = uids_remove(j.get("uid_hex", ""))

                            _json_response(cl, {
                                "ok": bool(ok),
                                "msg": msg,
                                "count": len(ALLOWED_UIDS),
                                "cards": uids_list_cards()
                            })
                            try:
                                cl.close()
                            except:
                                pass

                        elif method == "POST" and path == "/api/uids/set_name":
                            try:
                                j = ujson.loads(body.decode() if body else "{}")
                            except:
                                j = {}
                            ok, msg = uids_set_name(j.get("uid_hex", ""), j.get("name", ""))

                            _json_response(cl, {
                                "ok": bool(ok),
                                "msg": msg,
                                "count": len(ALLOWED_UIDS),
                                "cards": uids_list_cards()
                            })
                            try:
                                cl.close()
                            except:
                                pass

                        elif method == "POST" and path == "/api/uids/clear":
                            ok = uids_clear_all()
                            _json_response(cl, {
                                "ok": bool(ok),
                                "count": len(ALLOWED_UIDS),
                                "cards": uids_list_cards(),
                                "msg": "Cleared" if ok else "Clear failed"
                            })
                            try:
                                cl.close()
                            except:
                                pass

                        else:
                            _http_send(cl, status="404 Not Found", body="Not found")
                            try:
                                cl.close()
                            except:
                                pass

            # ---- Telegram: send "online" once ----
            if TG_ENABLED and tg_ready and tg_esp and (not tg_online_sent):
                now = now_ms()
                if ms_diff(now, tg_last_try_ms) > 10000:
                    tg_last_try_ms = now
                    try:
                        ok = tg_esp.send_text("ESP32 online: {}".format(TG_DEVICE_NAME))
                        tg_online_sent = bool(ok)
                    except Exception as e:
                        if DEBUG_ERRORS:
                            log("TG", "online send fail:", e)

            if TG_ENABLED and tg_ready and tg_esp:
                try:
                    tg_esp.tick(_tg_handle_cmd)
                except Exception:
                    pass

            # ---- NFC read ----
            uid = nfc.read_uid(timeout_ms=NFC_POLL_TIMEOUT_MS)
            if uid:
                op_t0 = time.ticks_ms()
                t = now_ms()

                if uid == last_uid and ms_diff(t, last_time) < 1200:
                    time.sleep_ms(40)
                else:
                    last_uid = uid
                    last_time = t

                    LAST_UID_HEX = uid_bytes_to_hex(uid)
                    LAST_NAME = UID_NAME_BY_HEX.get(LAST_UID_HEX, "") or ""

                    blink(led, times=1, on_ms=70, off_ms=35, color=(0, 0, 60))

                    if uid in ALLOWED_UIDS:
                        LAST_ACCESS = "GRANTED"
                        log("NFC", "UID", LAST_UID_HEX, "NAME", (LAST_NAME or "-"), "-> GRANTED")
                        breathe(led, color=(0, 60, 0), duration_ms=500, steps=18)
                    else:
                        LAST_ACCESS = "DENIED"
                        log("NFC", "UID", LAST_UID_HEX, "NAME", (LAST_NAME or "-"), "-> DENIED")
                        fast_blink(led, color=(60, 0, 0), times=4, on_ms=60, off_ms=60)

                    if TG_ENABLED and tg_ready and TG_NOTIFY_ON_TAP and tg_esp:
                        try:
                            tg_esp.notify_uid(LAST_UID_HEX, LAST_ACCESS, device_name=TG_DEVICE_NAME)
                        except Exception:
                            pass

                    EVENT_ID += 1
                    if sse_client:
                        try:
                            sse_client.send(_sse_event(
                                EVENT_ID, LAST_FW, LAST_UID_HEX, LAST_ACCESS,
                                uids_list_hex(), src="nfc",
                                cards=uids_list_cards(), name=LAST_NAME
                            ).encode())
                        except:
                            try:
                                sse_client.close()
                            except:
                                pass
                            sse_client = None
                            log("SSE", "client disconnected")

                    op_dt = op_ms(op_t0)
                    op_log("NFC_TAP", op_dt, "{} {} {}".format(LAST_ACCESS, LAST_UID_HEX, (LAST_NAME or "-")))

            time.sleep_ms(NFC_LOOP_SLEEP_MS)

        except KeyboardInterrupt:
            log("APP", "Stopped by user")
            try:
                if srv:
                    srv.close()
            except:
                pass
            try:
                if sse_client:
                    sse_client.close()
            except:
                pass
            return

        except Exception as e:
            if DEBUG_ERRORS:
                log("ERR", e)
            time.sleep_ms(120)