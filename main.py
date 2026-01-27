import time
import wifi_prov

print("BOOT: main.py start")

# 1) Connect to known Wi-Fi (wifi.json may contain multiple networks)
ok, info, ssid = wifi_prov.connect_known(timeout_each_s=12)

if ok:
    print("Wi-Fi OK:", ssid, "IP:", info[0])
else:
    print("No known Wi-Fi -> setup portal")
    wifi_prov.provisioning_portal(loop_forever=False)

    ok2, info2, ssid2 = wifi_prov.connect_known(timeout_each_s=15)
    if ok2:
        print("Wi-Fi OK:", ssid2, "IP:", info2[0])
    else:
        print("Wi-Fi still not connected (will continue anyway)")

time.sleep(0.2)

# 2) Start app (single start, no duplicate)
import app
app.run()