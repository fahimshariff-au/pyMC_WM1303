"""Packet Trace Collector for WM1303.

Provides an in-memory ring buffer that collects per-packet trace events,
grouped by packet hash.  Each trace captures the step-by-step journey
of a packet through the bridge engine (RX -> dedup -> forward -> TX).

When the same packet hash reappears after a long gap (>GAP_THRESHOLD),
a new trace entry is created to avoid misleading multi-minute total
durations caused by mesh-delayed duplicates.

Thread-safe: all mutations are protected by a lock.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

logger = logging.getLogger('PacketTrace')

_collector: TraceCollector | None = None

MAX_TRACES = 200
MAX_STEPS_PER_TRACE = 30
TRACE_TTL = 300       # seconds before a trace is considered stale for grouping
GAP_THRESHOLD = 30.0  # seconds — start new trace if gap since last event exceeds this


class TraceCollector:
    """Thread-safe in-memory ring buffer for packet traces."""

    def __init__(self, maxlen: int = MAX_TRACES):
        self._lock = threading.Lock()
        # OrderedDict keyed by lookup_key for fast lookup + insertion order.
        # lookup_key = pkt_hash or pkt_hash~N for duplicate arrivals.
        self._traces: OrderedDict[str, dict] = OrderedDict()
        self._maxlen = maxlen
        # Track the current active lookup key for each base pkt_hash
        self._active_key: dict[str, str] = {}  # pkt_hash -> current lookup_key
        self._seq: dict[str, int] = {}  # pkt_hash -> sequence counter

    def trace_event(self, pkt_hash: str, step_name: str,
                    channel: str = '', pkt_type: str = '',
                    detail: str = '', status: str = 'ok') -> None:
        """Record a trace step for the given packet hash.

        If a trace for this hash already exists (within TTL and without
        a large gap since the last event), the step is appended.
        Otherwise a new trace entry is created.
        """
        now_mono = time.monotonic()
        now_ts = time.time()
        iso_now = datetime.fromtimestamp(now_ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        with self._lock:
            # Find the current active trace for this base hash
            lookup_key = self._active_key.get(pkt_hash, pkt_hash)
            trace = self._traces.get(lookup_key)

            # Check if existing trace is stale (old packet with same hash)
            if trace and (now_mono - trace['_mono_first']) > TRACE_TTL:
                trace = None

            # Check for large gap since last event — start new trace
            if trace and (now_mono - trace['_mono_last']) > GAP_THRESHOLD:
                trace = None

            if trace is None:
                # Determine a unique lookup key
                seq = self._seq.get(pkt_hash, 0)
                if pkt_hash in self._active_key or pkt_hash in self._traces:
                    seq += 1
                self._seq[pkt_hash] = seq
                if seq == 0:
                    lookup_key = pkt_hash
                else:
                    lookup_key = f"{pkt_hash}~{seq}"
                self._active_key[pkt_hash] = lookup_key

                # New trace entry
                trace = {
                    'pkt_hash': pkt_hash,  # always the original hash for display
                    'first_seen': iso_now,
                    'channel': channel,
                    'type': pkt_type,
                    'status': 'ok',
                    'total_ms': 0.0,
                    'steps': [],
                    '_mono_first': now_mono,
                    '_mono_last': now_mono,
                    '_ts_first': now_ts,
                }
                # Evict oldest if at capacity
                if len(self._traces) >= self._maxlen:
                    evicted_key, _ = self._traces.popitem(last=False)
                    # Clean up _active_key if it points to the evicted key
                    for bh, ak in list(self._active_key.items()):
                        if ak == evicted_key:
                            del self._active_key[bh]
                            break
                self._traces[lookup_key] = trace
            else:
                # Move to end (most recent)
                self._traces.move_to_end(lookup_key)

            # Update last-event timestamp
            trace['_mono_last'] = now_mono

            # Update trace metadata
            if channel and not trace['channel']:
                trace['channel'] = channel
            if pkt_type and not trace['type']:
                trace['type'] = pkt_type

            # Compute elapsed from first step
            elapsed_ms = round((now_mono - trace['_mono_first']) * 1000, 1)

            # Add step (cap at MAX_STEPS_PER_TRACE)
            if len(trace['steps']) < MAX_STEPS_PER_TRACE:
                trace['steps'].append({
                    'name': step_name,
                    'time': iso_now,
                    'elapsed_ms': elapsed_ms,
                    'detail': detail,
                    'status': status,
                })

            # Update total_ms and overall status
            trace['total_ms'] = elapsed_ms

            # Track TX success/failure counts for status computation
            if 'tx_ok' not in trace:
                trace['tx_ok'] = 0
                trace['tx_fail'] = 0
                trace['has_critical'] = False

            # echo_dedup is normal healthy behavior — does NOT affect status
            if step_name == 'echo_dedup':
                pass  # status stays 'ok'
            elif step_name == 'dedup_drop':
                trace['status'] = 'dedup'
            elif step_name == 'filter_drop':
                trace['status'] = 'filtered'
            elif step_name == 'tx_send':
                if status == 'error':
                    trace['tx_fail'] += 1
                elif status == 'ok':
                    trace['tx_ok'] += 1
            elif status == 'error':
                trace['has_critical'] = True

            # Compute overall status from TX success/failure ratio
            # Only override if not already set to a specific category (dedup/filtered)
            if trace['status'] not in ('dedup', 'filtered'):
                if trace['has_critical'] or (trace['tx_fail'] > 0 and trace['tx_ok'] == 0):
                    trace['status'] = 'error'
                elif trace['tx_fail'] > 0 and trace['tx_ok'] > 0:
                    trace['status'] = 'partial'
                # else stays 'ok'

    def get_traces(self, limit: int = 50, status: str = '',
                   channel: str = '') -> list[dict]:
        """Return recent traces, newest first, with optional filters."""
        with self._lock:
            traces = list(self._traces.values())

        # Filter
        if status:
            traces = [t for t in traces if t.get('status') == status]
        if channel:
            traces = [t for t in traces if t.get('channel') == channel]

        # Reverse for newest-first, apply limit
        traces = list(reversed(traces))[:limit]

        # Strip internal fields before returning
        result = []
        for t in traces:
            entry = {
                'pkt_hash': t['pkt_hash'],
                'first_seen': t['first_seen'],
                'channel': t['channel'],
                'type': t['type'],
                'status': t['status'],
                'total_ms': t['total_ms'],
                'steps': t['steps'],
            }
            result.append(entry)
        return result

    def clear(self) -> None:
        """Clear all traces."""
        with self._lock:
            self._traces.clear()
            self._active_key.clear()
            self._seq.clear()


def get_collector() -> TraceCollector:
    """Get or create the module-level singleton TraceCollector."""
    global _collector
    if _collector is None:
        _collector = TraceCollector(maxlen=MAX_TRACES)
        logger.info('PacketTrace: collector initialized (maxlen=%d, gap_threshold=%.0fs)', MAX_TRACES, GAP_THRESHOLD)
    return _collector


def trace_event(pkt_hash: str, step_name: str, **kwargs) -> None:
    """Convenience wrapper: record a trace event on the global collector."""
    get_collector().trace_event(pkt_hash, step_name, **kwargs)


def get_traces(**kwargs) -> list[dict]:
    """Convenience wrapper: retrieve traces from the global collector."""
    return get_collector().get_traces(**kwargs)
