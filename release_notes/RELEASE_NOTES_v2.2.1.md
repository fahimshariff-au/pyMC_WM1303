# Release Notes — v2.2.1

**Release date:** 2026-04-22
**Previous version:** v2.2.0
**Upgrade:** Use the bootstrap one-liner — HAL recompilation and hardware deep-reset are handled automatically

---

## Highlights

- **SX1302 stability fix (root cause resolution)** — The intermittent RX freeze ("snap") that plagued all previous versions has been traced to a custom post-TX AGC reload routine and permanently eliminated. Replaced with a safe periodic 60-second timer-based AGC recalibration.
- **RX spreading factor filter** — Packets received on a channel frequency but with a non-matching spreading factor are now logged but not forwarded through the bridge, preventing wasted TX responses that the receiving node cannot decode.
- **SPI bus stability hardening** — SPI clock lowered from 16 MHz to 4 MHz, VPU core clock locked at ≥500 MHz, SPI polling threshold raised, CPU governor set to performance mode. All applied automatically at install/upgrade and every service start.
- **Deep hardware reset** — New `deep_reset` mode in `reset_lgw.sh` performs a ≥60 s power drain with all resets asserted, ensuring the SX1302/SX1261 start from a fully discharged state.
- **Tracing tab UX refinements** — Per-step duration and cumulative timing, virtual WAIT rows with context labels, accordion behavior, and CAD retry counts.
- **Unified RF TX ordering** — Origin-channel-first priority now applies to all RF endpoints including Channel E (SX1261), not just WM1303 radio channels.
- **Reduced TX hold times** — Spectral scan and noise floor measurement TX holds shortened from 5 s / 4 s to 2 s each, improving TX availability.

---

## 🔥 Critical Fix

### SX1302 RX Freeze — Root Cause Identified and Eliminated

| | Detail |
|---|---|
| **Symptom** | SX1302 multi-SF demodulator stops detecting preambles every 4–30 minutes ("snap"), requiring a full process restart to recover. Register values appear normal but no packets are received. |
| **Root cause** | A custom post-TX AGC reload block in `loragw_hal.c` (added in earlier versions) stopped and restarted the AGC MCU after every transmission. During rapid TX bursts (>4 reloads in <15 s), this churned internal SX1302 state — specifically correlator pipeline accumulators, drift trackers, and AGC fine-tuning registers that are not accessible via SPI and cannot be restored by a simple register re-write. |
| **Evidence** | A controlled A/B test on pi03 proved the fix: Phase A (AGC reload enabled, 4 hours) showed multiple snaps; Phase B (AGC reload disabled, 26+ minutes, 190 TX completions) showed zero snaps, zero dead RX cycles, zero watchdog events. The AGC MCU's autonomous `agc=0x01` status confirmed it handles TX→RX transitions correctly without host intervention. |
| **Fix** | Removed the entire post-TX AGC reload block (57 lines) from `lgw_receive()` in `loragw_hal.c`. Replaced with a safe periodic 60-second timer-based AGC recalibration that is fully decoupled from TX events, preventing burst-reload patterns while maintaining gain calibration. |
| **Removed recovery code** | All symptom-masking recovery mechanisms that were added to work around the snap have been removed: L0 burst detection, L1 correlator reinit, L2 full process restart, L2b semi-dead detection, and the SX1302 register monitoring function. These added complexity without addressing the root cause. |
| **Safety net retained** | Python-side Detection 4 (process-exit respawn) remains as a last-resort safety net for any future unexpected pkt_fwd crashes. |
| **Files** | `overlay/hal/libloragw/src/loragw_hal.c`, `overlay/hal/packet_forwarder/src/lora_pkt_fwd.c` |

---

## 🚀 New Features

### SPI Bus Stability Hardening

| Setting | Value | Why |
|---|---|---|
| **SPI clock speed** | 16 MHz → **4 MHz** | The previous 16 MHz was 8× the Semtech default (2 MHz) and double the chip maximum (8 MHz). Reduced to 4 MHz for reliable communication with margin. |
| **VPU core_freq_min** | default → **500 MHz** | Prevents the VideoCore clock from scaling below 500 MHz. SPI clock is derived from VPU clock via divider; at the default minimum (200 MHz), the SPI clock drifts from 4 MHz to ~1.6 MHz. |
| **SPI polling_limit_us** | 30 µs → **250 µs** | Raises the polling-mode threshold so transfers up to ~111 bytes use CPU polling instead of interrupt mode, eliminating jitter for medium-sized SPI transactions. |
| **CPU governor** | ondemand → **performance** | Locks ARM CPU frequency at maximum to eliminate scheduling jitter from frequency transitions. Applied at every service start. |
| **Implementation** | `config/spi_optimize.sh` (new) runs as `ExecStartPre` in the systemd service unit. All settings are idempotent and safe for single-core Pis. |
| **Files** | `overlay/hal/libloragw/inc/loragw_spi.h`, `config/spi_optimize.sh` (new), `config/spi-stability.conf` (new), `config/pymc-repeater.service`, `install.sh`, `upgrade.sh` |

### Deep Hardware Reset

