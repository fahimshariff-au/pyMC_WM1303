# Fresh Install Guide — fahimshariff-au/pyMC_WM1303 Fork
### AU915 Mid · SenseCAP M1 / WM1302-class hardware · v2.4.10 base

This guide covers a clean install of the AU-community fork of pyMC_WM1303 on a SenseCAP M1 (or any Raspberry Pi + WM1302/1303 HAT). It replaces the original AU915_SETUP.md for v2.4.10+ installs.

**What this fork adds over Hans's upstream:**
- AU915 Mid channel config baked in (correct RF center, SF9, BW125)
- TRACE/ping bug fixes — TCP companions can ping repeaters
- Companion RF RX fix — TCP companion actually hears received packets
- Correct spectrum scan range (915–928 MHz, not EU868)
- NF display fixes — no false spikes from Channel E / FSK

---

## Hardware

- SenseCAP M1 (CM4 + WM1302 HAT) — reference hardware
- Also works on RAK7248, MNTD Blackspot/Goldspot, Bobcat 300, and similar WM1302-class boards
- TX power 20 dBm (radio) + antenna gain. With stock SenseCAP M1 antenna (~2–3 dBi) = 22–23 dBm EIRP. Do not exceed 30 dBm EIRP (AU915 regulatory limit).

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
| TX Power | 20 dBm |
| Preamble | 16 |
| LBT | enabled |

**TX Frequency Bounds:** 915 – 928 MHz

**Sync Word:** Public (0x3444 / 13380)

**Channel E and Channel F:** leave **disabled**. Channel F at its default EU frequency (869 MHz) will crash the HAL if enabled.

**Bridge Rules:** add exactly two rules:
- `channel_a → Repeater`
- `Repeater → channel_a`

Hit **Save & Restart**.

> **Important:** After this point, do **not** use the Region / Preset selector in this UI. Selecting any preset (AU, Brazil, EU, US — any of them) will overwrite your RF center frequency and silently break Channel A. Treat this page as write-once after initial setup.

---

## Step 3 — pyMC Wizard

Open `http://<pi-ip>:8000` and run the setup wizard.

- Node name: set to whatever you like (keep location info out of it for privacy)
- Region: AU915
- Advert interval: 0.25 hours (15 minutes)
- TCP companion port: 5050 (or 5051 if you're running a second companion on the same unit)
- Mode: forward

Complete the wizard. The service will restart.

---

## Step 4 — Fix config.yaml

The wizard sets up repeater identity but does **not** sync the radio section of config.yaml from the hardware config. Several fields are left at EU/default values. Fix them all in one pass:

```bash
sudo sed -i \
  -e 's/sync_word: 5156/sync_word: 13380/' \
  -e 's/preamble_length: 8/preamble_length: 16/' \
  -e 's/tx_power: 14/tx_power: 20/' \
  -e 's/send_advert_interval_hours: 10/send_advert_interval_hours: 0.25/' \
  -e 's/path_hash_mode: 0/path_hash_mode: 1/' \
  -e 's/frequency: 869462000/frequency: 915075000/' \
  -e 's/spreading_factor: 10/spreading_factor: 9/' \
  -e 's/preamble_length: 17/preamble_length: 16/' \
  /etc/pymc_repeater/config.yaml
```

Verify the result looks right:

```bash
grep -E "sync_word|preamble|tx_power|advert|path_hash|frequency|spreading" \
  /etc/pymc_repeater/config.yaml
```

Expected output:
```
sync_word: 13380
preamble_length: 16
tx_power: 20
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

**rxnb stays at 0 permanently:**
This is a known hardware fault on some units where lora_pkt_fwd's HAL init fails. TX may still work. The fix is to run the l34rn3d KISS wrapper instead — see the KISS section in CLAUDE.md or ask in the Discord.

**Nodes appear as ? in MeshCore app:**
Usually means RX is working but ADVERTs aren't completing — check rxnb is > 0 and NF is clean. Also confirm sync_word in config.yaml is 13380 (not 5156).

**Pings time out from MeshCore app:**
This is fixed in our fork (`71d3aa8`). If pings still fail after a fresh install from our fork, check the service is actually running our overlay: `sudo journalctl -u pymc-repeater -b --no-pager | head -20` should reference the fork path.

---

## What NOT to Do After Setup

- **Do not** use the Region / Preset selector on the WM1303 hardware UI — it will reset your RF center frequency.
- **Do not** run the pyMC wizard again unless you intend to fully reconfigure — it will reset config.yaml fields you fixed in Step 4.
- **Do not** enable Channel F without reconfiguring it first — the default EU frequency (869 MHz) is outside the SX1302 IF limit for an AU915 center and will crash the HAL.
- **Do not** change TX power above 20 dBm if you're using a 6 dBi or higher gain antenna — 20 dBm + 6 dBi = 26 dBm EIRP, still within the AU915 30 dBm limit. Higher TX power with high-gain antenna risks exceeding the regulatory limit.
