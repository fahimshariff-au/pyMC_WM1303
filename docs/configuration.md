# Configuration

## Overview

The WM1303 configuration model has evolved into a **single-source-of-truth (SSOT)** approach for WM1303-specific runtime and UI state.

## Source of truth

The authoritative WM1303-specific configuration is:

- repository side: `config/wm1303_ui.json`
- installed runtime side: `/etc/pymc_repeater/wm1303_ui.json`

This file should be treated as the main source of truth for:

- channel definitions
- active/inactive state
- bridge-oriented UI/runtime settings
- LBT/CAD-related channel settings
- WM1303 Manager behavior

## Relationship to config.yaml

`config.yaml` still matters for repeater startup and compatibility, but it is **not the primary WM1303 UI/runtime source**.

### Practical model

1. changes are saved to `wm1303_ui.json`
2. required channel/runtime parts are synchronized into `config.yaml`
3. runtime/API/UI then reflect the SSOT-derived state

## 5-channel model

The current system documents and exposes a **5-channel architecture**.

- Channel A-D are part of the concentrator-backed channel model
- Channel E has SX1261-backed behavior and deserves separate explanation

See [`channel_e_sx1261.md`](./channel_e_sx1261.md).

## Persisted channel behavior

Important per-channel settings include:

- active/inactive state
- frequency
- spreading factor
- bandwidth
- LBT enable/disable
- CAD enable/disable where allowed
- channel-specific runtime metrics backing the UI

## Safe editing guidance

For operators and future development:

- prefer the UI/API flow for normal changes
- avoid manual drift between `wm1303_ui.json` and `config.yaml`
- treat `wm1303_ui.json` as authoritative when reconciling mismatches
- keep install/upgrade scripts aligned with any new config fields

## Related documents

- [`ui.md`](./ui.md)
- [`api.md`](./api.md)
- [`architecture.md`](./architecture.md)
