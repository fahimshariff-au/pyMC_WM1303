# Release Notes — v2.4.8

**Date:** 2025-05-06

## Summary

UI enhancement for packet tracing search and default configuration cleanup.

## Changes

### Tracing Tab — Search Filters (UI)
- Added three separate search input fields to the Tracing tab: **Src**, **Last hop**, and **Dst**
- Each field independently filters traces using partial, case-insensitive matching
- Fields are ordered to match the column header: Src → Last hop → Dst
- Filters are cumulative (AND logic): filling multiple fields narrows results
- Filtering is real-time (on each keystroke), no extra API calls required
- Operates client-side on already-loaded trace data

### Configuration Template Cleanup
- **LetsMesh MQTT broker**: disabled by default (`enabled: false`)
  - New installations no longer auto-connect to the community MQTT broker
  - Users must explicitly enable if they want LetsMesh integration
- **IATA code**: cleared from default template (was: `GLZ`)
  - Prevents new installations from broadcasting with a pre-filled location code

### Service Modem (SX1302)
- **chan_Lora_std** disabled by default in `bridge_conf.json` generation
  - The SX1302 service modem (IF chain 8) is not used in the current architecture
  - Research confirmed BW62.5 kHz RX is not supported by SX1302 hardware
  - Disabling prevents false-positive ghost detections and saves minimal power

## Technical Details

### Service Modem Research Conclusion
Extensive testing confirmed that the SX1302 service modem **cannot** receive BW62.5 kHz LoRa signals:
- BW62.5 correlator: hardware refuses to demodulate
- BW125 correlator + DDC 62.5 kHz: ghost events only (size=0, CRC_DISABLED)
- BW125 correlator + DDC 125 kHz + CONTINUOUS: false triggers (SNR << 0 dB)
- Software demodulation via capture_ram: channelizer corrupts symbol values

The SX1261 (channel E) remains the only viable path for BW62.5 kHz reception.

## Files Changed

| File | Change |
|---|---|
| `config/config.yaml.template` | `letsmesh.enabled: false`, `iata_code: ''` |
| `overlay/pymc_core/.../wm1303_backend.py` | `chan_Lora_std.enable: False` |
| `overlay/pymc_repeater/.../wm1303.html` | Tracing search filters added |
| `VERSION` | `2.4.7` → `2.4.8` |

## Upgrade Notes

- Hard refresh (Ctrl+F5) the WM1303 Manager UI to see the new search fields
- Existing installations with `letsmesh.enabled: true` in their config are **not affected** — the template change only applies to new installations
- The service modem disable only affects the initial `bridge_conf.json` generation; existing configs retain their current settings
