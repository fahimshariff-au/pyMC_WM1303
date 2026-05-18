# Release Notes v2.4.9

**Status:** ✅ **RELEASED**
**Release date:** 2026-05-18
**VERSION file:** `2.4.9`
**Scope:** Comprehensive changelog covering all work between v2.4.8 and v2.4.9, including multi-region regulatory support, Channel F (`chan_Lora_std`) full equivalence with A–D/E, device-wide sync_word migration, and the new installation wizard.

---

## Summary

v2.4.9 is a **major quality & capability release** focused on three pillars:

1. **Observability** — A ground-up overhaul of the Packet Tracing UI (stats dashboard, analytics, heatmaps, histograms, playback modal) combined with a new path-hash based echo classifier that replaces the legacy time-based heuristic.
2. **Metrics correctness & longevity** — A new tiered metrics query system (Hot/Warm/Cool/Cold) gives reliable visibility up to 8 days back, and a critical fix to the retention aggregator stops counter values from being inflated by SUM-over-cumulative-counters.
3. **Multi-region regulatory support** — Eight regional presets (EU868, US915, AU915, AS923, IN865, JP920, KR920) plus CUSTOM, a new wideband Channel F (`chan_Lora_std`) for BW125/250/500, an 8-preset community catalog, and four new REST endpoints. Resolves Issue #1 (AU915 BW250) and Issue #4 (hardcoded EU868 limits).

In addition, this release brings an upstream overlay refresh (USB/TCP radio support carried in from `pymc_core` dev), a config template overhaul, and many smaller installer/UI fixes.

---

## Highlights

- 🔭 **New Packet Tracing UI** — stats overview panel, analytics panel (heatmap + duration histogram), category filter tabs, mini-timeline sparkline, hop-path diagram, step-by-step playback modal with fine-grained speed control, export buttons, click-to-highlight hashes, real-time pulse animation, slow-trace highlighting, type icons, echo badges, and TX-target chips.
- 🎯 **Path-based echo classification** — `self_echo` / `mesh_echo` / `unknown_echo` classification driven by the local pubkey path-hash, registered with the radio backend at startup. Replaces the legacy time-window heuristic.
- 🗂 **Tiered metrics queries** — `tiered_query.py` (858 lines) seamlessly queries Hot (0–7h raw), Warm (7–24h _1m), Cool (24h–3d _10m), Cold (3–8d _15m) for any chart/timeframe.
- 🛠 **Metrics retention bugfix (critical)** — Cumulative counters (rx_count, tx_count, tx_failed, tx_airtime_ms, tx_bytes, lbt_blocked/passed, pkt_count) now use `MAX(x) - MIN(x)` per bucket instead of `SUM(x)`, fixing massively inflated rollup values.
- 📊 **Dedup tab fix** — `hal_mesh_echo` and `hal_unknown_echo` now properly aggregated and visualized (previously hidden); `dedup_ratio` recalculated to include all non-forwarded events; Self Echo (RF) card renamed for clarity.
- 🌍 **Multi-region support** — 8 regions + CUSTOM, region is a device-wide setting, per-region TX bounds and SX1261 image calibration.
- 📡 **Channel F (`chan_Lora_std`)** — new wideband single-SF channel supporting BW125/250/500, runs in parallel with Channels A–D, available in every region preset (not AU915-only).
- 🧰 **8 community presets** — EU/US/AU/AS/IN/JP/KR + Custom, each defining all six channels (A–F) so users can enable any combination after install.
- 🔌 **Upstream overlay refresh** — `pymc_core` and `pymc_repeater` overlays brought up to upstream HEAD (USB/TCP radio support, `resolve_storage_dir()`, sensor config defaults, safer sync_word parsing).
- 📜 **Config template overhaul** — `config.yaml.template` restructured (231 lines changed) with clear upstream sections and obvious device-specific values.

---

## Detailed Changes

### 🔭 Packet Tracing UI Overhaul (Phases 1–5)

