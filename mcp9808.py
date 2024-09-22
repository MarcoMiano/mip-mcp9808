from machine import SoftI2C, I2C

HYST_00 = 0b00  # Hysteresis 0°C (power-up default)
HYST_15 = 0b01  # Hysteresis 1,5°C
HYST_30 = 0b10  # Hysteresis 3,0°C
HYST_60 = 0b11  # Hysteresis 6,0°C

RES_0_5 = 0b00  # Resolution 0.5°C
RES_0_25 = 0b01  # Resolution 0.25°C
RES_0_125 = 0b10  # Resolution 0.125°C
RES_0_0625 = 0b11  # Resolution 0.0625°C


class MCP9808(object):
    BASE_ADDR = 0x18

    # Don't access register with address higher than 0x08
    REG_CFG = 0x01  # Config register
    REG_ATU = 0x02  # Alert Temperature Upper boundary trip register
    REG_ATL = 0x03  # Alert Temperature Lower boundary trip register
    REG_ATC = 0x04  # Critical Temperature Trip register
    REG_TEM = 0x05  # Temperature register
    REG_MFR = 0x06  # Manufacturer ID register
    REG_DEV = 0x07  # Device ID register
    REG_RES = 0x08  # Resolution register

    def __init__(
        self,
        i2c: SoftI2C | I2C,
        addr: int | None = None,
        A0: bool = False,
        A1: bool = False,
        A2: bool = False,
        debug: bool = False,
    ) -> None:
        self.__i2c: SoftI2C | I2C = i2c
        self.__debug_bit: bool = debug
        if addr:
            self.__addr = addr
        else:
            self.__addr: int = self.BASE_ADDR | (A2 << 2) | (A1 << 1) | A0
        self.__check_device()
        self.__get_config()

    def __debug(self, text: str) -> None:
        if self.__debug == True:
            print(text)

    def __check_device(self) -> None:
        self.__mfr_id: bytes = self.__i2c.readfrom_mem(self.__addr, self.REG_MFR, 2)
        if self.__mfr_id != b"\x00\x54":
            raise Exception(f"Invalid manufacturer ID {self.__mfr_id}")
        self.__dev_id: bytes = self.__i2c.readfrom_mem(self.__addr, self.REG_DEV, 2)
        if self.__dev_id[0] != 4:
            raise Exception(f"Invalid device ID {self.__dev_id[0]}")
        if self.__dev_id[1] != 0:
            self.__debug(
                f"[WARN] Module written for HW revision 0 but got {self.__dev_id[1]}.",
            )

    def __get_config(self) -> None:
        buf: bytes = self.__i2c.readfrom_mem(self.__addr, self.REG_CFG, 2)
        self.hyst_mode: int = (buf[0] >> 1) & 0x03
        self.shdn = bool(buf[0] & 0x01)
        self.crit_lock = bool((buf[1] >> 7) & 0x01)
        self.window_lock = bool((buf[1] >> 6) & 0x01)
        self.irq_clear_bit = bool((buf[1] >> 5) & 0x01)
        self.alert = bool((buf[1] >> 4) & 0x01)
        self.alert_ctrl = bool((buf[1] >> 3) & 0x01)
        self.alert_sel = bool((buf[1] >> 2) & 0x01)
        self.alert_pol = bool((buf[1] >> 1) & 0x01)
        self.alert_mode = bool(buf[1] & 0x01)

    def __set_config(
        self,
        hyst_mode: int | None = None,
        shdn: bool | None = None,
        crit_lock: bool | None = None,
        window_lock: bool | None = None,
        irq_clear_bit: bool = False,
        alert_ctrl: bool | None = None,
        alert_sel: bool | None = None,
        alert_pol: bool | None = None,
        alert_mode: bool | None = None,
    ) -> None:
        if hyst_mode is None:
            hyst_mode = self.hyst_mode
        if shdn is None:
            shdn = self.shdn
        if crit_lock is None:
            crit_lock = self.crit_lock
        if window_lock is None:
            window_lock = self.window_lock
        if alert_ctrl is None:
            alert_ctrl = self.alert_ctrl
        if alert_sel is None:
            alert_sel = self.alert_sel
        if alert_pol is None:
            alert_pol = self.alert_pol
        if alert_mode is None:
            alert_mode = self.alert_mode

        if hyst_mode not in [HYST_00, HYST_15, HYST_30, HYST_60]:
            raise ValueError(
                f"Invalid hysteresis mode: {hyst_mode}. Value should be between 0 and 3 inclusive."
            )
        if shdn.__class__ != bool:
            raise TypeError(
                f"Invalid shutdown argument type: {shdn} {shdn.__class__}. Expecting a bool.",
            )
        if crit_lock.__class__ != bool:
            raise TypeError(
                f"Invalid crit lock argument type: {crit_lock} {crit_lock.__class__}. Expecting a bool.",
            )
        if window_lock.__class__ != bool:
            raise TypeError(
                f"Invalid temperature window lock argument type: {window_lock} {window_lock.__class__}. Expecting a bool.",
            )
        if irq_clear_bit.__class__ != bool:
            raise TypeError(
                f"Invalid interrupt clear argument type: {irq_clear_bit} {irq_clear_bit.__class__}. Expecting a bool.",
            )
        if alert_ctrl.__class__ != bool:
            raise TypeError(
                f"Invalid alert output control argument type: {alert_ctrl} {alert_ctrl.__class__}. Expecting a bool.",
            )
        if alert_sel.__class__ != bool:
            raise TypeError(
                f"Invalid alert output select argument type: {alert_sel} {alert_sel.__class__}. Expecting a bool.",
            )
        if alert_pol.__class__ != bool:
            raise TypeError(
                f"Invalid alert output polarity argument type: {alert_pol} {alert_pol.__class__}. Expecting a bool.",
            )
        if alert_mode.__class__ != bool:
            raise TypeError(
                f"Invalid alert output mode argument type: {alert_mode} {alert_mode.__class__}. Expecting a bool.",
            )

        buf = bytearray(b"\x00\x00")
        buf[0] = (hyst_mode << 1) | shdn
        buf[1] = (
            (crit_lock << 7)
            | (window_lock << 6)
            | (irq_clear_bit << 5)
            | (alert_ctrl << 3)
            | (alert_sel << 2)
            | (alert_pol << 1)
            | alert_mode
        )
        self.__i2c.writeto_mem(self.__addr, self.REG_CFG, buf)
        self.__get_config()
        if self.hyst_mode != hyst_mode:
            self.__debug(
                f"[WARN] Tried to set hysteresis mode but failed. Set {hyst_mode} but get {self.hyst_mode}.",
            )
        if self.shdn != shdn:
            self.__debug(
                f"[WARN] Tried to set shutdown but failed. Set {shdn} but get {self.shdn}.",
            )
        if self.crit_lock != crit_lock:
            self.__debug(
                f"[WARN] Tried to set crit lock but failed. Set {crit_lock} but get {self.crit_lock}.",
            )
        if self.irq_clear_bit == True:
            self.__debug(
                "[WARN] Something wrong with interrupt clear bit. Read True should always be False"
            )
        if self.window_lock != window_lock:
            self.__debug(
                f"[WARN] Tried to set window lock but failed. Set {window_lock} but get {self.window_lock}.",
            )
        if self.alert_ctrl != alert_ctrl:
            self.__debug(
                f"[WARN] Tried to set alert output control but failed. Set {alert_ctrl} but get {self.alert_ctrl}.",
            )
        if self.alert_sel != alert_sel:
            self.__debug(
                f"[WARN] Tried to set alert output select but failed. Set {alert_sel} but get {self.alert_sel}.",
            )
        if self.alert_pol != alert_pol:
            self.__debug(
                f"[WARN] Tried to set alert output polarity but failed. Set {alert_pol} but get {self.alert_pol}.",
            )
        if self.alert_mode != alert_mode:
            self.__debug(
                f"[WARN] Tried to set alert output mode but failed. Set {alert_mode} but get {self.alert_mode}.",
            )

    def __set_alert_limit(self, limit: float | int, register: int) -> None:

        if not limit.__class__ in [float, int]:
            raise TypeError(
                f"Invalid temperature alert type, expecting float or int but got {limit.__class__}.",
            )
        if limit < -128 or limit > 127:
            raise ValueError("Temperature out of range [-128, 127]")
        if limit < -20 or limit > 100:
            self.__debug(
                "[WARN] Temperature outside of operational range, limit won't be ever reached.",
            )

        buf = bytearray(b"\x00\x00")

        # If limit is negative set sign fifth bit on otherwise leave it at 0
        if limit < 0:
            sign = 0x10
        else:
            sign = 0x00

        # If limit is between -1 and 0 (like -0.25) set integral to 0xFF (-0 in 2's complement)
        if -1 < limit < 0:
            integral: int = 0xFF
        # Otherwise truncate limit to a int and keep only the rightmost byte
        else:
            integral: int = int(limit) & 0xFF

        # Calculate the fractional part by keeping the 2 rightmost bits of the integer division of 0.25 (the sensitivity) and the remainder part of the decimal part of limit
        frac_normal = int((limit - integral) / 0.25) & 0x03

        # Build the send buffer highest byte combining (bitwise or) sign and the integral right shifted by 4
        buf[0] = sign | (integral >> 4)
        # Build the send buffer lowest byte combining (bitwise or) the integral left shifted by 4 and the fractional part left shifted by 2 (last 2 bit are 0)
        buf[1] = (integral << 4) | (frac_normal << 2)

        self.__i2c.writeto_mem(self.__addr, register, buf)

        check: bytes = self.__i2c.readfrom_mem(self.__addr, register, 2)

        if check != buf:
            self.__debug(
                f"[WARN] Tried to set alert limit temperature but failed. Set {buf[0]:08b}-{buf[1]:08b} but got {check[0]:08b}-{check[1]:08b}",
            )

    def set_hysteresis_mode(
        self,
        hyst_mode: int,
    ) -> None:
        self.__set_config(hyst_mode=hyst_mode)

    def shutdown(self, wake=False) -> None:
        self.__set_config(shdn=not wake)

    def lock_crit_limit(self, unlock=False) -> None:
        self.__set_config(crit_lock=not unlock)

    def lock_window_limit(self, unlock=False) -> None:
        self.__set_config(window_lock=not unlock)

    def irq_clear(self) -> None:
        self.__set_config(irq_clear_bit=True)

    def get_alert_status(self) -> bool:
        self.__get_config()
        return self.alert

    def enable_alert(self, disable=False) -> None:
        self.__set_config(alert_ctrl=not disable)

    def set_alert_threshold(self, only_crit=False) -> None:
        self.__set_config(alert_sel=only_crit)

    def set_alert_polarity(self, active_high=False) -> None:
        self.__set_config(alert_pol=active_high)

    def set_alert_mode(self, irq=False) -> None:
        self.__set_config(alert_mode=irq)

    def set_alert_upper_limit(self, upper_limit: float | int) -> None:
        self.__set_alert_limit(upper_limit, self.REG_ATU)

    def set_alert_lower_limit(self, lower_limit: float | int) -> None:
        self.__set_alert_limit(lower_limit, self.REG_ATL)

    def set_alert_crit_limit(self, crit_limit: float | int) -> None:
        self.__set_alert_limit(crit_limit, self.REG_ATC)

    def get_temeperature(self) -> float:
        # Read temperature register from sensor
        buf: bytes = self.__i2c.readfrom_mem(self.__addr, self.REG_TEM, 2)
        # Extract the sign bit
        sign: int = buf[0] & 0x10
        # Calculate the 4 upper bit of the integral by left shifting the first byte by 4 and keeping the rightmost byte of the first buf byte
        upper: int = (buf[0] << 4) & 0xFF
        # Calculate the 4 lower bit of the integral and the fractional part into a float by dividing by 16 the rightmost byte of the second buf byte
        lower: float = (buf[1] & 0xFF) / 16
        # Calculate the temperature as a float by adding the upper byte (leftmost 4 bit of integral) and the lower byte (rightmost 4 bit of integral + fractional).
        # In case of negative value subtract 256 from the sum to convert from 2's complement 8+4bit fractional value to negative float
        temp: float = (upper + lower) - 256 if sign else upper + lower
        return temp

    def get_alert_triggers(self) -> tuple[bool, bool, bool]:
        # Read temperature register from sensor
        buf: bytes = self.__i2c.readfrom_mem(self.__addr, self.REG_TEM, 2)
        # Extract the 16th bit (last), Ta vs. Tcrit. False = Ta < Tcrit | True = Ta >= Tcrit
        ta_tcrit = bool(buf[0] & 0x80)
        # Extract the 15th bit, Ta vs. Tupper. False = Ta <= Tupper | True = Ta > Tupper
        ta_tupper = bool(buf[0] & 0x40)
        # Extract the 14th bit, Ta vs Tlower. False = Ta <= Tlower | True = Ta > Tlower
        ta_tlower = bool(buf[0] & 0x20)

        return ta_tcrit, ta_tupper, ta_tlower

    def set_resolution(self, resolution=RES_0_0625) -> None:
        # Check if resolution is a compatible value
        if not resolution in [RES_0_5, RES_0_25, RES_0_125, RES_0_0625]:
            raise ValueError(
                f"Invalid resolution: {resolution}. Value should be between 0 and 3 inclusive.",
            )

        buf = bytearray(b"\x00")

        buf[0] |= resolution & 0x03
        self.__i2c.writeto_mem(self.__addr, self.REG_RES, buf)
        check = self.__i2c.readfrom_mem(self.__addr, self.REG_RES, 1)
        if check != buf:
            self.__debug(
                f"[WARN] Tried to set resolution but failed. Set {resolution} but got {check[0]}",
            )
