# CLAUDE.md — Working Conventions for Meshcore / pyMC_WM1303 Project

This file is read automatically at the start of each Cowork session. It captures standing rules so Claude does not need to be reminded of them each session.

---

## Pi Hardware

| Unit  | IP                | Hardware       | Role                  |
|-------|-------------------|----------------|-----------------------|
| mesh2 | 192.168.143.146   | SenseCAP M1    | Primary test unit (active dev) |
| mesh1 | 192.168.143.148   | SenseCAP M1    | Secondary test unit   |

- **Device**: SenseCAP M1 running pyMC_Repeater v1.0.8.dev241 (editable install)
- **Live service path**: `/opt/pymc_repeater/repos/pyMC_Repeater/`
- **Safe git working clone**: `~/pyMC_WM1303_work/` — use this for ALL git operations, never the live path
- **Service name**: `pymc-repeater` (managed by systemd)
- **Default SSH**: `pi@192.168.143.146` (mesh2) — use IP, not hostname

---

## Command Formatting Rules (Standing)

**SSH commands** — format for pasting directly into an SSH terminal session on the Pi. Use `\` line-continuation for multi-line commands so the whole block can be pasted at once. Do not wrap in `ssh pi@...` unless the command is meant to be run from Windows.

Example (correct — paste into SSH terminal):
```bash
sudo journalctl -u pymc-repeater -f --no-pager \
  | grep -v 'WATCHDOG' \
  | tee /tmp/out.log &
```

**SCP commands** — format for pasting into a **Windows PowerShell** window (not SSH, not cmd). Use the full Windows path with quotes. Always transfer FROM the Pi TO the workspace folder.

Example (correct — paste into Windows PowerShell):
```powershell
scp pi@192.168.143.146:/tmp/repeater_log.txt "C:\Users\fahim\OneDrive\Documents\Claude\Projects\Meshcore using Sensecap M1\repeater_log.txt"
```

---

## Log / File Workflow (Standard Approach)

**Always prefer SCP'd files over interactive bash log tailing.** This reduces round-trips and saves session context.

### Standard pattern for log investigation:
```bash
# On Pi — capture log to file
sudo journalctl -u pymc-repeater --since "10 minutes ago" > /tmp/repeater_log.txt

# SCP to Windows working folder (use IP, not hostname)
scp pi@192.168.143.146:/tmp/repeater_log.txt "C:\Users\fahim\OneDrive\Documents\Claude\Projects\Meshcore using Sensecap M1\"
```

Then share the file with Claude in the Cowork session (drag-and-drop or reference the path).

### For config files:
```bash
scp pi@192.168.143.146:/etc/pymc_repeater/config.yaml "C:\Users\fahim\OneDrive\Documents\Claude\Projects\Meshcore using Sensecap M1\"
scp pi@192.168.143.146:/opt/pymc_repeater/repos/pyMC_Repeater/repeater/main.py "C:\Users\fahim\OneDrive\Documents\Claude\Projects\Meshcore using Sensecap M1\"
```

### For mesh1 (192.168.143.148):
```bash
scp pi@192.168.143.148:/tmp/repeater_log.txt "C:\Users\fahim\OneDrive\Documents\Claude\Projects\Meshcore using Sensecap M1\mesh1_repeater_log.txt"
```

---

## Git — Always Use Token-Based Authentication

**Never use password-based git auth.** GitHub no longer supports passwords for git operations.

### Remote setup (Pi live repo):
```bash
# Check current remotes
git -C /opt/pymc_repeater/repos/pyMC_Repeater remote -v

# Set origin to fork with token embedded
git remote set-url origin https://TOKEN@github.com/fahimshariff-au/pyMC_WM1303.git