The Tracing tab in the WM1303 Manager UI was rebuilt in five phases. All changes live in `overlay/pymc_repeater/repeater/web/html/wm1303.html` (+1262 lines net since v2.4.8).

**Phase 1 — Quick wins**
- New `traceStatsPanel`: dashboard grid with summary counters (total traces, slowest, average, echo split, OK/error counts) for the selected window.
- Type icons on every trace row for quick category recognition.
- Slow-trace highlighting (visual emphasis for outlier durations).
- Echo badges (self/mesh/unknown) on trace rows.
- TX-target chips showing the destination channel for TX events.

**Phase 2 — Visual context**
- Mini-timeline sparkline alongside each trace summarising step timing.
- Hop-path diagram visualising the path-hash chain.

**Phase 3 — Analytics panel**
- New `traceAnalyticsPanel` with:
  - **Performance heatmap** of step-type × phase (with No-Data fallback).
  - **Duration histogram** with median + P95 markers.
  - **Group similar** checkbox to collapse near-identical traces.

**Phase 4 — Interactivity**
- Category filter tabs (`traceCategoryTabs`) for filtering by echo kind, status, channel, etc.
- Click-to-highlight: clicking a hash highlights all related rows.
- Real-time pulse animation on freshly arriving traces.
- Export buttons (JSON / CSV) for the current view.

**Phase 5 — Playback**
- `tracePlayModal`: step-by-step playback of a selected trace with:
  - Progress bar + label (current / total ms).
  - Pause / Restart / Speed / Close controls.
  - Fine-grained speed selector (0.1×, 0.25×, 0.5×, 1×, 2×, 5×).
  - Header info pane (hash, category, length).

**Refinements after initial rollout**
- Literal `\uXXXX` escapes replaced with actual emojis in trace UI.
- Echo classification switched from time-based to **path-hash based** (see next section).
- Column widening in trace rows for legibility.
- Heatmap improvements: sorting by count, count overlays, opacity by count, median + P95 markers, phase-based grouping.
- Defensive guards added around heatmap/histogram rendering to keep Trace Overview & Analytics panels visible if a runtime JS error occurs (force `display: block`, `try/catch` around render calls with `console.error` logging).
- `window._traceData` exposure fix so the Play button works (variable was previously trapped inside an IIFE).
- Empty-path packets now correctly classified as `self_echo` (Track C).

### 🎯 Path-Based Echo Classification

`overlay/pymc_core/.../wm1303_backend.py`
- New `set_local_identity(pub_key: bytes, path_hash_size: int = 1)` method on the radio backend.
- New `_classify_echo(payload: bytes) -> str` method returning one of:
  - `self_echo` — own TX heard back via RF self-coupling (last path-hash in payload matches our local hash, or empty path).
  - `mesh_echo` — a neighbour repeater retransmitted a packet we forwarded/originated (our path-hash present elsewhere in the path).
  - `unknown_echo` — content-hash matched a recent TX, but path/source did not confirm origin (degraded fallback).
- New internal counters: `_tx_self_echo_detected`, `_tx_mesh_echo_detected`, `_tx_unknown_echo_detected`.
- Per-classification trace events emitted via `_trace_ev(...)` so the Trace UI can show the echo kind.

`overlay/pymc_repeater/repeater/main.py`
- At repeater startup, the local pubkey and configured `path_hash_size` are passed to the radio backend via `self.radio.set_local_identity(pubkey, path_hash_size)`.
- Wrapped in `try/except` with a graceful warning if the radio backend doesn't expose the method (forward/backward compatibility).

### 🗂 Tiered Metrics Query System

**NEW FILE:** `overlay/pymc_repeater/repeater/web/tiered_query.py` (858 lines)

