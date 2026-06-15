"""
Database module for flight logbook
Uses SQLite for local storage
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

class FlightDatabase:
    """Manages flight log database"""
    
    def __init__(self, db_path='data/flights.db'):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """Ensure database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create flights table with extended fields
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                manufacturer TEXT NOT NULL,
                drone_model TEXT NOT NULL,
                flight_date TEXT,
                duration_minutes REAL DEFAULT 0,
                max_altitude_m REAL,
                max_speed_ms REAL,
                distance_km REAL,
                battery_start INTEGER,
                battery_end INTEGER,
                location_start_lat REAL,
                location_start_lon REAL,
                location_end_lat REAL,
                location_end_lon REAL,
                parser_used TEXT,
                confidence TEXT,
                raw_data TEXT,
                imported_at TEXT NOT NULL,
                notes TEXT
            )
        ''')
        
        # Create pilot_profile table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pilot_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                pilot_name TEXT,
                license_number TEXT,
                company_name TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Create import_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_date TEXT NOT NULL,
                flights_imported INTEGER DEFAULT 0,
                flights_skipped INTEGER DEFAULT 0,
                source_type TEXT,
                notes TEXT
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_manufacturer
            ON flights(manufacturer)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drone_model
            ON flights(drone_model)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_flight_date
            ON flights(flight_date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_imported_at
            ON flights(imported_at)
        ''')

        # drone_aliases: maps a unique serial number to a user-chosen display name
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drone_aliases (
                serial_number TEXT PRIMARY KEY,
                manufacturer  TEXT,
                default_model TEXT,
                custom_name   TEXT,
                first_seen    TEXT,
                last_seen     TEXT
            )
        ''')

        # Migrations — add columns if they don't exist yet
        for migration in [
            'ALTER TABLE flights ADD COLUMN aircraft_sn TEXT',
            'ALTER TABLE drone_aliases ADD COLUMN owner TEXT',
            'ALTER TABLE drone_aliases ADD COLUMN registration TEXT',
        ]:
            try:
                cursor.execute(migration)
            except sqlite3.OperationalError:
                pass

        conn.commit()
        conn.close()

        # Backfill: link any already-imported flights that have no serial
        # number (ArduPilot/MAVLink/CSV logs etc.) to a synthetic drone id
        # so they show up as Fleet cards too.
        self._backfill_aircraft_sn()

    def _backfill_aircraft_sn(self):
        """One-time backfill — assign a stable synthetic id to existing
        flights lacking aircraft_sn, and register them in drone_aliases."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, manufacturer, drone_model FROM flights "
            "WHERE aircraft_sn IS NULL OR aircraft_sn = ''"
        )
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return

        now = datetime.now().isoformat()
        for row in rows:
            manufacturer = row['manufacturer'] or 'Unknown'
            drone_model  = row['drone_model']  or 'Unknown'
            sn = f"model:{manufacturer}:{drone_model}".strip().lower().replace(' ', '_')

            cursor.execute('UPDATE flights SET aircraft_sn = ? WHERE id = ?', (sn, row['id']))
            cursor.execute('''
                INSERT INTO drone_aliases (serial_number, manufacturer, default_model, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(serial_number) DO UPDATE SET last_seen = excluded.last_seen
            ''', (sn, manufacturer, drone_model, now, now))

        conn.commit()
        conn.close()

    def is_duplicate_flight(self, flight_data):
        """
        Check if a flight is a duplicate based on:
        - Same flight date (within 1 minute)
        - Same duration (within 10 seconds)
        - Same drone model
        This catches renamed copies of the same flight
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            flight_date = flight_data.get('date', '')
            duration = flight_data.get('duration_minutes', 0)
            drone_model = flight_data.get('drone_model', '')
            
            if not flight_date or not duration:
                return (False, None)
            
            # Check for flights with similar date, duration, and same drone
            # Allow 1 minute variance in date, 0.17 minutes (10 seconds) in duration
            cursor.execute('''
                SELECT id, file_name FROM flights
                WHERE drone_model = ?
                AND ABS(duration_minutes - ?) < 0.17
                AND datetime(flight_date) BETWEEN
                    datetime(?, '-1 minute') AND datetime(?, '+1 minute')
            ''', (drone_model, duration, flight_date, flight_date))
            
            existing = cursor.fetchone()
            if existing:
                return (True, existing[1])  # Return True and the existing filename
            return (False, None)
            
        finally:
            conn.close()
    
    def add_flight(self, flight_data):
        """Add a flight record to the database."""
        is_dup, existing_file = self.is_duplicate_flight(flight_data)
        if is_dup:
            print(f"Skipping duplicate: {flight_data.get('file_name')} (duplicate of {existing_file})")
            return None

        # Apply drone alias if one exists for this serial number
        manufacturer = flight_data.get('manufacturer', 'Unknown')
        drone_model  = flight_data.get('drone_model', 'Unknown')
        sn           = flight_data.get('aircraft_sn') or ''

        if not sn:
            # No hardware serial available (ArduPilot/MAVLink/CSV logs etc.) —
            # derive a stable synthetic id from manufacturer+model so the
            # aircraft still gets registered and shows up as a Fleet card.
            sn = f"model:{manufacturer}:{drone_model}".strip().lower().replace(' ', '_')

        alias = self.get_drone_alias(sn)
        if alias and alias.get('custom_name'):
            drone_model = alias['custom_name']
        # Register / update alias table so the drone appears in Fleet
        self.upsert_drone(
            serial_number = sn,
            manufacturer  = manufacturer,
            default_model = flight_data.get('drone_model', 'Unknown'),
        )

        conn   = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            location_start = flight_data.get('location_start', {})
            location_end   = flight_data.get('location_end', {})
            start_lat = location_start.get('lat') if location_start else flight_data.get('location_start_lat')
            start_lon = location_start.get('lon') if location_start else flight_data.get('location_start_lon')
            end_lat   = location_end.get('lat')   if location_end   else flight_data.get('location_end_lat')
            end_lon   = location_end.get('lon')   if location_end   else flight_data.get('location_end_lon')

            cursor.execute('''
                INSERT INTO flights
                (file_path, file_name, manufacturer, drone_model, aircraft_sn,
                 flight_date, duration_minutes, max_altitude_m, max_speed_ms,
                 distance_km, battery_start, battery_end,
                 location_start_lat, location_start_lon,
                 location_end_lat, location_end_lon,
                 parser_used, confidence, raw_data, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                flight_data.get('file_path', ''),
                flight_data.get('file_name', ''),
                flight_data.get('manufacturer', 'Unknown'),
                drone_model,
                sn or None,
                flight_data.get('date', ''),
                flight_data.get('duration_minutes', 0),
                flight_data.get('max_altitude_m'),
                flight_data.get('max_speed_ms'),
                flight_data.get('distance_km'),
                flight_data.get('battery_start'),
                flight_data.get('battery_end'),
                start_lat, start_lon, end_lat, end_lon,
                flight_data.get('parser_used', 'Unknown'),
                flight_data.get('confidence', 'unknown'),
                flight_data.get('raw_data') if isinstance(flight_data.get('raw_data'), str) else json.dumps(flight_data),
                datetime.now().isoformat(),
            ))

            conn.commit()
            return cursor.lastrowid

        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def update_flight(self, flight_id: int, flight_data: dict):
        """
        Update an existing flight record with improved data (e.g. after re-parse).
        Only overwrites fields that are present and non-None in flight_data.
        """
        conn   = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            location_start = flight_data.get('location_start', {})
            location_end   = flight_data.get('location_end', {})
            start_lat = (location_start.get('lat') if location_start
                         else flight_data.get('location_start_lat'))
            start_lon = (location_start.get('lon') if location_start
                         else flight_data.get('location_start_lon'))
            end_lat   = (location_end.get('lat')   if location_end
                         else flight_data.get('location_end_lat'))
            end_lon   = (location_end.get('lon')   if location_end
                         else flight_data.get('location_end_lon'))

            raw = (flight_data.get('raw_data')
                   if isinstance(flight_data.get('raw_data'), str)
                   else None)

            cursor.execute('''
                UPDATE flights SET
                    drone_model          = COALESCE(?, drone_model),
                    manufacturer         = COALESCE(?, manufacturer),
                    flight_date          = COALESCE(?, flight_date),
                    duration_minutes     = COALESCE(?, duration_minutes),
                    max_altitude_m       = COALESCE(?, max_altitude_m),
                    max_speed_ms         = COALESCE(?, max_speed_ms),
                    distance_km          = COALESCE(?, distance_km),
                    battery_start        = COALESCE(?, battery_start),
                    battery_end          = COALESCE(?, battery_end),
                    location_start_lat   = COALESCE(?, location_start_lat),
                    location_start_lon   = COALESCE(?, location_start_lon),
                    location_end_lat     = COALESCE(?, location_end_lat),
                    location_end_lon     = COALESCE(?, location_end_lon),
                    parser_used          = COALESCE(?, parser_used),
                    confidence           = COALESCE(?, confidence),
                    raw_data             = COALESCE(?, raw_data)
                WHERE id = ?
            ''', (
                flight_data.get('drone_model'),
                flight_data.get('manufacturer'),
                flight_data.get('date'),
                flight_data.get('duration_minutes'),
                flight_data.get('max_altitude_m'),
                flight_data.get('max_speed_ms'),
                flight_data.get('distance_km'),
                flight_data.get('battery_start'),
                flight_data.get('battery_end'),
                start_lat, start_lon, end_lat, end_lon,
                flight_data.get('parser_used'),
                flight_data.get('confidence'),
                raw,
                flight_id,
            ))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ── Drone alias methods ───────────────────────────────────────────────────

    def upsert_drone(self, serial_number: str, manufacturer: str, default_model: str):
        """Register a drone on first seen; update last_seen on subsequent calls."""
        now  = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO drone_aliases (serial_number, manufacturer, default_model, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(serial_number) DO UPDATE SET
                last_seen     = excluded.last_seen,
                default_model = COALESCE(excluded.default_model, default_model)
        ''', (serial_number, manufacturer, default_model, now, now))
        conn.commit()
        conn.close()

    def get_drone_alias(self, serial_number: str):
        """Return alias row for a serial number, or None."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM drone_aliases WHERE serial_number = ?', (serial_number,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_drones(self):
        """Return all known drones with flight counts."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                da.*,
                COUNT(f.id)              AS flight_count,
                COALESCE(SUM(f.duration_minutes), 0) AS total_minutes
            FROM drone_aliases da
            LEFT JOIN flights f ON f.aircraft_sn = da.serial_number
            GROUP BY da.serial_number
            ORDER BY da.last_seen DESC
        ''')
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def update_drone_details(self, serial_number: str, custom_name: str, owner: str, registration: str):
        """Save nickname, owner and registration; apply name retroactively to all flights."""
        conn   = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''UPDATE drone_aliases
               SET custom_name = ?, owner = ?, registration = ?
               WHERE serial_number = ?''',
            (custom_name or None, owner or None, registration or None, serial_number),
        )
        if custom_name and custom_name.strip():
            cursor.execute(
                'UPDATE flights SET drone_model = ? WHERE aircraft_sn = ?',
                (custom_name.strip(), serial_number),
            )
        conn.commit()
        conn.close()

    def rename_drone(self, serial_number: str, custom_name: str):
        """Save a custom display name and apply it retroactively to all matching flights."""
        conn   = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE drone_aliases SET custom_name = ? WHERE serial_number = ?',
            (custom_name or None, serial_number),
        )
        # Retroactively rename all flights logged with this serial
        display = custom_name.strip() if custom_name and custom_name.strip() else None
        if display:
            cursor.execute(
                'UPDATE flights SET drone_model = ? WHERE aircraft_sn = ?',
                (display, serial_number),
            )
        conn.commit()
        conn.close()

    def get_flights_for_drone(self, serial_number: str):
        """Return all flights logged for a specific aircraft serial number."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM flights WHERE aircraft_sn = ? ORDER BY flight_date DESC',
            (serial_number,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def remove_drone(self, serial_number: str):
        """Delete a drone alias record (flights are kept, just unlinked from the alias)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM drone_aliases WHERE serial_number = ?', (serial_number,))
        conn.commit()
        conn.close()

    def get_dji_flights_for_reparse(self):
        """
        Return flights that are DJI .txt logs and could benefit from re-parsing
        (those parsed with the old file-size estimator or that have no raw_data).
        """
        conn   = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, file_path, file_name, parser_used, confidence, raw_data
            FROM flights
            WHERE manufacturer = 'DJI'
              AND (
                    file_name LIKE 'DJIFlightRecord%.txt'
                    OR file_path LIKE '%.txt'
                  )
              AND (
                    parser_used LIKE '%DJI Fly%'
                    OR parser_used = 'Unknown'
                    OR raw_data IS NULL
                    OR raw_data = ''
                  )
            ORDER BY flight_date DESC
        ''')
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_all_flights(self):
        """Get all flight records"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM flights
            ORDER BY flight_date DESC
        ''')
        
        flights = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return flights
    
    def get_flight_by_id(self, flight_id):
        """Get a specific flight by ID with all details"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM flights
            WHERE id = ?
        ''', (flight_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            flight = dict(row)
            # Parse raw_data JSON if it exists
            if flight.get('raw_data'):
                try:
                    flight['raw_data'] = json.loads(flight['raw_data'])
                except:
                    pass
            return flight
        return None
    
    def get_statistics(self):
        """Get flight statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total flight hours
        cursor.execute('''
            SELECT COALESCE(SUM(duration_minutes), 0) as total_minutes
            FROM flights
        ''')
        total_minutes = cursor.fetchone()[0]
        
        # Hours by drone model
        cursor.execute('''
            SELECT drone_model, 
                   COALESCE(SUM(duration_minutes), 0) as total_minutes,
                   COUNT(*) as flight_count
            FROM flights
            GROUP BY drone_model
            ORDER BY total_minutes DESC
        ''')
        by_drone = [
            {
                'model': row[0],
                'hours': round(row[1] / 60, 2),
                'minutes': round(row[1], 1),
                'flights': row[2]
            }
            for row in cursor.fetchall()
        ]
        
        # Hours by manufacturer
        cursor.execute('''
            SELECT manufacturer, 
                   COALESCE(SUM(duration_minutes), 0) as total_minutes,
                   COUNT(*) as flight_count
            FROM flights
            GROUP BY manufacturer
            ORDER BY total_minutes DESC
        ''')
        by_manufacturer = [
            {
                'manufacturer': row[0],
                'hours': round(row[1] / 60, 2),
                'minutes': round(row[1], 1),
                'flights': row[2]
            }
            for row in cursor.fetchall()
        ]
        
        # Total flights
        cursor.execute('SELECT COUNT(*) FROM flights')
        total_flights = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_hours': round(total_minutes / 60, 2),
            'total_minutes': round(total_minutes, 1),
            'total_flights': total_flights,
            'by_drone': by_drone,
            'by_manufacturer': by_manufacturer
        }
    
    def update_flight(self, flight_id, flight_data):
        """Update an existing flight record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Extract location data - handle both nested dict and direct fields
            location_start = flight_data.get('location_start', {})
            location_end = flight_data.get('location_end', {})
            
            # Get lat/lon from nested dict or direct fields
            start_lat = location_start.get('lat') if location_start else flight_data.get('location_start_lat')
            start_lon = location_start.get('lon') if location_start else flight_data.get('location_start_lon')
            end_lat = location_end.get('lat') if location_end else flight_data.get('location_end_lat')
            end_lon = location_end.get('lon') if location_end else flight_data.get('location_end_lon')
            
            cursor.execute('''
                UPDATE flights SET
                    manufacturer = ?,
                    drone_model = ?,
                    flight_date = ?,
                    duration_minutes = ?,
                    max_altitude_m = ?,
                    max_speed_ms = ?,
                    distance_km = ?,
                    battery_start = ?,
                    battery_end = ?,
                    location_start_lat = ?,
                    location_start_lon = ?,
                    location_end_lat = ?,
                    location_end_lon = ?,
                    parser_used = ?,
                    confidence = ?,
                    raw_data = ?
                WHERE id = ?
            ''', (
                flight_data.get('manufacturer', 'Unknown'),
                flight_data.get('drone_model', 'Unknown'),
                flight_data.get('date', ''),
                flight_data.get('duration_minutes', 0),
                flight_data.get('max_altitude_m'),
                flight_data.get('max_speed_ms'),
                flight_data.get('distance_km'),
                flight_data.get('battery_start'),
                flight_data.get('battery_end'),
                start_lat,
                start_lon,
                end_lat,
                end_lon,
                flight_data.get('parser_used', 'Unknown'),
                flight_data.get('confidence', 'unknown'),
                flight_data.get('raw_data') if isinstance(flight_data.get('raw_data'), str) else json.dumps(flight_data),
                flight_id
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error updating flight {flight_id}: {e}")
            return False
        finally:
            conn.close()
    
    def delete_flight(self, flight_id):
        """Delete a flight record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM flights WHERE id = ?', (flight_id,))
        conn.commit()
        conn.close()
    
    def clear_all(self):
        """Clear all flight records"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM flights')
        conn.commit()
        conn.close()
    
    def import_flights(self, flight_data_list):
        """Import multiple flights at once"""
        imported = 0
        skipped = 0
        
        for flight_data in flight_data_list:
            result = self.add_flight(flight_data)
            if result:
                imported += 1
            else:
                skipped += 1
        
        return {
            'imported': imported,
            'skipped': skipped,
            'total': len(flight_data_list)
        }
    
    def update_flight_details(self, flight_id, new_data):
        """Update an existing flight with detailed data from Airdata"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Extract location data
            location_start = new_data.get('location_start', {})
            location_end = new_data.get('location_end', {})
            
            # Update only the detailed fields, keep original file info
            cursor.execute('''
                UPDATE flights SET
                    max_altitude_m = ?,
                    max_speed_ms = ?,
                    distance_km = ?,
                    battery_start = ?,
                    battery_end = ?,
                    location_start_lat = ?,
                    location_start_lon = ?,
                    location_end_lat = ?,
                    location_end_lon = ?,
                    parser_used = ?,
                    confidence = ?
                WHERE id = ?
            ''', (
                new_data.get('max_altitude_m'),
                new_data.get('max_speed_ms'),
                new_data.get('distance_km'),
                new_data.get('battery_start'),
                new_data.get('battery_end'),
                location_start.get('lat') if location_start else None,
                location_start.get('lon') if location_start else None,
                location_end.get('lat') if location_end else None,
                location_end.get('lon') if location_end else None,
                new_data.get('parser_used', 'Airdata CSV Parser'),
                'high',  # Airdata data is always high confidence
                flight_id
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error updating flight {flight_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_pilot_profile(self):
        """Get pilot profile information"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM pilot_profile WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def save_pilot_profile(self, profile_data):
        """Save or update pilot profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            # Check if profile exists
            cursor.execute('SELECT id FROM pilot_profile WHERE id = 1')
            exists = cursor.fetchone()
            
            if exists:
                # Update existing profile
                cursor.execute('''
                    UPDATE pilot_profile SET
                        pilot_name = ?,
                        license_number = ?,
                        company_name = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE id = 1
                ''', (
                    profile_data.get('pilot_name', ''),
                    profile_data.get('license_number', ''),
                    profile_data.get('company_name', ''),
                    profile_data.get('notes', ''),
                    now
                ))
            else:
                # Insert new profile
                cursor.execute('''
                    INSERT INTO pilot_profile
                    (id, pilot_name, license_number, company_name, notes, created_at, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, ?)
                ''', (
                    profile_data.get('pilot_name', ''),
                    profile_data.get('license_number', ''),
                    profile_data.get('company_name', ''),
                    profile_data.get('notes', ''),
                    now,
                    now
                ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving pilot profile: {e}")
            return False
        finally:
            conn.close()
    
    def log_import(self, flights_imported, flights_skipped, source_type='manual', notes=''):
        """Log an import operation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO import_history
                (import_date, flights_imported, flights_skipped, source_type, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                flights_imported,
                flights_skipped,
                source_type,
                notes
            ))
            
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error logging import: {e}")
            return None
        finally:
            conn.close()
    
    def get_last_import(self):
        """Get the most recent import information"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM import_history
            ORDER BY import_date DESC
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_advanced_statistics(self):
        """Get advanced flight statistics for pilot reports"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Longest flight
        cursor.execute('''
            SELECT drone_model, duration_minutes, flight_date
            FROM flights
            ORDER BY duration_minutes DESC
            LIMIT 1
        ''')
        longest = cursor.fetchone()
        if longest:
            stats['longest_flight'] = {
                'drone': longest[0],
                'duration_minutes': longest[1],
                'duration_hours': round(longest[1] / 60, 2),
                'date': longest[2]
            }
        else:
            stats['longest_flight'] = None
        
        # Average flight duration
        cursor.execute('''
            SELECT AVG(duration_minutes) as avg_duration
            FROM flights
        ''')
        avg = cursor.fetchone()[0]
        stats['average_duration_minutes'] = round(avg, 1) if avg else 0
        stats['average_duration_hours'] = round(avg / 60, 2) if avg else 0
        
        # Most flown aircraft
        cursor.execute('''
            SELECT drone_model, COUNT(*) as flight_count
            FROM flights
            GROUP BY drone_model
            ORDER BY flight_count DESC
            LIMIT 1
        ''')
        most_flown = cursor.fetchone()
        if most_flown:
            stats['most_flown_aircraft'] = {
                'model': most_flown[0],
                'flights': most_flown[1]
            }
        else:
            stats['most_flown_aircraft'] = None
        
        # Most active month
        cursor.execute('''
            SELECT strftime('%Y-%m', flight_date) as month,
                   COUNT(*) as flight_count,
                   SUM(duration_minutes) as total_minutes
            FROM flights
            WHERE flight_date IS NOT NULL
            GROUP BY month
            ORDER BY flight_count DESC
            LIMIT 1
        ''')
        most_active = cursor.fetchone()
        if most_active:
            stats['most_active_month'] = {
                'month': most_active[0],
                'flights': most_active[1],
                'hours': round(most_active[2] / 60, 2) if most_active[2] else 0
            }
        else:
            stats['most_active_month'] = None
        
        # Flights this month
        cursor.execute('''
            SELECT COUNT(*) as flight_count,
                   SUM(duration_minutes) as total_minutes
            FROM flights
            WHERE strftime('%Y-%m', flight_date) = strftime('%Y-%m', 'now')
        ''')
        this_month = cursor.fetchone()
        stats['this_month'] = {
            'flights': this_month[0] if this_month[0] else 0,
            'hours': round(this_month[1] / 60, 2) if this_month[1] else 0,
            'minutes': round(this_month[1], 1) if this_month[1] else 0
        }
        
        # Total unique aircraft
        cursor.execute('SELECT COUNT(DISTINCT drone_model) FROM flights')
        stats['total_aircraft'] = cursor.fetchone()[0]
        
        # Total unique manufacturers
        cursor.execute('SELECT COUNT(DISTINCT manufacturer) FROM flights')
        stats['total_manufacturers'] = cursor.fetchone()[0]
        
        conn.close()
        return stats

# Made with Bob
