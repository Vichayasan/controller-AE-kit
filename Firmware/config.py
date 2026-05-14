# config.py - PIN and hardware constants
#
# Hardware:
# - Controller: Cytron MOTION 2350 Pro / RP2350
# - Peripheral: MKS MINI12864 V3 on shared SPI
#
# MKS MINI12864 V3 has an ST7567 LCD and onboard SD slot on the same SPI bus.
# The LCD and SD card must never have CS low at the same time.

PIN_NEOPIXEL    = 4
PIN_BEEPER      = 0
PIN_ENC_A       = 5
PIN_ENC_B       = 6
PIN_ENC_BTN     = 7

PIN_LCD_CS      = 2
PIN_LCD_DC      = 3
PIN_LCD_RST     = 1

# Shared SPI0 wiring from MOTION 2350 Pro GPIO header to MKS MINI12864 V3.
PIN_SPI_SCK     = 18
PIN_SPI_MOSI    = 19
PIN_SPI_MISO    = 16
PIN_SD_CS       = 17

PIN_AE_SENSOR02_ADC = 27
PIN_AE_SENSOR01_ADC = 26
PIN_RTC_SDA     = 28
PIN_RTC_SCL     = 29

LCD_BAUD = 2000000
SD_BAUD  = 25000
LCD_SPI_POLARITY = 1
LCD_SPI_PHASE    = 1
SD_SPI_POLARITY  = 1
SD_SPI_PHASE     = 1
SD_PARTITION_LBA = 32
SD_BOOT_DELAY_MS = 3000
SD_MOUNT_RETRIES = 5
SD_RETRY_DELAY_MS = 700
SD_CMD9_RETRIES = 5
SD_FRAME_HOLD_MS = 2500
SD_STATUS_CHECK_MS = 5000
SD_FULL_PERCENT = 1
DONE_HOLD_MS = 1200
AE_LOG_INTERVAL_MS = 1000
AE_LOG_FILE = "/sd/ae_record.csv"
VREF     = 3.3
