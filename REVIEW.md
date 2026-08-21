<!-- SPDX-FileCopyrightText: 2026 Marco Miano -->
<!-- SPDX-License-Identifier: MIT -->

# mip-mcp9808 review and improvement handover

Repository: https://github.com/MarcoMiano/mip-mcp9808

The review was performed against `main` at commit:

`77c4c6928e84dd6b8820812b79de506bc63eb992`

## Objective

Correct the driver and documentation, then simplify the implementation for predictable use on constrained MicroPython microcontrollers.

Priorities are:

1. Correctness.
2. Low and predictable allocation.
3. Few I²C transactions.
4. Small code and API surface.
5. Portability across MicroPython boards.
6. No unnecessary dependencies or desktop-oriented abstractions.

Do not add dataclasses, logging frameworks, background tasks, asyncio requirements, large typing dependencies, or other abstractions without a clear microcontroller benefit.

Preserve unrelated work. Review the repository state before editing and keep changes uncommitted until the exact commit structure is approved.

## Confirmed defects

### 1. Threshold encoding is broken

`_set_alert_limit()` encodes threshold registers incorrectly.

The current implementation can assign values above 255 to a `bytearray` element. For example, 16 °C produces 256 and raises:

`ValueError: byte must be in range(0, 256)`

Documented values such as 43.5 °C and 90 °C consequently fail. Negative fractional values are also encoded incorrectly, generally one degree too warm.

The README promises rounding to the nearest 0.25 °C, but the implementation truncates.

Convert once to signed quarter-degree units and encode the complete 11-bit two’s-complement register value:

```python
q = round(limit * 4)

if not -512 <= q <= 511:
    raise ValueError("limit must be between -128 and 127.75 °C")

raw = (q & 0x7FF) << 2
buf[0] = raw >> 8
buf[1] = raw & 0xFF
```

Alternatively, reject inputs that are not exact multiples of 0.25 °C. Choose one policy, document it precisely and test it.

Add exact-byte tests for at least:

- -128
- -16.25
- -1.50
- -0.25
- 0
- 0.25
- 15.75
- 16
- 43.5
- 90
- 127.75

Also test out-of-range and non-representable values.

Relevant source:

https://github.com/MarcoMiano/mip-mcp9808/blob/77c4c6928e84dd6b8820812b79de506bc63eb992/mcp9808.py#L335-L400

### 2. Repository-level mip.install() is incomplete

The repository contains manifest.py, which supports freezing the module into firmware, but it does not contain the package.json required for installing the repository as an ordinary self-hosted mip package.

Add a minimal package.json which installs only mcp9808.py.

Document and test:

mip.install("github:MarcoMiano/mip-mcp9808")

Prefer versioned tags in published installation examples once a corrected release exists. Also document a direct-file installation fallback if appropriate.

Do not claim a release or tag exists until one has actually been created.

Reference:

https://docs.micropython.org/en/latest/reference/packages.html

### 3. Interrupt example is invalid and unsafe

The README example:

- uses assignment inside an if;
- does not call get_alert_triggers();
- contains the heater_pon() typo;
- performs I²C operations and allocations from the interrupt callback.

The IRQ handler should only set a pre-existing flag or schedule a pre-bound callback. Perform irq_clear() and sensor reads from normal execution context.

Follow MicroPython’s interrupt-handler guidance:

https://docs.micropython.org/en/latest/reference/isr_rules.html

### 4. Documentation references nonexistent API names

Correct and synchronize the README, module documentation and tests:

- set_hysteresis_mode() versus the implemented hyst_mode property.
- set_upper_limit() versus set_alert_upper_limit().
- set_lower_limit() versus set_alert_lower_limit().
- set_crit_limit() versus set_alert_crit_limit().
- get_alerts_triggers() versus get_alert_triggers().

Choose one compact public API. Since there are currently no published tags or releases, avoid adding compatibility aliases unless there is evidence that they are necessary.

### 5. Two documented properties are ordinary cached attributes

irq_clear_bit and alert_pol are described as properties but _get_config() assigns them as mutable public attributes.

They can become stale and callers can overwrite them without modifying the device.

Either:

- implement genuine read-only properties backed by _irq_clear_bit and _alert_pol; or
- preferably, replace the numerous implicit configuration properties with an explicit read_config() or refresh() operation.

### 6. get_alert_status() reads the configuration twice

It calls _get_config() and then reads self.alert, whose property calls _get_config() again.

After refreshing, return the already populated private value instead.

### 7. Hardware test setup and assertion problems

The test suite constructs the driver before explicitly powering and settling the sensor.

Power the sensor, wait for startup, and only then construct or verify the driver.

After every power cycle, refresh or reconstruct any cached driver state.

One lock-related test repeats the alerts_lock assertion when it should verify that alert_ctrl remained disabled.

Keep hardware tests separate from dependency-free host tests.

