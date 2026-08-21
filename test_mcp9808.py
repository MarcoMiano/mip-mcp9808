# SPDX-FileCopyrightText: 2024-2026 Marco Miano
# SPDX-License-Identifier: MIT

"""Microchip MCP9808 driver/sensor test suite for MicroPython

THE MCP9808 IS A COMPLEX SENSOR WITH MANY FEATURES. IT IS ADVISABLE TO READ THE DATASHEET.

DO NOT ACCESS RESERVED REGISTERS WITH ADDRESSES HIGHER THAN 0x08.
ACCESSING THEM IS UNSUPPORTED AND MAY CAUSE UNSPECIFIED SENSOR BEHAVIOUR.

This test suite is designed to check the correct operation of the MCP9808 sensor driver and the
sensor itself. It is advisable to run this test suite if anything is changed in the driver code,
or if the sensor is not behaving right.
This test suite is written and tested on a Raspberry Pi Pico W Board with MicroPython v1.24.1.



Pin connections:
    - POWER: pin15
             The sensor is powered from a GPIO pin to be able to power cycle the sensor during the
             tests.
             CHECK THAT YOUR GPIO PIN CAN SUPPLY ENOUGH CURRENT AND VOLTAGE TO POWER THE SENSOR.
             (2.7V-5.5V AT 0.4mA)
    - SDA:   pin16
    - SCL:   pin17
    - ALERT: pin18
             The sensor alert pin is connected to a GPIO pin to check if the sensor is triggering
             alerts. The pin is pulled to VCC via the board internal pull-up resistor.
             The pin is active low. Wire an external pull-up resistor to VCC if needed.

Prerequisites:
    - Install the unittest module in the MicroPython device.
    - Install the MCP9808 driver in the MicroPython device.
    - Wire the sensor to the board as described above.
    - Run the test suite.
"""

import unittest
from time import sleep_ms

from machine import Pin, SoftI2C

import mcp9808
from mcp9808 import MCP9808

##############################################
# Change the pin numbers to match your setup #
##############################################
power_pin = Pin(15, Pin.OUT)
alert_pin = Pin(18, Pin.IN, pull=Pin.PULL_UP)
i2c_bus = SoftI2C(scl=Pin(17), sda=Pin(16), freq=400000)


class CountingI2C:
    """Proxy an I2C object and count register reads."""

    def __init__(self, i2c: SoftI2C) -> None:
        self.i2c: SoftI2C = i2c
        self.read_count: int = 0

    def readfrom_mem(self, addr: int, register: int, size: int) -> bytes:
        self.read_count += 1
        return self.i2c.readfrom_mem(addr, register, size)

    def readfrom_mem_into(self, addr: int, register: int, buf: bytearray) -> None:
        self.read_count += 1
        self.i2c.readfrom_mem_into(addr, register, buf)

    def writeto_mem(self, addr: int, register: int, buf: bytes) -> None:
        self.i2c.writeto_mem(addr, register, buf)


