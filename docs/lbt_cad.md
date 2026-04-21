# LBT and CAD

> Listen Before Talk and Channel Activity Detection in the WM1303 system

## Overview

The WM1303 system implements two channel-sensing mechanisms to reduce collisions before transmitting:

- **CAD (Channel Activity Detection)** — **Mandatory** hardware-level LoRa preamble detection on the SX1261, executed before every TX
- **LBT (Listen Before Talk)** — **Optional** per-channel RSSI-based check that runs after CAD when enabled

Since v2.1.0, CAD is mandatory and always active. LBT is an additional layer that can be independently enabled or disabled per channel. Since v2.1.1, the Python pre-TX software check has been removed — the C-level CAD+LBT is the sole channel assessment mechanism.

## CAD — Channel Activity Detection

### Mandatory Hardware CAD

Every transmission passes through a hardware-level LoRa CAD scan on the **SX1261** radio before the packet is sent via the SX1302. This is implemented in C code (`lora_pkt_fwd.c`) for minimal latency and direct hardware control.

CAD replaces the previous software-based collision avoidance (random TX delays) with a deterministic, hardware-driven approach.

### How It Works

1. **Stop RX** — the concentrator's RX is briefly paused
2. **CAD Scan** — the SX1261 performs a LoRa preamble detection scan on the exact TX frequency, spreading factor, and bandwidth
3. **Result** —
   - **Clear**: TX proceeds immediately (IMMEDIATE mode)
   - **Detected**: retry with fixed delays (50 → 100 → 200 → 300 → 400 ms), up to 5 retries
   - **After 5 retries**: force-send the packet (TX must not be blocked indefinitely)
4. **Resume RX** — RX is restored after TX completes

### SX1261 / SX1302 Interference Resolution

During development, a critical hardware interaction was discovered: configuring the SX1261 for LoRa CAD mode interferes with the SX1302's TX state machine, particularly on narrow-bandwidth channels (BW 62.5 kHz). This was resolved through several techniques:

| Issue | Solution |
|-------|----------|
| Race condition between `spectral_scan_abort()` and `SET_STANDBY` | **Abort + 5 ms delay + Standby** sequence prevents SX1261 state corruption |
| SX1261 state not fully restored after CAD | **GPIO hardware reset with PRAM reload** after each CAD scan |
| PRAM reload taking ~460 ms | **Bulk PRAM write** — single SPI transfer instead of 386 individual writes, reducing to ~42 ms |
| `uint8_t` overflow bug | Fixed firmware upload that truncated 1546-byte transfer to 11 bytes |
| Stale timestamps after CAD | **IMMEDIATE TX mode** instead of TIMESTAMPED, preventing SX1302 TX FSM stuck at `TX_SCHEDULED (0x91)` |
| Stuck TX FSM | **TX abort** (`lgw_abort_tx()`) when `TX_SCHEDULED` state detected before sending |

### CAD Timing Breakdown

The full CAD cycle has been optimized from **~500+ ms** down to **~37–56 ms**:

| Phase | Channel A (SF7 BW125) | Channel E (SF8 BW62.5) |
|-------|----------------------|------------------------|
| Abort (spectral scan) | 4.3 ms | 4.2 ms |
| Setup (frequency, modulation) | 6.5 ms | 6.5 ms |
| CAD scan (preamble detection) | 7.5–14 ms | 18–27 ms |
| Reinit (GPIO reset + PRAM) | 18.1 ms | 18.1 ms |
| **Total** | **~37–43 ms** | **~47–56 ms** |

Channel E takes longer due to its narrower bandwidth (BW 62.5 kHz) requiring more symbols for preamble detection.

### CAD Retry Delays (v2.1.1)

When a CAD scan detects activity, the system retries with fixed delays (changed from exponential backoff in v2.1.1):

| Retry | v2.1.0 (exponential) | v2.1.1 (fixed) |
|-------|---------------------|----------------|
| 1 | 100 ms | 50 ms |
| 2 | 200 ms | 100 ms |
| 3 | 400 ms | 200 ms |
| 4 | 800 ms | 300 ms |
| 5 | 1600 ms | 400 ms |
| **Worst-case total** | **3100 ms** | **1050 ms** |

This is a **66% reduction** in worst-case TX delay while maintaining 5 retry attempts for collision avoidance. After 5 retries, the packet is force-sent regardless.


