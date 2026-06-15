"""
Folder Watcher
Automatically monitors DJI Fly logs folder and imports new flights
"""
import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FlightLogHandler(FileSystemEventHandler):
    """Handles new flight log file events"""
    
    def __init__(self, parser_factory, database, callback=None):
        self.parser_factory = parser_factory
        self.database = database
        self.callback = callback
        self.processed_files = set()
        
        # Load already processed files
        flights = database.get_all_flights()
        for flight in flights:
            self.processed_files.add(flight.get('file_path', ''))
    
    def on_created(self, event):
        """Called when a new file is created"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Check if it's a flight log file
        if not (file_path.endswith('.txt') or file_path.endswith('.csv')):
            return
        
        # Avoid processing the same file twice
        if file_path in self.processed_files:
            return
        
        # Wait a moment for file to be fully written
        time.sleep(2)
        
        # Try to parse and import
        try:
            flight_data = self.parser_factory.parse_file(file_path)
            
            if flight_data:
                result = self.database.add_flight(flight_data)
                
                if result:
                    self.processed_files.add(file_path)
                    print(f"✓ Auto-imported: {Path(file_path).name}")
                    
                    # Notify callback if provided
                    if self.callback:
                        self.callback(flight_data)
                else:
                    print(f"  Skipped (duplicate): {Path(file_path).name}")
        except Exception as e:
            print(f"✗ Error importing {Path(file_path).name}: {e}")
    
    def on_modified(self, event):
        """Called when a file is modified"""
        # Treat modifications as new files (in case file was being written)
        self.on_created(event)

class FolderWatcher:
    """Watches a folder for new flight logs"""
    
    def __init__(self, parser_factory, database, callback=None):
        self.parser_factory = parser_factory
        self.database = database
        self.callback = callback
        self.observer = None
        self.watch_path = None
        self.is_watching = False
    
    def start(self, folder_path):
        """Start watching a folder"""
        if self.is_watching:
            self.stop()
        
        self.watch_path = folder_path
        
        # Create event handler
        event_handler = FlightLogHandler(
            self.parser_factory,
            self.database,
            self.callback
        )
        
        # Create observer
        self.observer = Observer()
        self.observer.schedule(event_handler, folder_path, recursive=True)
        self.observer.start()
        
        self.is_watching = True
        print(f"📁 Watching folder: {folder_path}")
    
    def stop(self):
        """Stop watching"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.is_watching = False
            print("⏹ Stopped watching folder")
    
    def is_active(self):
        """Check if watcher is active"""
        return self.is_watching

# Made with Bob