### 8. Documentation accuracy

Correct the following:

- Three address pins provide eight possible addresses, not seven.
- active_high=true must be active_high=True.
- The encoded threshold endpoint is 127.75 °C.
- Reserved-register access is unsupported and may produce unspecified behaviour, but the datasheet does not state that it irreparably damages the sensor.
- Fix method-name, heading and spelling inconsistencies throughout the README.

## MCU-oriented simplification and performance work

These are improvements, separate from the correctness fixes. Keep each change measurable and avoid making the class larger merely for convenience.

### Reusable I²C buffer

Allocate one two-byte bytearray per instance and use:

i2c.readfrom_mem_into(address, register, buffer)

Reuse it for reads and writes where safe. Do not expose the internal buffer.

This removes temporary byte-object allocations from the common temperature-read path.

Document that a single instance is not reentrant across IRQ and normal contexts.

### Integer temperature API

Provide an allocation-light integer operation such as:

read_temperature_x16()

It should return signed sixteenth-degrees Celsius, matching the sensor register resolution.

Keep a float-returning convenience wrapper for interactive use:

read_temperature()

Control loops can then avoid floating-point work on MCUs without an FPU.

### Integer threshold representation

Internally use signed quarter-degrees.

Consider an explicit integer method such as set_limit_x4() for performance-sensitive callers, with Celsius conversion retained as a convenience wrapper.

### Compact configuration representation

Represent configuration internally as one 16-bit value with named masks.

Use small helpers such as:

_read_u16(register) _write_u16(register, value)

Avoid maintaining many cached boolean attributes.

### Explicit hardware reads

Properties should not unexpectedly perform I²C transactions.

Prefer operations such as:

read_config() refresh() read_alert_status()

This makes execution time, allocation and power use visible to callers.

### Combined configuration

A restrained configure() or set_limits() helper may update related fields in one read-modify-write transaction.

Keep the hot path simple. Avoid keyword-heavy or allocation-heavy interfaces where they provide no material benefit.

### Selectable device verification

Construction currently performs several I²C reads.

Consider:

MCP9808(i2c, address=0x18, check=True)

or a separate:

sensor.verify()

Default verification gives better wiring diagnostics; optional verification gives faster startup. Choose and document the tradeoff.

### Remove concrete bus-type dependencies

The class only needs an object implementing the required I²C methods.

Avoid runtime imports of both machine.I2C and machine.SoftI2C solely for annotations. Accept a duck-typed bus object so the module works on more MicroPython ports.

### Avoid ineffective optimisation complexity

Do not introduce @micropython.native or @micropython.viper without measurements showing a meaningful improvement. The driver is primarily limited by I²C latency.

Do not introduce asyncio, dataclasses, enums, logging frameworks or background workers.

## Testing structure

Create dependency-free host-side tests around a small FakeI2C register model.

Host tests should verify:

- exact threshold bytes;
- positive and negative temperature decoding;
- decoding when all alert-status flags are set;
- configuration masks preserving unrelated bits;
- lock behaviour;
- interrupt-clear semantics;
- transaction counts for temperature and configuration reads;
- constructor verification behaviour;
- invalid identity values;
- range and type validation.

Keep a separate optional on-device smoke suite for:

- Pico W wiring;
- power cycling;
- temperature reads;
- resolution changes;
- physical ALERT output;
- comparator mode;
- interrupt mode;
- polarity;
- register locks.

Compile the module with the repository’s supported MicroPython toolchain. The previously reviewed source compiled successfully with MicroPython 1.24.1 mpy-cross, but the hardware suite was not executable during review because no Pico W and MCP9808 were connected.

## Suggested implementation order

1. Add failing host tests for threshold encoding.
2. Correct threshold encoding and range handling.
3. Correct the hardware fixture and mistaken assertion.
4. Synchronize API documentation and examples.
5. Add safe interrupt-handling documentation.
6. Add and test package.json.
7. Introduce reusable I²C buffers and verify transaction counts.
8. Add the integer temperature path.
9. Simplify configuration access and caching.
10. Run host tests, mpy-cross, and available hardware tests.
11. Review the final diff for code size, allocations and public API growth.

## Acceptance conditions

- All documented threshold values encode without exceptions.
- Exact register bytes match the datasheet.
- Negative fractional thresholds round or reject according to the documented policy.
- Repository-level mip.install() works from a pinned release/tag.
- IRQ examples perform no I²C work in the interrupt handler.
- README, implementation and tests use the same public method names.
- A temperature read uses one I²C transaction and no per-call driver allocation where the port API permits it.
- An integer temperature API is available for control loops.
- Configuration reads do not occur invisibly or redundantly.
- Host tests pass without hardware.
- Hardware tests clearly declare their board, wiring and power requirements.
- No unnecessary runtime dependency is introduced.
- Changes remain uncommitted until Marco approves the exact commit messages and scopes.
