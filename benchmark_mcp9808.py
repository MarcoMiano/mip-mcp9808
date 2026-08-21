# SPDX-FileCopyrightText: 2026 Marco Miano
# SPDX-License-Identifier: MIT

"""Microchip MCP9808 on-device performance benchmark for MicroPython

This benchmark compares the original allocating float temperature path with the reusable-buffer
float and integer paths provided by version 2 of the driver.

The sensor is powered from GPIO15 so it can be power-cycled before measurements. SDA is connected
to GPIO16 and SCL is connected to GPIO17, matching the hardware test suite.
"""

import gc
from time import sleep_ms, ticks_diff, ticks_us

from machine import Pin, SoftI2C

from mcp9808 import MCP9808

ITERATIONS = 200
ROUNDS = 5

power_pin = Pin(15, Pin.OUT)
power_pin.off()
sleep_ms(20)
power_pin.on()
sleep_ms(2000)

i2c_bus = SoftI2C(scl=Pin(17), sda=Pin(16), freq=400000)
t_sensor = MCP9808(i2c=i2c_bus)


def old_float_read() -> float:
    """Read and decode a temperature using the original allocating path."""
    buffer = i2c_bus.readfrom_mem(t_sensor.BASE_ADDR, t_sensor.REG_TEM, 2)
    sign = buffer[0] & 0x10
    upper = (buffer[0] << 4) & 0xFF
    lower = (buffer[1] & 0xFF) / 16
    return (upper + lower) - 256 if sign else upper + lower


def benchmark(label: str, function) -> None:
    """Measure elapsed time and retained heap use for one read path."""
    gc.collect()
    free_before = gc.mem_free()
    start = ticks_us()
    for _ in range(ITERATIONS):
        function()
    elapsed = ticks_diff(ticks_us(), start)
    heap_drop = free_before - gc.mem_free()
    print(label, elapsed, heap_drop)


print("firmware", __import__("sys").implementation.version)
print("iterations", ITERATIONS)
print("columns label elapsed_us heap_drop_bytes")
for round_number in range(ROUNDS):
    print("round", round_number + 1)
    benchmark("old_float", old_float_read)
    benchmark("buffered_float", t_sensor.get_temperature)
    benchmark("buffered_integer", t_sensor.get_temperature_x16)
