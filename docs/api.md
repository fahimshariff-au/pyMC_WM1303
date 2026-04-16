# API Reference

## Overview

The WM1303 integration exposes a dedicated REST API under **`/api/wm1303/*`** and provides live updates for the WM1303 Manager UI.

## Main API behavior

The API exposes:

- runtime status
- per-channel state
- noise-floor and signal-quality history
- bridge-related status/metrics
- spectrum-related data
- configuration-backed state from the WM1303 SSOT model

## Version endpoint

The API includes a version endpoint that reads from the project `VERSION` file so the deployed runtime can report the installed WM1303 integration version.

## Channel representation

The API now needs to be understood in the context of the **5-channel model**.

That means:

- per-channel payloads should be interpreted as channel-ID based
- charts and status must not assume unique frequency alone
- Channel E may appear in UI/API flows where supported by the current runtime feature set

## Noise-floor and signal-quality data

Noise-floor and signal-quality presentation no longer rely only on temporary memory state.

Important points:

- per-channel noise-floor values are persisted
- signal-quality views can read from database-backed `noise_floor_history`
- CAD/noise-floor values are exposed through status and live-update paths

## WebSocket / live updates

The UI uses live refresh paths for:

- channel state
- charts
- spectrum-related views
- recent runtime changes

## SSOT relation

The API should be read as exposing the **runtime state derived from `wm1303_ui.json`**, with compatibility synchronization into `config.yaml` where required by repeater startup/runtime integration.

## Related documents

- [`ui.md`](./ui.md)
- [`configuration.md`](./configuration.md)
- [`software.md`](./software.md)
