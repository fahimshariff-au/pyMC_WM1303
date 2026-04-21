# Release Notes — v2.2.0

**Release date:** 2026-04-21  
**Previous version:** v2.1.2  
**Upgrade:** Use the bootstrap one-liner — HAL recompilation and DB migration are handled automatically

---

## Highlights

- **Tracing tab overhaul** — full RX→TX packet lifecycle, dedup/echo annotations, per-channel LBT/CAD attribution, formatted RX RF metadata.
- **Spectrum tab at 1-minute resolution** — all charts (LBT History, Channel Activity, RSSI, SNR, CAD Activity, Noise Floor) now at 60 s buckets with continuous (spanGaps) plotting.
- **Centralized metrics retention** — new `metrics_retention.py` module, uniform 8-day retention across 11 tables, weekly VACUUM, 5 legacy cleaners retired.
- **Hardware CAD counters wired** (latent bug from v2.1.0) — `cad_hw_clear/detected` + `cad_sw_clear/detected` now written correctly, unlocking the CAD Activity chart.
- **Channel packets persistence fix** (latent bug) — packets bridged by `bridge_engine.inject_packet()` were not being written to the `packets` table; fixed.
- **Spectral scan collector rewrite** — now reads `/tmp/pymc_spectral_results.json` (written by the HAL fork) every 60 s; previously tailed journalctl and received nothing.
- **Debug bundle v2** — +13 additions including manifest.json, 7 metric table dumps, packet traces, bridge rules, adv_config snapshot, packets_tail, versions.txt, with extended privacy redactions.
- **Design-principles file** — RX availability #1 and TX-ASAP formalized in `design-principles.promptinclude.md`.

---

## 🚀 New Features

### Tracing Tab — Full Lifecycle Visualization

| Aspect | Detail |
|---|---|
| **Tab position** | Moved between Bridge Rules and Logs for natural reading order. |
| **`received` step** | New first step for every RX with channel, RSSI, SNR, noise floor, and friendly channel name on multi-line formatted output. |
| **RX vs TX labels** | Step labels disambiguate `bridge_forward`, `tx_enqueue`, `tx_send`, `tx_ack` per direction. |
| **Channel pills** | Multiple TX channels shown as pills at the end of `bridge_forward` and `tx_enqueue`. |
| **Dedup/echo badges** | Green ✅ badge rendered on trace rows identified as dedup or echo events. |
| **LBT/CAD per channel** | `cad_check` and `lbt_check` grouped with their `tx_send` and attributed to the correct channel via detail text. |
| **Files** | `overlay/pymc_repeater/repeater/web/packet_trace.py` (new), `web/wm1303_api.py`, `web/html/wm1303.html` |

### Hybrid `send_tx_ack` Flow

| | Detail |
|---|---|
| **What** | Added a post-TX ACK that carries CAD/LBT result data while preserving the existing enqueue-time ACK. |
| **Why** | Enqueue-time ACK arrives too early to know CAD/LBT outcome; the second ACK closes the feedback loop without delaying TX. |
| **Files** | `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py`, `tx_queue.py` |

### Centralized Metrics Retention

| | Detail |
|---|---|
| **Module** | `overlay/pymc_repeater/repeater/metrics_retention.py` (new) — singleton background thread, started from `main.py`. |
| **Retention** | Uniform **8 days** across 11 metric tables (previously mixed 7/8/31). |
| **Cadence** | Cleanup every hour, VACUUM weekly. |
| **Config key** | `storage.retention.metrics_days` (default 8). |
| **Tables covered** | `packets`, `adverts`, `crc_errors`, `noise_floor`, `dedup_events`, `noise_floor_history`, `cad_events`, `packet_activity`, `origin_channel_stats`, `channel_stats_history`, `spectrum_scans`. |
| **Legacy cleaners removed** | `sqlite_handler.py`, `wm1303_api.py`, `wm1303_backend.py`, `bridge_engine.py`, `engine.py`, `spectrum_collector.py`. |

### Dedup Configuration — Single Source of Truth

