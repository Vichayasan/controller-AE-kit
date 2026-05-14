# beeper_mod.py - Non-blocking PWM beeper

from machine import PWM, Pin
import time
import config

bz = PWM(Pin(config.PIN_BEEPER, Pin.OUT))
bz.duty_u16(0)

BEEP_DUTY  = 22000
PRESS_DUTY = 35000

_beep_until = 0
_beep_active = False
_enabled = True

def beep_start(freq=900, ms=60, duty=BEEP_DUTY):
    global _beep_until, _beep_active
    if not _enabled:
        bz.duty_u16(0)
        _beep_active = False
        return
    bz.freq(freq)
    bz.duty_u16(min(max(duty, 0), 65535))
    _beep_until = time.ticks_add(time.ticks_ms(), ms)
    _beep_active = True

def beep_update():
    global _beep_active
    if _beep_active and time.ticks_diff(time.ticks_ms(), _beep_until) >= 0:
        bz.duty_u16(0)
        _beep_active = False

def set_enabled(enabled):
    global _enabled, _beep_active
    _enabled = bool(enabled)
    if not _enabled:
        bz.duty_u16(0)
        _beep_active = False

def is_enabled():
    return _enabled
