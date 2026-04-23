# Release Notes — v2.2.3

**Release date:** 2026-04-23

## Overview

This release introduces **packet metrics charting** in the Spectrum tab, significantly improves **SX1302 RX stall recovery**, and hardens the watchdog with a full hardware power-cycle on restart. Tracing UI received several usability improvements.

---

## New Features

### Packet Metrics Charts (Spectrum Tab)
Five new real-time charts added to the Spectrum tab, providing per-channel visibility into packet traffic:

| Chart | Description |
|---|---|
| **RX Bytes per Channel** | Received bytes over time (CRC_OK packets only) |
| **TX Bytes per Channel** | Transmitted bytes over time |
| **TX Airtime & Wait per Channel** | Solid lines for airtime, dashed lines for queue wait time |
| **RX Hops per Channel** | Average hop count per minute (MeshCore path_len + 1) |
| **RX CRC Error Ratio** | Fraction of received packets with CRC errors (0.0 = healthy, 1.0 = all errors) |

**Implementation details:**
- New `packet_metrics` database table with per-packet RX/TX recording
- RX metrics include: channel, packet length, hop count, CRC status, RSSI, SNR
- TX metrics include: channel, packet length, airtime, wait time, CRC (always OK)
- CRC error writer filters out spectrum-scan noise using RSSI threshold (≥ -115 dBm)
- CRC error ratio uses Option B logic: ratio = 0 when no valid packets exist (prevents misleading 1.0 baseline)
- Hop count extraction uses MeshCore `path_len & 0x3F` with +1 for direct reception, max 63 hops
- API endpoint: `GET /api/wm1303/packet_metrics?hours=N`

### Tracing Tab Enhancements
- **Dedup check entries** shown in trace timeline
- **Timestamps** displayed for each processing step
- **Per-step duration** with cumulative timing and total row
- **Duration attribution**: time-from-previous logic so delays appear on the correct step
- **WAIT rows** with context-aware labels (CAD retries, RF-chain busy, RF transmission, JIT pickup)
- **Split wait rows**: RF transmission time shown separately from scheduling wait
- **CAD retry count** displayed on wait rows when applicable
- **Accordion behavior**: only one trace row expands at a time
- **Trace gap splitting**: packets grouped within 450s window (configurable GAP_THRESHOLD)
- **Auto-refresh disabled by default**

---

## Stability Improvements

### SX1302 Layered RX Stall Recovery (HAL)
New three-level recovery chain in the HAL when the SX1302 multi-SF correlator stalls:

| Level | Action | Duration | Trigger |
|---|---|---|---|
| **L1** (3×) | Correlator reinit — writes ~6 registers | ~5 ms | 5s of zero RX |
| **L1.5** (1×) | Deep modem reinit — writes ALL ~40+ registers | ~15 ms | L1 exhausted |
| **L2** | Process exit → Python respawns with full hardware reset | ~8 s | L1.5 exhausted |

- `lgw_l2_restart_requested` flag added to HAL header for clean L1→L2 escalation
- pkt_fwd main loop polls the flag and sets `quit_sig` for orderly shutdown
- Recovery levels reset automatically when RX resumes

### Hardware Power-Cycle on Watchdog Restart
- Watchdog restart now executes `power_cycle_lgw.sh` before restarting pkt_fwd
- Full 3-second power-off drain clears all capacitor charge in SX1302/SX1250/SX1261
- Falls back to standard `reset_lgw.sh` if power-cycle script is not found

### Watchdog Tuning
- **AGC reload interval default**: 300s → **30s** (prevents correlator drift before stall)
- **Respawn rate limit**: 10/hour → **30/hour** (more recovery attempts before lockout)
- **Watchdog cycle**: 5-second check interval for faster L2 detection
- AGC reload interval configurable via Advanced Config UI (`hal_advanced.agc_reload_interval_s`)

---

## Bug Fixes

- **RX Bytes chart**: Now counts only CRC_OK packets (previously included CRC errors and spectrum-scan noise)
- **TX Wait time**: Channel E bridge now stores `wait_time_ms` (was `wait_ms`, key mismatch)
- **Hop count**: Added +1 for direct reception (was showing 0 for single-hop), raised sanity cap from 15 to 63
- **CRC error ratio**: Starts at 0 instead of 1.0 when no valid packets exist (Option B)
- **Spectrum-scan noise filter**: CRC errors with RSSI < -115 dBm excluded from metrics
- **Trace gap threshold**: Changed from 30s to 450s to prevent splitting related events
- **Accordion click**: Fixed multiple rows expanding simultaneously

---

## Changed Files

| File | Changes |
|---|---|
| `loragw_hal.h` | L2 restart flag declaration |
| `loragw_hal.c` | L1/L1.5/L2 recovery chain, AGC default 30s |
| `lora_pkt_fwd.c` | L2 escalation polling in main loop |
| `wm1303_backend.py` | Power-cycle on restart, rate limit 30/hr, AGC default 30s, CRC error writer, packet metrics hooks |
| `bridge_engine.py` | RX/TX packet metrics recording, dedup trace events |
| `channel_e_bridge.py` | TX packet metrics recording, wait_time_ms fix |
| `sqlite_handler.py` | `packet_metrics` table schema and creation |
| `metrics_retention.py` | Retention for packet_metrics table |
| `wm1303.html` | 5 new charts, tracing enhancements, accordion fix |
| `packet_trace.py` | GAP_THRESHOLD 450s for trace grouping |
| `wm1303_api.py` | `/api/wm1303/packet_metrics` endpoint, CRC ratio Option B, hop +1 logic |

---

## Upgrade Notes

- **HAL rebuild required**: The L1/L1.5/L2 recovery changes require recompiling the HAL and packet forwarder. The upgrade script handles this automatically.
- **Database migration**: The `packet_metrics` table is created automatically on first startup. No manual migration needed.
- **AGC interval**: Default changed from 300s to 30s. Existing installations with a custom value in the Advanced Config UI will keep their setting.
- **Browser cache**: Hard-refresh (Ctrl+Shift+R) recommended after upgrade to load the new Spectrum charts and Tracing improvements.
