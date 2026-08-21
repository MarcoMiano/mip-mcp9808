# SPDX-FileCopyrightText: 2024-2026 Marco Miano
# SPDX-License-Identifier: MIT

"""Microchip MCP9808 driver for MicroPython

THE MCP9808 IS A COMPLEX SENSOR WITH MANY FEATURES. IT IS ADVISABLE TO READ THE DATASHEET.

DO NOT ACCESS RESERVED REGISTERS WITH ADDRESSES HIGHER THAN 0x08.
ACCESSING THEM IS UNSUPPORTED AND MAY CAUSE UNSPECIFIED SENSOR BEHAVIOUR.

This driver is a comprehensive implementation of the MCP9808 sensor's features. It is designed
to be easy to use and offers a high level of abstraction from the sensor's registers.
The driver includes built-in error checking (such as type validation and bounds checking
for register access) and a debug mode to assist with development.
The I2C object must implement readfrom_mem_into() and writeto_mem(). The driver reuses internal
buffers, so one sensor instance is not reentrant across normal and interrupt contexts.



Example usage:

from mcp9808 import MCP9808, HYST_15, RES_0_125
from machine import SoftI2C, Pin

i2c = SoftI2C(scl=Pin(17), sda=Pin(16), freq=400000)
t_sensor = MCP9808(i2c)

# Get temperature with default settings
temperature: float = t_sensor.get_temperature()
temperature_x16: int = t_sensor.get_temperature_x16()

# Various settings
t_sensor.hyst_mode = HYST_15
t_sensor.set_resolution(resolution=RES_0_125)
t_sensor.set_alert_crit_limit(crit_limit=65.0)
t_sensor.set_alert_upper_limit(upper_limit=50.0)
t_sensor.set_alert_lower_limit(lower_limit=-10.0)
t_sensor.set_alert_lower_limit_x4(lower_limit_x4=-40)
t_sensor.enable_alert()

# Enable debug mode to get warnings
t_sensor = MCP9808(i2c, debug=True)


# For more information, see the README file at
https://github.com/MarcoMiano/mip-mcp9808
"""

# Handy Constants
HYST_00 = 0b00  # Hysteresis 0°C (power-up default)
HYST_15 = 0b01  # Hysteresis 1,5°C
HYST_30 = 0b10  # Hysteresis 3,0°C
HYST_60 = 0b11  # Hysteresis 6,0°C

RES_0_5 = 0b00  # Resolution 0.5°C
RES_0_25 = 0b01  # Resolution 0.25°C
RES_0_125 = 0b10  # Resolution 0.125°C
RES_0_0625 = 0b11  # Resolution 0.0625°C (power-up default)