| | Detail |
|---|---|
| **What** | New `deep_reset` mode in `reset_lgw.sh` that powers down the concentrator with all reset lines asserted and waits ≥60 seconds for capacitors to fully drain before power-up. |
| **Why** | Ensures the SX1302, SX1261, and SX1250 radios start from a completely clean state with no residual charge or firmware remnants. |
| **Usage** | `reset_lgw.sh deep_reset [seconds]` — default 60 s drain time, configurable via second argument. |
| **Integration** | Automatically executed during `install.sh` and `upgrade.sh`. Standard `reset_lgw.sh start` continues to perform the quick reset for normal service starts. |
| **Files** | `config/reset_lgw.sh` |

### Unified RF TX Ordering (Origin-Channel-First)

| | Detail |
|---|---|
| **What** | The origin-channel-first TX priority (introduced in v2.1.1 for radio channels) now also applies to RF endpoints like Channel E (SX1261). |
| **How** | New `RF_ENDPOINTS` class constant in `bridge_engine.py` identifies endpoints that perform over-the-air TX. These are collected into a unified `rf_sends` list alongside WM1303 radio targets and sorted together, ensuring the origin channel always transmits first regardless of whether it's a radio channel or an RF endpoint. |
| **Result** | A packet received on Channel E is now retransmitted on Channel E first, then on Channel A — matching the existing behavior for radio-to-radio forwarding. |
| **Files** | `overlay/pymc_repeater/repeater/bridge_engine.py` |

### Detection 4: Process-Exit Respawn

| | Detail |
|---|---|
| **What** | The Python watchdog now detects when `lora_pkt_fwd` has exited (e.g., due to a crash or signal) and automatically respawns it with a full hardware reset. |
| **Why** | Previously, if pkt_fwd exited unexpectedly, the Python backend continued running but without a radio process. The only recovery was a manual service restart. |
| **Safety** | Rate-limited to 10 respawns per hour to prevent infinite crash loops. Cumulative respawn count tracked for diagnostics. |
| **Files** | `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` |

---

## ⚡ Improvements

### Tracing Tab — Duration and Timing Display

| Aspect | Detail |
|---|---|
| **Per-step duration** | Each trace step now shows how long it took (time until the next step). |
| **Cumulative time** | Running total from first to current step displayed in a dedicated column. |
| **Total row** | Summary row at the bottom shows total packet processing time. |
| **Virtual WAIT rows** | Gaps between steps are shown as explicit WAIT rows with context-aware labels (e.g., "CAD retries", "rf-chain busy", "JIT thread pickup"). |
| **Split rf-chain wait** | The previously opaque "rf-chain busy" wait is now split into "rf transmission" (actual airtime) and "waiting" (scheduling/guard margin). |
| **CAD retry count** | WAIT rows following CAD checks display the number of retries when applicable. |
| **Accordion behavior** | Only one trace row can be expanded at a time; clicking a new row collapses the previous one. |
| **Files** | `overlay/pymc_repeater/repeater/web/html/wm1303.html` |

### Reduced TX Hold Times

| Operation | Before | After | Impact |
|---|---|---|---|
| Spectral scan TX hold | 5.0 s | 2.0 s | −60 % hold time per scan |
| Spectral scan wait | 3.0 s | 1.5 s | Faster scan completion |
| Noise floor TX hold | 4.0 s | 2.0 s | −50 % hold time per measurement |
| **Files** | `overlay/pymc_repeater/repeater/web/wm1303_api.py` |

### C-Level TX Guard Margin

| | Detail |
|---|---|
| **Change** | Post-TX spectral/LBT scan guard increased from airtime + 50 ms to airtime + **150 ms**. |
| **Why** | Gives the PLL, LNA, and filters adequate settling time after TX before spectral/LBT scans resume. |
| **Files** | `overlay/hal/packet_forwarder/src/lora_pkt_fwd.c` |

### Spectral Scan Interval

| | Detail |
|---|---|
| **Change** | Default `pace_s` changed from 1 s to **60 s** in `global_conf.json`. |
| **Why** | A 1 s interval causes excessive SX1261 state transitions. At 60 s, spectral data remains useful for noise floor tracking while minimizing radio contention. |
| **Files** | `config/global_conf.json` |

### Minimum Packet Size Filter

| | Detail |
|---|---|
| **What** | Packets smaller than 5 bytes are now discarded at the backend level before entering the bridge engine. |
| **Why** | The SX1302 occasionally reports 2–4 byte CRC_ERROR fragments that are RF noise, not valid packets. When forwarded through the bridge, these created a self-echo feedback loop that consumed TX capacity. |
| **Files** | `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` |

### Periodic AGC Recalibration (60-Second Timer)

| | Detail |
|---|---|
| **What** | A timer-based AGC reload fires every 60 seconds inside the main `lgw_receive()` polling loop. It disables correlators, reloads the AGC MCU firmware, and re-enables correlators. |
| **Why** | The original post-TX AGC reload was removed because rapid bursts caused SX1302 correlator corruption (the "snap" root cause). Without any recalibration, AGC gain can drift over time due to temperature and environmental changes. The 60-second periodic reload provides a safe middle ground: at most 1 reload per minute, fully decoupled from TX events, with no burst risk. |
| **Impact** | Reloads reduced from 700+/hour (TX-coupled, with bursts of 6+ in 15 s) to exactly 60/hour (fixed interval, never more than 1 per minute). |
| **Files** | `overlay/hal/libloragw/src/loragw_hal.c` |