- Tier layout:
  | Tier  | Age       | Table suffix | Resolution |
  |-------|-----------|--------------|------------|
  | Hot   | 0 – 7 h   | (raw)        | Full       |
  | Warm  | 7 – 24 h  | `_1m`        | 1 minute   |
  | Cool  | 24 h – 3 d| `_10m`       | 10 minutes |
  | Cold  | 3 – 8 d   | `_15m`       | 15 minutes |
- Public helpers:
  - `tiered_packet_activity_query(conn, channel_id, since_ts, until_ts, bucket_seconds)`
  - `tiered_noise_floor_query(...)`
  - (and channel-stats variants)
- Cross-tier merging with overlap protection at tier boundaries.
- Used by API endpoints to make 1h/6h/24h/3d/8d timeframes all return consistent data regardless of which tier the underlying rows live in.

### 🛠 Metrics Retention — Critical Counter Fix

`overlay/pymc_repeater/repeater/metrics_retention.py`

**Bug:** `channel_stats_history` stores **cumulative counters** (monotonically increasing since service start) for `rx_count`, `tx_count`, `tx_failed`, `tx_airtime_ms`, `tx_bytes`, `lbt_blocked`, `lbt_passed`, `pkt_count`. The downsampler used `SUM(col)` per bucket, which multiplied the cumulative value by the number of samples in the bucket — yielding wildly inflated values in summary tables.

**Fix:** Replaced `SUM(col)` with `MAX(col) - MIN(col)` for all cumulative counters, which gives the correct per-bucket delta. With 1 sample per bucket this yields `0` (no observable delta in that minute), which is preferable to a fake number. Higher-tier re-aggregation (`_1m → _10m → _15m`) continues to use `SUM` on aliases starting with `total_`, correctly summing per-minute deltas into 10/15-minute deltas.

`AVG()` is retained for instantaneous gauges (`avg_rssi`, `avg_snr`, `noise_floor_dbm`, `tx_noisefloor_dbm`).

### 📊 API: Tracing, Dedup, Spectrum, Packet Activity

`overlay/pymc_repeater/repeater/web/wm1303_api.py` — ~1071 lines changed.

- **Dedup endpoint enhancements:**
  - Now aggregates `hal_mesh_echo` and `hal_unknown_echo` in addition to `hal_tx_echo`, `filtered`, `multi_demod`.
  - `dedup_ratio` formula widened to include all non-forwarded events.
  - Self Echo (RF) card label clarified (previously "HAL Echo").
- **Packet Activity endpoint:** new `/api/wm1303/packet_activity` using the tiered query system and the `packet_activity` table (delta-correct counts) instead of `channel_stats_history` (cumulative).
- **Internal helpers** factored out for reuse:
  - `_map_lbt_row(r)`
  - `_pkt_counts_for(conn, ch_id)`
  - `_build_sq_channel(rows, total_pkts, pkts_per_bucket)`
  - `_agg_channel_tiered(conn, ch_id)`
- **New endpoints (multi-region — see below):** `/api/wm1303/regions`, `/api/wm1303/region`, `/api/wm1303/presets`.
- **TX power & sync_word handling** prepared for the new UI dropdowns (16 LUT entries, per-channel sync_word presets).

### 🌍 Multi-Region Regulatory Support

**NEW FILE:** `overlay/pymc_core/src/pymc_core/hardware/region_config.py` (244 lines)
- 8 regions + CUSTOM:
  - **EU868** (863–870 MHz, sync 0x1424)
  - **US915** (902–928 MHz)
  - **AU915** (915–928 MHz) — unlocks Issue #1 (BW250 use case)
  - **AS923** (920–925 MHz)
  - **IN865** (865–867 MHz)
  - **JP920** (920–928 MHz)
  - **KR920** (920–925 MHz)
  - **CUSTOM** (user-supplied tx_freq_min / tx_freq_max)
- Helper functions:
  - `get_tx_bounds(region)` — returns `(tx_freq_min, tx_freq_max)`.
  - `get_sx1261_calib(region)` — returns the appropriate SX1261 image-calibration byte pair.
  - `get_region_summary(region)` — UI-friendly metadata dict.
