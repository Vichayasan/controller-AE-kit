# sd_utils.py - MKS MINI12864 V3 onboard SD slot on shared SPI

import machine
import os
import time
import config

lcd_cs_pin = machine.Pin(config.PIN_LCD_CS, machine.Pin.OUT, value=1)
sd_cs_pin = machine.Pin(config.PIN_SD_CS, machine.Pin.OUT, value=1)
last_error = ""


def _spi_to_sd(spi):
    lcd_cs_pin.value(1)
    sd_cs_pin.value(1)
    spi.init(
        baudrate=config.SD_BAUD,
        polarity=config.SD_SPI_POLARITY,
        phase=config.SD_SPI_PHASE,
    )


def _spi_to_lcd(spi):
    sd_cs_pin.value(1)
    lcd_cs_pin.value(1)
    spi.init(
        baudrate=config.LCD_BAUD,
        polarity=config.LCD_SPI_POLARITY,
        phase=config.LCD_SPI_PHASE,
    )


class SDCardNoWait:
    def __init__(self, spi_obj, cs_pin):
        self.spi = spi_obj
        self.cs = cs_pin
        self.cmdbuf = bytearray(6)
        self.cdv = 1
        self.sectors = 0
        self.cs.init(machine.Pin.OUT, value=1)
        self.init_card()

    def _recover_bus(self):
        self.cs.value(1)
        self.spi.write(b"\xff" * 16)
        time.sleep_ms(2)

    def _deselect(self):
        self.cs.value(1)
        self.spi.write(b"\xff\xff")

    def _select_fresh(self):
        self._deselect()
        time.sleep_us(50)
        self.cs.value(0)
        time.sleep_us(50)

    def _cmd(self, cmd, arg, crc, read_extra=0):
        self._select_fresh()
        self.cmdbuf[0] = 0x40 | cmd
        self.cmdbuf[1] = (arg >> 24) & 0xff
        self.cmdbuf[2] = (arg >> 16) & 0xff
        self.cmdbuf[3] = (arg >> 8) & 0xff
        self.cmdbuf[4] = arg & 0xff
        self.cmdbuf[5] = crc

        self.spi.write(b"\xff")
        self.spi.write(self.cmdbuf)

        for _ in range(20):
            r1 = self.spi.read(1, 0xff)[0]
            if not (r1 & 0x80):
                if read_extra:
                    return r1, self.spi.read(read_extra, 0xff)
                return r1, b""
        return -1, b""

    def _cmd_end(self):
        self.cs.value(1)
        self.spi.read(1, 0xff)

    def init_card(self):
        self.cs.value(1)
        self.spi.write(b"\xff" * 80)
        time.sleep_ms(50)

        r = -1
        for _ in range(10):
            r, _ = self._cmd(0, 0, 0x95, 0)
            self._cmd_end()
            if r == 0x01:
                break
            time.sleep_ms(10)
        if r != 0x01:
            raise OSError("SD CMD0 failed")

        ok = False
        for _ in range(8):
            r, extra = self._cmd(8, 0x000001AA, 0x87, 4)
            self._cmd_end()
            if r == 0x01 and extra == b"\x00\x00\x01\xaa":
                ok = True
                break
            time.sleep_ms(10)
        if not ok:
            raise OSError("SD CMD8 failed")

        for _ in range(200):
            r, _ = self._cmd(55, 0, 0x65, 0)
            self._cmd_end()
            if r < 0:
                time.sleep_ms(10)
                continue
            r, _ = self._cmd(41, 0x40000000, 0x77, 0)
            self._cmd_end()
            if r == 0x00:
                break
            time.sleep_ms(10)
        if r != 0x00:
            raise OSError("SD ACMD41 failed")

        r, extra = self._cmd(58, 0, 0xFD, 4)
        self._cmd_end()
        if r != 0x00:
            raise OSError("SD CMD58 failed")

        self.cdv = 1 if (extra[0] & 0x40) else 512
        if self.cdv == 512:
            r, _ = self._cmd(16, 512, 0xff, 0)
            self._cmd_end()
            if r != 0x00:
                raise OSError("SD CMD16 failed")

        r = -1
        for _ in range(config.SD_CMD9_RETRIES):
            r, _ = self._cmd(9, 0, 0xAF, 0)
            if r == 0x00:
                break
            self._cmd_end()
            self.spi.write(b"\xff" * 8)
            time.sleep_ms(50)
        if r != 0x00:
            raise OSError("SD CMD9 failed")

        for _ in range(20000):
            token = self.spi.read(1, 0xff)[0]
            if token == 0xfe:
                break
        else:
            self._cmd_end()
            raise OSError("SD CSD token timeout")

        csd = self.spi.read(16, 0xff)
        self.spi.read(2, 0xff)
        self._cmd_end()

        csd_version = csd[0] >> 6
        if csd_version == 1:
            c_size = ((csd[7] & 0x3f) << 16) | (csd[8] << 8) | csd[9]
            self.sectors = (c_size + 1) * 1024
        elif csd_version == 0:
            read_bl_len = csd[5] & 0x0f
            c_size = ((csd[6] & 0x03) << 10) | (csd[7] << 2) | ((csd[8] & 0xc0) >> 6)
            c_size_mult = ((csd[9] & 0x03) << 1) | ((csd[10] & 0x80) >> 7)
            block_len = 1 << read_bl_len
            block_nr = (c_size + 1) * (1 << (c_size_mult + 2))
            self.sectors = (block_nr * block_len) // 512
        else:
            raise OSError("Unsupported CSD v{}".format(csd_version))

    def readblocks(self, block_num, buf):
        mv = memoryview(buf)
        n = len(buf) // 512
        for i in range(n):
            block = block_num + i
            last_r = -1
            args = (block * self.cdv,)
            if self.cdv == 512:
                args = (block * 512, block)
            for attempt in range(3):
                for arg in args:
                    r, _ = self._cmd(17, arg, 0xff, 0)
                    last_r = r
                    if r == 0x00:
                        for _ in range(30000):
                            token = self.spi.read(1, 0xff)[0]
                            if token == 0xfe:
                                mv[i * 512:(i + 1) * 512] = self.spi.read(512, 0xff)
                                self.spi.read(2, 0xff)
                                self._cmd_end()
                                break
                        else:
                            self._cmd_end()
                            self._recover_bus()
                            time.sleep_ms(10)
                            continue
                        break

                    self._cmd_end()
                    self._recover_bus()
                    time.sleep_ms(10)
                else:
                    continue
                break
            else:
                raise OSError("SD CMD17 failed r={}".format(last_r))

    def writeblocks(self, block_num, buf):
        mv = memoryview(buf)
        n = len(buf) // 512
        for i in range(n):
            r, _ = self._cmd(24, (block_num + i) * self.cdv, 0, 0)
            if r != 0x00:
                self._cmd_end()
                raise OSError("SD CMD24 failed")
            self.spi.write(b"\xff\xfe")
            self.spi.write(mv[i * 512:(i + 1) * 512])
            self.spi.write(b"\xff\xff")
            token = self.spi.read(1, 0xff)[0]
            if (token & 0x1f) != 0x05:
                self._cmd_end()
                raise OSError("SD write rejected")
            for _ in range(20000):
                if self.spi.read(1, 0xff)[0] == 0xff:
                    break
            else:
                self._cmd_end()
                raise OSError("SD write timeout")
            self._cmd_end()

    def ioctl(self, op, arg):
        if op == 4:
            return self.sectors
        if op == 5:
            return 512
        if op == 6:
            return 1
        return 0


