"""
DJI Flight Log Parser
Wraps the MIT-licensed dji-log-parser CLI binary (lvauvillier/dji-log-parser).

Key features:
  - Auto-downloads the correct dji-log binary for the user's OS/arch on first run
  - Result caching: parsed frames saved as .frames.json so API is only called once
  - Full telemetry: GPS track, altitude, speed, battery, home point, duration

User setup required:
  - Nothing for pre-v13 logs (Mini 2, Air 2S, Phantom 4, etc.) — fully automatic
  - Free DJI API key for v13+ logs (Mini 3/4, Air 3, Avata 2, etc.)
    Get one free at: https://developer.dji.com  (Open API app type → SDK key)
    Key is only used once per log file — result cached locally after that.

Binary license: MIT (lvauvillier/dji-log-parser)
"""

import json
import os
import platform
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

# ── Release config ─────────────────────────────────────────────────────────────
GITHUB_REPO    = 'lvauvillier/dji-log-parser'
LATEST_RELEASE = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'

_ASSET_MAP = {
    ('Windows', 'AMD64'):   'dji-log-x86_64-pc-windows-msvc.zip',
    ('Windows', 'x86_64'):  'dji-log-x86_64-pc-windows-msvc.zip',
    ('Darwin',  'arm64'):   'dji-log-aarch64-apple-darwin.tar.gz',
    ('Darwin',  'x86_64'):  'dji-log-x86_64-apple-darwin.tar.gz',
    ('Linux',   'aarch64'): 'dji-log-aarch64-unknown-linux-gnu.tar.gz',
    ('Linux',   'x86_64'):  'dji-log-x86_64-unknown-linux-musl.tar.gz',
    ('Linux',   'armv7l'):  'dji-log-armv7-unknown-linux-gnueabihf.tar.gz',
}

BINARY_NAME      = 'dji-log.exe' if platform.system() == 'Windows' else 'dji-log'
CACHE_SUFFIX     = '.frames.json'   # local cache of parsed frames (avoids re-calling binary)
PARSE_TIMEOUT    = 90   # seconds per file
DOWNLOAD_TIMEOUT = 60   # seconds for binary download


# ── Binary auto-download ───────────────────────────────────────────────────────

def _default_binary_dir() -> Path:
    return Path(__file__).parent / '_dji_bin'


def _asset_name() -> str:
    system  = platform.system()
    machine = platform.machine()
    name = _ASSET_MAP.get((system, machine))
    if not name:
        raise RuntimeError(
            f"Unsupported platform: {system} {machine}. "
            f"Supported: {list(_ASSET_MAP.keys())}"
        )
    return name


def _fetch_latest_download_url() -> str:
    req = urllib.request.Request(
        LATEST_RELEASE,
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'skylogr-drone-logbook'}
    )
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
        data = json.loads(resp.read())

    wanted = _asset_name()
    for asset in data.get('assets', []):
        if asset['name'] == wanted:
            return asset['browser_download_url']

    raise RuntimeError(
        f"Asset '{wanted}' not found in latest release. "
        f"Available: {[a['name'] for a in data.get('assets', [])]}"
    )


def _extract_binary(archive_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)

    if archive_path.suffix == '.zip':
        with zipfile.ZipFile(archive_path) as zf:
            for member in zf.namelist():
                if member.endswith(BINARY_NAME) or member == BINARY_NAME:
                    zf.extract(member, dest_dir)
                    extracted = dest_dir / member
                    final = dest_dir / BINARY_NAME
                    if extracted != final:
                        extracted.rename(final)
                    return final
    else:
        with tarfile.open(archive_path, 'r:gz') as tf:
            for member in tf.getmembers():
                if member.name.endswith(BINARY_NAME) or member.name == BINARY_NAME:
                    member.name = BINARY_NAME
                    tf.extract(member, dest_dir)
                    return dest_dir / BINARY_NAME

    raise RuntimeError(f"Could not find '{BINARY_NAME}' inside {archive_path.name}")


