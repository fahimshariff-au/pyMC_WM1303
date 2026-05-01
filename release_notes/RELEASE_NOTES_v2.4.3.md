# Release Notes — v2.4.3

**Release date:** 2026-04-29

This release fixes RSSI/SNR signal quality propagation across the entire packet pipeline and adds path hash parsing to the bridge engine, ensuring the WM1303 Manager UI correctly displays signal quality metrics and routing path information for all received packets.

---

## Bug Fixes

### RSSI/SNR propagation — end-to-end fix

Previously, pymc-repeater could rarely determine the RSSI and SNR of nodes. Investigation revealed that while the WM1303 backend correctly extracts `rssi` and `lsnr` from the SX1302's `rxpk` JSON, the values were lost at multiple points in the pipeline.

**5 gaps identified and fixed:**

| # | Location | Problem | Fix |
|---|----------|---------|-----|
| 1 | `main.py` BridgeRepeaterHandler | Created new Packet objects from raw bytes with default rssi=0, snr=0 | Pass rssi/snr from bridge_engine and set `_rssi`/`_snr` private attributes |
| 2 | `channel_e_bridge.py` `_rx_from_backend()` | Had rssi/snr available but did not pass them to `inject_packet()` | Forward rssi/snr parameters to inject_packet() |
| 3 | `models.py` + `contact_store.py` | Contact model lacked `last_rssi`/`last_snr` fields | Added fields with serialize/deserialize support |
| 4 | `bridge_engine.py` `inject_packet()` | No rssi/snr parameters accepted | Added rssi/snr parameters, forwarded through `_forward_by_rules()` |
| 5 | `bridge_engine.py` `_update_repeater_counters()` | 7 callers never passed rssi/snr → always stored defaults (-120/0.0) in SQLite | All callers now pass actual rssi/snr values |

**Additional bug:** The Packet class defines `rssi` and `snr` as read-only `@property` descriptors. Initial fix attempted `pkt.rssi = value` which raised `AttributeError`. Corrected to set private attributes `pkt._rssi` / `pkt._snr` directly.

---

### Path/Hashes display — `????` replaced with actual routing data

The "Path/Hashes" column in the WM1303 Manager Recent Packets view always showed `????` because `_update_repeater_counters()` never parsed path information from the raw MeshCore packet bytes.

**Fix:** Added `_parse_path_info()` static method to BridgeEngine that extracts:
- **Path hashes** — per-hop routing addresses (1–3 bytes each)
- **Path hash display** — formatted as `[12, 7B, 43, 07, 7C]`
- **src_hash** — source address from payload (type-dependent)
- **dst_hash** — destination address from payload (type-dependent)
- **path_hash_size** — hash size per hop (1, 2, or 3 bytes)

The parsing follows the MeshCore wire format: header byte → optional transport codes → path_len byte (hop count + hash size encoding) → path bytes → payload.

Source/destination extraction rules (matching engine.py behavior):
- REQ/RESPONSE/TXT/PATH (0x00–0x02, 0x08): `dst = payload[0]`, `src = payload[1]`
- ADVERT (0x04): `src = payload[0]`
- ANON_REQ (0x07): `dst = payload[0]`

---

## Files Changed

| File | Changes |
|------|--------|
| `overlay/pymc_repeater/repeater/bridge_engine.py` | Added `_parse_path_info()`, RSSI/SNR passthrough in all `_update_repeater_counters()` callers, rssi/snr params in `inject_packet()` and `_forward_by_rules()` |
| `overlay/pymc_repeater/repeater/channel_e_bridge.py` | Forward rssi/snr from `_rx_from_backend()` to `inject_packet()` |
| `overlay/pymc_repeater/repeater/main.py` | BridgeRepeaterHandler sets `_rssi`/`_snr` on parsed Packets |
| `overlay/pymc_core/src/pymc_core/companion/models.py` | Added `last_rssi`/`last_snr` fields to Contact model |
| `overlay/pymc_core/src/pymc_core/companion/contact_store.py` | Serialize/deserialize RSSI/SNR per contact |
| `install.sh` | Copy companion overlay files during installation |
| `upgrade.sh` | Copy companion overlay files during upgrade |
| `VERSION` | 2.4.2 → 2.4.3 |

---

## Verification

Confirmed on test unit:
- RSSI values: -71 to -78 dBm (previously always -120)
- SNR values: 4.5 to 11.0 dB (previously always 0.0)
- Path hashes: `[12, 7B, 43, 07, 7C]` (previously `????`)
- Source/destination hashes: `src=79, dst=91` (previously blank)
- No errors in service logs after restart
