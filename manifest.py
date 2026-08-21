# SPDX-FileCopyrightText: 2024-2026 Marco Miano
# SPDX-License-Identifier: MIT

# MicroPython provides the manifest DSL functions when it evaluates this file
# ruff: noqa: F821

metadata(
    description="Microchip MCP9808 temperature sensor driver",
    version="2.0.0",
    license="MIT",
    author="Marco Miano",
)

# opt=2 so line numbers are preserved in case of exceptions
module("mcp9808.py", opt=2)
