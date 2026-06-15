"""
DAT File Converter - Safely uses DatCon as external tool
Converts DJI DAT files to CSV using DatCon (GPL, user-installed)
Legal for commercial use as external tool (see DATCON_LEGAL_REVIEW.md)
"""

import subprocess
import os
from pathlib import Path
import shutil

class DatConverter:
    """Converts DJI DAT files to CSV using DatCon external tool."""
    
    def __init__(self):
        self.datcon_path = self._find_datcon()
    
    def _find_datcon(self):
        """Find DatCon installation on system."""
        
        # Common DatCon installation locations
        possible_paths = [
            r"C:\Program Files\DatCon\DatCon.exe",
            r"C:\Program Files (x86)\DatCon\DatCon.exe",
            r"C:\DatCon\DatCon.exe",
            os.path.expanduser("~/DatCon/DatCon.exe"),
            os.path.expanduser("~/Applications/DatCon.app/Contents/MacOS/DatCon"),
            "/usr/local/bin/DatCon",
            "/opt/DatCon/DatCon",
        ]
        
        # Check if DatCon is in PATH
        if shutil.which("DatCon"):
            return "DatCon"
        
        # Check common installation paths
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def is_installed(self):
        """Check if DatCon is installed."""
        return self.datcon_path is not None
    
    def get_download_url(self):
        """Get DatCon download URL."""
        return "https://datfile.net/DatCon/intro.html"
    
    def convert_dat_to_csv(self, dat_file_path, output_dir=None):
        """
        Convert DAT file to CSV using DatCon.
        
        Args:
            dat_file_path: Path to .DAT file
            output_dir: Directory for output CSV (default: same as DAT file)
        
        Returns:
            Path to generated CSV file, or None if conversion failed
        """
        
        if not self.is_installed():
            raise RuntimeError("DatCon is not installed. Please install it from: " + self.get_download_url())
        
        dat_path = Path(dat_file_path)
        if not dat_path.exists():
            raise FileNotFoundError(f"DAT file not found: {dat_file_path}")
        
        # Determine output directory
        if output_dir is None:
            output_dir = dat_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # Expected CSV output path (DatCon names it based on DAT file)
        csv_path = output_dir / f"{dat_path.stem}.csv"
        
        try:
            # Call DatCon as external process
            # DatCon command line: DatCon -i input.DAT -o output_dir
            cmd = [
                str(self.datcon_path),
                "-i", str(dat_path),
                "-o", str(output_dir)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"DatCon conversion failed: {result.stderr}")
            
            # Check if CSV was created
            if csv_path.exists():
                return str(csv_path)
            else:
                # DatCon might use different naming
                # Look for any new CSV in output directory
                csv_files = list(output_dir.glob("*.csv"))
                if csv_files:
                    # Return the most recently created CSV
                    newest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
                    return str(newest_csv)
                else:
                    raise RuntimeError("DatCon did not generate CSV file")
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("DatCon conversion timed out (>60 seconds)")
        except Exception as e:
            raise RuntimeError(f"DatCon conversion error: {str(e)}")
    
    def convert_and_parse(self, dat_file_path, output_dir=None):
        """
        Convert DAT to CSV and return parsed flight data.
        
        Args:
            dat_file_path: Path to .DAT file
            output_dir: Directory for output CSV
        
        Returns:
            Dictionary with flight data, or None if conversion failed
        """
        
        try:
            csv_path = self.convert_dat_to_csv(dat_file_path, output_dir)
            
            if csv_path:
                # Parse the CSV using existing CSV parser
                from .parsers.airdata_csv_parser import AirdataCSVParser
                parser = AirdataCSVParser()
                
                flight_data = parser.parse(csv_path)
                
                # Override file_path to use DAT file (not CSV) for duplicate detection
                flight_data['file_path'] = str(dat_file_path)
                flight_data['file_name'] = Path(dat_file_path).name
                
                # Add source information
                flight_data['source_dat'] = str(dat_file_path)
                flight_data['source_csv'] = csv_path
                flight_data['parser_used'] = 'DatCon + CSV Parser'
                
                return flight_data
            
        except Exception as e:
            print(f"Error converting DAT file: {e}")
            return None
    
    def batch_convert(self, dat_directory, output_dir=None):
        """
        Convert all DAT files in a directory.
        
        Args:
            dat_directory: Directory containing .DAT files
            output_dir: Directory for output CSVs
        
        Returns:
            List of (dat_path, csv_path) tuples for successful conversions
        """
        
        dat_dir = Path(dat_directory)
        if not dat_dir.exists():
            raise FileNotFoundError(f"Directory not found: {dat_directory}")
        
        results = []
        dat_files = list(dat_dir.glob("*.DAT")) + list(dat_dir.glob("*.dat"))
        
        for dat_file in dat_files:
            try:
                csv_path = self.convert_dat_to_csv(dat_file, output_dir)
                if csv_path:
                    results.append((str(dat_file), csv_path))
                    print(f"[OK] Converted: {dat_file.name}")
            except Exception as e:
                print(f"[FAIL] Failed: {dat_file.name} - {e}")
        
        return results


def check_datcon_status():
    """Check DatCon installation status and provide guidance."""
    
    converter = DatConverter()
    
    print("DatCon Status Check")
    print("=" * 60)
    
    if converter.is_installed():
        print("[OK] DatCon is installed")
        print(f"  Location: {converter.datcon_path}")
        print("\nYou can now convert DAT files to get detailed flight metrics!")
    else:
        print("[NOT FOUND] DatCon is not installed")
        print("\nTo enable detailed flight metrics from DAT files:")
        print("1. Download DatCon (free, open-source):")
        print(f"   {converter.get_download_url()}")
        print("2. Install it to one of these locations:")
        print("   - C:\\Program Files\\DatCon\\")
        print("   - C:\\DatCon\\")
        print("   - Or add it to your system PATH")
        print("\nDatCon is GPL-licensed and safe to use with commercial software")
        print("as an external tool (see DATCON_LEGAL_REVIEW.md)")
    
    print("=" * 60)


if __name__ == "__main__":
    # Test DatCon installation
    check_datcon_status()

# Made with Bob
