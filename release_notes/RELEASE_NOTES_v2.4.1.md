# Release Notes — v2.4.1

**Date:** 2026-04-28  
**Type:** PATCH — performance optimizations, UI improvements, bug fixes

---

## Summary

This patch release eliminates redundant TX guard delays (reducing inter-packet latency by >90%), fixes the Channel Activity chart that was showing 0 TX data, adds complete dedup tracking across all layers, improves the Spectrum tab charts, and adds CAD statistics to the channel status cards.

---

## Changes

### 🚀 Performance — TX Guard Optimization

| File | Change |
|------|--------|
| `tx_queue.py` | Removed 36-line shared RF-chain guard sleep from GlobalTXScheduler; TX serialization now handled entirely by backend `_last_tx_end` guard + `_tx_lock` |
| `wm1303_backend.py` | Reduced dynamic TX hold from 100ms to 50ms for single-packet dedup window |
| `wm1303_backend.py` | Removed redundant +50ms padding from airtime wait calculation |
| `lora_pkt_fwd.c` | Removed dead `custom_lbt_guard_expiry` variable and two 12-line guard-expiry blocks (thread_down + thread_jit) |

**Impact:** Inter-packet TX delay reduced from ~150-200ms to ~37ms. First TX after idle has zero guard delay.

### 📊 UI — Spectrum Tab Improvements

| Change | Detail |
|--------|--------|
| LBT History chart simplified | Removed Noise Floor line, TX Clear dots, TX Busy crosses (6 datasets removed); chart now shows only LBT RSSI, RX RSSI, RX SNR, and LBT Threshold |
| CRC Error Rate bar chart removed | Redundant bottom chart removed; RX CRC Error Ratio per Channel (line chart) retained as single source of truth |
| TX Airtime & Wait Time dual Y-axis | Wait time datasets moved to right Y-axis (y2) so small wait values (~0.1-0.4ms) are visible instead of flat-lining against large airtime values (~500-8000ms) |
| CRC Error Rate chart relocated | Moved from Status tab to bottom of Spectrum tab |

### 📊 UI — Channel Activity Chart Fix

| File | Change |
|------|--------|
| `wm1303_api.py` | Fixed `tx_activity` API: replaced broken within-bucket delta calculation with consecutive-row deltas; both WM1303 channels and Channel E now return correct TX timeseries data |

**Root cause:** With ~60s recording intervals and 60s bucket size, each bucket contained exactly 1 row, making the "need ≥2 rows per bucket" delta calculation always return 0.

### 📊 UI — CAD Statistics in Channel Cards

| File | Change |
|------|--------|
| `wm1303_api.py` | Added `cad_clear` and `cad_detected` fields to live channel status API, tx_queues API (both WM1303 channels and Channel E) |
| `wm1303.html` | Added CAD row in channel status cards (Channels tab), showing "X detected / Y clear" with color coding, same style as existing LBT row |

### 📊 UI — Complete Dedup Tracking

| File | Change |
|------|--------|
| `wm1303_backend.py` | Added `hal_tx_echo` and `multi_demod` dedup event recording in `_process_rxpk()` |
| `packet_router.py` | Added `companion_dedup` event recording |
| `wm1303_api.py` | All 3 new event types added to SQL queries and totals; fixed `tx_echo` event type name (was `echo`, never matched) |
| `wm1303.html` | 3 new stat cards + chart datasets: HAL Echo (orange), Multi-Demod (purple), Companion (blue) |

**Dedup tab now shows all 7 layers:** Forwarded, Duplicate, Bridge Echo, Filtered, HAL Echo, Multi-Demod, Companion.

### 🔧 UI — Queue Delay Sub-row Removed

| File | Change |
|------|--------|
| `wm1303.html` | Removed redundant "Queue delay" sub-row from Processing phase bar in trace UI (no longer applicable after guard optimization) |

### 🔧 HAL — Comment Updates

| File | Change |
|------|--------|
| `lora_pkt_fwd.c` | Updated LBT RSSI sentinel comments to clarify they are overwritten by `lgw_lbt_get_last_rssi()` post-send |

---

## Files Modified (6)

| File | Lines Changed |
|------|---------------|
| `overlay/hal/packet_forwarder/src/lora_pkt_fwd.c` | +3 / -34 |
| `overlay/pymc_core/src/pymc_core/hardware/tx_queue.py` | +1 / -37 |
| `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` | +33 / -28 |
| `overlay/pymc_repeater/repeater/packet_router.py` | +8 / -0 |
| `overlay/pymc_repeater/repeater/web/html/wm1303.html` | ~245 / ~230 |
| `overlay/pymc_repeater/repeater/web/wm1303_api.py` | +78 / -60 |

## Scripts

- `install.sh` — no changes needed (all overlay files already covered)
- `upgrade.sh` — no changes needed (all overlay files already covered)

## Upgrade Notes

- After upgrade, HAL rebuild is required (handled automatically by `upgrade.sh`)
- Service restart required for Python changes
- Hard refresh (Ctrl+Shift+R) recommended for UI changes