# Add upstream for HansvanMeer original
git remote add upstream https://github.com/HansvanMeer/pyMC_WM1303.git
```

### Safe working clone (~/pyMC_WM1303_work):
```bash
git -C ~/pyMC_WM1303_work remote set-url origin https://TOKEN@github.com/fahimshariff-au/pyMC_WM1303.git
```

### Token management:
- Generate tokens at: https://github.com/settings/tokens
- Scope needed: `repo` (full repository access)
- **Never paste the token into chat** — set it directly in the remote URL on the Pi
- Token format: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

## Fork / Repository Info

- **Fork**: `fahimshariff-au/pyMC_WM1303` — this is the source of truth for Fahim's changes
- **Upstream**: `HansvanMeer/pyMC_WM1303` (original, do not push to this)
- **Fork uses overlay structure**: `overlay/pymc_repeater/repeater/` (not `repeater/` directly)
- **CRITICAL**: Never switch branches in `/opt/pymc_repeater/repos/pyMC_Repeater/` — it will break the live service. Always use `~/pyMC_WM1303_work` for branch work.

### Committing fixes via safe working clone:
```bash
cd ~/pyMC_WM1303_work
# Copy modified file from live path
cp /opt/pymc_repeater/repos/pyMC_Repeater/repeater/main.py overlay/pymc_repeater/repeater/main.py
git add overlay/pymc_repeater/repeater/main.py
git commit -m "fix: describe what was fixed"
git push origin main
```

---

## Key Technical Facts

### pymc_core Packet class
- `Packet.rssi` and `Packet.snr` are **read-only properties** — assigning them raises `AttributeError`
- Only `pkt._rssi` and `pkt._snr` (underscore-prefixed plain instance attributes) are writable

### Echo filter (bridge_engine.py)
- WM1303 uses a **hash-based TTL filter** (`_tx_echo_ttl = 10.0s`) — NOT RSSI-based
- Old RSSI-based −50 dBm filter from original pyMC_Repeater is NOT present in WM1303
- Drops show as `drop_reason="tx_echo"` in WM1303 UI — correct
- No action needed on echo filter

**History (do not re-investigate):** Earlier sessions saw packet drops from b6/75 in the pyMC dashboard. A previous model (Opus) incorrectly attributed this to a −50 dBm RSSI echo filter and advised lowering b6/75 TX power. That filter exists in the *original* pyMC_Repeater but is NOT present in WM1303. TX power was subsequently raised back to 22 dBm and drops are no longer observed. Real cause of the earlier drops was most likely **Bug 2 (companion RF RX deaf)** fixed in commit `2555cc0`, and/or other bridge_engine fixes made during the same period. The echo filter and TX power of b6/75 at 22 dBm are both correct — do not re-open this.

### Bug 2 (companion RF RX deaf) — FIXED
- Fix: `router.enqueue(pkt)` with `pkt._injected_for_tx = True` before `process_packet()` in `_bridge_repeater_handler`
- Script: `fix-bug2-companion-rf.sh` in workspace folder
- Committed to fork as `2555cc0`

### Repeater forwarding rule naming
- Rule named `channel_e_to_rep` matches `channel_a` traffic — cosmetic mismatch, harmless
- Worth tidying in Bridge Rules UI when convenient

---

## Current Network Topology (E4 / mesh2)

### Devices

| Node | Hardware | Type | Connection | Location / Role |
|------|----------|------|------------|-----------------|
| **e4** | SenseCAP M1 (mesh2, 192.168.143.146) | pyMC repeater | SSH via IP | South-facing window; primary repeater running pyMC_WM1303 |
| **c6** | Virtual TCP companion | Companion (virtual) | MeshCore app → TCP | Hosted on e4; MeshCore app (desktop/phone) connects to it via TCP. Not a physical device. Replaced old 6e companion. |
| **75** | LilyGo T-Echo | MeshCore.io repeater firmware | MeshCore app → BLE (via c6 or b6 login) | East-facing window; faces e8 (~4.5km) and sometimes 4E (~1.8km) and DA (~1.4km). No web UI — managed via MeshCore app login through c6 or b6. |
| **b6** | LilyGo T-Echo | MeshCore companion firmware | MeshCore app → BLE | Currently north-facing window; hits DA and E8 better from that position. Varies in location. |
| **e8** | Remote node | Repeater | RF only | ~4.5km east, marginal LOS |
| **4e** | Remote node | Repeater | RF only | ~1.8km south, marginal LOS |
| **DA** | Remote node | Repeater | RF only | ~1.4km east, sometimes reachable |

### RF Window Placement
- **e4** — south-facing window → primary path toward **4E** (~1.8km), sometimes reaches **E8**
- **75** — east-facing window → primary path toward **E8** (~4.5km), sometimes **4E** and **DA**
- **b6** — north-facing window (current) → hits **DA** and **E8** better; location varies
- Ideal: roof antenna to hit DA, E8, and 4E simultaneously from one point

### TX Power Notes
- WM1303 hardware steps: **20 dBm** and **27 dBm** — intermediate values are not true hardware steps
- pyMC UI accepts any numeric value but the SX1302 only honours supported levels
- E4 has a 6 dBi AU915 indoor antenna (replaced stock M1 antenna) — higher gain means effective EIRP is already elevated vs stock
- E4 current setting: 20 dBm. Pushing to 22–24 dBm via pyMC UI is worth testing to see if it makes a measurable difference at marginal range, but the hardware may just round to the nearest supported step
- **75 and b6**: both set to 22 dBm in MeshCore firmware; using stock T-Echo antennas
- **Do not exceed 30 dBm EIRP** (AU915 regulatory limit)

### Ping Behaviour
- **MeshCore app ping**: only available for Repeaters (discovered or manually added in the app)
- **e4 pyMC web UI → Neighbours → ping**: ✓ WORKING (fixed `71d3aa8`)
- **c6→e4 self-ping**: ✓ works — uses local-hash shortcut in `frame_server._cmd_send_trace_path`, bypasses `trace_helper` entirely
- **c6→75 ping**: ✓ WORKING (fixed `71d3aa8`)
- **b6→75 ping**: ✓ works — both running native MeshCore firmware, b6 and 75 at close range
- **b6→e4 ping**: not yet tested post-fix — may now work given the same three bugs affected all TRACE paths

**RF / noise floor status (as of May 2026):**
- New antenna fitted to E4 — noise floor now −106 dBm (was −65 to −75 dBm with old antenna, effectively deaf)
- LBT threshold updated from −55 dBm to −80 dBm to match new clean noise floor
- Noise spikes to ~−90 dBm (likely LoRaWAN IoT / Optus bleed) — still below LBT threshold, TX not suppressed

**Asymmetric link notes:**
- E4 TX reaches e8 (packets forwarded via e8 observed) but return path via e8 is zero — classic asymmetric link at marginal range
- With 75 active and b6 at a better window, full two-way path via e8/DA works. Without 75, return path fails.
- Local devices (within range) see each other fine — asymmetry is specific to the 4km+ e8/4e paths

---

## Open / Pending Issues

- **wm1303_backend.py manual patch — will not survive pymc_core upgrade**: The TRACE echo hash fix (skip storing hash for type 0x09) was applied directly to `/opt/pymc_repeater/venv/lib/python3.13/site-packages/pymc_core/hardware/wm1303_backend.py`. This file is part of the pymc_core pip package and is NOT tracked in the fork. If pymc_core is upgraded, the patch will be overwritten and pings will break again. Options: (a) pin pymc_core version and re-apply patch after any upgrade, (b) submit fix upstream to HansvanMeer/pyMC_WM1303 or pymc_core. See FORK_NOTES.md `71d3aa8` for full patch details.

- **b6→e4 ping — not yet re-tested post-fix**: The same three bugs (`71d3aa8`) that blocked c6→75 also affected all TRACE paths. b6→e4 may now work. Test when b6 is available.

- **Noise floor spikes to −47 dBm despite AU915 antenna** — E4 fitted with an AU915-focused indoor antenna (~6 dBi) but large spikes still occurring, reaching −47 dBm (55+ dB above baseline of −105 dBm). Spikes occur in irregular clusters (4–5 rapid spikes together, then quiet for 30+ minutes). Possible causes to investigate:
  - **SX1261 ↔ SX1302 RF switch transients** during CAD/LBT cycles — clustered spike pattern is consistent with RF switch timing glitches
  - **SX1302 front-end blocking** from a strong nearby transmitter (in-band or adjacent) overwhelming the LNA despite the filter
  - **SX1302 AGC recovery artifact** — after a large blocking event, AGC takes time to settle, producing apparent spike cluster
  - **Real in-band traffic** — a local LoRaWAN gateway or high-power IoT device on AU915 (at −47 dBm it would be very close/powerful)
  - Pi CM4 internal EMI less likely at this magnitude but worth noting
  - **Plan**: Build second M1 unit with same firmware to compare noise floor behaviour at same location — if second unit shows same spikes, it's environmental; if clean, it's hardware-specific to this unit. Consider running SDR scan during a spike event to identify the source frequency.
  - **Available SDR hardware**: RSPduo (primary, better dynamic range) + RTL-SDR (packed away). Available software: SDRConsole and SDRConnect (SDRuno found too complex). SDR investigation parked for now — second antenna connector not available. Will correlate spike timing with home activity in the meantime.
  - **CM4 onboard WiFi**: CM4 WiFi is active — used for SSH access. Cannot disable without alternative network path. Options: HomePlug/powerline adapter (preferred) or WiFi-to-ethernet bridge to provide wired access, then test with `sudo rfkill block wifi` and observe noise floor. Low priority until other causes eliminated.
  - **Optus phone (wife's device, third-party Optus)**: Optus Band 8 uplink is 890–915 MHz — handset transmitting to tower sits immediately below 915.075 MHz. At close range to the M1, could cause front-end blocking on SX1302. Spike pattern (irregular clusters, quiet for long stretches) is consistent with phone proximity. Test: correlate spike timing with phone location; try flight mode during a spike cluster to confirm.
  - **Possible code/measurement artifact**: The noise floor display uses SX1261 instantaneous RSSI reads for LBT/spectral scan. The SX1261 CAD cycle briefly activates the RF path — RF switch timing glitches during the measurement window can self-inject into the reading, producing apparent spikes that are not real signals. The −47 dBm spikes may be measurement artifacts rather than genuine external interference. Needs code investigation in the SX1261 RSSI read / spectral scan path.

- **Live repo git state**: currently on `feat/wm1303-bridge-mode` branch with stale conflict in `overlay/pymc_repeater/repeater/main.py` — service runs fine but branch is messy; clean up when safe
- **Pi origin remote**: updated to fork ✓ (both live repo and work clone point to fahimshariff-au/pyMC_WM1303)
- **README.md out of sync on Pi**: README was manually edited directly on GitHub (curl install instructions updated — previously pointed to HansvanMeer/upstream bootstrap address). The working clone (`~/pyMC_WM1303_work/`) and live path on Pi do NOT have this change. Next git session: run `git pull origin main` in `~/pyMC_WM1303_work/` to bring it back in sync before making any further README edits.

## Recently Fixed / Completed (this session)

- **Ping delivery fixed — c6→75 and e4 dashboard** (`71d3aa8`, `fecf31e`, manual wm1303_backend patch): Three bugs combined to silently drop every TRACE_RESP before it reached the companion. See FORK_NOTES.md `71d3aa8` for full root cause analysis. Key facts:
  - `trace_helper.py` actual path: `/opt/pymc_repeater/repos/pyMC_Repeater/repeater/handler_helpers/trace.py` (NOT `repeater/trace_helper.py`)
  - `wm1303_backend.py` is in the pymc_core venv, NOT in the fork — manual patch must be re-applied after any pymc_core upgrade
  - All three TRACE paths (c6→75, e4 dashboard, and likely b6→e4) share the same fix
- **`_load_prefs` GroupTextHandler sync** (`fecf31e`): `companion_bridge.py` now calls `gth.set_our_node_name()` after loading prefs from SQLite. Prevents stale echo filter name after UI rename.
- **CLAUDE.md topology corrected** (previous session): Full device table added (e4, c6, 75, b6, e8, 4e, DA), RF window placement, TX power notes, ping behaviour matrix, echo filter history.
- **GRP_TXT echo filter investigation** (previous session, investigation only): Confirmed "Own echo detected" logs are correct. GRP_TXT reception failure for c6 at 4km is RF asymmetry, not a software bug.
- **Trace event fixes** (`d38dc7d`): Added `tx_start`/`tx_drop` trace emissions to `bridge_engine.py` lines 787 and 1540. WM1303 UI trace logs now show complete packet lifecycle (received → dedup → bridge_inject → tx_start/drop). Fixes out-of-sync issue between UI traces and pymc dashboard.
- **Spectrum scan AU915** (`aacfc99`): scan range and heading changed from EU868 (863–870 MHz) to AU915 (915–928 MHz). Three files patched: `wm1303_api.py` (5 EU freq references), `sx1261_driver.py` (CalibrateImage bytes `[0xD7,0xDB]` → `[0xE1,0xE9]`), `wm1303.html` (hardcoded heading with en-dash).
- **Bug 2 companion RF RX deaf** (`2555cc0`): `router.enqueue(pkt)` with `_injected_for_tx=True` in `_bridge_repeater_handler`. Script: `fix-bug2-companion-rf.sh`.
- **radio_config SF/CR/TX power reporting** (`36a6017`, `e93e649`): `engine.py` built `radio_config` via `getattr(radio, "spreading_factor", 8)` etc. but `dispatcher.radio` is `VirtualLoRaRadio` which stored values in `self.channel_config` without plain attributes — `getattr` always fell back to EU defaults (SF=8, CR=8, tx_power=14). Fix: stamp `channel_config` values as plain instance attributes in `VirtualLoRaRadio.__init__` (overlay). Verified: logs now show `SF=9, BW=125000Hz, CR=5`. Note: `36a6017` (patched `repeater/config.py` stamping attrs on `WM1303Backend`) was a dead letter — `dispatcher.radio` is `VirtualLoRaRadio`, not `WM1303Backend`. `e93e649` is the real fix. Scripts: `fix-radio-config-reporting.sh` (dead letter), `fix-virtual-radio-attrs.sh` (real fix).
- **Fork documentation** (`913798e`): Added `AU915_SETUP.md` (AU915 Mid rationale, link budgets, Zindello community test results, Narrow coexistence, Optus caveat, ex-Helium hardware context) and `FORK_NOTES.md` (fork scope, `pi` username requirement flagged as future fix, complete AU modification log for all commits). Both files also saved to workspace folder.
- **README updated** (`949cad0`): Fork banner added at top, `pi` username requirement added to prerequisites, fork doc links added to documentation table.

---

## Session Tips

- **SCP logs, don't tail interactively** — saves context
- **Start fresh Cowork sessions** when a topic is resolved — less carried context = less usage per message
- **This CLAUDE.md is read at session start** — update it whenever a standing convention changes or an issue is resolved

---

## Standing Rule — Fork Hygiene

**Every fix, change, or investigation must consider whether the fork needs updating.**

At the end of any session where code is changed or a significant finding is made:

1. **Commit the fix** to `~/pyMC_WM1303_work` and push to `fahimshariff-au/pyMC_WM1303` (token method)
2. **Update `FORK_NOTES.md`** — add the commit to the AU modification log with hash, files changed, problem, and fix
3. **Update `README.md`** if the change affects prerequisites, install steps, or known limitations
4. **Update `AU915_SETUP.md`** if the change affects radio config, hardware behaviour, or AU915 band considerations
5. **Update this `CLAUDE.md`** — move resolved items to Recently Fixed, update Open/Pending Issues

If a session ends without a commit (e.g. investigation only), still note findings in CLAUDE.md so context is not lost.
