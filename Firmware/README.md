# REPCO AE Recorder Firmware

MicroPython firmware for an RP2350 controller with an MKS MINI12864 V3 display/SD peripheral.

## Hardware

- Controller: Cytron MOTION 2350 Pro / RP2350
- Display/SD peripheral: MKS MINI12864 V3
- RTC: DS3231
- AE analog inputs:
  - Ambient: GPIO26 / ADC0
  - Machine: GPIO27 / ADC1

## Boot Flow

1. Show startup logo silently.
2. Set up SD card with 5 retry attempts.
3. If SD setup fails, choose `Restart` or `Format SD`.
4. Show date/time setup using DS3231.
5. Show `AE is Recording`.
6. Enter main menu and log AE data to CSV.

## CSV Log

Default log file:

```text
/sd/ae_record.csv
```

CSV columns:

```text
timestamp_machine,raw_machine,volt_machine,timestamp_ambient,raw_ambient,volt_ambient
```

## Upload To Board

Copy all `.py` files in this folder to the MicroPython board root.

The boot file is:

```text
main.py
```

## Notes

- LCD and SD card share SPI. The firmware switches chip-select and SPI speed before each operation.
- Logo and SD setup screens are silent.
- Encoder rotation/press sounds can be toggled in the Setting menu.
- SD card status is shown as `OK`, `FAIL`, or `FULL`.
