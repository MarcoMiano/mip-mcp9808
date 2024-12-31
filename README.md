# Microchip MCP9808 driver for MicroPython
A single-file module to add support of Microchip MCP9808 precision temperature sensor to MicroPython.

## Simple temperature read
``` python
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

## Power-on defaults
The sensor will restore all the settings to the defaults every time is power cycled.
- Power mode: False (`continuous` mode)
- Critical limit lock: False (unlocked)
- Alerts limit lock: False (unlocked)
- Alert status: False (not asserted)
- Alert control: False (alert output disabled)
- Alert threshold selection: False (T~UPPER~, T~LOWER~ and T~CRIT~)
- Alert mode: False (`comparator` mode)
- T~HYST~ : 0°C
- T~UPPER~: 0°C
- T~LOWER~: 0°C
- T~CRIT~: 0°C
- Resolution: 0.0625°C

## Resolution
The sensor has 4 possible resolutions with different conversion times:
- 0.5°C: t~CONV~ ≃ 30ms or 33 readings per second (typical)
- 0.25°C: t~CONV~ ≃ 65ms or 15 readings per second (typical)
- 0.125°C: t~CONV~ ≃ 130ms or 7 readings per second (typical)
- 0.0625°C: t~CONV~ ≃ 250ms or 4 readings per second (typical)

## Alerts and interrupts
The sensor has optional features to operate an alert output that will trigger when the temperature cross  certain thresholds:
- T~CRIT~: critical threshold alert, trigger the alert when T~A~ >= T~CRIT~ and reset when T~A~ < T~CRIT~ - T~HYST~ 
- T~UPPER~: upper threshold alert, trigger the alert when T~A~ > T~UPPER~ and reset when T~A~ <= T~UPPER~ - T~HYST~
- T~LOWER~: lower threshold alert, trigger the alert when T~A~ < T~LOWER~ - T~HYST~ and reset when T~A~ >= T~LOWER~

Another parameter used to calculate the trigger or reset point of the alert is the Hysteresis T~HYST~. It can be set using the `set_hysteresis_mode()` method.

The alert output can operate in a `comparator` mode or `interrupt` mode:
- `comparator` mode: the alert output is active for the whole duration of the alert and will reset it self automatically when the alert condition is resolved
- `interrupt` mode: the alert output will activate when a alert condition is met and will remain active unless `irq_clear()` method is called. The T~CRIT~ threshold will force the alert output to behave as if in `comparator` mode so when the critical threshold trigger an alert it will not be possible to clear the interrupt but it will reset itself when the alert condition is resolved.

The alert output mode can be chosen with the `set_alert_mode()` method.

The alert output is normally an active low output, but its polarity can be set with the `set_alert_polarity()` method.

The alert can trigger with all three threshold or only with the critical threshold, this can be chosen with the `set_alert_threshold()` method.

The alerts are normally disabled, it is possible to enable them using the `enable_alert()` method and to disable them using the `disable_alert()` method.

Alert thresholds can be locked using the methods `lock_crit_limit()` and `lock_alerts_limit()`.
`lock_crit_limit()` will lock the T~CRIT~ threshold.
`lock_alerts_limit()` will lock the T~UPPER~ and T~LOWER~ thresholds.

## Usage

### Properties
Is it possible to access single configuration bit as properties:
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
The `shutdown()` method will put the sensor in `low power` mode.
The `wake()` method will wake the sensor in `continuous` mode.
```python
# Put the sensor in low power mode
t_sensor.shutdown()

# Wake the sensor (continuous mode)
t_sensor.wake()
```
> In `low power` mode the sensor will draw typically 0.1μA (2μA max)
> In `continuous` mode the sensor will draw typically 200μA (400μA max)

It's not possible to put the sensor in `low power` mode when either the `crit_lock` or `alerts_lock` bits are set. If in debug mode calling the `shutdown()` method will result in a warning.

The methods don't accept any argument and return `None`

### `lock_crit_limit()` and `lock_alerts_limit()` methods
The `lock_crit_limit()` will lock the T~CRIT~ register (0x4)
The `lock_alert_limit()` will lock the T~UPPER~ and T~LOWER~ registers (0x2 and 0x3)
```python
# Lock the Tcrit register
t_sensor.lock_crit_limit()