| | Detail |
|---|---|
| **Problem** | Dedup TTL / cache TTL / max cache size were defined in three places with drift risk. |
| **Fix** | Advanced-config tab is now SSOT; config file, UI API, and runtime are kept in three-way alignment. |
| **Files** | `web/wm1303_api.py`, `web/html/wm1303.html`, `repeater/config.py`, `engine.py` |

### Debug Bundle v2

| | Detail |
|---|---|
| **Additions (+13)** | `manifest.json`, 7 metric-table dumps, `packet_traces` (200 from ring buffer), bridge rules, adv_config snapshot, `versions.txt`, `packets_tail` (500 rows with redactions). |
| **Privacy** | Redact list extended with `gateway_id`, `gateway_ID`, `concentrator_serial`. |
| **Cleanup** | Dead `SELECT * FROM metrics` query removed. |
| **File** | `overlay/pymc_repeater/repeater/web/debug_collector.py` |

### Design-Principles File

| | Detail |
|---|---|
| **What** | New `design-principles.promptinclude.md` at project root formalizing fundamental rules. |
| **Key principles** | RX availability is **#1 priority**; TX must be **sent ASAP** after entering the queue; no TX holds for spectral scan / noise-floor measurements; version bump policy (MAJOR/MINOR/PATCH) clarified. |

---

## 🐛 Bug Fixes

### 1. HW CAD Counters Never Incremented (latent since v2.1.0)

| | Detail |
|---|---|
| **Problem** | `cad_events` rows recorded the same value into `cad_clear` and `cad_hw_clear`, and `cad_hw_detected` was always 0 — the CAD Activity chart was blank. |
| **Root cause** | No code path propagated the HW CAD result from `lora_pkt_fwd` back into the packet-activity recorder. |
| **Fix** | New `TXQueueManager.record_hw_cad_result(channel_id, cad_result)` method, called from `wm1303_backend._send_for_scheduler()` post-TX_ACK. `_packet_activity_recorder` now reads dedicated `cad_hw_clear/detected` + `cad_sw_clear/detected` keys and writes them to the correct columns. |
| **Files** | `tx_queue.py`, `wm1303_backend.py`, `bridge_engine.py`, `wm1303_api.py` |

### 2. `channel_e` Packets Not Persisted (broader than first thought)

| | Detail |
|---|---|
| **Problem** | Packets injected via `bridge_engine.inject_packet()` bypassed the repeater-counter path used by `_rx_loop()`. No `packets` rows since 15:14:55 pre-fix; all `channel_e` traffic was invisible to the DB and to every downstream chart. |
| **Fix** | `inject_packet()` now calls `_update_repeater_counters()` exactly like `_rx_loop()` does, while skipping `source=='repeater'` to avoid duplicate rows. |
| **File** | `overlay/pymc_repeater/repeater/bridge_engine.py` |

### 3. Adv. Config — Save & Restart JavaScript SyntaxError

| | Detail |
|---|---|
| **Problem** | Save & Restart button triggered a JavaScript SyntaxError, silently failing. |
| **Fix** | Syntax fix and removal of hardcoded placeholder values that masked the real config being posted. |
| **File** | `overlay/pymc_repeater/repeater/web/html/wm1303.html` |

### 4. `spectrum_scans` Collector Never Received Data

| | Detail |
|---|---|
| **Problem** | Collector tailed journalctl for spectral lines that the HAL fork no longer emits (writes atomic JSON instead). The `spectrum_scans` table stayed empty. |
| **Fix** | Rewrote collector to poll `/tmp/pymc_spectral_results.json` every 60 s. |
| **File** | `overlay/pymc_repeater/repeater/web/spectrum_collector.py` |

### 5. Dedup TTL Mismatch Between Config and Runtime

| | Detail |
|---|---|
| **Problem** | Advanced-config UI reported one TTL, runtime used another — no single source of truth. |
| **Fix** | Three-way alignment (config file, UI API, runtime) — see *Dedup Configuration — Single Source of Truth* above. |

---

## ✨ Improvements

### Spectrum Tab — 1-Minute Resolution

