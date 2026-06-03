# Fresh Install Guide — fahimshariff-au/pyMC_WM1303 Fork
### AU915 Mid · SenseCAP M1 / WM1302-class hardware · v2.5.1 base

This guide covers a clean install of the AU-community fork of pyMC_WM1303 on a SenseCAP M1 (or any Raspberry Pi + WM1302/1303 HAT). It replaces the original AU915_SETUP.md for v2.5.1+ installs.

**What this fork adds over Hans's upstream:**
- AU915 Mid channel config baked in (correct RF center, SF9, BW125)
- TRACE/ping bug fixes — TCP companions can ping repeaters
- Companion RF RX fix — TCP companion actually hears received packets
- Correct spectrum scan range (915–928 MHz, not EU868)
- NF display fixes — no false spikes from Channel E / FSK
- `lora_rx.enable` default fixed — prevents spurious SX1261 EU channel when Channel E is absent

> **⚠️ UPGRADE PATH WARNING (DO NOT USE `upgrade.sh` FROM OLDER INSTALLS):** Do NOT use `upgrade.sh` or `upgrade.sh --skip-pull` to move from an older Hans upstream build to this fork. The upgrade script does not reset the region/preset in `wm1303_ui.json`. If the region field is in the wrong format (plain string vs nested dict) or points to AU915 (which uses wrong SX1261 calibration bytes for 915.075 MHz), the radio will silently miscalibrate. rxnb=0 is a known consequence. **Always bootstrap fresh** — wipe and reinstall from scratch using the steps below. It takes 15 minutes and avoids this entire class of failure.

---

## Hardware

- SenseCAP M1 (CM4 + WM1302 HAT) — reference hardware
- Also works on RAK7248, MNTD Blackspot/Goldspot, Bobcat 300, and similar WM1302-class boards
- TX power 22 dBm (radio) is the recommended setting with the stock SenseCAP M1 antenna (~2–3 dBi) = 24–25 dBm EIRP. Do not exceed 30 dBm EIRP (AU915 regulatory limit). If using a 6 dBi outdoor antenna, reduce to 20 dBm (20 + 6 = 26 dBm EIRP).

---

## Step 1 — Bootstrap

SSH into the Pi and run:

```bash
curl -sSL https://raw.githubusercontent.com/fahimshariff-au/pyMC_WM1303/main/bootstrap.sh | sudo bash
```

This installs the pymc-repeater service from our fork. Wait for it to complete — it will pull dependencies and set up systemd. The service will start but is not yet configured.

---

## Step 2 — WM1303 Hardware UI

Open `http://<pi-ip>:8000/wm1303.html` in a browser.

**RF Center Frequency:** set to `915.275`

**Channels:** With v2.4.10 Presets v3 a fresh install has no channels pre-configured. Add one channel:

| Field | Value |
|---|---|
| Name (internal) | `channel_a` |
| Frequency | `915.075 MHz` |
| Spreading Factor | 9 |
| Bandwidth | 125 kHz |
| Coding Rate | 4/5 |
| TX Power | 22 dBm |
| Preamble | 16 |
| LBT | enabled |

**TX Frequency Bounds:** 915 – 928 MHz

**Sync Word:** Private (0x1424 / 5156)

**Channel E and Channel F:** leave **disabled**. Channel F at its default EU frequency (869 MHz) will crash the HAL if enabled.

**Bridge Rules:** add exactly two rules:
- `channel_a → Repeater`
- `Repeater → channel_a`

Hit **Save & Restart**.

> **⚠️ CRITICAL WARNING: Do NOT use the Region / Preset selector after this point.** Selecting any preset (AU915, US915, EU868 — any of them) will overwrite your RF center frequency back to a regional default and destroy your Channel A config. This is an irreversible UI action with no undo. It will also reset `wm1303_ui.json` in ways that can cause rxnb=0 (the radio goes permanently deaf) on some units. Treat this page as write-once after initial setup — the only safe buttons to use going forward are **Save & Restart** after editing individual channel or TX bound fields.

---

## Step 3 — pyMC Wizard

Open `http://<pi-ip>:8000` and run the setup wizard.

