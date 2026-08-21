<!-- SPDX-FileCopyrightText: 2024-2026 Marco Miano -->
<!-- SPDX-License-Identifier: MIT -->

# Microchip MCP9808 driver for MicroPython

A single-file module to add support of Microchip MCP9808 precision temperature sensor to MicroPython.

The driver accepts any I2C-compatible object that implements `readfrom_mem_into()` and `writeto_mem()`; it does not import concrete `machine.I2C` classes at runtime.

## Installation

Install the repository package from a host connected to the MicroPython device:

```console
mpremote mip install github:MarcoMiano/mip-mcp9808@v2.0.0
```

Alternatively, install only the module file:

```console
mpremote mip install github:MarcoMiano/mip-mcp9808/mcp9808.py@v2.0.0
```

The package metadata and repository tags follow [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). Tag `v1.0.0` preserves the original API, while `v2.0.0` is the current release and contains deliberate breaking API changes.

When upgrading from v1, provide an I²C object with `readfrom_mem_into()` instead of only `readfrom_mem()`, and call `refresh()` before reading configuration properties when the hardware may have changed outside the driver. See [`CHANGELOG.md`](CHANGELOG.md) for the complete release summary.

## Simple temperature read

```python
import mcp9808
from mcp9808 import MCP9808
from machine import SoftI2C, Pin

# Create I2C object
i2c = SoftI2C(scl=Pin(17), sda=Pin(16), freq=400000)

# Create a simple sensor object with the default address (A0, A1, A2 pin of the sensor are grounded)
t_sensor = MCP9808(i2c=i2c)

# Read the ambient temperature with the default configuration
ambient_temp: float = t_sensor.get_temperature()
```

Each driver instance reuses internal I2C buffers to avoid per-read byte allocations. A single instance is therefore not reentrant and must not be used simultaneously from normal code and an interrupt callback.

## Power-on defaults

The sensor restores all settings to their defaults every time it is power-cycled.

- Power mode: False (`continuous` mode)
- Critical limit lock: False (unlocked)
- Alerts limit lock: False (unlocked)
- Alert status: False (not asserted)
- Alert control: False (alert output disabled)
- Alert threshold selection: False (T<sub>UPPER</sub>, T<sub>LOWER</sub> and T<sub>CRIT</sub>)
- Alert mode: False (`comparator` mode)
- T<sub>HYST</sub> : 0°C
- T<sub>UPPER</sub>: 0°C
- T<sub>LOWER</sub>: 0°C
- T<sub>CRIT</sub>: 0°C
- Resolution: 0.0625°C

## Resolution

The sensor has four possible resolutions with different conversion times:

- 0.5°C: t<sub>CONV</sub> ≃ 30ms or 33 readings per second (typical)
- 0.25°C: t<sub>CONV</sub> ≃ 65ms or 15 readings per second (typical)
- 0.125°C: t<sub>CONV</sub> ≃ 130ms or 7 readings per second (typical)
- 0.0625°C: t<sub>CONV</sub> ≃ 250ms or 4 readings per second (typical)

## Alerts and interrupts

The sensor has optional features to operate an alert output that will trigger when the temperature crosses certain thresholds:

- T<sub>CRIT</sub>: critical threshold alert, trigger the alert when T<sub>A</sub> >= T<sub>CRIT</sub> and reset when T<sub>A</sub> < T<sub>CRIT</sub> - T<sub>HYST</sub>
- T<sub>UPPER</sub>: upper threshold alert, trigger the alert when T<sub>A</sub> > T<sub>UPPER</sub> and reset when T<sub>A</sub> <= T<sub>UPPER</sub> - T<sub>HYST</sub>
- T<sub>LOWER</sub>: lower threshold alert, trigger the alert when T<sub>A</sub> < T<sub>LOWER</sub> - T<sub>HYST</sub> and reset when T<sub>A</sub> >= T<sub>LOWER</sub>

