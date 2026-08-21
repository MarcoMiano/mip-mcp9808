# SPDX-FileCopyrightText: 2026 Marco Miano
# SPDX-License-Identifier: MIT

"""Dependency-free host test suite for the MicroPython MCP9808 driver.

FakeI2C provides a small in-memory register map. It allows tests to provide
temperatures, alert flags and identity values that are difficult or impossible
to reproduce reliably with one physical sensor at room temperature.
"""

import unittest

import mcp9808
from mcp9808 import MCP9808


class FakeI2C:
    """Provide the I2C methods used by MCP9808 and count every transaction."""

    def __init__(
        self,
        manufacturer_id: bytes = b"\x00\x54",
        device_id: bytes = b"\x04\x00",
        config: bytes = b"\x00\x00",
        address: int = MCP9808.BASE_ADDR,
    ) -> None:
        self.address: int = address
        self.registers: dict[int, bytearray] = {
            MCP9808.REG_CFG: bytearray(config),
            MCP9808.REG_ATU: bytearray(2),
            MCP9808.REG_ATL: bytearray(2),
            MCP9808.REG_ATC: bytearray(2),
            MCP9808.REG_TEM: bytearray(2),
            MCP9808.REG_MFR: bytearray(manufacturer_id),
            MCP9808.REG_DEV: bytearray(device_id),
            MCP9808.REG_RES: bytearray((mcp9808.RES_0_0625,)),
        }
        self.read_count: int = 0
        self.write_count: int = 0
        self.read_registers: list[int] = []
        self.write_registers: list[int] = []

    def readfrom_mem_into(self, addr: int, register: int, buf: bytearray) -> None:
        if addr != self.address:
            raise OSError(f"No device at address {addr}")
        self.read_count += 1
        self.read_registers.append(register)
        value = self.registers[register]
        for index in range(len(buf)):
            buf[index] = value[index]

    def writeto_mem(self, addr: int, register: int, buf: bytearray) -> None:
        if addr != self.address:
            raise OSError(f"No device at address {addr}")
        self.write_count += 1
        self.write_registers.append(register)
        value = bytearray(buf)
        if register == MCP9808.REG_CFG:
            old_value = self.registers[register]
            crit_lock = bool(old_value[1] & 0x80)
            alerts_lock = bool(old_value[1] & 0x40)
            # Locked configuration bits retain their previous values
            if crit_lock or alerts_lock:
                value[0] = (value[0] & 0xF9) | (old_value[0] & 0x06)
                if not old_value[0] & 0x01:
                    value[0] &= 0xFE
                value[1] = (value[1] & 0xF4) | (old_value[1] & 0x0B)
            if alerts_lock:
                value[1] = (value[1] & 0xFB) | (old_value[1] & 0x04)
            # Lock bits cannot be cleared before a power-on reset
            value[1] |= old_value[1] & 0xC0
            # Alert status is read-only and interrupt clear reads back as zero
            alert_status = old_value[1] & 0x10
            if value[1] & 0x20:
                alert_status = 0
            value[1] = (value[1] & 0xCF) | alert_status
        elif register == MCP9808.REG_ATC:
            if self.registers[MCP9808.REG_CFG][1] & 0x80:
                return
        elif register in [MCP9808.REG_ATU, MCP9808.REG_ATL]:
            if self.registers[MCP9808.REG_CFG][1] & 0x40:
                return
        self.registers[register] = value

    def set_register(self, register: int, value: bytes) -> None:
        """Set a simulated hardware register without counting an I2C transaction."""
        self.registers[register] = bytearray(value)

    def reset_counts(self) -> None:
        """Reset transaction counters and logs."""
        self.read_count = 0
        self.write_count = 0
        self.read_registers = []
        self.write_registers = []


