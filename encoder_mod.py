# encoder_mod.py - Rotary encoder with debounce

from machine import Pin
import time
import config

enc_a = Pin(config.PIN_ENC_A, Pin.IN, Pin.PULL_UP)
enc_b = Pin(config.PIN_ENC_B, Pin.IN, Pin.PULL_UP)
btn   = Pin(config.PIN_ENC_BTN, Pin.IN, Pin.PULL_UP)

TRANS = {
    (0, 1): +1, (1, 3): +1, (3, 2): +1, (2, 0): +1,
    (0, 2): -1, (2, 3): -1, (3, 1): -1, (1, 0): -1,
}

STEPS_PER_CLICK = 4
DEBOUNCE_MS     = 30
LONG_MS         = 700
ENC_IGNORE_MS   = 150

_last_state      = (enc_a.value() << 1) | enc_b.value()
_enc_accum       = 0
_last_btn        = btn.value()
_last_btn_t      = time.ticks_ms()
_press_t         = 0
_back_latched    = False
_enc_ignore_until = 0

delta_accum = 0   # +1 or -1 per click, read and clear in main
btn_pressed = False
btn_long    = False

def update():
    global _last_state, _enc_accum, delta_accum
    global _last_btn, _last_btn_t, _press_t, _back_latched
    global _enc_ignore_until, btn_pressed, btn_long

    now = time.ticks_ms()

    # encoder
    if btn.value() == 1 and time.ticks_diff(now, _enc_ignore_until) >= 0:
        s = (enc_a.value() << 1) | enc_b.value()
        if s != _last_state:
            d = TRANS.get((_last_state, s), 0)
            _last_state = s
            if d:
                _enc_accum += d
                if _enc_accum >= STEPS_PER_CLICK:
                    _enc_accum = 0
                    delta_accum += 1
                elif _enc_accum <= -STEPS_PER_CLICK:
                    _enc_accum = 0
                    delta_accum -= 1

    # button
    b = btn.value()
    if b != _last_btn and time.ticks_diff(now, _last_btn_t) > DEBOUNCE_MS:
        _last_btn = b
        _last_btn_t = now
        if b == 0:
            _press_t = now
            _back_latched = False
            _enc_ignore_until = time.ticks_add(now, ENC_IGNORE_MS)
            btn_pressed = True
        else:
            if not _back_latched:
                btn_pressed = True

    # long press
    if btn.value() == 0 and not _back_latched:
        if time.ticks_diff(now, _press_t) >= LONG_MS:
            _back_latched = True
            btn_long = True

def pop_delta():
    global delta_accum
    d = delta_accum
    delta_accum = 0
    return d

def pop_pressed():
    global btn_pressed
    p = btn_pressed
    btn_pressed = False
    return p

def pop_long():
    global btn_long
    l = btn_long
    btn_long = False
    return l