- Sync-word constants: `0x1424` (private) / `0x3444` (public).
- RU864 explicitly **removed** from the list per project requirements.

**`wm1303_backend.py` integration**
- Reads `region` field from `wm1303_ui.json` (string code or object with optional CUSTOM bounds).
- Replaces hardcoded `tx_freq_min: 863000000 / tx_freq_max: 870000000` with region-derived values.
- Logs the resolved region and bounds on startup.

**`sx1261_driver.py` integration**
- Replaces hardcoded image calibration `[0xD7, 0xDB]` (EU868) with region-derived values via `region_config.get_sx1261_calib(...)`.
- Adds `_read_region_from_ui()` helper.
- Falls back to EU868 if `region_config` is unavailable (backwards compatibility).

**API endpoints (`wm1303_api.py`)**
- `GET /api/wm1303/regions` — lists all regions with metadata.
- `GET /api/wm1303/region` — current region + resolved bounds.
- `POST/PUT /api/wm1303/region` — update region (validates code; CUSTOM requires bounds).
- `GET /api/wm1303/presets` — community channel preset catalog.

### 📡 Channel F — Wideband (`chan_Lora_std`)

- Activates the SX1302's dedicated `chan_Lora_std` slot, which runs in **parallel** with the multi-SF chains (Channels A–D) — no interference, no IF-chain locking required.
- Supports **BW125 / BW250 / BW500** (full hardware capability of `chan_Lora_std`).
- Disabled by default for backwards compatibility — existing EU users see no change.
- Available in every region preset (not AU-only).
- Schema added to `config/wm1303_ui.json` template:
  ```json
  "channel_f": {
    "enabled": false,
    "frequency": 869525000,
    "bandwidth": 250000,
    "spreading_factor": 9,
    "sync_word": 5188,
    "tx_power": 22,
    "lbt_enabled": true,
    ...
  }
  ```
- Backend dynamically wires `chan_Lora_std.enable / bandwidth / if` based on the UI config.
- Channels A–D unchanged: stay on `chan_multiSF_0..3` with BW125 multi-SF.

### 🧰 Community Channel Presets

**NEW FILE:** `config/presets.json` (847 lines)

| Preset       | Region | A–D active | Channel E | Channel F |
|--------------|--------|------------|-----------|-----------|
| EU-Default   | EU868  | 2          | ✅ ON     | ⬜ off    |
| US-Default   | US915  | 2          | ⬜ off    | ⬜ off    |
| AU-Default   | AU915  | 2          | ⬜ off    | ✅ ON (BW250) |
| AS-Default   | AS923  | 2          | ⬜ off    | ⬜ off    |
| IN-Default   | IN865  | 2          | ⬜ off    | ⬜ off    |
| JP-Default   | JP920  | 2          | ⬜ off    | ⬜ off    |
| KR-Default   | KR920  | 2          | ⬜ off    | ⬜ off    |
| Custom       | CUSTOM | 0          | ⬜ off    | ⬜ off    |

Every preset defines **all six channels (A–F)** with sensible defaults; users can enable any combination after install via the Channels tab.

### 🔌 Upstream Overlay Refresh

- **`overlay/pymc_core/src/pymc_core/hardware/__init__.py`** — merged with upstream HEAD: keeps `WM1303Backend` and `VirtualLoRaRadio`, adds upstream's `USBLoRaRadio` and `TCPLoRaRadio` (commit `1c8d8f2`).
- **`overlay/pymc_core/src/pymc_core/hardware/signal_utils.py`** — verified identical to upstream HEAD, no overlay action needed.
- **`overlay/pymc_repeater/repeater/config.py`** — refreshed from upstream HEAD (432 → 567 lines):
  - Gained `resolve_storage_dir()`, sensor config defaults, `pymc_tcp` / `pymc_usb` radio type support.
  - Safer `sync_word` parsing with default `0x12` and integer coercion.
  - WM1303 `elif` branch carefully re-inserted on top of refreshed upstream.
