# pyMC WM1303

pyMC WM1303 is a **SenseCAP M1 / WM1303 integration project** that turns the device into a **multi-channel MeshCore bridge and repeater**.

It combines upstream source repositories with WM1303-specific overlays, scripts, configuration, API/UI extensions, and documentation maintained in this repository.

## Current scope

The project now documents and implements a **5-channel architecture**:

- **Channel A-D** through the concentrator-backed VirtualLoRaRadio model
- **Channel E** through the SX1261-backed path and related runtime support

Channel E became large enough to deserve its own document:

- [`docs/channel_e_sx1261.md`](docs/channel_e_sx1261.md)

## Main features

- multi-channel MeshCore bridge/repeater operation
- WM1303 backend integration for pyMC_core / pyMC_Repeater
- bridge engine and per-channel TX queueing
- WM1303 Manager UI and REST API
- spectral scan, noise-floor, LBT, and CAD-related functionality
- install and upgrade scripts that reapply the required overlay-based integration

## Architecture at a glance

The main runtime layers are:

1. **Hardware** — SenseCAP M1, WM1303, SX1261
2. **HAL / packet forwarder** — modified `libloragw` and `lora_pkt_fwd`
3. **Backend** — `WM1303Backend`, `VirtualLoRaRadio`, `TXQueue`, bridge integration
4. **Web/API** — WM1303 Manager UI, REST API, live runtime data

## Configuration model

The WM1303-specific runtime/UI source of truth is centered on:

- `config/wm1303_ui.json` in the repository
- `/etc/pymc_repeater/wm1303_ui.json` on the installed system

`config.yaml` is still used for repeater compatibility/runtime integration, but it is no longer the best place to explain WM1303-specific UI/runtime behavior on its own.

## Runtime behavior highlights

- **CAD depends on LBT** per channel
- the old **noise-floor hold** was removed
- the remaining intentional TX hold is the **2-second batch window**
- routine noise-floor monitoring should **not pause TX queues**
- per-channel metrics are tracked by **channel ID**, which matters for same-frequency / different-SF cases

## Repository role

This repository contains:

- overlay files
- install/upgrade/bootstrap scripts
- config templates and runtime config assets
- WM1303-specific documentation
- release/version tracking

It uses these upstream sources:

- `sx1302_hal` as HAL / packet forwarder base
- `pyMC_core` `dev`
- `pyMC_Repeater` `dev`

## Documentation

### Core documents

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/hardware.md`](docs/hardware.md)
- [`docs/software.md`](docs/software.md)
- [`docs/radio.md`](docs/radio.md)
- [`docs/configuration.md`](docs/configuration.md)
- [`docs/api.md`](docs/api.md)
- [`docs/ui.md`](docs/ui.md)
- [`docs/lbt_cad.md`](docs/lbt_cad.md)
- [`docs/tx_queue.md`](docs/tx_queue.md)
- [`docs/installation.md`](docs/installation.md)
- [`docs/repositories.md`](docs/repositories.md)

### Channel E

- [`docs/channel_e_sx1261.md`](docs/channel_e_sx1261.md)

### Diagram assets

- [`docs/images/architecture-overview.png`](docs/images/architecture-overview.png)
- [`docs/images/component-dependencies.png`](docs/images/component-dependencies.png)
- [`docs/images/data-flow-rx.png`](docs/images/data-flow-rx.png)
- [`docs/images/data-flow-tx.png`](docs/images/data-flow-tx.png)
- [`docs/images/spectral-scan-flow.png`](docs/images/spectral-scan-flow.png)
- [`docs/diagram-style-guide.md`](docs/diagram-style-guide.md)

## No GitHub push performed

Changes remain local unless you explicitly ask to push them.
