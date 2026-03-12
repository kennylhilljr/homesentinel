"""
Speed Test Service for HomeSentinel.

2026-03-11: Runs Ookla speedtest on the Chester 5G router via SSH.
Chester firmware 2.4.0+ includes `speedtest` (Ookla) built-in.
SSH into the router and run `speedtest --format=json` for accurate WAN speed.
Also captures Chester cellular signal data at time of test for correlation.
"""

import json
import logging
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpeedTestService:
    """SSHs into Chester router to run Ookla speedtest and stores results."""

    def __init__(self, db, chester_service=None, chester_client=None):
        self.db = db
        self.chester_service = chester_service
        self.chester_client = chester_client

    def _get_ssh_creds(self) -> Dict[str, str]:
        """Get Chester SSH credentials for speedtest.

        2026-03-11: Chester HTTP API uses username 'admin', but SSH requires 'root'.
        Always use 'root' for SSH regardless of chester_client.username.
        Password is the same for both.
        """
        if self.chester_client:
            return {
                "host": self.chester_client.host or "192.168.12.1",
                "username": "root",  # SSH always uses root, not admin
                "password": self.chester_client.password or "",
            }
        return {"host": "192.168.12.1", "username": "root", "password": ""}

    def run_speedtest(self) -> Dict[str, Any]:
        """SSH into Chester router and run Ookla speedtest.

        2026-03-11: Chester firmware 2.4.0+ has `speedtest` (by Ookla) built-in.
        `ssh root@<chester_ip>` then `speedtest --format=json` gives JSON output.
        This tests the actual WAN speed at the router level — most accurate.
        """
        test_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        # Capture Chester cellular state at time of test
        cellular = self._get_cellular_snapshot()

        creds = self._get_ssh_creds()
        if not creds["password"]:
            return self._store_error_result(
                test_id, "Chester SSH password not configured", cellular
            )

        try:
            # 2026-03-11: SSH into Chester and run speedtest with JSON output.
            # Use sshpass for non-interactive password auth.
            # StrictHostKeyChecking=no since it's a local network device.
            ssh_cmd = [
                "sshpass", "-p", creds["password"],
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=10",
                "-p", "22",
                f"{creds['username']}@{creds['host']}",
                "speedtest --format=json --accept-license --accept-gdpr",
            ]

            logger.info(f"Running speedtest on Chester router at {creds['host']}...")
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=180,  # speedtest can take up to ~2 min
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or f"Exit code {result.returncode}"
                # Check for common SSH issues
                if "Permission denied" in error_msg:
                    error_msg = "SSH authentication failed — check Chester password"
                elif "Connection refused" in error_msg:
                    error_msg = "SSH connection refused — ensure SSH is enabled on Chester (port 22)"
                elif "No route to host" in error_msg or "Connection timed out" in error_msg:
                    error_msg = f"Cannot reach Chester at {creds['host']}"
                logger.error(f"Chester speedtest failed: {error_msg}")
                return self._store_error_result(test_id, error_msg, cellular)

            # Parse Ookla JSON output
            stdout = result.stdout.strip()
            # Sometimes SSH banners or MOTD precede JSON — find the JSON object
            json_start = stdout.find("{")
            if json_start < 0:
                return self._store_error_result(
                    test_id, f"No JSON in speedtest output: {stdout[:200]}", cellular
                )
            data = json.loads(stdout[json_start:])
            elapsed = (datetime.utcnow() - start_time).total_seconds()

            # Ookla speedtest JSON format:
            # download/upload: { bandwidth: bytes/sec }
            # ping: { latency: ms, jitter: ms }
            # server: { name, id, host, ip, location }
            # isp, interface.externalIp
            dl_bw = data.get("download", {}).get("bandwidth", 0)
            ul_bw = data.get("upload", {}).get("bandwidth", 0)
            # bandwidth is bytes/sec, convert to Mbps (megabits)
            download_mbps = round((dl_bw * 8) / 1_000_000, 2)
            upload_mbps = round((ul_bw * 8) / 1_000_000, 2)

            ping_info = data.get("ping", {})
            ping_ms = round(ping_info.get("latency", 0), 2)
            jitter_ms = round(ping_info.get("jitter", 0), 2)

            server = data.get("server", {})
            iface = data.get("interface", {})

            dl_bytes = data.get("download", {}).get("bytes", 0)
            ul_bytes = data.get("upload", {}).get("bytes", 0)

            test_result = {
                "test_id": test_id,
                "download_mbps": download_mbps,
                "upload_mbps": upload_mbps,
                "ping_ms": ping_ms,
                "jitter_ms": jitter_ms,
                "server_name": server.get("name", ""),
                "server_id": str(server.get("id", "")),
                "server_host": server.get("host", ""),
                "isp": data.get("isp", ""),
                "external_ip": iface.get("externalIp", ""),
                "bytes_sent": ul_bytes,
                "bytes_received": dl_bytes,
                "test_duration_seconds": round(elapsed, 1),
                "error": None,
                "timestamp": datetime.utcnow().isoformat(),
                **cellular,
            }

            self._store_result(test_result)
            logger.info(
                f"Chester speedtest complete: ↓{download_mbps} Mbps ↑{upload_mbps} Mbps "
                f"ping {ping_ms}ms jitter {jitter_ms}ms via {server.get('name', 'unknown')}"
            )
            return test_result

        except subprocess.TimeoutExpired:
            return self._store_error_result(
                test_id, "Chester speedtest timed out (180s)", cellular
            )
        except json.JSONDecodeError as e:
            return self._store_error_result(
                test_id, f"Invalid JSON from Chester speedtest: {e}", cellular
            )
        except FileNotFoundError:
            return self._store_error_result(
                test_id,
                "sshpass not installed — run: brew install hudochenkov/sshpass/sshpass",
                cellular,
            )
        except Exception as e:
            return self._store_error_result(test_id, str(e), cellular)

    def _get_cellular_snapshot(self) -> Dict[str, Any]:
        """Capture Chester cellular signal + carrier aggregation data at time of speed test.

        2026-03-11: Extended to capture full CA band info, ARFCN, PCID, cell_id
        for tracking which bands/channels correlate with better speeds.
        """
        empty = {
            "cellular_band": None,
            "cellular_rsrp": None,
            "cellular_rsrq": None,
            "cellular_sinr": None,
            "cellular_connection_type": None,
            "cellular_ca_bands": None,
            "cellular_ca_count": None,
            "cellular_arfcn": None,
            "cellular_pcid": None,
            "cellular_cell_id": None,
            "cellular_is_5g": None,
            "cellular_mcc": None,
            "cellular_mnc": None,
        }
        if not self.chester_service:
            return empty

        try:
            info = self.chester_service.get_system_info()
            ca_bands = info.get("ca_band", [])
            # Parse CA bands into structured list: [{role, band, arfcn}, ...]
            parsed_ca = []
            for entry in ca_bands:
                parts = entry.replace('"', '').split(",")
                if len(parts) >= 4:
                    parsed_ca.append({
                        "role": parts[0].strip(),       # PCC or SCC
                        "arfcn": parts[1].strip(),
                        "bandwidth": parts[2].strip(),
                        "band": parts[3].strip(),       # e.g. "NR5G BAND 41"
                    })
            return {
                "cellular_band": info.get("band", ""),
                "cellular_rsrp": info.get("rsrp"),
                "cellular_rsrq": info.get("rsrq"),
                "cellular_sinr": info.get("sinr"),
                "cellular_connection_type": info.get("connection_type", ""),
                "cellular_ca_bands": json.dumps(parsed_ca) if parsed_ca else None,
                "cellular_ca_count": len(parsed_ca) if parsed_ca else None,
                "cellular_arfcn": str(info.get("arfcn", "")),
                "cellular_pcid": str(info.get("pcid", "")),
                "cellular_cell_id": str(info.get("cell_id", "")),
                "cellular_is_5g": 1 if info.get("is_5g") else 0,
                "cellular_mcc": str(info.get("mcc", "")),
                "cellular_mnc": str(info.get("mnc", "")),
            }
        except Exception as e:
            logger.warning(f"Failed to capture cellular snapshot: {e}")
            return empty

    def _store_result(self, result: Dict[str, Any]):
        """Store a speed test result in the database."""
        conn = self.db.connection
        conn.execute(
            """INSERT INTO speed_tests (
                test_id, download_mbps, upload_mbps, ping_ms, jitter_ms,
                server_name, server_id, server_host, isp, external_ip,
                cellular_band, cellular_rsrp, cellular_rsrq, cellular_sinr,
                cellular_connection_type, cellular_ca_bands, cellular_ca_count,
                cellular_arfcn, cellular_pcid, cellular_cell_id, cellular_is_5g,
                cellular_mcc, cellular_mnc,
                bytes_sent, bytes_received,
                test_duration_seconds, error, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result["test_id"],
                result["download_mbps"],
                result["upload_mbps"],
                result["ping_ms"],
                result.get("jitter_ms"),
                result.get("server_name"),
                result.get("server_id"),
                result.get("server_host"),
                result.get("isp"),
                result.get("external_ip"),
                result.get("cellular_band"),
                result.get("cellular_rsrp"),
                result.get("cellular_rsrq"),
                result.get("cellular_sinr"),
                result.get("cellular_connection_type"),
                result.get("cellular_ca_bands"),
                result.get("cellular_ca_count"),
                result.get("cellular_arfcn"),
                result.get("cellular_pcid"),
                result.get("cellular_cell_id"),
                result.get("cellular_is_5g"),
                result.get("cellular_mcc"),
                result.get("cellular_mnc"),
                result.get("bytes_sent"),
                result.get("bytes_received"),
                result.get("test_duration_seconds"),
                result.get("error"),
                result["timestamp"],
            ),
        )
        conn.commit()

    def _store_error_result(
        self, test_id: str, error: str, cellular: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store a failed speed test result."""
        result = {
            "test_id": test_id,
            "download_mbps": 0,
            "upload_mbps": 0,
            "ping_ms": 0,
            "jitter_ms": None,
            "server_name": None,
            "server_id": None,
            "server_host": None,
            "isp": None,
            "external_ip": None,
            "bytes_sent": 0,
            "bytes_received": 0,
            "test_duration_seconds": 0,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
            **cellular,
        }
        self._store_result(result)
        logger.error(f"Speed test error stored: {error}")
        return result

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Get the most recent speed test result."""
        conn = self.db.connection
        row = conn.execute(
            "SELECT * FROM speed_tests WHERE error IS NULL ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_previous(self) -> Optional[Dict[str, Any]]:
        """Get the second most recent speed test result (for % change calc)."""
        conn = self.db.connection
        row = conn.execute(
            "SELECT * FROM speed_tests WHERE error IS NULL ORDER BY timestamp DESC LIMIT 1 OFFSET 1"
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_latest_with_change(self) -> Dict[str, Any]:
        """Get latest result plus % change from previous test."""
        latest = self.get_latest()
        if not latest:
            return {"latest": None, "previous": None, "change": None}

        previous = self.get_previous()
        change = None
        if previous:
            change = {
                "download_pct": self._pct_change(
                    previous["download_mbps"], latest["download_mbps"]
                ),
                "upload_pct": self._pct_change(
                    previous["upload_mbps"], latest["upload_mbps"]
                ),
                "ping_pct": self._pct_change(
                    previous["ping_ms"], latest["ping_ms"]
                ),
            }

        return {"latest": latest, "previous": previous, "change": change}

    def get_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get speed test results for the last N hours."""
        conn = self.db.connection
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            """SELECT * FROM speed_tests
               WHERE timestamp >= ? AND error IS NULL
               ORDER BY timestamp ASC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_history(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Get all speed test results (for insights analysis)."""
        conn = self.db.connection
        rows = conn.execute(
            "SELECT * FROM speed_tests WHERE error IS NULL ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get aggregate stats for the last N hours."""
        conn = self.db.connection
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        row = conn.execute(
            """SELECT
                COUNT(*) as test_count,
                AVG(download_mbps) as avg_download,
                MAX(download_mbps) as max_download,
                MIN(download_mbps) as min_download,
                AVG(upload_mbps) as avg_upload,
                MAX(upload_mbps) as max_upload,
                MIN(upload_mbps) as min_upload,
                AVG(ping_ms) as avg_ping,
                MIN(ping_ms) as min_ping,
                MAX(ping_ms) as max_ping
               FROM speed_tests
               WHERE timestamp >= ? AND error IS NULL""",
            (cutoff,),
        ).fetchone()
        if not row or row["test_count"] == 0:
            return {"test_count": 0}
        return {k: round(v, 2) if isinstance(v, float) else v for k, v in dict(row).items()}

    def get_hourly_averages(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get average speeds grouped by hour of day (for pattern detection)."""
        conn = self.db.connection
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT
                CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                AVG(download_mbps) as avg_download,
                AVG(upload_mbps) as avg_upload,
                AVG(ping_ms) as avg_ping,
                COUNT(*) as sample_count
               FROM speed_tests
               WHERE timestamp >= ? AND error IS NULL
               GROUP BY hour
               ORDER BY hour""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Insights storage --

    def store_insight(self, insight: Dict[str, Any]):
        """Store an AI-generated insight."""
        conn = self.db.connection
        conn.execute(
            """INSERT OR REPLACE INTO speed_insights
               (insight_id, insight_type, title, description, data_json, confidence, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                insight["insight_id"],
                insight["insight_type"],
                insight["title"],
                insight["description"],
                json.dumps(insight.get("data")) if insight.get("data") else None,
                insight.get("confidence"),
                datetime.utcnow().isoformat(),
                insight.get("expires_at"),
            ),
        )
        conn.commit()

    def get_insights(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent insights, excluding expired ones."""
        conn = self.db.connection
        now = datetime.utcnow().isoformat()
        rows = conn.execute(
            """SELECT * FROM speed_insights
               WHERE expires_at IS NULL OR expires_at > ?
               ORDER BY created_at DESC LIMIT ?""",
            (now, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("data_json"):
                d["data"] = json.loads(d["data_json"])
            else:
                d["data"] = None
            del d["data_json"]
            results.append(d)
        return results

    def generate_insights(self) -> List[Dict[str, Any]]:
        """Generate insights from speed test data using statistical analysis.

        2026-03-11: Rule-based insights engine — analyzes patterns in speed data
        and generates human-readable findings. Runs after each speed test.
        """
        insights = []
        history = self.get_all_history(limit=500)
        if len(history) < 3:
            return insights

        # --- Insight 1: Speed trend (last 10 tests) ---
        recent = history[:10]
        if len(recent) >= 5:
            first_half = recent[len(recent) // 2 :]
            second_half = recent[: len(recent) // 2]
            avg_old_dl = sum(t["download_mbps"] for t in first_half) / len(first_half)
            avg_new_dl = sum(t["download_mbps"] for t in second_half) / len(second_half)
            if avg_old_dl > 0:
                trend_pct = ((avg_new_dl - avg_old_dl) / avg_old_dl) * 100
                if abs(trend_pct) > 10:
                    direction = "improving" if trend_pct > 0 else "declining"
                    insight = {
                        "insight_id": f"trend-{datetime.utcnow().strftime('%Y%m%d')}",
                        "insight_type": "trend",
                        "title": f"Download speed {direction}",
                        "description": (
                            f"Download speeds have {'increased' if trend_pct > 0 else 'decreased'} "
                            f"by {abs(trend_pct):.1f}% over the last {len(recent)} tests. "
                            f"Recent average: {avg_new_dl:.1f} Mbps vs prior: {avg_old_dl:.1f} Mbps."
                        ),
                        "data": {
                            "trend_pct": round(trend_pct, 1),
                            "avg_new": round(avg_new_dl, 1),
                            "avg_old": round(avg_old_dl, 1),
                        },
                        "confidence": min(0.9, 0.5 + len(recent) * 0.04),
                    }
                    insights.append(insight)
                    self.store_insight(insight)

        # --- Insight 2: Peak/off-peak hours ---
        hourly = self.get_hourly_averages(days=7)
        if len(hourly) >= 6:
            sorted_hours = sorted(hourly, key=lambda h: h["avg_download"], reverse=True)
            best = sorted_hours[0]
            worst = sorted_hours[-1]
            if best["avg_download"] > 0 and worst["avg_download"] > 0:
                diff_pct = ((best["avg_download"] - worst["avg_download"]) / worst["avg_download"]) * 100
                if diff_pct > 15:
                    insight = {
                        "insight_id": f"peak-hours-{datetime.utcnow().strftime('%Y%m%d')}",
                        "insight_type": "hourly_pattern",
                        "title": "Peak vs off-peak speed difference detected",
                        "description": (
                            f"Fastest speeds at {best['hour']:02d}:00 "
                            f"({best['avg_download']:.1f} Mbps avg), "
                            f"slowest at {worst['hour']:02d}:00 "
                            f"({worst['avg_download']:.1f} Mbps avg). "
                            f"That's a {diff_pct:.0f}% difference. "
                            f"Schedule heavy downloads during off-peak hours for best performance."
                        ),
                        "data": {
                            "best_hour": best["hour"],
                            "best_avg": round(best["avg_download"], 1),
                            "worst_hour": worst["hour"],
                            "worst_avg": round(worst["avg_download"], 1),
                            "diff_pct": round(diff_pct, 0),
                        },
                        "confidence": min(0.85, 0.4 + len(hourly) * 0.05),
                    }
                    insights.append(insight)
                    self.store_insight(insight)

        # --- Insight 3: Cellular signal correlation ---
        tests_with_signal = [
            t for t in history if t.get("cellular_rsrp") is not None and t["cellular_rsrp"] != ""
        ]
        if len(tests_with_signal) >= 5:
            rsrps = sorted(tests_with_signal, key=lambda t: float(t["cellular_rsrp"]))
            mid = len(rsrps) // 2
            weak_signal = rsrps[:mid]
            strong_signal = rsrps[mid:]
            avg_weak_dl = sum(t["download_mbps"] for t in weak_signal) / len(weak_signal)
            avg_strong_dl = sum(t["download_mbps"] for t in strong_signal) / len(strong_signal)
            if avg_weak_dl > 0:
                signal_impact = ((avg_strong_dl - avg_weak_dl) / avg_weak_dl) * 100
                if abs(signal_impact) > 10:
                    avg_weak_rsrp = sum(float(t["cellular_rsrp"]) for t in weak_signal) / len(weak_signal)
                    avg_strong_rsrp = sum(float(t["cellular_rsrp"]) for t in strong_signal) / len(strong_signal)
                    insight = {
                        "insight_id": f"signal-corr-{datetime.utcnow().strftime('%Y%m%d')}",
                        "insight_type": "recommendation",
                        "title": "Cellular signal affects download speed",
                        "description": (
                            f"When signal is stronger (RSRP ~{avg_strong_rsrp:.0f} dBm), "
                            f"downloads average {avg_strong_dl:.1f} Mbps. "
                            f"With weaker signal (RSRP ~{avg_weak_rsrp:.0f} dBm), "
                            f"only {avg_weak_dl:.1f} Mbps — "
                            f"a {abs(signal_impact):.0f}% {'improvement' if signal_impact > 0 else 'reduction'}. "
                            f"Consider router placement or antenna orientation for better signal."
                        ),
                        "data": {
                            "avg_weak_rsrp": round(avg_weak_rsrp, 0),
                            "avg_strong_rsrp": round(avg_strong_rsrp, 0),
                            "avg_weak_dl": round(avg_weak_dl, 1),
                            "avg_strong_dl": round(avg_strong_dl, 1),
                            "impact_pct": round(signal_impact, 1),
                        },
                        "confidence": min(0.8, 0.4 + len(tests_with_signal) * 0.03),
                    }
                    insights.append(insight)
                    self.store_insight(insight)

        # --- Insight 4: Anomaly detection (outliers) ---
        if len(history) >= 10:
            dls = [t["download_mbps"] for t in history]
            avg_dl = sum(dls) / len(dls)
            std_dl = (sum((x - avg_dl) ** 2 for x in dls) / len(dls)) ** 0.5
            latest = history[0]
            if std_dl > 0:
                z_score = (latest["download_mbps"] - avg_dl) / std_dl
                if abs(z_score) > 2:
                    direction = "unusually fast" if z_score > 0 else "unusually slow"
                    insight = {
                        "insight_id": f"anomaly-{latest['test_id'][:8]}",
                        "insight_type": "anomaly",
                        "title": f"Latest test was {direction}",
                        "description": (
                            f"The most recent test ({latest['download_mbps']:.1f} Mbps download) "
                            f"is {abs(z_score):.1f} standard deviations from the average "
                            f"({avg_dl:.1f} Mbps). This could indicate "
                            f"{'optimal conditions' if z_score > 0 else 'network congestion or signal degradation'}."
                        ),
                        "data": {
                            "z_score": round(z_score, 2),
                            "latest_dl": latest["download_mbps"],
                            "avg_dl": round(avg_dl, 1),
                            "std_dl": round(std_dl, 1),
                        },
                        "confidence": 0.7,
                        "expires_at": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
                    }
                    insights.append(insight)
                    self.store_insight(insight)

        # --- Insight 5: Upload/Download ratio ---
        if len(history) >= 5:
            ratios = [
                t["upload_mbps"] / t["download_mbps"]
                for t in history[:20]
                if t["download_mbps"] > 0
            ]
            if ratios:
                avg_ratio = sum(ratios) / len(ratios)
                if avg_ratio < 0.1:
                    insight = {
                        "insight_id": f"ratio-{datetime.utcnow().strftime('%Y%m%d')}",
                        "insight_type": "recommendation",
                        "title": "Highly asymmetric connection detected",
                        "description": (
                            f"Upload speed averages only {avg_ratio * 100:.1f}% of download speed. "
                            f"This is typical for cellular connections but may affect video calls, "
                            f"cloud backups, and file uploads."
                        ),
                        "data": {"avg_ratio": round(avg_ratio, 3)},
                        "confidence": 0.8,
                    }
                    insights.append(insight)
                    self.store_insight(insight)

        # --- Insight 6: Carrier aggregation band correlation ---
        # 2026-03-11: Track which CA band combos give better speeds
        tests_with_ca = [
            t for t in history
            if t.get("cellular_ca_count") is not None and t["cellular_ca_count"] > 0
        ]
        if len(tests_with_ca) >= 5:
            # Group by CA count
            by_ca_count: Dict[int, list] = {}
            for t in tests_with_ca:
                count = t["cellular_ca_count"]
                by_ca_count.setdefault(count, []).append(t)

            # Compare speeds by CA count
            ca_stats = {}
            for count, tests in sorted(by_ca_count.items()):
                avg_dl = sum(t["download_mbps"] for t in tests) / len(tests)
                avg_ul = sum(t["upload_mbps"] for t in tests) / len(tests)
                ca_stats[count] = {
                    "avg_download": round(avg_dl, 1),
                    "avg_upload": round(avg_ul, 1),
                    "sample_count": len(tests),
                }

            if len(ca_stats) >= 2:
                best_count = max(ca_stats, key=lambda c: ca_stats[c]["avg_download"])
                worst_count = min(ca_stats, key=lambda c: ca_stats[c]["avg_download"])
                best = ca_stats[best_count]
                worst = ca_stats[worst_count]
                if worst["avg_download"] > 0:
                    diff_pct = ((best["avg_download"] - worst["avg_download"]) / worst["avg_download"]) * 100
                    if diff_pct > 10:
                        insight = {
                            "insight_id": f"ca-count-{datetime.utcnow().strftime('%Y%m%d')}",
                            "insight_type": "recommendation",
                            "title": "More carrier aggregation = faster speeds",
                            "description": (
                                f"With {best_count} aggregated carriers, download averages "
                                f"{best['avg_download']} Mbps vs {worst['avg_download']} Mbps "
                                f"with only {worst_count} carrier{'s' if worst_count != 1 else ''}. "
                                f"That's {diff_pct:.0f}% faster. "
                                f"More carriers are typically available during off-peak hours."
                            ),
                            "data": {
                                "ca_stats": ca_stats,
                                "best_count": best_count,
                                "worst_count": worst_count,
                                "diff_pct": round(diff_pct, 0),
                            },
                            "confidence": min(0.85, 0.4 + len(tests_with_ca) * 0.03),
                        }
                        insights.append(insight)
                        self.store_insight(insight)

            # Group by primary band and compare
            by_band: Dict[str, list] = {}
            for t in tests_with_ca:
                band = str(t.get("cellular_band", ""))
                if band:
                    by_band.setdefault(band, []).append(t)

            band_stats = {}
            for band, tests in by_band.items():
                if len(tests) >= 3:
                    avg_dl = sum(t["download_mbps"] for t in tests) / len(tests)
                    avg_ul = sum(t["upload_mbps"] for t in tests) / len(tests)
                    avg_ping = sum(t["ping_ms"] for t in tests) / len(tests)
                    band_stats[band] = {
                        "avg_download": round(avg_dl, 1),
                        "avg_upload": round(avg_ul, 1),
                        "avg_ping": round(avg_ping, 1),
                        "sample_count": len(tests),
                    }

            if len(band_stats) >= 2:
                best_band = max(band_stats, key=lambda b: band_stats[b]["avg_download"])
                worst_band = min(band_stats, key=lambda b: band_stats[b]["avg_download"])
                best_b = band_stats[best_band]
                worst_b = band_stats[worst_band]
                if worst_b["avg_download"] > 0:
                    diff_pct = ((best_b["avg_download"] - worst_b["avg_download"]) / worst_b["avg_download"]) * 100
                    if diff_pct > 15:
                        insight = {
                            "insight_id": f"band-perf-{datetime.utcnow().strftime('%Y%m%d')}",
                            "insight_type": "recommendation",
                            "title": f"Band n{best_band} outperforms n{worst_band}",
                            "description": (
                                f"On primary band n{best_band}: avg {best_b['avg_download']} Mbps down, "
                                f"{best_b['avg_ping']} ms ping ({best_b['sample_count']} tests). "
                                f"On n{worst_band}: avg {worst_b['avg_download']} Mbps down, "
                                f"{worst_b['avg_ping']} ms ping ({worst_b['sample_count']} tests). "
                                f"Band n{best_band} is {diff_pct:.0f}% faster on average."
                            ),
                            "data": {
                                "band_stats": band_stats,
                                "best_band": best_band,
                                "worst_band": worst_band,
                            },
                            "confidence": min(0.85, 0.4 + sum(b["sample_count"] for b in band_stats.values()) * 0.02),
                        }
                        insights.append(insight)
                        self.store_insight(insight)

        return insights

    @staticmethod
    def _pct_change(old: float, new: float) -> Optional[float]:
        if old == 0:
            return None
        return round(((new - old) / old) * 100, 1)
