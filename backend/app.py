"""
Flask backend for Drone Flight Logbook
"""
from flask import Flask, render_template, request, jsonify, send_from_directory, Response, stream_with_context
from werkzeug.utils import secure_filename
import os
import json
import time
from pathlib import Path
from parsers.parser_factory import ParserFactory
from parsers.airdata_csv_parser import AirdataCSVParser
from database import FlightDatabase
import threading
from queue import Queue

app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static')

# Configuration
UPLOAD_FOLDER = Path('../data/uploads')
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Initialize components
db = FlightDatabase('../data/flights.db')
parser_factory = ParserFactory()

# Progress tracking
progress_queues = {}

# Disable caching for API responses
@app.after_request
def add_no_cache_headers(response):
    """Add headers to prevent caching of API responses"""
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    """Main landing page"""
    return render_template('index.html')

@app.route('/api/statistics')
def get_statistics():
    """Get flight statistics"""
    try:
        stats = db.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/flights')
def get_flights():
    """Get all flights"""
    try:
        flights = db.get_all_flights()
        return jsonify(flights)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/flight/<int:flight_id>')
def get_flight_details(flight_id):
    """Get detailed information for a specific flight"""
    try:
        flight = db.get_flight_by_id(flight_id)
        if flight:
            return jsonify(flight)
        else:
            return jsonify({'error': 'Flight not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Upload and parse flight log files"""
    try:
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files[]')
        results = []
        
        for file in files:
            if not file.filename or file.filename == '':
                continue
            
            # Save file
            filename = secure_filename(file.filename)
            filepath = UPLOAD_FOLDER / filename
            file.save(filepath)
            
            # Parse file using parser factory (auto-detects format)
            flight_data = parser_factory.parse_file(str(filepath))
            
            if flight_data:
                # Add to database
                flight_id = db.add_flight(flight_data)
                results.append({
                    'filename': filename,
                    'success': flight_id is not None,
                    'flight_id': flight_id,
                    'parser': flight_data.get('parser_used', 'Unknown'),
                    'data': flight_data
                })
            else:
                results.append({
                    'filename': filename,
                    'success': False,
                    'error': 'No compatible parser found for this file'
                })
        
        return jsonify({
            'results': results,
            'total': len(files),
            'successful': sum(1 for r in results if r['success'])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import-folder', methods=['POST'])
def import_folder():
    """Import all flight logs from a folder with progress tracking"""
    try:
        data = request.get_json()
        folder_path = data.get('folder_path')
        
        if not folder_path or not Path(folder_path).exists():
            return jsonify({'error': 'Invalid folder path'}), 400
        
        # Get all supported files
        path = Path(folder_path)
        files = (list(path.rglob('*.txt')) + list(path.rglob('*.csv')) +
                list(path.rglob('*.bin')) + list(path.rglob('*.BIN')) +
                list(path.rglob('*.dat')) + list(path.rglob('*.DAT')))
        
        if not files:
            return jsonify({'error': 'No flight log files found'}), 400
        
        # Create progress queue
        import uuid
        session_id = str(uuid.uuid4())
        progress_queues[session_id] = Queue()
        
        # Start import in background thread
        def do_import():
            imported = 0
            skipped = 0
            failed = 0
            
            for i, file_path in enumerate(files):
                try:
                    # Send progress update
                    progress = {
                        'current': i + 1,
                        'total': len(files),
                        'percent': int((i + 1) / len(files) * 100),
                        'file': file_path.name,
                        'status': 'processing'
                    }
                    progress_queues[session_id].put(json.dumps(progress))
                    
                    # Parse and import
                    flight_data = parser_factory.parse_file(str(file_path))
                    if flight_data:
                        result = db.add_flight(flight_data)
                        if result:
                            imported += 1
                        else:
                            skipped += 1
                    else:
                        failed += 1
                        
                except Exception as e:
                    print(f"Error importing {file_path}: {e}")
                    failed += 1
            
            # Send completion
            final = {
                'status': 'complete',
                'imported': imported,
                'skipped': skipped,
                'failed': failed,
                'total': len(files)
            }
            progress_queues[session_id].put(json.dumps(final))
            progress_queues[session_id].put('DONE')
        
        thread = threading.Thread(target=do_import)
        thread.daemon = True
        thread.start()
        
        return jsonify({'session_id': session_id, 'total_files': len(files)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import-progress/<session_id>')
def import_progress(session_id):
    """Stream import progress updates"""
    def generate():
        if session_id not in progress_queues:
            yield f"data: {json.dumps({'error': 'Invalid session'})}\n\n"
            return
        
        queue = progress_queues[session_id]
        
        while True:
            try:
                message = queue.get(timeout=30)
                if message == 'DONE':
                    # Clean up
                    del progress_queues[session_id]
                    break
                yield f"data: {message}\n\n"
            except:
                break
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/flight/<int:flight_id>', methods=['DELETE'])
def delete_flight(flight_id):
    """Delete a flight record"""
    try:
        db.delete_flight(flight_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-all', methods=['POST'])
def clear_all():
    """Clear all flight records"""
    try:
        db.clear_all()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import webbrowser
    import threading
    
    print("=" * 60)
    print("Drone Flight Logbook Server")
    print("=" * 60)
    print("Server starting at: http://localhost:5000")
    print("Opening browser...")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open('http://localhost:5000')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(debug=False, host='0.0.0.0', port=5000)

# Made with Bob
