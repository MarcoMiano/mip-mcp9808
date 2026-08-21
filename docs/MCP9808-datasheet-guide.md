<!-- SPDX-FileCopyrightText: 2026 Marco Miano -->
<!-- SPDX-License-Identifier: MIT -->

# MCP9808 datasheet guide

This is a structured reading aid for Microchip document DS20005095B, `MCP9808-0.5C-Maximum-Accuracy-Digital-Temperature-Sensor-Data-Sheet-DS20005095B.pdf`. It emphasizes the information needed to implement or review an MCP9808 driver. The PDF remains the authoritative source, especially for electrical limits, timing diagrams, package dimensions, and ordering information.

Page references below are the page numbers printed in the datasheet.

## Quick facts

| Property                  | Value                                                                                                                      | Source          |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------- | --------------- |
| Supply voltage            | 2.7 V to 5.5 V                                                                                                             | p. 3            |
| Operating temperature     | -40 degrees C to +125 degrees C                                                                                            | pp. 3-4         |
| Accuracy                  | maximum +/-0.5 degrees C from -20 degrees C to +100 degrees C; maximum +/-1 degrees C from -40 degrees C to +125 degrees C | pp. 1, 3        |
| Typical operating current | 200 microamps; 400 microamps maximum                                                                                       | p. 3            |
| Typical shutdown current  | 0.1 microamps; 2 microamps maximum                                                                                         | p. 3            |
| Interface                 | I2C/SMBus-compatible, up to 400 kHz                                                                                        | pp. 1, 5, 13-14 |
| Default 7-bit address     | `0x18` when A2, A1, and A0 are low                                                                                         | pp. 11, 14      |
| Address range             | `0x18` through `0x1F`                                                                                                      | pp. 11, 14      |
| Temperature resolutions   | 0.5, 0.25, 0.125, or 0.0625 degrees C/LSb                                                                                  | p. 29           |
| Power-on resolution       | 0.0625 degrees C (`0x03`)                                                                                                  | pp. 29, 31, 33  |
| Alert output              | Open drain; external pull-up required                                                                                      | pp. 3, 11, 30   |
| Packages                  | 8-pin 2x3 DFN and 8-pin MSOP                                                                                               | pp. 1, 37-42    |

Do not confuse resolution with accuracy. The finest digital step is 0.0625 degrees C, while the specified sensor accuracy is wider.

## Pinout

| Pin | Name  | Function and integration note                                                         |
| --: | ----- | ------------------------------------------------------------------------------------- |
|   1 | SDA   | Bidirectional serial data; requires a pull-up.                                        |
|   2 | SCL   | Serial clock input.                                                                   |
|   3 | Alert | Open-drain temperature alert output; requires a pull-up.                              |
|   4 | GND   | Ground.                                                                               |
|   5 | A2    | I2C address bit 2. Tie to GND or VDD.                                                 |
|   6 | A1    | I2C address bit 1. Tie to GND or VDD.                                                 |
|   7 | A0    | I2C address bit 0. Tie to GND or VDD.                                                 |
|   8 | VDD   | 2.7 V to 5.5 V supply.                                                                |
|   9 | EP    | DFN exposed pad only; internally connected to GND and may be connected to PCB ground. |

The datasheet recommends a 0.1 to 1 microfarad high-frequency ceramic decoupling capacitor close to VDD and GND (p. 35).

## I2C addressing and transactions

The 7-bit address is:

```text
0b0011_A2_A1_A0
0x18 | (A2 << 2) | (A1 << 1) | A0
```

For the default address, the address byte on the wire is `0x30` for a write and `0x31` for a read. APIs that accept a 7-bit address should receive `0x18`, not either wire-format byte.

Important protocol properties (pp. 13-14):

- Every register access is selected through the 8-bit register pointer.
- Pointer bits 7:4 must be zero.
- The device does **not** support sequential register reads or writes. Address each register separately.
- The previously selected pointer is retained, so a later receive operation may read that register without writing the pointer again. Explicit pointer writes are usually safer in a driver.
- A normal read is: START, address+write, pointer, repeated START, address+read, data, STOP.
- For a 16-bit read, the device sends the most-significant byte first. The master ACKs the first byte and NAKs the final byte.
- If SCL remains high or low for 25 to 35 ms, the sensor resets its serial interface. A repeated START is then required.
- The device does not stretch the SCL-low time.

