"""Centralized metrics retention for pyMC_Repeater.

Single source of truth for how long to keep metric/log rows in SQLite.
Runs a background thread that cleans all registered tables on a fixed cadence,
plus a weekly VACUUM to reclaim disk.
"""
import logging
import os
import sqlite3
import threading
import time
from typing import List, Tuple, Optional

logger = logging.getLogger("metrics_retention")

DEFAULT_RETENTION_DAYS = 8
DEFAULT_CLEANUP_INTERVAL_S = 3600        # once per hour
DEFAULT_VACUUM_INTERVAL_S = 7 * 86400    # weekly

# (db_filename, table_name, timestamp_column)
# db_filename is relative to DB_DIR
METRICS_TABLES: List[Tuple[str, str, str]] = [
    ("repeater.db",         "packets",                 "timestamp"),
    ("repeater.db",         "adverts",                 "timestamp"),
    ("repeater.db",         "crc_errors",              "timestamp"),
    ("repeater.db",         "noise_floor",             "timestamp"),
    ("repeater.db",         "dedup_events",            "ts"),
    ("repeater.db",         "noise_floor_history",     "timestamp"),
    ("repeater.db",         "cad_events",              "timestamp"),
    ("repeater.db",         "packet_activity",         "timestamp"),
    ("repeater.db",         "origin_channel_stats",    "timestamp"),
    ("repeater.db",         "channel_stats_history",   "timestamp"),
    ("repeater.db",         "packet_metrics",          "timestamp"),
    ("spectrum_history.db", "spectrum_scans",          "timestamp"),
]

DB_DIR = "/var/lib/pymc_repeater"


class MetricsRetention:
    def __init__(self,
                 retention_days: int = DEFAULT_RETENTION_DAYS,
                 cleanup_interval_s: int = DEFAULT_CLEANUP_INTERVAL_S,
                 vacuum_interval_s: int = DEFAULT_VACUUM_INTERVAL_S,
                 db_dir: str = DB_DIR):
        self.retention_days = retention_days
        self.cleanup_interval_s = cleanup_interval_s
        self.vacuum_interval_s = vacuum_interval_s
        self.db_dir = db_dir
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_vacuum = 0.0

    @property
    def retention_seconds(self) -> int:
        return self.retention_days * 86400

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="MetricsRetention")
        self._thread.start()
        logger.info("MetricsRetention started (retention=%dd, cleanup_every=%ds, vacuum_every=%ds)",
                    self.retention_days, self.cleanup_interval_s, self.vacuum_interval_s)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        # First run after 60s so service start is clean
        time.sleep(60)
        while self._running:
            try:
                self.cleanup_once()
                if time.time() - self._last_vacuum >= self.vacuum_interval_s:
                    self.vacuum_once()
                    self._last_vacuum = time.time()
            except Exception as e:
                logger.error("Retention cycle error: %s", e)
            # Sleep in 5s chunks to allow clean shutdown
            for _ in range(self.cleanup_interval_s // 5):
                if not self._running:
                    return
                time.sleep(5)

    def cleanup_once(self):
        cutoff = time.time() - self.retention_seconds
        total_deleted = 0
        by_db = {}
        for db_name, table, ts_col in METRICS_TABLES:
            by_db.setdefault(db_name, []).append((table, ts_col))
        for db_name, tables in by_db.items():
            db_path = os.path.join(self.db_dir, db_name)
            if not os.path.exists(db_path):
                continue
            try:
                with sqlite3.connect(db_path, timeout=10) as conn:
                    for table, ts_col in tables:
                        try:
                            exists = conn.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                                (table,)
                            ).fetchone()
                            if not exists:
                                continue
                            cur = conn.execute(
                                f"DELETE FROM {table} WHERE {ts_col} < ?",
                                (cutoff,)
                            )
                            if cur.rowcount > 0:
                                total_deleted += cur.rowcount
                                logger.info("MetricsRetention: %s.%s deleted %d rows",
                                            db_name, table, cur.rowcount)
                        except Exception as e:
                            logger.warning("MetricsRetention: %s.%s cleanup failed: %s",
                                           db_name, table, e)
                    conn.commit()
            except Exception as e:
                logger.warning("MetricsRetention: %s open failed: %s", db_name, e)
        logger.info("MetricsRetention cleanup pass complete, %d rows deleted", total_deleted)

    def vacuum_once(self):
        by_db = set(db_name for db_name, _, _ in METRICS_TABLES)
        for db_name in by_db:
            db_path = os.path.join(self.db_dir, db_name)
            if not os.path.exists(db_path):
                continue
            try:
                with sqlite3.connect(db_path, timeout=30) as conn:
                    conn.execute("VACUUM")
                logger.info("MetricsRetention: VACUUM %s complete", db_name)
            except Exception as e:
                logger.warning("MetricsRetention: VACUUM %s failed: %s", db_name, e)


_singleton: Optional[MetricsRetention] = None


def get_retention() -> MetricsRetention:
    global _singleton
    if _singleton is None:
        # Read config if available
        retention_days = DEFAULT_RETENTION_DAYS
        try:
            from repeater import config as _cfg
            cfg = getattr(_cfg, "CONFIG", None) or {}
            retention_days = int(
                cfg.get("storage", {}).get("retention", {}).get("metrics_days",
                                                               DEFAULT_RETENTION_DAYS)
            )
        except Exception:
            pass
        _singleton = MetricsRetention(retention_days=retention_days)
    return _singleton


def start():
    get_retention().start()