| Chart | Before | After |
|---|---|---|
| Channel stats snapshot interval (source) | 300 s | **60 s** |
| `tx_activity` / `signal_quality` / `lbt_history` / `origin_stats` / `cad_stats` API bucket | 600 s | **60 s** |
| LBT History | noise floor only | continuous NF + LBT RSSI + RX RSSI (spanGaps) + RX SNR (right axis, spanGaps) + LBT threshold edge-to-edge line + TX markers |
| Channel Activity | 10-min bars | 1-min bars with non-zero filter |
| Noise-floor chart | fixed radius | density-aware radius |
| RSSI / SNR / CAD Activity per channel | 10-min buckets | 1-min buckets, spanGaps |

### UI Polish

- Channel pills at end of `bridge_forward` / `tx_enqueue` trace rows.
- Friendly channel names used consistently (never as reference IDs).
- `elapsed_ms` semantics clarified in tooltips and docs.
- Trace step-level channel preserved via detail text rather than dropped.

### Trace Clarity

- Dedup/echo events explicitly emitted as trace steps with ✅ badges.
- LBT/CAD events per `tx_send` with per-channel attribution.
- `received` step carries full RF metadata in multi-line format.

---

## 🔧 Under the Hood

| Area | Change |
|---|---|
| New module | `overlay/pymc_repeater/repeater/metrics_retention.py` (161 lines) |
| New module | `overlay/pymc_repeater/repeater/web/packet_trace.py` (179 lines) |
| Config template | `bridge.dedup_ttl` renamed to `bridge.dedup_ttl_seconds`; `repeater.cache_ttl` bumped 30→60; `repeater.max_cache_size: 1000` added |
| Schema (additive) | `cad_events.{cad_hw_clear, cad_hw_detected, cad_sw_clear, cad_sw_detected}` — already migrated on existing installs; `CREATE TABLE IF NOT EXISTS` protects fresh installs |
| Removed | Five legacy inline retention cleaners |
| Formalized | Design principles (RX first, TX ASAP, no TX holds) |

---

## 📁 Files Changed

| File | Summary |
|---|---|
| `overlay/pymc_repeater/repeater/metrics_retention.py` | **NEW** — centralized retention (singleton, 8-day, weekly VACUUM) |
| `overlay/pymc_repeater/repeater/web/packet_trace.py` | **NEW** — packet trace ring buffer + API helpers |
| `overlay/pymc_repeater/repeater/bridge_engine.py` | `inject_packet()` repeater-counter fix; origin-channel-first plumbing; dedup event emission |
| `overlay/pymc_repeater/repeater/channel_e_bridge.py` | origin_channel plumbing, minor hardening |
| `overlay/pymc_repeater/repeater/engine.py` | Removed legacy retention cleaner; storage integration |
| `overlay/pymc_repeater/repeater/main.py` | Starts `metrics_retention` at boot |
| `overlay/pymc_repeater/repeater/web/wm1303_api.py` | 1-min buckets on all spectrum endpoints; HW CAD counters; packet_trace integration; legacy cleaner removed |
| `overlay/pymc_repeater/repeater/web/html/wm1303.html` | Tracing tab overhaul; Spectrum charts; Adv. Config JS fix |
| `overlay/pymc_repeater/repeater/web/spectrum_collector.py` | Rewritten to poll `/tmp/pymc_spectral_results.json` every 60 s |
| `overlay/pymc_repeater/repeater/web/debug_collector.py` | Debug bundle v2 additions + redaction extensions |
| `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` | Hybrid `send_tx_ack`, HW CAD result propagation |
| `overlay/pymc_core/src/pymc_core/hardware/tx_queue.py` | `record_hw_cad_result()` added |
| `overlay/hal/packet_forwarder/src/lora_pkt_fwd.c` | Spectral scan writes atomic JSON to `/tmp/pymc_spectral_results.json`; TX queue tuning |
| `config/config.yaml.template` | `dedup_ttl`→`dedup_ttl_seconds`, `cache_ttl: 60`, `max_cache_size: 1000` |
| `design-principles.promptinclude.md` | **NEW** — formalizes RX-first / TX-ASAP / version-bump rules |

*(Diff summary: 13 files changed, +1770 / −231 lines; plus 2 new files.)*

