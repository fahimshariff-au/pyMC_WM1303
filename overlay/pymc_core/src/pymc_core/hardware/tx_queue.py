"""TX Queue Manager for WM1303 RF0-TX Architecture (direct PULL_RESP).

Provides per-channel TX queues that serialize transmissions through
PULL_RESP to lora_pkt_fwd, which routes TX to RF0 via SKY66420 FEM.
RF0 handles TX (with PA) and RX. RF1 is RX-only.

Architecture:
  ChannelTXQueue  - Simple FIFO per channel (no burst loop)
  TXQueueManager  - Manages per-channel TX queues
  GlobalTXScheduler - Round-robin scheduler, sends one packet at a time
"""
from __future__ import annotations

import asyncio
import base64
import logging
import math
import random
import re
import time
from collections import deque
from typing import Any, Callable, Optional

logger = logging.getLogger("TXQueue")

# Maximum channels supported
MAX_CHANNELS = 4

# LBT RSSI rolling buffer size
LBT_RSSI_BUFFER_SIZE = 20


def _bw_hz_to_str(bw_hz: int) -> str:
    """Convert bandwidth in Hz to string for datr field."""
    mapping = {62500: "62", 125000: "125", 250000: "250", 500000: "500"}
    return mapping.get(int(bw_hz), "125")


def _datr_str(sf: int, bw_hz: int) -> str:
    """Build datr string like SF8BW125."""
    return f"SF{sf}BW{_bw_hz_to_str(bw_hz)}"


def estimate_lora_airtime_ms(
    payload_size: int,
    sf: int = 8,
    bw_hz: int = 125000,
    cr: int = 5,
    preamble: int = 17,
    explicit_header: bool = True,
    crc_on: bool = True,
    low_dr_optimize: bool | None = None,
) -> float:
    """Estimate LoRa packet airtime in milliseconds.

    Uses the standard Semtech airtime formula for LoRa modulation.

    Args:
        payload_size: Payload size in bytes.
        sf: Spreading factor (7-12).
        bw_hz: Bandwidth in Hz (e.g. 125000, 62500).
        cr: Coding rate denominator (5-8 for 4/5 to 4/8).
        preamble: Preamble symbol count.
        explicit_header: True for explicit header mode.
        crc_on: True if CRC is enabled.
        low_dr_optimize: Low data-rate optimization; auto-detected if None.

    Returns:
        Estimated airtime in milliseconds.
    """
    if low_dr_optimize is None:
        # Auto-enable for SF11/SF12 with BW125 or lower
        low_dr_optimize = (sf >= 11 and bw_hz <= 125000)

    t_sym_ms = (2 ** sf) / (bw_hz / 1000.0)  # symbol duration in ms
    t_preamble_ms = (preamble + 4.25) * t_sym_ms

    de = 1 if low_dr_optimize else 0
    ih = 0 if explicit_header else 1
    crc_val = 1 if crc_on else 0

    numerator = 8 * payload_size - 4 * sf + 28 + 16 * crc_val - 20 * ih
    denominator = 4 * (sf - 2 * de)
    n_payload = 8 + max(0, math.ceil(numerator / denominator)) * (cr if cr <= 4 else cr)

    t_payload_ms = n_payload * t_sym_ms
    return t_preamble_ms + t_payload_ms



