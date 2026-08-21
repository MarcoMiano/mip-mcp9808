<!-- SPDX-FileCopyrightText: 2026 Marco Miano -->
<!-- SPDX-License-Identifier: MIT -->

# MCP9808 performance benchmarks

The on-device [`benchmark_mcp9808.py`](benchmark_mcp9808.py) script compares 200 temperature-register reads through the original allocating float implementation, the v2 reusable-buffer float API, and the v2 reusable-buffer integer API. Each invocation runs five rounds and reports elapsed microseconds plus the decrease in free heap before garbage collection.

The values below were measured on a Raspberry Pi Pico W with an MCP9808 connected through `SoftI2C` on GPIO16 and GPIO17. The sensor was powered through GPIO15 and power-cycled before each benchmark invocation. MicroPython reported a 125 MHz CPU clock and an effective 500 kHz `SoftI2C` clock when configured with `freq=400000`.

## MicroPython 1.28.0

These results are the median of five rounds collected on 2026-08-21.

| Read path        | 200 reads | Heap decrease | Relative to original |
| ---------------- | --------: | ------------: | -------------------: |
| Original float   | 77,055 us |  12,800 bytes |             baseline |
| Buffered float   | 76,859 us |   3,200 bytes |          0.3% faster |
| Buffered integer | 63,897 us |       0 bytes |         17.1% faster |

## MicroPython 1.24.1

These earlier values are single-round measurements collected before the firmware update and should be treated as a historical reference rather than an equally strong baseline.

| Read path        | 200 reads | Heap decrease |
| ---------------- | --------: | ------------: |
| Original float   | 56,282 us |  12,848 bytes |
| Buffered float   | 54,115 us |   3,248 bytes |
| Buffered integer | 47,958 us |       0 bytes |

## Interpretation

Compare paths within the same invocation and firmware build. Absolute timings depend on the MicroPython version, board clock, I2C implementation, configured bus frequency, interrupts, and connected hardware, so results from different environments are not directly interchangeable.

The integer API provides the clearest improvement for allocation-sensitive loops: it retained no heap across the measured reads and was faster than both float paths. The reusable-buffer float API substantially reduces retained heap while preserving a Celsius float result.
