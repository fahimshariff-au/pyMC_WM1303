# Release Notes — v2.2.2

**Release date:** 2025-04-23

## Summary

This release focuses on **SX1302 RX stability**, **RF-chain timing precision**, and
**radio resilience**. A two-layer automatic recovery system detects and repairs
correlator stalls without manual intervention. The AGC reload interval is now
configurable from the UI, and several filters reduce unnecessary radio load.

---

## New Features

### Layered SX1302 Recovery System

The SX1302 multi-SF correlators can occasionally lose lock on individual
spreading factors ("snap" events). A two-layer recovery system now handles
this automatically:

| Layer | Trigger | Action | Downtime |
|-------|---------|--------|----------|
| **L1 — Correlator reinit** | 5 s with zero SX1302 RX | Disable correlators → AGC reload → correlator reinit | ~2–8 ms |
| **L2 — Process restart** | 3 consecutive post-TX ACK timeouts | Python restarts pkt_fwd with full GPIO hardware reset | ~3–5 s |

- Layer 1 runs in the C HAL (`loragw_hal.c`, inside `lgw_receive()`) and
  recovers most stalls within milliseconds.
- Layer 2 runs in the Python backend (`wm1303_backend.py`) and acts as a
  safety net when Layer 1 cannot recover the hardware.
- Layer 1 attempts up to 3 consecutive reinits before yielding to Layer 2.

### Configurable AGC Reload Interval

- The periodic AGC reload + correlator reinit interval is now configurable
  via **Advanced Config → HAL Advanced → AGC Reload Interval (s)**.
- Default changed from 60 s to **300 s** after analysis showed no
  time-dependent CRC error degradation.
- Range: 0 (disabled) to 3600 s.
- The setting flows through: UI → `wm1303_ui.json` → `global_conf.json` →
  `lora_pkt_fwd.c` → `loragw_hal.c`.

### ACK-Based Precise RF-Chain Guard

- The TX queue now uses the post-TX ACK from the C code to determine
  exactly when the RF transmission starts.
- Guard timing is calculated as **actual airtime + 100 ms** (was: estimated
  airtime + 150 ms starting from UDP send).
- Falls back to a conservative guard when no ACK is received.
- Reduces inter-packet delay and improves TX throughput.

---

## Improvements

### SX1261 Spectral Scan Recovery

- Added full standby-to-RX recovery for spectral scan timeout, SPI read
  errors, and unexpected status responses.
- The SX1261 is forced into STDBY_RC, allowed 2 ms to settle, then
  restarted in RX mode, preventing stuck states that previously required
  a full service restart.

### SF Mismatch Filter

- Packets received on a channel whose spreading factor does not match the
  channel's configured SF are now logged and dropped at the backend level.
- Prevents mismatched packets from entering the bridge and generating
  spurious TX activity.
- Hourly statistics now include `SF_MISMATCH` and `NOISE` counters.

### Minimum Packet Size Filter

- Packets smaller than 5 bytes are discarded as noise, preventing
  self-echo feedback loops from tiny CRC_ERROR fragments.

### Trace Gap Splitting

- The packet tracing engine now creates a new trace entry when a gap
  of more than 30 seconds occurs between events for the same packet hash.
- Prevents misleading multi-minute total durations caused by
  mesh-delayed duplicate arrivals.

### TX Queue TTL

- Default TX queue TTL increased from 30 s to **60 s**, allowing more
  time for CAD retries and RF-chain availability on busy gateways.

### Spectral Scan Interval

- Default spectral scan pace changed from 60 s to **300 s**, reducing
  SPI bus load and minimizing interference with RX/TX operations.

---

## Files Changed

| File | Changes |
|------|---------|
| `overlay/hal/libloragw/src/loragw_hal.c` | Configurable AGC interval, Layer 1 stall detection |
| `overlay/hal/packet_forwarder/src/lora_pkt_fwd.c` | AGC interval parsing, SX1261 scan recovery, TX pickup guard |
| `overlay/pymc_core/src/pymc_core/hardware/tx_queue.py` | ACK-based precise guard, TTL increase |
| `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` | Layer 2 ACK detection, SF filter, noise filter, AGC config |
| `overlay/pymc_repeater/repeater/web/html/wm1303.html` | AGC Reload Interval UI field |
| `overlay/pymc_repeater/repeater/web/wm1303_api.py` | AGC reload interval in adv_config API |
| `overlay/pymc_repeater/repeater/web/packet_trace.py` | Gap-based trace splitting |
| `config/global_conf.json` | Spectral scan pace_s: 60 → 300 |
| `config/wm1303_ui.json` | Added `adv_config.hal_advanced.agc_reload_interval_s` default |

---

## Upgrade Notes

- **HAL rebuild required** — the C-level changes require recompilation.
  The upgrade script handles this automatically.
- The new `agc_reload_interval_s` key is automatically added to
  `wm1303_ui.json` during upgrade (smart-merge).
- Existing `global_conf.json` files are regenerated on service restart;
  the new AGC interval and spectral scan pace take effect immediately.
- No database schema changes.
- No breaking API changes.
