# preamp_mod.py - Multi-sensor support with isolated state

from machine import ADC, Pin
import time
import config
import lcd_mod as LCD

PLOT_Y0 = 12
PLOT_H  = 40
PLOT_W  = 128

class AESensor:
    """Single AE sensor with isolated buffer and state"""
    
    def __init__(self, adc_pin, name="AE", buffer_size=128, sample_ms=20, draw_ms=80):
        self.adc = ADC(Pin(adc_pin))
        self.name = name
        self.buffer_size = buffer_size
        self.sample_ms = sample_ms
        self.draw_ms = draw_ms
        
        # Isolated state per sensor
        self._buf = [0] * buffer_size
        self._idx = 0
        self._latest = 0
        self._last_sample_t = 0
        self._last_draw_t = 0
        
        self.init()
    
    def init(self):
        """Initialize/reset sensor buffer"""
        self._latest = self.adc.read_u16()
        for i in range(self.buffer_size):
            self._buf[i] = self._latest
        self._idx = 0
        now = time.ticks_ms()
        self._last_sample_t = now
        self._last_draw_t = 0
    
    def add_sample(self, raw):
        """Add sample to circular buffer"""
        self._latest = raw
        self._buf[self._idx] = raw
        self._idx = (self._idx + 1) % self.buffer_size
    
    def read_and_add(self):
        """Read from ADC and add to buffer"""
        raw = self.adc.read_u16()
        self.add_sample(raw)
        return raw
    
    def sample_due(self, now):
        """Check if it's time to sample"""
        return time.ticks_diff(now, self._last_sample_t) >= self.sample_ms
    
    def update_sample_time(self, now):
        """Update last sample timestamp"""
        self._last_sample_t = now
    
    def raw_to_v(self, raw):
        """Convert raw ADC to voltage"""
        return raw * config.VREF / 65535.0
    
    def get_ordered_buffer(self):
        """Get buffer in chronological order"""
        return self._buf[self._idx:] + self._buf[:self._idx]
    
    def draw_screen(self, log_enabled=False, force=False):
        """Draw waveform to LCD"""
        now = time.ticks_ms()
        if (not force) and time.ticks_diff(now, self._last_draw_t) < self.draw_ms:
            return
        self._last_draw_t = now
        
        ordered = self.get_ordered_buffer()
        units = [x / 65535.0 for x in ordered]
        v = self.raw_to_v(self._latest)
        
        LCD.lcd.fill(0)
        LCD.lcd.text(self.name, 0, 0)
        LCD.lcd.text("----------------", 0, 10)
        LCD.fill_rect(0, PLOT_Y0, PLOT_W, PLOT_H, 0)
        self._draw_trace(units)
        LCD.lcd.text("V:{:.2f} LOG:{}".format(v, "Y" if log_enabled else "N"), 0, 54)
        LCD.lcd_update()
    
    def _draw_trace(self, units):
        """Draw trace on LCD"""
        def _clamp(x, lo, hi):
            return lo if x < lo else (hi if x > hi else x)
        
        def _y_from_unit(u):
            u = _clamp(u, 0.0, 1.0)
            return PLOT_Y0 + (PLOT_H - 1) - int(u * (PLOT_H - 1))
        
        prev_y = _y_from_unit(units[0])
        LCD.pixel(0, prev_y, 1)
        for x in range(1, min(PLOT_W, len(units))):
            y = _y_from_unit(units[x])
            LCD.pixel(x, y, 1)
            if y > prev_y:
                for yy in range(prev_y, y + 1):
                    LCD.pixel(x, yy, 1)
            elif y < prev_y:
                for yy in range(y, prev_y + 1):
                    LCD.pixel(x, yy, 1)
            prev_y = y


# ── Create sensor instances ──────────────────
sensors = {
    'AE01': AESensor(config.PIN_AE_SENSOR01_ADC, name="AE SENSOR 01"),
    'AE02': AESensor(config.PIN_AE_SENSOR02_ADC, name="AE SENSOR 02"),
    # 'AE03': AESensor(config.PIN_AE_SENSOR03_ADC, name="AE SENSOR 03"),  # เพิ่มง่าย
}

# ── Backward compatibility (optional) ─────────
def get_sensor(name='AE01'):
    """Get sensor by name"""
    return sensors.get(name)