Another parameter used to calculate the trigger or reset point of the alert is the hysteresis T<sub>HYST</sub>. Set it by assigning one of the `HYST_*` constants to the `hyst_mode` property, for example `t_sensor.hyst_mode = HYST_15`.

The alert output can operate in a `comparator` mode or `interrupt` mode:

- `comparator` mode: the alert output is active for the whole duration of the alert and resets itself automatically when the alert condition is resolved
- `interrupt` mode: the alert output activates when an alert condition is met and remains active until `irq_clear()` is called. The T<sub>CRIT</sub> threshold forces the alert output to behave as if it were in `comparator` mode, so a critical alert cannot be cleared until the condition is resolved.

The alert output mode can be chosen with the `set_alert_mode()` method.

The alert output is normally an active low output, but its polarity can be set with the `set_alert_polarity()` method.

The alert can trigger with all three thresholds or only with the critical threshold; choose this with the `set_alert_threshold()` method.

The alerts are normally disabled, it is possible to enable them using the `enable_alert()` method and to disable them using the `disable_alert()` method.

Alert thresholds can be locked using the methods `lock_crit_limit()` and `lock_alerts_limit()`. `lock_crit_limit()` will lock the T<sub>CRIT</sub> threshold. `lock_alerts_limit()` will lock the T<sub>UPPER</sub> and T<sub>LOWER</sub> thresholds.

## Usage

### Properties

Individual configuration bits are available as cached properties:

- `hyst_mode`: Hysteresis mode (int)
- `shdn`: Shutdown mode (bool)
- `crit_lock`: Critical temperature register lock (bool)
- `alerts_lock`: Alerts temperature registers lock (bool)
- `irq_clear_bit`: Interrupt clear bit (bool)
- `alert`: Alert output status (bool)
- `alert_ctrl`: Alert control (bool)
- `alert_sel`: Alert output select (bool)
- `alert_pol`: Alert output polarity (bool)
- `alert_mode`: Alert output mode (bool)

The constructor and every configuration setter refresh these cached values. Property access performs no hidden I2C transaction; call `refresh()` after an external hardware change or before reading time-sensitive status.

### `refresh()` method

The `refresh()` method reads the configuration register once and updates every cached configuration property.

```python
t_sensor.refresh()
if t_sensor.alert:
    handle_alert()
```

The method doesn't accept any argument and returns `None`.

### Module constants

The module contains some handy constants that reference different settings. (C enum style)

- `HYST_00`: 0b00 (0) Hysteresis 0°C
- `HYST_15`: 0b01 (1) Hysteresis 1.5°C
- `HYST_30`: 0b10 (2) Hysteresis 3.0°C
- `HYST_60`: 0b11 (3) Hysteresis 6.0°C
- `RES_0_5`: 0b00 (0) Resolution 0.5°C
- `RES_0_25`: 0b01 (1) Resolution 0.25°C
- `RES_0_125`: 0b10 (2) Resolution 0.125°C
- `RES_0_0625`: 0b11 (3) Resolution 0.0625°C

### `shutdown()` and `wake()` methods

The `shutdown()` method will put the sensor in `low power` mode. The `wake()` method will wake the sensor in `continuous` mode.

```python
# Put the sensor in low power mode
t_sensor.shutdown()

# Wake the sensor (continuous mode)
t_sensor.wake()
```

> In `low power` mode the sensor will draw typically 0.1μA (2μA max) In `continuous` mode the sensor will draw typically 200μA (400μA max)

It's not possible to put the sensor in `low power` mode when either the `crit_lock` or `alerts_lock` bits are set. If in debug mode calling the `shutdown()` method will result in a warning.

The methods don't accept any argument and return `None`.

### `lock_crit_limit()` and `lock_alerts_limit()` methods

The `lock_crit_limit()` will lock the T<sub>CRIT</sub> register (0x4).

