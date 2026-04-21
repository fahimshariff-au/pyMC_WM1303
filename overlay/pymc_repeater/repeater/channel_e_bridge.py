"""Channel E (native LoRa) Bridge Plugin for pymc-repeater.

Minimal plugin that:
- Listens on UDP port 1733 for LoRa packets from the Channel E RX daemon
- Injects them into the BridgeEngine (RX path)
- Handles TX by routing packets through the existing GlobalTXScheduler

Channel E parameters (frequency, SF, BW, CR, preamble, tx_power) are
read dynamically from /etc/pymc_repeater/wm1303_ui.json at runtime.

TX uses the SX1302/SX1250/SKY66420 path via PULL_RESP to lora_pkt_fwd.

Usage (inside pymc-repeater):
    from channel_e_bridge import ChannelEBridge
    ch_e = ChannelEBridge(bridge_engine, backend=radio)
    asyncio.create_task(ch_e.run())
"""
import asyncio
import json
import logging
import socket
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

CHANNEL_E_NAME = 'channel_e'
CHANNEL_E_UDP_PORT = 1733
CHANNEL_E_TX_CHANNEL = 'channel_e'
UI_CONFIG_PATH = Path('/etc/pymc_repeater/wm1303_ui.json')


def _load_channel_e_ui() -> dict:
    """Load channel_e settings from wm1303_ui.json."""
    try:
        if UI_CONFIG_PATH.exists():
            return json.loads(UI_CONFIG_PATH.read_text()).get('channel_e', {})
    except Exception as e:
        logger.warning('ChannelEBridge: failed to read UI config: %s', e)
    return {}


class ChannelEBridge:
    """Async UDP listener that feeds Channel E decoded packets into BridgeEngine."""

    def __init__(self, bridge_engine, udp_port=CHANNEL_E_UDP_PORT, backend=None):
        self.bridge = bridge_engine
        self.udp_port = udp_port
        self.backend = backend  # WM1303Backend for TX
        self.packets_received = 0
        self.packets_injected = 0
        self.packets_errors = 0
        self.tx_packets = 0
        self.tx_errors = 0
        self._running = False
        self._loop = None  # stored in run() for cross-thread async injection

    async def _tx_handler(self, data: bytes):
        """Handle packets forwarded TO Channel E - TX via HAL.

        Uses the SX1302/SX1250/SKY66420 TX path with parameters from
        the channel_e TX queue (configured from wm1303_ui.json).
        """
        if self.backend is None:
            logger.warning('Channel E TX: no backend, cannot send %d bytes', len(data))
            return

        try:
            # Route through existing TX queue (GlobalTXScheduler)
            if hasattr(self.backend, '_tx_queue_manager') and self.backend._tx_queue_manager:
                queue = self.backend._tx_queue_manager.queues.get(CHANNEL_E_TX_CHANNEL)
                if queue:
                    result = await queue.enqueue(data)
                    if result.get('ok'):
                        self.tx_packets += 1
                        logger.info(
                            'Channel E TX: sent %d bytes via HAL '
                            '(send=%.1fms, airtime=%.1fms)',
                            len(data),
                            result.get('send_ms', 0),
                            result.get('airtime_ms', 0)
                        )
                    else:
                        self.tx_errors += 1
                        logger.warning(
                            'Channel E TX FAIL: %s (%d bytes)',
                            result.get('error', 'unknown'), len(data)
                        )
                    return
                else:
                    logger.warning('Channel E TX: no channel_e queue found in TXQueueManager')
            else:
                logger.warning('Channel E TX: no TXQueueManager on backend')

            # Fallback: try backend.send() directly with UI-configured tx_power
            _ui = _load_channel_e_ui()
            _tx_power = int(_ui.get('tx_power', 27))
            meta = await self.backend.send(CHANNEL_E_TX_CHANNEL, data, tx_power=_tx_power)
            self.tx_packets += 1
            logger.info('Channel E TX: sent %d bytes via backend.send() (tx_power=%d)',
                       len(data), _tx_power)
        except Exception as e:
            self.tx_errors += 1
            logger.error('Channel E TX error: %s', e)


    def _rx_from_backend(self, payload, rssi=0, snr=0.0):
        """Callback invoked by WM1303Backend when a channel_e-frequency packet arrives."""
        self.packets_received += 1
        pkt_hash = hashlib.sha256(payload).hexdigest()[:12]
        logger.info("Channel E RX (via backend): %dB rssi=%d snr=%.1f hash=%s",
                    len(payload), rssi, snr, pkt_hash)
        try:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(
                    self._loop.create_task,
                    self.bridge.inject_packet(CHANNEL_E_NAME, payload, origin_channel='channel_e')
                )
                self.packets_injected += 1
            else:
                logger.warning("Channel E RX: no event loop stored, cannot inject")
        except Exception as e:
            self.packets_errors += 1
            logger.error("Channel E RX inject error: %s", e)


    async def _wait_for_bridge(self, timeout=30):
        """Wait for bridge_engine to be fully initialized."""
        for i in range(timeout * 10):
            if (self.bridge is not None
                    and hasattr(self.bridge, '_endpoint_handlers')
                    and self.bridge._endpoint_handlers is not None):
                return True
            await asyncio.sleep(0.1)
        return False

    async def run(self):
        """Start the UDP listener and inject packets into the bridge."""
        if not await self._wait_for_bridge():
            logger.error('Channel E: bridge engine not ready after timeout')
            return

        self.bridge._endpoint_handlers[CHANNEL_E_NAME] = self._tx_handler
        logger.info('Channel E: registered TX handler for %r (backend=%s)',
                    CHANNEL_E_NAME, type(self.backend).__name__ if self.backend else 'None')

        # Register RX callback with backend for channel_e frequency matching
        if self.backend is not None:
            self.backend._channel_e_rx_callback = self._rx_from_backend
            logger.info('Channel E: registered RX callback with backend for freq matching')

        loop = asyncio.get_event_loop()
        self._loop = loop  # store for cross-thread RX callback
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', self.udp_port))
        sock.setblocking(False)

        logger.info('Channel E: listening on UDP port %d', self.udp_port)
        self._running = True

        while self._running:
            try:
                data = await loop.sock_recv(sock, 4096)
                if not data or len(data) < 2:
                    continue

                self.packets_received += 1
                pkt_hash = hashlib.sha256(data).hexdigest()[:12]

                mc_hdr = data[0]
                mc_type = (mc_hdr >> 2) & 0x0F
                MC_TYPES = {
                    0: 'REQ', 1: 'RESP', 2: 'TXT', 3: 'ACK',
                    4: 'ADVERT', 5: 'GRP_TXT', 6: 'GRP_DATA',
                    7: 'ANON', 8: 'PATH', 9: 'TRACE',
                    10: 'MULTI', 11: 'CTRL', 15: 'RAW'
                }

                logger.info('Channel E RX: %dB %s hash=%s (Channel E native)',
                           len(data), MC_TYPES.get(mc_type, f'?{mc_type}'), pkt_hash)

                try:
                    await self.bridge.inject_packet(CHANNEL_E_NAME, data, origin_channel='channel_e')
                    self.packets_injected += 1
                except Exception as e:
                    self.packets_errors += 1
                    logger.error('Channel E inject error: %s', e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error('Channel E UDP error: %s', e)
                await asyncio.sleep(0.1)

        sock.close()

    def stop(self):
        self._running = False

    def get_stats(self) -> dict:
        return {
            'received': self.packets_received,
            'injected': self.packets_injected,
            'errors': self.packets_errors,
            'tx_packets': self.tx_packets,
            'tx_errors': self.tx_errors,
        }
