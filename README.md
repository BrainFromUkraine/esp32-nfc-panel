# 🔐 ESP32 NFC Panel (PN532)

**ESP32 + PN532 NFC access panel with real-time Web UI (SSE), on-device UID management and Wi‑Fi provisioning portal**

---

## 🚀 Overview

This project is a **fully autonomous NFC access control panel** built on **ESP32 (MicroPython)** and **PN532 (I2C)**.

The device provides:

* real-time **Web UI with live updates (SSE)**
* **local UID database** stored on the device
* **Wi‑Fi provisioning without reflashing**
* **button‑based recovery and setup**
* optional **Telegram notifications & commands**

All configuration and management can be done **directly from the device**, without PC, IDE or serial access.

---

## ✨ Key Features

### 🔑 NFC (PN532)

* Stable PN532 I2C driver
* Robust frame parsing (fixes common **Bad LCS** issues)
* UID debounce & retry logic
* Access decision: **GRANTED / DENIED**
* Visual feedback via WS2812 (NeoPixel)

### 🌐 Web Interface

* Built‑in HTTP server (port `80`)
* **Live updates via Server‑Sent Events (SSE)** (`/events`)
* Manage cards directly from browser:

  * Add UID
  * Remove UID
  * Assign names to cards
  * Add **LAST UID** with one click
* Real‑time access log
* Client‑side history (last 20 events)
* Theme switcher: Light / Dark / Dark Blue

### 📶 Wi‑Fi Provisioning

* Automatic connection to known networks
* Multi‑network support (`wifi.json`)
* **SoftAP setup portal** (`192.168.4.1`)
* No reflashing required to change Wi‑Fi
* AP automatically disabled after successful connection

### 🧠 Button Control (BOOT / GPIO0)

* **7 taps within 30 seconds** → open Wi‑Fi setup portal
* **Hold for 10 seconds** → clear Wi‑Fi config and open portal
* Safe recovery even if Wi‑Fi credentials are broken

### 📲 Telegram Integration (Optional)

* Works fully on ESP32 (no external server)
* Commands:

  * `/last` — show last scanned UID
  * `/add_last` — add last UID to allowed list
* Notifications on every NFC tap
* Automatically disabled if module is not present

---

## 🧩 Hardware

* ESP32 / ESP32‑S3
* PN532 NFC module (I2C)
* WS2812 (NeoPixel) LED
  *(Freenove boards: GPIO48)*
* BOOT button
  *(Freenove boards: GPIO0)*

### 🔌 Wiring (PN532 → ESP32)

| PN532 | ESP32 |
| ----- | ----- |
| SDA   | GPIO9 |
| SCL   | GPIO8 |
| VCC   | 3.3V  |
| GND   | GND   |

---

## 📂 Project Structure

```
.
├── main.py              # Boot logic: Wi‑Fi → portal → app
├── app.py               # Main application loop
├── wifi_prov.py         # Wi‑Fi provisioning & SoftAP portal
├── ui_html.py           # Web UI (HTML/CSS/JS)
├── pn532.py             # Robust PN532 I2C driver
├── tg_esp.py            # Telegram integration (optional)
├── config.example.py    # Example config (no secrets)
├── wifi.example.json    # Wi‑Fi config example
├── uids.example.json    # UID database example
├── README.md
└── LICENSE
```

---

## 📄 Configuration Files

### `wifi.json`

```json
{
  "networks": [
    { "ssid": "HomeWiFi", "password": "password" }
  ],
  "last_ssid": "HomeWiFi"
}
```

### `uids.json`

```json
{
  "cards": [
    { "uid": "15 D6 14 06", "name": "Master card" }
  ]
}
```

⚠️ **`wifi.json`, `uids.json` and `config.py` must NOT be committed.**

---

## 🌍 Web API Endpoints

| Method | Endpoint             | Description          |
| ------ | -------------------- | -------------------- |
| GET    | `/`                  | Web UI               |
| GET    | `/events`            | SSE live updates     |
| POST   | `/api/uids/list`     | List all cards       |
| POST   | `/api/uids/add`      | Add UID              |
| POST   | `/api/uids/add_last` | Add last scanned UID |
| POST   | `/api/uids/remove`   | Remove UID           |
| POST   | `/api/uids/set_name` | Set card name        |
| POST   | `/api/uids/clear`    | Clear all cards      |

---

## 🛡️ Security Notes

* No cloud dependency
* All data stored locally on device
* Secrets are kept outside repository
* Safe recovery via hardware button

---

## 🧪 Tested With

* MicroPython v1.27+
* ESP32 / ESP32‑S3
* PN532 (HW‑147C and compatible)
* Chrome / Firefox / Mobile browsers

---

## 📜 License

MIT License
Free to use, modify and integrate into commercial projects.

---

## ⭐ Why This Project

This is not a demo or toy project.

It is a **real‑world, deployable NFC access controller** designed for:

* workshops
* offices
* labs
* makerspaces
* IoT access systems

Built to be **stable, autonomous and serviceable without a PC**.