# Loc the Tupper and Tlower registers
t_sensor.lock_alerts_limit()
```
Both locks can be only disable by a power cycle of the sensor.

The methods don't accept any argument and return `None`

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
    # Acknowledge the interrupt
    t_sensor.irq_clear()
    # Do stuff to resolve alert but be quick to return to main loop as soon as possible
    if t_sensor.get_alert_triggers = (False, False, True):
        heater_pon()
    ...

# Set the pin of that has to act as an interrupt
irq_pin = Pin(18, Pin.IN, pull=Pin.PULL_UP)
# Set the interrupt to be triggered on the falling edge 
# (set trigger to Pin.IRQ_RISING if t_sensor.polarity is set to active_high)
irq_pin.irq(handler=irq_handler, trigger=Pin.IRQ_FALLING)

# Set the alert limits
t_sensor.set_alert_lower_limit(-10)
t_sensor.set_alert_upper_limit(30)
t_sensor.set_alert_crit_limit(40)
# Enable the limits
t_sensor.enable_alert()

while True:
    # MAIN LOOP
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
It's not possible to enable or disable the alert ouput if either `crit_lock` or `alerts_lock` are set.
It's possible to enable or disable the alert output when in `low power` mode but the alert output will not assert or deassert until the sensor is back in `continuous` mode.
The methods don't accept any argument and return `None`

### `set_alert_threshold()` method
The `set_alert_threshold()` method set which thresholds will trigger the alert output, T~CRIT~ or T~CRIT~, T~UPPER~, T~LOWER~.
The power-up default is 
```python
# Set the alert output to trigger only on Tcrit
t_sensor.set_alert_threshold(only_crit=True)

# Set the alert output to trigger on Tcrit, Tupper and Tlower
t_sensor.set_alert_threshold(only_crit=False)
```
The method accept one `bool` argument `only_crit`:
- if `True` alert output will only trigger on T~CRIT~
- if `False` alert output will trigger on T~CRIT~, T~UPPER~, T~LOWER~

If `alerts_lock` is set is not possible to select which threshlods can trigger the alert output.If attempted a warning is issued if in `debug` mode.
The method return `None`.

### `set_alert_polarity()` method
The `set_alert_polarity()` method set the alert output polarity to active high or active low.
```python
# Set alert output polarity to active high
t_sensor.set_alert_polarity(active_high=True)

# Set alert output polarity to active low
t_sensor.set_alert_polarity(active_high=False)
```

The method accept one `bool` argument `active_high`:
- if `True` alert output will be set to active high (an ongoing alert will be a high signal)
- if `False` alert output will be set to active low (an ongoing alert will be a low signal)

If either `crit_lock` or `alerts_lock` are set is not possible to change the polarity of the alert output. If attempted a warning is issued if in `debug` mode.
It's possible to change polarity of the alert ouput when the sensor is in `low power` mode but the alert output will not assert or deassert until the sensor is back in `continuous` mode.
The method return `None`

### `set_alert_mode()` method
The `set_alert_mode()` method set the alert output mode between `comparator` and `interrupt`. [see above](#alerts-and-interrupts)
```python
# Set alert output to interrupt mode
t_sensor.set_alert_mode(irq=True)

