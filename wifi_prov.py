# wifi_prov.py
import network, socket, time, ubinascii, ujson

CFG_FILE = "wifi.json"

AP_SSID_PREFIX = "ESP32-SETUP"
AP_PASS = "12345678"  # мін 8 символів

AP_IP = "192.168.4.1"
AP_MASK = "255.255.255.0"
AP_GW = "192.168.4.1"
AP_DNS = "8.8.8.8"


def _html_escape(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# -----------------------
# CFG (multiple networks)
# Structure:
# {
#   "networks": [{"ssid":"AlaNet","password":"..."}, ...],
#   "last_ssid": "AlaNet"
# }
# -----------------------
def load_cfg():
    try:
        with open(CFG_FILE, "r") as f:
            cfg = ujson.load(f)
            if not isinstance(cfg, dict):
                return {"networks": [], "last_ssid": ""}
            if "networks" not in cfg or not isinstance(cfg["networks"], list):
                cfg["networks"] = []
            if "last_ssid" not in cfg:
                cfg["last_ssid"] = ""
            return cfg
    except:
        return {"networks": [], "last_ssid": ""}


def save_cfg(cfg):
    with open(CFG_FILE, "w") as f:
        ujson.dump(cfg, f)


def clear_cfg():
    try:
        import os
        os.remove(CFG_FILE)
        return True
    except:
        return False


def upsert_network(ssid, pwd):
    cfg = load_cfg()
    nets = cfg.get("networks", [])
    for n in nets:
        if n.get("ssid") == ssid:
            n["password"] = pwd
            cfg["last_ssid"] = ssid
            save_cfg(cfg)
            return
    nets.append({"ssid": ssid, "password": pwd})
    cfg["networks"] = nets
    cfg["last_ssid"] = ssid
    save_cfg(cfg)


def connect_sta(ssid, password, timeout_s=20):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # якщо вже підключений до цього SSID — повертаємо одразу
    try:
        if wlan.isconnected() and wlan.config("essid") == ssid:
            return True, wlan.ifconfig()
    except:
        pass

    try:
        wlan.connect(ssid, password)
    except:
        # інколи корисно зробити disconnect і повторити
        try:
            wlan.disconnect()
            time.sleep(0.2)
            wlan.connect(ssid, password)
        except:
            return False, None

    t0 = time.time()
    while not wlan.isconnected():
        if time.time() - t0 > timeout_s:
            return False, None
        time.sleep(0.3)

    return True, wlan.ifconfig()


def connect_known(timeout_each_s=10):
    """
    Try to connect to known networks.
    1) try last_ssid first
    2) then others
    """
    cfg = load_cfg()
    nets = cfg.get("networks", [])
    if not nets:
        return False, None, None

    last = cfg.get("last_ssid", "")
    ordered = []
    if last:
        for n in nets:
            if n.get("ssid") == last:
                ordered.append(n)
        for n in nets:
            if n.get("ssid") != last:
                ordered.append(n)
    else:
        ordered = nets

    for n in ordered:
        ssid = n.get("ssid", "")
        pwd = n.get("password", "")
        if not ssid:
            continue
        ok, info = connect_sta(ssid, pwd, timeout_s=timeout_each_s)
        if ok:
            return True, info, ssid

    return False, None, None


# -----------------------
# AP + Portal
# -----------------------
def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)

    # ✅ ЯВНО задаємо IP, щоб телефон завжди відкривав 192.168.4.1
    try:
        ap.ifconfig((AP_IP, AP_MASK, AP_GW, AP_DNS))
    except:
        pass

    mac = ubinascii.hexlify(ap.config("mac")[-3:]).decode().upper()
    ssid = "{}-{}".format(AP_SSID_PREFIX, mac)

    try:
        ap.config(essid=ssid, password=AP_PASS, authmode=network.AUTH_WPA_WPA2_PSK)
    except:
        # fallback без authmode
        ap.config(essid=ssid, password=AP_PASS)

    return ap, ssid


def scan_networks():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep(0.2)
    nets = []
    try:
        for n in wlan.scan():
            ssid = n[0].decode() if isinstance(n[0], (bytes, bytearray)) else str(n[0])
            rssi = n[3]
            auth = n[4]
            nets.append((ssid, rssi, auth))
    except:
        pass
    nets = [x for x in nets if x[0]]
    nets.sort(key=lambda x: x[1], reverse=True)
    return nets