The `lock_alerts_limit()` method locks the T<sub>UPPER</sub> and T<sub>LOWER</sub> registers (`0x02` and `0x03`).

```python
# Lock the Tcrit register
t_sensor.lock_crit_limit()

# Lock the Tupper and Tlower registers
t_sensor.lock_alerts_limit()
```

Both locks can only be disabled by a power cycle of the sensor.

The methods don't accept any argument and return `None`.

### `irq_clear()` method

When in `interrupt` mode the alert output has to be acknowledged with the `irq_clear()` method to silence it.

```python
from mcp9808 import MCP9808
from machine import SoftI2C, Pin

# Create I2C object
i2c = SoftI2C(scl=Pin(17), sda=Pin(16), freq=400000)
# Create sensor object
t_sensor = MCP9808(i2c=i2c)
# Set alert mode to IRQ
t_sensor.set_alert_mode(irq=True)


def irq_handler(pin):
    # Only set a pre-existing flag in interrupt context
    global irq_pending
    irq_pending = True


# Create the flag before registering the interrupt
irq_pending = False

# Set the pin that acts as an interrupt
irq_pin = Pin(18, Pin.IN, pull=Pin.PULL_UP)
# Trigger the interrupt on the falling edge
# (use Pin.IRQ_RISING if alert_pol is set to active high)
irq_pin.irq(handler=irq_handler, trigger=Pin.IRQ_FALLING)

# Set the alert limits
t_sensor.set_alert_lower_limit(-10)
t_sensor.set_alert_upper_limit(30)
t_sensor.set_alert_crit_limit(40)
# Enable the alert output
t_sensor.enable_alert()

while True:
    if irq_pending:
        irq_pending = False
        # Perform sensor reads and I2C writes outside interrupt context
        triggers = t_sensor.get_alert_triggers()
        t_sensor.irq_clear()
        if triggers == (False, False, True):
            heater_on()
    stuff()
```

### `enable_alert()` and `disable_alert()` methods

The `enable_alert()` method will enable the alert output.

The `disable_alert()` method will disable the alert output.

```python
# Enable alert output
t_sensor.enable_alert()

# Disable alert output
t_sensor.disable_alert()
```

It's not possible to enable or disable the alert output if either `crit_lock` or `alerts_lock` is set.

It's possible to enable or disable the alert output when in `low power` mode but the alert output will not assert or deassert until the sensor is back in `continuous` mode.

The methods don't accept any argument and return `None`.

### `set_alert_threshold()` method

The `set_alert_threshold()` method sets which thresholds trigger the alert output: only T<sub>CRIT</sub>, or T<sub>CRIT</sub>, T<sub>UPPER</sub>, and T<sub>LOWER</sub>.

```python
# Set the alert output to trigger only on Tcrit
t_sensor.set_alert_threshold(only_crit=True)

# Set the alert output to trigger on Tcrit, Tupper and Tlower
t_sensor.set_alert_threshold(only_crit=False)
```

The method accepts one `bool` argument, `only_crit`:

- if `True` alert output will only trigger on T<sub>CRIT</sub>
- if `False` alert output will trigger on T<sub>CRIT</sub>, T<sub>UPPER</sub>, T<sub>LOWER</sub>

If `alerts_lock` is set, it is not possible to select which thresholds can trigger the alert output. If attempted, a warning is issued in `debug` mode.

The method returns `None`.

### `set_alert_polarity()` method

The `set_alert_polarity()` method sets the alert output polarity to active high or active low.

```python
# Set alert output polarity to active high
t_sensor.set_alert_polarity(active_high=True)

# Set alert output polarity to active low
t_sensor.set_alert_polarity(active_high=False)
```

The method accepts one `bool` argument, `active_high`:

- if `True` alert output will be set to active high (an ongoing alert will be a high signal)
- if `False` alert output will be set to active low (an ongoing alert will be a low signal)

If either `crit_lock` or `alerts_lock` is set, it is not possible to change the polarity of the alert output. If attempted, a warning is issued in `debug` mode.

