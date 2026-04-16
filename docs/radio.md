# Radio Architecture

## Overview

The WM1303 integration exposes a **5-channel radio model** to the rest of the MeshCore stack.

- **Channel A-D** are the primary logical channels built on the concentrator-backed `VirtualLoRaRadio` abstraction.
- **Channel E** is the SX1261-backed path with its own operational role and additional complexity.

For the full Channel E explanation, see [`channel_e_sx1261.md`](./channel_e_sx1261.md).

## Topology

| Channel | Backend path | Typical purpose |
|---|---|---|
| A | VirtualLoRaRadio | Mesh traffic |
| B | VirtualLoRaRadio | Mesh traffic |
| C | VirtualLoRaRadio | Mesh traffic |
| D | VirtualLoRaRadio | Mesh traffic |
| E | SX1261-backed path | Extended radio behavior / dedicated path |

## VirtualLoRaRadio

`VirtualLoRaRadio` is the per-channel abstraction used by the repeater/bridge stack.

It provides:

- a standard LoRaRadio-facing interface
- per-channel RX dispatch
- per-channel TX submission into backend scheduling
- per-channel statistics
- channel-specific noise-floor and signal behavior exposure

## Channel E / SX1261

Channel E became more than a helper path. It is now part of the user-visible architecture and should be considered when looking at:

- channel charts
- channel configuration
- bridge behavior
- noise-floor / CAD / spectrum tooling
- troubleshooting and validation

## Noise-floor behavior

Noise-floor values are maintained **per channel** and are stored using **direct channel IDs**. This is important when multiple channels share the same frequency but use different spreading factors.

### Current behavior

- `NoiseFloorMonitor` runs every **30 seconds**
- it harvests spectral scan results generated below the Python layer
- TX queues are **not paused** for routine monitoring
- values are persisted and exposed through API/UI

### Fallback chain

Use the following order as the authoritative description:

1. **Spectral scan data**
2. **SX1261 point/radio measurement where available**
3. **RX packet-based estimation fallback**

If all channels remain stuck at **`-120.0 dBm`**, scan data is typically not being collected correctly and the system is running on fallback/default behavior.

## CAD and LBT relationship

CAD and LBT are related but not identical.

### Current rule

**CAD is only active when LBT is enabled for that channel.**

That dependency should be reflected consistently in config, API, and UI.

## RF behavior notes

The architecture is designed to keep RX availability high while still supporting:

- per-channel TX queueing
- LBT checks
- CAD checks
- noise-floor updates
- bridge fan-out

## Troubleshooting hints

### Incorrect per-channel values
If channels with the same frequency but different SF appear to share the wrong values, check whether channel ID mapping is correct end-to-end.

### No useful noise-floor data
If all values stay around `-120.0 dBm`, verify:

- spectral scan output generation
- SX1261 availability
- runtime file permissions
- API/UI metric refresh path

## Related documents

- [`architecture.md`](./architecture.md)
- [`channel_e_sx1261.md`](./channel_e_sx1261.md)
- [`lbt_cad.md`](./lbt_cad.md)
- [`tx_queue.md`](./tx_queue.md)