class ChannelTXQueue:
    """Simple FIFO TX queue for a single channel.

    Stores packets with futures for result notification.
    Does NOT have its own processing loop - the GlobalTXScheduler
    pulls packets from all queues in round-robin order.

    Overflow policy: when full, DROP OLDEST packet to make room for new one.
    This ensures the most recent packets (which are more relevant) are always queued.
    """

    def __init__(self, channel_id: str, freq_hz: int, bw_khz: float,
                 sf: int, cr: int, preamble: int = 17,
                 tx_power: int = 14, queue_size: int = 15,
                 ttl_seconds: float = 30.0):
        self.channel_id = channel_id
        self.freq_hz = freq_hz
        self.bw_khz = bw_khz
        self.sf = sf
        self.cr = cr
        self.preamble = preamble
        self.tx_power = tx_power
        self.ttl_seconds = ttl_seconds
        self._queue_size = queue_size
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)

        # Stats
        self.stats = {
            "pending": 0,
            "total_sent": 0,
            "total_failed": 0,
            "dropped_ttl": 0,
            "dropped_overflow": 0,
            "dropped_stale": 0,
            "last_tx_time": None,
            "avg_tx_time_ms": 0,
            "avg_send_ms": 0,
            "avg_airtime_ms": 0,
            "avg_wait_ms": 0,
            "last_send_ms": 0,
            "last_airtime_ms": 0,
            "last_wait_ms": 0,
            "total_airtime_ms": 0,
            "total_send_ms": 0,
            "enabled": True,
            "lbt_blocked": 0,
            "lbt_passed": 0,
            "lbt_skipped": 0,
            "lbt_force_sent": 0,
            "lbt_last_blocked_at": None,
            "lbt_last_rssi": None,
            "lbt_last_threshold": None,
            "cad_clear": 0,
            "cad_detected": 0,
            "cad_timeout": 0,
            "cad_last_result": None,
            # HW CAD (done by HAL C code before every TX, reported via TX_ACK)
            "cad_hw_clear": 0,
            "cad_hw_detected": 0,
            # SW CAD (optional SX1261-based CAD in Python LBT path)
            "cad_sw_clear": 0,
            "cad_sw_detected": 0,
            # LBT RSSI noise floor stats (rolling buffer)
            "noise_floor_lbt_avg": None,
            "noise_floor_lbt_min": None,
            "noise_floor_lbt_max": None,
            "noise_floor_lbt_samples": 0,
        }
        self._tx_times: list[float] = []
        self._send_times: list[float] = []
        self._airtime_times: list[float] = []
        self._wait_times: list[float] = []

        # LBT RSSI rolling buffer for noise floor estimation
        self._lbt_rssi_buffer: deque = deque(maxlen=LBT_RSSI_BUFFER_SIZE)

    async def enqueue(self, payload: bytes, tx_power: int = None) -> dict:
        """Enqueue a TX request and wait for the GlobalTXScheduler to send it.

        Overflow policy: when full, drop the OLDEST packet to make room.
        New packets are more important than stale ones.

        Returns:
            dict with {"ok": True/False, ...}
        """
        if tx_power is None:
            tx_power = self.tx_power
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        request = {
            "payload": payload,
            "tx_power": tx_power,
            "future": future,
            "enqueue_time": time.time(),
        }
        try:
            self.queue.put_nowait(request)
            self.stats["pending"] = self.queue.qsize()
            logger.info("ChannelTXQueue[%s]: enqueued %d bytes (pending=%d)",
                       self.channel_id, len(payload), self.queue.qsize())
        except asyncio.QueueFull:
            # Drop OLDEST packet to make room for the new one
            try:
                old_req = self.queue.get_nowait()
                old_future = old_req.get("future")
                if old_future and not old_future.done():
                    old_future.set_result({"ok": False, "error": "dropped_overflow"})
                self.stats["dropped_overflow"] += 1
                old_age = time.time() - old_req.get("enqueue_time", 0)
                logger.warning(
                    "ChannelTXQueue[%s]: queue full (%d/%d), dropped OLDEST packet "
                    "(age=%.1fs, %d bytes) to make room for new one",
                    self.channel_id, self._queue_size, self._queue_size,
                    old_age, len(old_req.get("payload", b"")))
            except asyncio.QueueEmpty:
                pass  # shouldn't happen but be safe
            # Now enqueue the new packet
            try:
                self.queue.put_nowait(request)
                self.stats["pending"] = self.queue.qsize()
                logger.info("ChannelTXQueue[%s]: enqueued %d bytes after overflow drop (pending=%d)",
                           self.channel_id, len(payload), self.queue.qsize())
            except asyncio.QueueFull:
                # Still full somehow - reject
                logger.error("ChannelTXQueue[%s]: queue still full after drop, rejecting packet",
                            self.channel_id)
                self.stats["total_failed"] += 1
                return {"ok": False, "error": "queue_full"}

        try:
            result = await asyncio.wait_for(future, timeout=15.0)
            return result
        except asyncio.TimeoutError:
            logger.warning("ChannelTXQueue[%s]: TX wait timeout",
                          self.channel_id)
            self.stats["total_failed"] += 1
            return {"ok": False, "error": "timeout"}

    def dequeue_nowait(self):
        """Non-blocking dequeue. Returns request dict or raises asyncio.QueueEmpty."""
        request = self.queue.get_nowait()  # raises QueueEmpty if empty
        self.stats["pending"] = self.queue.qsize()
        return request

    def build_txpk(self, payload: bytes, tx_power: int = None) -> dict:
        """Build txpk JSON object for PULL_RESP.

        The lora_pkt_fwd HAL uses the freq/datr to select the right
        SX1250 radio. RF1 has tx_enable=true, so all TX
        goes through RF1/SX1250_1. RF0 is RX + Clock.
        """
        if tx_power is None:
            tx_power = self.tx_power
        freq_mhz = self.freq_hz / 1e6
        cr_str = f"4/{self.cr}"
        datr = _datr_str(self.sf, int(self.bw_khz * 1000))
        payload_b64 = base64.b64encode(payload).decode()
        return {
            "imme": True,
            "freq": round(freq_mhz, 6),
            "rfch": 0,  # RF0 = TX chain (SKY66420 FEM with PA)
            "powe": tx_power,
            "modu": "LORA",
            "datr": datr,
            "codr": cr_str,
            "ipol": False,
            "size": len(payload),
            "data": payload_b64,
            "prea": self.preamble,
            "ncrc": False,
        }

    def record_tx_time(self, tx_time_ms: float) -> None:
        """Record TX time for rolling average (legacy/compat)."""
        self._tx_times.append(tx_time_ms)
        if len(self._tx_times) > 50:
            self._tx_times = self._tx_times[-50:]
        self.stats["avg_tx_time_ms"] = round(
            sum(self._tx_times) / len(self._tx_times), 1)

    def record_tx_timing(self, send_ms: float, airtime_ms: float, wait_ms: float) -> None:
        """Record detailed TX timing metrics (send, airtime, queue wait)."""
        # Send time (wall-clock UDP send)
        self._send_times.append(send_ms)
        if len(self._send_times) > 50:
            self._send_times = self._send_times[-50:]
        self.stats["avg_send_ms"] = round(
            sum(self._send_times) / len(self._send_times), 1)
        self.stats["last_send_ms"] = round(send_ms, 1)

        # Airtime (calculated LoRa time-on-air)
        self._airtime_times.append(airtime_ms)
        if len(self._airtime_times) > 50:
            self._airtime_times = self._airtime_times[-50:]
        self.stats["avg_airtime_ms"] = round(
            sum(self._airtime_times) / len(self._airtime_times), 1)
        self.stats["last_airtime_ms"] = round(airtime_ms, 1)
        self.stats["total_airtime_ms"] = round(
            self.stats.get("total_airtime_ms", 0) + airtime_ms, 1)

        # Queue wait time
        self._wait_times.append(wait_ms)
        if len(self._wait_times) > 50:
            self._wait_times = self._wait_times[-50:]
        self.stats["avg_wait_ms"] = round(
            sum(self._wait_times) / len(self._wait_times), 1)
        self.stats["last_wait_ms"] = round(wait_ms, 1)

        # Total send time
        self.stats["total_send_ms"] = round(
            self.stats.get("total_send_ms", 0) + send_ms, 1)

    def record_lbt_rssi(self, rssi: float) -> None:
        """Record an LBT RSSI measurement in the rolling buffer.

        Called after every LBT check (pass or block) to build a
        noise floor estimate from real pre-TX RSSI measurements.
        """
        if rssi is None:
            return
        self._lbt_rssi_buffer.append(rssi)
        n = len(self._lbt_rssi_buffer)
        self.stats["lbt_last_rssi"] = round(rssi, 1)
        self.stats["noise_floor_lbt_samples"] = n
        if n > 0:
            vals = list(self._lbt_rssi_buffer)
            self.stats["noise_floor_lbt_avg"] = round(sum(vals) / n, 1)
            self.stats["noise_floor_lbt_min"] = round(min(vals), 1)
            self.stats["noise_floor_lbt_max"] = round(max(vals), 1)

    def get_status(self) -> dict:
        """Return queue status and stats."""
        self.stats["pending"] = self.queue.qsize()
        return {
            "channel_id": self.channel_id,
            "freq_hz": self.freq_hz,
            "bw_khz": self.bw_khz,
            "sf": self.sf,
            "cr": self.cr,
            "preamble": self.preamble,
            "queue_size": self._queue_size,
            "ttl_seconds": self.ttl_seconds,
            **self.stats,
        }