# Set alert output to comparator mode
t_sensor.set_alert_mode(irq=False)
```
The method accept one `bool` argument `irq`:
- if `True` alert output mode will be set to `interrupt`
- if `False` alert output mode will be set to `comparator`

If either `crit_lock` or `alerts_lock` are set is not possible to change the mode of the alert output. If attempted a warning is issued if in `debug` mode.
It's possible to change mode of the alert ouput when the sensor is in `low power` mode but the alert output will not assert or deassert until the sensor is back in `continuous` mode.
The method return `None`

### `set_upper_limit()`, `set_lower_limit()` and `set_crit_limit()` methods
The `set_upper_limit()`, `set_lower_limit()` and `set_crit_limit()` methods set the upper, lower and crit threshold registers T~UPPER~, T~LOWER~, T~CRIT~.
```python
# Set Tupper to 43.5°C
t_sensor.set_upper_limit(43.5)
```
The method accept one `float|int` argument expressed in degree Celsius. The limit will be rounded to the nearest 0.25°C.

The methods type check the argument and will raise a `TypeError` exception if the type of the argument is not `float` or `int.
The methods check if the argument is out of the range [-128°C, 127°C] and will raise a `ValueError`.

In debug mode a warning is issued if the argument is outside of the operational range of the sensor [-40°C, 125°C].

It's not possible to change the upper and lower limit register if `alerts_lock` is set. If attempted a warning is issued if in `debug` mode.
It's not possible to change the crit limit register if `crit_lock` is set. If attempted a warning is issued if in `debug` mode.
The methods return `None`

### `set_resolution()` method
The `set_resolution()` method set the resolution of the sensor. [see above](#resolution)
```python
# Set the resolution of the sensor to 0.5°C
t_sensor.set_resolution(RES_0_5)

# Set the resolution of the sensor to 0.25°C
t_sensor.set_resolution(1)
```

The method accept a `int` argument between 0 and 3 inclusive.

The method will raise a `ValueError` if the argument is outside the valid values.

The resolution can be changed when the sensor is in `low power` mode but the temperature register will not change until the sensor is back in `continuous` mode.

The method returns `None`

### `get_temperature()` method
The `get_temperature()` method will return the latest temperature sampled by the sensor.
```python
# Get current tempererature
temp: float = t_sensor.get_temperature()
```
The method doesn't accept any argument.
The method returns a `float`.

If the sensor is in `low power` mode it will return the last temperature sampled.

### `get_alerts_triggers()` method
The `get_alerts_triggers()` method will return the 3 primitive trigger for the alert output.
```python
# Get the alerts triggers
triggers: tuple[bool, bool, bool] = t_sensor.get_alerts_triggers()
```

The method doesn't accept any argument.
The method return 3 `bool` in a `tuple` `tuple[bool, bool, bool]` :
1. First element is `True` if T~A~ >= T~CRIT~
2. Second element is `True` if T~A~ > T~UPPER~
3. Third element is `True` if T~A~ < T~LOWER~

Trigger bits are not influenced by `alert_mode`, `alert_pol` or `alert_ctrl`. These are the triggers that can affect the alert output.

If the sensor is in `low_power` mode it will return the triggers based on the last temperature sampled.



### Custom Address
The sensor has a default address of `0x18` or `0b0011000`. This address is partially hardcoded on the silicon itself. The user has the ability to change the last 3 bit of the address to have up to 7 different sensors on one I^2^C bus using the `A0` `A1` `A2` pins.
```python
# Set the full address
t_sensor = MCP9808(i2c=i2c, addr=0x1A)

# Use the A0, A1, A2 arguments
t_sensor = MCP9808(i2c=i2c, A2=False, A1=True, A0=False)
```
> Microchip© by custom request can also produce an alternative silicon with an alternate fixed address `0x48` or `0b1001000`. However the 3 custom bits are still present.
> In this case use a full address with the `addr` argument

### Debug
The module offer built-in debug warnings when the `debug` argument is set to `True`.
```python
t_sensor = MCP9808(i2c=i2c, debug=True)
```
Debug warnings are issued when a register is not set succesfully. This can happen when trying to write a register when the sensor in `low power` mode or when some parts of the registers are lock by the `crit_lock` and `alerts_lock` bits.
```python
t_sensor = MCP9808(i2c=i2c, debug=True)

# Lock the alert threshold window
t_sensor.lock_alerts_limit()

# Try to change the alert pin polarity
t_sensor.set_alert_polarity(active_high=true)
```
```console
[WARN] Failed to set alert_pol. Set True got False.
```