def _build_page(msg="", ipinfo=""):
    nets = scan_networks()
    options = "\n".join([
        '<option value="{}">{} (RSSI {})</option>'.format(_html_escape(s), _html_escape(s), r)
        for s, r, _ in nets
    ])

    return """HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Connection: close

<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>ESP32 Wi-Fi Setup</title>
  <style>
    body {{ font-family: Arial; margin: 18px; }}
    .box {{ max-width: 480px; padding: 14px; border: 1px solid #ddd; border-radius: 10px; }}
    label {{ display:block; margin-top:10px; }}
    input, select {{ width:100%; padding:10px; font-size:16px; }}
    button {{ margin-top:12px; padding:12px; width:100%; font-size:16px; }}
    .msg {{ margin-top:10px; color:#0a0; }}
    .ip {{ margin-top:10px; color:#333; }}
  </style>
</head>
<body>
  <div class="box">
    <h2>Wi-Fi Setup</h2>
    <p>Оберіть мережу, введіть пароль і натисніть Connect. Мережа буде ДОДАНА/ОНОВЛЕНА у wifi.json.</p>

    {ipblock}
    {msgblock}

    <form method="POST" action="/connect">
      <label>Network (SSID)</label>
      <select name="ssid" required>
        {options}
      </select>

      <label>Password</label>
      <input name="password" type="password" placeholder="Wi-Fi password" />

      <button type="submit">Connect</button>
    </form>

    <form method="GET" action="/rescan">
      <button type="submit">Rescan</button>
    </form>

    <p style="margin-top:12px;font-size:13px;color:#777;">
      Порада: 7x BOOT → відкрити цей портал. 10s BOOT → очистити всі мережі.
    </p>
  </div>
</body>
</html>
""".format(
        options=options,
        ipblock=("<div class='ip'><b>{}</b></div>".format(_html_escape(ipinfo)) if ipinfo else ""),
        msgblock=("<div class='msg'>{}</div>".format(_html_escape(msg)) if msg else "")
    )


def _parse_form(body_bytes):
    try:
        body = body_bytes.decode()
    except:
        return "", ""

    ssid = ""
    pwd = ""
    for part in body.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            v = v.replace("+", " ")

            out = []
            i = 0
            while i < len(v):
                if v[i] == "%" and i + 2 < len(v):
                    try:
                        out.append(chr(int(v[i+1:i+3], 16)))
                        i += 3
                        continue
                    except:
                        pass
                out.append(v[i])
                i += 1
            v = "".join(out)

            if k == "ssid":
                ssid = v
            elif k == "password":
                pwd = v
    return ssid, pwd


def _read_full_request(cl, max_total=4096):
    """
    Read headers + body (Content-Length) safely.
    """
    cl.settimeout(2.0)
    data = b""
    try:
        data = cl.recv(2048)
    except:
        return b""

    if not data:
        return b""

    # wait for header end
    t0 = time.ticks_ms()
    while (b"\r\n\r\n" not in data) and (time.ticks_diff(time.ticks_ms(), t0) < 300):
        try:
            more = cl.recv(1024)
            if not more:
                break
            data += more
            if len(data) >= max_total:
                break
        except:
            break

    # read extra body if content-length says so
    try:
        head, body = data.split(b"\r\n\r\n", 1)
    except:
        return data

    headers = head.split(b"\r\n")[1:]
    cl_len = 0
    for h in headers:
        if h.lower().startswith(b"content-length:"):
            try:
                cl_len = int(h.split(b":", 1)[1].strip())
            except:
                cl_len = 0
            break

    need = cl_len - len(body)
    while need > 0 and len(data) < max_total:
        try:
            chunk = cl.recv(min(1024, need))
        except:
            break
        if not chunk:
            break
        data += chunk
        need -= len(chunk)

    return data


def provisioning_portal(loop_forever=True):
    ap, ap_ssid = start_ap()
    print("AP started:", ap_ssid, "pass:", AP_PASS)
    print("Open in phone browser:", "http://" + AP_IP)

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(2)

    while True:
        cl, _ = s.accept()
        try:
            req = _read_full_request(cl)
            if not req:
                try:
                    cl.close()
                except:
                    pass
                continue

            first = req.split(b"\r\n", 1)[0]
            parts = first.split()
            method = parts[0].decode() if len(parts) > 0 else "GET"
            path = parts[1].decode() if len(parts) > 1 else "/"

            if method == "GET" and (path == "/" or path.startswith("/rescan")):
                cl.send(_build_page().encode())
                cl.close()
                continue

            if method == "POST" and path.startswith("/connect"):
                body = req.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in req else b""
                ssid, pwd = _parse_form(body)

                if not ssid:
                    cl.send(_build_page(msg="SSID is empty").encode())
                    cl.close()
                    continue

                cl.send(_build_page(msg="Connecting... please wait").encode())
                cl.close()

                ok, info = connect_sta(ssid, pwd, timeout_s=25)
                if ok:
                    upsert_network(ssid, pwd)
                    ip = info[0]
                    print("Connected to", ssid, "IP:", ip)

                    # ✅ FIX: звільнити порт 80 і вимкнути AP
                    try:
                        s.close()
                    except:
                        pass

                    try:
                        ap.active(False)
                    except:
                        pass

                    try:
                        network.WLAN(network.AP_IF).active(False)
                    except:
                        pass

                    if not loop_forever:
                        return True, ip
                else:
                    print("Failed to connect to", ssid)
                continue

            cl.send(_build_page().encode())
            cl.close()

        except Exception as e:
            try:
                cl.close()
            except:
                pass
            print("HTTP error:", e)