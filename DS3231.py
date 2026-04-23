"""
Minimal DS3231 MicroPython driver.
Compatible with code that does:
    from DS3231 import DS3231
    rtc = DS3231(i2c)  or DS3231(i2c, 0x68)
    rtc.datetime()     -> (year, month, day, weekday, hour, minute, second, subsecond)
Also provides DateTime() as an alias.
"""

class DS3231:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr

    @staticmethod
    def _bcd2dec(x):
        return ((x >> 4) * 10) + (x & 0x0F)

    @staticmethod
    def _dec2bcd(x):
        return ((x // 10) << 4) | (x % 10)

    def _read_regs(self, reg, n):
        return self.i2c.readfrom_mem(self.addr, reg, n)

    def _write_regs(self, reg, data):
        self.i2c.writeto_mem(self.addr, reg, data)

    def datetime(self, dt=None):
        """
        Getter:
            returns (year, month, day, weekday, hour, minute, second, subsecond)
        Setter:
            accepts tuple in the same style:
            (year, month, day, weekday, hour, minute, second[, subsecond])
        """
        if dt is None:
            data = self._read_regs(0x00, 7)
            second = self._bcd2dec(data[0] & 0x7F)
            minute = self._bcd2dec(data[1] & 0x7F)
            hour_reg = data[2]
            if hour_reg & 0x40:
                # 12-hour mode
                hour = self._bcd2dec(hour_reg & 0x1F)
                pm = 1 if (hour_reg & 0x20) else 0
                if hour == 12:
                    hour = 0
                hour += 12 * pm
            else:
                # 24-hour mode
                hour = self._bcd2dec(hour_reg & 0x3F)
            weekday = self._bcd2dec(data[3] & 0x07)
            day = self._bcd2dec(data[4] & 0x3F)
            month_reg = data[5]
            month = self._bcd2dec(month_reg & 0x1F)
            year = 2000 + self._bcd2dec(data[6])
            return (year, month, day, weekday, hour, minute, second, 0)

        # setter
        if len(dt) < 7:
            raise ValueError("datetime tuple must have at least 7 items")

        year = int(dt[0])
        month = int(dt[1])
        day = int(dt[2])
        weekday = int(dt[3])
        hour = int(dt[4])
        minute = int(dt[5])
        second = int(dt[6])

        if year < 2000 or year > 2099:
            raise ValueError("DS3231 year must be 2000..2099")
        if not 1 <= month <= 12:
            raise ValueError("month out of range")
        if not 1 <= day <= 31:
            raise ValueError("day out of range")
        if not 1 <= weekday <= 7:
            # Allow machine.RTC style weekday 0..6 too.
            if 0 <= weekday <= 6:
                weekday += 1
            else:
                raise ValueError("weekday out of range")
        if not 0 <= hour <= 23:
            raise ValueError("hour out of range")
        if not 0 <= minute <= 59:
            raise ValueError("minute out of range")
        if not 0 <= second <= 59:
            raise ValueError("second out of range")

        data = bytearray(7)
        data[0] = self._dec2bcd(second)
        data[1] = self._dec2bcd(minute)
        data[2] = self._dec2bcd(hour)      # force 24-hour mode
        data[3] = self._dec2bcd(weekday)
        data[4] = self._dec2bcd(day)
        data[5] = self._dec2bcd(month)
        data[6] = self._dec2bcd(year - 2000)
        self._write_regs(0x00, data)
        return dt

    def DateTime(self):
        return self.datetime()

    def temperature(self):
        data = self._read_regs(0x11, 2)
        msb = data[0]
        lsb = data[1] >> 6
        if msb & 0x80:
            msb -= 256
        return msb + (lsb * 0.25)

    def square_wave(self, mode=0):
        """
        mode:
            0 = disable SQW, keep INTCN=1
            1 = 1 Hz
            2 = 1.024 kHz
            3 = 4.096 kHz
            4 = 8.192 kHz
        """
        ctrl = self._read_regs(0x0E, 1)[0]
        if mode == 0:
            ctrl |= 0x04      # INTCN = 1
            ctrl &= ~0x18
        else:
            ctrl &= ~0x04     # INTCN = 0
            ctrl &= ~0x18
            if mode == 2:
                ctrl |= 0x08
            elif mode == 3:
                ctrl |= 0x10
            elif mode == 4:
                ctrl |= 0x18
            # mode == 1 leaves RS bits at 00 for 1Hz
        self._write_regs(0x0E, bytes([ctrl]))
