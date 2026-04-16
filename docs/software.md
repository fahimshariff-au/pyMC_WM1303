# Software Components

## Overview

The WM1303 software stack combines modified upstream projects with this repository's overlay files, scripts, config, and documentation.

The current implementation supports a **5-channel runtime model** and includes dedicated handling for **Channel E / SX1261** behavior.

## Main backend components

| Component | Location | Role |
|---|---|---|
| `wm1303_backend.py` | overlay/pymc_core | Main backend coordinator |
| `virtual_radio.py` | overlay/pymc_core | Per-channel radio abstraction |
| `tx_queue.py` | overlay/pymc_core | Per-channel queued TX logic |
| `bridge_engine.py` | overlay/pymc_repeater | Cross-channel routing and dedup |
| `channel_e_bridge.py` | overlay/pymc_repeater | Channel E repeater-side integration |
| `wm1303_api.py` | overlay/pymc_repeater | WM1303 REST API |
| `spectrum_collector.py` | overlay/pymc_repeater | Spectrum/UI data collection |
| `cad_calibration_engine.py` | overlay/pymc_repeater | CAD calibration support |

## WM1303Backend

`WM1303Backend` is the core coordinator between Python, the packet forwarder, and the radio abstractions.

It is responsible for:

- UDP handling towards `lora_pkt_fwd`
- RX dispatch to logical channels
- TX emission back to the forwarder
- watchdog and runtime health logic
- noise-floor collection integration
- bridge-related packet entry/exit points
- channel-specific runtime state

## NoiseFloorMonitor

The current behavior is:

- startup stabilization delay before first collection
- periodic update every **30 seconds**
- retry behavior for TX-free harvesting windows
- no routine pausing of TX queues
- persistence of history for API/UI use

## Metrics and persistence

Runtime metrics are not only kept in memory.

Important persisted data includes:

- `noise_floor_history`
- CAD-related events/history
- bridge/dedup related runtime data
- per-channel counters and snapshots

This persistence is important because several charts and API endpoints now read from the database-backed history instead of relying only on temporary in-memory buffers.

## Per-channel mapping

The software uses **channel ID keyed state** for important metrics, especially noise-floor and related chart data.

This prevents collisions when channels use:

- the same frequency
- different spreading factors
- shared frontend/radio assumptions

## Channel E integration

Channel E is not just a note in the hardware layer anymore. The software stack includes explicit Channel E handling in:

- backend radio behavior
- repeater integration
- UI/API exposure
- spectrum and signal-quality presentation

## API and UI integration

The software stack exposes WM1303-specific capabilities through:

- `/api/wm1303/*`
- WebSocket/live refresh paths
- `wm1303.html`
- integration into the existing pyMC repeater web server

## SSOT behavior

The effective operational source of truth for WM1303-specific UI/runtime state is:

- **`/etc/pymc_repeater/wm1303_ui.json`** at runtime
- `config/wm1303_ui.json` as repository-managed source material

Save paths synchronize required channel/runtime data into `config.yaml` where compatibility with repeater startup requires it.

## Related documents

- [`architecture.md`](./architecture.md)
- [`configuration.md`](./configuration.md)
- [`api.md`](./api.md)
- [`ui.md`](./ui.md)
- [`channel_e_sx1261.md`](./channel_e_sx1261.md)