- **`install.sh`** — now copies `region_config.py` and `presets.json` to the installed locations during install/upgrade.

### 📜 Config Template Overhaul (committed)

**Commit `808bd32` — `config: overhaul template with upstream sections and clear device-specific values`**

`config/config.yaml.template` was restructured (231 lines changed) so that:
- Upstream-equivalent sections are grouped and clearly labelled.
- Device-specific values (WM1303 paths, radio binding, etc.) are clearly marked so installers / users can spot them at a glance.
- Comments updated to reflect current behaviour.

### 🩹 Installer Fix (committed)

**Commit `6c50c1e` — `fix: create /opt/pymc_repeater before copying spi_optimize.sh in Phase 2.9`**

Prevents an installer failure on fresh systems where the target directory didn't yet exist when `spi_optimize.sh` was copied.

---

## Channel F Backend Equivalence

Channel F was already wired at config-level in earlier drafts, but in v2.4.9 it received **first-class equivalence** with Channels A–D and E across the full stack — bridge engine, TX queue, RX classifier, dashboards, color mapping, friendly-name resolver, and metrics buckets.

### New file
- **`overlay/pymc_repeater/repeater/channel_f_bridge.py`** — Channel F bridge handler analogous to `channel_e_bridge.py`. Routes Channel F packets through the same forwarding/dedup pipeline as the SX1302 multi-SF channels (A–D) via the HAL pkt_fwd path.

### Backend integration (`overlay/pymc_repeater/repeater/bridge_engine.py`)
- `channel_f` added to endpoint sets (RX sources, TX destinations).
- `RF_ENDPOINTS` updated so bridge rules can route to/from Channel F.
- Channel ID handling is channel-agnostic so existing dedup, hop counting, and trace logic apply uniformly.

### Packet router (`overlay/pymc_repeater/repeater/packet_router.py`)
- Verified channel-id-agnostic; no changes required (Channel F flows through existing routing paths).

### TX queue manager
- Dedicated `channel_f` queue with identical scheduling semantics as A–D/E queues (RX-priority preservation, `tx_hold` window, LBT/CAD gating).

### RX classifier (`overlay/pymc_core/.../wm1303_backend.py`)
- New per-packet classifier matches incoming `chan_Lora_std` packets to `channel_f` based on frequency + BW + SF tuple, with comment noting collision fallback behavior.

### API & dashboards (`overlay/pymc_repeater/repeater/web/wm1303_api.py`)
- **`_channels_live_get`** — Channel F card with `is_chan_lora_std: True` flag plus full metric set (rx_count, tx_count, rssi/snr histograms, etc.).
- **Six dashboard endpoints** extended for Channel F:
  - `/api/wm1303/lbt_history`
  - `/api/wm1303/signal_quality`
  - `/api/wm1303/packet_activity`
  - `/api/wm1303/packet_metrics`
  - `/api/wm1303/tx_activity`
  - `/api/wm1303/origin_stats`
- **Color mapping** — `channel_f → #a855f7` (purple/violet) added to all 4 `ch_colors` dicts in API + UI.
- **Friendly-name resolver** — picks up channel_f friendly name from `wm1303_ui.json` via existing UI-load pattern (no code changes needed).
- **Noise floor processing** — channel_f bucket included alongside A–D/E.

### Packet tracing
- `uniform_tracer.py` Hook 1 + `packet_trace.py` channel-id-agnostic; Channel F packets appear in trace UI with correct echo classification and TX-target chips.

### Metrics retention
- `metrics_retention.py` channel-id-agnostic; Channel F gets its own bucket in `channel_stats_history` + tiered rollups automatically.

