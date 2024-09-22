import unittest
import mcp9808
from mcp9808 import MCP9808
from machine import SoftI2C, Pin
from time import sleep_ms


class TestMCP9808(unittest.TestCase):
    def setUp(self):
        self.power = Pin(15, Pin.OUT)
        self.sensor_reset()
        self.i2c = SoftI2C(scl=Pin(17), sda=Pin(16), freq=400000)
        self.sensor = MCP9808(self.i2c)

    def sensor_reset(self) -> None:
        self.power.off()
        sleep_ms(20)
        self.power.on()

    def test_powerup_defaults(self) -> None:
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_00)
        self.assertFalse(self.sensor.shdn)
        self.assertFalse(self.sensor.crit_lock)
        self.assertFalse(self.sensor.window_lock)
        self.assertFalse(self.sensor.irq_clear_bit)
        self.assertFalse(self.sensor.alert)
        self.assertFalse(self.sensor.alert_ctrl)
        self.assertFalse(self.sensor.alert_sel)
        self.assertFalse(self.sensor.alert_pol)
        self.assertFalse(self.sensor.alert_mode)

    def test_hysteresis_set(self) -> None:
        self.sensor.set_hysteresis_mode(hyst_mode=mcp9808.HYST_15)
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_15)
        self.sensor.set_hysteresis_mode(hyst_mode=mcp9808.HYST_30)
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_30)
        self.sensor.set_hysteresis_mode(hyst_mode=mcp9808.HYST_60)
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_60)
        self.sensor.set_hysteresis_mode(hyst_mode=mcp9808.HYST_00)
        self.assertEqual(self.sensor.hyst_mode, mcp9808.HYST_00)

    def test_shutdown(self) -> None:
        self.sensor.shutdown()
        self.assertTrue(self.sensor.shdn)
        self.sensor.shutdown(wake=True)
        self.assertFalse(self.sensor.shdn)

    def test_crit_lock(self) -> None:
        self.sensor.lock_crit_limit()
        self.assertTrue(self.sensor.crit_lock)
        self.sensor.enable_alert()
        self.assertFalse(self.sensor.alert_ctrl)
        self.sensor.lock_crit_limit(unlock=True)
        self.assertTrue(self.sensor.crit_lock)
        self.sensor_reset()

    def test_window_lock(self) -> None:
        self.sensor.lock_window_limit()
        self.assertTrue(self.sensor.window_lock)
        self.sensor.enable_alert()
        self.assertFalse(self.sensor.alert_ctrl)
        self.sensor.lock_window_limit(unlock=True)
        self.assertTrue(self.sensor.window_lock)
        self.sensor_reset()

    def test_interrupt(self) -> None:
        self.sensor.irq_clear()


if __name__ == "__main__":
    unittest.main()
