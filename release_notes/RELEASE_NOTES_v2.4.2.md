# Release Notes — v2.4.2

**Release date:** 2026-04-28

This release introduces per-channel Listen Before Talk (LBT) enable/disable, fixes a critical AGC handshake issue, optimizes CAD scan retries, improves trace UI accuracy, and updates the README.

---

## Critical Fix

### Per-channel LBT: AGC handshake fix
- **Problem:** Disabling LBT on a specific channel caused the HAL to skip the SX1261 LBT scan entirely. Because the SX1302 AGC firmware expects a completed LBT handshake for every TX (when LBT is globally enabled), skipping the scan prevented the AGC from enabling the PA/FEM power amplifier. The TX appeared successful in logs (`TX_ACK=sent`) but **no RF signal was actually transmitted**.
- **Root cause:** `lgw_lbt_start()` returned early without performing the carrier-sense scan, so the AGC never received the signal to switch the FEM from LNA (receive) to PA (transmit) mode.
- **Fix:** Instead of skipping the LBT scan, channels with LBT disabled now use a permit-all RSSI threshold of 127 dBm. The AGC handshake always completes, but the threshold is unreachable so TX is never blocked.
- **Impact:** The LBT scan still runs for all channels (~5-10 ms overhead per TX), but this is unavoidable due to the SX1302+SX1261 AGC architecture.
- **Files:** `loragw_lbt.c`, `loragw_hal.h`, `lora_pkt_fwd.c`, `wm1303_backend.py`

---

## New Features

### Per-channel LBT enable/disable
- LBT can now be enabled or disabled independently per channel through the WM1303 Manager UI.
- Added `bool enable` field to `lgw_conf_chan_lbt_s` struct in `loragw_hal.h`.
- The packet forwarder parses the per-channel `enable` field from `global_conf.json` with backward-compatible default (`true`).
- The Python backend generates the per-channel `enable` flag in the LBT channel configuration.
- Disabled channels use a permit-all threshold (127 dBm) to maintain the AGC handshake while never blocking TX.
- The `hal_lbt_lookup()` function now returns the per-channel enable status for accurate trace/API reporting.

---

## Optimizations

### CAD noisefloor skip on retries
- The FSK RX noisefloor measurement (Phase 2 of `sx1261_cad_scan()`) is now skipped on CAD retries.
- The noisefloor is only measured on the first CAD scan; retries reuse the initial value.
- Added `skip_noisefloor` parameter to `sx1261_cad_scan()` function signature.
- **Savings:** ~12 ms per CAD retry (~10% faster retries).
- **Files:** `loragw_sx1261.h`, `loragw_sx1261.c`, `lora_pkt_fwd.c`

---

## Trace UI Improvements

### CAD scan duration accuracy
- The trace now displays actual HAL-measured CAD scan duration instead of a hardcoded 72 ms estimate.
- Duration correctly scales with retry count (e.g., 0 retries ≈ 75 ms, 5 retries ≈ 570 ms, 15 retries ≈ 1450 ms).
- Falls back to the estimated constant when HAL duration data is unavailable.

### Simplified phase grouping
- Merged RX + Routing phases into a single **Processing** phase.
- Guard phase absorbed into TX phase.
- Reduces visual clutter from 7+ phase bars to 2-3 (Processing → TX → TX).
- Dedup events (dedup_check, dedup_skip, dedup_drop, echo_dedup) remain visible within the Processing phase.

### Trace event ordering fix
- `received` event now always precedes `dedup_check` for all channel types (was reversed for local-test/channel_a packets).
- Added missing `bridge_inject` event for local-test packets, ensuring consistent 24-step traces across all message types.

---

## README Update

- Rewritten project description: clearer explanation of what the project does and its hardware scope.
- Added "Key Features" section highlighting 5-channel support, per-channel configuration, and per-channel LBT.
- Added note about hardware compatibility beyond SenseCAP M1.

---

## Files Changed (9)

| File | Type | Changes |
|------|------|---------|
| `overlay/hal/libloragw/inc/loragw_hal.h` | C header | Added `enable` field to LBT channel struct |
| `overlay/hal/libloragw/inc/loragw_sx1261.h` | C header | Added `skip_noisefloor` parameter to CAD function |
| `overlay/hal/libloragw/src/loragw_lbt.c` | C source | Per-channel LBT with permit-all threshold |
| `overlay/hal/libloragw/src/loragw_sx1261.c` | C source | Noisefloor skip on CAD retries |
| `overlay/hal/packet_forwarder/src/lora_pkt_fwd.c` | C source | Per-channel LBT parsing and enable reporting |
| `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` | Python | LBT config generation + CAD duration trace fix |
| `overlay/pymc_repeater/repeater/bridge_engine.py` | Python | Trace event ordering + missing bridge_inject |
| `overlay/pymc_repeater/repeater/web/html/wm1303.html` | HTML/JS | Simplified phase grouping |
| `README.md` | Markdown | Updated project description and features |

---

## Upgrade Notes

- No changes required to `install.sh` or `upgrade.sh`.
- The HAL binary must be rebuilt (handled automatically by upgrade script).
- Existing `wm1303_ui.json` configurations are backward compatible — channels without an explicit `lbt_enabled` setting default to `true`.
- The `enable` field in `global_conf.json` LBT channel entries defaults to `true` if absent.
