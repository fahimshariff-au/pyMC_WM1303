# Release Notes — v2.4.7

**Date:** 2026-05-05

## Summary

Uniform all-channel packet tracing with redesigned Tracing UI — full MeshCore packet dissection, multi-byte hash support, duration timeline chart, and cross-channel visibility.

---

## New Features

### Uniform All-Channel Packet Tracer
- **New module `uniform_tracer.py`** — central packet tracer that hooks into RX callbacks of ALL configured channels (not just channel_e)
- Traces packets from channel_a (EU-Narrow), channel_e (local-test), and any future channels uniformly
- Friendly channel names displayed instead of internal identifiers
- MAX_TRACES increased from 200 to 1000 for longer history retention
- Retry mechanism for channel_e registration (handles async startup timing)

### Redesigned Tracing Tab UI
- **8-column packet detail table**: Full Hash, Hop Count, Source, Hash Size (bytes), Hop Path, Src → Last hop → Dst, Payload, Channel
- **Full payload display**: complete hex dump + ASCII representation (no truncation)
- **Metadata panel**: expandable per-packet details with timing, RSSI/SNR, coding rate
- **Copy-to-clipboard buttons** for packet hash, payload hex, and full metadata
- **Multi-byte hash detection**: correctly identifies and displays 1-byte, 2-byte, and 3-byte path hashes
- **Hop legend**: deduplicated, compact format with byte-size indicator
- **CRC_ERROR handling**: suppresses hash parsing for corrupted packets to avoid misleading data

### Packet Duration Timeline Chart
- Chart.js-based line chart showing packet processing duration per type
- Configurable filter: excludes traces < 250 ms and > 10 s
- Per-packet-type color coding
- Interactive tooltips with timing details

---

## Bug Fixes

- **install.sh / upgrade.sh**: Added missing `uniform_tracer.py` to overlay copy loop — previously new installs would not receive this file

---

## Technical Details

### Files Changed
| File | Change |
|---|---|
| `overlay/pymc_repeater/repeater/uniform_tracer.py` | **NEW** — Central cross-channel packet tracer |
| `overlay/pymc_repeater/repeater/bridge_engine.py` | Added uniform tracer hooks, CRC_ERROR hash suppression |
| `overlay/pymc_repeater/repeater/main.py` | UniformTracer initialization, channel handler registration with retry |
| `overlay/pymc_repeater/repeater/web/packet_trace.py` | Multi-channel support, friendly names map, MAX_TRACES 1000 |
| `overlay/pymc_repeater/repeater/web/html/wm1303.html` | Complete Tracing tab redesign (395 lines added) |
| `install.sh` | Added `uniform_tracer.py` to overlay deployment loop |
| `upgrade.sh` | Added `uniform_tracer.py` to overlay deployment loop |

### Memory Impact
- MAX_TRACES 1000 × ~4 KB per trace ≈ 4 MB maximum (bounded deque, auto-evicts)
- No new database tables — traces are in-memory only
- No additional threads — hooks into existing RX callback infrastructure

---

## Upgrade Notes

Standard bootstrap one-liner upgrades automatically. The new `uniform_tracer.py` will be deployed by the updated overlay copy loop.

After upgrade, hard-refresh the WM1303 Manager UI (Ctrl+Shift+R) to load the redesigned Tracing tab.