class BlockDevPartition:
    def __init__(self, dev, lba_start):
        self.dev = dev
        self.lba_start = lba_start

    def readblocks(self, block_num, buf):
        return self.dev.readblocks(self.lba_start + block_num, buf)

    def writeblocks(self, block_num, buf):
        return self.dev.writeblocks(self.lba_start + block_num, buf)

    def ioctl(self, op, arg):
        if op == 4:
            return self.dev.ioctl(4, arg) - self.lba_start
        if op == 5:
            return 512
        if op == 6:
            return 1
        return self.dev.ioctl(op, arg)


def mount_sd(spi):
    global last_error
    last_error = ""
    try:
        _spi_to_sd(spi)
        driver = SDCardNoWait(spi, sd_cs_pin)
        errors = []

        for dev in (driver, BlockDevPartition(driver, config.SD_PARTITION_LBA)):
            try:
                vfs = os.VfsFat(dev)
                try:
                    os.mount(vfs, "/sd")
                except OSError:
                    try:
                        os.umount("/sd")
                    except Exception:
                        pass
                    os.mount(vfs, "/sd")
                return True
            except Exception as e:
                errors.append(str(e))

        probe = bytearray(512)
        driver.readblocks(0, probe)
        sec0_blank = probe[510] != 0x55 or probe[511] != 0xaa
        driver.readblocks(config.SD_PARTITION_LBA, probe)
        part_blank = probe[510] != 0x55 or probe[511] != 0xaa
        if sec0_blank and part_blank:
            raise OSError("FORMAT SD FAT32")

        raise OSError("; ".join(errors))
    except Exception as e:
        last_error = str(e)
        print("Mount failed:", last_error)
        return False
    finally:
        _spi_to_lcd(spi)


def format_sd(spi):
    global last_error
    last_error = ""
    try:
        try:
            os.umount("/sd")
        except Exception:
            pass

        _spi_to_sd(spi)
        driver = SDCardNoWait(spi, sd_cs_pin)
        os.VfsFat.mkfs(driver)
        return True
    except Exception as e:
        last_error = str(e)
        print("Format failed:", last_error)
        return False
    finally:
        _spi_to_lcd(spi)
