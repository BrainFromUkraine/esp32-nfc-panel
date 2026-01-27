import time

PN532_I2C_ADDR = 0x24

# PN532 frame constants
_PN532_HOSTTOPN532 = 0xD4
_PN532_PN532TOHOST = 0xD5

_CMD_GETFIRMWAREVERSION  = 0x02
_CMD_SAMCONFIGURATION    = 0x14
_CMD_INLISTPASSIVETARGET = 0x4A


class PN532_I2C:
    def __init__(self, i2c, addr=PN532_I2C_ADDR):
        self.i2c = i2c
        self.addr = addr

    # ----------------- low level helpers -----------------

    def _checksum(self, data):
        return (~sum(data) + 1) & 0xFF

    def _write_frame(self, data):
        # Build PN532 frame: 00 00 FF LEN LCS [DATA...] DCS 00
        length = len(data)
        lcs = (~length + 1) & 0xFF
        dcs = self._checksum(data)

        frame = bytearray([0x00, 0x00, 0xFF, length, lcs])
        frame.extend(data)
        frame.append(dcs)
        frame.append(0x00)

        # I2C write uses leading 0x00
        self.i2c.writeto(self.addr, b"\x00" + frame)

    def _wait_ready(self, timeout_ms=1000):
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            # status byte: 0x01 = ready
            try:
                s = self.i2c.readfrom(self.addr, 1)[0]
            except Exception:
                s = 0x00
            if s == 0x01:
                return True
            time.sleep_ms(10)
        return False

    def _try_parse_from_32(self, raw):
        """
        raw: bytes from i2c.readfrom(addr, 32)
        format: [STATUS][...stream...]
        STATUS should be 0x01.
        We search 00 00 FF, then validate LEN/LCS and DCS.
        Return payload (without TFI), or None if not valid.
        """
        if len(raw) < 12 or raw[0] != 0x01:
            return None

        buf = raw[1:]  # strip status

        # Quick ignore: junk stream often starts with 0x80
        if len(buf) and buf[0] == 0x80:
            return None

        # Find header 00 00 FF
        idx = -1
        for i in range(0, len(buf) - 2):
            if buf[i] == 0x00 and buf[i+1] == 0x00 and buf[i+2] == 0xFF:
                idx = i
                break
        if idx < 0:
            return None

        buf = buf[idx:]
        if len(buf) < 8:
            return None

        length = buf[3]
        lcs = buf[4]

        # Validate LCS: LEN + LCS == 0x00 (mod 256)
        if ((length + lcs) & 0xFF) != 0x00:
            return None

        frame_start = 5
        frame_end = frame_start + length  # includes TFI + payload
        if len(buf) < frame_end + 2:
            return None

        data = buf[frame_start:frame_end]  # TFI + payload
        dcs = buf[frame_end]
        post = buf[frame_end + 1]

        if post != 0x00:
            return None

        # Validate DCS: sum(data) + dcs == 0 (mod 256)
        if ((sum(data) + dcs) & 0xFF) != 0x00:
            return None

        # Validate TFI
        if not data or data[0] != _PN532_PN532TOHOST:
            return None

        return data[1:]  # payload only (starts with response code)

    def _read_frame(self, timeout_ms=1000):
        if not self._wait_ready(timeout_ms):
            raise RuntimeError("PN532 not ready (read)")

        # Read ONLY small chunks, with retries.
        # Your module sometimes returns 0x80 garbage on larger reads.
        for _ in range(12):
            raw = self.i2c.readfrom(self.addr, 32)
            payload = self._try_parse_from_32(raw)
            if payload is not None:
                return payload

            # second chunk right away
            raw2 = self.i2c.readfrom(self.addr, 32)
            payload2 = self._try_parse_from_32(raw2)
            if payload2 is not None:
                return payload2

            time.sleep_ms(20)

        raise RuntimeError("Bad LCS (no valid frame after retries)")

    def _command(self, cmd, params=b"", timeout_ms=1000):
        data = bytearray([_PN532_HOSTTOPN532, cmd])
        data.extend(params)

        self._write_frame(data)
        resp = self._read_frame(timeout_ms)

        # First byte in payload must be cmd+1 (response code)
        if not resp or resp[0] != (cmd + 1):
            raise RuntimeError("Unexpected response code")
        return resp[1:]  # response data

    # ----------------- high level API -----------------

    def get_firmware_version(self):
        r = self._command(_CMD_GETFIRMWAREVERSION, b"", 1500)
        if len(r) < 4:
            return None
        return (r[0] << 24) | (r[1] << 16) | (r[2] << 8) | r[3]

    def sam_config(self):
        # mode=0x01 (normal), timeout=0x14, use_irq=0x01
        self._command(_CMD_SAMCONFIGURATION, bytes([0x01, 0x14, 0x01]), 1500)
        time.sleep_ms(50)

    def read_uid(self, timeout_ms=2000):
        """
        Returns UID bytes or None.
        Doesn't crash on occasional garbage reads.
        """

        # Flush a bit of garbage from buffer (HW-147C often does this)
        try:
            self.i2c.readfrom(self.addr, 32)
            self.i2c.readfrom(self.addr, 32)
        except Exception:
            pass

        for _ in range(3):
            try:
                r = self._command(_CMD_INLISTPASSIVETARGET, bytes([0x01, 0x00]), timeout_ms)

                # Expected: NbTg, Tg, SensRes1, SensRes2, SelRes, UIDLen, UID...
                if len(r) >= 7 and r[0] == 0x01:
                    uid_len = r[5]
                    return r[6:6 + uid_len]

                return None

            except Exception:
                time.sleep_ms(120)

        return None