### CAD Timing Optimizations Applied

| Optimization | Before | After | Savings |
|-------------|--------|-------|---------|
| Bulk PRAM write | 460 ms | 42 ms | 418 ms |
| Abort delay reduction | 5 ms | 2 ms | 3 ms |
| Skip full calibrate in reinit | 10 ms | 0 ms | 10 ms |
| Calibrate wait reduction | 10 ms | 4 ms | 6 ms |
| Skip `sx1261_calibrate()` | 7 ms | 0 ms | 7 ms |
| TCXO wait reduction | 5 ms | 2 ms | 3 ms |
| Image calibrate wait reduction | 5 ms | 2 ms | 3 ms |
| **Total overhead reduction** | **~500+ ms** | **~37–56 ms** | **~90% faster** |

### CAD Event Tracking

CAD events are recorded per channel with two outcomes:

- **Clear** — no LoRa preamble detected, TX proceeds
- **Detected** — LoRa activity found, TX was force-sent after all retries were exhausted

Events are stored in `repeater.db` (`cad_events` table) and displayed in the Spectrum tab's **CAD Activity** chart. The chart shows Clear (green) and Detected (red) counts per channel.

> **Note:** "Detected" in the chart means the CAD scan found activity on all 5 retry attempts, and the packet was ultimately force-sent. This is expected to be rare in normal operation.

## LBT — Listen Before Talk

### Custom Per-Channel RSSI Check

LBT provides an additional RSSI-based channel assessment that runs **after** the mandatory CAD scan. When enabled for a channel, it measures the actual signal strength in continuous RX mode and compares it against a configurable threshold.

> ⚠️ **LBT is work-in-progress.** It is currently recommended to keep LBT **disabled** until further testing validates its effectiveness in production environments.

### How It Works

1. After a successful CAD scan (or after CAD retries), LBT is checked if enabled for the TX channel
2. The SX1261 switches to continuous RX mode on the TX frequency
3. A real RSSI measurement is taken after a settle time
4. The measured RSSI is compared to the per-channel LBT threshold
5. If RSSI > threshold → channel is busy → TX is delayed
6. If RSSI ≤ threshold → channel is clear → TX proceeds

### Configuration (per channel)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `lbt_enabled` | Enable/disable LBT for this channel | `false` |
| `lbt_threshold` | RSSI threshold in dBm | `-80` |

Both parameters are configurable per channel via the **Channels** tab in the WM1303 Manager UI.

### Timing Impact

LBT adds approximately **47 ms** when enabled. When disabled, it is completely skipped with zero overhead:

| Scenario | Channel A (SF7 BW125) | Channel E (SF8 BW62.5) |
|----------|----------------------|------------------------|
| CAD only (LBT off) | ~37–43 ms | ~47–56 ms |
| CAD + LBT (LBT on) | ~84–90 ms | ~95–104 ms |

### LBT Event Tracking

LBT events are recorded per channel with frequency and RSSI values, stored in `repeater.db` and displayed in the Spectrum tab's **LBT History** chart.

## TX Delay Elimination

With mandatory CAD handling collision avoidance, **all random TX delays have been set to zero** in v2.1.0:

| Parameter | Before | After |
|-----------|--------|-------|
| `tx_delay_factor` | 1.0 | **0.0** |
| `direct_tx_delay_factor` | 0.5 | **0.0** |
| Per-rule `tx_delay_ms` | variable | **0 ms** |
| Python airtime guard | duplicated check | **removed** |

## TX Hold Behavior

| Hold Type | Status | Duration | Purpose |
|-----------|--------|----------|---------|
| **CAD scan** | ✅ Mandatory | 37–56 ms | Hardware preamble detection before every TX |
| **CAD retry backoff** | ✅ Active (on detection) | 50–400 ms (fixed) | Wait for channel to clear (worst-case 1050 ms total) |
| **LBT check** | ⚙️ Optional (per channel) | ~47 ms when enabled | RSSI-based channel assessment |
| **Python pre-TX check** | ❌ Removed (v2.1.1) | — | Was: software LBT/CAD check before PULL_RESP (redundant with C-level CAD) |
| TX batch window | ✅ Active | 2 seconds | Group concurrent bridge sends |
| Queue depth hold | ✅ Active | 100 ms (1 pkt) to 2 s (batch) | Brief dedup window |
| Noise floor hold | ❌ Removed | — | Was: pause TX for noise measurement |