class TXQueueManager:
    """Manages up to 4 per-channel TX queues.

    Queues are simple FIFOs. The GlobalTXScheduler handles
    actual transmission in round-robin order.
    """

    def __init__(self):
        self.queues: dict[str, ChannelTXQueue] = {}

    def add_channel(self, channel_id: str, freq_hz: int,
                    bw_khz: float = 125.0, sf: int = 8,
                    cr: int = 5, preamble: int = 17,
                    tx_power: int = 14,
                    ttl_seconds: float = 30.0) -> None:
        """Add a channel TX queue."""
        if len(self.queues) >= MAX_CHANNELS:
            raise ValueError(f"Maximum {MAX_CHANNELS} TX queues supported")
        self.queues[channel_id] = ChannelTXQueue(
            channel_id=channel_id,
            freq_hz=freq_hz,
            bw_khz=bw_khz,
            sf=sf,
            cr=cr,
            preamble=preamble,
            tx_power=tx_power,
            ttl_seconds=ttl_seconds,
        )
        logger.info("TXQueueManager: added queue for %s "
                   "(freq=%d, SF%d, BW%.0fkHz, CR4/%d, TX%ddBm, qsize=%d, ttl=%.0fs)",
                   channel_id, freq_hz, sf, bw_khz, cr, tx_power, 15, ttl_seconds)

    async def enqueue(self, channel_id: str, payload: bytes,
                      tx_power: int = None) -> dict:
        """Enqueue a TX packet to the appropriate channel queue."""
        queue = self.queues.get(channel_id)
        if not queue:
            return {"ok": False, "error": f"unknown channel: {channel_id}"}
        return await queue.enqueue(payload, tx_power)

    def stop_all(self) -> None:
        """Stop all TX queue processing (no-op since queues are passive FIFOs)."""
        logger.info("TXQueueManager: all queues stopped")

    def record_hw_cad_result(self, channel_id: str, cad_result: dict) -> None:
        """Increment HW CAD counters from a post-TX_ACK hardware CAD result.

        The WM1303 HAL C code performs HW CAD before every TX and reports the
        outcome in the post-TX TX_ACK packet. This method wires those results
        into the per-channel queue stats so the UI and cad_events persistence
        can see HW CAD activity even when SW LBT/CAD is disabled.

        Args:
            channel_id: per-channel queue identifier.
            cad_result: dict with keys 'enabled' (bool), 'detected' (bool),
                optional 'reason' (str).
        """
        if not cad_result or not cad_result.get("enabled"):
            return
        q = self.queues.get(channel_id)
        if q is None:
            return
        if cad_result.get("detected"):
            q.stats["cad_detected"] = q.stats.get("cad_detected", 0) + 1
            q.stats["cad_hw_detected"] = q.stats.get("cad_hw_detected", 0) + 1
        else:
            q.stats["cad_clear"] = q.stats.get("cad_clear", 0) + 1
            q.stats["cad_hw_clear"] = q.stats.get("cad_hw_clear", 0) + 1
        q.stats["cad_last_result"] = cad_result.get("reason", "hw")

    def get_status(self) -> dict:
        """Return status of all TX queues."""
        return {
            channel_id: queue.get_status()
            for channel_id, queue in self.queues.items()
        }


