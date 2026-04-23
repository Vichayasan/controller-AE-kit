# neopixel_mod.py - NeoPixel LED

from machine import Pin
import config

try:
    import neopixel
    NPIX = 3
    np = neopixel.NeoPixel(Pin(config.PIN_NEOPIXEL, Pin.OUT), NPIX)

    def leds_rgb(r, g, b):
        for i in range(NPIX):
            np[i] = (g, r, b)  # GRB order
        np.write()

except ImportError:
    def leds_rgb(r, g, b):
        pass

LED_G  = 80
led_on = True
leds_rgb(0, LED_G, 0)

def toggle():
    global led_on
    led_on = not led_on
    leds_rgb(0, LED_G if led_on else 0, 0)
    