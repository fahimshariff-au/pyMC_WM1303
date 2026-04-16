# Installation

## Overview

The installation flow prepares Raspberry Pi OS Lite on a SenseCAP M1 for the WM1303-based pyMC runtime.

The repository is designed so that installation uses upstream source repositories plus **overlay files from this repository**, rather than storing direct modifications in the upstream forks.

## Source repositories and branches

| Repository | Role | Branch / base |
|---|---|---|
| `sx1302_hal` | HAL and packet forwarder source | stable HAL 2.10 basis |
| `pyMC_core` | core MeshCore library | `dev` |
| `pyMC_Repeater` | repeater application | `dev` |
| `pyMC_WM1303` | overlays, scripts, docs, config | this repository |

## High-level install flow

1. update the OS and install build/runtime prerequisites
2. enable required interfaces such as SPI
3. clone/update required upstream repositories
4. apply WM1303 overlay files from this repository
5. build HAL and packet forwarder
6. install/update Python packages
7. install config, scripts, and service files
8. prepare runtime permissions/files
9. start and validate the service

## Overlay strategy

This project keeps WM1303-specific changes in overlay form.

That means installation:

- fetches upstream repositories
- copies overlay files into the correct locations
- rebuilds components as needed
- avoids editing the fork repositories as the primary source of truth in this project

## Runtime preparation

The install/upgrade flow also accounts for runtime file handling and permissions, including cases where files under `/tmp` need to exist with the right ownership/permissions before the service starts using them.

## SPI and platform setup

Installation should ensure:

- SPI is enabled
- required packages for build and runtime are installed
- required user permissions and group membership are in place
- service startup can access the radio hardware and runtime files

## Post-install validation

A successful install should validate at least:

- service starts correctly
- API is reachable
- UI is reachable
- channels are loaded correctly
- noise-floor/spectrum-related runtime data starts updating
- SX1261-related functionality is available where expected

## Upgrade behavior

`upgrade.sh` follows the same general model:

- stop service
- refresh/update sources
- reapply overlays
- rebuild as needed
- reinstall/update Python/runtime pieces
- merge or preserve configuration carefully
- restart service

## Related documents

- [`repositories.md`](./repositories.md)
- [`configuration.md`](./configuration.md)
- [`hardware.md`](./hardware.md)