- Node name: set to whatever you like (keep location info out of it for privacy)
- **Region: select AU915** — the calibration bytes bug in earlier versions has been fixed in v2.5.2. Hans's `region_config.py` AU915 entry now uses `(0xE1, 0xE9)` covering 900–932 MHz, which correctly includes 915.075 MHz. If you are on an older version (pre-v2.5.2), use US915 instead as a workaround — US915 has the same calibration bytes and will operate correctly on AU915 Mid frequency.
- Advert interval: 0.25 hours (15 minutes)
- TCP companion port: 5050 (or 5051 if you're running a second companion on the same unit)
- Mode: forward

Complete the wizard. The service will restart.

---

## Step 4 — Fix config.yaml

The wizard sets up repeater identity but does **not** sync the radio section of config.yaml from the hardware config. Several fields are left at EU/default values. Fix them all in one pass:

```bash
sudo sed -i \
  -e 's/preamble_length: 8/preamble_length: 16/' \
  -e 's/tx_power: 14/tx_power: 22/' \
  -e 's/send_advert_interval_hours: 10/send_advert_interval_hours: 0.25/' \
  -e 's/path_hash_mode: 0/path_hash_mode: 1/' \
  -e 's/frequency: 869462000/frequency: 915075000/' \
  -e 's/spreading_factor: 10/spreading_factor: 9/' \
  -e 's/preamble_length: 17/preamble_length: 16/' \
  /etc/pymc_repeater/config.yaml
```

> **⚠️ Do NOT change sync_word.** The wizard default of `sync_word: 5156` (0x1424) is correct for MeshCore — this is the LoRaWAN "private network" sync word that all MeshCore and Meshtastic devices use on-air. Changing it to 13380 (0x3444, LoRaWAN public) puts the node on the TTN/Helium sync word and makes it invisible to all MeshCore devices.

> Note: if the wizard picked AU915 as the region (v2.5.2+), it may have already defaulted `tx_power` to 22 rather than 14. The sed command is safe — if 14 is not found, that line is skipped.

Verify the result looks right:

```bash
grep -E "sync_word|preamble|tx_power|advert|path_hash|frequency|spreading" \
  /etc/pymc_repeater/config.yaml
```

Expected output:
```
sync_word: 5156
preamble_length: 16
tx_power: 22
send_advert_interval_hours: 0.25
path_hash_mode: 1
frequency: 915075000
spreading_factor: 9
```

---

## Step 5 — Fix LBT Threshold

The WM1303 UI "LBT (dBm)" field writes to `lbt_rssi_target` but the field that actually controls TX blocking is `lbt_threshold`. In v2.4.10 these are synced together, so set both directly:

```bash
sudo jq '
  (.channels[] | select(.name == "channel_a")).lbt_threshold = -65 |
  (.channels[] | select(.name == "channel_a")).lbt_rssi_target = -65
' /etc/pymc_repeater/wm1303_ui.json > /tmp/ui_lbt.json \
  && sudo cp /tmp/ui_lbt.json /etc/pymc_repeater/wm1303_ui.json
```

−65 dBm is a safe AU value for a clean indoor environment. If your noise floor is higher (e.g. near smart meters), you may need to raise this slightly — but start here.

---

## Step 5b — Fix ARB Correlators (MANDATORY for v2.5.x — prevents rxnb=0)

**This step is required on all v2.5.x installs.** A bug in Hans's WM1303 branch of `loragw_sx1302.c` writes `0x00` to the ARB correlator enable register, disabling all SX1302 demodulation. Without this fix, `chan_multiSF` is permanently dead and rxnb=0 on all units.

```bash
# On the Pi — patch the source and rebuild lora_pkt_fwd
cd /opt/pymc_repeater
grep -n "sx1302_arb_debug_write(3, 0x00)" $(find . -name "loragw_sx1302.c") 
```

Find the line (it will be inside an `#if defined(WM1303)` or similar block with a comment "FORCE ENABLED for all SF"). Change `0x00` to `0xFF`:

```bash
# Replace in source (confirm the path from the grep above first)
sudo sed -i 's/sx1302_arb_debug_write(3, 0x00)/sx1302_arb_debug_write(3, 0xFF)/' \
  /opt/pymc_repeater/lora_gateway/libloragw/src/loragw_sx1302.c
```

Then rebuild:
```bash
cd /opt/pymc_repeater/lora_gateway && sudo make clean && sudo make
sudo cp /opt/pymc_repeater/lora_gateway/lora_pkt_fwd/lora_pkt_fwd \
  /opt/pymc_repeater/bin/lora_pkt_fwd
```

After restart (Step 6), the logs should show:
```
ARB: dual demodulation FORCE ENABLED for all SF (WM1303 RX fix)
```
and rxnb should climb above 0 within a few minutes if other nodes are transmitting nearby.

---

## Step 6 — Restart and Verify

```bash
sudo systemctl restart pymc-repeater
sleep 15
```

**Check NF — should be below −80 dBm:**
```bash
sudo journalctl -u pymc-repeater -b --no-pager | grep -i "noise\|NF" | tail -5
```

**Check rxnb — should be climbing above 0 within a few minutes if other nodes are on air nearby:**
```bash
sudo journalctl -u pymc-repeater -b --no-pager | grep "rxnb" | tail -5
```

**Check TX — advert should fire within 15 minutes:**
```bash
sudo journalctl -u pymc-repeater -b --no-pager | grep -i "TX result\|direct TX\|advert" | tail -10
```

If NF is below −80 dBm and rxnb is climbing, you're on air and receiving. Open the pyMC dashboard (`http://<pi-ip>:8000`) — the Neighbours tab should start populating within a few minutes of first RX.

---

## Troubleshooting

**NF stuck at −64 to −75 dBm:**
Channel E or FSK is likely active. Check the WM1303 UI channels list and make sure only `channel_a` is present. If a second channel entry exists, remove it via jq:
```bash
sudo jq '.channels = [.channels[] | select(.name == "channel_a")]' \
  /etc/pymc_repeater/wm1303_ui.json > /tmp/clean.json \
  && sudo cp /tmp/clean.json /etc/pymc_repeater/wm1303_ui.json
sudo systemctl restart pymc-repeater
```

**rxnb stays at 0 permanently (even after fresh binary / fresh install):**
This is a known lora_pkt_fwd HAL init failure seen on multiple SenseCAP M1 units. TX typically still works (LBT PASS, CAD CLEAR, packets sent). Rebuilding lora_pkt_fwd from source (sx1302_hal latest master) does NOT fix it — the problem is in the HAL init path itself, not a specific binary version. The l34rn3d KISS wrapper uses a different init path and recovers RX on the same hardware. **If rxnb=0 persists after 30+ minutes with other nodes transmitting nearby, switch to KISS mode.** See CLAUDE.md KISS mode section, or the l34rn3d repo (github.com/l34rn3d/KISS_MeshCore_SX1302, semtech-driver branch).

> Note: Some users have also seen rxnb recover spontaneously after the unit has been running for several hours. Leave it running before concluding it's permanently deaf.

**Nodes appear as ? in MeshCore app:**
Usually means RX is working but ADVERTs aren't completing — check rxnb is > 0 and NF is clean. Also confirm sync_word in config.yaml is 5156 (not 13380 — 13380 is the LoRaWAN public sync word, invisible to MeshCore).

**Pings time out from MeshCore app:**
This is fixed in our fork (`71d3aa8`). If pings still fail after a fresh install from our fork, check the service is actually running our overlay: `sudo journalctl -u pymc-repeater -b --no-pager | head -20` should reference the fork path.

---

## What NOT to Do After Setup

- **Do not** use the Region / Preset selector on the WM1303 hardware UI — it will reset your RF center frequency and can cause rxnb=0 (radio goes deaf permanently on some units). This is the most dangerous action you can take on a running install.
- **Do not** change `sync_word` in config.yaml from 5156 to 13380 — 13380 is the LoRaWAN public (TTN/Helium) sync word and will make the node invisible to all MeshCore and Meshtastic devices. The wizard default of 5156 (0x1424, LoRaWAN private) is correct.
- **Do not** use `upgrade.sh` or `upgrade.sh --skip-pull` to move from an older install — always bootstrap fresh (see upgrade warning at the top of this guide).
- **Do not** run the pyMC wizard again unless you intend to fully reconfigure — it will reset config.yaml fields you fixed in Step 4.
- **Do not** enable Channel F without reconfiguring it first — the default EU frequency (869 MHz) is outside the SX1302 IF limit for an AU915 center and will crash the HAL.
- **Do not** change TX power above 22 dBm if you're using a 6 dBi or higher gain antenna — 22 dBm + 6 dBi = 28 dBm EIRP, within the AU915 30 dBm limit, but 27 dBm + 6 dBi = 33 dBm EIRP which exceeds it.