class TestMCP9808(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.power: Pin = power_pin
        cls.alert: Pin = alert_pin
        cls.i2c: SoftI2C = i2c_bus

    def setUp(self) -> None:
        self.power.off()
        sleep_ms(20)
        self.power.on()
        sleep_ms(2000)
        self.sensor = MCP9808(self.i2c)

    def _assert_alert_limit_encodings(self, cases: tuple) -> None:
        failures: list = []
        for limit, expected in cases:
            try:
                self.sensor.set_alert_lower_limit(limit)
                actual = self.i2c.readfrom_mem(
                    self.sensor.BASE_ADDR,
                    self.sensor.REG_ATL,
                    2,
                )
                if actual != expected:
                    failures.append(
                        f"{limit}: got {actual.hex()}, expected {expected.hex()}",
                    )
            except ValueError as error:
                failures.append(
                    f"{limit}: got {error.__class__.__name__}: {error}, "
                    f"expected {expected.hex()}",
                )
        self.assertEqual(failures, [])

    def test_powerup_defaults(self) -> None:
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_00)
        self.assertFalse(self.sensor.shdn)
        self.assertFalse(self.sensor.crit_lock)
        self.assertFalse(self.sensor.alerts_lock)
        self.assertFalse(self.sensor.irq_clear_bit)
        self.assertFalse(self.sensor.alert)
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_sel)
        self.assertFalse(self.sensor.alert_pol)
        self.assertFalse(self.sensor.alert_mode)

    def test_read_only_config_properties(self) -> None:
        # Check that callers cannot overwrite values without modifying the sensor
        with self.assertRaises(AttributeError):
            self.sensor.irq_clear_bit = True
        with self.assertRaises(AttributeError):
            self.sensor.alert_pol = True
        # Set the alert polarity through the public method and check the property
        self.sensor.set_alert_polarity(active_high=True)
        self.assertTrue(self.sensor.alert_pol)

    def test_cached_properties_and_refresh(self) -> None:
        counting_i2c = CountingI2C(self.i2c)
        sensor = MCP9808(counting_i2c)
        counting_i2c.read_count = 0
        # Reading cached properties must not perform hidden I2C transactions
        self.assertFalse(sensor.shdn)
        self.assertFalse(sensor.alert_ctrl)
        self.assertFalse(sensor.alert_pol)
        self.assertEqual(counting_i2c.read_count, 0)
        # An explicit refresh performs exactly one configuration-register read
        sensor.refresh()
        self.assertEqual(counting_i2c.read_count, 1)

    def test_constructor_verification(self) -> None:
        counting_i2c = CountingI2C(self.i2c)
        # Default construction reads two identity registers and the configuration
        MCP9808(counting_i2c)
        self.assertEqual(counting_i2c.read_count, 3)
        # Verification can be skipped, leaving only the configuration read
        counting_i2c.read_count = 0
        sensor = MCP9808(counting_i2c, verify=False)
        self.assertEqual(counting_i2c.read_count, 1)
        # Verification remains available explicitly when it is needed later
        counting_i2c.read_count = 0
        sensor.verify()
        self.assertEqual(counting_i2c.read_count, 2)

    def test_hysteresis_set(self) -> None:
        self.sensor.hyst_mode = mcp9808.HYST_15
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_15)
        self.sensor.hyst_mode = mcp9808.HYST_30
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_30)
        self.sensor.hyst_mode = mcp9808.HYST_60
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_60)
        self.sensor.hyst_mode = mcp9808.HYST_00
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_00)

    def test_alert_limit_positive_encoding(self) -> None:
        cases: tuple = (
            (0, b"\x00\x00"),
            (0.25, b"\x00\x04"),
            (15.75, b"\x00\xfc"),
            (16, b"\x01\x00"),
            (43.5, b"\x02\xb8"),
            (90, b"\x05\xa0"),
        )
        self._assert_alert_limit_encodings(cases)

    def test_alert_limit_negative_encoding(self) -> None:
        cases: tuple = (
            (-16.25, b"\x1e\xfc"),
            (-1.5, b"\x1f\xe8"),
            (-0.25, b"\x1f\xfc"),
        )
        self._assert_alert_limit_encodings(cases)

    def test_alert_limit_endpoints(self) -> None:
        cases: tuple = (
            (-128, b"\x18\x00"),
            (127.75, b"\x07\xfc"),
        )
        self._assert_alert_limit_encodings(cases)

    def test_alert_limit_rounding(self) -> None:
        cases: tuple = (
            (1.24, b"\x00\x14"),
            (-1.24, b"\x1f\xec"),
            (1.125, b"\x00\x10"),
            (1.375, b"\x00\x18"),
            (-1.125, b"\x1f\xf0"),
            (-1.375, b"\x1f\xe8"),
        )
        self._assert_alert_limit_encodings(cases)

    def test_alert_limit_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            self.sensor.set_alert_lower_limit(-128.01)
        with self.assertRaises(ValueError):
            self.sensor.set_alert_lower_limit(127.76)

    def test_alert_limit_invalid_type(self) -> None:
        with self.assertRaises(TypeError):
            self.sensor.set_alert_lower_limit(None)
        with self.assertRaises(TypeError):
            self.sensor.set_alert_lower_limit("1")
        with self.assertRaises(TypeError):
            self.sensor.set_alert_lower_limit(True)

    def test_alert_limit_register_selection(self) -> None:
        self.sensor.set_alert_upper_limit(16.25)
        self.sensor.set_alert_lower_limit(43.5)
        self.sensor.set_alert_crit_limit(90)
        self.assertEqual(
            self.i2c.readfrom_mem(
                self.sensor.BASE_ADDR,
                self.sensor.REG_ATU,
                2,
            ),
            b"\x01\x04",
        )
        self.assertEqual(
            self.i2c.readfrom_mem(
                self.sensor.BASE_ADDR,
                self.sensor.REG_ATL,
                2,
            ),
            b"\x02\xb8",
        )
        self.assertEqual(
            self.i2c.readfrom_mem(
                self.sensor.BASE_ADDR,
                self.sensor.REG_ATC,
                2,
            ),
            b"\x05\xa0",
        )

    def test_alert_limit_integer_api(self) -> None:
        self.sensor.set_alert_upper_limit_x4(65)
        self.sensor.set_alert_lower_limit_x4(-65)
        self.sensor.set_alert_crit_limit_x4(360)
        self.assertEqual(
            self.i2c.readfrom_mem(
                self.sensor.BASE_ADDR,
                self.sensor.REG_ATU,
                2,
            ),
            b"\x01\x04",
        )
        self.assertEqual(
            self.i2c.readfrom_mem(
                self.sensor.BASE_ADDR,
                self.sensor.REG_ATL,
                2,
            ),
            b"\x1e\xfc",
        )
        self.assertEqual(
            self.i2c.readfrom_mem(
                self.sensor.BASE_ADDR,
                self.sensor.REG_ATC,
                2,
            ),
            b"\x05\xa0",
        )
        with self.assertRaises(ValueError):
            self.sensor.set_alert_lower_limit_x4(-513)
        with self.assertRaises(ValueError):
            self.sensor.set_alert_upper_limit_x4(512)
        with self.assertRaises(TypeError):
            self.sensor.set_alert_crit_limit_x4(1.0)

    def test_temperature_integer_api(self) -> None:
        temperature_x16 = self.sensor.get_temperature_x16()
        self.assertEqual(temperature_x16.__class__, int)
        # The float convenience API must remain within one sample step
        temperature = self.sensor.get_temperature()
        self.assertTrue(abs(temperature_x16 / 16 - temperature) <= 0.0625)

    def test_alert_status_single_read(self) -> None:
        counting_i2c = CountingI2C(self.i2c)
        sensor = MCP9808(counting_i2c)
        counting_i2c.read_count = 0
        sensor.get_alert_status()
        self.assertEqual(counting_i2c.read_count, 1)

    def test_shutdown(self) -> None:
        self.sensor.shutdown()
        self.assertTrue(self.sensor.shdn)
        self.sensor.wake()
        self.assertFalse(self.sensor.shdn)

    def test_crit_lock(self) -> None:
        # Lock critical limit register
        self.sensor.lock_crit_limit()
        # Check if the critical limit register is locked
        self.assertTrue(self.sensor.crit_lock)
        # Try to enable alerts
        self.sensor.enable_alert()
        # Alerts should not be enabled
        self.assertFalse(self.sensor.alert_ctrl)
        # Reset sensor
        self.setUp()
        # Check if the critical limit register is unlocked
        self.assertFalse(self.sensor.crit_lock)

    def test_alerts_lock(self) -> None:
        # Lock alerts limit registers
        self.sensor.lock_alerts_limit()
        # Check if the alerts limit registers are locked
        self.assertTrue(self.sensor.alerts_lock)
        # Try to enable alerts
        self.sensor.enable_alert()
        # Alerts should not be enabled
        self.assertFalse(self.sensor.alert_ctrl)
        # Reset sensor
        self.setUp()
        # Check if the alerts limit registers are unlocked
        self.assertFalse(self.sensor.alerts_lock)

    def test_alert_control(self) -> None:
        # Get current temperature
        temp: float = self.sensor.get_temperature()
        # Enable alerts
        self.sensor.enable_alert()
        # Check if alerts are enabled
        self.assertTrue(self.sensor.alert_ctrl)
        # Set lower limit to current temperature + 10°C
        self.sensor.set_alert_lower_limit(temp + 10)
        sleep_ms(10)
        # Check if hardware alert is triggered
        self.assertEqual(self.alert.value(), 0)
        # Disable alerts
        self.sensor.disable_alert()
        # Check if alerts are disabled
        self.assertFalse(self.sensor.alert_ctrl)
        # Check if hardware alert is cleared
        self.assertEqual(self.alert.value(), 1)

    def test_comp_lower_alerts(self) -> None:
        # Get current temperature
        temp: float = self.sensor.get_temperature()
        # Check if alert is disabled and in comparator mode
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_mode)
        # Set upper limit to 100°C
        #     crit limit to 100°C
        #     lower limit to current temperature + 10°C
        self.sensor.set_alert_upper_limit(100)
        self.sensor.set_alert_crit_limit(100)
        self.sensor.set_alert_lower_limit(temp + 10)
        # Enable alerts
        self.sensor.enable_alert()
        sleep_ms(10)
        # Check if hardware alert is triggered
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is set
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, True))
        # Set lower limit to current temperature - 10°C (simulating temperature increase)
        self.sensor.set_alert_lower_limit(temp - 10)
        sleep_ms(10)
        # Check if hardware alert is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is cleared
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, False))

    def test_comp_upper_alerts(self) -> None:
        # Get current temperature
        temp: float = self.sensor.get_temperature()
        # Check if alert is disabled and in comparator mode
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_mode)
        # Set lower limit to 0°C
        #     crit limit to 100°C
        #     upper limit to current temperature - 10°C
        self.sensor.set_alert_lower_limit(0)
        self.sensor.set_alert_crit_limit(100)
        self.sensor.set_alert_upper_limit(temp - 10)
        # Enable alerts
        self.sensor.enable_alert()
        sleep_ms(10)
        # Check if hardware alert is triggered
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is set
        self.assertEqual(self.sensor.get_alert_triggers(), (False, True, False))
        # Set lower limit to current temperature + 10°C (simulating temperature drop)
        self.sensor.set_alert_upper_limit(temp + 10)
        sleep_ms(10)
        # Check if hardware alert is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is cleared
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, False))

    def test_comp_crit_alerts(self) -> None:
        # Get current temperature
        temp: float = self.sensor.get_temperature()
        # Check if alert is disabled and in comparator mode
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_mode)
        # Set lower limit to 0°C
        #     upper limit to 100°C
        #     crit limit to current temperature - 10°C
        self.sensor.set_alert_lower_limit(0)
        self.sensor.set_alert_upper_limit(100)
        self.sensor.set_alert_crit_limit(temp - 10)
        # Enable alerts
        self.sensor.enable_alert()
        sleep_ms(10)
        # Check if hardware alert is triggered
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is set
        self.assertEqual(self.sensor.get_alert_triggers(), (True, False, False))
        # Set lower limit to current temperature + 10°C (simulating temperature drop)
        self.sensor.set_alert_crit_limit(temp + 10)
        sleep_ms(10)
        # Check if hardware alert is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is cleared
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, False))

    def test_irq_lower_alerts(self) -> None:
        # Get current temperature
        temp: float = self.sensor.get_temperature()
        # Check if alert is disabled and in comparator mode
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_mode)
        # Set and check alert mode to IRQ
        self.sensor.set_alert_mode(irq=True)
        self.assertTrue(self.sensor.alert_mode)
        # Set lower limit to current temperature + 10°C
        #     upper limit to 100°C
        #     crit limit to 100°C
        self.sensor.set_alert_lower_limit(temp + 10)
        self.sensor.set_alert_upper_limit(100)
        self.sensor.set_alert_crit_limit(100)
        # Enable alerts
        self.sensor.enable_alert()
        sleep_ms(10)
        # Check if hardware IRQ is triggered
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is set
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, True))
        # Clear IRQ
        self.sensor.irq_clear()
        # Check if hardware IRQ is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is still set
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, True))
        # Set lower limit to current temperature - 10°C (simulating temperature increase)
        self.sensor.set_alert_lower_limit(temp - 10)
        sleep_ms(10)
        # Check if hardware IRQ is triggered
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is cleared
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, False))
        # Clear IRQ
        self.sensor.irq_clear()
        # Check if alert is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is cleared
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, False))

    def test_irq_upper_alerts(self) -> None:
        # Get current temperature
        temp: float = self.sensor.get_temperature()
        # Check if alert is disabled and in comparator mode
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_mode)
        # Set and check alert mode to IRQ
        self.sensor.set_alert_mode(irq=True)
        self.assertTrue(self.sensor.alert_mode)
        # Set lower limit 0°C
        #     upper limit to current temperature - 10°C
        #     crit limit to 100°C
        self.sensor.set_alert_lower_limit(0)
        self.sensor.set_alert_upper_limit(temp - 10)
        self.sensor.set_alert_crit_limit(100)
        # Enable alerts
        self.sensor.enable_alert()
        sleep_ms(10)
        # Check if hardware IRQ is triggered
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is set
        self.assertEqual(self.sensor.get_alert_triggers(), (False, True, False))
        # Clear IRQ
        self.sensor.irq_clear()
        # Check if hardware IRQ is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is still set
        self.assertEqual(self.sensor.get_alert_triggers(), (False, True, False))
        # Set upper limit to current temperature + 10°C (simulating temperature drop)
        self.sensor.set_alert_upper_limit(temp + 10)
        sleep_ms(10)
        # Check if hardware IRQ is triggered
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is cleared
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, False))
        # Clear IRQ
        self.sensor.irq_clear()
        # Check if alert is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is cleared
        self.assertEqual(self.sensor.get_alert_triggers(), (False, False, False))

    def test_irq_crit_alerts(self) -> None:
        # Get current temperature
        temp: float = self.sensor.get_temperature()
        # Check if alert is disabled and in comparator mode
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_mode)
        # Set and check alert mode to IRQ
        self.sensor.set_alert_mode(irq=True)
        self.assertTrue(self.sensor.alert_mode)
        # Set lower limit 0°C
        #     upper limit to current temperature - 10°C
        #     crit limit to 100°C
        self.sensor.set_alert_lower_limit(0)
        self.sensor.set_alert_upper_limit(temp - 10)
        self.sensor.set_alert_crit_limit(100)
        # Enable alerts (first IRQ from upper limit)
        self.sensor.enable_alert()
        sleep_ms(10)
        # Check if alert is triggered
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is set
        self.assertEqual(self.sensor.get_alert_triggers(), (False, True, False))
        # Clear IRQ
        self.sensor.irq_clear()
        # Check if alert is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is still set
        self.assertEqual(self.sensor.get_alert_triggers(), (False, True, False))
        # Set crit limit to current temperature - 5°C (to trigger second IRQ from crit limit)
        self.sensor.set_alert_crit_limit(temp - 5)
        sleep_ms(10)
        # Check if alert is triggered (second IRQ from crit limit)
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is set
        self.assertEqual(self.sensor.get_alert_triggers(), (True, True, False))
        # Clear IRQ
        self.sensor.irq_clear()
        # Check if alert is NOT cleared
        self.assertEqual(self.alert.value(), 0)
        # Check if correct alert trigger bit is still set
        self.assertEqual(self.sensor.get_alert_triggers(), (True, True, False))
        # Set crit limit to current temperature + 5°C (simulating temperature drop)
        self.sensor.set_alert_crit_limit(temp + 5)
        sleep_ms(10)
        # Check if alert is cleared
        self.assertEqual(self.alert.value(), 1)
        # Check if correct alert trigger bit is cleared
        self.assertEqual(self.sensor.get_alert_triggers(), (False, True, False))


if __name__ == "__main__":
    unittest.main()
