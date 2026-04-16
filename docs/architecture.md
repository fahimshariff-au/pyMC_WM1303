# System Architecture

> pyMC WM1303 — Multi-channel MeshCore bridge/repeater for SenseCAP M1

## Overview

pyMC WM1303 turns a **SenseCAP M1** into a **multi-channel MeshCore bridge and repeater** built around the **WM1303 concentrator** and an additional **SX1261-backed Channel E path**.

The system now operates as a **5-channel platform**:

- **Channel A-D** are the main logical radio channels exposed through the concentrator-backed `VirtualLoRaRadio` layer.
- **Channel E** is the dedicated SX1261-backed path that grew from a helper/scanner role into a meaningful part of the radio story and therefore has its own document: [`channel_e_sx1261.md`](./channel_e_sx1261.md).

The implementation combines:

- a modified **SX1302 HAL**
- a modified **`lora_pkt_fwd`** packet forwarder
- overlay-based integration in **pyMC_core** and **pyMC_Repeater**
- a dedicated **WM1303 Manager UI** and API

## Design priorities

The project is designed around these principles:

1. **RX availability has priority**.
2. **TX should happen as fast as possible** once queued.
3. Monitoring tasks such as spectral scan and noise-floor collection must **not unnecessarily block RX/TX**.
4. Documentation, install, and upgrade flow must match the actual deployed system.

## 5-channel architecture

### Logical channels

| Channel | Main role | Notes |
|---|---|---|
| Channel A | VirtualLoRaRadio | Normal mesh traffic path |
| Channel B | VirtualLoRaRadio | Normal mesh traffic path |
| Channel C | VirtualLoRaRadio | Normal mesh traffic path |
| Channel D | VirtualLoRaRadio | Normal mesh traffic path |
| Channel E | SX1261-backed path | See dedicated Channel E document |

The main bridge/repeater logic is aware of multiple channels and uses **per-channel configuration, metrics, queueing, and UI/API exposure**.

## Hardware responsibility split

### SX1302 / SX1250 side
The concentrator side is responsible for the primary multi-channel receive/transmit pipeline used by Channels A-D.

### SX1261 side
The SX1261 side is used for **Channel E-related behavior** and for **radio-management functions** such as spectral scan, LBT-related measurement support, and CAD-related support where applicable.

## SPI split

The system uses a split SPI model:

| Device | Purpose |
|---|---|
| `/dev/spidev0.0` | SX1302 / SX1250 concentrator path |
| `/dev/spidev0.1` | SX1261 path |

This separation is important because it allows **SX1261 operations to run independently** from the main concentrator path, which helps protect RX availability and keeps TX delays low.

The implementation has evolved beyond the early “2 MHz only” assumptions. The overlay and runtime behavior were optimized so that SPI traffic is handled more efficiently while keeping the architecture safe for the current implementation.

## Layered architecture

### 1. Hardware layer

- SenseCAP M1 (Raspberry Pi based)
- WM1303 HAT
- SX1302/SX1250 concentrator radio path
- SX1261 companion radio path
- board-specific GPIO reset/power helpers

### 2. HAL / packet forwarder layer

- modified `libloragw`
- modified `lora_pkt_fwd`
- spectral scan support
- SX1261 integration
- custom JSON-driven configuration
- UDP server on **`:1730`**

### 3. Backend layer

Core backend components include:

| Component | Role |
|---|---|
| `WM1303Backend` | Main radio/backend coordinator |
| `VirtualLoRaRadio` | Per-channel LoRaRadio abstraction |
| `TXQueue` | Per-channel queued TX scheduling |
| `NoiseFloorMonitor` | Periodic spectral/noise-floor collection |
| `BridgeEngine` | Packet routing between channels and repeater logic |
| `channel_e_bridge.py` | Channel E integration path in repeater side |

## Runtime data flow

### RX path

1. RF is received by concentrator or SX1261-backed path.
2. HAL / forwarder converts receive events into UDP traffic.
3. `WM1303Backend` parses incoming packets.
4. Packets are mapped to the correct logical channel.
5. `VirtualLoRaRadio` exposes them to the repeater/bridge stack.
6. `BridgeEngine` evaluates rules, deduplication, and packet-type routing.
7. Runtime statistics are persisted and exposed to the UI/API.

### TX path

1. A packet is accepted by bridge/repeater logic.
2. It is placed into the correct **per-channel TX queue**.
3. The queue applies TTL, queue-depth, LBT, and CAD-related logic as configured.
4. TX is emitted via UDP `PULL_RESP` towards `lora_pkt_fwd`.
5. Forwarder and HAL transmit the frame and provide TX acknowledgement feedback.

### Spectral scan / noise-floor path

There are **two different cadences** involved:

| Layer | Interval | Purpose |
|---|---|---|
| HAL / forwarder scan pacing | about **1 second** | Try to perform scan work when TX allows it |
| Python `NoiseFloorMonitor` | every **30 seconds** | Harvest results and update runtime noise-floor state |

Important behavior:

- routine noise-floor monitoring **must not pause TX queues**
- the old separate noise-floor TX hold was removed
- the remaining intentional TX hold is the **2-second batch window**

## Bridge engine role

The bridge layer is responsible for:

- source-to-target packet routing
- packet-type filtering
- deduplication / echo suppression
- calling repeater logic where required
- feeding packets into the correct TX queues

Although implemented here as part of the WM1303 integration, the bridge concept itself is largely generic and can also be applied beyond this specific hardware integration.

## SSOT configuration model

The current project uses **`wm1303_ui.json` as the main source of truth** for UI/runtime-oriented WM1303 state.

### Practical meaning

- API/UI helper paths read from `wm1303_ui.json`
- channel and runtime-oriented settings are persisted there first
- compatibility/runtime synchronization into `config.yaml` is done where needed
- save operations trigger channel synchronization so runtime and repeater integration stay aligned

This is important for:

- active/inactive channel selection
- LBT/CAD behavior
- channel-specific settings
- UI consistency after reloads

## Per-channel metrics and mapping

Per-channel runtime metrics are tracked using **direct channel identifiers**, which is especially important when channels share a frequency but differ in spreading factor.

This avoids incorrect merging of statistics and ensures:

- correct noise-floor association
- correct CAD/LBT history
- correct chart rendering
- correct API exposure per channel

## Web / API layer

The web layer consists of:

- **WM1303 Manager UI** (`wm1303.html`)
- WM1303 REST API under **`/api/wm1303/*`**
- WebSocket/live updates for charts and status
- integration with the existing pyMC repeater UI/server stack

Main user-facing areas include:

- Status
- Channels
- Bridge
- Spectrum
- Advanced configuration

## Installed structure

Typical runtime layout:

- `/opt/pymc_repeater/` — main runtime installation
- `/etc/pymc_repeater/` — config files including synced runtime config
- `/tmp/` — runtime-generated files, metrics, scan output, and transient state

## Related documents

- [`channel_e_sx1261.md`](./channel_e_sx1261.md)
- [`radio.md`](./radio.md)
- [`software.md`](./software.md)
- [`lbt_cad.md`](./lbt_cad.md)
- [`configuration.md`](./configuration.md)
- [`api.md`](./api.md)
- [`ui.md`](./ui.md)
