# Release Notes — v2.1.1

**Release Date:** 2026-04-20  
**Previous Version:** v2.1.0  
**Upgrade:** Use the bootstrap one-liner — HAL recompilation is handled automatically

---

## Highlights

This patch release focuses on **TX pipeline optimization** and **UI improvements**. The Python pre-TX software check has been removed entirely — the C-level CAD+LBT in `lora_pkt_fwd.c` is now the sole channel assessment mechanism. CAD retry delays have been reduced from 3100 ms to 1050 ms worst-case. A new **origin-channel-first TX priority** ensures that repeated packets are transmitted back to the originating channel before other channels.

---

## 🚀 Origin-Channel-First TX Priority

When the repeater receives a packet on a channel and forwards it to multiple channels, the **originating channel now gets TX priority**. This reduces latency for the node that originally sent the packet.

### How It Works

1. Packet received on `channel_e` → forwarded to repeater
2. Repeater processes and injects back with `origin_channel=channel_e`
3. Bridge engine reorders `radio_sends` — `channel_e` is enqueued **first**
4. Other channels follow in their normal order

### Implementation

| File | Change |
|---|---|
| `bridge_engine.py` | `inject_packet()` accepts optional `origin_channel` parameter; `_forward_by_rules()` reorders `radio_sends` so origin channel is first |
| `main.py` | `_bridge_repeater_handler()` accepts and forwards `origin_channel` through the pipeline |

The `origin_channel` is passed purely as function parameters (stack-local), making it fully safe for concurrent packet processing.

---

## ⚡ CAD Retry Delay Optimization

The hardware CAD retry delays in `lora_pkt_fwd.c` have been changed from exponential backoff to fixed values, significantly reducing worst-case TX latency.

| Retry | Old (exponential) | New (fixed) |
|---|---|---|
| 0 | — (direct) | — (direct) |
| 1 | 100 ms | 50 ms |
| 2 | 200 ms | 100 ms |
| 3 | 400 ms | 200 ms |
| 4 | 800 ms | 300 ms |
| 5 | 1600 ms | 400 ms |
| **Worst-case total** | **3100 ms** | **1050 ms** |

This is a **66% reduction** in worst-case TX delay while maintaining 5 retry attempts for collision avoidance.

---

## 🗑️ Python Pre-TX Check Removed

The legacy Python software-based pre-TX check (Laag 1) has been removed. This check used cached spectral scan and noise floor data to assess channel availability before sending `PULL_RESP` to `lora_pkt_fwd`. With the C-level hardware CAD+LBT now fully operational, the software check was redundant.

### Impact

| Aspect | Before (v2.1.0) | After (v2.1.1) |
|---|---|---|
| Pre-TX checks | 2 layers (Python + C) | 1 layer (C only) |
| Python retry delays | [0, 0.5s, 1.0s, 1.5s] + 2.0s force | None |
| Worst-case total delay | ~8.1s (Python 5.0s + C 3.1s) | **~1.05s** (C only) |
| Check method | Software (cached data) + Hardware (SX1261) | Hardware (SX1261) only |

Change: `GlobalTXScheduler` is now instantiated with `lbt_check=None` in `wm1303_backend.py`.

---

## 📊 Origin Channel Metrics & Chart

New per-channel metrics tracking how many packets each channel sources for the repeater, stored in SQLite with 8-day retention.

### Components

| Component | Description |
|---|---|
| Bridge Engine | In-memory counters per channel with thread-safe locking |
| SQLite | `origin_channel_stats` table (timestamp, channel_id, count) |
| Periodic flush | Every 60 seconds, counters flushed to SQLite (10-minute buckets) |
| API | `GET /api/wm1303/origin_stats?hours=N` — per-channel timeseries |
| Retention | Automatic cleanup of data older than 8 days |

### Chart Merge

The Origin Channel Activity chart has been merged into the **TX Activity per Channel** chart, renamed to **Channel Activity**. Both TX and RX Origin data share the same timeline (X-axis).

- TX bars: light colors, solid border, stack `tx_<channel>`
- RX Origin bars: dark semi-transparent (70%), dashed border, stack `rx_<channel>`
- Counter shows: `XX TX | XX RX Origin`

---

## 🔧 Bug Fixes & Improvements

### SF? Display Bug Fixed

The channel configuration card showed "SF?" for channels where the JSON stored `sf` instead of `spreading_factor`. A normalizer function `normCh()` was added to the UI that converts legacy field names (`sf`, `bw`, `cr`) to standard names on every data load.

### RRDtool Fix

The `rrdtool` Python module was not available inside the pymc-repeater virtual environment due to Python 3.13 C-extension incompatibility. Fixed by symlinking the system `rrdtool.so` into the venv `site-packages`. Both `install.sh` and `upgrade.sh` now include this step.

### Signal History Default

The Signal History (📈) time range selector now defaults to **1h** instead of 24h for a more responsive initial view.

---

## 📁 Files Changed

| File | Changes |
|---|---|
| `overlay/pymc_repeater/repeater/bridge_engine.py` | Origin channel tracking in `inject_packet()` and `_forward_by_rules()`, origin counters, SQLite flush |
| `overlay/pymc_repeater/repeater/main.py` | `_bridge_repeater_handler()` forwards `origin_channel` |
| `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` | `lbt_check=None` — Python pre-TX check disabled |
| `overlay/hal/packet_forwarder/src/lora_pkt_fwd.c` | CAD retry delays changed to fixed array [50, 100, 200, 300, 400] ms |
| `overlay/pymc_repeater/repeater/web/html/wm1303.html` | SF normalizer, origin chart merged into Channel Activity, Signal History default 1h |
| `overlay/pymc_repeater/repeater/web/wm1303_api.py` | `/api/wm1303/origin_stats` endpoint |
| `install.sh` | rrdtool symlink step added |
| `upgrade.sh` | rrdtool packages + symlink step added |

---

## Upgrade Instructions

Use the standard bootstrap one-liner. HAL recompilation is required for the CAD delay changes and is handled automatically by the upgrade script.
