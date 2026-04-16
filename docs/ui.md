# WM1303 Manager UI

## Overview

The WM1303 Manager UI provides the dedicated operational interface for the WM1303 integration on top of the existing pyMC repeater web stack.

## Main tabs

Typical areas include:

- Status
- Channels
- Bridge
- Spectrum
- Advanced Config

## 5-channel model in the UI

The UI should be understood as operating on a **5-channel architecture**.

- Channel A-D represent the concentrator-backed logical channels
- Channel E represents the SX1261-backed part of the platform story

Where relevant, Channel E should be visible in charts, status views, and configuration flows.

## Channels tab

The Channels tab is used to inspect and configure per-channel settings such as:

- active state
- frequency
- SF/BW
- LBT behavior
- CAD behavior where enabled

## CAD / LBT controls

The UI reflects the runtime rule:

- **CAD is unavailable unless LBT is enabled for that channel**

This should appear as disabled/greyed controls when LBT is off.

## Noise-floor and signal views

Displayed values are backed by persisted runtime metrics rather than only short-lived in-memory buffers.

This improves:

- chart continuity
- channel-specific visibility
- handling of same-frequency / different-SF channels

## Runtime refresh behavior

UI changes are designed to apply quickly through runtime reload/cache behavior and should not normally require full service restarts for regular WM1303 Manager changes.

## SSOT behavior

The UI effectively works against the WM1303 SSOT model centered on `wm1303_ui.json`, with downstream synchronization where needed.

## Related documents

- [`configuration.md`](./configuration.md)
- [`api.md`](./api.md)
- [`channel_e_sx1261.md`](./channel_e_sx1261.md)
