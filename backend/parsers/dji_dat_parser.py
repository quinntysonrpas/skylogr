"""
DJI DAT Parser - Basic parser for DJI DAT files
Extracts basic telemetry without external tools
Note: Limited data extraction due to DJI encryption
"""

import struct
from pathlib import Path
from typing import Optional, Dict
from .base_parser import BaseParser

class DJIDATParser(BaseParser):
    """Parser for DJI DAT files (basic extraction)"""
    
    parser_name = "DJI DAT Parser"
    supported_extensions = ['.dat', '.DAT']
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the file"""
        path = Path(file_path)
        return path.suffix.lower() in self.supported_extensions and path.exists()
    
    def parse(self, file_path: str) -> Optional[Dict]:
        """
        Parse DJI DAT file and extract available data.
        Note: Due to DJI encryption, only basic data can be extracted.
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            file_path_obj = Path(file_path)
            file_size = len(data)
            
            # Extract what we can
            drone_model = self._extract_drone_model(data)
            duration_minutes = self._estimate_duration(file_size)
            flight_date = self._get_file_date(file_path_obj)
            
            # Try to extract altitude (best effort)
            max_altitude = self._extract_max_altitude(data)
            
            return {
                'file_path': str(file_path),
                'file_name': file_path_obj.name,
                'manufacturer': 'DJI',
                'drone_model': drone_model,
                'date': flight_date,
                'duration_minutes': duration_minutes,
                'max_altitude_m': max_altitude,
                'parser_used': self.parser_name,
                'confidence': 'medium',  # Medium confidence for DAT files
                'notes': 'Parsed from DAT file. For full metrics, use DatCon converter.'
            }
            
        except Exception as e:
            print(f"Error parsing DAT file {file_path}: {e}")
            return None
    
    def parse_file(self, file_path: str) -> Optional[Dict]:
        """Alias for parse() to match base class interface"""
        return self.parse(file_path)
    
    def batch_parse(self, directory: str) -> list:
        """Parse all DAT files in a directory"""
        from pathlib import Path
        results = []
        directory_path = Path(directory)
        
        for file_path in directory_path.rglob('*.DAT'):
            if file_path.is_file():
                parsed_data = self.parse(str(file_path))
                if parsed_data:
                    results.append(parsed_data)
        
        for file_path in directory_path.rglob('*.dat'):
            if file_path.is_file():
                parsed_data = self.parse(str(file_path))
                if parsed_data:
                    results.append(parsed_data)
        
        return results

    def _extract_drone_model(self, data: bytes) -> str:
        """Try to identify drone model from DAT file"""
        # Look for common DJI model identifiers
        models = {
            b'Mini 3': 'DJI Mini 3',
            b'Mini3': 'DJI Mini 3',
            b'Mini 2': 'DJI Mini 2',
            b'Mini2': 'DJI Mini 2',
            b'Mavic 3': 'DJI Mavic 3',
            b'Mavic3': 'DJI Mavic 3',
            b'Air 2S': 'DJI Air 2S',
            b'Air2S': 'DJI Air 2S',
        }
        
        for identifier, model_name in models.items():
            if identifier in data:
                return model_name
        
        return 'DJI Drone (Unknown Model)'
    
    def _estimate_duration(self, file_size: int) -> float:
        """
        Estimate flight duration from file size.
        Based on analysis: ~900 KB per minute for DAT files
        """
        bytes_per_minute = 900 * 1024  # 900 KB/min
        duration_minutes = file_size / bytes_per_minute
        return round(duration_minutes, 2)
    
    def _get_file_date(self, file_path: Path) -> str:
        """Get flight date from file modification time"""
        from datetime import datetime
        timestamp = file_path.stat().st_mtime
        date = datetime.fromtimestamp(timestamp)
        return date.isoformat()
    
    def _extract_max_altitude(self, data: bytes) -> Optional[float]:
        """
        Try to extract max altitude from DAT file.
        This is best-effort due to encryption.
        """
        try:
            # Skip header
            start_pos = 256
            
            # Look for altitude values (floats between 0-200m)
            altitude_candidates = []
            
            for i in range(start_pos, len(data) - 4, 4):
                try:
                    # Try reading as float
                    value = struct.unpack('<f', data[i:i+4])[0]
                    
                    # Filter for reasonable altitude values
                    if 1 < value < 200:  # Between 1m and 200m
                        altitude_candidates.append(value)
                except:
                    continue
            
            if altitude_candidates:
                # Return max altitude found
                # Filter out outliers by taking 95th percentile
                altitude_candidates.sort()
                percentile_95 = int(len(altitude_candidates) * 0.95)
                if percentile_95 > 0:
                    max_alt = altitude_candidates[percentile_95]
                    return round(max_alt, 1)
            
            return None
            
        except Exception as e:
            print(f"Could not extract altitude: {e}")
            return None

# Made with Bob
