"""
DJI Binary Parser
Wraps DJIFlightLogParser (which uses the MIT dji-log-parser Rust binary).

- Pre-v13 logs: parsed completely offline, no key needed
- v13+ logs:   one API call to DJI using the stored developer key,
               keychain cached locally — all future parses offline
"""

from pathlib import Path
from typing import Dict, List, Optional
from .base_parser import BaseParser


# DJI Fly filename prefix — highly reliable detection signal
DJI_FILENAME_PREFIX = 'DJIFlightRecord'

# Byte signatures found in DJI Fly .txt binary headers
DJI_FIRST_BYTE_SIGNATURES = {0x22, 0x29, 0x2A, 0x2B, 0x30, 0x31, 0x32}


class DJIBinaryParser(BaseParser):
    """
    Parser for DJI Fly app .txt log files using the dji-log-parser Rust binary.

    api_key and keychain_dir are set at construction time. The parser factory
    sets these from the app's encrypted config on startup.
    """

    def __init__(self, api_key: Optional[str] = None, keychain_dir: Optional[str] = None):
        super().__init__()
        self.supported_extensions = ['.txt']
        self.parser_name          = 'DJI Log Parser (MIT)'
        self.api_key              = api_key
        self.keychain_dir         = keychain_dir
        self._dji_parser          = None   # lazy-init to avoid binary download at startup

    def _get_parser(self):
        if self._dji_parser is None:
            from backend.dji_parser import DJIFlightLogParser
            self._dji_parser = DJIFlightLogParser(
                api_key      = self.api_key,
                keychain_dir = self.keychain_dir,
            )
        else:
            # Update API key in case it was set after construction
            self._dji_parser.api_key = self.api_key
        return self._dji_parser

    def update_api_key(self, api_key: Optional[str]):
        """Call this when the user saves a new DJI API key."""
        self.api_key = api_key
        if self._dji_parser is not None:
            self._dji_parser.api_key = api_key

    # ── Detection ──────────────────────────────────────────────────────────────

    def can_parse(self, file_path: str) -> bool:
        path = Path(file_path)

        if path.suffix.lower() != '.txt':
            return False

        # DJI Fly log filenames always start with DJIFlightRecord
        if path.name.startswith(DJI_FILENAME_PREFIX):
            return True

        if path.stat().st_size < 1000:
            return False

        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)

            # Check first-byte signatures
            if header and header[0] in DJI_FIRST_BYTE_SIGNATURES:
                return True

            # Version byte at offset 6 should be 1-30 for valid DJI Fly logs
            if len(header) >= 7 and 1 <= header[6] <= 30:
                # Also check that file isn't plain text (DJI logs are binary)
                ascii_ratio = sum(1 for b in header if 32 <= b < 127) / len(header)
                if ascii_ratio < 0.8:
                    return True

        except Exception:
            pass

        return False

    # ── Parse ──────────────────────────────────────────────────────────────────

    def parse_file(self, file_path: str) -> Optional[Dict]:
        try:
            return self._get_parser().parse_file(file_path)
        except Exception as e:
            print(f"[DJIBinaryParser] Error parsing {file_path}: {e}")
            return None

    def batch_parse(self, directory: str) -> List[Dict]:
        results = []
        root = Path(directory)
        for txt_file in sorted(root.rglob('*.txt')):
            if self.can_parse(str(txt_file)):
                result = self.parse_file(str(txt_file))
                if result:
                    results.append(result)
        return results

    # ── Helpers ────────────────────────────────────────────────────────────────

    def needs_api_key(self, file_path: str) -> bool:
        """True if this specific log is v13+ and has no cached keychain."""
        return self._get_parser().needs_api_key(file_path)

    def get_log_version(self, file_path: str) -> Optional[int]:
        from backend.dji_parser import DJIFlightLogParser
        return DJIFlightLogParser.detect_log_version(file_path)

    def is_binary_ready(self) -> bool:
        """True if the dji-log binary is already downloaded."""
        from backend.dji_parser import is_binary_available
        return is_binary_available()
