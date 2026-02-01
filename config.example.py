# Rename to config.py (this file must NOT be committed)

TG_ENABLED = False
TG_BOT_TOKEN = ""
TG_ADMIN_CHAT_ID = 0
TG_DEVICE_NAME = "ESP32-NFC-1"
TG_POLL_EVERY_MS = 2500
TG_NOTIFY_ON_TAP = True

AP_PASS = "12345678"

# HTTP Basic Auth for Web UI (optional)
# Add these to your .env file to enable authentication:
# UI_AUTH_ENABLED=True
# UI_USER=admin
# UI_PASS=yourpassword
# 
# When enabled, browser will prompt for username/password before loading UI.
# Protects: GET /, GET /events, POST /api/uids/list
# Write endpoints remain protected by ADMIN_TOKEN as before.
