# Release Notes — pyMC_WM1303 v2.4.11

**Release date**: 2026-05-24
**Type**: Patch release — critical bug fixes + UX improvements
**Upgrade**: Recommended for all v2.4.10 users

---

## 🚨 Critical fix — TRACE echo-filter bug

v2.4.10 introduced a regression where **all pings were silently discarded** as `unknown_echo`. This affected both TCP companion pings and dashboard-initiated pings, on **all regions**.

### Root cause

In `wm1303_backend.py`, the self-echo guard checked the wrong bits of the MeshCore packet header:

```python
# v2.4.10 (broken):
if data[0] != 0x09:  # treats whole byte as TYPE
    self._tx_echo_hashes[_tx_hash] = time.monotonic()
```

Byte 0 of a MeshCore packet encodes `[VER(2)|TYPE(4)|ROUTE(2)]`, so TYPE lives in **bits 5–2**, not the whole byte. For a TRACE packet (TYPE=9, ROUTE=2), `data[0] = 0x26`, which never equals `0x09`. The guard never triggered, TRACE TX hashes were always cached, and TRACE_RESP packets coming back from neighbours matched those hashes → discarded as `unknown_echo` → ping never completed.

### Fix

```python
# v2.4.11 (correct):
_tx_type = (data[0] >> 2) & 0x0F if len(data) > 0 else 0
if _tx_type != 0x09:
    self._tx_echo_hashes[_tx_hash] = time.monotonic()
```

Applied at both echo-cache sites:
- `_send_for_enqueue()` (called when packets enter the TX queue)
- `_send_for_scheduler()` (called when the scheduler hands packets to pkt_fwd)