### Design Principles

The TX pipeline follows the project's core design principles:

- **RX availability is the #1 priority** — CAD + TX duration is minimized to restore RX as quickly as possible
- **TX must be sent ASAP** — zero random delays, CAD overhead is deterministic and minimal
- **TX duration must be as short as possible** — IMMEDIATE TX mode, optimized CAD cycle

## SPI Considerations

- The SX1261 operates on a **separate SPI bus** (`/dev/spidev0.1`) from the SX1302 concentrator
- SPI clock runs at optimized speed for minimal transfer overhead
- Bulk PRAM write uses a single SPI transaction for the entire 1546-byte firmware image
- The separate SPI paths mean CAD/LBT operations on the SX1261 do not block SX1302 RX data transfer

## UI Behavior

### CAD Display

CAD is always active and has no user toggle. The **Spectrum** tab shows:

- **CAD Activity chart** — per-channel Clear (green) and Detected (red) counts
- Explanatory text below the chart describes what Clear and Detected mean

### LBT Controls

Available on all channels (A–E) in the **Channels** tab:

- Toggle to enable/disable LBT per channel
- RSSI threshold slider (when enabled)
- Changes apply within 5 seconds (cache TTL auto-reload)

### Charts

| Chart | Data Source | Database | Shows |
|-------|------------|----------|-------|
| CAD Activity | `_packet_activity_recorder` (Python stats) | `repeater.db` → `cad_events` | Per-channel Clear / Detected counts |
| LBT History | `_packet_activity_recorder` (Python stats) | `repeater.db` | Per-channel LBT events with frequency and RSSI |
| Noise Floor | `_packet_activity_recorder` | `repeater.db` → `noise_floor` | Per-channel noise floor values over time |

Channel E is shown in **orange** in all charts.

> **Data Architecture Note:** CAD and LBT chart data is sourced exclusively from Python-level statistics in `repeater.db`. The `spectrum_collector.py` log parsers for CAD/LBT have been removed. Spectral scan data remains in `spectrum_history.db`.

## Noise Floor Interaction

Noise floor values provide context for LBT threshold decisions:

- Per-channel noise floor tracking shows the baseline signal level
- LBT threshold should be set above the noise floor to avoid false busy detections
- Noise floor is measured by the NoiseFloorMonitor without pausing TX (uses TX-free window detection with retry logic)

### Noise Floor Sources (Fallback Chain)

1. **Spectral scan data** — Primary, from SX1261 continuous scan
2. **SX1261 RSSI point measurement** — Secondary
3. **RX packet-based estimation** — Last resort

All values are persisted to `repeater.db` and exposed through API and WebSocket.

## Metrics Retention

| Database | Retention | Relevant Tables |
|----------|-----------|----------------|
| `repeater.db` | 8 days | `cad_events`, `noise_floor`, `noise_floor_history`, `packet_activity` |
| `spectrum_history.db` | 7 days | `spectrum_scans` |

## Troubleshooting

### CAD always showing "Detected"
- This may indicate persistent LoRa activity on the channel
- Check the Noise Floor chart for elevated signal levels
- Verify there are no nearby transmitters on the same frequency
- After 5 retries, packets are force-sent regardless — check if this is causing issues

### LBT blocking all TX
- Check noise floor values — if stuck at `-120 dBm`, scan data may not be updating
- Verify SX1261 is operational (check system logs for SPI errors)
- LBT threshold may be set too low — raise it above the noise floor
- Consider disabling LBT (it is still work-in-progress)

### High CAD retry rate
- Channel may be genuinely busy with LoRa traffic
- Check if other devices are transmitting on the same frequency/SF/BW
- Monitor the CAD Activity chart for patterns

### TX latency seems high
- Verify LBT is disabled if not needed (saves ~47 ms per TX)
- Check CAD retry counts — frequent retries add exponential backoff delays
- Review the packet forwarder logs for timing details

## Related Documents

- [`tx_queue.md`](./tx_queue.md) — TX queue system
- [`radio.md`](./radio.md) — Radio architecture and RF chains
- [`channel_e_sx1261.md`](./channel_e_sx1261.md) — Channel E / SX1261 specifics
- [`configuration.md`](./configuration.md) — Configuration files
- [`ui.md`](./ui.md) — WM1303 Manager UI
- [`architecture.md`](./architecture.md) — System architecture