### RX Spreading Factor Filter

| | Detail |
|---|---|
| **What** | Packets received on a channel's frequency but with a non-matching spreading factor are now logged as `SF-MISMATCH` and **not routed** to the bridge engine. Previously, these were forwarded with a "FREQ-ONLY match" warning. |
| **Why** | When a node transmits on the same frequency as a channel but with a different SF, the SX1302 multi-SF demodulator receives it. Without the filter, the bridge would process the packet and transmit a response on the channel's configured SF — which the node cannot decode, wasting TX airtime. |
| **Behavior** | The RX watchdog timestamp is still updated (the radio IS receiving), and mismatched packets are counted in the new `SF_MISMATCH` hourly stats counter. |
| **Files** | `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` |

### Enhanced Hourly Stats

| | Detail |
|---|---|
| **What** | The `[HOURLY]` log line now includes `SF_MISMATCH` and `NOISE` counters alongside the existing RX, TX, Bridge, and Scan metrics. |
| **Why** | Provides visibility into how many packets are filtered by the SF filter and the minimum-packet-size noise filter, aiding in channel configuration and RF environment diagnostics. |
| **Files** | `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` |

---

## 🛠️ Install & Upgrade Script Changes

Both `install.sh` and `upgrade.sh` now include:

| Step | Description |
|---|---|
| VPU core_freq_min=500 | Added to `/boot/firmware/config.txt` (or `/boot/config.txt`) |
| SPI polling_limit_us=250 | Persistent via `/etc/modprobe.d/spi-bcm2835-opts.conf` + runtime apply |
| spi_optimize.sh deployment | Copied to `/opt/pymc_repeater/spi_optimize.sh` |
| Deep hardware reset | Executed during install/upgrade for clean radio state |
| HAL rebuild | Triggered automatically when overlay checksums differ |

---

## 📦 New Files

| File | Purpose |
|---|---|
| `config/spi_optimize.sh` | Runtime SPI bus optimizations (CPU governor, polling_limit, RT scheduling) |
| `config/spi-stability.conf` | Documentation of all SPI stability settings and their rationale |

---

## 📁 Files Changed (16)

| File | Changes |
|---|---|
| `overlay/hal/libloragw/src/loragw_hal.c` | Removed post-TX AGC reload block (57 lines) |
| `overlay/hal/libloragw/inc/loragw_spi.h` | SPI speed 16 MHz → 4 MHz |
| `overlay/hal/libloragw/inc/loragw_sx1302.h` | Added correlator_disable/reinit function declarations (retained for reference) |
| `overlay/hal/libloragw/src/loragw_sx1302.c` | Added correlator_disable/reinit implementations (retained for reference) |
| `overlay/hal/packet_forwarder/src/lora_pkt_fwd.c` | Removed monitoring + watchdog code; TX guard 50→150 ms |
| `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` | Detection 4 respawn; min packet size filter; watchdog diagnostics |
| `overlay/pymc_core/src/pymc_core/hardware/tx_queue.py` | TX queue TTL adjustment |
| `overlay/pymc_repeater/repeater/bridge_engine.py` | Unified RF TX ordering (RF_ENDPOINTS); refactored _forward_by_rules |
| `overlay/pymc_repeater/repeater/web/html/wm1303.html` | Tracing tab duration/timing/WAIT rows/accordion |
| `overlay/pymc_repeater/repeater/web/wm1303_api.py` | Reduced TX hold times for spectral/noise floor scans |
| `config/global_conf.json` | Spectral scan pace_s 1 → 60 |
| `config/pymc-repeater.service` | Added ExecStartPre for spi_optimize.sh |
| `config/reset_lgw.sh` | Added deep_reset mode with configurable drain time |
| `config/spi_optimize.sh` | New: runtime SPI bus optimizations |
| `config/spi-stability.conf` | New: SPI stability settings documentation |
| `install.sh` | SPI stability steps, deep reset integration |
| `upgrade.sh` | SPI stability steps, deep reset integration |
| `TODO.md` | Added entries #170 (SPI stability) and #171 (unified RF TX ordering) |

---

## ⚠️ Breaking Changes

None. All changes are backwards-compatible.

---

## 🔄 Upgrade Notes

- **HAL recompilation required** — The overlay changes to `loragw_hal.c`, `loragw_spi.h`, `loragw_sx1302.c/h`, and `lora_pkt_fwd.c` trigger an automatic HAL rebuild during upgrade.
- **Reboot may be required** — The VPU `core_freq_min=500` setting in `/boot/firmware/config.txt` takes effect after reboot. The upgrade script will indicate if a reboot is needed.
- **Deep hardware reset** — The upgrade script performs a ≥60 s deep reset automatically. Plan for a brief downtime window.
- **No config migration needed** — No configuration file format changes in this release.