### UI completion (`overlay/pymc_repeater/repeater/web/html/wm1303.html`)
- TX queue grid: Channel F card (purple badge "SX1302 RF0", full metrics row).
- Radio summary aggregator: Channel F automatically included.
- Trace filter dropdown: Channel F option.
- Charts: `CAD_CH_COLORS` extended for Channel F line color.

---

## Sync Word Architecture Migration

v2.4.9 includes a significant architecture change in how sync_word is configured and exposed.

### Before v2.4.9
- Sync_word was per-channel (one selector per channel A–D, E, F in the UI).
- Each channel card had Private / Public / Custom hex options.
- Stored under each channel's config block in `wm1303_ui.json`.

### After v2.4.9
- **Sync_word is device-wide.** A single selector lives next to the Region selector in the REGION & REGULATORY block.
- Stored as a **top-level** key `sync_word: {value, mode}` in `wm1303_ui.json`.
- Per-channel sync_word fields removed from UI and `wm1303_ui.json` schema.
- Only two modes: **Private (0x1424 → board flag 0x12)** and **Public (0x3444 → board flag 0x34)**. Custom mode removed.
- New API endpoints: `GET/POST /api/wm1303/sync_word`.
- Backend (`wm1303_backend.py`) reads top-level sync_word, derives `lorawan_public` board flag (Public → true, Private → false), passes through to `global_conf.json`.
- Bootstrap wizard prompts for sync_word (Private default, Public option) with `WM1303_SYNC_WORD` env-var override.

### Why this change

Hardware research into HAL v2.10 (`sx1302_hal/libloragw/src/loragw_sx1302.c` lines 1187–1218 and `packet_forwarder/src/lora_pkt_fwd.c`) revealed that the SX1302 chip has **no per-channel sync_word register**. The HAL function `sx1302_lora_syncword()` writes two hardcoded peak-position values to `FRAME_SYNCH0/1` registers:

| Mode | `PEAK1_POS` | `PEAK2_POS` | LoRa byte |
|---|---|---|---|
| Private | 2 | 4 | 0x12 |
| Public | 2 (SF5/6) / 6 (SF7-12) | 4 (SF5/6) / 8 (SF7-12) | 0x34 |

The `lorawan_public` board flag is the only sync_word control on SX1302 — it's hardware-global across all multi-SF channels (A–D) and `chan_Lora_std` (F). The previous per-channel UI was misleading because the hardware could never honor different sync_words across channels.

Custom sync_word values (other than 0x12/0x34) are **not supported** by SX1302 hardware — there is no parameterized peak-position register. Writing arbitrary values would be undefined behavior and break interoperability with the broader MeshCore network (which uses Private 0x12 as standard). Custom mode was removed from UI.

### Legacy config handling

The API defensively normalizes any legacy `mode: "custom"` value found in older `wm1303_ui.json` files to `mode: "private"` (the safe MeshCore default) without warning. POST requests with `mode: "custom"` are rejected with HTTP 400 and a clear error explaining the hardware limitation.

### Channel E/F sync_word config field

The `sync_word` field in `chan_Lora_std` (Channel F) and `lora_rx` (Channel E SX1261) `global_conf.json` blocks is **retained** with a clear code comment marking it as reserved for future HAL extensions. HAL v2.10 currently ignores these fields (board-level flag is authoritative). With Custom mode removed, the per-channel values always match the board flag — no divergence is possible.

---

## Issues Resolved

- **Issue #1 — AU915 BW250 silently rejected:** AU users can now select the AU-Default preset (or set region = AU915 manually) and enable Channel F with BW250 to get a working wideband configuration. The previous hardcoded EU868 TX bounds no longer reject AU frequencies.
- **Issue #4 — Hardcoded EU868 frequency limits:** All region-dependent constants (TX bounds in `wm1303_backend.py`, SX1261 image calibration in `sx1261_driver.py`, and the EU-only `global_conf.json` assumptions) now flow from the central `region_config` module.

---

## Completed Items (all v2.4.9 scope items shipped)