It's possible to change the polarity of the alert output when the sensor is in `low power` mode, but the alert output will not assert or deassert until the sensor is back in `continuous` mode.

The method returns `None`.

### `set_alert_mode()` method

The `set_alert_mode()` method sets the alert output mode to either `comparator` or `interrupt`. [See the alert overview above.](#alerts-and-interrupts)

```python
# Set alert output to interrupt mode
t_sensor.set_alert_mode(irq=True)

# Set alert output to comparator mode
t_sensor.set_alert_mode(irq=False)
```

The method accepts one `bool` argument, `irq`:

- if `True` alert output mode will be set to `interrupt`
- if `False` alert output mode will be set to `comparator`

If either `crit_lock` or `alerts_lock` is set, it is not possible to change the mode of the alert output. If attempted, a warning is issued in `debug` mode.

It's possible to change the mode of the alert output when the sensor is in `low power` mode, but the alert output will not assert or deassert until the sensor is back in `continuous` mode.

The method returns `None`.

### `set_alert_upper_limit()`, `set_alert_lower_limit()` and `set_alert_crit_limit()` methods

The `set_alert_upper_limit()`, `set_alert_lower_limit()` and `set_alert_crit_limit()` methods set the T<sub>UPPER</sub>, T<sub>LOWER</sub>, and T<sub>CRIT</sub> threshold registers.

```python
# Set Tupper to 43.5°C
t_sensor.set_alert_upper_limit(43.5)
```

The method accepts one `float|int` argument expressed in degrees Celsius. The limit is rounded to the nearest 0.25°C.

The methods type-check the argument and raise `TypeError` if it is not a `float` or `int`. They round to the nearest 0.25°C using round-to-even for halfway values and raise `ValueError` outside the encoded range [-128°C, 127.75°C].

Allocation-sensitive code can set exact signed quarter-degree values without floating-point conversion by using `set_alert_upper_limit_x4()`, `set_alert_lower_limit_x4()`, and `set_alert_crit_limit_x4()`. For example, `set_alert_upper_limit_x4(174)` sets 43.5°C, while `set_alert_lower_limit_x4(-65)` sets -16.25°C.

In debug mode a warning is issued if the argument is outside of the operational range of the sensor [-40°C, 125°C].

It's not possible to change the upper and lower limit register if `alerts_lock` is set. If attempted a warning is issued if in `debug` mode.

It's not possible to change the crit limit register if `crit_lock` is set. If attempted a warning is issued if in `debug` mode.

The methods return `None`.

### `set_resolution()` method

The `set_resolution()` method sets the resolution of the sensor. [See the resolution overview above.](#resolution)

```python
# Set the resolution of the sensor to 0.5°C
t_sensor.set_resolution(RES_0_5)

# Set the resolution of the sensor to 0.25°C
t_sensor.set_resolution(1)
```

The method accepts an `int` argument between 0 and 3 inclusive.

The method raises `TypeError` if the argument is not an `int`, including `bool`, and raises `ValueError` if the integer is outside the valid values.

The resolution can be changed when the sensor is in `low power` mode but the temperature register will not change until the sensor is back in `continuous` mode.

The method returns `None`.

### `get_temperature()` method

The `get_temperature()` method will return the latest temperature sampled by the sensor.

```python
# Get current temperature
temp: float = t_sensor.get_temperature()
```

The method doesn't accept any argument. The method returns a `float`.

The `get_temperature_x16()` method performs the same single I2C transaction but returns a signed integer in sixteenth-degree units. For example, `400` represents 25°C and `-24` represents -1.5°C.

```python
temperature_x16: int = t_sensor.get_temperature_x16()
```

Use the integer method in allocation-sensitive control loops and the float method for convenience.

If the sensor is in `low power` mode it will return the last temperature sampled.

### `get_alert_triggers()` method

The `get_alert_triggers()` method returns the three primitive triggers for the alert output.

```python
# Get the alerts triggers
triggers: tuple[bool, bool, bool] = t_sensor.get_alert_triggers()
```

The method doesn't accept any argument. It returns three `bool` values in a `tuple[bool, bool, bool]`:

1. First element is `True` if T<sub>A</sub> >= T<sub>CRIT</sub>
2. Second element is `True` if T<sub>A</sub> > T<sub>UPPER</sub>
3. Third element is `True` if T<sub>A</sub> < T<sub>LOWER</sub>

Trigger bits are not influenced by `alert_mode`, `alert_pol` or `alert_ctrl`. These are the triggers that can affect the alert output.

If the sensor is in `low_power` mode it will return the triggers based on the last temperature sampled.

### Custom Address

The sensor has a default address of `0x18` or `0b0011000`. This address is partially hardcoded in the silicon. The `A0`, `A1`, and `A2` pins select the last three address bits, allowing up to eight MCP9808 sensors on one I<sup>2</sup>C bus.

```python
# Set the full address
t_sensor = MCP9808(i2c=i2c, addr=0x1A)

# Use the A0, A1, A2 arguments
t_sensor = MCP9808(i2c=i2c, A2=False, A1=True, A0=False)
```

By default, construction verifies the manufacturer and device IDs with two I2C reads and then reads the configuration register. Set `verify=False` to skip the identity reads when startup latency matters, and call `verify()` explicitly later if needed.

The constructor requires `A0`, `A1`, `A2`, `debug`, and `verify` to be actual `bool` values. An explicit `addr` must be an integer in the seven-bit I²C address range from `0x00` through `0x7f`.

```python
t_sensor = MCP9808(i2c=i2c, verify=False)
t_sensor.verify()
```

> Microchip© by custom request can also produce an alternative silicon with an alternate fixed address `0x48` or `0b1001000`. However the 3 custom bits are still present. In this case use a full address with the `addr` argument

### Debug

The module offers built-in debug warnings when the `debug` argument is set to `True`.

```python
t_sensor = MCP9808(i2c=i2c, debug=True)
```

Debug warnings are issued when a register is not set successfully. This can happen when trying to write a register while the sensor is in `low power` mode or when parts of the registers are locked by the `crit_lock` and `alerts_lock` bits.

```python
t_sensor = MCP9808(i2c=i2c, debug=True)

# Lock the alert threshold window
t_sensor.lock_alerts_limit()

# Try to change the alert pin polarity
t_sensor.set_alert_polarity(active_high=True)
```

```console
[WARN] Failed to set alert_pol. Set True got False.
```

## Testing

Run the dependency-free host tests with an in-memory `FakeI2C` register model:

```console
python -m unittest -v test_mcp9808_host.py
```

Run the physical Pico W and MCP9808 suite from the repository root:

```console
mpremote connect /dev/ttyACM0 mount . run test_mcp9808.py
```

Run the allocation and timing benchmark on the same physical setup:

```console
mpremote connect /dev/ttyACM0 mount . run benchmark_mcp9808.py
```

The benchmark power-cycles the sensor through GPIO15, then compares the original allocating float path with the v2 buffered float and integer paths over five rounds. See [`BENCHMARKS.md`](BENCHMARKS.md) for the recorded baselines and interpretation guidance.

## Datasheet

The structured [`MCP9808 datasheet guide`](docs/MCP9808-datasheet-guide.md) summarizes the register and protocol details relevant to this driver. Use Microchip's [official MCP9808 datasheet](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/MCP9808-0.5C-Maximum-Accuracy-Digital-Temperature-Sensor-Data-Sheet-DS20005095B.pdf) as the authoritative source for electrical limits, timing, packages, and ordering information.

## License

The project-authored code and documentation are licensed under the MIT License; each source file uses a concise SPDX identifier and the complete license text is kept in [`LICENSE`](LICENSE).
