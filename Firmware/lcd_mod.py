# lcd_mod.py - LCD ST7567 + SPI management

from machine import SPI, Pin
from ST7567driver import ST7567
import config

spi = SPI(
    0,
    baudrate=config.LCD_BAUD,
    polarity=config.LCD_SPI_POLARITY,
    phase=config.LCD_SPI_PHASE,
    sck=Pin(config.PIN_SPI_SCK),
    mosi=Pin(config.PIN_SPI_MOSI),
    miso=Pin(config.PIN_SPI_MISO),
)

lcd_cs_pin  = Pin(config.PIN_LCD_CS,  Pin.OUT, value=1)
lcd_dc_pin  = Pin(config.PIN_LCD_DC,  Pin.OUT, value=0)
lcd_rst_pin = Pin(config.PIN_LCD_RST, Pin.OUT, value=1)
sd_cs_pin   = Pin(config.PIN_SD_CS,   Pin.OUT, value=1)

lcd = None

def spi_to_lcd_speed():
    sd_cs_pin.value(1)
    lcd_cs_pin.value(1)
    spi.init(
        baudrate=config.LCD_BAUD,
        polarity=config.LCD_SPI_POLARITY,
        phase=config.LCD_SPI_PHASE,
    )

def spi_to_sd_speed():
    lcd_cs_pin.value(1)
    sd_cs_pin.value(1)
    spi.init(
        baudrate=config.SD_BAUD,
        polarity=config.SD_SPI_POLARITY,
        phase=config.SD_SPI_PHASE,
    )

def lcd_create():
    global lcd
    spi_to_lcd_speed()
    lcd_rst_pin.value(1)
    lcd_cs_pin.value(1)
    lcd = ST7567(
        spi,
        a0=lcd_dc_pin,
        cs=lcd_cs_pin,
        rst=lcd_rst_pin,
        elecvolt=0x30,
        regratio=0x03,
        invX=False,
        invY=True,
        invdisp=False,
    )

def lcd_update():
    if lcd is not None:
        lcd.show()

def pixel(x, y, c=1):
    if lcd is not None:
        lcd.pixel(x, y, c)

def fill_rect(x, y, w, h, c=0):
    if lcd is not None:
        lcd.fill_rect(x, y, w, h, c)

# init on import
lcd_create()