def download_binary(
    dest_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    def _log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(f"[dji-log setup] {msg}")

    out_dir = Path(dest_dir) if dest_dir else _default_binary_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    binary  = out_dir / BINARY_NAME

    if binary.exists():
        _log(f"Binary already present at {binary}")
        return binary

    _log("Checking GitHub for latest dji-log-parser release...")
    url = _fetch_latest_download_url()
    _log(f"Downloading {_asset_name()} ...")

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / _asset_name()

        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as resp:
            total      = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 65536
            with open(archive, 'wb') as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded / total * 100)
                        _log(f"  {pct}%  ({downloaded // 1024}KB / {total // 1024}KB)")

        _log("Extracting...")
        extracted = _extract_binary(archive, out_dir)

    if platform.system() != 'Windows':
        extracted.chmod(extracted.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    _log(f"Ready: {extracted}")
    return extracted


def ensure_binary(
    binary_path: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    if binary_path:
        p = Path(binary_path)
        if p.exists():
            return str(p)

    default = _default_binary_dir() / BINARY_NAME
    if default.exists():
        return str(default)

    import shutil
    on_path = shutil.which('dji-log')
    if on_path:
        return on_path

    return str(download_binary(progress_callback=progress_callback))


def is_binary_available() -> bool:
    """Check whether the dji-log binary is already downloaded (no network needed)."""
    import shutil
    return (_default_binary_dir() / BINARY_NAME).exists() or bool(shutil.which('dji-log'))


# ── Main parser class ──────────────────────────────────────────────────────────

class DJIFlightLogParser:
    """
    Full-fidelity DJI .txt flight log parser.

    On first use, automatically downloads the correct dji-log binary for the
    user's OS. No manual setup required except a DJI API key for v13+ logs.

    Usage:
        parser = DJIFlightLogParser(api_key='YOUR_SDK_KEY')
        result = parser.parse_file('DJIFlightRecord_2025-01-15.txt')
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        binary_path: Optional[str] = None,
        keychain_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.api_key      = api_key
        self.keychain_dir = Path(keychain_dir) if keychain_dir else None
        self._binary_path = binary_path
        self._binary      = None
        self._progress_cb = progress_callback

    def _get_binary(self) -> str:
        if self._binary is None:
            self._binary = ensure_binary(
                binary_path       = self._binary_path,
                progress_callback = self._progress_cb,
            )
        return self._binary

    def _cache_path(self, log_path: Path) -> Optional[Path]:
        """Path to the local frames cache file, or None if no cache dir configured."""
        if self.keychain_dir:
            d = Path(self.keychain_dir)
            d.mkdir(parents=True, exist_ok=True)
            return d / (log_path.stem + CACHE_SUFFIX)
        return None

    @staticmethod
    def detect_log_version(file_path: str) -> Optional[int]:
        """
        Read the log version from byte offset 6.
        < 13  → unencrypted, fully offline, no key needed
        >= 13 → AES encrypted, needs --api-key on first parse
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
            if len(header) >= 7:
                return header[6]
        except Exception:
            pass
        return None

    def needs_api_key(self, file_path: str) -> bool:
        """True if v13+ AND no cached frames (meaning we'd need a live API call)."""
        version = self.detect_log_version(file_path)
        if version is None or version < 13:
            return False
        cache = self._cache_path(Path(file_path))
        if cache and cache.exists():
            return False          # already parsed once, cache handles it
        return not bool(self.api_key)

    # ── Core parse ─────────────────────────────────────────────────────────────

    def _run_binary(self, file_path: str) -> Optional[List[dict]]:
        """
        Run dji-log binary and return raw frames list, or None on failure.

        Result is cached as a local .frames.json file so the binary (and any
        DJI API call for v13+ logs) only runs once per log file.
        """
        path   = Path(file_path)
        binary = self._get_binary()
        cache  = self._cache_path(path)

        # ── Return cached frames if available ──────────────────────────────
        if cache and cache.exists():
            try:
                cached = json.loads(cache.read_text(encoding='utf-8'))
                if isinstance(cached, list) and cached:
                    return cached
                else:
                    # Cache contains a non-list (e.g. dict from a previous broken parse)
                    print(f"[DJIParser] Stale/bad cache for '{path.name}' — deleting and re-parsing")
                    cache.unlink(missing_ok=True)
            except Exception:
                cache.unlink(missing_ok=True)  # corrupt JSON — delete and re-parse

        # ── Build command ──────────────────────────────────────────────────
        # Actual CLI: dji-log.exe [--api-key <KEY>] <FILE>
        # Binary outputs normalised JSON frames to stdout by default.
        cmd = [binary]
        if self.api_key:
            cmd += ['--api-key', self.api_key]
        cmd.append(str(path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=PARSE_TIMEOUT,
            )
        except FileNotFoundError:
            print(f"[DJIParser] Binary not found: {binary}")
            return None
        except subprocess.TimeoutExpired:
            print(f"[DJIParser] Timeout parsing {path.name}")
            return None

        if result.returncode != 0:
            stderr  = result.stderr.strip()
            version = self.detect_log_version(file_path)
            if version is not None and version >= 13 and not self.api_key:
                print(
                    f"[DJIParser] '{path.name}' is v{version} (encrypted). "
                    f"Add your DJI API key in Profile → DJI Settings to parse it."
                )
            else:
                print(f"[DJIParser] Parse failed for '{path.name}': {stderr}")
            return None

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            print(f"[DJIParser] Bad JSON for '{path.name}': {e}")
            print(f"[DJIParser] stdout (first 400 chars): {result.stdout[:400]!r}")
            return None

        # ── Normalise output: binary may return a list or a wrapped dict ───
        if isinstance(output, list):
            frames = output
        elif isinstance(output, dict):
            # Try common wrapper keys
            found = None
            for key in ('frames', 'records', 'data', 'logs', 'items', 'flightLogs'):
                val = output.get(key)
                if isinstance(val, list) and val:
                    found = (key, val)
                    break
            if found:
                print(f"[DJIParser] '{path.name}': reading frames from top-level key '{found[0]}'")
                frames = found[1]
            else:
                # Not a recognised wrapper — log the structure so we can fix it
                print(
                    f"[DJIParser] '{path.name}': binary returned a JSON object with keys "
                    f"{list(output.keys())[:15]} — expected a list of frames. "
                    f"First 400 chars: {result.stdout[:400]!r}"
                )
                return None
        else:
            print(f"[DJIParser] '{path.name}': unexpected JSON type {type(output).__name__}")
            return None

        if not frames:
            print(f"[DJIParser] No frames in '{path.name}'")
            return None

        print(f"[DJIParser] '{path.name}': parsed {len(frames)} frames")

        # ── Cache result so future imports are instant + offline ───────────
        if cache:
            try:
                cache.write_text(json.dumps(frames), encoding='utf-8')
            except Exception:
                pass

        return frames

    def parse_file(self, file_path: str) -> Optional[dict]:
        """Parse a DJI .txt log. Returns flight summary dict or None."""
        path   = Path(file_path)
        frames = self._run_binary(file_path)
        if frames is None:
            return None
        try:
            return self._build_result(frames, path)
        except Exception as e:
            import traceback
            print(f"[DJIParser] _build_result failed for '{path.name}': {e}")
            traceback.print_exc()
            return None

    # ── Result builder ─────────────────────────────────────────────────────────

    @staticmethod
    def _g(frame: dict, *keys, default=None):
        """Safe nested getter: _g(frame, 'osd', 'height') → frame['osd']['height']."""
        obj = frame
        for k in keys:
            if not isinstance(obj, dict):
                return default
            obj = obj.get(k)
            if obj is None:
                return default
        return obj

    def _build_result(self, frames: List[dict], path: Path) -> dict:
        """
        Build a complete flight result dict from raw frames.

        Frame structure (from dji-log-parser):
          frame.osd.flyTime   — seconds elapsed
          frame.osd.height    — relative altitude above home (metres)
          frame.osd.latitude/longitude
          frame.osd.xSpeed/ySpeed — m/s components
          frame.battery.chargeLevel — percent
          frame.battery.voltage     — volts (already V)
          frame.battery.current     — amps (already A)
          frame.recover.aircraftName
          frame.custom.dateTime     — ISO string (often epoch; fall back to filename)
        """
        import re
        from math import radians, cos, sin, asin, sqrt

        g = self._g
        first = frames[0]
        last  = frames[-1]

        # ── Date ──────────────────────────────────────────────────────────────
        # custom.dateTime is frequently '1970-01-01T00:00:00Z' for DJI logs,
        # so we prefer the filename date which is always accurate.
        date_iso = None
        m = re.search(r'(\d{4}-\d{2}-\d{2})_\[(\d{2}-\d{2}-\d{2})\]', path.name)
        if m:
            date_iso = f"{m.group(1)}T{m.group(2).replace('-', ':')}"
        else:
            raw_dt = g(first, 'custom', 'dateTime')
            if raw_dt and '1970' not in str(raw_dt):
                date_iso = raw_dt

        # ── Duration ──────────────────────────────────────────────────────────
        flight_time_s = float(g(last, 'osd', 'flyTime') or 0)

        # ── Drone identity ────────────────────────────────────────────────────
        # `recover` (aircraft name/serial) is frequently blank in the opening
        # frames and only gets populated partway through the flight once the
        # app/aircraft handshake completes — scan all frames for the first
        # frame where it's actually filled in, rather than trusting frame[0].
        def _first_recover(key):
            for fr in frames:
                v = g(fr, 'recover', key)
                if v:
                    return v
            return None

        drone_model = (_first_recover('aircraftName')
                       or g(first, 'osd', 'droneType')
                       or 'DJI Unknown')
        aircraft_sn = _first_recover('aircraftSn') or ''

        # ── Pass over all frames for stats ────────────────────────────────────
        altitudes   = []
        speeds      = []
        battery     = []
        start_lat = start_lon = end_lat = end_lon = None
        max_dist_km = 0.0

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371.0
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
            return 2 * R * asin(sqrt(max(0.0, min(1.0, a))))

        for f in frames:
            h = g(f, 'osd', 'height')
            if h is not None and h > 0:
                altitudes.append(h)

            vx = g(f, 'osd', 'xSpeed') or 0.0
            vy = g(f, 'osd', 'ySpeed') or 0.0
            spd = (vx ** 2 + vy ** 2) ** 0.5
            if spd > 0:
                speeds.append(spd)

            cl = g(f, 'battery', 'chargeLevel')
            if cl is not None:
                battery.append(int(cl))

            lat = g(f, 'osd', 'latitude')
            lon = g(f, 'osd', 'longitude')
            if lat and lon and abs(lat) > 0.0001:
                if start_lat is None:
                    start_lat, start_lon = lat, lon
                end_lat, end_lon = lat, lon
                if start_lat:
                    d = haversine(start_lat, start_lon, lat, lon)
                    if d > max_dist_km:
                        max_dist_km = d

        # ── Telemetry profiles for charts (max ~500 points each) ──────────────
        n        = max(1, len(frames) // 500)
        n_gps    = max(1, len(frames) // 200)
        altitude_profile      = []
        speed_profile         = []
        vertical_speed_profile = []
        attitude_profile      = []
        gimbal_profile        = []
        battery_profile       = []
        gps_track             = []
        prev_gps              = None

        for i, f in enumerate(frames):
            # app.py chart code does p['time'] / 60, so store time in seconds
            t_sec = round(float(g(f, 'osd', 'flyTime') or 0), 1)

            if i % n == 0:
                h = g(f, 'osd', 'height')
                if h is not None and h < 2000:   # filter GPS-glitch outliers
                    altitude_profile.append({'time': t_sec, 'alt': round(h, 1)})

                vx  = g(f, 'osd', 'xSpeed') or 0.0
                vy  = g(f, 'osd', 'ySpeed') or 0.0
                spd = (vx ** 2 + vy ** 2) ** 0.5
                if spd < 200:                    # filter GPS-glitch spikes
                    speed_profile.append({'time': t_sec, 'speed': round(spd, 2)})

                vz = g(f, 'osd', 'zSpeed')
                if vz is not None and abs(vz) < 50:
                    vertical_speed_profile.append({'time': t_sec, 'vspeed': round(vz, 2)})

                # Aircraft attitude (airframe pitch/roll/yaw, from the OSD — not the gimbal)
                ap = g(f, 'osd', 'pitch')
                ar = g(f, 'osd', 'roll')
                ay = g(f, 'osd', 'yaw')
                if any(v is not None for v in [ap, ar, ay]):
                    att_entry = {'time': t_sec}
                    if ap is not None: att_entry['pitch'] = round(ap, 1)
                    if ar is not None: att_entry['roll']  = round(ar, 1)
                    if ay is not None: att_entry['yaw']   = round(ay, 1)
                    attitude_profile.append(att_entry)

                # Gimbal — try both direct and 'Actual' field variants
                # NOTE: must use explicit None check — `0.0 or fallback` would wrongly drop 0
                def _gim(key, fallback):
                    v = g(f, 'gimbal', key)
                    return v if v is not None else g(f, 'gimbal', fallback)
                gp = _gim('pitch', 'pitchActual')
                gr = _gim('roll',  'rollActual')
                gy = _gim('yaw',   'yawActual')
                if any(v is not None for v in [gp, gr, gy]):
                    gp_entry = {'time': t_sec}
                    if gp is not None: gp_entry['pitch'] = round(gp, 1)
                    if gr is not None: gp_entry['roll']  = round(gr, 1)
                    if gy is not None: gp_entry['yaw']   = round(gy, 1)
                    gimbal_profile.append(gp_entry)

                v   = g(f, 'battery', 'voltage')
                cur = g(f, 'battery', 'current')
                cl  = g(f, 'battery', 'chargeLevel')
                tmp = g(f, 'battery', 'temperature')
                if any(x is not None for x in [v, cur, cl, tmp]):
                    bp = {'time': t_sec}
                    if v   is not None: bp['voltage']     = round(v, 2)
                    if cur is not None: bp['current']     = round(cur, 2)
                    if cl  is not None: bp['remaining']   = int(cl)
                    if tmp is not None: bp['temperature'] = round(tmp, 1)
                    battery_profile.append(bp)

            if i % n_gps == 0:
                lat = g(f, 'osd', 'latitude')
                lon = g(f, 'osd', 'longitude')
                if lat and lon and abs(lat) > 0.0001 and (lat, lon) != prev_gps:
                    gps_track.append({
                        'lat': round(lat, 7),
                        'lon': round(lon, 7),
                        'alt': round(g(f, 'osd', 'height') or 0, 1),
                    })
                    prev_gps = (lat, lon)

        # ── Force ground-level endpoint so charts always return to 0 ─────────
        # Sampling skips the last N frames; explicitly anchor the final timestamp.
        last_t = round(float(g(frames[-1], 'osd', 'flyTime') or 0), 1)
        if altitude_profile and altitude_profile[-1]['time'] < last_t:
            altitude_profile.append({'time': last_t, 'alt': 0.0})
        if speed_profile and speed_profile[-1]['time'] < last_t:
            speed_profile.append({'time': last_t, 'speed': 0.0})
        if vertical_speed_profile and vertical_speed_profile[-1]['time'] < last_t:
            vertical_speed_profile.append({'time': last_t, 'vspeed': 0.0})

        # ── Version / confidence ──────────────────────────────────────────────
        version       = self.detect_log_version(str(path))
        cache         = self._cache_path(path)
        frames_cached = bool(cache and cache.exists())

        raw_data = {
            'altitude_profile':       altitude_profile,
            'speed_profile':          speed_profile,
            'vertical_speed_profile': vertical_speed_profile,
            'attitude_profile':       attitude_profile,
            'gimbal_profile':         gimbal_profile,
            'battery_profile':        battery_profile,
            'gps_track':              gps_track,
        }

        return {
            'file_path':    str(path),
            'file_name':    path.name,
            'manufacturer': 'DJI',
            'drone_model':  drone_model,
            'aircraft_sn':  aircraft_sn,

            'date':             date_iso,
            'duration_seconds': int(flight_time_s),
            'duration_minutes': round(flight_time_s / 60, 1),

            'max_altitude_m': round(max(altitudes), 1) if altitudes else 0,
            'max_speed_ms':   round(max(speeds),    2) if speeds    else 0,
            'distance_km':    round(max_dist_km,    2),

            'battery_start': battery[0]  if battery else None,
            'battery_end':   battery[-1] if battery else None,

            'location_start_lat': start_lat,
            'location_start_lon': start_lon,
            'location_end_lat':   end_lat,
            'location_end_lon':   end_lon,

            'parser_used':   'DJI Log Parser (MIT)',
            'confidence':    'high' if frames_cached or (version is not None and version < 13) else 'medium',
            'log_version':   version,
            'frame_count':   len(frames),
            'frames_cached': frames_cached,

            'raw_data': json.dumps(raw_data),
        }

    def batch_parse(self, directory: str, api_key: Optional[str] = None) -> List[dict]:
        """Parse all DJI .txt logs in a directory. Returns list of result dicts."""
        if api_key:
            self.api_key = api_key
        root    = Path(directory)
        files   = sorted(root.rglob('*.txt'))
        results = []
        for log_path in files:
            result = self.parse_file(str(log_path))
            if result:
                results.append(result)
        return results