## Register map

All pointer values above `0x08` are reserved. Some reserved registers contain test and calibration data; the datasheet warns that accessing them may cause the device to operate outside its specification (p. 16).

| Pointer | Name               | Width | Access     | Power-on value | Purpose                                                  |
| ------: | ------------------ | ----: | ---------- | -------------: | -------------------------------------------------------- |
|  `0x00` | RFU                |    16 | read-only  |       `0x001F` | Reserved for future use.                                 |
|  `0x01` | CONFIG             |    16 | read/write |       `0x0000` | Operating and Alert configuration.                       |
|  `0x02` | TUPPER             |    16 | read/write |       `0x0000` | Upper Alert threshold.                                   |
|  `0x03` | TLOWER             |    16 | read/write |       `0x0000` | Lower Alert threshold.                                   |
|  `0x04` | TCRIT              |    16 | read/write |       `0x0000` | Critical Alert threshold.                                |
|  `0x05` | TA                 |    16 | read-only  |       `0x0000` | Ambient temperature and comparison flags.                |
|  `0x06` | Manufacturer ID    |    16 | read-only  |       `0x0054` | Microchip manufacturer identifier.                       |
|  `0x07` | Device ID/revision |    16 | read-only  |       `0x0400` | ID `0x04` in the upper byte; revision in the lower byte. |
|  `0x08` | Resolution         |     8 | read/write |         `0x03` | Conversion resolution and rate.                          |

Sources: register summary on pp. 16-17 and power-on defaults on p. 33.

## CONFIG register (`0x01`)

CONFIG is a 16-bit, big-endian register. Bits 15:11 are unimplemented and read as zero.

| Bits |     Mask | Name        | Meaning when set                                      |
| ---: | -------: | ----------- | ----------------------------------------------------- |
| 10:9 | `0x0600` | THYST       | Hysteresis selection; see below.                      |
|    8 | `0x0100` | SHDN        | Shutdown/low-power mode.                              |
|    7 | `0x0080` | Crit. Lock  | Lock TCRIT until a power-on reset.                    |
|    6 | `0x0040` | Win. Lock   | Lock TUPPER and TLOWER until a power-on reset.        |
|    5 | `0x0020` | Int. Clear  | Clear a latched interrupt; reads back as zero.        |
|    4 | `0x0010` | Alert Stat. | Read-only current Alert output status.                |
|    3 | `0x0008` | Alert Cnt.  | Enable the Alert output.                              |
|    2 | `0x0004` | Alert Sel.  | Alert only for TCRIT; window thresholds are disabled. |
|    1 | `0x0002` | Alert Pol.  | Active-high Alert. Zero means active-low.             |
|    0 | `0x0001` | Alert Mod.  | Interrupt mode. Zero means comparator mode.           |

Hysteresis selection:

| Bits 10:9 |     Hysteresis |
| --------- | -------------: |
| `00`      |    0 degrees C |
| `01`      | +1.5 degrees C |
| `10`      | +3.0 degrees C |
| `11`      | +6.0 degrees C |

### Configuration restrictions

The lock bits are one-way until the device experiences a power-on reset. A driver should treat setting them as an irreversible operation for the current powered session.

- If either lock bit is set, THYST, Alert Cnt., Alert Pol., and Alert Mod. cannot be changed.
- SHDN cannot be set while either lock bit is set, but an already-set SHDN bit can be cleared to return to continuous conversion.
- Win. Lock prevents changing Alert Sel.
- Crit. Lock prevents writes to TCRIT.
- Win. Lock prevents writes to TUPPER and TLOWER.
- Configuration and threshold registers are generally accessible in shutdown, subject to the restrictions above.
- Int. Clear cannot be asserted after entering shutdown. If an interrupt was cleared as the device entered shutdown, both Int. Clear and Alert Stat. read back cleared.
- Alert configuration may be written in shutdown, but the physical output does not update until continuous conversion resumes.