- [x] **UI: REGION & REGULATORY block** in Channels tab (right of RF Center Frequency), with live tx_freq_min/max display.
- [x] **UI: Channel F card** in Channels tab (purple/violet badge, clone of channel_e card pattern).
- [x] **UI: BW dropdowns per channel** — A–D: BW125 locked; E: 62.5 / 125 / 250 / 500; F: 125 / 250 / 500.
- [x] **UI: TX Power dropdown** — all 16 LUT-supported values (12–27 dBm) on every channel.
- [x] **Sync_word UI** — ⚠️ *Scope changed during implementation*: originally planned as per-channel selector (Private/Public/Custom). After hardware research (SX1302 `lorawan_public` is a board-level flag with hardcoded peak positions for 0x12/0x34 only), this was migrated to **device-wide** placement next to the Region selector, with only Private (0x1424) and Public (0x3444) options. See "Sync Word Architecture Migration" section below.
- [x] **Installation wizard** in `bootstrap.sh` — interactive region + preset + sync_word selection, with `WM1303_REGION` / `WM1303_PRESET` / `WM1303_SYNC_WORD` env-var overrides and `--non-interactive` flag.
- [x] **Channel F backend equivalence** — full first-class equivalence with A–D/E across bridge engine, TX queue, RX classifier, dashboard endpoints, color mapping, friendly-name resolver, and metrics buckets. See "Channel F Backend Equivalence" section below.
- [ ] **UI ↔ config parameter completeness audit** — deferred to follow-up release.
- [ ] **Deploy + smoke test on pi01** (192.168.101.52) — performed after this commit lands.

---

## Files Changed (final)

### Modified (working tree → committed in v2.4.9)
| File | Δ Lines | Notes |
|------|--------:|-------|
| `overlay/pymc_repeater/repeater/web/html/wm1303.html` | +1718 | Trace UI overhaul, REGION block, Channel F card, BW dropdowns, TX power 16 LUT, sync_word UI under Region, TX queue grid for Channel F, color mappings |
| `overlay/pymc_repeater/repeater/web/wm1303_api.py` | +1578 | Tracing/dedup/packet_activity, region/preset/sync_word endpoints, tiered query integration, 6 dashboard endpoints extended for Channel F, channel color dicts |
| `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` | +477 | Path-based echo classifier, region integration, Channel F full equivalence (TX queue, RX classifier, `chan_Lora_std` config generation), device-wide sync_word read, `lorawan_public` board flag derive |
| `bootstrap.sh` | +258 | Installation wizard: region + preset + sync_word prompts, env-var overrides (`WM1303_REGION` / `WM1303_PRESET` / `WM1303_SYNC_WORD`), `--non-interactive` flag, jq-based merge into `wm1303_ui.json` |
| `config/config.yaml.template` | +231 | Overhaul (committed `808bd32`) |
| `overlay/pymc_repeater/repeater/config.py` | +141 | Upstream refresh (`resolve_storage_dir`, sensors, `pymc_tcp` / `pymc_usb`, safer sync_word parsing) |
| `config/wm1303_ui.json` | +61 | Top-level `region` and `sync_word`, `channel_f` block, per-channel `sync_word` removed |
| `overlay/pymc_core/src/pymc_core/hardware/sx1261_driver.py` | +58 | Region-aware image calibration |
| `overlay/pymc_repeater/repeater/main.py` | +45 | Register local identity with radio backend (`set_local_identity`) |
| `overlay/pymc_core/src/pymc_core/hardware/__init__.py` | +39 | Merge: WM1303 + Virtual + upstream USB/TCP |
| `overlay/pymc_repeater/repeater/metrics_retention.py` | +38 | Critical SUM → MAX-MIN fix for cumulative counters; channel-id-agnostic (Channel F gets bucket automatically) |
| `overlay/pymc_repeater/repeater/bridge_engine.py` | +16 | `channel_f` added to endpoint sets + `RF_ENDPOINTS` |
| `install.sh` | +11 | Copy `region_config.py` + `presets.json`; mkdir fix for `spi_optimize.sh` (`6c50c1e`) |

