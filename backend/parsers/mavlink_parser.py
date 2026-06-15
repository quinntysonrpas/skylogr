"""
MAVLink Telemetry Parser
Parses MAVLink telemetry log files (.tlog, .rlog)
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from .base_parser import BaseParser

try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False
    print("Warning: pymavlink not installed. MAVLink parsing will be limited.")

class MAVLinkParser(BaseParser):
    """Parser for MAVLink telemetry files"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.tlog', '.rlog', '.TLOG', '.RLOG']
        self.parser_name = "MAVLink Telemetry Parser"
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this is a MAVLink telemetry file"""
        if not PYMAVLINK_AVAILABLE:
            return False
        
        path = Path(file_path)
        
        if path.suffix.lower() not in ['.tlog', '.rlog']:
            return False
        
        if not path.exists() or path.stat().st_size < 100:
            return False
        
        try:
            # Try to open with mavutil
            mlog = mavutil.mavlink_connection(str(file_path))
            msg = mlog.recv_match(timeout=1)
            return msg is not None
        except Exception as e:
            print(f"Error checking MAVLink file {file_path}: {e}")
            return False
    
    def parse_file(self, file_path: str) -> Optional[Dict]:
        """Parse a MAVLink telemetry file"""
        if not PYMAVLINK_AVAILABLE:
            print("pymavlink not available. Cannot parse MAVLink files.")
            return None
        
        try:
            mlog = mavutil.mavlink_connection(str(file_path))
            
            flight_data = {
                'file_path': str(file_path),
                'file_name': Path(file_path).name,
                'manufacturer': 'ArduPilot',
                'parser_used': self.parser_name,
                'confidence': 'high'
            }
            
            # Extract flight statistics
            stats = self._extract_flight_stats(mlog)
            flight_data.update(stats)
            
            # Get drone model
            drone_model = self._extract_drone_model(mlog)
            flight_data['drone_model'] = drone_model
            
            # Get flight date
            date_info = self._extract_date(mlog, file_path)
            flight_data.update(date_info)
            
            # Validate
            if self._validate_parsed_data(flight_data):
                return flight_data
            else:
                return None
                
        except Exception as e:
            print(f"Error parsing MAVLink file {file_path}: {e}")
            return None
    
    def _extract_flight_stats(self, mlog) -> Dict:
        """Extract flight statistics from MAVLink messages"""
        stats = {
            'duration_minutes': 0,
            'max_altitude_m': 0,
            'max_speed_ms': 0,
            'distance_km': 0,
            'battery_start': None,
            'battery_end': None
        }
        
        try:
            first_timestamp = None
            last_timestamp = None
            max_alt = 0
            max_speed = 0
            first_battery = None
            last_battery = None
            
            # GPS coordinates
            first_gps = None
            last_gps = None
            
            # Reset to start of file
            mlog.rewind()
            
            # Process all messages
            while True:
                msg = mlog.recv_match(blocking=False)
                if msg is None:
                    break
                
                msg_type = msg.get_type()
                timestamp = getattr(msg, '_timestamp', None)
                
                # Track timestamps
                if timestamp:
                    if first_timestamp is None:
                        first_timestamp = timestamp
                    last_timestamp = timestamp
                
                # GPS data
                if msg_type == 'GLOBAL_POSITION_INT':
                    alt = getattr(msg, 'relative_alt', 0) / 1000.0  # mm to m
                    max_alt = max(max_alt, alt)
                    
                    # Track GPS positions
                    lat = getattr(msg, 'lat', 0) / 1e7
                    lon = getattr(msg, 'lon', 0) / 1e7
                    if first_gps is None and lat != 0 and lon != 0:
                        first_gps = {'lat': lat, 'lon': lon}
                    if lat != 0 and lon != 0:
                        last_gps = {'lat': lat, 'lon': lon}
                
                # VFR_HUD for speed
                elif msg_type == 'VFR_HUD':
                    speed = getattr(msg, 'groundspeed', 0)
                    max_speed = max(max_speed, speed)
                
                # Battery data
                elif msg_type == 'BATTERY_STATUS' or msg_type == 'SYS_STATUS':
                    if msg_type == 'BATTERY_STATUS':
                        battery = getattr(msg, 'battery_remaining', -1)
                    else:
                        battery = getattr(msg, 'battery_remaining', -1)
                    
                    if battery >= 0:
                        if first_battery is None:
                            first_battery = battery
                        last_battery = battery
            
            # Calculate duration
            if first_timestamp and last_timestamp:
                duration_sec = last_timestamp - first_timestamp
                stats['duration_minutes'] = round(duration_sec / 60, 1)
            
            # Set statistics
            stats['max_altitude_m'] = round(max_alt, 1)
            stats['max_speed_ms'] = round(max_speed, 1)
            
            # Estimate distance (speed * time)
            if stats['duration_minutes'] > 0 and max_speed > 0:
                avg_speed = max_speed * 0.6  # Rough average
                distance_m = stats['duration_minutes'] * 60 * avg_speed
                stats['distance_km'] = round(distance_m / 1000, 2)
            
            # Battery
            if first_battery is not None:
                stats['battery_start'] = int(first_battery)
            if last_battery is not None:
                stats['battery_end'] = int(last_battery)
            
            # GPS coordinates
            if first_gps:
                stats['location_start'] = first_gps
            if last_gps:
                stats['location_end'] = last_gps
            
        except Exception as e:
            print(f"Error extracting MAVLink stats: {e}")
        
        return stats
    
    def _extract_drone_model(self, mlog) -> str:
        """Extract drone/vehicle model from MAVLink messages"""
        try:
            mlog.rewind()
            
            # Look for AUTOPILOT_VERSION message
            msg = mlog.recv_match(type='AUTOPILOT_VERSION', blocking=False, timeout=5)
            if msg:
                # Get vehicle type
                vehicle_type = getattr(msg, 'vehicle_type', 0)
                
                vehicle_types = {
                    0: 'Generic',
                    1: 'Fixed Wing',
                    2: 'Quadrotor',
                    3: 'Coaxial',
                    4: 'Helicopter',
                    13: 'Hexarotor',
                    14: 'Octorotor',
                    19: 'VTOL',
                }
                
                vehicle_name = vehicle_types.get(vehicle_type, 'Unknown')
                return f'ArduPilot {vehicle_name}'
            
            # Fallback: check HEARTBEAT
            mlog.rewind()
            msg = mlog.recv_match(type='HEARTBEAT', blocking=False, timeout=5)
            if msg:
                mav_type = getattr(msg, 'type', 0)
                
                if mav_type == 2:
                    return 'ArduPilot Quadcopter'
                elif mav_type == 1:
                    return 'ArduPilot Fixed-Wing'
                elif mav_type == 10:
                    return 'ArduPilot Ground Rover'
                elif mav_type == 12:
                    return 'ArduPilot Submarine'
            
        except Exception as e:
            print(f"Error extracting drone model: {e}")
        
        return 'ArduPilot Vehicle'
    
    def _extract_date(self, mlog, file_path: str) -> Dict:
        """Extract flight date from MAVLink messages"""
        date_info = {}
        
        try:
            mlog.rewind()
            
            # Try to get GPS time
            msg = mlog.recv_match(type='SYSTEM_TIME', blocking=False, timeout=5)
            if msg:
                time_unix = getattr(msg, 'time_unix_usec', 0) / 1e6
                if time_unix > 0:
                    date_info['date'] = datetime.fromtimestamp(time_unix).isoformat()
                    date_info['timestamp'] = int(time_unix)
                    date_info['date_source'] = 'gps_time'
                    return date_info
            
            # Fallback to file modification time
            path = Path(file_path)
            mtime = path.stat().st_mtime
            date_info['date'] = datetime.fromtimestamp(mtime).isoformat()
            date_info['timestamp'] = int(mtime)
            date_info['date_source'] = 'file_metadata'
            
        except Exception as e:
            print(f"Error extracting date: {e}")
            date_info['date'] = datetime.now().isoformat()
            date_info['timestamp'] = int(datetime.now().timestamp())
            date_info['date_source'] = 'fallback'
        
        return date_info
    
    def batch_parse(self, directory: str) -> List[Dict]:
        """Parse all MAVLink files in a directory"""
        if not PYMAVLINK_AVAILABLE:
            return []
        
        directory_path = Path(directory)
        results = []
        
        for ext in ['.tlog', '.rlog', '.TLOG', '.RLOG']:
            for file_path in directory_path.rglob(f'*{ext}'):
                if self.can_parse(str(file_path)):
                    result = self.parse_file(str(file_path))
                    if result:
                        results.append(result)
        
        return results

# Made with Bob