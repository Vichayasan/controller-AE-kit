# rtc_mod.py - DS3231 RTC

from machine import I2C, Pin
import config

try:
    from DS3231 import DS3231
except Exception:
    DS3231 = None

rtc_i2c = None
rtc_obj  = None
rtc_ok   = False
rtc_status_text = "RTC not init"

def rtc_init():
    global rtc_i2c, rtc_obj, rtc_ok, rtc_status_text

    rtc_ok  = False
    rtc_obj = None
    rtc_status_text = "RTC init fail"

    try:
        rtc_i2c = I2C(0,
            sda=Pin(config.PIN_RTC_SDA),
            scl=Pin(config.PIN_RTC_SCL),
            freq=100000
        )
    except Exception as e:
        rtc_status_text = "I2C fail"
        print("[rtc] i2c init failed:", repr(e))
        return False

    try:
        addrs = rtc_i2c.scan()
        if 0x68 not in addrs:
            rtc_status_text = "0x68 not found"
            print("[rtc] scan:", addrs)
            return False
    except Exception as e:
        rtc_status_text = "RTC scan fail"
        print("[rtc] scan failed:", repr(e))
        return False

    if DS3231 is None:
        rtc_status_text = "DS3231.py missing"
        print("[rtc] DS3231 library not found")
        return False

    for attempt in (lambda: DS3231(rtc_i2c), lambda: DS3231(rtc_i2c, 0x68)):
        try:
            rtc_obj = attempt()
            break
        except Exception:
            rtc_obj = None

    if rtc_obj is None:
        rtc_status_text = "RTC object fail"
        print("[rtc] could not create DS3231 object")
        return False

    try:
        _ = get_datetime()
        rtc_ok = True
        rtc_status_text = "RTC OK"
        return True
    except Exception as e:
        rtc_status_text = "RTC read fail"
        print("[rtc] read failed:", repr(e))
        rtc_obj = None
        return False

def get_datetime():
    if rtc_obj is None:
        raise RuntimeError("rtc_obj is None")
    for attr in ("datetime", "DateTime"):
        if hasattr(rtc_obj, attr):
            t = getattr(rtc_obj, attr)()
            if isinstance(t, tuple) and len(t) >= 7:
                return t
    raise RuntimeError("Unsupported RTC API")

def time_string():
    try:
        t = get_datetime()
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            t[0], t[1], t[2], t[4], t[5], t[6]
        )
    except Exception:
        return "RTC_READ_FAIL"

def time_hms():
    try:
        t = get_datetime()
        return "{:02d}:{:02d}:{:02d}".format(t[4], t[5], t[6])
    except Exception:
        return "--:--:--"

def set_datetime(year, month, day, hour, minute, second):
    global rtc_ok, rtc_status_text
    if rtc_obj is None:
        rtc_status_text = "RTC not ready"
        return False
    try:
        # DS3231 weekday is accepted as 1..7 by the local driver.
        rtc_obj.datetime((year, month, day, 1, hour, minute, second, 0))
        rtc_ok = True
        rtc_status_text = "RTC OK"
        return True
    except Exception as e:
        rtc_status_text = "RTC set fail"
        print("[rtc] set failed:", repr(e))
        return False