See pp. 18-19 for the complete bit descriptions.

## Ambient temperature register (`TA`, `0x05`)

TA is a read-only, 16-bit, big-endian register. It is double-buffered and is updated once per conversion, so it can be read while the next conversion is in progress.

```text
bit 15     TA >= TCRIT
bit 14     TA >  TUPPER
bit 13     TA <  TLOWER
bit 12     temperature sign
bits 11:0  signed temperature value, 1/16 degree C per LSb
```

The comparison flags are produced independently of Alert enable, polarity, and mode. Mask them before decoding the temperature.

### Robust decoding formula

```python
word = (msb << 8) | lsb
flags = (bool(word & 0x8000), bool(word & 0x4000), bool(word & 0x2000))
raw = word & 0x1FFF
if raw & 0x1000:
    raw -= 0x2000
temperature_c = raw / 16.0
```

Examples:

| Register word | Meaning           |
| ------------: | ----------------- |
|      `0x0194` | +25.25 degrees C  |
|      `0x0001` | +0.0625 degrees C |
|      `0x1FFF` | -0.0625 degrees C |
|      `0x1F60` | -10.0 degrees C   |

Only the bits supported by the selected resolution change. At 0.5 degrees C, for example, the lowest three temperature bits remain zero.

## Threshold registers (`0x02` through `0x04`)

TUPPER, TLOWER, and TCRIT are 16-bit, big-endian registers with a resolution of 0.25 degrees C. Bits 15:13 and 1:0 are unimplemented and must be zero. The signed threshold occupies bits 12:2.

### Encoding

```python
# Valid representable range is -128.0 through +127.75 degrees C.
quarter_degrees = round(temperature_c * 4)
word = (quarter_degrees & 0x07FF) << 2
msb = word >> 8
lsb = word & 0xFF
```

If the public API promises rounding, define how midpoint values and values that are not multiples of 0.25 degrees C are handled. Plain `int()` truncation is not rounding.

### Decoding

```python
raw = ((msb << 8) | lsb) >> 2
raw &= 0x07FF
if raw & 0x0400:
    raw -= 0x0800
temperature_c = raw / 4.0
```

The datasheet example encodes +90 degrees C as `0x05A0` (p. 23).

## Resolution register (`0x08`)

Only bits 1:0 are implemented.

|  Value |       Resolution | Typical conversion time | Typical samples/s |
| -----: | ---------------: | ----------------------: | ----------------: |
| `0x00` |    0.5 degrees C |                   30 ms |                33 |
| `0x01` |   0.25 degrees C |                   65 ms |                15 |
| `0x02` |  0.125 degrees C |                  130 ms |                 7 |
| `0x03` | 0.0625 degrees C |                  250 ms |                 4 |

The documented power-on value is `0x03` (pp. 29, 31, and 33). A note under the TA register on p. 24 instead says the power-up default is 0.25 degrees C. That single note conflicts with the resolution-register definition and the power-on defaults table; it should be treated as a likely documentation error, not as a second device mode.

## Shutdown behavior

Setting CONFIG bit 8 stops temperature conversions while keeping the serial interface available. TA retains the last completed reading. Typical current is 0.1 microamps, although bus traffic and an asserted Alert output increase it.

The device stays shut down until bit 8 is cleared or power is cycled. After waking, allow one complete conversion time for fresh TA and Alert state. If Alert was asserted on entry, the physical output remains asserted in shutdown.

## Alert behavior

Alert is open drain. In the default active-low configuration it needs a pull-up to VDD and sinks current when asserted. CONFIG bit 4 reports whether the output is asserted.

There are three independent comparisons, also visible in TA bits 15:13:

- Critical: `TA >= TCRIT`.
- Upper: `TA > TUPPER`.
- Lower: `TA < TLOWER`.

The comparison flags express those direct comparisons. Hysteresis controls the physical Alert state transitions and is therefore not identical to simply reading the flags.

### Comparator mode

Comparator mode tracks the threshold condition continuously. It suits a thermostat, fan control, or thermal shutdown.