class GlobalTXScheduler:
    """Round-robin TX scheduler across all channel queues.

    Sends one packet at a time through a single TX radio,
    preventing collisions. No burst cycle, no collect window.
    Packets are sent within milliseconds of being enqueued.

    LBT (Listen-Before-Talk) is non-blocking: when a channel is LBT-blocked,
    it is skipped and other channels can continue transmitting. The blocked
    channel is retried on the next round-robin pass after a delay.
    """

    # LBT retry delays (seconds): attempt 0 is immediate, then 0.5s, 1.0s, 1.5s
    LBT_RETRY_DELAYS = [0, 0.5, 1.0, 1.5]
    # After all retries exhausted, wait this long before force-sending
    LBT_FORCE_DELAY = 2.0

    def __init__(self, send_func: Callable, queues: dict[str, ChannelTXQueue],
                 post_tx_callback: Callable = None,
                 lbt_check: Callable = None,
                 tx_hold_getter: Callable = None):
        """
        Args:
            send_func: async callable(txpk_dict, channel_id) -> {"ok": bool, ...}
            queues: dict of channel_id -> ChannelTXQueue
            post_tx_callback: optional callable(channel_id, send_ms, airtime_ms, wait_ms, payload_len)
                              called after each successful TX for stats tracking
            tx_hold_getter: optional callable() -> float (monotonic timestamp until TX is held)
                            When time.monotonic() < tx_hold_getter(), TX is delayed.
                            Used to batch-collect RX packets before forwarding.
        """
        self._send_func = send_func
        self._queues = queues
        self._post_tx_callback = post_tx_callback
        self._lbt_check = lbt_check
        self._tx_hold_getter = tx_hold_getter
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._packets_scheduled = 0
        self._round_index = 0  # Rotating start index for fair round-robin

        # Random TX delay for collision avoidance between repeaters.
        # With mandatory CAD before every TX, this delay is no longer needed
        # for collision avoidance. Default: 0 (disabled).
        self._tx_delay_factor: float = 0.0

        # Per-channel LBT blocked state for non-blocking retry.
        # Key: channel_id, Value: dict with:
        #   request: the original dequeued request dict
        #   txpk: pre-built txpk dict
        #   queue_wait_ms: queue wait time measured at first dequeue
        #   attempt: current retry attempt index (0-based into LBT_RETRY_DELAYS)
        #   retry_after: monotonic timestamp when this channel can be retried
        #   force_send: bool, True if all retries exhausted and waiting for force delay
        #   last_lbt_result: last LBT check result for logging
        self._blocked: dict[str, dict] = {}

    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("GlobalTXScheduler: started (queues=%s)",
                   list(self._queues.keys()))

    async def stop(self):
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("GlobalTXScheduler: stopped (total_scheduled=%d)",
                   self._packets_scheduled)

    def _record_lbt_cad_stats(self, queue: ChannelTXQueue, lbt_result: dict,
                               passed: bool) -> None:
        """Record LBT and CAD statistics from an LBT check result."""
        # Record LBT RSSI in rolling buffer
        _lbt_rssi = lbt_result.get("rssi")
        if _lbt_rssi is not None:
            queue.record_lbt_rssi(_lbt_rssi)

        if passed:
            queue.stats["lbt_passed"] += 1
        else:
            queue.stats["lbt_blocked"] += 1
            queue.stats["lbt_last_blocked_at"] = time.time()

        queue.stats["lbt_last_threshold"] = lbt_result.get("threshold")

        # Track CAD stats from LBT result
        _cad = lbt_result.get('cad_result')
        if _cad is not None:
            if _cad.get('detected', False):
                queue.stats["cad_detected"] += 1
            else:
                queue.stats["cad_clear"] += 1
            queue.stats["cad_last_result"] = _cad.get('reason', 'unknown')

    async def _do_send(self, channel_id: str, queue: ChannelTXQueue,
                       request: dict, txpk: dict, queue_wait_ms: float) -> None:
        """Execute the actual TX send and handle result/stats/future."""
        # Airtime-proportional random TX delay (MeshCore/pymc style)
        airtime_est_ms = estimate_lora_airtime_ms(
            payload_size=len(request["payload"]),
            sf=queue.sf,
            bw_hz=int(queue.bw_khz * 1000),
            cr=queue.cr,
            preamble=queue.preamble,
        )
        tx_delay_factor = max(0.0, float(self._tx_delay_factor))
        if tx_delay_factor > 0:
            base_delay_ms = (airtime_est_ms * 52.0 / 50.0) / 2.0
            delay_ms = random.uniform(0.0, 5.0) * base_delay_ms * tx_delay_factor
            if delay_ms > 1:
                logger.info(
                    "GlobalTXScheduler: airtime TX delay %.0fms on %s (factor=%.3f, airtime_est=%.1fms)",
                    delay_ms, channel_id, tx_delay_factor, airtime_est_ms,
                )
                await asyncio.sleep(delay_ms / 1000.0)

        # TX Hold check: if RX batching window active, wait before TX
        if self._tx_hold_getter:
            _hold_until = self._tx_hold_getter()
            _hold_remaining = _hold_until - time.monotonic()
            if _hold_remaining > 0.01:
                logger.info("GlobalTXScheduler: TX hold active on %s, "
                           "waiting %.1fs (batch window)",
                           channel_id, _hold_remaining)
                await asyncio.sleep(_hold_remaining)

        # Send via the backend's PULL_RESP sender
        try:
            result = await self._send_func(txpk, channel_id)
        except Exception as e:
            logger.error("GlobalTXScheduler: send error on %s: %s",
                        channel_id, e, exc_info=True)
            result = {"ok": False, "error": str(e)}

        # FIX Bug1: Use send_ms from result dict (UDP send only)
        # not wall-clock around send_func (includes airtime wait)
        send_ms = result.get("send_ms", 0)
        airtime_ms = result.get("airtime_ms", 0)

        if result.get("ok"):
            queue.stats["total_sent"] += 1
            queue.stats["last_tx_time"] = time.time()
            queue.record_tx_time(send_ms)
            queue.record_tx_timing(send_ms, airtime_ms, queue_wait_ms)
            result["send_ms"] = send_ms
            result["airtime_ms"] = airtime_ms
            result["queue_wait_ms"] = queue_wait_ms
            logger.info("GlobalTXScheduler: TX OK on %s (%d bytes, "
                       "freq=%.3f, datr=%s, send=%.1fms, "
                       "airtime=%.1fms, queue_wait=%.1fms)",
                       channel_id, len(request["payload"]),
                       txpk.get("freq", 0), txpk.get("datr", ""),
                       send_ms, airtime_ms, queue_wait_ms)
            # Notify backend for per-channel TX stats tracking
            if self._post_tx_callback:
                try:
                    self._post_tx_callback(
                        channel_id, send_ms, airtime_ms,
                        queue_wait_ms, len(request["payload"]))
                except Exception as _cb_err:
                    logger.debug("GlobalTXScheduler: post_tx_callback error: %s", _cb_err)
        else:
            queue.stats["total_failed"] += 1
            logger.warning("GlobalTXScheduler: TX FAIL on %s: %s "
                          "(send=%.1fms, queue_wait=%.1fms)",
                          channel_id, result.get("error", "unknown"),
                          send_ms, queue_wait_ms)

        # Resolve the caller's future
        future = request.get("future")
        if future and not future.done():
            future.set_result(result)

        self._packets_scheduled += 1
        # Shared RF-chain guard: all channels transmit via the same physical
        # rf_chain 0.  The SX1302 can only transmit one packet at a time —
        # calling lgw_send() while a previous TX is still in progress will
        # OVERWRITE the TX buffer, silently killing the first packet.
        # We must wait at least the full estimated airtime of the packet we
        # just sent, plus a safety margin, before sending the next one.
        # The margin accounts for:
        #   - JIT thread processing delay (~100ms from Python lgw_send to C pickup)
        #   - CAD scan overhead (~50ms when CAD is enabled)
        #   - SX1302 TX scheduling latency (~50ms)
        #   - Safety buffer
        _rf_guard_margin_ms = 150.0  # margin to cover JIT + CAD + scheduling (was 250)
        _shared_rf_guard_ms = airtime_est_ms + _rf_guard_margin_ms
        logger.info("GlobalTXScheduler: rf-chain guard after %s, %.1fms "
                    "(airtime_est=%.1fms + %.0fms margin)",
                    channel_id, _shared_rf_guard_ms, airtime_est_ms, _rf_guard_margin_ms)
        await asyncio.sleep(_shared_rf_guard_ms / 1000.0)

    async def _scheduler_loop(self):
        """Round-robin poll all TX queues, send one packet at a time.

        Uses a rotating start index so each channel gets equal priority
        over time. Each round starts from the next channel in sequence:
        Round 1: a -> b -> c, Round 2: b -> c -> a, Round 3: c -> a -> b, etc.

        LBT is non-blocking: when a channel is LBT-blocked, it is skipped
        and a retry_after timestamp is set. Other channels continue transmitting.
        On the next pass, the blocked channel is retried if enough time has passed.
        After max retries, the packet is force-sent after a short delay.
        """
        queue_list = list(self._queues.items())  # [(channel_id, ChannelTXQueue), ...]
        n_queues = len(queue_list)
        logger.info("GlobalTXScheduler: scheduler loop running with %d queues",
                   n_queues)

        while self._running:
            sent_any = False
            # Rotate start position for fair scheduling
            start = self._round_index % n_queues
            rotated = queue_list[start:] + queue_list[:start]
            for channel_id, queue in rotated:

                # --- Check for a previously LBT-blocked request first ---
                blocked = self._blocked.get(channel_id)
                if blocked:
                    now_mono = time.monotonic()
                    if now_mono < blocked["retry_after"]:
                        # Not yet time to retry this channel - skip it
                        continue

                    request = blocked["request"]
                    txpk = blocked["txpk"]
                    queue_wait_ms = blocked["queue_wait_ms"]

                    # Check if the caller already timed out while we were waiting
                    _future = request.get("future")
                    if _future and _future.done():
                        _stale_age = time.time() - request["enqueue_time"]
                        queue.stats["dropped_stale"] += 1
                        logger.info("GlobalTXScheduler: dropping stale blocked packet on %s "
                                   "(age=%.1fs, future already resolved)",
                                   channel_id, _stale_age)
                        del self._blocked[channel_id]
                        continue

                    # TTL re-check
                    age = time.time() - request["enqueue_time"]
                    if age > queue.ttl_seconds:
                        logger.warning("GlobalTXScheduler: blocked packet expired on %s "
                                      "(age=%.1fs, TTL=%.0fs)",
                                      channel_id, age, queue.ttl_seconds)
                        queue.stats["dropped_ttl"] += 1
                        future = request.get("future")
                        if future and not future.done():
                            future.set_result({"ok": False, "error": "ttl_expired",
                                               "age": round(age, 1)})
                        del self._blocked[channel_id]
                        continue

                    if blocked["force_send"]:
                        # All retries exhausted, force delay has elapsed -> FORCE SEND
                        queue.stats["lbt_force_sent"] += 1
                        last_lbt = blocked.get("last_lbt_result", {})
                        logger.warning("GlobalTXScheduler: FORCE SENDING packet on %s "
                                      "despite pre-TX block (rssi=%.1f, threshold=%.1f)",
                                      channel_id,
                                      last_lbt.get("rssi", 0),
                                      last_lbt.get("threshold", 0))
                        del self._blocked[channel_id]
                        await self._do_send(channel_id, queue, request, txpk, queue_wait_ms)
                        sent_any = True
                        continue

                    # Retry pre-TX check
                    attempt = blocked["attempt"]
                    lbt_result = self._lbt_check(channel_id, queue.freq_hz, queue.sf)

                    # Record LBT RSSI
                    _lbt_rssi = lbt_result.get("rssi")
                    if _lbt_rssi is not None:
                        queue.record_lbt_rssi(_lbt_rssi)

                    if lbt_result.get("allow", True):
                        # Pre-TX check passed on retry!
                        self._record_lbt_cad_stats(queue, lbt_result, passed=True)
                        _reason = lbt_result.get("reason", "clear")
                        logger.info("GlobalTXScheduler: pre-TX PASSED on %s "
                                   "after %d attempts (reason=%s, rssi=%s, threshold=%s)",
                                   channel_id, attempt + 1, _reason,
                                   lbt_result.get("rssi", "n/a"),
                                   lbt_result.get("threshold", "n/a"))
                        del self._blocked[channel_id]
                        await self._do_send(channel_id, queue, request, txpk, queue_wait_ms)
                        sent_any = True
                        continue

                    # Still blocked - advance to next retry or force-send
                    next_attempt = attempt + 1
                    if next_attempt < len(self.LBT_RETRY_DELAYS):
                        # Schedule next retry
                        delay = self.LBT_RETRY_DELAYS[next_attempt]
                        blocked["attempt"] = next_attempt
                        blocked["retry_after"] = time.monotonic() + delay
                        blocked["last_lbt_result"] = lbt_result
                        logger.info("GlobalTXScheduler: pre-TX retry %d/%d on %s, "
                                   "will retry in %.1fs (reason=%s, rssi=%s, threshold=%s)",
                                   next_attempt + 1, len(self.LBT_RETRY_DELAYS),
                                   channel_id, delay,
                                   lbt_result.get("reason", "unknown"),
                                   lbt_result.get("rssi", "n/a"),
                                   lbt_result.get("threshold", "n/a"))
                    else:
                        # All retries exhausted - schedule force-send after delay
                        self._record_lbt_cad_stats(queue, lbt_result, passed=False)
                        blocked["force_send"] = True
                        blocked["retry_after"] = time.monotonic() + self.LBT_FORCE_DELAY
                        blocked["last_lbt_result"] = lbt_result
                        logger.warning("GlobalTXScheduler: pre-TX BLOCKED on %s after %d "
                                      "attempts - will FORCE SEND in %.1fs "
                                      "(reason=%s, rssi=%s, threshold=%s, freq=%.3fMHz)",
                                      channel_id, len(self.LBT_RETRY_DELAYS),
                                      self.LBT_FORCE_DELAY,
                                      lbt_result.get("reason", "unknown"),
                                      lbt_result.get("rssi", "n/a"),
                                      lbt_result.get("threshold", "n/a"),
                                      queue.freq_hz / 1e6)
                    # Skip this channel for now, move to next
                    continue

                # --- No blocked request: try to dequeue a new packet ---
                try:
                    request = queue.dequeue_nowait()
                except asyncio.QueueEmpty:
                    continue

                # Stale-future check: if the caller already timed out
                # (asyncio.wait_for in enqueue()), skip this packet.
                _future = request.get("future")
                if _future and _future.done():
                    _stale_age = time.time() - request["enqueue_time"]
                    queue.stats["dropped_stale"] += 1
                    logger.info("GlobalTXScheduler: skipping stale packet on %s "
                               "(age=%.1fs, future already resolved)",
                               channel_id, _stale_age)
                    continue

                # TTL check
                age = time.time() - request["enqueue_time"]
                if age > queue.ttl_seconds:
                    logger.warning("GlobalTXScheduler: packet expired on %s "
                                  "(age=%.1fs, TTL=%.0fs)",
                                  channel_id, age, queue.ttl_seconds)
                    queue.stats["dropped_ttl"] += 1
                    future = request.get("future")
                    if future and not future.done():
                        future.set_result({"ok": False, "error": "ttl_expired",
                                           "age": round(age, 1)})
                    continue

                # Build txpk using the queue's channel config
                txpk = queue.build_txpk(
                    request["payload"],
                    request.get("tx_power", queue.tx_power))

                # Measure queue wait BEFORE calling send_func
                queue_wait_ms = (time.time() - request["enqueue_time"]) * 1000

                # --- Pre-TX check (CAD and/or LBT, independently configurable) ---
                if self._lbt_check:
                    lbt_result = self._lbt_check(channel_id, queue.freq_hz, queue.sf)
                    _cad_on = lbt_result.get("cad_enabled", False)
                    _lbt_on = lbt_result.get("lbt_enabled", False)
                    if not _cad_on and not _lbt_on:
                        # Both checks disabled on this channel - send immediately
                        queue.stats["lbt_skipped"] += 1
                    else:
                        # At least one check is active
                        # Record RSSI in rolling buffer (if available)
                        _lbt_rssi = lbt_result.get("rssi")
                        if _lbt_rssi is not None:
                            queue.record_lbt_rssi(_lbt_rssi)

                        if lbt_result.get("allow", True):
                            # Pre-TX check passed
                            self._record_lbt_cad_stats(queue, lbt_result, passed=True)
                        else:
                            # Blocked (by CAD or LBT) - store as blocked
                            # and skip to next channel (non-blocking)
                            next_attempt = 1
                            if next_attempt < len(self.LBT_RETRY_DELAYS):
                                delay = self.LBT_RETRY_DELAYS[next_attempt]
                            else:
                                delay = self.LBT_FORCE_DELAY
                            self._blocked[channel_id] = {
                                "request": request,
                                "txpk": txpk,
                                "queue_wait_ms": queue_wait_ms,
                                "attempt": next_attempt,
                                "retry_after": time.monotonic() + delay,
                                "force_send": next_attempt >= len(self.LBT_RETRY_DELAYS),
                                "last_lbt_result": lbt_result,
                            }
                            _reason = lbt_result.get("reason", "unknown")
                            logger.info("GlobalTXScheduler: pre-TX blocked on %s "
                                       "(reason=%s, attempt 1/%d, retry in %.1fs, "
                                       "rssi=%s, threshold=%s)",
                                       channel_id, _reason,
                                       len(self.LBT_RETRY_DELAYS), delay,
                                       lbt_result.get("rssi", "n/a"),
                                       lbt_result.get("threshold", "n/a"))
                            continue  # Non-blocking: move to next channel

                # --- Send the packet ---
                await self._do_send(channel_id, queue, request, txpk, queue_wait_ms)
                sent_any = True

            if sent_any:
                # Rotate start position for next round
                self._round_index += 1
            else:
                # No packets in any queue - brief sleep to avoid busy-wait
                await asyncio.sleep(0.001)  # 1ms poll interval (was 10ms)

        logger.info("GlobalTXScheduler: loop exited")

    def get_stats(self) -> dict:
        """Return scheduler stats."""
        return {
            "running": self._running,
            "packets_scheduled": self._packets_scheduled,
            "round_index": self._round_index,
            "queues": list(self._queues.keys()),
            "lbt_blocked_channels": list(self._blocked.keys()),
        }
