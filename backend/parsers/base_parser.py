"""
Base Parser Class
All flight log parsers inherit from this
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pathlib import Path

class BaseParser(ABC):
    """Abstract base class for flight log parsers"""
    
    def __init__(self):
        self.supported_extensions = []
        self.parser_name = "Base Parser"
    
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """
        Check if this parser can handle the given file
        Returns True if the file format is supported
        """
        pass
    
    @abstractmethod
    def parse_file(self, file_path: str) -> Optional[Dict]:
        """
        Parse a flight log file
        Returns a dictionary with standardized flight information or None if parsing fails
        
        Standard format:
        {
            'file_path': str,
            'file_name': str,
            'manufacturer': str,
            'drone_model': str,
            'date': str (ISO format),
            'duration_minutes': float,
            'distance_km': float (optional),
            'max_altitude_m': float (optional),
            'max_speed_ms': float (optional),
            'battery_start': int (optional),
            'battery_end': int (optional),
            'location_start': {'lat': float, 'lon': float} (optional),
            'location_end': {'lat': float, 'lon': float} (optional),
            'parser_used': str,
            'confidence': str ('high', 'medium', 'low')
        }
        """
        pass
    
    @abstractmethod
    def batch_parse(self, directory: str) -> List[Dict]:
        """
        Parse all compatible files in a directory
        Returns a list of parsed flight data dictionaries
        """
        pass
    
    def _validate_parsed_data(self, data: Dict) -> bool:
        """Validate that parsed data has required fields"""
        required_fields = ['file_path', 'file_name', 'manufacturer', 'drone_model', 'date']
        return all(field in data for field in required_fields)

# Made with Bob
