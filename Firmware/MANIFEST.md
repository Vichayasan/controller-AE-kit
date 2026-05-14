# Firmware File Manifest

## Board Files

- `main.py` - main app and firmware flow
- `config.py` - pin map and hardware constants
- `lcd_mod.py` - ST7567 LCD and shared SPI management
- `ST7567driver.py` - LCD driver
- `sd_utils.py` - SD card SPI driver, mount, format, retry handling
- `rtc_mod.py` - RTC wrapper
- `DS3231.py` - DS3231 library
- `encoder_mod.py` - rotary encoder and button input
- `beeper_mod.py` - PWM beeper with ON/OFF control
- `neopixel_mod.py` - NeoPixel ON/OFF control
- `preamp_mod.py` - AE sensor sampling and waveform drawing
- `logo_mod.py` - startup logo rendering

## Documentation / Assets

- `firmware_flow_chart.png` - system firmware flow chart
- `assets/logo.png` - source logo image
- `assets/logo.c` - source RGB565 logo conversion

## Generated / Excluded

Do not commit local board pull-back files such as:

- `com18_uploaded_*.py`
- `__pycache__/`
- editor or virtual environment folders