class MCP9808:
    """A class to interface with the Microchip MCP9808 temperature sensor over I2C.

    Attributes:
        ``BASE_ADDR`` (int): The base I2C address for the MCP9808 sensor.
        ``REG_CFG`` (int): Address of the configuration register.
        ``REG_ATU`` (int): Address of the alert temperature upper boundary trip register.
        ``REG_ATL`` (int): Address of the alert temperature lower boundary trip register.
        ``REG_ATC`` (int): Address of the critical temperature trip register.
        ``REG_TEM`` (int): Address of the temperature register.
        ``REG_MFR`` (int): Address of the manufacturer ID register.
        ``REG_DEV`` (int): Address of the device ID register.
        ``REG_RES`` (int): Address of the resolution register.
    """

    BASE_ADDR = 0x18
    #######################################################
    # DON'T ACCESS REGISTERS WITH ADDRESSES HIGHER THAN 0X08 #
    #######################################################
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
        i2c,
        addr: int | None = None,
        A0: bool = False,
        A1: bool = False,
        A2: bool = False,
        debug: bool = False,
        verify: bool = True,
    ) -> None:
        """Initialize the sensor object instance.

        Args:
            ``i2c``: An I2C-compatible object implementing readfrom_mem_into() and writeto_mem().
            ``addr`` (int | None, optional): The I2C address of the sensor. If not provided,
                the address will be calculated based on A0, A1, and A2. Defaults to None.
            ``A0`` (bool, optional): The state of address pin A0. Defaults to False.
            ``A1`` (bool, optional): The state of address pin A1. Defaults to False.
            ``A2`` (bool, optional): The state of address pin A2. Defaults to False.
            ``debug`` (bool, optional): Enable or disable debug mode. Defaults to False.
            ``verify`` (bool, optional): Verify the manufacturer and device IDs during
                construction. Defaults to True.
        Returns:
            ``None``
        Raises:
            ``TypeError``: If addr is not an int or None.
            ``ValueError``: If addr is outside the 7-bit I2C address range.
            ``TypeError``: If A0, A1, A2, debug, or verify is not a bool.
        """

        if addr is not None and addr.__class__ is not int:
            raise TypeError(
                f"addr: {addr} {addr.__class__}. Expecting an int or None.",
            )
        if addr is not None and (addr < 0 or addr > 0x7F):
            raise ValueError(f"addr: {addr}. Expecting a 7-bit I2C address.")
        if A0.__class__ is not bool:
            raise TypeError(f"A0: {A0} {A0.__class__}. Expecting a bool.")
        if A1.__class__ is not bool:
            raise TypeError(f"A1: {A1} {A1.__class__}. Expecting a bool.")
        if A2.__class__ is not bool:
            raise TypeError(f"A2: {A2} {A2.__class__}. Expecting a bool.")
        if debug.__class__ is not bool:
            raise TypeError(
                f"debug: {debug} {debug.__class__}. Expecting a bool.",
            )
        if verify.__class__ is not bool:
            raise TypeError(
                f"verify: {verify} {verify.__class__}. Expecting a bool.",
            )

        self._i2c = i2c
        self._debug: bool = debug
        # Reuse fixed buffers so register reads do not allocate a new bytes object
        self._buf = bytearray(2)
        self._buf1 = bytearray(1)
        if addr is not None:
            self._addr = addr
        else:
            self._addr: int = self.BASE_ADDR | (A2 << 2) | (A1 << 1) | A0
        if verify:
            self.verify()
        self.refresh()

    def verify(self) -> None:
        """Check the manufacturer and device IDs to verify the connected sensor.

        Raises:
            ``RuntimeError``: If the manufacturer ID does not match the expected value.
            ``RuntimeError``: If the device ID does not match the expected value.
        Warns:
            If the hardware revision does not match the expected value and debug mode is enabled.
        Returns:
            ``None``
        """

        # Read and check the manufacturer ID
        self._i2c.readfrom_mem_into(self._addr, self.REG_MFR, self._buf)
        if self._buf[0] != 0 or self._buf[1] != 0x54:
            raise RuntimeError(
                f"Invalid manufacturer ID {self._buf[0]:02x}{self._buf[1]:02x}",
            )
        # Read and check the device ID and hardware revision
        self._i2c.readfrom_mem_into(self._addr, self.REG_DEV, self._buf)
        if self._buf[0] != 4:
            raise RuntimeError(f"Invalid device ID {self._buf[0]}")
        if self._buf[1] != 0 and self._debug:
            print(
                f"[WARN] Module written for HW revision 0 but got {self._buf[1]}.",
            )

    def refresh(self) -> None:
        """Read the configuration register and refresh the cached properties.

        This method reads 2 bytes from the configuration register of the sensor.
        It then parses the bytes to update the following instance attributes:
            ``_hyst_mode``: Hysteresis mode (int)
            ``_shdn``: Shutdown mode (bool)
            ``_crit_lock``: Critical temperature register lock (bool)
            ``_alerts_lock``: Alerts temperature registers lock (bool)
            ``_irq_clear_bit``: Interrupt clear bit (bool)
            ``_alert``: Alert output status (bool)
            ``_alert_ctrl``: Alert control (bool)
            ``_alert_sel``: Alert output select (bool)
            ``_alert_pol``: Alert output polarity (bool)
            ``_alert_mode``: Alert output mode (bool)
        Returns:
            ``None``
        """

        self._i2c.readfrom_mem_into(self._addr, self.REG_CFG, self._buf)
        self._hyst_mode: int = (self._buf[0] >> 1) & 0x03
        self._shdn = bool(self._buf[0] & 0x01)
        self._crit_lock = bool(self._buf[1] & 0x80)
        self._alerts_lock = bool(self._buf[1] & 0x40)
        self._irq_clear_bit = bool(self._buf[1] & 0x20)
        self._alert = bool(self._buf[1] & 0x10)
        self._alert_ctrl = bool(self._buf[1] & 0x08)
        self._alert_sel = bool(self._buf[1] & 0x04)
        self._alert_pol = bool(self._buf[1] & 0x02)
        self._alert_mode = bool(self._buf[1] & 0x01)

    def _set_config(
        self,
        hyst_mode: int | None = None,
        shdn: bool | None = None,
        crit_lock: bool | None = None,
        alerts_lock: bool | None = None,
        irq_clear_bit: bool = False,
        alert_ctrl: bool | None = None,
        alert_sel: bool | None = None,
        alert_pol: bool | None = None,
        alert_mode: bool | None = None,
    ) -> None:
        """Private method to set the configuration of the sensor.

        Parameters:
            ``hyst_mode`` (int | None): Hysteresis mode. Valid values are HYST_00, HYST_15, HYST_30, HYST_60.
            ``shdn`` (bool | None): Shutdown mode.
            ``crit_lock`` (bool | None): Critical temperature register lock.
            ``alerts_lock`` (bool | None): Alerts temperature registers lock.
            ``irq_clear_bit`` (bool): Interrupt clear bit.
            ``alert_ctrl`` (bool | None): Alert output control.
            ``alert_sel`` (bool | None): Alert output select.
            ``alert_pol`` (bool | None): Alert output polarity.
            ``alert_mode`` (bool | None): Alert output mode.
        Raises:
            ``ValueError``: If hyst_mode is not one of the valid values.
            ``TypeError``: If any of the boolean parameters are not of type bool.
        Returns:
            ``None``
        """

        if hyst_mode is None:
            hyst_mode = self._hyst_mode
        if shdn is None:
            shdn = self._shdn
        if crit_lock is None:
            crit_lock = self._crit_lock
        if alerts_lock is None:
            alerts_lock = self._alerts_lock
        if alert_ctrl is None:
            alert_ctrl = self._alert_ctrl
        if alert_sel is None:
            alert_sel = self._alert_sel
        if alert_pol is None:
            alert_pol = self._alert_pol
        if alert_mode is None:
            alert_mode = self._alert_mode

        # Type/value check the parameters
        if hyst_mode.__class__ is not int:
            raise TypeError(
                f"hyst_mode: {hyst_mode} {hyst_mode.__class__}. Expecting an int.",
            )
        if hyst_mode not in [HYST_00, HYST_15, HYST_30, HYST_60]:
            raise ValueError(
                f"hyst_mode: {hyst_mode}. Value should be between 0 and 3 inclusive."
            )
        if shdn.__class__ is not bool:
            raise TypeError(
                f"shdn: {shdn} {shdn.__class__}. Expecting a bool.",
            )
        if crit_lock.__class__ is not bool:
            raise TypeError(
                f"crit_lock: {crit_lock} {crit_lock.__class__}. Expecting a bool.",
            )
        if alerts_lock.__class__ is not bool:
            raise TypeError(
                f"alerts_lock: {alerts_lock} {alerts_lock.__class__}. Expecting a bool.",
            )
        if irq_clear_bit.__class__ is not bool:
            raise TypeError(
                f"irq_clear_bit: {irq_clear_bit} {irq_clear_bit.__class__}. Expecting a bool.",
            )
        if alert_ctrl.__class__ is not bool:
            raise TypeError(
                f"alert_ctrl: {alert_ctrl} {alert_ctrl.__class__}. Expecting a bool.",
            )
        if alert_sel.__class__ is not bool:
            raise TypeError(
                f"alert_sel: {alert_sel} {alert_sel.__class__}. Expecting a bool.",
            )
        if alert_pol.__class__ is not bool:
            raise TypeError(
                f"alert_pol: {alert_pol} {alert_pol.__class__}. Expecting a bool.",
            )
        if alert_mode.__class__ is not bool:
            raise TypeError(
                f"alert_mode: {alert_mode} {alert_mode.__class__}. Expecting a bool.",
            )

        # Build the send buffer
        self._buf[0] = (hyst_mode << 1) | shdn
        self._buf[1] = (
            (crit_lock << 7)
            | (alerts_lock << 6)
            | (irq_clear_bit << 5)
            | (alert_ctrl << 3)
            | (alert_sel << 2)
            | (alert_pol << 1)
            | alert_mode
        )
        # Write the buffer to the sensor
        self._i2c.writeto_mem(self._addr, self.REG_CFG, self._buf)
        self.refresh()
        # Check if the configuration was set correctly if debug mode is enabled
        if self._debug:
            if self._hyst_mode != hyst_mode:
                print(
                    f"[WARN] Failed to set hyst_mode. Set {hyst_mode} got {self._hyst_mode}",
                )
            if self._shdn != shdn:
                print(
                    f"[WARN] Failed to set shdn. Set {shdn} got {self._shdn}",
                )
            if self._crit_lock != crit_lock:
                print(
                    f"[WARN] Failed to set crit_lock. Set {crit_lock} got {self._crit_lock}",
                )
            if self._irq_clear_bit:
                print(
                    "[WARN] Something wrong with irq_clear_bit. Should always read False"
                )
            if self._alerts_lock != alerts_lock:
                print(
                    f"[WARN] Failed to set alerts_lock. Set {alerts_lock} got {self._alerts_lock}",
                )
            if self._alert_ctrl != alert_ctrl:
                print(
                    f"[WARN] Failed to set alert_ctrl. Set {alert_ctrl} got {self._alert_ctrl}.",
                )
            if self._alert_sel != alert_sel:
                print(
                    f"[WARN] Failed to set alert_sel. Set {alert_sel} got {self._alert_sel}.",
                )
            if self._alert_pol != alert_pol:
                print(
                    f"[WARN] Failed to set alert_pol. Set {alert_pol} got {self._alert_pol}.",
                )
            if self._alert_mode != alert_mode:
                print(
                    f"[WARN] Failed to set alert_mode. Set {alert_mode} got {self._alert_mode}.",
                )

    def _set_alert_limit(self, limit: float, register: int) -> None:
        """Private method to set the alert limit register.

        Intended to be used by the set_alert_XXXXX_limit wrapper methods.
        Args:
            ``limit`` (float | int): The temperature limit to set. Must be between -128 and 127.75.
                It will be rounded to the nearest 0.25°C using round-to-even for halfway values.
            ``register`` (int): The register address to write the limit to.
        Raises:
            ``TypeError``: If the limit is not a float or int.
            ``ValueError``: If the limit is out of the range [-128, 127.75].
            ``ValueError``: If the register address is not valid.
        Debug:
            - Issue a warning if the threshold is outside of the operational range.
            - Issue a warning if the alert limit was not set correctly.
        Returns:
            ``None``
        """

        if limit.__class__ not in [float, int]:
            raise TypeError(
                f"limit: {limit} {limit.__class__}. Expecting float|int.",
            )
        if limit < -128 or limit > 127.75:
            raise ValueError("Temperature out of range [-128, 127.75]")
        # Convert the limit to signed quarter-degree units, rounding halfway values to even
        quarter_degrees: int = round(limit * 4)
        self._set_alert_limit_x4(quarter_degrees, register)

    def _set_alert_limit_x4(self, limit_x4: int, register: int) -> None:
        """Private method to set an alert limit from signed quarter-degree units.

        Args:
            ``limit_x4`` (int): The temperature limit multiplied by four.
            ``register`` (int): The register address to write the limit to.
        Raises:
            ``TypeError``: If limit_x4 is not an int.
            ``ValueError``: If limit_x4 is out of the range [-512, 511].
            ``ValueError``: If the register address is not valid.
        Returns:
            ``None``
        """

        if limit_x4.__class__ is not int:
            raise TypeError(
                f"limit_x4: {limit_x4} {limit_x4.__class__}. Expecting int.",
            )
        if limit_x4 < -512 or limit_x4 > 511:
            raise ValueError("Temperature out of range [-512, 511] quarter-degrees")
        if register not in [self.REG_ATU, self.REG_ATL, self.REG_ATC]:
            raise ValueError(f"Invalid register address {register}")
        if (limit_x4 < -160 or limit_x4 > 500) and self._debug:
            print(
                "[WARN] Temperature outside of operational range, limit won't be ever reached.",
            )

        # Keep the 11-bit two's-complement value and shift it to the register bit position
        raw: int = (limit_x4 & 0x7FF) << 2

        # Split the complete register value into the two bytes sent over I2C
        self._buf[0] = (raw >> 8) & 0xFF
        self._buf[1] = raw & 0xFF

        self._i2c.writeto_mem(self._addr, register, self._buf)

        if self._debug:
            self._i2c.readfrom_mem_into(self._addr, register, self._buf)
            check: int = (self._buf[0] << 8) | self._buf[1]
            if check != raw:
                print(
                    f"[WARN] Failed to set alert limit. Set {raw:016b}",
                    f"but got {check:016b}",
                )

    def shutdown(self) -> None:
        """Put the sensor in low power mode.

        Returns:
            ``None``
        """
        self._set_config(shdn=True)

    def wake(self) -> None:
        """Wake the sensor from low power mode.

        Returns:
            ``None``
        """
        self._set_config(shdn=False)

    def lock_crit_limit(self) -> None:
        """Locks the critical temperature limit.

        When the critical temperature limit is locked, it cannot be changed
        until the sensor is power cycled.
        Returns:
            ``None``
        """
        self._set_config(crit_lock=True)

    def lock_alerts_limit(self) -> None:
        """Locks the alerts limits.

        When the alerts limits are locked, they cannot be changed
        until the sensor is power cycled.
        Returns:
            ``None``
        """
        self._set_config(alerts_lock=True)

    def irq_clear(self) -> None:
        """Clears the interrupt output.

        This method clears the interrupt output.
        Returns:
            ``None``
        """
        self._set_config(irq_clear_bit=True)

    def get_alert_status(self) -> bool:
        """Get the alert status.

        This method reads the alert status from the sensor.
        Returns:
            ``bool``: The alert status.
        """
        self.refresh()
        return self._alert

    def enable_alert(self) -> None:
        """Enable the alert output.

        Returns:
            ``None``
        """
        self._set_config(alert_ctrl=True)

    def disable_alert(self) -> None:
        """Disable the alert output.

        Returns:
            ``None``
        """
        self._set_config(alert_ctrl=False)

    def set_alert_threshold(self, only_crit=False) -> None:
        """Set the alert output select.

        Select if the alert output should be activated only by the critical limit or both critical
        and upper/lower limits.
        Args:
            ``only_crit`` (bool, optional): Set the alert output to only critical. Defaults to False.
        Returns:
            ``None``
        """
        self._set_config(alert_sel=only_crit)

    def set_alert_polarity(self, active_high=False) -> None:
        """Set the alert output polarity.

        Set the alert output polarity to active high or active low.
        Args:
            ``active_high`` (bool, optional): Set the alert output polarity to active high.
                                          Defaults to False.
        Returns:
            ``None``
        """
        self._set_config(alert_pol=active_high)

    def set_alert_mode(self, irq=False) -> None:
        """Set the alert output mode.

        Set the alert output mode to interrupt or comparator.
        Args:
            ``irq`` (bool, optional): Set the alert output mode to interrupt. Defaults to False.
        Returns:
            ``None``
        """
        self._set_config(alert_mode=irq)

    def set_alert_upper_limit(self, upper_limit: float) -> None:
        """Set the alert upper limit.

        Args:
            upper_limit (float | int): The upper limit to set.
                                       It will be rounded to the nearest 0.25°C.
        Raises:
            ``TypeError``: If the limit is not a float or int.
            ``ValueError``: If the limit is out of the range [-128, 127.75].
        Debug:
            - Issue a warning if the threshold is outside of the operational range.
            - Issue a warning if the alert limit was not set correctly.
        Returns:
            ``None``
        """
        self._set_alert_limit(upper_limit, self.REG_ATU)

    def set_alert_upper_limit_x4(self, upper_limit_x4: int) -> None:
        """Set the alert upper limit in signed quarter-degree units.

        Args:
            upper_limit_x4 (int): The upper limit multiplied by four.
        Returns:
            ``None``
        """
        self._set_alert_limit_x4(upper_limit_x4, self.REG_ATU)

    def set_alert_lower_limit(self, lower_limit: float) -> None:
        """Set the alert lower limit.

        Args:
            lower_limit (float | int): The lower limit to set.
                                       It will be rounded to the nearest 0.25°C.
        Raises:
            ``TypeError``: If the limit is not a float or int.
            ``ValueError``: If the limit is out of the range [-128, 127.75].
        Debug:
            - Issue a warning if the threshold is outside of the operational range.
            - Issue a warning if the alert limit was not set correctly.
        Returns:
            ``None``
        """
        self._set_alert_limit(lower_limit, self.REG_ATL)

    def set_alert_lower_limit_x4(self, lower_limit_x4: int) -> None:
        """Set the alert lower limit in signed quarter-degree units.

        Args:
            lower_limit_x4 (int): The lower limit multiplied by four.
        Returns:
            ``None``
        """
        self._set_alert_limit_x4(lower_limit_x4, self.REG_ATL)

    def set_alert_crit_limit(self, crit_limit: float) -> None:
        """Set the alert critical limit.

        Args:
            crit_limit (float | int): The critical limit to set.
                                      It will be rounded to the nearest 0.25°C.
        Raises:
            ``TypeError``: If the limit is not a float or int.
            ``ValueError``: If the limit is out of the range [-128, 127.75].
        Debug:
            - Issue a warning if the threshold is outside of the operational range.
            - Issue a warning if the alert limit was not set correctly.
        Returns:
            ``None``
        """
        self._set_alert_limit(crit_limit, self.REG_ATC)

    def set_alert_crit_limit_x4(self, crit_limit_x4: int) -> None:
        """Set the alert critical limit in signed quarter-degree units.

        Args:
            crit_limit_x4 (int): The critical limit multiplied by four.
        Returns:
            ``None``
        """
        self._set_alert_limit_x4(crit_limit_x4, self.REG_ATC)

    def get_temperature(self) -> float:
        """Get the temperature from the sensor.

        Returns:
            ``float``: The temperature in degrees Celsius.
        """
        return self.get_temperature_x16() / 16

    def get_temperature_x16(self) -> int:
        """Get the temperature as signed sixteenth-degree units.

        Returns:
            ``int``: The temperature multiplied by sixteen.
        """
        # Read the temperature register into the reusable buffer
        self._i2c.readfrom_mem_into(self._addr, self.REG_TEM, self._buf)
        # Remove the alert flags and combine the 13-bit two's-complement value
        temperature_x16: int = ((self._buf[0] & 0x1F) << 8) | self._buf[1]
        # Convert a negative 13-bit value to a signed MicroPython integer
        if temperature_x16 & 0x1000:
            temperature_x16 -= 0x2000
        return temperature_x16

    def get_alert_triggers(self) -> tuple[bool, bool, bool]:
        """Get the alert triggers.

        Trigger bits are not influenced by the alert output mode (compare or interrupt) or by the
        alert polarity (active high or active low) or by the alert control (enable or disable).
        Returns:
            ``tuple[bool, bool, bool]``: A tuple containing the alert triggers.
                The first element is True if the temperature is greater or equal to the critical
                limit.
                The second element is True if the temperature is greater than the upper limit.
                The third element is True if the temperature is less than the lower limit.
        """
        # Read temperature register into the reusable buffer
        self._i2c.readfrom_mem_into(self._addr, self.REG_TEM, self._buf)
        # Extract the 16th bit (last), Ta vs. Tcrit.    False = Ta < Tcrit   | True = Ta >= Tcrit
        ta_tcrit = bool(self._buf[0] & 0x80)
        # Extract the 15th bit, Ta vs. Tupper.          False = Ta <= Tupper | True = Ta > Tupper
        ta_tupper = bool(self._buf[0] & 0x40)
        # Extract the 14th bit, Ta vs Tlower.           False = Ta >= Tlower | True = Ta < Tlower
        ta_tlower = bool(self._buf[0] & 0x20)

        return ta_tcrit, ta_tupper, ta_tlower

    def set_resolution(self, resolution=RES_0_0625) -> None:
        """Set the resolution of the sensor.

        Args:
            resolution (int, optional): The resolution to set.
                Valid values are RES_0_5, RES_0_25, RES_0_125, RES_0_0625.
                Defaults to RES_0_0625.
        Raises:
            TypeError: If the resolution is not an int.
            ValueError: If the resolution is not a valid value.
        Debug:
            - Issue a warning if the resolution was not set correctly.
        Returns:
            ``None``
        """
        # Check if resolution is a compatible value
        if resolution.__class__ is not int:
            raise TypeError(
                f"resolution: {resolution} {resolution.__class__}. Expecting an int.",
            )
        if resolution not in [RES_0_5, RES_0_25, RES_0_125, RES_0_0625]:
            raise ValueError(
                f"Invalid resolution: {resolution}. Value should be between 0 and 3 inclusive.",
            )

        self._buf1[0] = resolution & 0x03
        self._i2c.writeto_mem(self._addr, self.REG_RES, self._buf1)
        if self._debug:
            self._i2c.readfrom_mem_into(self._addr, self.REG_RES, self._buf1)
            if self._buf1[0] != resolution:
                print(
                    f"[WARN] Failed to set resolution. Set {resolution} got {self._buf1[0]}"
                )

    @property
    def hyst_mode(self) -> int:
        """Get the cached hysteresis mode.

        Returns:
            ``int``: The hysteresis mode.
        """
        return self._hyst_mode

    @hyst_mode.setter
    def hyst_mode(self, hyst_mode: int) -> None:
        """Set the hysteresis mode.

        Args:
            ``hyst_mode`` (int): The hysteresis mode to set.
                Valid values are HYST_00, HYST_15, HYST_30, HYST_60.
        """
        if hyst_mode.__class__ is not int:
            raise TypeError(
                f"hyst_mode: {hyst_mode} {hyst_mode.__class__}. Expecting an int.",
            )
        self._set_config(hyst_mode=hyst_mode)

    @property
    def shdn(self) -> bool:
        """Get the cached shutdown mode.

        Returns:
            ``bool``: The shutdown mode.
        """
        return self._shdn

    @property
    def crit_lock(self) -> bool:
        """Get the cached critical temperature register lock.

        Returns:
            ``bool``: The critical temperature register lock.
        """
        return self._crit_lock

    @property
    def alerts_lock(self) -> bool:
        """Get the cached alerts temperature registers lock.

        Returns:
            ``bool``: The alerts temperature registers lock.
        """
        return self._alerts_lock

    @property
    def irq_clear_bit(self) -> bool:
        """Get the cached interrupt clear bit.

        Returns:
            ``bool``: The interrupt clear bit.
        """
        return self._irq_clear_bit

    @property
    def alert(self) -> bool:
        """Get the cached alert status.

        Returns:
            ``bool``: The alert output status.
        """
        return self._alert

    @property
    def alert_ctrl(self) -> bool:
        """Get the cached alert control.

        Returns:
            ``bool``: The alert control.
        """
        return self._alert_ctrl

    @property
    def alert_sel(self) -> bool:
        """Get the cached alert output select.

        Returns:
            ``bool``: The alert output select.
        """
        return self._alert_sel

    @property
    def alert_pol(self) -> bool:
        """Get the cached alert output polarity.

        Returns:
            ``bool``: The alert output polarity.
        """
        return self._alert_pol

    @property
    def alert_mode(self) -> bool:
        """Get the cached alert output mode.

        Returns:
            ``bool``: The alert output mode.
        """
        return self._alert_mode
