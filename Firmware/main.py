# main.py - Main loop only

import time
try:
    from enum import Enum
except ImportError:
    class Enum:
        pass
import micropython
micropython.alloc_emergency_exception_buf(200)
import os
import machine

import config
import lcd_mod    as LCD
import rtc_mod    as RTC
import beeper_mod as BEEPER
import encoder_mod as ENC
import neopixel_mod as NEO
import preamp_mod as PREAMP
import logo_mod   as LOGO

class Mode(Enum):
    MENU = 1
    SETTING = 2
    SENSOR = 3

class App:
    AE_LOG_INTERVAL_MS = getattr(config, "AE_LOG_INTERVAL_MS", 1000)
    AE_LOG_FILE = getattr(config, "AE_LOG_FILE", "/sd/ae_record.csv")
    SD_STATUS_CHECK_MS = getattr(config, "SD_STATUS_CHECK_MS", 5000)
    SD_FULL_PERCENT = getattr(config, "SD_FULL_PERCENT", 1)

    def __init__(self):
        # -- hardware and module setup --
        RTC.rtc_init()
        LOGO.show(LCD.lcd, LCD.lcd_update, 2500)
        self.sd_status = "FAIL"
        self.fs_ok = self.show_sd_free_space(restart_on_fail=True)
        self.sd_full_latched = self.sd_status == "FULL"
        self.sd_popup_until = 0
        self.last_sd_check_t = time.ticks_ms()
        self.show_datetime_setup()
        self.recording_ok = False
        self.last_log_t = time.ticks_ms()

        # -- sensor mapping --
        self.SENSOR_MAP = {
            'Ambient': 'AE01',
            'Machine': 'AE02'
        }

        # -- menu page state --
        self.menu = ['Ambient', 'Machine', 'Setting']
        self.menu_sel = 0
        self.menu_top = 0
        self.VISIBLE_MENU_ITEMS = 3

        # -- setting page state --
        self.setting = ['Sound', 'Bright', 'SD Card', 'Date&Time']
        self.setting_sel = 0
        self.setting_top = 0
        self.VISIBLE_SETTING_ITEMS = 5

        # -- application state --
        self.mode = Mode.MENU
        self.page = 0
        self.active_sensor = None

        self.start_ae_recording()
        self.draw_menu()

    def show_datetime_setup(self):
        try:
            RTC.rtc_init()
        except Exception as e:
            print("Date/time setup error:", e)

        values = [2026, 1, 1, 0, 0, 0]
        if getattr(RTC, "rtc_ok", False):
            try:
                t = RTC.get_datetime()
                values = [t[0], t[1], t[2], t[4], t[5], t[6]]
            except Exception as e:
                print("RTC read for setup failed:", e)

        labels = ("Y", "M", "D", "h", "m", "s")
        mins = (2000, 1, 1, 0, 0, 0)
        maxs = (2099, 12, 31, 23, 59, 59)
        sel = 0
        editing = False
        edit_field = 0
        dirty = True
        last_draw = 0

        while True:
            try:
                BEEPER.beep_update()
                ENC.update()

                d = ENC.pop_delta()
                if d:
                    if editing:
                        values[edit_field] += d
                        if values[edit_field] < mins[edit_field]:
                            values[edit_field] = maxs[edit_field]
                        elif values[edit_field] > maxs[edit_field]:
                            values[edit_field] = mins[edit_field]
                        BEEPER.beep_start(3200, 40)
                    else:
                        sel = (sel + d) % 3
                        BEEPER.beep_start(3200, 40)
                    dirty = True

                if ENC.pop_pressed():
                    if editing:
                        if edit_field in (2, 5):
                            editing = False
                        else:
                            edit_field += 1
                        BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                    elif sel == 0:
                        editing = True
                        edit_field = 0
                        BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                    elif sel == 1:
                        editing = True
                        edit_field = 3
                        BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                    else:
                        if RTC.set_datetime(values[0], values[1], values[2], values[3], values[4], values[5]):
                            self.draw_sd_status("DATE TIME SAVED", "DONE")
                        else:
                            self.draw_sd_status("RTC SET FAIL", getattr(RTC, "rtc_status_text", ""))
                        time.sleep_ms(config.DONE_HOLD_MS)
                        break
                    dirty = True

                now = time.ticks_ms()
                if dirty or time.ticks_diff(now, last_draw) >= 300:
                    LCD.spi_to_lcd_speed()
                    LCD.lcd.fill(0)
                    LCD.lcd.text("DATE TIME SETUP", 0, 0)
                    LCD.lcd.text("----------------", 0, 10)

                    date_text = "{:04d}-{:02d}-{:02d}".format(values[0], values[1], values[2])
                    time_text = "{:02d}:{:02d}:{:02d}".format(values[3], values[4], values[5])
                    LCD.lcd.text((">" if sel == 0 else " ") + date_text, 0, 22)
                    LCD.lcd.text((">" if sel == 1 else " ") + time_text, 0, 34)

                    if editing:
                        LCD.lcd.text("EDIT {} {}".format(labels[edit_field], values[edit_field])[:16], 0, 52)
                    else:
                        LCD.lcd.text((">" if sel == 2 else " ") + "DONE", 0, 52)
                    LCD.lcd_update()
                    last_draw = now
                    dirty = False
                time.sleep_ms(10)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print("Date/time setup loop error:", e)
                break

    def show_sd_free_space(self, restart_on_fail=True):
        ok = False
        mounted = False
        text = "SD: FAIL"
        detail = ""
        self.sd_status = "FAIL"

        try:
            import sd_utils
            self.draw_sd_status("SD SETUP", "PLEASE WAIT")
            time.sleep_ms(config.SD_BOOT_DELAY_MS)
            for attempt in range(config.SD_MOUNT_RETRIES):
                if sd_utils.mount_sd(LCD.spi):
                    mounted = True
                    s = os.statvfs("/sd")
                    free_kb = (s[0] * s[3]) // 1024
                    total_kb = (s[0] * s[2]) // 1024
                    if total_kb > 0:
                        percent = (free_kb * 100) // total_kb
                        if percent <= self.SD_FULL_PERCENT:
                            text = "SD CARD FULL"
                            detail = "FREE: {}%".format(percent)
                            self.sd_status = "FULL"
                        else:
                            text = "SD CARD OK"
                            detail = "FREE: {}%".format(percent)
                            self.sd_status = "OK"
                            ok = True
                    else:
                        text = "SD CARD OK"
                        detail = "FREE: N/A"
                        self.sd_status = "OK"
                        ok = True
                    break
                detail = getattr(sd_utils, "last_error", "")
                print("SD mount retry:", attempt + 1, detail)
                self.draw_sd_status("SD SETUP {}/{}".format(attempt + 1, config.SD_MOUNT_RETRIES), detail)
                time.sleep_ms(config.SD_FRAME_HOLD_MS)
                time.sleep_ms(config.SD_RETRY_DELAY_MS)
        except Exception as e:
            print("SD status error:", e)
            text = "SD: FAIL"
            detail = str(e)
            self.sd_status = "FAIL"
        finally:
            try:
                LCD.spi_to_lcd_speed()
                LCD.lcd.fill(0)
                LCD.lcd.text("SD FREE SPACE", 6, 12)
                LCD.lcd.text("----------------", 0, 24)
                LCD.lcd.text(text, 20, 38)
                if detail:
                    LCD.lcd.text(detail[:16], 0, 52)
                LCD.lcd_update()
                time.sleep_ms(config.SD_FRAME_HOLD_MS)
            except Exception as e:
                print("SD screen error:", e)

        if not mounted and restart_on_fail:
            return self.show_sd_fail_options()

        return ok

    def show_sd_fail_options(self):
        sel = 0
        dirty = True

        while True:
            try:
                BEEPER.beep_update()
                ENC.update()

                d = ENC.pop_delta()
                if d:
                    sel = (sel + d) % 2
                    dirty = True
                    BEEPER.beep_start(3200, 40)

                if ENC.pop_pressed():
                    BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                    if sel == 0:
                        self.draw_sd_status("RESTARTING", "")
                        time.sleep_ms(config.DONE_HOLD_MS)
                        machine.reset()

                    self.draw_sd_status("FORMAT SD", "PLEASE WAIT")
                    time.sleep_ms(config.DONE_HOLD_MS)
                    try:
                        import sd_utils
                        if sd_utils.format_sd(LCD.spi):
                            self.draw_sd_status("FORMAT OK", "MOUNTING")
                            time.sleep_ms(config.DONE_HOLD_MS)
                            return self.show_sd_free_space(restart_on_fail=False)
                        self.draw_sd_status("FORMAT FAIL", getattr(sd_utils, "last_error", ""))
                    except Exception as e:
                        self.draw_sd_status("FORMAT FAIL", str(e))
                    time.sleep_ms(config.SD_FRAME_HOLD_MS)
                    dirty = True

                if dirty:
                    LCD.spi_to_lcd_speed()
                    LCD.lcd.fill(0)
                    LCD.lcd.text("SD SETUP FAIL", 0, 0)
                    LCD.lcd.text("----------------", 0, 10)
                    LCD.lcd.text((">" if sel == 0 else " ") + "Restart", 0, 28)
                    LCD.lcd.text((">" if sel == 1 else " ") + "Format SD", 0, 42)
                    LCD.lcd_update()
                    dirty = False
                time.sleep_ms(10)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print("SD fail option error:", e)
                self.draw_sd_status("SYSTEM ERROR", "SD OPTION")
                time.sleep_ms(config.SD_FRAME_HOLD_MS)
                machine.reset()

    def draw_sd_status(self, line1, line2=""):
        try:
            LCD.spi_to_lcd_speed()
            LCD.lcd.fill(0)
            LCD.lcd.text(line1[:16], 0, 18)
            if line2:
                LCD.lcd.text(line2[:16], 0, 34)
            LCD.lcd_update()
        except Exception as e:
            print("SD status draw error:", e)

    def draw_sd_full_popup(self):
        try:
            LCD.spi_to_lcd_speed()
            LCD.lcd.fill(0)
            LCD.lcd.text("SD CARD FULL", 14, 18)
            LCD.lcd.text("LOGGING STOPPED", 0, 34)
            LCD.lcd_update()
        except Exception as e:
            print("SD full popup error:", e)

    def show_recording_screen(self, line2=""):
        try:
            LCD.spi_to_lcd_speed()
            LCD.lcd.fill(0)
            LCD.lcd.text("AE is Recording", 0, 20)
            if line2:
                LCD.lcd.text(line2[:16], 0, 38)
            LCD.lcd_update()
            time.sleep_ms(config.SD_FRAME_HOLD_MS)
        except Exception as e:
            print("Recording screen error:", e)

    def start_ae_recording(self):
        self.recording_ok = False
        if not self.fs_ok:
            return False

        try:
            try:
                os.stat(self.AE_LOG_FILE)
                new_file = False
            except OSError:
                new_file = True

            with open(self.AE_LOG_FILE, "a") as f:
                if new_file:
                    f.write("timestamp_machine,raw_machine,volt_machine,timestamp_ambient,raw_ambient,volt_ambient\n")
            self.recording_ok = True
            self.show_recording_screen()
            return True
        except OSError as e:
            print("AE recording start error:", e)
            self.handle_sd_write_error(e)
            return False

    def handle_sd_write_error(self, err):
        print("SD write error:", err)
        self.sd_status = "FULL"
        self.fs_ok = False
        self.recording_ok = False
        self.sd_full_latched = True
        self.sd_popup_until = time.ticks_add(time.ticks_ms(), config.SD_FRAME_HOLD_MS)
        BEEPER.beep_start(500, 180, BEEPER.PRESS_DUTY)

    def log_ae_row(self, now):
        if (not self.recording_ok) or (not self.fs_ok):
            return
        if time.ticks_diff(now, self.last_log_t) < self.AE_LOG_INTERVAL_MS:
            return
        self.last_log_t = now

        try:
            machine_sensor = PREAMP.sensors["AE02"]
            ambient_sensor = PREAMP.sensors["AE01"]
            raw_machine = machine_sensor._latest
            raw_ambient = ambient_sensor._latest
            volt_machine = machine_sensor.raw_to_v(raw_machine)
            volt_ambient = ambient_sensor.raw_to_v(raw_ambient)
            ts_machine = RTC.time_string()
            ts_ambient = ts_machine

            with open(self.AE_LOG_FILE, "a") as f:
                f.write("{},{},{:.4f},{},{},{:.4f}\n".format(
                    ts_machine,
                    raw_machine,
                    volt_machine,
                    ts_ambient,
                    raw_ambient,
                    volt_ambient
                ))
        except OSError as e:
            self.handle_sd_write_error(e)
        except Exception as e:
            print("AE log error:", e)

    def update_sd_runtime_status(self, now):
        if not self.fs_ok:
            return
        if time.ticks_diff(now, self.last_sd_check_t) < self.SD_STATUS_CHECK_MS:
            return
        self.last_sd_check_t = now

        try:
            s = os.statvfs("/sd")
            free_kb = (s[0] * s[3]) // 1024
            total_kb = (s[0] * s[2]) // 1024
            if total_kb > 0:
                percent = (free_kb * 100) // total_kb
                if percent <= self.SD_FULL_PERCENT:
                    self.sd_status = "FULL"
                    self.fs_ok = False
                    self.recording_ok = False
                    if not self.sd_full_latched:
                        self.sd_full_latched = True
                        self.sd_popup_until = time.ticks_add(now, config.SD_FRAME_HOLD_MS)
                        BEEPER.beep_start(500, 180, BEEPER.PRESS_DUTY)
                else:
                    self.sd_status = "OK"
                    self.sd_full_latched = False
        except OSError as e:
            print("SD runtime status error:", e)
            self.sd_status = "FAIL"
            self.fs_ok = False
            self.recording_ok = False

    def _sync_menu_window(self):
        if self.menu_sel < self.menu_top:
            self.menu_top = self.menu_sel
        elif self.menu_sel >= self.menu_top + self.VISIBLE_MENU_ITEMS:
            self.menu_top = self.menu_sel - self.VISIBLE_MENU_ITEMS + 1

    def _sync_setting_window(self):
        if self.setting_sel < self.setting_top:
            self.setting_top = self.setting_sel
        elif self.setting_sel >= self.setting_top + self.VISIBLE_SETTING_ITEMS:
            self.setting_top = self.setting_sel - self.VISIBLE_SETTING_ITEMS + 1

    def draw_menu(self):
        self._sync_menu_window()
        LCD.lcd.fill(0)
        LCD.lcd.text(RTC.time_hms(), 0, 0)
        LCD.lcd.text("----------------", 0, 10)

        for row in range(self.VISIBLE_MENU_ITEMS):
            i = self.menu_top + row
            if i >= len(self.menu):
                break
            prefix = ">" if i == self.menu_sel else " "
            LCD.lcd.text(prefix + self.menu[i], 0, 22 + row * 10)

        LCD.lcd_update()

    def draw_setting(self):
        self._sync_setting_window()
        LCD.lcd.fill(0)
        LCD.lcd.text('Setting', 0, 0)
        LCD.lcd.text("----------------", 0, 10)
        
        for row in range(self.VISIBLE_SETTING_ITEMS):
            i = self.setting_top + row
            if i >= len(self.setting):
                break
            prefix = ">" if i == self.setting_sel else " "
            LCD.lcd.text(prefix + self.setting[i], 0, 22 + row * 10)
            if i == 0:
                LCD.lcd.text("ON" if BEEPER.is_enabled() else "OFF", 104, 22 + row * 10)
            elif i == 1:
                LCD.lcd.text("ON" if NEO.is_enabled() else "OFF", 104, 22 + row * 10)
            elif i == 2:
                LCD.lcd.text(self.sd_status, 88, 22 + row * 10)

        LCD.lcd_update()

    def enter_sensor(self, sensor_type):
        try:
            sensor_name = self.SENSOR_MAP[sensor_type]
            self.active_sensor = PREAMP.sensors[sensor_name]
            self.active_sensor.init()
            self.mode = Mode.SENSOR
            return True
        except Exception as e:
            print("Sensor init error:", e)
            self.active_sensor = None
            self.mode = Mode.MENU
            return False

    def run(self):
        while True:
            try:
                now = time.ticks_ms()

                # -- services --
                BEEPER.beep_update()
                ENC.update()
                self.update_sd_runtime_status(now)
                self.log_ae_row(now)

                # -- sampling (safe) --
                for sensor in PREAMP.sensors.values():
                    try:
                        if sensor.sample_due(now):
                            sensor.update_sample_time(now)
                            sensor.read_and_add()
                    except Exception as e:
                        print("Sensor error:", e)

                # -- encoder rotation --
                d = ENC.pop_delta()
                if d != 0:
                    if self.mode == Mode.MENU:
                        self.menu_sel = (self.menu_sel + d) % len(self.menu)
                        BEEPER.beep_start(3200, 60)
                    elif self.mode == Mode.SETTING:
                        self.setting_sel = (self.setting_sel + d) % len(self.setting)
                        BEEPER.beep_start(3200, 60)

                # -- button press --
                if ENC.pop_pressed():
                    if self.mode == Mode.MENU:
                        selected = self.menu[self.menu_sel]
                        self.page = self.menu_sel
                        if selected in self.SENSOR_MAP:
                            self.enter_sensor(selected)
                        else:
                            self.mode = Mode.SETTING
                        BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                    elif self.mode == Mode.SETTING:
                        if self.setting_sel == 0:
                            BEEPER.set_enabled(not BEEPER.is_enabled())
                            if BEEPER.is_enabled():
                                BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                        elif self.setting_sel == 1:
                            NEO.toggle()
                            BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                        elif self.setting_sel == 2:
                            pass
                        elif self.setting_sel == 3:
                            BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                            self.show_datetime_setup()
                            self.mode = Mode.SETTING
                        else:
                            print("Setting item:", self.setting[self.setting_sel])
                            BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)
                    elif self.mode == Mode.SENSOR:
                        self.enter_sensor(self.menu[self.page])
                        BEEPER.beep_start(900, 60, BEEPER.PRESS_DUTY)

                # -- button long press --
                if ENC.pop_long():
                    if self.mode == Mode.SENSOR:
                        self.mode = Mode.MENU
                        self.active_sensor = None
                        LCD.lcd.fill(0)
                    elif self.mode == Mode.SETTING:
                        self.mode = Mode.MENU
                    BEEPER.beep_start(500, 100)

                # -- rendering --
                try:
                    if time.ticks_diff(self.sd_popup_until, now) > 0:
                        self.draw_sd_full_popup()
                    elif self.mode == Mode.MENU:
                        self.draw_menu()
                    elif self.mode == Mode.SETTING:
                        self.draw_setting()
                    elif self.mode == Mode.SENSOR:
                        if self.active_sensor is not None:
                            self.active_sensor.draw_screen(log_enabled=self.fs_ok)
                except OSError as e:
                    print("FS error:", e)
                    self.fs_ok = False
                    self.mode = Mode.MENU
                    self.active_sensor = None
                    LCD.lcd.fill(0)
                    LCD.lcd.text("filesystem error", 0, 0)
                    LCD.lcd.text("Contact: 0XXXXXXXXX", 0, 10)
                    LCD.lcd_update()
                except Exception as e:
                    print("Render error:", e)
                    self.mode = Mode.MENU
                    self.active_sensor = None
            
            except KeyboardInterrupt:
                print("User interrupt (Ctrl+C)")
                try:
                    self.active_sensor = None
                    LCD.lcd.fill(0)
                    LCD.lcd.text("STOPPED", 0, 0)
                    LCD.lcd.text("Contact: 0XXXXXXXXX", 0, 10)
                    LCD.lcd_update()
                except:
                    pass
                break

            except Exception as e:
                print("FATAL:", e)
                self.mode = Mode.MENU
                self.active_sensor = None
                try:
                    LCD.lcd.fill(0)
                    LCD.lcd.text("SYSTEM ERROR", 0, 0)
                    LCD.lcd.text("Contact: 0XXXXXXXXX", 0, 10)
                    LCD.lcd_update()
                except:
                    pass
                time.sleep_ms(200)

            time.sleep_ms(5)

if __name__ == "__main__":
    app = App()
    app.run()
