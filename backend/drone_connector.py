"""
Drone Connector
Connect to ArduPilot/PX4 drones via MAVLink to download logs directly

Optimizations vs original:
- Single log_request_list_send (no duplicate spam that causes collisions)
- Windowed/chunked log download with gap detection and retransmit requests
- Non-blocking receive with short poll timeout (0.1s) to avoid dead-wait
- Adaptive no-data timeout: short for completion, longer for mid-transfer stalls
- Progress callback throttle reduced to 100ms for smoother UI
- Connection uses source_system=255 (GCS) to avoid target filtering issues
"""

from pathlib import Path
from typing import Optional, List, Dict, Callable
import time
from datetime import datetime

try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False

# ── Tuning constants ──────────────────────────────────────────────────────────
CHUNK_SIZE          = 90          # MAVLink LOG_DATA payload is always 90 bytes max
WINDOW_SIZE         = 64          # How many chunks to request before waiting for ACKs
LOG_LIST_TIMEOUT    = 12          # Seconds to wait for full log list
LOG_DATA_TIMEOUT    = 180         # Overall download timeout (3 min)
NO_DATA_STALL_MS    = 3000        # Retransmit if no packet for this many ms
HEARTBEAT_TIMEOUT   = 10          # Seconds to wait for initial heartbeat
PROGRESS_INTERVAL   = 0.1         # Seconds between progress callback calls
RECV_POLL_TIMEOUT   = 0.1         # Non-blocking receive poll timeout (keep short!)
# ─────────────────────────────────────────────────────────────────────────────


