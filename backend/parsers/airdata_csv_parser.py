"""
Airdata UAV CSV Parser
Parses CSV exports from Airdata UAV
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from .base_parser import BaseParser

class AirdataCSVParser(BaseParser):
    """Parser for Airdata UAV CSV exports"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.csv']
        self.parser_name = "Airdata CSV Parser"
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this is an Airdata CSV file"""
        path = Path(file_path)
        
        if path.suffix.lower() != '.csv':
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                # Check for Airdata-specific headers
                airdata_headers = [
                    'time(millisecond)',
                    'height_above_takeoff(feet)',
                    'distance(feet)',
                    'datetime(utc)'
                ]
                
                if headers and all(h in headers for h in airdata_headers):
                    return True
                    
        except Exception as e:
            print(f"Error checking CSV file {file_path}: {e}")
        
        return False
    
    def parse_file(self, file_path: str) -> Optional[Dict]:
        """Parse an Airdata CSV file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if not rows:
                return None
            
            flight_data = {
                'file_path': str(file_path),
                'file_name': Path(file_path).name,
                'manufacturer': 'DJI',  # Airdata primarily supports DJI
                'parser_used': self.parser_name,
                'confidence': 'high'
            }
            
            # Extract flight summary from CSV data
            summary = self._extract_flight_summary(rows)
            flight_data.update(summary)
            
            # Validate
            if self._validate_parsed_data(flight_data):
                return flight_data
            else:
                return None
                
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None
    
    def _extract_flight_summary(self, rows: List[Dict]) -> Dict:
        """Extract flight summary from CSV rows"""
        summary = {}
        
        try:
            # Get duration from last row
            last_row = rows[-1]
            duration_ms = int(last_row['time(millisecond)'])
            summary['duration_minutes'] = round(duration_ms / 1000 / 60, 1)
            
            # Get date from first row with valid datetime
            for row in rows:
                if row.get('datetime(utc)'):
                    try:
                        dt = datetime.strptime(row['datetime(utc)'], '%Y-%m-%d %H:%M:%S')
                        summary['date'] = dt.isoformat()
                        summary['timestamp'] = int(dt.timestamp())
                        break
                    except:
                        pass
            
            # Extract drone model from flycState or message fields
            summary['drone_model'] = self._extract_drone_model(rows)
            
            # Get max altitude (convert feet to meters)
            altitudes = []
            for row in rows:
                alt_str = row.get('height_above_takeoff(feet)', '')
                if alt_str and alt_str != 'Available with any HD 360 subscription':
                    try:
                        alt_ft = float(alt_str)
                        altitudes.append(alt_ft)
                    except:
                        pass
            
            if altitudes:
                max_alt_ft = max(altitudes)
                summary['max_altitude_m'] = round(max_alt_ft * 0.3048, 1)
            
            # Get max distance (convert feet to meters)
            distances = []
            for row in rows:
                dist_str = row.get('distance(feet)', '')
                if dist_str:
                    try:
                        dist_ft = float(dist_str)
                        distances.append(dist_ft)
                    except:
                        pass
            
            if distances:
                max_dist_ft = max(distances)
                summary['distance_km'] = round(max_dist_ft * 0.3048 / 1000, 2)
            
            # Get max speed (convert mph to m/s)
            speeds = []
            for row in rows:
                speed_str = row.get('speed(mph)', '')
                if speed_str:
                    try:
                        speed_mph = float(speed_str)
                        speeds.append(speed_mph)
                    except:
                        pass
            
            if speeds:
                max_speed_mph = max(speeds)
                summary['max_speed_ms'] = round(max_speed_mph * 0.44704, 1)
            
            # Get GPS coordinates (start and end)
            first_row = rows[0]
            if first_row.get('latitude') and first_row.get('longitude'):
                try:
                    summary['location_start'] = {
                        'lat': float(first_row['latitude']),
                        'lon': float(first_row['longitude'])
                    }
                except:
                    pass
            
            if last_row.get('latitude') and last_row.get('longitude'):
                try:
                    summary['location_end'] = {
                        'lat': float(last_row['latitude']),
                        'lon': float(last_row['longitude'])
                    }
                except:
                    pass
            
            # Get battery info
            if first_row.get('battery_percent'):
                try:
                    summary['battery_start'] = int(float(first_row['battery_percent']))
                except:
                    pass
            
            if last_row.get('battery_percent'):
                try:
                    summary['battery_end'] = int(float(last_row['battery_percent']))
                except:
                    pass
            
            # Extract detailed telemetry profiles for charts
            telemetry = self._extract_telemetry_profiles(rows)
            if telemetry:
                summary['raw_data'] = json.dumps(telemetry)
            
        except Exception as e:
            print(f"Error extracting flight summary: {e}")
        
        return summary
    
    def _extract_telemetry_profiles(self, rows: List[Dict]) -> Dict:
        """Extract detailed telemetry data for visualization"""
        gps_track = []
        altitude_profile = []
        speed_profile = []
        battery_profile = []
        attitude_profile = []
        motor_profile = []
        gimbal_profile = []
        wind_profile = []
        
        # Sample every 3rd row for smooth visualization while keeping file size reasonable
        for i, row in enumerate(rows):
            if i % 3 != 0:
                continue
                
            try:
                # Time in seconds
                time_s = float(row.get('time(millisecond)', 0)) / 1000.0
                
                # GPS coordinates with multiple altitude sources
                if row.get('latitude') and row.get('longitude'):
                    lat = float(row['latitude'])
                    lon = float(row['longitude'])
                    if lat != 0 and lon != 0:  # Skip invalid coordinates
                        alt_ft = float(row.get('height_above_takeoff(feet)', 0))
                        alt_m = alt_ft * 0.3048  # Convert to meters
                        gps_track.append({
                            'lat': round(lat, 7),
                            'lon': round(lon, 7),
                            'alt': round(alt_m, 1)
                        })
                
                # Altitude profile with multiple sources
                alt_data = {'time': round(time_s, 1)}
                if row.get('height_above_takeoff(feet)'):
                    alt_data['alt'] = round(float(row['height_above_takeoff(feet)']) * 0.3048, 1)
                if row.get('height_above_ground_at_drone_location(feet)'):
                    alt_data['agl'] = round(float(row['height_above_ground_at_drone_location(feet)']) * 0.3048, 1)
                if row.get('altitude_above_seaLevel(feet)'):
                    alt_data['msl'] = round(float(row['altitude_above_seaLevel(feet)']) * 0.3048, 1)
                if len(alt_data) > 1:
                    altitude_profile.append(alt_data)
                
                # Speed profile with component speeds
                speed_data = {'time': round(time_s, 1)}
                if row.get('speed(mph)'):
                    speed_data['speed'] = round(float(row['speed(mph)']) * 0.44704, 2)
                if row.get('xSpeed(mph)'):
                    speed_data['x'] = round(float(row['xSpeed(mph)']) * 0.44704, 2)
                if row.get('ySpeed(mph)'):
                    speed_data['y'] = round(float(row['ySpeed(mph)']) * 0.44704, 2)
                if row.get('zSpeed(mph)'):
                    speed_data['z'] = round(float(row['zSpeed(mph)']) * 0.44704, 2)
                if len(speed_data) > 1:
                    speed_profile.append(speed_data)
                
                # Battery profile with comprehensive data
                battery_data = {'time': round(time_s, 1)}
                if row.get('battery_percent'):
                    battery_data['remaining'] = int(float(row['battery_percent']))
                if row.get('voltage(v)'):
                    battery_data['voltage'] = round(float(row['voltage(v)']), 2)
                if row.get('current(A)'):
                    battery_data['current'] = round(float(row['current(A)']), 2)
                if row.get('battery_temperature(f)'):
                    # Convert Fahrenheit to Celsius
                    temp_f = float(row['battery_temperature(f)'])
                    battery_data['temperature'] = round((temp_f - 32) * 5/9, 1)
                
                # Individual cell voltages
                for cell_num in range(1, 7):
                    cell_col = f'voltageCell{cell_num}'
                    if row.get(cell_col):
                        try:
                            battery_data[f'cell{cell_num}'] = round(float(row[cell_col]), 2)
                        except:
                            pass
                
                if len(battery_data) > 1:
                    battery_profile.append(battery_data)
                
                # Attitude data (drone orientation)
                attitude_data = {'time': round(time_s, 1)}
                # Note: Some Airdata CSVs have spaces before column names
                roll_val = row.get('roll(degrees)') or row.get(' roll(degrees)')
                if roll_val:
                    try:
                        attitude_data['roll'] = round(float(roll_val), 2)
                    except (ValueError, TypeError):
                        pass
                
                pitch_val = row.get('pitch(degrees)') or row.get(' pitch(degrees)')
                if pitch_val:
                    try:
                        attitude_data['pitch'] = round(float(pitch_val), 2)
                    except (ValueError, TypeError):
                        pass
                
                yaw_val = row.get('compass_heading(degrees)') or row.get(' compass_heading(degrees)')
                if yaw_val:
                    try:
                        attitude_data['yaw'] = round(float(yaw_val), 2)
                    except (ValueError, TypeError):
                        pass
                
                if len(attitude_data) > 1:
                    attitude_profile.append(attitude_data)
                
                # Motor/RC control inputs
                motor_data = {'time': round(time_s, 1)}
                if row.get('rc_elevator(percent)'):
                    motor_data['elevator'] = round(float(row['rc_elevator(percent)']), 1)
                if row.get('rc_aileron(percent)'):
                    motor_data['aileron'] = round(float(row['rc_aileron(percent)']), 1)
                if row.get('rc_throttle(percent)'):
                    motor_data['throttle'] = round(float(row['rc_throttle(percent)']), 1)
                if row.get('rc_rudder(percent)'):
                    motor_data['rudder'] = round(float(row['rc_rudder(percent)']), 1)
                if len(motor_data) > 1:
                    motor_profile.append(motor_data)
                
                # Gimbal orientation
                gimbal_data = {'time': round(time_s, 1)}
                if row.get('gimbal_heading(degrees)'):
                    gimbal_data['heading'] = round(float(row['gimbal_heading(degrees)']), 2)
                if row.get('gimbal_pitch(degrees)'):
                    gimbal_data['pitch'] = round(float(row['gimbal_pitch(degrees)']), 2)
                if row.get('gimbal_roll(degrees)'):
                    gimbal_data['roll'] = round(float(row['gimbal_roll(degrees)']), 2)
                if len(gimbal_data) > 1:
                    gimbal_profile.append(gimbal_data)
                
                # Wind data
                wind_data = {'time': round(time_s, 1)}
                if row.get('wind_speed(mph)'):
                    wind_data['speed'] = round(float(row['wind_speed(mph)']) * 0.44704, 2)
                if row.get('wind_direction(degrees)'):
                    wind_data['direction'] = round(float(row['wind_direction(degrees)']), 1)
                if len(wind_data) > 1:
                    wind_profile.append(wind_data)
                    
            except (ValueError, TypeError):
                continue
        
        return {
            'gps_track': gps_track,
            'altitude_profile': altitude_profile,
            'speed_profile': speed_profile,
            'battery_profile': battery_profile,
            'attitude_profile': attitude_profile,
            'motor_profile': motor_profile,
            'gimbal_profile': gimbal_profile,
            'wind_profile': wind_profile,
        }
    
    def _extract_drone_model(self, rows: List[Dict]) -> str:
        """Extract drone model from CSV data"""
        # Check messages for drone model info
        for row in rows:
            message = row.get('message', '')
            if 'Mini 3' in message:
                return 'DJI Mini 3'
            elif 'Mini 2' in message:
                return 'DJI Mini 2'
            elif 'Air 2S' in message:
                return 'DJI Air 2S'
            elif 'Mavic' in message:
                return 'DJI Mavic'
        
        # Default
        return 'DJI Drone'
    
    def batch_parse(self, directory: str) -> List[Dict]:
        """Parse all Airdata CSV files in a directory"""
        directory_path = Path(directory)
        results = []
        
        for file_path in directory_path.rglob('*.csv'):
            if self.can_parse(str(file_path)):
                result = self.parse_file(str(file_path))
                if result:
                    results.append(result)
        
        return results

# Made with Bob