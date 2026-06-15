"""
Parser Factory
Automatically detects and selects the appropriate parser for a given file.
"""

from typing import Optional, List, Dict
from pathlib import Path
from .base_parser import BaseParser
from .dji_binary_parser import DJIBinaryParser
from .dji_fly_parser import DJIFlyParser
from .dji_dat_parser import DJIDATParser
from .airdata_csv_parser import AirdataCSVParser
from .ardupilot_parser import ArduPilotParser
from .mavlink_parser import MAVLinkParser


class ParserFactory:
    """Factory class that manages and selects the appropriate parser for each file."""

    def __init__(self, dji_api_key: Optional[str] = None, dji_keychain_dir: Optional[str] = None):
        # DJIBinaryParser uses the MIT dji-log-parser Rust binary.
        # It handles pre-v13 offline and v13+ with a one-time API call.
        self.dji_binary_parser = DJIBinaryParser(
            api_key      = dji_api_key,
            keychain_dir = dji_keychain_dir,
        )

        # Parser order: most reliable / most specific first.
        # DJIBinaryParser must come before DJIFlyParser so that .txt files
        # with DJI signatures go through the proper parser, not the estimator.
        self.parsers: List[BaseParser] = [
            AirdataCSVParser(),          # Airdata UAV CSV — highest fidelity
            MAVLinkParser(),             # MAVLink .tlog/.rlog
            ArduPilotParser(),           # ArduPilot .bin
            self.dji_binary_parser,      # DJI Fly .txt via dji-log-parser (MIT)
            DJIFlyParser(),              # Legacy DJI Fly estimator (fallback only)
            DJIDATParser(),              # DJI .dat (basic extraction)
        ]

    def set_dji_api_key(self, api_key: Optional[str]):
        """Update the DJI API key at runtime (e.g. after user saves it in Profile)."""
        self.dji_binary_parser.update_api_key(api_key)

    def get_parser(self, file_path: str) -> Optional[BaseParser]:
        for parser in self.parsers:
            try:
                if parser.can_parse(file_path):
                    return parser
            except Exception:
                continue
        return None

    def parse_file(self, file_path: str) -> Optional[Dict]:
        parser = self.get_parser(file_path)
        if parser:
            return parser.parse_file(file_path)
        return None

    def batch_parse(self, directory: str) -> List[Dict]:
        results = []
        for file_path in Path(directory).rglob('*'):
            if file_path.is_file():
                parsed = self.parse_file(str(file_path))
                if parsed:
                    results.append(parsed)
        return results

    def get_supported_formats(self) -> List[Dict[str, str]]:
        return [
            {'parser_name': p.parser_name, 'extensions': p.supported_extensions}
            for p in self.parsers
        ]