- Upper Alert asserts when `TA > TUPPER` and deasserts when `TA <= TUPPER - THYST`.
- Lower Alert asserts when `TA < TLOWER - THYST` and deasserts when `TA >= TLOWER`.
- Critical Alert asserts when `TA >= TCRIT` and deasserts when `TA < TCRIT - THYST`.

### Interrupt mode

Crossing a window threshold latches the Alert output. The controller clears it by writing CONFIG with Int. Clear (bit 5) set. The comparison flags in TA remain descriptions of the current temperature and are not cleared by acknowledging the interrupt.

Critical temperature overrides interrupt mode: at or above TCRIT, Alert behaves as a comparator regardless of CONFIG bit 0. It cannot be cleared while the critical condition persists. Normal configured behavior resumes only below `TCRIT - THYST`.

### Critical-only selection

When Alert Sel. (CONFIG bit 2) is set, TUPPER and TLOWER no longer drive Alert. The output acts as a critical comparator and CONFIG bit 0 is ignored.

Figure 5-10 on p. 32 is the authoritative state diagram for Alert behavior.

## Power-on defaults

After VDD falls below the typical 2.2 V power-on-reset threshold, the device restores these settings:

- Continuous conversion.
- 0 degrees C hysteresis.
- All locks clear.
- Alert disabled and not asserted.
- Active-low Alert polarity.
- Comparator mode.
- All three thresholds selected for Alert.
- TUPPER, TLOWER, and TCRIT equal 0 degrees C.
- Resolution 0.0625 degrees C.
- Manufacturer ID `0x0054`.
- Device ID/revision `0x0400` for the documented first revision.

## Electrical and layout constraints relevant to a driver

- SCL, SDA, and address-pin input-low is at most 0.3 x VDD; input-high is at least 0.7 x VDD.
- The serial clock range is 0 to 400 kHz.
- SDA and Alert are open-drain outputs; size pull-ups so their sink-current and low-level voltage specifications are respected.
- Heavy pull-ups increase self-heating. The datasheet estimates errors around +0.5 degrees C when communication pins carry their maximum specified current.
- Keep the decoupling capacitor close to the sensor and use PCB ground copper under the device to improve thermal coupling.
- Avoid placing the sensor where heat from the host MCU, regulators, or pull-up resistors dominates the ambient temperature being measured.

Exact serial timing limits are tabulated on p. 5. Package thermal data are on pp. 3-4 and the application discussion is on p. 35.

## Datasheet navigation

| Topic                                             | Printed pages |
| ------------------------------------------------- | ------------: |
| Features and functional block diagram             |           1-2 |
| Electrical and serial timing limits               |           3-5 |
| Typical performance curves                        |          7-10 |
| Pins and address selection                        |            11 |
| I2C protocol                                      |         13-14 |
| Register overview                                 |         15-17 |
| CONFIG                                            |         18-21 |
| Threshold registers                               |         22-23 |
| Ambient temperature and conversion                |         24-26 |
| Manufacturer and device IDs                       |         27-28 |
| Resolution, shutdown, hysteresis, and Alert modes |         29-32 |
| Power-on defaults                                 |            33 |
| Layout and self-heating                           |            35 |
| Package markings and dimensions                   |         37-42 |
| Microchip PIC I2C example                         |         43-45 |
| Revision history                                  |            47 |
| Ordering information                              |            48 |

## Driver-review checklist

- Use a 7-bit address from `0x18` to `0x1F`.
- Keep register pointers within `0x00` to `0x08`; do not probe beyond `0x08`.
- Read and write 16-bit registers most-significant byte first.
- Do not rely on sequential register access.
- Preserve read-only/reserved CONFIG bits during read-modify-write operations.
- Decode TA only after masking bits 15:13.
- Sign-extend the 13-bit TA field before dividing by 16.
- Encode thresholds at 0.25-degree resolution, not the selected TA resolution.
- Treat lock writes as irreversible until power is cycled.
- Distinguish direct TA comparison flags from the hysteretic/latching Alert pin.
- Account for the configured conversion time after power-up, wake, or a resolution change before requiring a fresh sample.
- Verify manufacturer ID `0x0054` and device ID upper byte `0x04`; handle later revision-byte values without assuming they are different devices.