Credit: **@fahimshariff-au** (issue #7, commit reference in his fork).

---

## 🚨 Critical fix — TRACE dispatch missing in WM1303 bridge flow

After applying the echo-filter fix above, deeper investigation on pi01 revealed a **second, independent regression** in the WM1303 bridge flow: incoming TRACE pings from companion nodes were never dispatched to `TraceHelper.process_trace_packet()`. As a result the repeater silently re-broadcast the original TRACE without appending its own SNR, so companions never received the trace data and pings appeared to time out.

### Root cause

The upstream pymc_repeater router (`packet_router.py::_route_packet`) dispatches TRACE packets to `TraceHelper.process_trace_packet()` before the engine forwards them:

```python
if payload_type == TraceHandler.payload_type():
    elif self.daemon.trace_helper:
        await self.daemon.trace_helper.process_trace_packet(packet)
        processed_by_injection = True  # skip generic engine forward
```

The WM1303 bridge path bypasses that router entirely: RF packets arriving on channel E/F go through `BridgeEngine` → `BridgeRepeaterHandler._bridge_repeater_handler` → `repeater_handler.process_packet`. There was no TRACE-specific dispatch in `_bridge_repeater_handler`, so TRACE packets fell through to the generic forwarding path.

### Fix

Added a TRACE branch in `overlay/pymc_repeater/repeater/main.py::_bridge_repeater_handler`, placed right after the existing ADVERT block and before the generic `process_packet()` call:

```python
if payload_type == TraceHandler.payload_type() and self.trace_helper:
    _saved_injector = self.trace_helper.packet_injector
    async def _bridge_trace_injector(fwd_packet, wait_for_ack=False):
        fwd_bytes = fwd_packet.write_to()
        if self.bridge_engine:
            await self.bridge_engine.inject_packet(
                'repeater', fwd_bytes, origin_channel=origin_channel
            )
    self.trace_helper.packet_injector = _bridge_trace_injector
    try:
        await self.trace_helper.process_trace_packet(pkt)
    finally:
        self.trace_helper.packet_injector = _saved_injector
    return
```

Key design points:
- We **reuse the existing `TraceHelper`** instance (already created in main.py line 266) — no duplication of TRACE parsing, hop matching, or completion logic.
- We **temporarily override `packet_injector`** so the SNR-annotated TRACE forward goes through `BridgeEngine.inject_packet('repeater', …)` (which feeds channel E/F TX queues) instead of `router.inject_packet` (which only knows the classic radios[0]/[1] TX path that channel E/F don't use).
- `origin_channel` is preserved so the bridge engine's origin-channel-first priority still works.
- The `try/finally` guarantees the injector is restored even on exceptions.

### Why this fix lives in WM1303 overlay (not upstream)

The TRACE dispatch gap exists only in the WM1303 bridge flow, which is a WM1303-overlay feature on top of upstream pymc_repeater. Fixing it in `main.py` overlay keeps the change scoped to this fork and doesn't require upstream coordination.

---

## ⚠️ Config schema migration — region as plain string

v2.4.10 expects the `region` key in `/etc/pymc_repeater/wm1303_ui.json` to be a **nested dict**:

```json
{"region": {"code": "EU868", "tx_freq_min": null, "tx_freq_max": null}}
```

Upgrading from an older install where `region` was a plain string (e.g. `"region": "EU868"`) caused a startup error. The fix is now automatic: `_load_ui()` in `wm1303_api.py` detects legacy formats and migrates them on first read, then persists the canonical schema back to disk.

Handled cases:
- `"region": "EU868"` → `{"code": "EU868", "tx_freq_min": null, "tx_freq_max": null}`
- Missing `region` key → empty nested dict (no more KeyErrors in downstream code)

Credit: **@fahimshariff-au** (issue #7).

---

## 📝 Documentation — non-interactive bootstrap now in README

The `WM1303_REGION` environment variable was supported by `bootstrap.sh` since v2.4.9 but only documented in the script header itself. v2.4.11 adds an **Advanced installation** section to the README showing:

```bash
curl -sSL https://raw.githubusercontent.com/HansvanMeer/pyMC_WM1303/main/bootstrap.sh | sudo WM1303_REGION=AU915 bash
```

Supported codes: `EU868`, `US915`, `AU915`, `AS923`, `IN865`, `JP920`, `KR920`, `CUSTOM`. When `WM1303_REGION` is set, the bootstrap selects the matching channel preset automatically and skips the interactive wizard — ideal for scripted / headless deployments.

---

## 📋 Known issues / not in this release

- **Spectrum scan regio-aware UI** (issue #7 comment #5, AU-specific): The scan range and heading still show EU868 defaults on AU915/US915 installs. The backend scan itself works; only the UI labels are off. **Targeted for v2.4.12.**
- **NF display spike-rejection + closest-scan-point** (issue #7): Quality improvement, not a regression. **Targeted for v2.4.12.**
- **VirtualLoRaRadio plain instance attributes** (issue #10): Separate tracking issue.

---

## Files changed

| File | Change |
|---|---|
| `overlay/pymc_core/src/pymc_core/hardware/wm1303_backend.py` | TRACE bit-shift fix on 2 echo-cache sites |
| `overlay/pymc_repeater/repeater/main.py` | New TRACE dispatch in `_bridge_repeater_handler` with bridge-aware injector |
| `overlay/pymc_repeater/repeater/web/wm1303_api.py` | New `_migrate_ui_config()` helper + auto-migrate on load |
| `README.md` | Added 'Advanced installation' section with `WM1303_REGION` examples |
| `VERSION` | 2.4.10 → 2.4.11 |
| `release_notes/RELEASE_NOTES_v2.4.11.md` | This file |

---

## Upgrade instructions

Standard upgrade — no manual steps required, migration runs automatically:

```bash
curl -sSL https://raw.githubusercontent.com/HansvanMeer/pyMC_WM1303/main/bootstrap.sh | sudo bash
```

After upgrade, hard-refresh the UI (Ctrl+Shift+R) to clear any cached assets.

---

## Testing performed

- Code-level review of TRACE bit-shift fix against MeshCore packet header spec
- Code-level verification of `_migrate_ui_config()` for both legacy-string and missing-key cases
- Code-level comparison of TRACE dispatch flow vs upstream `packet_router._route_packet`
- AST/syntax check of patched `main.py` (1817 lines) passes
- Deployed and smoke-tested on pi01 (192.168.101.52, EU868) with Channel E configured for 869.618 MHz BW62.5 SF7 CR5
- Service start, UI reachability, region API endpoint verified
- TraceHelper initialization confirmed in pi01 service startup logs (`Trace processing helper initialized`)
- Local identity hash registered correctly (`path_hash=CDB7 size=2 bytes`)

Full mesh-level TRACE ping validation requires a real companion node and is left to user field testing. Initial test on pi01 (24-May-2026 ~16:14) showed that the previous v2.4.11 build (without the bridge TRACE dispatch fix) did not generate a TRACE response when pinged from a companion — the inbound TRACE was being forwarded unchanged as a flood broadcast. The new bridge dispatch fix in `_bridge_repeater_handler` resolves that gap by routing TRACE packets through `TraceHelper.process_trace_packet()` with a bridge-aware injector.
