# Fork Notes — fahimshariff-au/pyMC_WM1303

This document records the scope, known requirements, and complete modification history of this fork relative to the upstream [HansvanMeer/pyMC_WM1303](https://github.com/HansvanMeer/pyMC_WM1303).

---

## Fork Scope

This fork targets **Pi-based hardware with a WM1302/WM1303 LoRa HAT** running MeshCore repeater firmware in the **Australian 915–928 MHz ISM band**, configured for **AU915 Mid** (915.075 MHz, SF9, BW125kHz, CR4/5).

The hardware class this fork is built and tested on includes:

- **SenseCAP M1** (Raspberry Pi CM4 + WM1302 HAT) — primary test hardware
- Repurposed Helium miners with the same Pi + WM1302 architecture (RAK hotspots, MNTD, Bobcat 300, etc.)
- Any Raspberry Pi fitted with a WM1302 or WM1303 HAT

The WM1302/1303 HAT includes an external PA stage, which means this hardware class can achieve the full **30 dBm EIRP** used in the AU915 Mid configuration — the full link budget advantage over Narrow applies.

**This fork is bespoke for AU915 Mid.** There is no runtime region-selection or multi-profile system. If you need a different region or frequency, manually edit `config.yaml`. A multi-region profile system is flagged as a future improvement (see Known Issues below).

See [AU915_SETUP.md](AU915_SETUP.md) for the full rationale for AU915 Mid.

---

## Known Requirements and Limitations

### Pi User Account: Must Be `pi`

**The bootstrap install script and all patch/fix scripts in this fork hardcode the username `pi`.** The install path assumptions are:

- Home directory: `/home/pi/`
- Working clone: `/home/pi/pyMC_WM1303_work/`
- Fix scripts are copied to `~/` (i.e. `/home/pi/`)

**Requirement**: The Raspberry Pi must be set up with `pi` as the primary admin account. If you have renamed the account or are using a different username, paths in the scripts will break.

**Future fix (flagged)**: Update all scripts to either (a) detect the calling user at runtime (`whoami` / `$HOME`) or (b) accept a `--user <username>` argument at install time. This will be addressed in a later release. For now, use the default `pi` account.

### Upstream Bootstrap Script

The upstream `bootstrap.sh` from HansvanMeer is invasive — it modifies system packages and installs a systemd service. **Back up your SD card before running it.** The fork patches are applied on top of an existing install; the bootstrap itself is not patched.

---

## AU Modification Log

All changes relative to upstream `HansvanMeer/pyMC_WM1303` are recorded here in reverse chronological order.

---

### `e93e649` — Fix radio_config SF/CR/TX power reporting (real fix)

**Date**: May 2026  
**Files patched**: `overlay/pymc_core/src/pymc_core/hardware/virtual_radio.py`  
**Script**: `fix-virtual-radio-attrs.sh`

**Problem**: `engine.py` builds `radio_config` using plain `getattr()` calls:
```python
getattr(radio, "spreading_factor", 8)   # → always 8 (EU default)
getattr(radio, "coding_rate", 8)         # → always 8 (EU default)
getattr(radio, "tx_power", 14)           # → always 14 (EU default)
```
`dispatcher.radio` is `VirtualLoRaRadio`, which stored the correct values in `self.channel_config` but never exposed them as plain instance attributes. `getattr()` therefore always fell through to the EU hardcoded defaults (SF8, CR8, tx_power=14) regardless of the actual AU915 config.

Effect: companion apps received wrong radio parameters in every ACK; `calculate_packet_score()` used incorrect SF thresholds.

**Fix**: In `VirtualLoRaRadio.__init__`, after `self.channel_config = channel_config`, stamp the channel config values as plain instance attributes:
```python
_cr = channel_config.get('coding_rate', '4/5')
_cr_map = {'4/5': 5, '4/6': 6, '4/7': 7, '4/8': 8}
self.spreading_factor = int(channel_config.get('spreading_factor', 9))
self.bandwidth        = int(channel_config.get('bandwidth', 125000))
self.coding_rate      = _cr_map.get(str(_cr), 5) if isinstance(_cr, str) else int(_cr)
self.tx_power         = int(channel_config.get('tx_power', 20))
self.frequency        = int(channel_config.get('frequency', 916200000))
self.preamble_length  = int(channel_config.get('preamble_length', 17))
```
Note: `coding_rate` is converted from string `"4/5"` to integer `5` to match the format `engine.py` and `CompanionBridge` expect.

**Verified**: After restart, logs show `radio settings: SF=9, BW=125000Hz, CR=5` (correct AU915 Mid values) instead of `SF=8, BW=125000Hz, CR=8`.

---

### `36a6017` — Fix radio_config reporting (dead letter — harmless)

**Date**: May 2026  
**Files patched**: `repeater/config.py`  
**Script**: `fix-radio-config-reporting.sh`

**Note**: This commit attempted to fix the same radio_config bug by stamping attributes on `WM1303Backend` after creation in `get_radio_for_board()`. It was ineffective because `dispatcher.radio` is `VirtualLoRaRadio`, not `WM1303Backend`. The patch is harmless and was left in place. The real fix is `e93e649` above.

---

### `2555cc0` — Fix companion RF RX deaf (Bug 2)

**Date**: May 2026  
**Files patched**: `overlay/pymc_repeater/repeater/main.py`  
**Script**: `fix-bug2-companion-rf.sh`

**Problem**: The RF-to-companion bridge path in `_bridge_repeater_handler` was not injecting received RF packets into the router queue before processing, causing companion apps to be deaf to RF traffic — they could transmit but not receive.

**Fix**: In `_bridge_repeater_handler`, before calling `process_packet()`, enqueue the packet with the injection flag:
```python
pkt._injected_for_tx = True
router.enqueue(pkt)
```
This ensures the packet is routed to connected companions.

---

### `aacfc99` — Spectrum scan AU915 (frequency and calibration fix)

**Date**: May 2026  
**Files patched**:
- `overlay/pymc_repeater/wm1303_api.py` (5 EU frequency references)
- `overlay/pymc_core/src/pymc_core/hardware/sx1261_driver.py` (CalibrateImage bytes)
- `overlay/pymc_repeater/wm1303.html` (hardcoded heading)

**Problem**: The spectrum scanner was calibrated and ranged for the EU868 band (863–870 MHz). Running in Australia, the scan returned no useful data and the UI displayed the wrong frequency range.

**Fix**:

*`wm1303_api.py`* — Changed 5 EU868 frequency references to AU915 range:
- Scan start: 863 MHz → 915 MHz
- Scan end: 870 MHz → 928 MHz
- Related step/range calculations updated accordingly

*`sx1261_driver.py`* — Changed `CalibrateImage` bytes from EU868 calibration to AU915:
```python
# Before (EU868):
[0xD7, 0xDB]
# After (AU915):
[0xE1, 0xE9]
```
The SX1261 image rejection calibration must be run for the target frequency band. `0xE1` = 915 MHz lower bound, `0xE9` = 928 MHz upper bound per the SX1261 datasheet table.

*`wm1303.html`* — Changed the hardcoded spectrum scan heading from the EU868 range label to display the AU915 range (915–928 MHz).

---

### Default config targeting AU915 Mid

**Note**: The reference `config.yaml` in this fork is configured for AU915 Mid out of the box:
- `frequency: 916200000` — **this should be updated to `915075000` for AU915 Mid**
- `bandwidth: 125000`
- `spreading_factor: 9`
- `coding_rate: "4/5"`
- `tx_power: 20`

> **TODO**: Update the default `config.yaml` in the fork to use `915075000` as the default frequency so fresh installs are pre-configured for AU915 Mid without manual adjustment.

---

## Future / Flagged Items

| Item | Priority | Notes |
|------|----------|-------|
| Multi-region profile system | Low | Not planned for near term; fork is AU915 Mid only. Update `config.yaml` manually for other regions. |
| Fix hardcoded `pi` username in scripts | Medium | All scripts assume `/home/pi/`. Should detect `$HOME`/`$USER` or accept `--user` arg at install time. |
| Update default `config.yaml` to 915075000 | Medium | Currently ships with a legacy frequency; fresh installs need manual edit. |
| Regional profile at first-run setup | Low | Future improvement: installer asks for region and sets config accordingly. |

---

## Upstream Reference

- Upstream repo: [HansvanMeer/pyMC_WM1303](https://github.com/HansvanMeer/pyMC_WM1303)
- This fork: [fahimshariff-au/pyMC_WM1303](https://github.com/fahimshariff-au/pyMC_WM1303)
- Fork strategy: overlay model — customisations live in `overlay/` and are applied over the upstream install via editable pip installs and systemd path overrides. The live service path is `/opt/pymc_repeater/repos/pyMC_Repeater/`. **Never switch branches in the live path** — use `~/pyMC_WM1303_work/` for all git operations.