### Added (new files)
| File | Lines | Purpose |
|------|------:|---------|
| `overlay/pymc_repeater/repeater/web/tiered_query.py` | 858 | Tiered metrics query system (Hot/Warm/Cool/Cold) |
| `config/presets.json` | 847 | 8-preset community catalog (EU/US/AU/AS/IN/JP/KR/Custom) |
| `overlay/pymc_core/src/pymc_core/hardware/region_config.py` | 244 | 8 regions + CUSTOM, helpers, sync-word constants |
| `overlay/pymc_repeater/repeater/channel_f_bridge.py` | (new) | Channel F bridge handler analogous to `channel_e_bridge.py` |
| `_BACKEND_HANDOVER.md` | (new) | Backend status documentation |

### Total
- **12 files modified** (+3777 / −663 lines)
- **5+ new files** (Channel F bridge, region_config, presets, tiered_query, handover doc + this release notes file)

---

## Upgrade Notes

| User group | Impact | Action |
|------------|--------|--------|
| EU868 users (existing) | None — defaults unchanged | Just upgrade |
| AU915 / US915 / other non-EU users | Can now operate legally with correct TX bounds and SX1261 calibration | Set region via UI/API or pick a regional preset during install |
| AU915 users wanting BW250 | Channel F unlocks wideband operation | Enable Channel F (BW250) after upgrade |
| Operators relying on long-term metrics | 8 days of usable history with no rollup inflation bug | No action; just verify charts on first 24h after upgrade |
| Users on legacy time-based echo detection | Replaced with path-hash classification | No action; classification is automatic at startup |

---

## Architecture Decisions (locked-in for v2.4.9)

1. **Region is device-wide**, not per-channel.
2. **Sync_word is device-wide**, not per-channel. Stored as top-level `sync_word: {value, mode}` in `wm1303_ui.json`. Only Private (0x1424) and Public (0x3444) supported — Custom removed because SX1302 hardware uses hardcoded peak positions (HAL v2.10 `lorawan_public` board-flag).
3. **Channels A–D** stay on `chan_multiSF_0..3` (BW125 multi-SF only — SX1302 hardware constraint).
4. **Channel E** uses the SX1261 companion chip (BW62.5 / 125 / 250 / 500 — full chip capability exposed to UI).
5. **Channel F** uses `chan_Lora_std` (BW125 / 250 / 500), runs in parallel with A–D, available in **every** preset, with first-class equivalence (bridge, TX queue, RX classifier, dashboards, color, friendly-name, metrics).
6. **RU864 is not supported** (explicitly removed from region list).
7. **Echo classification is path-hash based**, not time-based; falls back to `unknown_echo` if local identity is not yet registered.
8. **Metrics rollup uses MAX-MIN for cumulative counters**, AVG for gauges, SUM for already-delta `total_*` aliases at higher tiers.
9. **Tiered query boundaries:** 7h / 24h / 3d / 8d with small overlap to avoid jitter-induced gaps.

---

## Status of this Release

- ✅ Committed to `main`
- ✅ Pushed to GitHub (`HansvanMeer/pyMC_WM1303`)
- ✅ VERSION file bumped: `2.4.8` → `2.4.9`
- ⬜ No GitHub release created (deferred per user request — release notes published as `release_notes/RELEASE_NOTES_v2.4.9.md` in the repo)
- ✅ All Python files pass syntax check
- ✅ All JSON files pass validity check
- ✅ `install.sh` and `bootstrap.sh` pass bash syntax check
- ✅ Backend + UI + wizard complete
- ⬜ Deploy + smoke test on pi01 (192.168.101.52) — scheduled immediately after this commit lands

> Post-release: deploy via `upgrade.sh` on pi01, run validation checklist, evaluate whether to create a GitHub release tag.
