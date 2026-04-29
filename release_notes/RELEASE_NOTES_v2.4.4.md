# Release Notes v2.4.4

## Upstream Sync — pyMC_core 1.0.10 & pyMC_Repeater 1.0.8.dev210

Major upstream synchronization bringing 18 commits from pyMC_core and ~140 commits from pyMC_Repeater into the WM1303 overlay architecture. All 9 affected overlay files have been re-merged, tested, and verified on hardware.

---

### Upstream Features Adopted

#### From pyMC_core 1.0.10 (18 commits)
- **Multiple EN pins support** — SX1262 wrapper accepts `en_pins[]` list for multi-radio setups
- **CLI_DATA text type** — New `TXT_TYPE_CLI_DATA` message type for admin CLI communication
- **Companion race condition fixes** — Writer teardown and client eviction improvements
- **Python 3.9 type-hint compatibility** — Broader platform support

#### From pyMC_Repeater dev210 (~140 commits)
- **MQTT broker migration** — LetsMesh handler replaced by modern MQTT handler with multi-broker support, JWT authentication, and automatic reconnection
- **TX Lock** — `asyncio.Lock` serializes radio TX to prevent SPI interleaving (correctly co-exists with WM1303's separate TX queue architecture)
- **Glass platform integration** — New pyMC Glass telemetry publishing
- **Performance optimizations:**
  - `deque(maxlen=50)` for recent packets (was unbounded list)
  - O(1) hash index for duplicate detection (was O(n) reverse scan)
  - Single SHA-256 per packet, result reused throughout pipeline
  - Debug log guards (`isEnabledFor(DEBUG)`) prevent string formatting overhead
  - Cached noise floor readings
- **In-flight task semaphore** — `max_in_flight=30` prevents unbounded concurrent forwarding tasks
- **Graceful shutdown** — Drain packet router, cancel tasks, double-shutdown guard
- **SQLite improvements** — Thread-local connections, WAL mode, busy timeout, new schema migrations
- **Live radio config** — Runtime radio parameter changes without restart
- **Airtime tracking** — New API endpoint with bucket aggregation
- **HTTP thread pool** — Configurable `thread_pool=8`, `thread_pool_max=16`

---

### Overlay Re-merge Summary

| File | Upstream Adoptions | WM1303 Preserved |
|---|---|---|
| `engine.py` | TX lock, deque, hash caching, debug guards, cached noise floor | Multi-channel TX, bridge integration, custom scoring, TTL eviction |
| `sqlite_handler.py` | Thread-local connections, WAL mode, 3 new migrations | WM1303 tables, custom queries, channel metrics |
| `storage_collector.py` | MQTT handler, glass publisher, deferred publishing | WM1303 stats, spectrum/noise/CAD collection |
| `config.py` | MQTT config, glass config, owner_info, unscoped_flood | WM1303 radio type, channel config, bridge config |
| `main.py` | Graceful shutdown, glass handler, MQTT init | WM1303 backend, bridge engine, BridgeRepeaterHandler |
| `api_endpoints.py` | MQTT endpoints, airtime, flood rename | WM1303 API (channels, spectrum, bridge, TX queue) |
| `packet_router.py` | In-flight semaphore, graceful drain | Multi-channel routing, bridge integration |
| `config_manager.py` | Live radio config methods | HAL config generation, channel management |
| `http_server.py` | Thread pool configuration | WM1303 web UI, WebSocket, custom routes |

---

### Bug Fix

- **Missing `wm1303` radio type** — The `get_radio_for_board()` function in `config.py` was missing the `wm1303` radio type case after re-merge, causing service startup failure. Fixed immediately during testing.

---

### New Dependencies

- `paho-mqtt>=1.6.0` — Required by the new MQTT handler (installed automatically via pyproject.toml)

---

### Safety & Rollback

- Tag `v2.4.3-safe` created before this upgrade — use `git checkout v2.4.3-safe` to revert if needed
- Forks synced: `HansvanMeer/pyMC_core` → `rightup/pyMC_core` (dev branch)
- Forks synced: `HansvanMeer/pyMC_Repeater` → `rightup/pyMC_Repeater` (dev branch)

---

### Tested On

- **pi03** (192.168.101.80) — Full pipeline verified: service active, MQTT connected (Europe + US West), Channel E RX/TX, Bridge forwarding, database storage with RSSI/SNR/path hashes, WM1303 API HTTP 200
