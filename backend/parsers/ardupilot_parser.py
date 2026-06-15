"""
ArduPilot/Mission Planner BIN Parser
Parses ArduPilot binary log files (.bin)
Much easier to parse than DJI logs - open format!
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import struct
from .base_parser import BaseParser

try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False
    print("Warning: pymavlink not available. ArduPilot parsing will be less accurate.")

class ArduPilotParser(BaseParser):
    """Parser for ArduPilot/PX4 binary log files"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.bin', '.BIN']
        self.parser_name = "ArduPilot BIN Parser"
        
        # ArduPilot log message types
        self.MSG_TYPES = {
            0x80: 'FMT',   # Format definition
            0x81: 'PARM',  # Parameter
            0x82: 'GPS',   # GPS data
            0x83: 'IMU',   # IMU data
            0x84: 'MSG',   # Text message
            0x85: 'CMD',   # Command
            0x86: 'RADIO', # Radio
            0x87: 'BARO',  # Barometer
            0x88: 'POWR',  # Power status
            0x89: 'AHR2',  # AHRS2
            0x8A: 'SIMSTATE', # Simulation state
            0x8B: 'EKF1',  # EKF1
            0x8C: 'EKF2',  # EKF2
            0x8D: 'EKF3',  # EKF3
            0x8E: 'EKF4',  # EKF4
            0x8F: 'TERR',  # Terrain
            0x90: 'GPS2',  # GPS2
            0x91: 'MODE',  # Mode change
        }
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this is an ArduPilot BIN file"""
        path = Path(file_path)
        
        if path.suffix.lower() not in self.supported_extensions:
            return False
        
        if not path.exists() or path.stat().st_size < 100:
            return False
        
        try:
            with open(file_path, 'rb') as f:
                # ArduPilot logs start with FMT messages
                header = f.read(100)
                
                # Check for ArduPilot signature
                # First byte is usually 0xA3 (log header) or 0x80 (FMT message)
                if header[0] in [0xA3, 0x80]:
                    return True
                
                # Alternative check: look for "FMT" string in first 200 bytes
                if b'FMT' in header or b'ArduPilot' in header:
                    return True
                    
        except Exception as e:
            print(f"Error checking ArduPilot file {file_path}: {e}")
        
        return False
    
    def parse_file(self, file_path: str) -> Optional[Dict]:
        """Parse an ArduPilot BIN file"""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            if len(data) < 100:
                return None
            
            flight_data = {
                'file_path': str(file_path),
                'file_name': Path(file_path).name,
                'manufacturer': 'ArduPilot',
                'parser_used': self.parser_name,
                'confidence': 'high'
            }
            
            # Extract flight information (includes date from GPS if available)
            stats = self._extract_flight_stats(data)
            flight_data.update(stats)
            
            # Get drone model from parameters
            drone_model = self._extract_drone_model(data)
            flight_data['drone_model'] = drone_model
            
            # Get flight date - only use fallback if not already set by GPS
            # Check both existence and if it's from GPS (not file metadata)
            if 'date' not in flight_data or flight_data.get('date_source') != 'gps_time':
                date_info = self._extract_date(data, file_path)
                # Only update if we don't have GPS time
                if flight_data.get('date_source') != 'gps_time':
                    flight_data.update(date_info)
            
            # Validate
            if self._validate_parsed_data(flight_data):
                return flight_data
            else:
                return None
                
        except Exception as e:
            print(f"Error parsing ArduPilot file {file_path}: {e}")
            return None
    
    def _extract_flight_stats(self, data: bytes) -> Dict:
        """Extract flight statistics from log data"""
        stats = {
            'duration_minutes': 0.0,
            'max_altitude_m': 0.0,
            'max_speed_ms': 0.0,
            'distance_km': 0.0
        }
        
        try:
            if PYMAVLINK_AVAILABLE:
                # Use pymavlink for accurate parsing
                stats = self._extract_stats_with_pymavlink(data)
            else:
                # Fallback to estimation method
                stats = self._extract_stats_fallback(data)
            
        except Exception as e:
            print(f"Error extracting flight stats: {e}")
            # Try fallback method
            try:
                stats = self._extract_stats_fallback(data)
            except:
                pass
        
        return stats
    
    def _extract_stats_with_pymavlink(self, data: bytes) -> Dict:
        """Extract comprehensive stats using pymavlink library"""
        import tempfile
        import os
        import json
        from math import radians, cos, sin, asin, sqrt
        from datetime import datetime, timedelta
        
        stats = {
            'duration_minutes': 0.0,
            'max_altitude_m': 0.0,
            'max_speed_ms': 0.0,
            'distance_km': 0.0,
            'battery_start': None,
            'battery_end': None,
            'location_start_lat': None,
            'location_start_lon': None,
            'location_end_lat': None,
            'location_end_lon': None,
        }
        
        # Write data to temp file (pymavlink needs a file path)
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.bin', delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        
        try:
            # Open with pymavlink
            mlog = mavutil.mavlink_connection(tmp_path)
            
            # Track data
            first_timestamp = None
            last_timestamp = None
            altitudes = []
            speeds = []
            gps_points = []
            battery_samples = []
            flight_date = None
            home_altitude = None  # Track starting altitude for relative altitude
            
            # For detailed telemetry storage
            gps_track = []  # For flight path
            altitude_profile = []
            speed_profile = []
            
            # Comprehensive telemetry profiles
            battery_profile = []  # Voltage, current, remaining %
            motor_profile = []    # Motor outputs (PWM/throttle)
            vibration_profile = []  # X/Y/Z vibration
            attitude_profile = []  # Roll, pitch, yaw
            mode_changes = []     # Flight mode timeline
            
            # Read all messages
            while True:
                msg = mlog.recv_match(blocking=False)
                if msg is None:
                    break
                
                # Get timestamp
                if hasattr(msg, 'TimeUS'):
                    if first_timestamp is None:
                        first_timestamp = msg.TimeUS
                    last_timestamp = msg.TimeUS
                
                # Extract barometric altitude (BARO only - most accurate and consistent)
                if msg.get_type() == 'BARO':
                    if hasattr(msg, 'Alt') and msg.Alt is not None:
                        alt_m = msg.Alt  # Already in meters
                        
                        # Set home altitude from first reading
                        if home_altitude is None:
                            home_altitude = alt_m
                        
                        # Calculate relative altitude (starts at 0)
                        relative_alt = alt_m - home_altitude
                        
                        # Only accept positive altitudes (above home point)
                        if 0 <= relative_alt < 1000:
                            altitudes.append(relative_alt)
                            # Store altitude profile (sample every 10th point to keep size manageable)
                            if len(altitudes) % 10 == 0:  # Sample every 10th reading
                                altitude_profile.append({
                                    'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                                    'alt': round(relative_alt, 1)
                                })
                
                # Extract airspeed from ARSP message (more accurate for fast flight)
                if msg.get_type() == 'ARSP':
                    if hasattr(msg, 'Airspeed') and msg.Airspeed is not None:
                        speed_ms = abs(msg.Airspeed)  # Use absolute value
                        if 0.1 <= speed_ms < 100:  # Ignore very low speeds (noise)
                            speeds.append(speed_ms)
                            if len(speeds) % 10 == 0:
                                speed_profile.append({
                                    'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                                    'speed': round(speed_ms, 2)
                                })
                
                # Extract velocity from EKF (Extended Kalman Filter) - most accurate
                if msg.get_type() == 'EKF1':
                    if hasattr(msg, 'VN') and hasattr(msg, 'VE'):
                        # Calculate ground speed from North/East velocity components
                        import math
                        speed_ms = math.sqrt(abs(msg.VN)**2 + abs(msg.VE)**2)
                        if 0.1 <= speed_ms < 100:  # Ignore very low speeds
                            speeds.append(speed_ms)
                            if len(speeds) % 10 == 0:
                                speed_profile.append({
                                    'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                                    'speed': round(speed_ms, 2)
                                })
                
                # Extract GPS data for position, date, and speed (fallback)
                if msg.get_type() == 'GPS':
                    # Get GPS time for accurate date (only if GPS week is valid)
                    if flight_date is None and hasattr(msg, 'GWk') and hasattr(msg, 'GMS'):
                        try:
                            # GPS Week 0 means no GPS lock - skip it
                            if msg.GWk > 0:
                                # GPS epoch is January 6, 1980
                                gps_epoch = datetime(1980, 1, 6)
                                flight_date = gps_epoch + timedelta(weeks=msg.GWk, milliseconds=msg.GMS)
                        except:
                            pass
                    
                    # GPS speed (convert from cm/s to m/s)
                    speed_ms = None
                    if hasattr(msg, 'Spd') and msg.Spd is not None and msg.Spd > 10:  # > 0.1 m/s
                        speed_ms = abs(msg.Spd) / 100.0  # cm/s to m/s
                    elif hasattr(msg, 'GSpd') and msg.GSpd is not None and msg.GSpd > 10:
                        speed_ms = abs(msg.GSpd) / 100.0
                    
                    if speed_ms is not None and 0.1 <= speed_ms < 100:
                        speeds.append(speed_ms)
                        if len(speeds) % 10 == 0:
                            speed_profile.append({
                                'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                                'speed': round(speed_ms, 2)
                            })
                    
                    if hasattr(msg, 'Lat') and hasattr(msg, 'Lng'):
                        # Skip invalid GPS coordinates (0,0 means no GPS lock)
                        if msg.Lat != 0 and msg.Lng != 0 and abs(msg.Lat) > 0.001 and abs(msg.Lng) > 0.001:
                            # pymavlink already converts to degrees, no need to divide by 1e7
                            lat = msg.Lat
                            lon = msg.Lng
                            gps_points.append((lat, lon))
                            
                            # Store GPS track (sample every 3rd point for smoother path)
                            if len(gps_points) % 3 == 0:
                                baro_alt = altitudes[-1] if altitudes else None
                                gps_track.append({
                                    'lat': round(lat, 7),
                                    'lon': round(lon, 7),
                                    'alt': round(baro_alt, 1) if baro_alt is not None else None
                                })
                            
                            # Store start/end locations
                            if stats['location_start_lat'] is None:
                                stats['location_start_lat'] = lat
                                stats['location_start_lon'] = lon
                            stats['location_end_lat'] = lat
                            stats['location_end_lon'] = lon
                
                # Extract comprehensive battery data
                if msg.get_type() == 'BAT':
                    if hasattr(msg, 'RemPct') and msg.RemPct is not None:
                        battery_samples.append(msg.RemPct)
                    elif hasattr(msg, 'Volt') and msg.Volt is not None:
                        # Estimate percentage from voltage (rough estimate)
                        # Typical LiPo: 4.2V full, 3.5V empty per cell
                        # Assuming 4S battery (16.8V full, 14.0V empty)
                        voltage = msg.Volt
                        if 12.0 < voltage < 20.0:  # Reasonable range
                            pct = ((voltage - 14.0) / (16.8 - 14.0)) * 100
                            pct = max(0, min(100, pct))  # Clamp to 0-100
                            battery_samples.append(int(pct))
                    
                    # Store detailed battery telemetry (sample every 10th)
                    if len(battery_samples) % 10 == 0:
                        battery_data = {
                            'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                        }
                        if hasattr(msg, 'Volt'):
                            battery_data['voltage'] = round(msg.Volt, 2)
                        if hasattr(msg, 'Curr'):
                            battery_data['current'] = round(msg.Curr, 2)
                        if hasattr(msg, 'RemPct'):
                            battery_data['remaining'] = int(msg.RemPct)
                        battery_profile.append(battery_data)
                
                # Extract motor outputs (RCOU = RC Output) - sample every 10th
                if msg.get_type() == 'RCOU':
                    motor_data = {
                        'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                    }
                    # Motors are typically on channels 1-4 (or 1-6 for hex)
                    for i in range(1, 9):  # Check up to 8 channels
                        chan = f'C{i}'
                        if hasattr(msg, chan):
                            motor_data[f'motor{i}'] = getattr(msg, chan)
                    motor_profile.append(motor_data)
                
                # Extract vibration data - sample every 10th
                if msg.get_type() == 'VIBE':
                    vibe_data = {
                        'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                    }
                    if hasattr(msg, 'VibeX'):
                        vibe_data['x'] = round(msg.VibeX, 2)
                    if hasattr(msg, 'VibeY'):
                        vibe_data['y'] = round(msg.VibeY, 2)
                    if hasattr(msg, 'VibeZ'):
                        vibe_data['z'] = round(msg.VibeZ, 2)
                    if hasattr(msg, 'Clip0'):
                        vibe_data['clip'] = msg.Clip0
                    vibration_profile.append(vibe_data)
                
                # Extract attitude data (roll, pitch, yaw) - sample every 10th
                if msg.get_type() == 'ATT':
                    att_data = {
                        'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                    }
                    if hasattr(msg, 'Roll'):
                        att_data['roll'] = round(msg.Roll, 2)
                    if hasattr(msg, 'Pitch'):
                        att_data['pitch'] = round(msg.Pitch, 2)
                    if hasattr(msg, 'Yaw'):
                        att_data['yaw'] = round(msg.Yaw, 2)
                    attitude_profile.append(att_data)
                
                # Extract flight mode changes
                if msg.get_type() == 'MODE':
                    if hasattr(msg, 'Mode'):
                        mode_changes.append({
                            'time': (msg.TimeUS - first_timestamp) / 1e6 if first_timestamp else 0,
                            'mode': msg.Mode,
                            'mode_num': getattr(msg, 'ModeNum', 0) if hasattr(msg, 'ModeNum') else 0
                        })
            
            # Calculate duration
            if first_timestamp and last_timestamp:
                duration_seconds = (last_timestamp - first_timestamp) / 1e6
                stats['duration_minutes'] = round(duration_seconds / 60, 2)
            
            # Calculate max altitude
            if altitudes:
                stats['max_altitude_m'] = round(max(altitudes), 1)
            
            # Calculate max speed
            if speeds:
                stats['max_speed_ms'] = round(max(speeds), 1)
            
            # Calculate distance using GPS points
            if len(gps_points) > 1:
                def haversine(lat1, lon1, lat2, lon2):
                    """Calculate distance between two GPS points (already in degrees)"""
                    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                    c = 2 * asin(sqrt(a))
                    return c * 6371  # Earth radius in km
                
                total_distance = 0.0
                for i in range(1, len(gps_points)):
                    lat1, lon1 = gps_points[i-1]
                    lat2, lon2 = gps_points[i]
                    total_distance += haversine(lat1, lon1, lat2, lon2)
                
                stats['distance_km'] = round(total_distance, 2)
            
            # Set battery start/end
            if battery_samples:
                stats['battery_start'] = int(battery_samples[0])
                stats['battery_end'] = int(battery_samples[-1])
            
            # Sample telemetry data to reduce size (keep every 10th point)
            def sample_data(data_list, interval=10):
                """Sample every Nth item from a list"""
                if not data_list or len(data_list) <= interval:
                    return data_list
                return [data_list[i] for i in range(0, len(data_list), interval)]
            
            # Apply sampling to reduce data size
            motor_profile = sample_data(motor_profile, 10)
            vibration_profile = sample_data(vibration_profile, 10)
            attitude_profile = sample_data(attitude_profile, 10)
            
            # Store detailed telemetry as JSON in raw_data field
            if gps_track or altitude_profile or speed_profile or battery_profile or motor_profile or vibration_profile or attitude_profile:
                raw_data = {
                    'gps_track': gps_track,
                    'altitude_profile': altitude_profile,
                    'speed_profile': speed_profile,
                    'battery_profile': battery_profile,
                    'motor_profile': motor_profile,
                    'vibration_profile': vibration_profile,
                    'attitude_profile': attitude_profile,
                    'mode_changes': mode_changes,
                    'flight_date_gps': flight_date.isoformat() if flight_date else None
                }
                stats['raw_data'] = json.dumps(raw_data)
            
            # Use GPS time if available
            if flight_date:
                stats['date'] = flight_date.isoformat()
                stats['timestamp'] = int(flight_date.timestamp())
                stats['date_source'] = 'gps_time'
        
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        return stats
    
    def _extract_stats_fallback(self, data: bytes) -> Dict:
        """Fallback method when pymavlink is not available"""
        stats = {
            'duration_minutes': 0.0,
            'max_altitude_m': 0.0,
            'max_speed_ms': 0.0,
            'distance_km': 0.0
        }
        
        # Estimate duration from file size
        # ArduPilot logs: ~50-100 KB per minute depending on logging rate
        bytes_per_minute = 75 * 1024  # 75 KB/min average
        stats['duration_minutes'] = round(len(data) / bytes_per_minute, 1)
        
        # Try to extract altitude and speed from GPS messages
        altitudes = []
        speeds = []
        
        # Simple scan for GPS-like data patterns
        for i in range(0, len(data) - 8, 4):
            try:
                value = struct.unpack('<i', data[i:i+4])[0]
                
                # Filter for reasonable altitude values (in cm)
                if 0 < value < 50000:  # 0-500m in centimeters
                    alt_m = value / 100.0
                    if 0 < alt_m < 500:
                        altitudes.append(alt_m)
                
                # Speed values (in cm/s)
                if 0 < value < 10000:  # 0-100 m/s in cm/s
                    speed_ms = value / 100.0
                    if 0 < speed_ms < 100:
                        speeds.append(speed_ms)
            except:
                continue
        
        if altitudes:
            altitudes.sort()
            idx = int(len(altitudes) * 0.95)
            stats['max_altitude_m'] = round(altitudes[idx], 1)
        
        if speeds:
            speeds.sort()
            idx = int(len(speeds) * 0.95)
            stats['max_speed_ms'] = round(speeds[idx], 1)
        
        # Estimate distance
        if speeds:
            avg_speed = sum(speeds) / len(speeds)
            distance_m = stats['duration_minutes'] * 60 * avg_speed
            stats['distance_km'] = round(distance_m / 1000, 2)
        
        return stats
    
    def _extract_drone_model(self, data: bytes) -> str:
        """Extract drone/vehicle model from log"""
        try:
            # Look for vehicle type in text messages
            text = data[:5000].decode('ascii', errors='ignore')
            
            # Common ArduPilot vehicle types
            if 'Copter' in text or 'QUAD' in text:
                return 'ArduPilot Quadcopter'
            elif 'Plane' in text:
                return 'ArduPilot Fixed-Wing'
            elif 'Rover' in text:
                return 'ArduPilot Rover'
            elif 'Sub' in text:
                return 'ArduPilot Submarine'
            elif 'Heli' in text:
                return 'ArduPilot Helicopter'
            
            # Check for specific frame types
            if 'X' in text or 'QUAD_X' in text:
                return 'ArduPilot Quadcopter (X)'
            elif 'PLUS' in text:
                return 'ArduPilot Quadcopter (+)'
            elif 'HEXA' in text:
                return 'ArduPilot Hexacopter'
            elif 'OCTA' in text:
                return 'ArduPilot Octocopter'
            
        except:
            pass
        
        return 'ArduPilot Vehicle'
    
    def _extract_date(self, data: bytes, file_path: str) -> Dict:
        """Extract flight date from log"""
        date_info = {}
        
        try:
            # ArduPilot logs contain GPS time
            # For now, use file modification time
            path = Path(file_path)
            mtime = path.stat().st_mtime
            date_info['date'] = datetime.fromtimestamp(mtime).isoformat()
            date_info['timestamp'] = int(mtime)
            date_info['date_source'] = 'file_metadata'
        except:
            date_info['date'] = datetime.now().isoformat()
            date_info['timestamp'] = int(datetime.now().timestamp())
            date_info['date_source'] = 'fallback'
        
        return date_info
    
    def batch_parse(self, directory: str) -> List[Dict]:
        """Parse all ArduPilot BIN files in a directory"""
        directory_path = Path(directory)
        results = []
        
        for file_path in directory_path.rglob('*.bin'):
            if self.can_parse(str(file_path)):
                result = self.parse_file(str(file_path))
                if result:
                    results.append(result)
        
        for file_path in directory_path.rglob('*.BIN'):
            if self.can_parse(str(file_path)):
                result = self.parse_file(str(file_path))
                if result:
                    results.append(result)
        
        return results

# Made with Bob