class DroneConnector:
    """Manages connection to drones for log download"""

    def __init__(self):
        self.connection = None
        self.is_connected = False
        self.vehicle_info: Dict = {}

    # ── Port Discovery ────────────────────────────────────────────────────────

    def get_available_ports(self) -> List[str]:
        """Get list of available serial ports"""
        ports = []
        try:
            import serial.tools.list_ports
            for port in serial.tools.list_ports.comports():
                if 'COM1' not in port.device or 'USB' in port.description.upper():
                    ports.append(f"{port.device} - {port.description}")
        except ImportError:
            import platform
            if platform.system() == 'Windows':
                ports = [f'COM{i}' for i in range(2, 20)]
            else:
                ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']

        ports.extend([
            'UDP:127.0.0.1:14550 (Simulator)',
            'UDP:0.0.0.0:14550 (Listen)',
            'TCP:127.0.0.1:5760 (Companion Computer)',
        ])
        return ports

    # ── Auto-detect ───────────────────────────────────────────────────────────

    def auto_detect_drone(self, progress_callback=None) -> Optional[tuple]:
        """
        Auto-detect connected drone by scanning all ports.
        Returns (port, baud_rate) tuple if found, else None.
        """
        if not PYMAVLINK_AVAILABLE:
            return None

        try:
            import serial.tools.list_ports
            available_ports = [
                p.device for p in serial.tools.list_ports.comports()
                if 'COM1' not in p.device
            ]
            if not available_ports:
                return None

            # Try fastest baud rates first — 921600 is common for newer FCs
            baud_rates = [921600, 115200, 57600]
            total = len(available_ports) * len(baud_rates)
            attempt = 0

            for port in available_ports:
                for baud in baud_rates:
                    attempt += 1
                    if progress_callback:
                        progress_callback(attempt, total, f"Testing {port} @ {baud}")
                    try:
                        conn = mavutil.mavlink_connection(port, baud=baud)
                        msg = conn.recv_match(type='HEARTBEAT', blocking=True, timeout=2)
                        conn.close()
                        if msg:
                            return (port, baud)
                    except Exception:
                        continue

        except Exception as e:
            print(f"Auto-detect error: {e}")

        return None

    # ── Connect / Disconnect ──────────────────────────────────────────────────

    def connect(self, connection_string: str, baud_rate=57600) -> bool:
        """
        Connect to drone.

        Args:
            connection_string: Serial port or network address
            baud_rate: Baud rate (int, or string like "115200")
        Returns:
            True on success
        """
        if not PYMAVLINK_AVAILABLE:
            raise RuntimeError("pymavlink not installed. Run: pip install pymavlink")

        try:
            if isinstance(baud_rate, str):
                baud_rate = int(baud_rate.split()[0])
            else:
                baud_rate = int(baud_rate)

            # Parse connection string
            if connection_string.startswith(('UDP:', 'TCP:')):
                conn_str = connection_string.split(':', 1)[1].strip()
            else:
                conn_str = connection_string.split(' - ')[0].strip()
                if not (conn_str.startswith('/dev/') or conn_str.startswith('COM')):
                    conn_str = connection_string

            print(f"Connecting to {conn_str} @ {baud_rate} baud...")

            # source_system=255 identifies us as a GCS — avoids message filtering
            if any(p in conn_str.lower() for p in ('udp:', 'tcp:')):
                self.connection = mavutil.mavlink_connection(
                    conn_str, source_system=255
                )
            else:
                self.connection = mavutil.mavlink_connection(
                    conn_str, baud=baud_rate, source_system=255
                )

            print("Waiting for heartbeat...")
            self.connection.wait_heartbeat(timeout=HEARTBEAT_TIMEOUT)
            self.is_connected = True
            print("Connected!")
            self._get_vehicle_info()
            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            import traceback; traceback.print_exc()
            self.is_connected = False
            return False

    def disconnect(self):
        """Disconnect from drone"""
        if self.connection:
            self.connection.close()
        self.is_connected = False
        self.vehicle_info = {}

    # ── Vehicle Info ──────────────────────────────────────────────────────────

    def _get_vehicle_info(self):
        if not self.is_connected:
            return
        try:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES,
                0, 1, 0, 0, 0, 0, 0, 0
            )
            msg = self.connection.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            if msg:
                self.vehicle_info.update({
                    'type': msg.type,
                    'autopilot': msg.autopilot,
                    'base_mode': msg.base_mode,
                    'system_status': msg.system_status,
                })
            msg = self.connection.recv_match(type='AUTOPILOT_VERSION', blocking=True, timeout=5)
            if msg:
                self.vehicle_info.update({
                    'flight_sw_version': msg.flight_sw_version,
                    'board_version': msg.board_version,
                })
        except Exception as e:
            print(f"Error getting vehicle info: {e}")

    def get_vehicle_info(self) -> Dict:
        return self.vehicle_info.copy()

    # ── Log Listing ───────────────────────────────────────────────────────────

    def list_logs(self) -> List[Dict]:
        """
        List available logs on the drone.

        Key fix: send the request ONCE. Sending it multiple times causes the
        drone to restart its list transmission, colliding with your receive loop
        and dropping entries.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to drone")

        logs: Dict[int, Dict] = {}  # keyed by log id to deduplicate

        try:
            sys  = self.connection.target_system
            comp = self.connection.target_component

            print(f"Requesting log list (sys={sys} comp={comp})...")

            # ── Send request ONCE ──────────────────────────────────────────
            self.connection.mav.log_request_list_send(sys, comp, 0, 0xFFFF)

            deadline      = time.time() + LOG_LIST_TIMEOUT
            num_logs      = None   # filled once first LOG_ENTRY arrives
            last_rx       = time.time()

            while time.time() < deadline:
                msg = self.connection.recv_match(
                    type='LOG_ENTRY',
                    blocking=True,
                    timeout=RECV_POLL_TIMEOUT,
                )

                if msg is None:
                    # If we know how many logs to expect and got them all, done
                    if num_logs is not None and len(logs) >= num_logs:
                        break
                    # Stall: no new data for 2s after first entry received — re-request
                    if num_logs is not None and (time.time() - last_rx) > 2.0:
                        print("Stall detected — re-requesting log list...")
                        self.connection.mav.log_request_list_send(sys, comp, 0, 0xFFFF)
                        last_rx = time.time()  # reset stall timer
                    continue

                last_rx  = time.time()
                num_logs = msg.num_logs

                logs[msg.id] = {
                    'id':           msg.id,
                    'num_logs':     msg.num_logs,
                    'last_log_num': msg.last_log_num,
                    'time_utc':     msg.time_utc,
                    'size':         msg.size,
                }

                print(f"  LOG_ENTRY id={msg.id}  size={msg.size}B  "
                      f"({len(logs)}/{num_logs})")

                if len(logs) >= num_logs:
                    break

        except Exception as e:
            print(f"Error listing logs: {e}")
            import traceback; traceback.print_exc()

        result = sorted(logs.values(), key=lambda x: x['id'])
        print(f"Got {len(result)} log(s)")
        return result

    # ── Log Download ──────────────────────────────────────────────────────────

    def download_log(
        self,
        log_id: int,
        output_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        expected_size: int = 0,
    ) -> bool:
        """
        Download a single log using a sliding-window + gap-retransmit strategy.

        How it works:
        1. Request the first WINDOW_SIZE * CHUNK_SIZE bytes.
        2. As packets arrive, track which offsets we have.
        3. When a window is complete (or stalls), request the next window.
        4. If a gap is detected after a stall, retransmit only the missing range.
        5. End-of-log is signalled by a packet with count < CHUNK_SIZE.

        This is dramatically faster than requesting 0xFFFFFFFF at once and
        waiting because:
        - The FC can pipeline within a known window
        - Gaps are caught and retransmitted quickly
        - We're never waiting 5s for a "maybe finished" signal
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to drone")

        sys  = self.connection.target_system
        comp = self.connection.target_component

        # ── State ──────────────────────────────────────────────────────────
        received: Dict[int, bytes] = {}   # offset → payload bytes
        eof_offset: Optional[int]  = None # set when we receive final short packet
        last_rx_time               = time.time()
        last_progress_time         = time.time()
        deadline                   = time.time() + LOG_DATA_TIMEOUT
        window_start               = 0

        def _request_window(offset: int):
            """Ask for WINDOW_SIZE chunks starting at offset."""
            count = WINDOW_SIZE * CHUNK_SIZE
            print(f"  Requesting window offset={offset} count={count}")
            self.connection.mav.log_request_data_send(
                sys, comp, log_id, offset, count
            )

        _request_window(0)

        print(f"Downloading log {log_id}  (expected {expected_size}B)...")

        while time.time() < deadline:
            msg = self.connection.recv_match(
                type='LOG_DATA',
                blocking=True,
                timeout=RECV_POLL_TIMEOUT,
            )

            if msg is not None and msg.id == log_id:
                offset  = msg.ofs
                payload = bytes(msg.data[:msg.count])
                received[offset] = payload
                last_rx_time = time.time()

                # Detect end-of-log (short packet)
                if msg.count < CHUNK_SIZE:
                    eof_offset = offset + msg.count
                    print(f"  EOF packet at offset={offset} count={msg.count}")

                # Progress callback
                if progress_callback and (time.time() - last_progress_time) > PROGRESS_INTERVAL:
                    bytes_so_far = sum(len(v) for v in received.values())
                    total        = expected_size if expected_size > 0 else bytes_so_far
                    progress_callback(bytes_so_far, total)
                    last_progress_time = time.time()

                # Advance window when we've filled enough of the current one
                next_expected = window_start + WINDOW_SIZE * CHUNK_SIZE
                if offset >= next_expected - CHUNK_SIZE * 4:
                    window_start = next_expected
                    if eof_offset is None:
                        _request_window(window_start)

            else:
                # Nothing came in — check for stall or completion
                stall = (time.time() - last_rx_time) > (NO_DATA_STALL_MS / 1000)

                if eof_offset is not None:
                    # We know the end; check if we have everything
                    missing = self._find_missing_offsets(received, eof_offset)
                    if not missing:
                        print("  All packets received, download complete.")
                        break
                    if stall:
                        # Retransmit only the first missing gap
                        gap_start, gap_count = missing[0]
                        print(f"  Retransmitting gap: offset={gap_start} count={gap_count}")
                        self.connection.mav.log_request_data_send(
                            sys, comp, log_id, gap_start, gap_count
                        )
                        last_rx_time = time.time()
                elif stall:
                    # No EOF yet, no data for a while — re-request current window
                    print(f"  Stall (no EOF yet) — re-requesting window at {window_start}")
                    _request_window(window_start)
                    last_rx_time = time.time()

        # ── Assemble file ──────────────────────────────────────────────────
        if not received:
            print(f"No data received for log {log_id}")
            return False

        end = eof_offset if eof_offset is not None else (max(received) + len(received[max(received)]))
        buf = bytearray(end)
        for off, data in received.items():
            buf[off:off + len(data)] = data

        # Final progress
        if progress_callback:
            progress_callback(len(buf), len(buf))

        print(f"Saving {len(buf)}B → {output_path}")
        Path(output_path).write_bytes(buf)
        print(f"Log {log_id} done  ({len(received)} packets)")
        return True

    @staticmethod
    def _find_missing_offsets(
        received: Dict[int, bytes], eof_offset: int
    ) -> List[tuple]:
        """
        Return list of (start_offset, byte_count) tuples for gaps in received data.
        Coalesces adjacent missing chunks into single retransmit requests.
        """
        if not received:
            return [(0, eof_offset)]

        gaps = []
        cursor = 0
        for off in sorted(received):
            if off > cursor:
                gaps.append((cursor, off - cursor))
            cursor = max(cursor, off + len(received[off]))
        if cursor < eof_offset:
            gaps.append((cursor, eof_offset - cursor))
        return gaps

    # ── Bulk Download ─────────────────────────────────────────────────────────

    def download_all_logs(
        self,
        output_dir: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[str]:
        """
        Download all logs from drone.

        Args:
            output_dir: Directory to save logs
            progress_callback: callback(current_log_index, total_logs, filename)
        Returns:
            List of successfully downloaded file paths
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to drone")

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        logs = self.list_logs()
        if not logs:
            print("No logs found on drone")
            return []

        print(f"Found {len(logs)} log(s)")
        downloaded = []

        for i, log_info in enumerate(logs, 1):
            log_id   = log_info['id']
            log_size = log_info.get('size', 0)

            if log_info['time_utc'] > 0:
                ts = datetime.fromtimestamp(log_info['time_utc']).strftime('%Y%m%d_%H%M%S')
            else:
                ts = f"log{log_id:04d}"

            filename = f"{ts}.bin"
            filepath = out / filename

            print(f"\n[{i}/{len(logs)}] {filename}  ({log_size}B)")
            if progress_callback:
                progress_callback(i, len(logs), filename)

            if self.download_log(log_id, str(filepath), expected_size=log_size):
                downloaded.append(str(filepath))
                print(f"  ✓ {filename}")
            else:
                print(f"  ✗ {filename} — FAILED")

        print(f"\nDone: {len(downloaded)}/{len(logs)} logs downloaded")
        return downloaded

    # ── Status ────────────────────────────────────────────────────────────────

    def get_connection_status(self) -> Dict:
        return {
            'connected':    self.is_connected,
            'vehicle_info': self.vehicle_info,
            'connection':   str(self.connection) if self.connection else None,
        }