class TestMCP9808Host(unittest.TestCase):
    def setUp(self) -> None:
        self.i2c = FakeI2C()
        self.sensor = MCP9808(self.i2c)

    def test_constructor_verification(self) -> None:
        self.assertEqual(
            self.i2c.read_registers,
            [MCP9808.REG_MFR, MCP9808.REG_DEV, MCP9808.REG_CFG],
        )
        # Verification can be skipped to save the two identity transactions
        i2c = FakeI2C()
        MCP9808(i2c, verify=False)
        self.assertEqual(i2c.read_registers, [MCP9808.REG_CFG])
        # The public method performs the two checks when requested later
        i2c.reset_counts()
        sensor = MCP9808(i2c, verify=False)
        i2c.reset_counts()
        sensor.verify()
        self.assertEqual(i2c.read_registers, [MCP9808.REG_MFR, MCP9808.REG_DEV])

    def test_constructor_verification_errors(self) -> None:
        with self.assertRaises(RuntimeError):
            MCP9808(FakeI2C(manufacturer_id=b"\x00\x00"))
        with self.assertRaises(RuntimeError):
            MCP9808(FakeI2C(device_id=b"\x00\x00"))
        with self.assertRaises(TypeError):
            MCP9808(FakeI2C(), verify=1)

    def test_constructor_address_and_validation(self) -> None:
        i2c = FakeI2C(address=0x1D)
        sensor = MCP9808(i2c, A0=True, A2=True)
        self.assertEqual(sensor._addr, 0x1D)
        i2c = FakeI2C(address=0x48)
        sensor = MCP9808(i2c, addr=0x48)
        self.assertEqual(sensor._addr, 0x48)
        for invalid_address in [True, 1.5, "24"]:
            with self.assertRaises(TypeError):
                MCP9808(FakeI2C(), addr=invalid_address, verify=False)
        for invalid_address in [-1, 0x80]:
            with self.assertRaises(ValueError):
                MCP9808(FakeI2C(), addr=invalid_address, verify=False)
        for keyword in ["A0", "A1", "A2", "debug"]:
            with self.assertRaises(TypeError):
                MCP9808(FakeI2C(), verify=False, **{keyword: 1})

    def test_temperature_decoding(self) -> None:
        # Positive 25°C is 400 sixteenth-degree units
        self.i2c.set_register(MCP9808.REG_TEM, b"\x01\x90")
        self.assertEqual(self.sensor.get_temperature_x16(), 400)
        self.assertEqual(self.sensor.get_temperature(), 25.0)
        # Negative -1.5°C is -24 sixteenth-degree units
        self.i2c.set_register(MCP9808.REG_TEM, b"\x1f\xe8")
        self.assertEqual(self.sensor.get_temperature_x16(), -24)
        self.assertEqual(self.sensor.get_temperature(), -1.5)

    def test_temperature_alert_flags(self) -> None:
        # Set all three alert flags while retaining a positive 25°C value
        self.i2c.set_register(MCP9808.REG_TEM, b"\xe1\x90")
        self.assertEqual(self.sensor.get_temperature_x16(), 400)
        self.assertEqual(self.sensor.get_alert_triggers(), (True, True, True))

    def test_temperature_transaction_count(self) -> None:
        self.i2c.reset_counts()
        self.sensor.get_temperature_x16()
        self.assertEqual(self.i2c.read_count, 1)
        self.sensor.get_temperature()
        self.assertEqual(self.i2c.read_count, 2)

    def test_alert_limit_encoding(self) -> None:
        cases: tuple = (
            (-128, b"\x18\x00"),
            (-16.25, b"\x1e\xfc"),
            (-1.5, b"\x1f\xe8"),
            (-0.25, b"\x1f\xfc"),
            (0, b"\x00\x00"),
            (0.25, b"\x00\x04"),
            (15.75, b"\x00\xfc"),
            (16, b"\x01\x00"),
            (43.5, b"\x02\xb8"),
            (90, b"\x05\xa0"),
            (127.75, b"\x07\xfc"),
        )
        for limit, expected in cases:
            self.sensor.set_alert_lower_limit(limit)
            self.assertEqual(self.i2c.registers[MCP9808.REG_ATL], expected)

    def test_alert_limit_rounding(self) -> None:
        cases: tuple = (
            (1.24, b"\x00\x14"),
            (-1.24, b"\x1f\xec"),
            (1.125, b"\x00\x10"),
            (1.375, b"\x00\x18"),
            (-1.125, b"\x1f\xf0"),
            (-1.375, b"\x1f\xe8"),
        )
        for limit, expected in cases:
            self.sensor.set_alert_lower_limit(limit)
            self.assertEqual(self.i2c.registers[MCP9808.REG_ATL], expected)

    def test_alert_limit_integer_api(self) -> None:
        self.sensor.set_alert_upper_limit_x4(65)
        self.sensor.set_alert_lower_limit_x4(-65)
        self.sensor.set_alert_crit_limit_x4(360)
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATU], b"\x01\x04")
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATL], b"\x1e\xfc")
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATC], b"\x05\xa0")

    def test_alert_limit_register_selection(self) -> None:
        self.sensor.set_alert_upper_limit(16.25)
        self.sensor.set_alert_lower_limit(43.5)
        self.sensor.set_alert_crit_limit(90)
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATU], b"\x01\x04")
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATL], b"\x02\xb8")
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATC], b"\x05\xa0")

    def test_alert_limit_validation(self) -> None:
        with self.assertRaises(ValueError):
            self.sensor.set_alert_lower_limit(-128.01)
        with self.assertRaises(ValueError):
            self.sensor.set_alert_upper_limit(127.76)
        with self.assertRaises(TypeError):
            self.sensor.set_alert_crit_limit(True)
        with self.assertRaises(ValueError):
            self.sensor.set_alert_lower_limit_x4(-513)
        with self.assertRaises(ValueError):
            self.sensor.set_alert_upper_limit_x4(512)
        with self.assertRaises(TypeError):
            self.sensor.set_alert_crit_limit_x4(1.0)

    def test_cached_properties_and_refresh(self) -> None:
        self.i2c.reset_counts()
        # External hardware changes do not cause hidden reads from properties
        self.i2c.set_register(MCP9808.REG_CFG, b"\x00\x0a")
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_pol)
        self.assertEqual(self.i2c.read_count, 0)
        # One explicit refresh updates every cached property
        self.sensor.refresh()
        self.assertTrue(self.sensor.alert_ctrl)
        self.assertTrue(self.sensor.alert_pol)
        self.assertEqual(self.i2c.read_count, 1)

    def test_configuration_properties_are_read_only(self) -> None:
        for property_name in [
            "shdn",
            "crit_lock",
            "alerts_lock",
            "irq_clear_bit",
            "alert",
            "alert_ctrl",
            "alert_sel",
            "alert_pol",
            "alert_mode",
        ]:
            with self.assertRaises(AttributeError):
                setattr(self.sensor, property_name, True)

    def test_configuration_write_preserves_cached_bits(self) -> None:
        self.i2c.set_register(MCP9808.REG_CFG, b"\x00\x0d")
        self.sensor.refresh()
        self.i2c.reset_counts()
        self.sensor.set_alert_polarity(active_high=True)
        self.assertEqual(self.i2c.registers[MCP9808.REG_CFG], b"\x00\x0f")
        self.assertEqual(self.i2c.write_count, 1)
        self.assertEqual(self.i2c.read_count, 1)

    def test_alert_status_single_read(self) -> None:
        self.i2c.set_register(MCP9808.REG_CFG, b"\x00\x10")
        self.i2c.reset_counts()
        self.assertTrue(self.sensor.get_alert_status())
        self.assertEqual(self.i2c.read_count, 1)

    def test_interrupt_clear_semantics(self) -> None:
        self.i2c.set_register(MCP9808.REG_CFG, b"\x00\x19")
        self.sensor.refresh()
        self.i2c.reset_counts()
        self.sensor.irq_clear()
        self.assertEqual(self.i2c.registers[MCP9808.REG_CFG], b"\x00\x09")
        self.assertFalse(self.sensor.irq_clear_bit)
        self.assertFalse(self.sensor.alert)
        self.assertEqual(self.i2c.write_count, 1)
        self.assertEqual(self.i2c.read_count, 1)

    def test_lock_behaviour(self) -> None:
        self.sensor.set_alert_upper_limit(10)
        self.sensor.set_alert_lower_limit(-10)
        self.sensor.set_alert_crit_limit(20)
        self.sensor.lock_alerts_limit()
        self.sensor.enable_alert()
        self.sensor.set_alert_threshold(only_crit=True)
        self.sensor.set_alert_polarity(active_high=True)
        self.sensor.set_alert_mode(irq=True)
        self.sensor.hyst_mode = mcp9808.HYST_60
        self.sensor.shutdown()
        self.sensor.set_alert_upper_limit(30)
        self.sensor.set_alert_lower_limit(-30)
        self.assertTrue(self.sensor.alerts_lock)
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_sel)
        self.assertFalse(self.sensor.alert_pol)
        self.assertFalse(self.sensor.alert_mode)
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_00)
        self.assertFalse(self.sensor.shdn)
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATU], b"\x00\xa0")
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATL], b"\x1f\x60")
        self.sensor.lock_crit_limit()
        self.sensor.set_alert_crit_limit(40)
        self.assertTrue(self.sensor.crit_lock)
        self.assertEqual(self.i2c.registers[MCP9808.REG_ATC], b"\x01\x40")

    def test_resolution_and_hysteresis_validation(self) -> None:
        for invalid_resolution in [True, 1.0, None]:
            with self.assertRaises(TypeError):
                self.sensor.set_resolution(invalid_resolution)
        with self.assertRaises(ValueError):
            self.sensor.set_resolution(4)
        for invalid_hysteresis in [True, 1.0, None]:
            with self.assertRaises(TypeError):
                self.sensor.hyst_mode = invalid_hysteresis
        with self.assertRaises(ValueError):
            self.sensor.hyst_mode = 4


if __name__ == "__main__":
    unittest.main()
