# Repositories

## Overview

The WM1303 solution is built from multiple repositories with this repository acting as the **integration, overlay, install, upgrade, and documentation repository**.

## Used repositories

| Repository | Purpose | Branch / base |
|---|---|---|
| `pyMC_WM1303` | overlays, scripts, docs, config, packaging | current repository |
| `sx1302_hal` | HAL + packet forwarder source base | stable HAL 2.10 basis |
| `pyMC_core` | MeshCore core library | `dev` |
| `pyMC_Repeater` | repeater application | `dev` |

## Overlay strategy

This repository intentionally keeps WM1303-specific behavior outside the upstream source repositories as much as possible.

In practice:

- upstream repositories are consumed as source inputs
- overlay files from this repository are applied during install/upgrade
- this repository carries the WM1303-specific integration story

## Why this matters

This approach keeps the project easier to maintain because:

- the upstream dev branches remain recognizable
- WM1303-specific changes are documented in one place
- install/upgrade scripts can reapply the exact required changes
- documentation stays aligned with the delivered system

## Install and upgrade behavior

The install/upgrade scripts:

- retrieve or refresh upstream sources
- apply overlays from this repository
- build HAL/packet forwarder where required
- install/update Python packages
- update config/runtime files
- restart the WM1303-enabled repeater service

## Versioning

This repository tracks its own version through the `VERSION` file and accompanying release notes.

## Related documents

- [`installation.md`](./installation.md)
- [`architecture.md`](./architecture.md)
