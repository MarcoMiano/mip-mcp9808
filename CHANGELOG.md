<!-- SPDX-FileCopyrightText: 2026 Marco Miano -->
<!-- SPDX-License-Identifier: MIT -->

# Changelog

This project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## 2.0.0 - 2026-08-21

### Breaking changes

- Require the I²C object to implement `readfrom_mem_into()` and `writeto_mem()`; the driver no longer imports or depends on concrete `machine.I2C` classes.
- Make configuration properties cached and side-effect-free; call `refresh()` when an explicit hardware read is required.
- Make `irq_clear_bit` and `alert_pol` genuine read-only properties instead of mutable public attributes.
- Reject invalid constructor, resolution, and hysteresis argument types instead of accepting bool-like integer values.

### Added

- Add `verify=False` and the explicit `verify()` method for selectable device-identity checks.
- Add `get_temperature_x16()` for allocation-sensitive signed sixteenth-degree readings.
- Add `set_alert_upper_limit_x4()`, `set_alert_lower_limit_x4()`, and `set_alert_crit_limit_x4()` for exact signed quarter-degree thresholds.
- Add a repository-level `package.json`, dependency-free `FakeI2C` host tests, expanded Pico W hardware tests, SPDX file headers, and a datasheet reading guide.

### Fixed

- Correct positive and negative threshold encoding over the complete -128 degrees C through 127.75 degrees C register range.
- Round Celsius thresholds to the nearest quarter degree using round-to-even for halfway values.
- Remove redundant configuration reads and per-read temporary byte allocations from the common temperature path.
- Correct the hardware fixture, lock assertion, interrupt example, method names, register limits, and address-count documentation.

## 1.0.0 - 2026-08-21

- Retrospectively tag the original driver API and implementation that existed before the breaking v2 changes.