# Legacy TXQueue compatibility (deprecated)
# ======================================================================

class TXQueue:
    """DEPRECATED: Legacy Channel E TX Queue.

    This class is kept for backward compatibility only.
    New code should use TXQueueManager + ChannelTXQueue + GlobalTXScheduler.
    """

    def __init__(self, radio=None, inter_packet_delay_ms: float = 20.0,
                 max_queue_size: int = 100):
        logger.warning("TXQueue: DEPRECATED - use TXQueueManager instead")
        self._running = False
        self._task = None
        self.tx_count = 0
        self.tx_errors = 0
        self.tx_queue_drops = 0
        self.last_tx_time = 0
        self.avg_tx_time_ms = 0

    async def start(self) -> None:
        logger.warning("TXQueue.start(): DEPRECATED - no-op")
        self._running = True

    def stop(self) -> None:
        self._running = False

    async def enqueue(self, **kwargs) -> dict:
        logger.warning("TXQueue.enqueue(): DEPRECATED - returning error")
        return {"ok": False, "error": "deprecated_sx1261_queue"}

    def get_stats(self) -> dict:
        return {
            "deprecated": True,
            "tx_count": self.tx_count,
            "tx_errors": self.tx_errors,
            "running": self._running,
        }

    @property
    def pending(self) -> int:
        return 0
