"""
Skylogr - Professional Flight Logging
A clean, fully offline desktop app for tracking drone flight hours
Built with NiceGUI for a modern, professional interface
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
import json
import asyncio
from urllib.parse import quote

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from nicegui import ui, app
from backend.database import FlightDatabase
from backend.parsers.parser_factory import ParserFactory
from backend.config_manager import ConfigManager
from backend.drone_connector import DroneConnector

# Initialize backend
db = FlightDatabase('data/flights.db')
config = ConfigManager()

# Initialize parser factory with DJI API key (if already saved by user)
_dji_keychain_dir = str(Path('data/dji_keychains'))
parser_factory = ParserFactory(
    dji_api_key      = config.get_dji_api_key(),
    dji_keychain_dir = _dji_keychain_dir,
)
Path(_dji_keychain_dir).mkdir(parents=True, exist_ok=True)

drone_connector = DroneConnector()

# Theme colors
COLORS = {
    'dark': {
        'primary': '#667eea',
        'secondary': '#764ba2',
        'background': '#1a1a2e',
        'surface': '#16213e',
        'text': '#ffffff',
        'text_secondary': '#a0a0a0',
        'success': '#10b981',
        'warning': '#f59e0b',
        'error': '#ef4444',
    },
    'light': {
        'primary': '#667eea',
        'secondary': '#764ba2',
        'background': '#f5f5f5',
        'surface': '#ffffff',
        'text': '#1a1a1a',
        'text_secondary': '#666666',
        'success': '#10b981',
        'warning': '#f59e0b',
        'error': '#ef4444',
    }
}

def get_theme_colors():
    """Get current theme colors - always dark mode"""
    return COLORS['dark']

def apply_theme():
    """Apply theme to UI - always dark mode"""
    colors = COLORS['dark']
    
    # Apply custom CSS
    ui.add_head_html(f'''
        <style>
            :root {{
                --primary-color: {colors['primary']};
                --secondary-color: {colors['secondary']};
                --background-color: {colors['background']};
                --surface-color: {colors['surface']};
                --text-color: {colors['text']};
                --text-secondary-color: {colors['text_secondary']};
            }}

            body {{
                background-color: {colors['background']} !important;
                color: {colors['text']} !important;
                font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
            }}

            /* Cards */
            .q-card {{
                background-color: {colors['surface']} !important;
                color: {colors['text']} !important;
                border: 1px solid rgba(255,255,255,0.06) !important;
                border-radius: 12px !important;
                transition: box-shadow 0.2s ease, transform 0.2s ease !important;
            }}
            .q-card:hover {{
                box-shadow: 0 8px 32px rgba(0,0,0,0.45) !important;
            }}

            /* Buttons */
            .q-btn {{ border-radius: 8px !important; font-weight: 600 !important; letter-spacing: 0.3px !important; }}
            .q-btn--flat {{ color: rgba(255,255,255,0.85) !important; }}
            .q-btn--flat:hover {{ background: rgba(255,255,255,0.1) !important; color: white !important; }}

            /* Header */
            .q-header {{ box-shadow: 0 2px 20px rgba(0,0,0,0.5) !important; }}

            /* Table — force dark theme on all layers */
            .q-table__container,
            .q-table__middle,
            .q-table {{ background: {colors['surface']} !important; color: {colors['text']} !important; }}
            .q-table thead tr,
            .q-table thead tr th {{
                background: rgba(255,255,255,0.04) !important;
                color: {colors['text_secondary']} !important;
                font-size: 11px !important;
                letter-spacing: 1px !important;
                text-transform: uppercase !important;
                border-bottom: 1px solid rgba(255,255,255,0.08) !important;
            }}
            .q-table tbody tr {{
                background: {colors['surface']} !important;
                border-bottom: 1px solid rgba(255,255,255,0.04) !important;
            }}
            .q-table tbody tr:hover {{
                background: rgba(102,126,234,0.12) !important;
                cursor: pointer;
            }}
            .q-table tbody tr td {{
                background: transparent !important;
                color: {colors['text']} !important;
                border: none !important;
            }}
            .q-table__bottom {{
                background: {colors['surface']} !important;
                color: {colors['text_secondary']} !important;
                border-top: 1px solid rgba(255,255,255,0.06) !important;
            }}

            /* Inputs — text typed/selected by the user must stay readable on the dark background */
            .q-field__control {{ background: rgba(255,255,255,0.05) !important; border-radius: 8px !important; }}
            .q-field__label {{ color: {colors['text_secondary']} !important; }}
            .q-field__native,
            .q-field__input,
            .q-field__native input,
            .q-field__native textarea,
            .q-field input,
            .q-field textarea,
            .q-field .q-select__input {{
                color: {colors['text']} !important;
                caret-color: {colors['text']} !important;
            }}
            .q-field__native::placeholder,
            .q-field__input::placeholder,
            .q-field input::placeholder,
            .q-field textarea::placeholder {{
                color: {colors['text_secondary']} !important;
                opacity: 0.7 !important;
            }}
            .q-field__suffix,
            .q-field__prefix,
            .q-field__counter {{ color: {colors['text_secondary']} !important; }}
            .q-field--standard .q-field__control:before {{ border-color: rgba(255,255,255,0.2) !important; }}

            /* Select / Autocomplete dropdown menus — match the dark theme */
            .q-menu {{
                background: {colors['surface']} !important;
                color: {colors['text']} !important;
                border: 1px solid rgba(255,255,255,0.08) !important;
            }}
            .q-menu .q-item {{ color: {colors['text']} !important; }}
            .q-menu .q-item__label {{ color: {colors['text']} !important; }}
            .q-menu .q-item__label--caption {{ color: {colors['text_secondary']} !important; }}
            .q-menu .q-item.q-manual-focusable--focused,
            .q-menu .q-item:hover {{
                background: rgba(102,126,234,0.18) !important;
            }}

            /* Progress bar */
            .q-linear-progress__track {{ background: rgba(255,255,255,0.1) !important; }}
            .q-linear-progress__model {{ background: {colors['primary']} !important; }}

            /* Scrollbar */
            ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
            ::-webkit-scrollbar-track {{ background: {colors['background']}; }}
            ::-webkit-scrollbar-thumb {{ background: {colors['primary']}; border-radius: 3px; }}

            /* Notification */
            .q-notification {{ border-radius: 10px !important; font-weight: 500 !important; }}

            /* Hero section */
            .skylogr-hero {{
                background: linear-gradient(135deg, #0f0c29 0%, #302b63 60%, #24243e 100%);
                border: 1px solid rgba(102,126,234,0.25) !important;
                border-radius: 16px !important;
            }}

            /* Stat mini-card */
            .stat-card {{
                background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']});
                border-radius: 12px;
                padding: 24px;
                color: white;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .stat-value {{ font-size: 48px; font-weight: bold; margin: 12px 0; }}
            .stat-label {{ font-size: 14px; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; }}

            /* Upload zone */
            .q-uploader {{ background: rgba(255,255,255,0.03) !important; border: 2px dashed rgba(102,126,234,0.4) !important; border-radius: 12px !important; }}
        </style>
    ''')

# Global state
current_page = 'dashboard'

def create_header():
    """Create application header"""
    colors = get_theme_colors()
    
    with ui.header().classes('items-center justify-between').style(f'background: linear-gradient(135deg, {colors["primary"]}, {colors["secondary"]})'):
        with ui.row().classes('items-center gap-4'):
            # SL logo text
            ui.label('SL').classes('text-h4 font-bold').style('color: white; font-size: 32px; font-weight: 900;')
            ui.label('SKYLOGR').classes('text-h5 font-bold')
        
        with ui.row().classes('items-center gap-2'):
            # Navigation (removed theme toggle - dark mode only)
            ui.button('Dashboard', on_click=lambda: navigate_to('dashboard')).props('flat')
            ui.button('Flights',   on_click=lambda: navigate_to('flights')).props('flat')
            ui.button('Fleet',     on_click=lambda: navigate_to('fleet')).props('flat')
            ui.button('Import',    on_click=lambda: navigate_to('import')).props('flat')
            ui.button('Profile',   on_click=lambda: navigate_to('profile')).props('flat')
            ui.button('About',     on_click=lambda: navigate_to('about')).props('flat')

def toggle_theme():
    """Toggle between light and dark theme"""
    config.toggle_theme()
    ui.notify('Theme changed! Refresh page to apply.', type='info')

def navigate_to(page: str):
    """Navigate to a different page"""
    global current_page
    current_page = page
    ui.navigate.to(f'/{page}')

def filter_by_drone(drone_model: str):
    """Navigate to flights page filtered by drone model"""
    ui.navigate.to(f'/flights?drone={quote(drone_model)}')

def filter_by_manufacturer(manufacturer: str):
    """Navigate to flights page filtered by manufacturer"""
    ui.navigate.to(f'/flights?manufacturer={quote(manufacturer)}')

@ui.page('/')
@ui.page('/dashboard')
def dashboard_page():
    """Main dashboard page"""
    apply_theme()
    create_header()
    
    colors = get_theme_colors()
    
    with ui.column().classes('w-full p-4 gap-4'):
        # Get all statistics
        stats = db.get_statistics()
        advanced_stats = db.get_advanced_statistics()
        last_import = db.get_last_import()
        pilot_profile = db.get_pilot_profile()
        
        # ── Hero Banner ─────────────────────────────────────────────────────
        with ui.card().classes('w-full skylogr-hero').style('padding: 36px 44px;'):
            with ui.row().classes('w-full items-center').style('gap: 0;'):

                # Left: Pilot identity
                with ui.column().style('flex: 0 0 auto; min-width: 260px; padding-right: 40px; border-right: 1px solid rgba(255,255,255,0.1);'):
                    if pilot_profile and pilot_profile.get('pilot_name'):
                        ui.label(pilot_profile.get('pilot_name', '')).style(
                            'font-size: 44px; font-weight: 900; color: white; '
                            'line-height: 1; letter-spacing: -1px; margin-bottom: 10px;'
                        )
                        if pilot_profile.get('license_number'):
                            ui.label(f"Lic. {pilot_profile.get('license_number', '')}").style(
                                'font-size: 13px; color: rgba(255,255,255,0.45); letter-spacing: 0.5px; margin-bottom: 4px;'
                            )
                        if pilot_profile.get('company_name'):
                            ui.label(pilot_profile.get('company_name', '')).style(
                                'font-size: 15px; color: rgba(255,255,255,0.65); font-weight: 500;'
                            )
                    else:
                        ui.label('SKYLOGR').style(
                            'font-size: 44px; font-weight: 900; color: white; letter-spacing: -2px;'
                        )
                        ui.label('Set up your pilot profile →').style(
                            'font-size: 13px; color: rgba(255,255,255,0.4); cursor: pointer;'
                        ).on('click', lambda: navigate_to('profile'))

                # Center: Total hours — the centerpiece
                with ui.column().classes('items-center').style('flex: 1; padding: 0 40px;'):
                    ui.label('TOTAL FLIGHT HOURS').style(
                        'font-size: 13px; font-weight: 800; color: rgba(255,255,255,0.7); letter-spacing: 3px; margin-bottom: 6px;'
                    )
                    ui.label(f'{stats["total_hours"]:.1f}').style(
                        'font-size: 108px; font-weight: 900; color: white; line-height: 1; '
                        'letter-spacing: -4px; text-shadow: 0 0 60px rgba(102,126,234,0.6);'
                    )
                    ui.label(f'{stats["total_minutes"]:.0f} minutes logged').style(
                        'font-size: 13px; color: rgba(255,255,255,0.35); margin-top: -4px;'
                    )

                # Right: Flights count + this month
                with ui.column().classes('items-end').style(
                    'flex: 0 0 auto; min-width: 200px; padding-left: 40px; '
                    'border-left: 1px solid rgba(255,255,255,0.1);'
                ):
                    ui.label('TOTAL FLIGHTS').style(
                        'font-size: 13px; font-weight: 800; color: rgba(255,255,255,0.7); letter-spacing: 3px; margin-bottom: 6px;'
                    )
                    ui.label(f'{stats["total_flights"]}').style(
                        'font-size: 72px; font-weight: 900; line-height: 1; '
                        'background: linear-gradient(135deg, #667eea, #a78bfa); '
                        '-webkit-background-clip: text; -webkit-text-fill-color: transparent; '
                        'background-clip: text;'
                    )
                    ui.html(f'''
                        <div style="margin-top: 12px; text-align: right;">
                            <span style="font-size: 26px; font-weight: 800; color: white;">
                                {advanced_stats["this_month"]["flights"]}
                            </span>
                            <span style="font-size: 12px; color: rgba(255,255,255,0.4); margin-left: 6px;">
                                this month
                            </span>
                        </div>
                        <div style="font-size: 12px; color: rgba(255,255,255,0.3); text-align: right;">
                            {advanced_stats["this_month"]["hours"]:.1f}h this month
                        </div>
                    ''')
        
        # ── Quick Stats Row ──────────────────────────────────────────────────
        _card_style = 'padding: 18px 20px; min-height: 110px;'
        _label_style = 'font-size: 12px; font-weight: 800; color: rgba(255,255,255,0.7); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;'
        _num_style   = 'font-size: 34px; font-weight: 800; color: white; line-height: 1; margin-bottom: 4px;'
        _sub_style   = 'font-size: 11px; color: rgba(255,255,255,0.4);'

        with ui.row().classes('w-full gap-3'):
            lf = advanced_stats.get('longest_flight')
            mf = advanced_stats.get('most_flown_aircraft')

            with ui.card().classes('flex-1').style(_card_style):
                ui.html(f'''
                    <div style="{_label_style}">Fleet</div>
                    <div style="display:flex; gap: 28px; align-items:flex-end;">
                        <div>
                            <div style="{_num_style}">{advanced_stats['total_aircraft']}</div>
                            <div style="{_sub_style}">aircraft</div>
                        </div>
                        <div>
                            <div style="{_num_style}">{advanced_stats['total_manufacturers']}</div>
                            <div style="{_sub_style}">brands</div>
                        </div>
                    </div>
                ''')

            with ui.card().classes('flex-1').style(_card_style):
                ui.html(f'''
                    <div style="{_label_style}">Longest Flight</div>
                    <div style="{_num_style}">{lf["duration_hours"]:.2f}h</div>
                    <div style="{_sub_style}">{lf["drone"] if lf else "—"}</div>
                ''' if lf else f'''
                    <div style="{_label_style}">Longest Flight</div>
                    <div style="{_num_style}">—</div>
                    <div style="{_sub_style}">no flights yet</div>
                ''')

            with ui.card().classes('flex-1').style(_card_style):
                ui.html(f'''
                    <div style="{_label_style}">Avg Flight</div>
                    <div style="{_num_style}">{advanced_stats["average_duration_hours"]:.2f}h</div>
                    <div style="{_sub_style}">per flight</div>
                ''')

            with ui.card().classes('flex-1').style(_card_style):
                ui.html(f'''
                    <div style="{_label_style}">Most Flown</div>
                    <div style="font-size: 20px; font-weight: 800; color: white; line-height: 1.2; margin-bottom: 4px;">{mf["model"] if mf else "—"}</div>
                    <div style="{_sub_style}">{mf["flights"] if mf else 0} flights</div>
                ''' if mf else f'''
                    <div style="{_label_style}">Most Flown</div>
                    <div style="{_num_style}">—</div>
                    <div style="{_sub_style}">no flights yet</div>
                ''')
        
        # ── Hours tables ────────────────────────────────────────────────────
        with ui.row().classes('w-full gap-3'):
            # Hours by Drone
            with ui.card().classes('flex-1'):
                ui.label('Hours by Drone Model').style('font-size: 14px; font-weight: 800; letter-spacing: 1.5px; color: rgba(255,255,255,0.75); text-transform: uppercase; margin-bottom: 12px;')
                
                if stats['by_drone']:
                    columns = [
                        {'name': 'model', 'label': 'Drone Model', 'field': 'model', 'align': 'left'},
                        {'name': 'hours', 'label': 'Hours', 'field': 'hours', 'align': 'right'},
                        {'name': 'flights', 'label': 'Flights', 'field': 'flights', 'align': 'right'},
                    ]
                    
                    rows = [
                        {
                            'model': d['model'],
                            'hours': f"{d['hours']:.1f}h",
                            'flights': d['flights']
                        }
                        for d in stats['by_drone']
                    ]
                    
                    table = ui.table(columns=columns, rows=rows, row_key='model').classes('w-full')
                    table.on('rowClick', lambda e: filter_by_drone(e.args[1]['model']))
                else:
                    ui.label('No flight data yet. Import some logs to get started!').classes('text-center p-4')
            
            # Hours by Manufacturer
            with ui.card().classes('flex-1'):
                ui.label('Hours by Manufacturer').style('font-size: 14px; font-weight: 800; letter-spacing: 1.5px; color: rgba(255,255,255,0.75); text-transform: uppercase; margin-bottom: 12px;')
                
                if stats['by_manufacturer']:
                    columns = [
                        {'name': 'manufacturer', 'label': 'Manufacturer', 'field': 'manufacturer', 'align': 'left'},
                        {'name': 'hours', 'label': 'Hours', 'field': 'hours', 'align': 'right'},
                        {'name': 'flights', 'label': 'Flights', 'field': 'flights', 'align': 'right'},
                    ]
                    
                    rows = [
                        {
                            'manufacturer': m['manufacturer'],
                            'hours': f"{m['hours']:.1f}h",
                            'flights': m['flights']
                        }
                        for m in stats['by_manufacturer']
                    ]
                    
                    table = ui.table(columns=columns, rows=rows, row_key='manufacturer').classes('w-full')
                    table.on('rowClick', lambda e: filter_by_manufacturer(e.args[1]['manufacturer']))
                else:
                    ui.label('No flight data yet.').classes('text-center p-4')
        
        # ── Export Your Portfolio ────────────────────────────────────────────
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                with ui.column().classes('gap-1'):
                    ui.label('EXPORT YOUR PORTFOLIO').style(
                        'font-size: 14px; font-weight: 800; letter-spacing: 1.5px; '
                        'color: rgba(255,255,255,0.75); text-transform: uppercase;'
                    )
                    ui.label(
                        'A complete breakdown of your flying career — totals, by-aircraft and '
                        'by-manufacturer stats, plus every flight on record.'
                    ).classes('text-caption').style('color:#a0a0a0;')
                with ui.row().classes('gap-3'):
                    ui.button('Portfolio PDF', icon='picture_as_pdf',
                              on_click=generate_pdf_report, color='primary').props('outline').classes('px-5')
                    ui.button('Portfolio CSV', icon='download',
                              on_click=export_flights, color='primary').props('outline').classes('px-5')

        # ── Recent Flights ───────────────────────────────────────────────────
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between mb-3'):
                ui.label('Recent Flights').style('font-size: 14px; font-weight: 800; letter-spacing: 1.5px; color: rgba(255,255,255,0.75); text-transform: uppercase;')
                ui.button('View All', on_click=lambda: navigate_to('flights'), icon='chevron_right').props('flat dense').style('font-size: 12px; color: #667eea;')
            
            flights = db.get_all_flights()[:10]
            
            if flights:
                columns = [
                    {'name': 'date', 'label': 'Date', 'field': 'flight_date', 'sortable': True},
                    {'name': 'drone', 'label': 'Drone Model', 'field': 'drone_model', 'sortable': True},
                    {'name': 'duration', 'label': 'Duration', 'field': 'duration_minutes', 'sortable': True},
                    {'name': 'confidence', 'label': 'Quality', 'field': 'confidence', 'sortable': True},
                ]
                
                rows = []
                for flight in flights:
                    date_str = flight.get('flight_date', '')[:10] if flight.get('flight_date') else 'Unknown'
                    duration = flight.get('duration_minutes', 0)
                    duration_str = f"{duration:.1f} min ({duration/60:.2f} hrs)"
                    
                    rows.append({
                        'id': flight.get('id'),
                        'flight_date': date_str,
                        'drone_model': flight.get('drone_model', 'Unknown'),
                        'duration_minutes': duration_str,
                        'confidence': flight.get('confidence', 'unknown').capitalize(),
                    })
                
                table = ui.table(columns=columns, rows=rows, row_key='flight_date').classes('w-full')
                table.on('rowClick', lambda e: show_flight_details(e.args[1]['id']))
            else:
                ui.label('No flights recorded yet. Import your flight logs to get started!').classes('text-center p-4')

@ui.page('/flights')
def flights_page(drone: str = None, manufacturer: str = None):
    """Flights list page with filters"""
    apply_theme()
    create_header()
    
    # Build filter option lists fresh from the database so any newly-recognized
    # drone/manufacturer shows up the moment its first flight is imported.
    drone_options = ['All'] + [d['model'] for d in db.get_statistics()['by_drone']]
    manufacturer_options = ['All'] + [m['manufacturer'] for m in db.get_statistics()['by_manufacturer']]

    # Get URL parameters — fall back to 'All' if the value doesn't match a known option
    # (e.g. a stale link from before a drone was renamed)
    initial_drone = drone if drone in drone_options else 'All'
    initial_manufacturer = manufacturer if manufacturer in manufacturer_options else 'All'

    with ui.column().classes('w-full p-8 gap-6'):
        ui.label('Flight History').classes('text-h4 font-bold')
        
        # Show filter info if coming from dashboard
        if initial_drone != 'All':
            ui.label(f'Filtered by Drone: {initial_drone}').classes('text-subtitle1 text-primary')
        if initial_manufacturer != 'All':
            ui.label(f'Filtered by Manufacturer: {initial_manufacturer}').classes('text-subtitle1 text-primary')

        # ── Report & Backup ────────────────────────────────────────────────
        with ui.row().classes('w-full gap-3 justify-end items-center'):
            ui.label('Export current view:').classes('text-caption').style('color: #a0a0a0;')

            def _pdf_report_filtered():
                # Pass active filter state so the report can honour it
                generate_pdf_report()

            def _backup_filtered():
                backup_flight_data()

            ui.button('PDF Report', icon='picture_as_pdf',
                      on_click=_pdf_report_filtered).props('outline color=primary').classes('px-5')
            ui.button('Backup', icon='backup',
                      on_click=_backup_filtered).props('outline color=positive').classes('px-5')

        # Filters
        with ui.card().classes('w-full'):
            ui.label('Filters').classes('text-h6 mb-4')
            
            with ui.row().classes('w-full gap-4'):
                drone_filter = ui.select(
                    label='Drone Model',
                    options=drone_options,
                    value=initial_drone
                ).classes('flex-1')

                manufacturer_filter = ui.select(
                    label='Manufacturer',
                    options=manufacturer_options,
                    value=initial_manufacturer
                ).classes('flex-1')
                
                date_from = ui.input(label='From Date', placeholder='YYYY-MM-DD').props('stack-label').classes('flex-1')
                date_to = ui.input(label='To Date', placeholder='YYYY-MM-DD').props('stack-label').classes('flex-1')
                
                ui.button('Apply Filters', on_click=lambda: filter_flights(drone_filter.value, manufacturer_filter.value, date_from.value, date_to.value))
        
        # Flights table
        flights_container = ui.column().classes('w-full')
        
        def filter_flights(drone, manufacturer, date_from_val, date_to_val):
            flights_container.clear()
            
            with flights_container:
                flights = db.get_all_flights()
                
                # Apply filters
                if drone != 'All':
                    flights = [f for f in flights if f.get('drone_model') == drone]
                
                if manufacturer != 'All':
                    flights = [f for f in flights if f.get('manufacturer') == manufacturer]
                
                if date_from_val:
                    flights = [f for f in flights if f.get('flight_date', '') >= date_from_val]
                
                if date_to_val:
                    flights = [f for f in flights if f.get('flight_date', '') <= date_to_val]
                
                ui.label(f'Showing {len(flights)} flights').classes('text-subtitle1 mb-4')
                
                if flights:
                    columns = [
                        {'name': 'drone', 'label': 'Drone', 'field': 'drone_model', 'sortable': True, 'align': 'left'},
                        {'name': 'id', 'label': '#', 'field': 'id', 'sortable': True},
                        {'name': 'date', 'label': 'Date', 'field': 'flight_date', 'sortable': True},
                        {'name': 'duration', 'label': 'Duration', 'field': 'duration_minutes', 'sortable': True},
                        {'name': 'altitude', 'label': 'Max Alt', 'field': 'max_altitude_m', 'sortable': True},
                        {'name': 'distance', 'label': 'Distance', 'field': 'distance_km', 'sortable': True},
                    ]
                    
                    rows = []
                    for flight in flights:
                        rows.append({
                            'drone_model': flight.get('drone_model', 'Unknown'),
                            'id': flight.get('id'),
                            'flight_date': flight.get('flight_date', '')[:10] if flight.get('flight_date') else 'Unknown',
                            'duration_minutes': f"{flight.get('duration_minutes', 0):.1f} min",
                            'max_altitude_m': f"{flight.get('max_altitude_m', 0):.1f}m" if flight.get('max_altitude_m') else 'N/A',
                            'distance_km': f"{flight.get('distance_km', 0):.2f}km" if flight.get('distance_km') else 'N/A',
                        })
                    
                    # Make table clickable
                    table = ui.table(columns=columns, rows=rows, row_key='id').classes('w-full')
                    table.on('rowClick', lambda e: show_flight_details(e.args[1]['id']))
                else:
                    ui.label('No flights match the selected filters.').classes('text-center p-8')
        
        # Initial load with URL parameters
        filter_flights(initial_drone, initial_manufacturer, '', '')
        
        # Action buttons
        with ui.row().classes('w-full justify-between mt-4 items-center'):
            with ui.row().classes('gap-3 items-center'):
                ui.button('Clear All Data', icon='delete_forever', on_click=clear_all_data, color='negative')
                ui.button('Export to CSV', icon='download', on_click=export_flights)

            # ── Gather DJI Data button + help ─────────────────────────────
            with ui.row().classes('items-center gap-2'):
                ui.button(
                    'Enhance DJI Logs',
                    icon='flight_takeoff',
                    on_click=lambda: gather_dji_flight_data(),
                    color='primary',
                ).props('outline').classes('px-4')

                # ? help icon — opens explanation dialog
                with ui.button(icon='help_outline').props('flat round dense').style('color: #a0a0a0;'):
                    with ui.menu().props('auto-close'):
                        with ui.card().style('max-width: 380px; padding: 20px;'):
                            ui.label('What does "Enhance DJI Logs" do?').style(
                                'font-weight: 700; font-size: 15px; margin-bottom: 10px;'
                            )
                            ui.label(
                                'Re-parses all DJI Fly .txt logs already in your logbook '
                                'using the full MIT-licensed dji-log-parser tool. '
                                'This replaces rough estimates with real GPS tracks, '
                                'accurate altitude, speed, and battery telemetry.'
                            ).style('font-size: 13px; color: #a0a0a0; margin-bottom: 12px;')
                            ui.label('Why do I need an internet connection?').style(
                                'font-weight: 600; font-size: 13px; margin-bottom: 6px;'
                            )
                            ui.label(
                                'DJI Fly app v13+ (Mini 3/4, Air 3, Avata 2, etc.) encrypts '
                                'its logs. The first time each log is parsed, one small request '
                                'is made to DJI\'s servers using your API key to retrieve the '
                                'decryption keychain. After that, all parsing is 100% offline '
                                'and the keychain is cached locally forever.'
                            ).style('font-size: 13px; color: #a0a0a0; margin-bottom: 12px;')
                            ui.label('How do I get a free API key?').style(
                                'font-weight: 600; font-size: 13px; margin-bottom: 6px;'
                            )
                            ui.label(
                                '1. Visit developer.dji.com\n'
                                '2. Register / log in with your DJI account\n'
                                '3. Create an app → choose "Open API" type\n'
                                '4. Copy the SDK Key\n'
                                '5. Paste it in Profile → DJI Settings'
                            ).style('font-size: 13px; color: #a0a0a0; white-space: pre-line;')
                            ui.label(
                                'Pre-v13 logs (Mini 2, Air 2S, Phantom 4, etc.) '
                                'parse completely offline — no key needed at all.'
                            ).style('font-size: 12px; color: #667eea; margin-top: 10px;')

def gather_dji_flight_data():
    """Re-parse all DJI .txt flights with the proper dji-log-parser binary."""
    import threading

    has_key = config.has_dji_api_key()

    candidates = db.get_dji_flights_for_reparse()
    if not candidates:
        ui.notify(
            'All DJI logs already have full telemetry data — nothing to enhance.',
            type='positive', timeout=4000
        )
        return

    # Filter to files that still exist on disk
    to_process = [f for f in candidates if f.get('file_path') and Path(f['file_path']).exists()]
    if not to_process:
        ui.notify(
            f'Found {len(candidates)} DJI log(s) to enhance, but none of the '
            'original files are on disk anymore. Re-import them first.',
            type='warning', timeout=6000
        )
        return

    state = {'done': False, 'updated': 0, 'failed': 0, 'skipped': 0, 'current': ''}

    with ui.dialog() as dlg, ui.card().classes('w-full max-w-lg').style('padding: 28px;'):
        ui.label('Enhancing DJI Logs').style('font-size: 20px; font-weight: 700; margin-bottom: 4px;')
        if not has_key:
            ui.label(
                '⚠ No DJI API key set — pre-v13 logs will be enhanced offline. '
                'v13+ encrypted logs will be skipped. Add your key in Profile → DJI Settings.'
            ).style('font-size: 12px; color: #f59e0b; margin-bottom: 12px;')
        else:
            ui.label(
                f'Processing {len(to_process)} log file(s). '
                'v13+ logs will make a one-time call to DJI to fetch decryption keys.'
            ).style('font-size: 13px; color: #a0a0a0; margin-bottom: 12px;')

        progress_bar   = ui.linear_progress(value=0).classes('w-full mb-2')
        current_label  = ui.label('Starting…').style('font-size: 12px; color: #a0a0a0;')
        summary_label  = ui.label('').style('font-size: 12px; color: #a0a0a0;')
        close_btn      = ui.button('Close', on_click=lambda: (dlg.close(), ui.navigate.reload())).classes('mt-4 w-full')
        close_btn.visible = False

        def poll():
            current_label.text = state['current']
            summary_label.text = (
                f"Updated: {state['updated']}  Skipped: {state['skipped']}  Failed: {state['failed']}"
            )
            if state['done']:
                progress_bar.set_value(1.0)
                current_label.text = 'Done!'
                close_btn.visible  = True
                timer.cancel()

        timer = ui.timer(0.2, poll)

        def worker():
            total = len(to_process)
            for i, flight in enumerate(to_process):
                fp   = flight['file_path']
                name = flight['file_name']
                state['current'] = f'[{i+1}/{total}] {name}'
                progress_bar.set_value(i / total)

                try:
                    result = parser_factory.parse_file(fp)
                    if result and result.get('parser_used') == 'DJI Log Parser (MIT)':
                        db.update_flight(flight['id'], result)
                        state['updated'] += 1
                    else:
                        state['skipped'] += 1
                except Exception as e:
                    print(f"[Gather DJI] Error on {name}: {e}")
                    state['failed'] += 1

            state['done'] = True

        threading.Thread(target=worker, daemon=True).start()

    dlg.open()


def export_flights():
    """Export flights to CSV"""
    try:
        flights = db.get_all_flights()
        
        if not flights:
            ui.notify('No flights to export', type='warning')
            return
        
        # Create CSV
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'date', 'drone_model', 'manufacturer', 'duration_minutes',
            'max_altitude_m', 'max_speed_ms', 'distance_km', 'confidence'
        ])
        
        writer.writeheader()
        for flight in flights:
            writer.writerow({
                'id': flight.get('id'),
                'date': flight.get('flight_date', ''),
                'drone_model': flight.get('drone_model', ''),
                'manufacturer': flight.get('manufacturer', ''),
                'duration_minutes': flight.get('duration_minutes', 0),
                'max_altitude_m': flight.get('max_altitude_m', ''),
                'max_speed_ms': flight.get('max_speed_ms', ''),
                'distance_km': flight.get('distance_km', ''),
                'confidence': flight.get('confidence', ''),
            })
        
        # Save file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'flight_export_{timestamp}.csv'
        filepath = Path('data/exports') / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        filepath.write_text(output.getvalue())
        
        ui.notify(f'Exported to {filepath}', type='positive')
        
    except Exception as e:
        ui.notify(f'Export failed: {e}', type='negative')

def clear_all_data():
    """Clear all flight data"""
    with ui.dialog() as dialog, ui.card():
        ui.label('Are you sure you want to delete ALL flight records?').classes('text-h6')
        ui.label('This cannot be undone!').classes('text-negative')
        with ui.row():
            ui.button('Cancel', on_click=dialog.close)
            ui.button('Delete All', on_click=lambda: do_clear(dialog), color='negative')
    
    def do_clear(dialog):
        try:
            db.clear_all()
            dialog.close()
            ui.notify('All flight data cleared', type='info')
            ui.navigate.reload()
        except Exception as e:
            ui.notify(f'Failed to clear data: {e}', type='negative')
    
    dialog.open()

def show_flight_details(flight_id):
    """Show detailed flight information in a dialog"""
    flights = db.get_all_flights()
    flight = next((f for f in flights if f['id'] == flight_id), None)
    
    if not flight:
        ui.notify('Flight not found', type='negative')
        return
    
    def export_flight_csv():
        """Export flight data to CSV"""
        try:
            import csv
            from io import StringIO
            from datetime import datetime
            
            # Create CSV content
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Field', 'Value'])
            
            # Basic information
            writer.writerow(['Flight ID', flight.get('id', '')])
            writer.writerow(['File Name', flight.get('file_name', '')])
            writer.writerow(['Drone Model', flight.get('drone_model', '')])
            writer.writerow(['Manufacturer', flight.get('manufacturer', '')])
            writer.writerow(['Flight Date', flight.get('flight_date', '')[:19] if flight.get('flight_date') else ''])
            
            # Flight metrics
            duration = flight.get('duration_minutes', 0)
            writer.writerow(['Duration (minutes)', f"{duration:.1f}"])
            writer.writerow(['Duration (hours)', f"{duration/60:.2f}"])
            writer.writerow(['Max Altitude (m)', f"{flight.get('max_altitude_m', 0):.1f}"])
            writer.writerow(['Max Speed (m/s)', f"{flight.get('max_speed_ms', 0):.1f}"])
            writer.writerow(['Distance (km)', f"{flight.get('distance_km', 0):.2f}"])
            
            # Battery
            writer.writerow(['Battery Start (%)', flight.get('battery_start', '')])
            writer.writerow(['Battery End (%)', flight.get('battery_end', '')])
            if flight.get('battery_start') and flight.get('battery_end'):
                writer.writerow(['Battery Used (%)', flight['battery_start'] - flight['battery_end']])
            
            # GPS
            writer.writerow(['Start Latitude', flight.get('location_start_lat', '')])
            writer.writerow(['Start Longitude', flight.get('location_start_lon', '')])
            writer.writerow(['End Latitude', flight.get('location_end_lat', '')])
            writer.writerow(['End Longitude', flight.get('location_end_lon', '')])
            
            # Data source
            writer.writerow(['Parser Used', flight.get('parser_used', '')])
            writer.writerow(['Data Quality', flight.get('confidence', '')])
            writer.writerow(['Import Date', flight.get('import_date', '')])
            
            # Get CSV content
            csv_content = output.getvalue()
            
            # Create download
            filename = f"flight_{flight.get('id', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            ui.download(csv_content.encode('utf-8'), filename)
            ui.notify(f'Flight data exported to {filename}', type='positive')
            
        except Exception as e:
            ui.notify(f'Failed to export CSV: {e}', type='negative')
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl'):
        # Header with export and delete buttons
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label(f"Flight Details - {flight.get('file_name', 'Unknown')}").classes('text-h5')
            with ui.row().classes('gap-2'):
                ui.button('PDF Report', icon='picture_as_pdf',
                          on_click=lambda: generate_flight_pdf(flight_id), color='primary').props('outline')
                ui.button('CSV Export', icon='timeline',
                          on_click=lambda: export_flight_airdata_csv(flight), color='primary').props('outline')
                ui.button('Export CSV', icon='download', on_click=export_flight_csv, color='primary')
                ui.button('Delete Flight', icon='delete', on_click=lambda: delete_flight(flight_id, dialog), color='negative')
        
        # Basic info
        with ui.card().classes('w-full mb-4'):
            ui.label('Basic Information').classes('text-h6 mb-2')
            ui.label(f"Drone: {flight.get('drone_model', 'Unknown')}")
            ui.label(f"Manufacturer: {flight.get('manufacturer', 'Unknown')}")
            date_str = flight.get('flight_date', '')[:19] if flight.get('flight_date') else 'Unknown'
            ui.label(f"Date: {date_str}")
        
        # Flight metrics
        with ui.card().classes('w-full mb-4'):
            ui.label('Flight Metrics').classes('text-h6 mb-2')
            duration = flight.get('duration_minutes', 0)
            ui.label(f"Duration: {duration:.1f} minutes ({duration/60:.2f} hours)")
            
            if flight.get('max_altitude_m'):
                ui.label(f"Max Altitude: {flight['max_altitude_m']:.1f} meters")
            if flight.get('max_speed_ms'):
                ui.label(f"Max Speed: {flight['max_speed_ms']:.1f} m/s")
            if flight.get('distance_km'):
                ui.label(f"Distance: {flight['distance_km']:.2f} km")
        
        # Battery
        if flight.get('battery_start') or flight.get('battery_end'):
            with ui.card().classes('w-full mb-4'):
                ui.label('Battery').classes('text-h6 mb-2')
                if flight.get('battery_start'):
                    ui.label(f"Start: {flight['battery_start']}%")
                if flight.get('battery_end'):
                    ui.label(f"End: {flight['battery_end']}%")
                if flight.get('battery_start') and flight.get('battery_end'):
                    used = flight['battery_start'] - flight['battery_end']
                    ui.label(f"Used: {used}%")
        
        # GPS
        if flight.get('location_start_lat'):
            with ui.card().classes('w-full mb-4'):
                ui.label('GPS Coordinates').classes('text-h6 mb-2')
                ui.label(f"Start: {flight['location_start_lat']:.6f}, {flight['location_start_lon']:.6f}")
                if flight.get('location_end_lat'):
                    ui.label(f"End: {flight['location_end_lat']:.6f}, {flight['location_end_lon']:.6f}")
        
        # Data quality
        with ui.card().classes('w-full mb-4'):
            ui.label('Data Source').classes('text-h6 mb-2')
            ui.label(f"Parser: {flight.get('parser_used', 'Unknown')}")
            ui.label(f"Quality: {flight.get('confidence', 'unknown').capitalize()}")
        
        # Charts - if raw_data is available
        if flight.get('raw_data'):
            try:
                raw_data = json.loads(flight['raw_data']) if isinstance(flight['raw_data'], str) else flight['raw_data']
                
                # Altitude chart
                if raw_data.get('altitude_profile'):
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Altitude Profile').classes('text-h6 mb-2')
                        alt_data = raw_data['altitude_profile']
                        duration_min = flight.get('duration_minutes', 0)
                        times = [p['time']/60 for p in alt_data]
                        alts = [p['alt'] for p in alt_data]
                        # Anchor to ground at takeoff and landing
                        if times and times[0] > 0.08:
                            times = [0] + times
                            alts = [0] + alts
                        if times and duration_min and times[-1] < duration_min - 0.08:
                            times = times + [duration_min]
                            alts = alts + [0]

                        import plotly.graph_objects as go
                        colors_t = get_theme_colors()
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=times, y=alts, mode='lines', name='Altitude',
                            line=dict(color='#667eea', width=2),
                            fill='tozeroy', fillcolor='rgba(102,126,234,0.15)'
                        ))
                        fig.update_layout(
                            xaxis_title='Time (minutes)',
                            yaxis_title='Altitude (m)',
                            height=280,
                            margin=dict(l=50, r=20, t=20, b=50),
                            plot_bgcolor=colors_t['surface'],
                            paper_bgcolor=colors_t['surface'],
                            font=dict(color='#ffffff'),
                            xaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True),
                            yaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True, rangemode='tozero'),
                            showlegend=False,
                        )
                        ui.plotly(fig).classes('w-full')
                
                # Speed chart
                if raw_data.get('speed_profile'):
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Speed Profile').classes('text-h6 mb-2')
                        speed_data = raw_data['speed_profile']
                        duration_min = flight.get('duration_minutes', 0)
                        times = [p['time']/60 for p in speed_data]
                        speeds = [p['speed'] for p in speed_data]
                        # Anchor to 0 at start and end
                        if times and times[0] > 0.08:
                            times = [0] + times
                            speeds = [0] + speeds
                        if times and duration_min and times[-1] < duration_min - 0.08:
                            times = times + [duration_min]
                            speeds = speeds + [0]

                        colors_t = get_theme_colors()
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=times, y=speeds, mode='lines', name='Speed',
                            line=dict(color='#764ba2', width=2),
                            fill='tozeroy', fillcolor='rgba(118,75,162,0.15)'
                        ))
                        fig.update_layout(
                            xaxis_title='Time (minutes)',
                            yaxis_title='Speed (m/s)',
                            height=280,
                            margin=dict(l=50, r=20, t=20, b=50),
                            plot_bgcolor=colors_t['surface'],
                            paper_bgcolor=colors_t['surface'],
                            font=dict(color='#ffffff'),
                            xaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True),
                            yaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True, rangemode='tozero'),
                            showlegend=False,
                        )
                        ui.plotly(fig).classes('w-full')

                # Vertical speed chart (climb / descent rate)
                if raw_data.get('vertical_speed_profile') and len(raw_data['vertical_speed_profile']) > 0:
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Vertical Speed (Climb / Descent)').classes('text-h6 mb-2')
                        vs_data = raw_data['vertical_speed_profile']
                        duration_min = flight.get('duration_minutes', 0)
                        times  = [p['time'] / 60 for p in vs_data]
                        vspeeds = [p['vspeed'] for p in vs_data]
                        if times and times[0] > 0.08:
                            times   = [0] + times
                            vspeeds = [0] + vspeeds
                        if times and duration_min and times[-1] < duration_min - 0.08:
                            times   = times   + [duration_min]
                            vspeeds = vspeeds + [0]

                        colors_t = get_theme_colors()
                        fig = go.Figure()
                        # Positive (climb) filled green, negative (descent) filled red
                        fig.add_trace(go.Scatter(
                            x=times, y=vspeeds, mode='lines', name='Vertical Speed',
                            line=dict(color='#10b981', width=2),
                            fill='tozeroy',
                            fillcolor='rgba(16,185,129,0.15)',
                        ))
                        fig.add_shape(type='line', x0=0, x1=1, xref='paper',
                                      y0=0, y1=0, yref='y',
                                      line=dict(color='rgba(255,255,255,0.3)', width=1, dash='dot'))
                        fig.update_layout(
                            xaxis_title='Time (minutes)',
                            yaxis_title='m/s  (+ climb  − descent)',
                            height=240,
                            margin=dict(l=60, r=20, t=20, b=50),
                            plot_bgcolor=colors_t['surface'],
                            paper_bgcolor=colors_t['surface'],
                            font=dict(color='#ffffff'),
                            xaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True),
                            yaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True, zeroline=True,
                                       zerolinecolor='rgba(255,255,255,0.25)'),
                            showlegend=False,
                        )
                        ui.plotly(fig).classes('w-full')

                # GPS track map
                if raw_data.get('gps_track') and len(raw_data['gps_track']) > 0:
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Flight Path').classes('text-h6 mb-2')
                        gps_data = raw_data['gps_track']
                        lats = [p['lat'] for p in gps_data]
                        lons = [p['lon'] for p in gps_data]
                        
                        fig = go.Figure()
                        fig.add_trace(go.Scattermapbox(
                            lat=lats,
                            lon=lons,
                            mode='lines+markers',
                            marker=dict(size=4, color='#667eea'),
                            line=dict(width=2, color='#764ba2'),
                            name='Flight Path'
                        ))
                        
                        # Center map on flight path
                        center_lat = sum(lats) / len(lats)
                        center_lon = sum(lons) / len(lons)
                        
                        fig.update_layout(
                            mapbox=dict(
                                style='open-street-map',
                                center=dict(lat=center_lat, lon=center_lon),
                                zoom=14
                            ),
                            height=400,
                            margin=dict(l=0, r=0, t=0, b=0)
                        )
                        ui.plotly(fig).classes('w-full')
                
                # Battery telemetry chart
                if raw_data.get('battery_profile') and len(raw_data['battery_profile']) > 0:
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Battery Telemetry').classes('text-h6 mb-2')
                        battery_data = raw_data['battery_profile']
                        times = [p['time']/60 for p in battery_data]
                        
                        fig = go.Figure()
                        
                        # Voltage trace
                        if any('voltage' in p for p in battery_data):
                            voltages = [p.get('voltage', 0) for p in battery_data]
                            fig.add_trace(go.Scatter(
                                x=times, y=voltages,
                                mode='lines',
                                name='Voltage (V)',
                                line=dict(color='#10b981', width=2),
                                yaxis='y'
                            ))
                        
                        # Current trace
                        if any('current' in p for p in battery_data):
                            currents = [p.get('current', 0) for p in battery_data]
                            fig.add_trace(go.Scatter(
                                x=times, y=currents,
                                mode='lines',
                                name='Current (A)',
                                line=dict(color='#f59e0b', width=2),
                                yaxis='y2'
                            ))
                        
                        # Remaining % trace
                        if any('remaining' in p for p in battery_data):
                            remaining = [p.get('remaining', 0) for p in battery_data]
                            fig.add_trace(go.Scatter(
                                x=times, y=remaining,
                                mode='lines',
                                name='Remaining (%)',
                                line=dict(color='#667eea', width=2),
                                yaxis='y3'
                            ))
                        
                        fig.update_layout(
                            xaxis_title='Time (minutes)',
                            yaxis=dict(title='Voltage (V)', side='left', color='#ffffff'),
                            yaxis2=dict(title='Current (A)', overlaying='y', side='right', color='#ffffff'),
                            yaxis3=dict(title='Remaining (%)', overlaying='y', side='right', position=0.95, color='#ffffff'),
                            height=350,
                            margin=dict(l=50, r=100, t=50, b=50),
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='#ffffff'),
                            legend=dict(
                                orientation='h',
                                yanchor='top',
                                y=1.12,
                                xanchor='left',
                                x=0,
                                bgcolor='rgba(0,0,0,0.5)'
                            )
                        )
                        ui.plotly(fig).classes('w-full')

                # Battery temperature chart
                if raw_data.get('battery_profile') and any('temperature' in p for p in raw_data['battery_profile']):
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Battery Temperature').classes('text-h6 mb-2')
                        bt_data = raw_data['battery_profile']
                        times = [p['time'] / 60 for p in bt_data if 'temperature' in p]
                        temps = [p['temperature'] for p in bt_data if 'temperature' in p]
                        colors_t = get_theme_colors()
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=times, y=temps, mode='lines', name='Temp (°C)',
                            line=dict(color='#f97316', width=2),
                            fill='tozeroy', fillcolor='rgba(249,115,22,0.12)',
                        ))
                        fig.update_layout(
                            xaxis_title='Time (minutes)',
                            yaxis_title='Temperature (°C)',
                            height=220,
                            margin=dict(l=60, r=20, t=20, b=50),
                            plot_bgcolor=colors_t['surface'],
                            paper_bgcolor=colors_t['surface'],
                            font=dict(color='#ffffff'),
                            xaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True),
                            yaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True),
                            showlegend=False,
                        )
                        ui.plotly(fig).classes('w-full')

                # Gimbal angle chart
                if raw_data.get('gimbal_profile') and len(raw_data['gimbal_profile']) > 0:
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Gimbal — Pitch / Roll / Yaw').classes('text-h6 mb-2')
                        gim_data = raw_data['gimbal_profile']
                        times = [p['time'] / 60 for p in gim_data]
                        colors_t = get_theme_colors()
                        fig = go.Figure()
                        if any('heading' in p for p in gim_data):
                            fig.add_trace(go.Scatter(
                                x=times, y=[p.get('heading', 0) for p in gim_data],
                                mode='lines', name='Heading',
                                line=dict(color='#8b5cf6', width=1.5),
                            ))
                        if any('pitch' in p for p in gim_data):
                            fig.add_trace(go.Scatter(
                                x=times, y=[p.get('pitch', 0) for p in gim_data],
                                mode='lines', name='Pitch',
                                line=dict(color='#667eea', width=2),
                            ))
                        if any('roll' in p for p in gim_data):
                            fig.add_trace(go.Scatter(
                                x=times, y=[p.get('roll', 0) for p in gim_data],
                                mode='lines', name='Roll',
                                line=dict(color='#10b981', width=1.5),
                            ))
                        if any('yaw' in p for p in gim_data):
                            fig.add_trace(go.Scatter(
                                x=times, y=[p.get('yaw', 0) for p in gim_data],
                                mode='lines', name='Yaw',
                                line=dict(color='#f59e0b', width=1.5),
                            ))
                        fig.add_shape(type='line', x0=0, x1=1, xref='paper',
                                      y0=0, y1=0, yref='y',
                                      line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dot'))
                        fig.update_layout(
                            xaxis_title='Time (minutes)',
                            yaxis_title='Angle (degrees)',
                            height=260,
                            margin=dict(l=60, r=20, t=20, b=50),
                            plot_bgcolor=colors_t['surface'],
                            paper_bgcolor=colors_t['surface'],
                            font=dict(color='#ffffff'),
                            xaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True),
                            yaxis=dict(gridcolor='rgba(255,255,255,0.08)', showgrid=True, zeroline=True,
                                       zerolinecolor='rgba(255,255,255,0.25)'),
                            legend=dict(orientation='h', yanchor='top', y=1.12, xanchor='left', x=0,
                                        bgcolor='rgba(0,0,0,0.5)'),
                        )
                        ui.plotly(fig).classes('w-full')

                # Motor/RC outputs chart
                if raw_data.get('motor_profile') and len(raw_data['motor_profile']) > 0:
                    with ui.card().classes('w-full mb-4'):
                        motor_data = raw_data['motor_profile']
                        duration_min = flight.get('duration_minutes', 0)
                        times = [p['time']/60 for p in motor_data]
                        # Anchor motor chart: prepend idle (1000 PWM) and append at end
                        _first_p = dict(motor_data[0])
                        _last_p = dict(motor_data[-1])
                        if times and times[0] > 0.08:
                            anchor_start = {k: (1000 if k.startswith('motor') else v) for k, v in _first_p.items()}
                            anchor_start['time'] = 0
                            motor_data = [anchor_start] + list(motor_data)
                            times = [0] + times
                        if times and duration_min and times[-1] < duration_min - 0.08:
                            anchor_end = {k: (1000 if k.startswith('motor') else v) for k, v in _last_p.items()}
                            anchor_end['time'] = duration_min * 60
                            motor_data = list(motor_data) + [anchor_end]
                            times = times + [duration_min]
                        
                        # Check if this is ArduPilot (motor1-8) or Airdata (elevator/aileron/etc)
                        has_motors = any('motor1' in p for p in motor_data)
                        has_rc_inputs = any('elevator' in p for p in motor_data)
                        
                        if has_motors:
                            ui.label('Motor Outputs (PWM)').classes('text-h6 mb-2')
                        elif has_rc_inputs:
                            ui.label('RC Control Inputs').classes('text-h6 mb-2')
                        else:
                            ui.label('Motor/RC Data').classes('text-h6 mb-2')
                        
                        fig = go.Figure()
                        colors = ['#667eea', '#764ba2', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4']
                        
                        if has_motors:
                            # ArduPilot motor outputs (PWM 1000-2000)
                            for i in range(1, 9):
                                motor_key = f'motor{i}'
                                if any(motor_key in p for p in motor_data):
                                    values = [p.get(motor_key, 0) for p in motor_data]
                                    # Only show if motor was active (not all zeros)
                                    if max(values) > 1000:
                                        fig.add_trace(go.Scatter(
                                            x=times, y=values,
                                            mode='lines',
                                            name=f'Motor {i}',
                                            line=dict(color=colors[i-1], width=1.5)
                                        ))
                            y_label = 'PWM Output'
                        
                        elif has_rc_inputs:
                            # Airdata RC inputs (percentage -100 to +100, centered at 0)
                            rc_channels = [
                                ('elevator', 'Elevator (Pitch)', colors[0]),
                                ('aileron', 'Aileron (Roll)', colors[1]),
                                ('throttle', 'Throttle', colors[2]),
                                ('rudder', 'Rudder (Yaw)', colors[3])
                            ]
                            for key, label, color in rc_channels:
                                if any(key in p for p in motor_data):
                                    values = [p.get(key, 0) for p in motor_data]
                                    # Show if channel has any non-zero values (positive or negative)
                                    if any(v != 0 for v in values):
                                        fig.add_trace(go.Scatter(
                                            x=times, y=values,
                                            mode='lines',
                                            name=label,
                                            line=dict(color=color, width=2)
                                        ))
                            y_label = 'RC Input (% from center)'
                        
                        else:
                            # Fallback for unknown motor/RC data format
                            y_label = 'Value'
                        
                        colors_theme = get_theme_colors()
                        fig.update_layout(
                            xaxis_title='Time (minutes)',
                            yaxis_title=y_label,
                            hovermode='x unified',
                            plot_bgcolor=colors_theme['surface'],
                            paper_bgcolor=colors_theme['surface'],
                            font=dict(color=colors_theme['text']),
                            xaxis=dict(gridcolor=colors_theme['text_secondary'], showgrid=True),
                            yaxis=dict(
                                gridcolor=colors_theme['text_secondary'],
                                showgrid=True,
                                # For RC inputs, show zero line to indicate neutral position
                                zeroline=True if has_rc_inputs else False,
                                zerolinecolor=colors_theme['text_secondary'] if has_rc_inputs else None,
                                zerolinewidth=2 if has_rc_inputs else None
                            ),
                            legend=dict(
                                orientation='h',
                                yanchor='bottom',
                                y=1.02,
                                xanchor='right',
                                x=1,
                                bgcolor='rgba(0,0,0,0.5)'
                            )
                        )
                        ui.plotly(fig).classes('w-full')
                
                # Vibration analysis chart
                if raw_data.get('vibration_profile') and len(raw_data['vibration_profile']) > 0:
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Vibration Analysis').classes('text-h6 mb-2')
                        vibe_data = raw_data['vibration_profile']
                        times = [p['time']/60 for p in vibe_data]
                        
                        fig = go.Figure()
                        
                        # X, Y, Z vibration traces
                        if any('x' in p for p in vibe_data):
                            x_vibes = [p.get('x', 0) for p in vibe_data]
                            fig.add_trace(go.Scatter(
                                x=times, y=x_vibes,
                                mode='lines',
                                name='X-axis',
                                line=dict(color='#ef4444', width=1.5)
                            ))
                        
                        if any('y' in p for p in vibe_data):
                            y_vibes = [p.get('y', 0) for p in vibe_data]
                            fig.add_trace(go.Scatter(
                                x=times, y=y_vibes,
                                mode='lines',
                                name='Y-axis',
                                line=dict(color='#10b981', width=1.5)
                            ))
                        
                        if any('z' in p for p in vibe_data):
                            z_vibes = [p.get('z', 0) for p in vibe_data]
                            fig.add_trace(go.Scatter(
                                x=times, y=z_vibes,
                                mode='lines',
                                name='Z-axis',
                                line=dict(color='#667eea', width=1.5)
                            ))
                        
                        fig.update_layout(
                            xaxis_title='Time (minutes)',
                            yaxis_title='Vibration Level',
                            height=300,
                            margin=dict(l=50, r=20, t=40, b=50),
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='#ffffff'),
                            legend=dict(
                                orientation='h',
                                yanchor='top',
                                y=1.15,
                                xanchor='left',
                                x=0,
                                bgcolor='rgba(0,0,0,0.5)'
                            )
                        )
                        ui.plotly(fig).classes('w-full')
                
                # Attitude - Roll/Pitch chart (separate from yaw due to scale difference)
                if raw_data.get('attitude_profile') and len(raw_data['attitude_profile']) > 0:
                    att_data = raw_data['attitude_profile']
                    times = [p['time']/60 for p in att_data]
                    
                    # Roll and Pitch chart
                    if any('roll' in p for p in att_data) or any('pitch' in p for p in att_data):
                        with ui.card().classes('w-full mb-4'):
                            ui.label('Roll and Pitch').classes('text-h6 mb-2')
                            
                            import plotly.graph_objects as go
                            fig = go.Figure()
                            colors_theme = get_theme_colors()
                            
                            # Roll trace
                            if any('roll' in p for p in att_data):
                                rolls = [p.get('roll', 0) for p in att_data]
                                fig.add_trace(go.Scatter(
                                    x=times, y=rolls,
                                    mode='lines',
                                    name='Roll',
                                    line=dict(color='#ef4444', width=2)
                                ))

                            # Pitch trace
                            if any('pitch' in p for p in att_data):
                                pitches = [p.get('pitch', 0) for p in att_data]
                                fig.add_trace(go.Scatter(
                                    x=times, y=pitches,
                                    mode='lines',
                                    name='Pitch',
                                    line=dict(color='#10b981', width=2)
                                ))
                            
                            fig.update_layout(
                                xaxis_title='Time (minutes)',
                                yaxis_title='Degrees',
                                hovermode='x unified',
                                plot_bgcolor=colors_theme['surface'],
                                paper_bgcolor=colors_theme['surface'],
                                font=dict(color=colors_theme['text']),
                                xaxis=dict(gridcolor=colors_theme['text_secondary'], showgrid=True),
                                yaxis=dict(gridcolor=colors_theme['text_secondary'], showgrid=True),
                                height=300,
                                margin=dict(l=50, r=20, t=10, b=50),
                                legend=dict(
                                    orientation='h',
                                    yanchor='bottom',
                                    y=1.02,
                                    xanchor='right',
                                    x=1,
                                    bgcolor='rgba(0,0,0,0.5)'
                                )
                            )
                            ui.plotly(fig).classes('w-full')
                    
                    # Yaw chart (separate)
                    if any('yaw' in p for p in att_data):
                        with ui.card().classes('w-full mb-4'):
                            ui.label('Yaw (Heading)').classes('text-h6 mb-2')
                            
                            import plotly.graph_objects as go
                            fig = go.Figure()
                            colors_theme = get_theme_colors()
                            
                            yaws = [p.get('yaw', 0) for p in att_data]
                            fig.add_trace(go.Scatter(
                                x=times, y=yaws,
                                mode='lines',
                                name='Yaw',
                                line=dict(color='#667eea', width=2)
                            ))
                            
                            fig.update_layout(
                                xaxis_title='Time (minutes)',
                                yaxis_title='Degrees',
                                hovermode='x unified',
                                plot_bgcolor=colors_theme['surface'],
                                paper_bgcolor=colors_theme['surface'],
                                font=dict(color=colors_theme['text']),
                                xaxis=dict(gridcolor=colors_theme['text_secondary'], showgrid=True),
                                yaxis=dict(gridcolor=colors_theme['text_secondary'], showgrid=True),
                                height=250,
                                margin=dict(l=50, r=20, t=10, b=50),
                                showlegend=False
                            )
                            ui.plotly(fig).classes('w-full')

                # Wind conditions chart (Airdata CSV)
                if raw_data.get('wind_profile') and len(raw_data['wind_profile']) > 0:
                    with ui.card().classes('w-full mb-4'):
                        ui.label('Wind Conditions').classes('text-h6 mb-2')
                        wind_data = raw_data['wind_profile']
                        times = [p['time']/60 for p in wind_data]
                        
                        import plotly.graph_objects as go
                        from plotly.subplots import make_subplots
                        
                        # Create subplot with 2 y-axes
                        fig = make_subplots(specs=[[{"secondary_y": True}]])
                        
                        # Wind speed
                        if any('speed' in p for p in wind_data):
                            speeds = [p.get('speed', 0) for p in wind_data]
                            fig.add_trace(
                                go.Scatter(
                                    x=times, y=speeds,
                                    mode='lines',
                                    name='Wind Speed',
                                    line=dict(color='#667eea', width=2)
                                ),
                                secondary_y=False
                            )
                        
                        # Wind direction
                        if any('direction' in p for p in wind_data):
                            directions = [p.get('direction', 0) for p in wind_data]
                            fig.add_trace(
                                go.Scatter(
                                    x=times, y=directions,
                                    mode='lines',
                                    name='Wind Direction',
                                    line=dict(color='#f59e0b', width=2, dash='dot')
                                ),
                                secondary_y=True
                            )
                        
                        colors = get_theme_colors()
                        fig.update_xaxes(title_text='Time (minutes)', gridcolor=colors['text_secondary'], showgrid=True)
                        fig.update_yaxes(title_text='Speed (m/s)', secondary_y=False, gridcolor=colors['text_secondary'], showgrid=True)
                        fig.update_yaxes(title_text='Direction (degrees)', secondary_y=True, gridcolor=colors['text_secondary'], showgrid=True)
                        
                        fig.update_layout(
                            hovermode='x unified',
                            plot_bgcolor=colors['surface'],
                            paper_bgcolor=colors['surface'],
                            font=dict(color=colors['text']),
                            legend=dict(
                                orientation='h',
                                yanchor='bottom',
                                y=1.02,
                                xanchor='right',
                                x=1,
                                bgcolor='rgba(0,0,0,0.5)'
                            )
                        )
                        ui.plotly(fig).classes('w-full')
            except Exception as e:
                ui.label(f'Could not load charts: {e}').classes('text-caption text-negative')
        
        ui.button('Close', on_click=dialog.close).classes('mt-4')
    
    dialog.open()

def delete_flight(flight_id, dialog):
    """Delete a single flight"""
    try:
        db.delete_flight(flight_id)
        dialog.close()
        ui.notify('Flight deleted successfully', type='positive')
        ui.navigate.reload()
    except Exception as e:
        ui.notify(f'Failed to delete flight: {e}', type='negative')

@ui.page('/import')
def import_page():
    """Import page for uploading flight logs"""
    apply_theme()
    create_header()
    
    with ui.column().classes('w-full p-8 gap-6'):
        ui.label('Import Flight Logs').classes('text-h4 font-bold')
        
        # File upload
        with ui.card().classes('w-full'):
            ui.label('Upload Files').classes('text-h6 mb-4')
            
            ui.upload(
                label='Select flight log files',
                multiple=True,
                on_upload=handle_file_upload,
                auto_upload=True
            ).props('accept=".txt,.csv,.bin,.BIN,.dat,.DAT,.tlog,.rlog"').classes('w-full')
        
        # Folder import
        with ui.card().classes('w-full'):
            ui.label('Import from Folder').classes('text-h6 mb-4')

            folder_input = ui.input(
                label='Folder Path',
                placeholder='Click Browse or paste a path…',
            ).props('stack-label').classes('w-full mb-2')

            async def browse_folder():
                import asyncio
                import threading
                import tkinter as tk
                from tkinter import filedialog

                def _pick():
                    root = tk.Tk()
                    root.withdraw()
                    root.wm_attributes('-topmost', True)
                    p = filedialog.askdirectory(title='Select flight logs folder')
                    root.destroy()
                    return p

                chosen = await asyncio.get_event_loop().run_in_executor(None, _pick)
                if not chosen:
                    return

                chosen = chosen.replace('/', '\\')
                folder_input.set_value(chosen)

                folder_name = Path(chosen).name or chosen
                exts = ('*.txt', '*.csv', '*.bin', '*.BIN', '*.dat', '*.DAT')
                files = []
                for ext in exts:
                    files += list(Path(chosen).rglob(ext))

                if not files:
                    ui.notify('No flight log files found in that folder.', type='warning')
                    return

                total = len(files)

                # Single dialog — confirm phase switches to progress phase in-place
                with ui.dialog() as dlg, ui.card().classes('gap-4').style('min-width:420px; padding:28px;'):

                    # ── Phase 1: confirm ──────────────────────────────────────
                    confirm_col = ui.column().classes('gap-2 w-full')
                    with confirm_col:
                        ui.label('Import Flight Logs').classes('text-h6 font-bold')
                        ui.label('Import all logs from:').classes('text-caption opacity-70')
                        ui.label(f'"{folder_name}"').classes('text-body1 font-bold')
                        ui.label(chosen).classes('text-caption font-mono').style('color:#888;')
                        ui.label(f'{total} file{"s" if total != 1 else ""} found') \
                            .classes('text-caption').style('color:#10b981;')

                    # ── Phase 2: progress (hidden until Import clicked) ───────
                    prog_col = ui.column().classes('gap-3 w-full')
                    prog_col.visible = False
                    with prog_col:
                        prog_label  = ui.label(f'0 of {total} files…').classes('text-body2')
                        prog_bar    = ui.linear_progress(value=0).classes('w-full')
                        file_label  = ui.label('Starting…').classes('text-caption').style('color:#a0a0a0;')
                        stats_label = ui.label('').classes('text-caption').style('color:#a0a0a0;')
                        with ui.row().classes('gap-2 w-full mt-1'):
                            cancel_btn = ui.button(
                                'Cancel', icon='stop',
                                on_click=lambda: state.update({'cancelled': True}),
                            ).props('flat color=negative').classes('flex-1')
                            done_btn = ui.button(
                                'Done', icon='check',
                                on_click=lambda: (dlg.close(), ui.navigate.reload()),
                            ).props('color=positive').classes('flex-1')
                            done_btn.visible = False

                    # ── Button row (confirm phase) ────────────────────────────
                    btn_row = ui.row().classes('gap-2 justify-end w-full mt-1')
                    with btn_row:
                        ui.button('Cancel', on_click=dlg.close).props('flat')

                        def start_import():
                            confirm_col.visible = False
                            btn_row.visible     = False
                            prog_col.visible    = True

                            state.update({'done': False, 'i': 0, 'current': '',
                                          'imported': 0, 'skipped': 0, 'failed': 0,
                                          'cancelled': False})

                            def poll():
                                prog_bar.set_value(state['i'] / total if total else 1)
                                prog_label.set_text(f"{state['i']} of {total} files…")
                                file_label.set_text(state['current'])
                                if state['done']:
                                    prog_bar.set_value(state['i'] / total if total else 1)
                                    prog_label.set_text(
                                        'Cancelled.' if state['cancelled'] else 'Import complete!'
                                    )
                                    file_label.set_text('')
                                    stats_label.set_text(
                                        f"✓ {state['imported']} imported  ·  "
                                        f"⊘ {state['skipped']} skipped  ·  "
                                        f"✗ {state['failed']} failed"
                                    )
                                    cancel_btn.visible = False
                                    done_btn.visible   = True
                                    t.cancel()

                            t = ui.timer(0.1, poll)

                            def worker():
                                for idx, fp in enumerate(files, 1):
                                    if state['cancelled']:
                                        break
                                    state['i']       = idx
                                    state['current'] = fp.name
                                    try:
                                        data = parser_factory.parse_file(str(fp))
                                        if data:
                                            state['imported' if db.add_flight(data) else 'skipped'] += 1
                                        else:
                                            state['failed'] += 1
                                    except Exception as exc:
                                        print(f'Error importing {fp}: {exc}')
                                        state['failed'] += 1
                                db.log_import(
                                    state['imported'], state['skipped'],
                                    'folder_import', f'Folder: {chosen}',
                                )
                                state['done'] = True

                            threading.Thread(target=worker, daemon=True).start()

                        ui.button('Import', icon='upload', on_click=start_import).props('color=primary')

                # state dict must exist before cancel_btn's on_click closure captures it
                state = {}
                dlg.open()

            def import_typed_path():
                """Import from the manually typed folder path."""
                path = folder_input.value.strip()
                if not path:
                    ui.notify('Enter a folder path first.', type='warning')
                    return
                import_folder(path)

            with ui.row().classes('gap-2 mt-1'):
                ui.button('Browse…', icon='folder_open', on_click=browse_folder)
                ui.button('Import Folder', icon='upload', on_click=import_typed_path)

        # ── Connect to Drone ──────────────────────────────────────────────────
        ui.separator()
        ui.label('Connect to Drone').classes('text-h5 font-bold mt-2')

        # Download dialog (created at import_page scope so all inner functions can reference it)
        with ui.dialog() as _dl_dialog, ui.card().classes('p-8 gap-4'):
            ui.label('Download Flight Logs?').classes('text-h5 font-bold mb-2')
            ui.label('Would you like to download all flight logs from the connected drone?').classes('mb-4')
            with ui.row().classes('gap-4 w-full justify-end'):
                _dl_no_btn  = ui.button('No',  icon='close',    color='negative').classes('px-6')
                _dl_yes_btn = ui.button('Yes', icon='download', color='positive').classes('px-6')

        with ui.card().classes('w-full'):
            ui.label('⚠️ Safety Warning: Only connect to drones that are powered off or in a safe environment').classes('text-warning mb-1')
            ui.label('ℹ️ Note: After connecting there may be a brief delay before the download popup appears while the system reads the flight controller').classes('text-info mb-4')

            ui.label('Connection Settings').classes('text-h6 mb-4')

            _ports = drone_connector.get_available_ports()
            _port_select = ui.select(label='Connection', options=_ports, value=_ports[0] if _ports else None).classes('w-full')

            with ui.row().classes('w-full gap-4'):
                _baud_select = ui.select(label='Baud Rate', options=[57600, 115200, 921600], value=115200).classes('flex-1')
                _baud_input  = ui.number(label='Or enter custom baud', value=115200, min=9600, max=921600).classes('flex-1')

            ui.label('⚠️ Use 115200 or higher for fast log downloads. 57600 is very slow!').classes('text-sm text-warning mb-4')

            _status_card = ui.card().classes('w-full')

            async def _auto_detect():
                with ui.dialog() as _dd, ui.card().classes('w-96'):
                    ui.label('Auto-Detecting Drone...').classes('text-h6 mb-4')
                    _det_label = ui.label('Scanning ports...')
                    _det_bar   = ui.linear_progress(value=0).classes('w-full')
                    _dd.open()

                    def _det_worker():
                        def _upd(cur, tot, msg):
                            _det_label.text = msg
                            _det_bar.value  = cur / tot
                        result = drone_connector.auto_detect_drone(progress_callback=_upd)
                        if result:
                            port, baud = result
                            _det_label.text = f'✓ Found drone on {port} @ {baud} baud'
                            time.sleep(1)
                            _dd.close()
                            for p in _ports:
                                if port in p or p.startswith(port):
                                    _port_select.value = p; break
                            _baud_select.value = baud
                            time.sleep(0.2)
                            if drone_connector.connect(port, baud):
                                _status_card.clear()
                                with _status_card:
                                    ui.label('✓ Connected').classes('text-positive text-h6')
                                    _inf = drone_connector.get_vehicle_info()
                                    ui.label(f'Vehicle Type: {_inf.get("type","Unknown")}')
                                    ui.label(f'Autopilot: {_inf.get("autopilot","Unknown")}')
                                _dl_dialog.open()
                        else:
                            _det_label.text = '✗ No drone found'
                            time.sleep(2)
                            _dd.close()

                    import threading as _thr
                    _thr.Thread(target=_det_worker, daemon=True).start()

            ui.button('Auto-Detect Drone', icon='search', on_click=_auto_detect, color='primary').classes('w-full mb-4')

            def _disconnect_drone():
                drone_connector.disconnect()
                _status_card.clear()
                with _status_card:
                    ui.label('Disconnected').classes('text-h6')

            def _download_logs():
                if not drone_connector.is_connected:
                    ui.notify('Not connected to drone', type='negative')
                    return
                _ps = {'step': 'Step 1/6: Fetching log list...', 'status': 'Requesting logs from drone (up to 30s)',
                       'progress': 0.0, 'done': False, 'error': None, 'visible': True}
                _status_card.clear()
                with _status_card:
                    ui.label('📥 Downloading Logs').classes('text-h6 font-bold mb-4')
                    _pl = ui.label(_ps['step']).classes('mb-2')
                    _pb = ui.linear_progress(value=0).classes('w-full mb-2')
                    _sl = ui.label(_ps['status']).classes('text-sm')

                    def _upd_ui():
                        if not _ps['visible']: return
                        _pl.text = _ps['step']; _sl.text = _ps['status']; _pb.value = _ps['progress']
                        if _ps['done']:
                            _tmr.cancel(); _ps['visible'] = False
                            if _ps['error']:
                                ui.notify(f'Error: {_ps["error"]}', type='negative')
                            else:
                                ui.notify(_ps['status'], type='positive')
                            _status_card.clear()
                            with _status_card:
                                ui.label('✓ Download Complete').classes('text-positive text-h6')

                    _tmr = ui.timer(0.1, _upd_ui)

                    def _dl_worker():
                        try:
                            _ps['step'] = 'Step 1/6: Fetching log list...'; _ps['progress'] = 1/6
                            logs = drone_connector.list_logs()
                            if not logs:
                                _ps['step'] = 'No logs found on drone'; _ps['status'] = 'Check if SD card has logs'
                                _ps['error'] = 'No logs found'; _ps['done'] = True; return
                            _ps['step'] = f'Step 2/6: Found {len(logs)} logs'; _ps['status'] = 'Preparing...'
                            _ps['progress'] = 2/6; time.sleep(0.5)
                            downloaded, skipped_dl = [], 0
                            out_dir = Path('data/uploads'); out_dir.mkdir(parents=True, exist_ok=True)
                            for i, log in enumerate(logs):
                                lid = log['id']; lsz = log.get('size', 0)
                                ts = datetime.fromtimestamp(log['time_utc']) if log['time_utc'] > 0 else datetime.now()
                                fname = f"drone_log_{ts.strftime('%Y-%m-%d_%H-%M-%S')}_{lid}.bin"
                                fpath = out_dir / fname
                                _ps['step'] = f'Step 3/6: Downloading log {i+1}/{len(logs)}'
                                _ps['progress'] = (2 + i / len(logs)) / 6
                                existing = list(out_dir.glob(f'drone_log_*_{lid}.bin'))
                                if existing:
                                    _ps['status'] = f'⊘ Already downloaded (log {lid}) — skipping'
                                    downloaded.append(str(existing[0])); skipped_dl += 1; time.sleep(0.05); continue
                                _ps['status'] = f'{fname} ({lsz} bytes)'
                                if drone_connector.download_log(lid, str(fpath), expected_size=lsz):
                                    downloaded.append(str(fpath)); _ps['status'] = f'✓ Downloaded: {fname}'
                                else:
                                    _ps['status'] = f'✗ Failed: {fname}'
                                time.sleep(0.2)
                            _ps['step'] = 'Step 5/6: Importing logs...'; _ps['status'] = f'Processing {len(downloaded)} files'
                            _ps['progress'] = 5/6
                            imp_cnt = 0
                            for fp in downloaded:
                                try:
                                    fd = parser_factory.parse_file(str(fp))
                                    if fd and db.add_flight(fd) != 'duplicate': imp_cnt += 1
                                except Exception as _e: print(f'Error importing {fp}: {_e}')
                            new_dl = len(downloaded) - skipped_dl
                            _ps['progress'] = 1.0; _ps['step'] = 'Step 6/6: Complete!'
                            _ps['status'] = f'{new_dl} downloaded, {skipped_dl} already existed, {imp_cnt} new flights added.'
                            _ps['done'] = True; time.sleep(1)
                        except Exception as _e:
                            _ps['step'] = 'Error!'; _ps['status'] = str(_e); _ps['error'] = str(_e); _ps['done'] = True
                            import traceback; traceback.print_exc()

                    import threading as _thr2
                    _thr2.Thread(target=_dl_worker, daemon=True).start()

            def _connect_drone(port, baud):
                _status_card.clear()
                with _status_card:
                    ui.label('Connecting...').classes('text-h6')
                    if drone_connector.connect(port, baud):
                        _status_card.clear()
                        ui.label('✓ Connected').classes('text-positive text-h6')
                        _inf = drone_connector.get_vehicle_info()
                        ui.label(f'Vehicle Type: {_inf.get("type","Unknown")}')
                        ui.label(f'Autopilot: {_inf.get("autopilot","Unknown")}')
                        import time as _t; _t.sleep(0.5)
                        try: _dl_dialog.open()
                        except Exception: pass
                    else:
                        _status_card.clear()
                        ui.label('✗ Connection failed').classes('text-negative text-h6')

            with ui.row().classes('gap-4 mt-2'):
                ui.button('Connect',    icon='link',     on_click=lambda: _connect_drone(_port_select.value, _baud_input.value or _baud_select.value), color='positive')
                ui.button('Disconnect', icon='link_off', on_click=_disconnect_drone, color='negative')

            def _on_dl_yes():
                _dl_dialog.close(); _download_logs()

            def _on_dl_no():
                _dl_dialog.close()

            _dl_yes_btn.on('click', _on_dl_yes)
            _dl_no_btn.on('click',  _on_dl_no)

async def handle_file_upload(e):
    """Handle file upload — shows a spinner notification while parsing."""
    import asyncio

    upload_dir = Path('data/uploads')
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / e.name
    file_path.write_bytes(e.content.read())

    notif = ui.notification(f'Parsing {e.name}…', spinner=True, timeout=0, type='ongoing')

    try:
        flight_data = await asyncio.get_event_loop().run_in_executor(
            None, parser_factory.parse_file, str(file_path)
        )

        notif.dismiss()

        if flight_data:
            result = db.add_flight(flight_data)
            if result:
                msg = f'✓ Imported: {e.name}'
                if flight_data.get('needs_dji_api_key'):
                    msg += ' (DJI v13+ — enter API key in Profile for better data)'
                ui.notify(msg, type='positive' if not flight_data.get('needs_dji_api_key') else 'warning')
                db.log_import(1, 0, 'file_upload', f'Uploaded: {e.name}')
            else:
                ui.notify(f'⊘ Skipped (duplicate): {e.name}', type='warning')
                db.log_import(0, 1, 'file_upload', f'Skipped duplicate: {e.name}')
        else:
            if e.name.lower().endswith('.txt') and not config.has_dji_api_key():
                ui.notify(
                    f'✗ Could not parse: {e.name} — if this is a DJI Fly v13+ log, '
                    'add your DJI API key in Profile → DJI Settings',
                    type='negative', timeout=8000,
                )
            else:
                ui.notify(f'✗ Failed to parse: {e.name} — no compatible parser found', type='negative')

    except Exception as ex:
        notif.dismiss()
        import traceback
        traceback.print_exc()
        ui.notify(f'Error uploading {e.name}: {str(ex)}', type='negative')

def run_bulk_import(files, source_label='bulk_import'):
    """Open a progress dialog and import files in a background thread."""
    import threading

    total = len(files)
    state = {'done': False, 'i': 0, 'current': '', 'imported': 0, 'skipped': 0, 'failed': 0}

    with ui.dialog() as dialog, ui.card().classes('gap-4').style('min-width:420px; padding:28px;'):
        ui.label('Importing Flight Logs').classes('text-h6 font-bold')
        prog_label  = ui.label(f'0 of {total} files…').classes('text-body2')
        prog_bar    = ui.linear_progress(value=0).classes('w-full')
        file_label  = ui.label('Starting…').classes('text-caption').style('color:#a0a0a0;')
        stats_label = ui.label('').classes('text-caption').style('color:#a0a0a0;')

        # Close button created on main thread — revealed only when done
        close_btn = ui.button(
            'Done', icon='check',
            on_click=lambda: (dialog.close(), ui.navigate.reload()),
        ).classes('w-full mt-2').props('color=positive')
        close_btn.visible = False

        def poll():
            i = state['i']
            prog_bar.set_value(i / total if total else 1)
            prog_label.set_text(f'{i} of {total} files…')
            file_label.set_text(state['current'])
            if state['done']:
                prog_bar.set_value(1.0)
                prog_label.set_text('Import complete!')
                file_label.set_text('')
                stats_label.set_text(
                    f"✓ {state['imported']} imported  ·  "
                    f"⊘ {state['skipped']} skipped  ·  "
                    f"✗ {state['failed']} failed"
                )
                close_btn.visible = True
                timer.cancel()

        timer = ui.timer(0.1, poll)

        def worker():
            for idx, fp in enumerate(files, 1):
                # Only update shared state from thread — timer handles all UI writes
                state['i']       = idx
                state['current'] = fp.name
                try:
                    data = parser_factory.parse_file(str(fp))
                    if data:
                        state['imported' if db.add_flight(data) else 'skipped'] += 1
                    else:
                        state['failed'] += 1
                except Exception as exc:
                    print(f'Error importing {fp}: {exc}')
                    import traceback; traceback.print_exc()
                    state['failed'] += 1
            db.log_import(state['imported'], state['skipped'], source_label, f'{total} files')
            state['done'] = True

        threading.Thread(target=worker, daemon=True).start()

    dialog.open()

def import_folder(folder_path: str):
    """Import all files from a folder - automatically handles large batches"""
    if not folder_path:
        ui.notify('Please enter a folder path', type='warning')
        return
    
    try:
        path = Path(folder_path)
        if not path.exists():
            ui.notify('Folder not found', type='negative')
            return
        
        # Get all supported files
        files = list(path.rglob('*.txt')) + list(path.rglob('*.csv')) + \
                list(path.rglob('*.bin')) + list(path.rglob('*.BIN')) + \
                list(path.rglob('*.dat')) + list(path.rglob('*.DAT'))
        
        if not files:
            ui.notify('No flight log files found', type='warning')
            return

        # Always use the background progress dialog regardless of file count
        run_bulk_import(files)
        
    except Exception as e:
        ui.notify(f'Import failed: {e}', type='negative')

def _drone_icon_html(size_px: int = 40, color: str = '#667eea', opacity: float = 1.0) -> str:
    """
    Inline top-down quadcopter SVG.
    The bundled Material Icons / Material Symbols fonts have no 'drone' glyph
    (closest is 'flight', an airplane) — so we draw one ourselves.
    """
    return f'''
        <svg width="{size_px}" height="{size_px}" viewBox="0 0 24 24" fill="none"
             style="opacity:{opacity}; display:block;">
            <g stroke="{color}" stroke-width="1.6" stroke-linecap="round">
                <line x1="12" y1="12" x2="5"  y2="5"/>
                <line x1="12" y1="12" x2="19" y2="5"/>
                <line x1="12" y1="12" x2="5"  y2="19"/>
                <line x1="12" y1="12" x2="19" y2="19"/>
                <circle cx="5"  cy="5"  r="2.7" fill="none"/>
                <circle cx="19" cy="5"  r="2.7" fill="none"/>
                <circle cx="5"  cy="19" r="2.7" fill="none"/>
                <circle cx="19" cy="19" r="2.7" fill="none"/>
            </g>
            <rect x="9.3" y="9.3" width="5.4" height="5.4" rx="1.4" fill="{color}"/>
        </svg>
    '''


@ui.page('/fleet')
def fleet_page():
    """Fleet overview — one card per drone"""
    apply_theme()
    create_header()

    _card_base = (
        'background: linear-gradient(135deg, rgba(102,126,234,0.15) 0%, rgba(118,75,162,0.15) 100%);'
        'border: 1px solid rgba(102,126,234,0.3); border-radius: 16px;'
        'padding: 24px; cursor: pointer; transition: transform 0.15s;'
    )

    with ui.column().classes('w-full p-8 gap-6'):
        ui.label('My Fleet').classes('text-h4 font-bold')
        ui.label('Click a drone to view its flights and update details.') \
            .classes('text-caption').style('color:#a0a0a0;')

        drones = db.get_all_drones()

        if not drones:
            with ui.card().classes('w-full p-8 text-center'):
                ui.html(_drone_icon_html(64, '#667eea', 0.4)).classes('mx-auto')
                ui.label('No drones on record yet.').classes('text-h6 mt-4')
                ui.label('Import some flight logs and they will appear here.').classes('text-caption').style('color:#a0a0a0;')
        else:
            with ui.grid(columns=2).classes('w-full gap-5'):
                for drone in drones:
                    sn           = drone['serial_number']
                    default_name = drone['default_model'] or 'Unknown'
                    display_name = drone['custom_name'] or default_name
                    flights      = drone['flight_count']
                    hours        = round((drone['total_minutes'] or 0) / 60, 1)
                    last_seen    = (drone['last_seen'] or '')[:10]
                    mfr          = drone['manufacturer'] or ''

                    with ui.element('div').style(_card_base).on('click', lambda _sn=sn: ui.navigate.to(f'/fleet/{_sn}')):
                        with ui.row().classes('items-center gap-4 mb-4'):
                            ui.html(_drone_icon_html(40, '#667eea'))
                            with ui.column().classes('gap-0'):
                                ui.html(f'<div style="font-size:18px;font-weight:800;color:white;line-height:1.2;">{display_name}</div>')
                                ui.html(f'<div style="font-size:12px;color:#a0a0a0;">{mfr}  ·  SN: {sn[:12]}…</div>' if len(sn) > 12 else f'<div style="font-size:12px;color:#a0a0a0;">{mfr}  ·  SN: {sn}</div>')
                        with ui.row().classes('w-full gap-6'):
                            with ui.column().classes('gap-0'):
                                ui.html(f'<div style="font-size:28px;font-weight:900;color:#667eea;">{flights}</div>')
                                ui.html('<div style="font-size:11px;color:#a0a0a0;text-transform:uppercase;letter-spacing:1px;">Flights</div>')
                            with ui.column().classes('gap-0'):
                                ui.html(f'<div style="font-size:28px;font-weight:900;color:#764ba2;">{hours}h</div>')
                                ui.html('<div style="font-size:11px;color:#a0a0a0;text-transform:uppercase;letter-spacing:1px;">Air Time</div>')
                            with ui.column().classes('gap-0 ml-auto'):
                                ui.html(f'<div style="font-size:12px;color:#888;">Last seen</div>')
                                ui.html(f'<div style="font-size:13px;color:#ccc;">{last_seen or "—"}</div>')


@ui.page('/fleet/{sn}')
def fleet_drone_page(sn: str):
    """Detail page for a single drone"""
    apply_theme()
    create_header()

    drone = db.get_drone_alias(sn)
    if not drone:
        with ui.column().classes('w-full p-8'):
            ui.label('Drone not found.').classes('text-h5')
            ui.button('Back to Fleet', icon='arrow_back', on_click=lambda: ui.navigate.to('/fleet'))
        return

    default_name = drone.get('default_model') or 'Unknown'
    mfr          = drone.get('manufacturer') or ''

    with ui.column().classes('w-full p-8 gap-6'):
        with ui.row().classes('items-center gap-4'):
            ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/fleet')).props('flat round')
            with ui.column().classes('gap-0'):
                ui.label(drone.get('custom_name') or default_name).classes('text-h4 font-bold')
                _owner_val = (drone.get('owner') or '').strip()
                _reg_val   = (drone.get('registration') or '').strip()
                _bits = []
                if _owner_val:
                    _bits.append(f'Owner: {_owner_val}')
                if _reg_val:
                    _bits.append(f'Registration: {_reg_val}')
                if _bits:
                    ui.label('  ·  '.join(_bits)).classes('text-subtitle1').style('color:#c8c8c8;')
                ui.label(f'{mfr}  ·  SN: {sn}').classes('text-caption').style('color:#888;')

        # ── Details form ─────────────────────────────────────────────────────
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Drone Details').classes('text-h6 mb-4')
            ui.label(
                'Nickname and owner info persist across all past and future imports of this drone.'
            ).classes('text-caption mb-4').style('color:#a0a0a0;')

            _nick  = ui.input('Nickname',     value=drone.get('custom_name') or '',  placeholder=default_name).props('stack-label').classes('w-full mb-3')
            _owner = ui.input('Owner',         value=drone.get('owner') or '',        placeholder='Pilot name / company').props('stack-label').classes('w-full mb-3')
            _reg   = ui.input('Registration', value=drone.get('registration') or '', placeholder='e.g. C-FABC').props('stack-label').classes('w-full mb-4')

            def _save_details():
                db.update_drone_details(sn, _nick.value.strip(), _owner.value.strip(), _reg.value.strip())
                ui.notify('Drone details saved — all flights updated.', type='positive')
                ui.navigate.to(f'/fleet/{sn}')

            def _clear_nick():
                db.update_drone_details(sn, '', _owner.value.strip(), _reg.value.strip())
                _nick.set_value('')
                ui.notify('Nickname cleared.', type='info')

            with ui.row().classes('gap-3 items-center justify-between w-full'):
                with ui.row().classes('gap-3'):
                    ui.button('Save',           icon='save',  on_click=_save_details).props('color=primary')
                    ui.button('Clear Nickname', icon='clear', on_click=_clear_nick).props('flat')

                def _confirm_remove():
                    with ui.dialog() as _rm_dlg, ui.card().classes('p-8 gap-4'):
                        ui.label('Remove from Fleet?').classes('text-h6 font-bold mb-2')
                        ui.label(
                            f'This removes the drone record and its nickname. '
                            f'All flights stay in your logbook — they just won\'t be linked to this entry anymore.'
                        ).classes('mb-4').style('max-width:340px;')
                        with ui.row().classes('gap-4 w-full justify-end'):
                            ui.button('Cancel', on_click=_rm_dlg.close).props('flat')
                            def _do_remove():
                                db.remove_drone(sn)
                                _rm_dlg.close()
                                ui.notify('Drone removed from fleet.', type='info')
                                ui.navigate.to('/fleet')
                            ui.button('Remove', icon='delete', on_click=_do_remove).props('color=negative')
                    _rm_dlg.open()

                ui.button('Remove from Fleet', icon='delete_forever', on_click=_confirm_remove).props('flat color=negative')

        # ── Flights for this drone ────────────────────────────────────────────
        with ui.card().classes('w-full'):
            flights = db.get_flights_for_drone(sn)
            total_flights = len(flights)
            total_hours   = round(sum(f.get('duration_minutes', 0) for f in flights) / 60, 1)

            with ui.row().classes('items-center justify-between mb-4'):
                ui.label('Flight History').classes('text-h6')
                with ui.row().classes('items-center gap-3'):
                    ui.label(f'{total_flights} flights  ·  {total_hours} h total').classes('text-caption').style('color:#a0a0a0;')
                    _drone_label = drone.get('custom_name') or default_name
                    ui.button('PDF Report', icon='picture_as_pdf',
                              on_click=lambda: generate_drone_pdf(sn)).props('outline color=primary dense').classes('px-3')
                    ui.button('Export CSV', icon='download',
                              on_click=lambda: export_drone_flights_csv(sn, _drone_label)).props('outline color=primary dense').classes('px-3')

            if not flights:
                ui.label('No flights recorded for this drone yet.').classes('text-caption').style('color:#a0a0a0;')
            else:
                columns = [
                    {'name': 'id',       'label': '#',        'field': 'id',                'sortable': True},
                    {'name': 'date',     'label': 'Date',     'field': 'flight_date',        'sortable': True, 'align': 'left'},
                    {'name': 'duration', 'label': 'Duration', 'field': 'duration_minutes',   'sortable': True},
                    {'name': 'altitude', 'label': 'Max Alt',  'field': 'max_altitude_m',     'sortable': True},
                    {'name': 'distance', 'label': 'Distance', 'field': 'distance_km',        'sortable': True},
                ]
                rows = [{
                    'id':               f.get('id'),
                    'flight_date':      (f.get('flight_date') or '')[:10],
                    'duration_minutes': f'{f.get("duration_minutes", 0):.1f} min',
                    'max_altitude_m':   f'{f.get("max_altitude_m", 0):.1f} m' if f.get('max_altitude_m') else 'N/A',
                    'distance_km':      f'{f.get("distance_km", 0):.2f} km'   if f.get('distance_km')    else 'N/A',
                } for f in flights]

                tbl = ui.table(columns=columns, rows=rows, row_key='id').classes('w-full')
                tbl.on('rowClick', lambda e: show_flight_details(e.args[1]['id']))


@ui.page('/about')
def about_page():
    """About page with license info"""
    apply_theme()
    create_header()
    
    with ui.column().classes('w-full p-8 gap-6'):
        ui.label('About SKYLOGR').classes('text-h4 font-bold')

        with ui.card().classes('w-full'):
            ui.label('Beta Release').classes('text-h6 mb-4')
            ui.label('A clean, local-first flight logbook built for working drone pilots and operators —')
            ui.label('import your logs, track every aircraft in your fleet, and generate client-ready reports.')
            ui.label('Developed by QCT Aerial Solutions')
            ui.label('Built with Python, NiceGUI, and ❤️').classes('mt-2')

        with ui.card().classes('w-full'):
            ui.label('Core Features').classes('text-h6 mb-4')
            ui.label('✓ Local-first & Private — your flights are stored in a database on your own computer, never uploaded')
            ui.label('✓ Multi-Format Log Import — DJI Fly (.txt) with full GPS/telemetry, ArduPilot (.bin), MAVLink (.tlog/.rlog), Airdata UAV CSV, and legacy DJI (.DAT)')
            ui.label('✓ Direct Drone Connection — connect over USB/serial and download logs straight from the flight controller')
            ui.label('✓ Fleet Management — every aircraft is recognized automatically; give it a nickname, owner, and registration, and remove it without losing its flight history')
            ui.label('✓ Professional Dashboard — total hours, hours by drone and manufacturer, and pilot stats at a glance')
            ui.label('✓ Detailed Flight Analysis — altitude, speed, battery, and GPS track playback for every flight')
            ui.label('✓ Enhance DJI Logs — re-process DJI Fly logs with the full MIT-licensed dji-log-parser for accurate GPS, altitude, speed, and battery data')
            ui.label('✓ PDF Report Generation — produce client-ready flight reports in one click')
            ui.label('✓ CSV Export & One-Click Backup — export your logbook or back up your database, uploads, and settings any time')
            ui.label('✓ Pilot Profile — store your name, license/certificate number, and company details for use on reports')

        with ui.card().classes('w-full'):
            ui.label('Supported Log Formats').classes('text-h6 mb-4')
            ui.label('• DJI Fly app logs (.txt) — including newer v13+ logs via a one-time DJI key lookup')
            ui.label('• Legacy DJI flight logs (.DAT)')
            ui.label('• ArduPilot / Mission Planner logs (.bin)')
            ui.label('• MAVLink telemetry (.tlog, .rlog)')
            ui.label('• Airdata UAV CSV exports')
            ui.label('• Direct serial connection to supported flight controllers')
            ui.label('').classes('mt-2')
            ui.label(
                'SKYLOGR works fully offline. The only exception is the optional "Enhance DJI '
                'Logs" feature for newer (v13+) DJI logs, which needs a brief one-time internet '
                'connection to fetch a decryption key — after that, those logs parse offline too.'
            ).classes('text-caption').style('color: #a0a0a0;')

        with ui.card().classes('w-full'):
            ui.label('About QCT Aerial Solutions').classes('text-h6 mb-4')
            ui.label('QCT Aerial Solutions is a drone operations company — SKYLOGR was built out of a real')
            ui.label('need for a straightforward, offline flight logbook that keeps pace with a working fleet.')
            ui.label('').classes('mt-2')
            ui.label('SKYLOGR is under active development. Your feedback during the beta directly shapes what gets built next.')

        with ui.card().classes('w-full'):
            ui.label('License & Copyright').classes('text-h6 mb-4')
            ui.label('© 2024-2026 QCT Aerial Solutions. All rights reserved.')
            ui.label('This software is provided for personal and commercial use.')
            ui.label('SKYLOGR is currently in beta testing — features and pricing may change before the full release.')

def activate_license(license_key: str):
    """Activate premium license"""
    if config.set_license_key(license_key):
        ui.notify('License activated! Premium features unlocked.', type='positive')
    else:
        ui.notify('Invalid license key', type='negative')

def backup_flight_data():
    """Backup all flight data including database and uploaded files"""
    try:
        import shutil
        from datetime import datetime
        
        # Create backup directory with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = Path(f'data/backups/backup_{timestamp}')
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup database
        db_source = Path('data/flights.db')
        if db_source.exists():
            shutil.copy2(db_source, backup_dir / 'flights.db')
        
        # Backup uploaded files
        uploads_source = Path('data/uploads')
        if uploads_source.exists():
            uploads_backup = backup_dir / 'uploads'
            shutil.copytree(uploads_source, uploads_backup, dirs_exist_ok=True)
        
        # Backup config
        config_source = Path('data/config')
        if config_source.exists():
            config_backup = backup_dir / 'config'
            shutil.copytree(config_source, config_backup, dirs_exist_ok=True)
        
        # Create backup info file
        info_file = backup_dir / 'backup_info.txt'
        stats = db.get_statistics()
        with open(info_file, 'w') as f:
            f.write(f"Drone Flight Logbook Backup\n")
            f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\nBackup Contents:\n")
            f.write(f"- Total Flights: {stats['total_flights']}\n")
            f.write(f"- Total Hours: {stats['total_hours']:.2f}\n")
            f.write(f"- Database: flights.db\n")
            f.write(f"- Uploaded Files: uploads/\n")
            f.write(f"- Configuration: config/\n")
            f.write(f"\nTo restore:\n")
            f.write(f"1. Copy flights.db to data/\n")
            f.write(f"2. Copy uploads/ to data/\n")
            f.write(f"3. Copy config/ to data/\n")
        
        ui.notify(f'✓ Backup created: {backup_dir.name}', type='positive', timeout=5000)
        
        # Open backup folder
        import subprocess
        import platform
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', str(backup_dir.parent)])
        elif platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', str(backup_dir.parent)])
        else:  # Linux
            subprocess.Popen(['xdg-open', str(backup_dir.parent)])
            
    except Exception as e:
        ui.notify(f'Error creating backup: {e}', type='negative')
        print(f"Backup error: {e}")
        import traceback
        traceback.print_exc()

# ════════════════════════════════════════════════════════════════════
# Branded export helpers — shared "beautiful" styling and chart
# rendering reused by every generated report (single-flight,
# per-aircraft, and portfolio PDFs/CSVs).
# ════════════════════════════════════════════════════════════════════

def _pdf_styles():
    """Shared brand ParagraphStyles so every PDF looks like the same family of report."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    styles = getSampleStyleSheet()
    title = ParagraphStyle('BrandTitle', parent=styles['Heading1'], fontSize=22,
                           textColor=colors.HexColor('#667eea'), spaceAfter=6, alignment=TA_CENTER)
    subtitle = ParagraphStyle('BrandSubtitle', parent=styles['Normal'], fontSize=11,
                              textColor=colors.HexColor('#666666'), spaceAfter=18, alignment=TA_CENTER)
    heading = ParagraphStyle('BrandHeading', parent=styles['Heading2'], fontSize=15,
                             textColor=colors.HexColor('#667eea'), spaceAfter=10, spaceBefore=16)
    caption = ParagraphStyle('BrandCaption', parent=styles['Heading3'], fontSize=11,
                             textColor=colors.HexColor('#444444'), spaceAfter=4, spaceBefore=10)
    return title, subtitle, heading, caption


def _kv_table(rows, col_widths=None):
    """A clean two-column label/value table used for summary blocks across every report."""
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import Table, TableStyle

    table = Table(rows, colWidths=col_widths or [2*inch, 4.2*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#667eea')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return table


def _brand_table(header_row, data_rows, col_widths, repeat_header=True):
    """The signature Skylogr report table: purple header, beige body, black grid."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table = Table([header_row] + data_rows, colWidths=col_widths,
                  repeatRows=1 if repeat_header else 0)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    return table


def _chart_png(series, xlabel, ylabel, figsize=(6.6, 2.5), fill=False, zero_line=False):
    """
    Render a small branded line chart to PNG bytes for embedding in a PDF.
    series: list of (label_or_None, x_values, y_values, hex_color) tuples.
    Charts use a light background (unlike the in-app dark theme) since PDFs print on white.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from io import BytesIO

    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    for label, xs, ys, color in series:
        ax.plot(xs, ys, color=color, linewidth=1.5, label=label)
        if fill:
            ax.fill_between(xs, ys, color=color, alpha=0.15)
    if zero_line:
        ax.axhline(0, color='#bbbbbb', linewidth=0.8, linestyle='--')
    ax.set_xlabel(xlabel, fontsize=8, color='#555555')
    ax.set_ylabel(ylabel, fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#555555')
    ax.grid(True, color='#e6e6e6', linewidth=0.6)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    if any(label for label, *_ in series):
        ax.legend(fontsize=7, frameon=False, loc='upper right')
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


def _track_png(lats, lons, figsize=(6.6, 3.2)):
    """Render a simple branded flight-path plot (latitude/longitude) to PNG bytes."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from io import BytesIO

    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    ax.plot(lons, lats, color='#764ba2', linewidth=1.6, zorder=2)
    ax.scatter([lons[0]], [lats[0]], color='#10b981', s=36, zorder=3, label='Takeoff')
    ax.scatter([lons[-1]], [lats[-1]], color='#ef4444', s=36, zorder=3, label='Landing')
    ax.set_xlabel('Longitude', fontsize=8, color='#555555')
    ax.set_ylabel('Latitude', fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#555555')
    ax.set_aspect('equal', adjustable='datalim')
    ax.grid(True, color='#e6e6e6', linewidth=0.6)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    ax.legend(fontsize=7, frameon=False, loc='best')
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


def _chart_flowable(png_buf, caption_text, caption_style, max_width_in=6.5):
    """Wrap a chart PNG + caption into flowables sized to fit neatly on the page."""
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, Spacer
    from PIL import Image as PILImage

    png_buf.seek(0)
    w_px, h_px = PILImage.open(png_buf).size
    png_buf.seek(0)
    width = max_width_in * inch
    height = width * (h_px / w_px)
    return [Paragraph(caption_text, caption_style), Image(png_buf, width=width, height=height),
            Spacer(1, 0.12*inch)]


def _open_file(path: Path):
    """Open a freshly generated report with the OS default application."""
    import subprocess
    import platform
    if platform.system() == 'Windows':
        subprocess.Popen(['start', '', str(path)], shell=True)
    elif platform.system() == 'Darwin':
        subprocess.Popen(['open', str(path)])
    else:
        subprocess.Popen(['xdg-open', str(path)])


def _safe_filename_part(text: str, fallback: str = 'report') -> str:
    """Turn an arbitrary label into a filesystem-safe filename fragment."""
    cleaned = ''.join(c if c.isalnum() else '_' for c in (text or '')).strip('_')
    return cleaned or fallback


# ════════════════════════════════════════════════════════════════════
# Single-flight export — "beautiful" branded PDF with full telemetry
# charts, plus an Airdata-UAV-style per-second telemetry CSV.
# ════════════════════════════════════════════════════════════════════

def generate_flight_pdf(flight_id):
    """Generate a beautiful single-flight PDF report with full telemetry charts."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

        flight = db.get_flight_by_id(flight_id)
        if not flight:
            ui.notify('Flight not found', type='negative')
            return

        raw_data = flight.get('raw_data') or {}
        if isinstance(raw_data, str):
            raw_data = json.loads(raw_data) if raw_data else {}

        pilot_profile = db.get_pilot_profile()
        title_style, subtitle_style, heading_style, caption_style = _pdf_styles()

        output_dir = Path('data/reports')
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = output_dir / f'flight_{flight_id}_{timestamp}.pdf'

        doc = SimpleDocTemplate(str(filename), pagesize=letter,
                                topMargin=0.7*inch, bottomMargin=0.6*inch)
        story = []

        date_str = (flight.get('flight_date') or '')[:19].replace('T', '   ·   ') or 'Unknown date'
        duration = flight.get('duration_minutes', 0) or 0

        story.append(Paragraph('Flight Report', title_style))
        story.append(Paragraph(f"{flight.get('drone_model', 'Unknown Aircraft')}   —   {date_str}", subtitle_style))

        if pilot_profile and pilot_profile.get('pilot_name'):
            story.append(_kv_table([
                ['Pilot:', pilot_profile.get('pilot_name', '')],
                ['Company:', pilot_profile.get('company_name') or 'N/A'],
                ['License / Cert #:', pilot_profile.get('license_number') or 'N/A'],
            ]))
            story.append(Spacer(1, 0.2*inch))

        story.append(Paragraph('Flight Summary', heading_style))
        summary_rows = [
            ['Aircraft:', f"{flight.get('drone_model', 'Unknown')}  ({flight.get('manufacturer', 'Unknown')})"],
            ['Date / Time:', date_str],
            ['Duration:', f"{duration:.1f} min   ({duration/60:.2f} hours)"],
            ['Source File:', flight.get('file_name', 'N/A')],
        ]
        if flight.get('max_altitude_m'):
            summary_rows.append(['Max Altitude:', f"{flight['max_altitude_m']:.1f} m"])
        if flight.get('max_speed_ms'):
            summary_rows.append(['Max Speed:', f"{flight['max_speed_ms']:.1f} m/s"])
        if flight.get('distance_km'):
            summary_rows.append(['Distance Traveled:', f"{flight['distance_km']:.2f} km"])
        if flight.get('battery_start') is not None and flight.get('battery_end') is not None:
            used = flight['battery_start'] - flight['battery_end']
            summary_rows.append(['Battery:', f"{flight['battery_start']}%  →  {flight['battery_end']}%   (used {used}%)"])
        if flight.get('location_start_lat') is not None:
            summary_rows.append(['Takeoff GPS:', f"{flight['location_start_lat']:.6f}, {flight['location_start_lon']:.6f}"])
        if flight.get('location_end_lat') is not None:
            summary_rows.append(['Landing GPS:', f"{flight['location_end_lat']:.6f}, {flight['location_end_lon']:.6f}"])
        summary_rows.append(['Source / Quality:',
                             f"{flight.get('parser_used', 'Unknown')}   ·   "
                             f"{(flight.get('confidence') or 'unknown').capitalize()} confidence"])
        story.append(_kv_table(summary_rows))

        # ── Telemetry charts (mirrors the in-app flight-detail charts) ────────
        duration_min = duration

        def _anchored(times, values, zero_value=0.0):
            """Pin the trace to 0 at takeoff/landing so it visually matches the in-app chart."""
            t, v = list(times), list(values)
            if t and t[0] > 0.08:
                t = [0] + t
                v = [zero_value] + v
            if t and duration_min and t[-1] < duration_min - 0.08:
                t = t + [duration_min]
                v = v + [zero_value]
            return t, v

        chart_blocks = []

        if raw_data.get('altitude_profile'):
            data = raw_data['altitude_profile']
            t, a = _anchored([p['time']/60 for p in data], [p['alt'] for p in data])
            png = _chart_png([(None, t, a, '#667eea')], 'Time (minutes)', 'Altitude (m)', fill=True)
            chart_blocks += _chart_flowable(png, 'Altitude Profile', caption_style)

        if raw_data.get('speed_profile'):
            data = raw_data['speed_profile']
            t, s = _anchored([p['time']/60 for p in data], [p['speed'] for p in data])
            png = _chart_png([(None, t, s, '#764ba2')], 'Time (minutes)', 'Speed (m/s)', fill=True)
            chart_blocks += _chart_flowable(png, 'Speed Profile', caption_style)

        if raw_data.get('vertical_speed_profile'):
            data = raw_data['vertical_speed_profile']
            t, v = _anchored([p['time']/60 for p in data], [p['vspeed'] for p in data])
            png = _chart_png([(None, t, v, '#10b981')], 'Time (minutes)', 'm/s  (+ climb / − descent)',
                             fill=True, zero_line=True)
            chart_blocks += _chart_flowable(png, 'Vertical Speed (Climb / Descent)', caption_style)

        if raw_data.get('gps_track') and len(raw_data['gps_track']) > 1:
            gps = raw_data['gps_track']
            png = _track_png([p['lat'] for p in gps], [p['lon'] for p in gps])
            chart_blocks += _chart_flowable(png, 'Flight Path', caption_style, max_width_in=5.5)

        battery = raw_data.get('battery_profile') or []
        if battery:
            if any('remaining' in p for p in battery):
                ts = [p['time']/60 for p in battery if 'remaining' in p]
                vals = [p['remaining'] for p in battery if 'remaining' in p]
                png = _chart_png([(None, ts, vals, '#667eea')], 'Time (minutes)', 'Battery Remaining (%)', fill=True)
                chart_blocks += _chart_flowable(png, 'Battery Level', caption_style)

            series = []
            if any('voltage' in p for p in battery):
                ts = [p['time']/60 for p in battery if 'voltage' in p]
                series.append(('Voltage (V)', ts, [p['voltage'] for p in battery if 'voltage' in p], '#10b981'))
            if any('current' in p for p in battery):
                ts = [p['time']/60 for p in battery if 'current' in p]
                series.append(('Current (A)', ts, [p['current'] for p in battery if 'current' in p], '#f59e0b'))
            if series:
                png = _chart_png(series, 'Time (minutes)', 'Voltage (V)  /  Current (A)')
                chart_blocks += _chart_flowable(png, 'Battery Voltage & Current', caption_style)

            if any('temperature' in p for p in battery):
                ts = [p['time']/60 for p in battery if 'temperature' in p]
                temps = [p['temperature'] for p in battery if 'temperature' in p]
                png = _chart_png([(None, ts, temps, '#f97316')], 'Time (minutes)', 'Temperature (°C)', fill=True)
                chart_blocks += _chart_flowable(png, 'Battery Temperature', caption_style)

        attitude = raw_data.get('attitude_profile') or []
        if attitude:
            ts = [p['time']/60 for p in attitude]
            series = []
            if any('roll' in p for p in attitude):
                series.append(('Roll', ts, [p.get('roll', 0) for p in attitude], '#ef4444'))
            if any('pitch' in p for p in attitude):
                series.append(('Pitch', ts, [p.get('pitch', 0) for p in attitude], '#10b981'))
            if series:
                png = _chart_png(series, 'Time (minutes)', 'Degrees')
                chart_blocks += _chart_flowable(png, 'Aircraft Attitude — Roll & Pitch', caption_style)
            if any('yaw' in p for p in attitude):
                yaws = [p.get('yaw', 0) for p in attitude]
                png = _chart_png([('Yaw', ts, yaws, '#667eea')], 'Time (minutes)', 'Degrees')
                chart_blocks += _chart_flowable(png, 'Aircraft Attitude — Yaw (Heading)', caption_style)

        gimbal = raw_data.get('gimbal_profile') or []
        if gimbal:
            ts = [p['time']/60 for p in gimbal]
            series = []
            if any('pitch' in p for p in gimbal):
                series.append(('Pitch', ts, [p.get('pitch', 0) for p in gimbal], '#667eea'))
            if any('roll' in p for p in gimbal):
                series.append(('Roll', ts, [p.get('roll', 0) for p in gimbal], '#10b981'))
            if any('yaw' in p for p in gimbal):
                series.append(('Yaw', ts, [p.get('yaw', 0) for p in gimbal], '#f59e0b'))
            if series:
                png = _chart_png(series, 'Time (minutes)', 'Angle (degrees)', zero_line=True)
                chart_blocks += _chart_flowable(png, 'Gimbal — Pitch / Roll / Yaw', caption_style)

        motor = raw_data.get('motor_profile') or []
        if motor:
            ts = [p['time']/60 for p in motor]
            palette = ['#667eea', '#764ba2', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4']
            series = []
            if any('motor1' in p for p in motor):
                for i in range(1, 9):
                    key = f'motor{i}'
                    if any(key in p for p in motor):
                        vals = [p.get(key, 0) for p in motor]
                        if max(vals) > 1000:
                            series.append((f'Motor {i}', ts, vals, palette[i-1]))
                ylabel, zline = 'PWM Output', False
            else:
                rc_channels = [('elevator', 'Elevator (Pitch)'), ('aileron', 'Aileron (Roll)'),
                               ('throttle', 'Throttle'), ('rudder', 'Rudder (Yaw)')]
                for idx, (key, label) in enumerate(rc_channels):
                    if any(key in p for p in motor):
                        vals = [p.get(key, 0) for p in motor]
                        if any(val != 0 for val in vals):
                            series.append((label, ts, vals, palette[idx]))
                ylabel, zline = 'RC Input (% from center)', True
            if series:
                png = _chart_png(series, 'Time (minutes)', ylabel, zero_line=zline)
                chart_blocks += _chart_flowable(png, 'Motor / RC Outputs', caption_style)

        if chart_blocks:
            story.append(PageBreak())
            story.append(Paragraph('Telemetry Charts', heading_style))
            story.extend(chart_blocks)

        doc.build(story)
        ui.notify(f'✓ Flight report generated: {filename.name}', type='positive')
        _open_file(filename)

    except Exception as e:
        ui.notify(f'Error generating flight report: {e}', type='negative')
        print(f"Flight PDF generation error: {e}")
        import traceback
        traceback.print_exc()


def _build_airdata_style_rows(flight, raw_data):
    """
    Reconstruct an Airdata-UAV-style telemetry table from Skylogr's stored
    per-flight profile arrays. Profiles are sampled independently (different
    rates / conditions), so rows are merged by nearest timestamp — this is what
    makes every row carry position, altitude, speed, gimbal and battery data
    side-by-side, just like a native Airdata CSV export.
    """
    import bisect
    from math import radians, sin, cos, sqrt, atan2

    def haversine_m(lat1, lon1, lat2, lon2):
        R = 6371000.0
        phi1, phi2 = radians(lat1), radians(lat2)
        dphi = radians(lat2 - lat1)
        dlambda = radians(lon2 - lon1)
        a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
        return 2 * R * atan2(sqrt(a), sqrt(1 - a))

    def make_lookup(profile, tol=3.0):
        if not profile:
            return lambda t: None
        times = [p['time'] for p in profile]

        def lookup(t):
            idx = bisect.bisect_left(times, t)
            cands = [i for i in (idx - 1, idx) if 0 <= i < len(times)]
            if not cands:
                return None
            best = min(cands, key=lambda i: abs(times[i] - t))
            return profile[best] if abs(times[best] - t) <= tol else None
        return lookup

    gps   = raw_data.get('gps_track') or []
    alt_p = raw_data.get('altitude_profile') or []
    spd_p = raw_data.get('speed_profile') or []
    vsp_p = raw_data.get('vertical_speed_profile') or []
    bat_p = raw_data.get('battery_profile') or []
    gim_p = raw_data.get('gimbal_profile') or []

    if not (gps or alt_p):
        return []

    duration_s = (flight.get('duration_minutes') or 0) * 60.0

    # Build the time "spine" — prefer the GPS track since Airdata-style exports
    # are fundamentally a per-position telemetry table. GPS points carry no
    # timestamp of their own, so spread them evenly across the flight duration.
    spine = []
    if gps and len(gps) > 1:
        n = len(gps)
        for i, p in enumerate(gps):
            t = (i / (n - 1)) * duration_s
            spine.append({'time': round(t, 1), 'lat': p.get('lat'), 'lon': p.get('lon'), 'alt_m': p.get('alt')})
    else:
        for p in alt_p:
            spine.append({'time': p['time'], 'lat': None, 'lon': None, 'alt_m': p.get('alt')})

    look_alt = make_lookup(alt_p)
    look_spd = make_lookup(spd_p)
    look_vsp = make_lookup(vsp_p)
    look_bat = make_lookup(bat_p)
    look_gim = make_lookup(gim_p)

    start_dt = None
    fd = flight.get('flight_date')
    if fd:
        try:
            start_dt = datetime.fromisoformat(fd[:19])
        except Exception:
            start_dt = None

    rows = []
    cum_dist_m = 0.0
    prev_pt = None
    for s in spine:
        t = s['time']
        lat, lon = s.get('lat'), s.get('lon')
        if prev_pt is not None and lat is not None:
            cum_dist_m += haversine_m(prev_pt[0], prev_pt[1], lat, lon)
        if lat is not None:
            prev_pt = (lat, lon)

        alt_e = look_alt(t)
        spd_e = look_spd(t)
        vsp_e = look_vsp(t)
        bat_e = look_bat(t)
        gim_e = look_gim(t)

        alt_m = (alt_e or {}).get('alt', s.get('alt_m'))

        rows.append({
            'time(millisecond)':          int(round(t * 1000)),
            'datetime(utc)':              (start_dt + timedelta(seconds=t)).strftime('%Y-%m-%d %H:%M:%S') if start_dt else '',
            'latitude':                   lat if lat is not None else '',
            'longitude':                  lon if lon is not None else '',
            'height_above_takeoff(feet)': round(alt_m / 0.3048, 1) if alt_m is not None else '',
            'distance(feet)':             round(cum_dist_m / 0.3048, 1),
            'speed(mph)':                 round(spd_e['speed'] / 0.44704, 1) if spd_e and 'speed' in spd_e else '',
            'vertical_speed(feet/min)':   round(vsp_e['vspeed'] * 196.850, 1) if vsp_e and 'vspeed' in vsp_e else '',
            'gimbal_pitch(degrees)':      gim_e.get('pitch', '') if gim_e else '',
            'gimbal_roll(degrees)':       gim_e.get('roll', '') if gim_e else '',
            'gimbal_yaw(degrees)':        gim_e.get('yaw', '') if gim_e else '',
            'battery_percent':            bat_e.get('remaining', '') if bat_e else '',
            'voltage':                    bat_e.get('voltage', '') if bat_e else '',
            'current':                    bat_e.get('current', '') if bat_e else '',
            'battery_temperature(C)':     bat_e.get('temperature', '') if bat_e else '',
        })
    return rows


def export_flight_airdata_csv(flight):
    """Export an Airdata-UAV-style per-position telemetry CSV for a single flight."""
    try:
        import csv
        from io import StringIO

        raw_data = flight.get('raw_data') or {}
        if isinstance(raw_data, str):
            raw_data = json.loads(raw_data) if raw_data else {}

        rows = _build_airdata_style_rows(flight, raw_data)
        if not rows:
            ui.notify('No detailed telemetry is stored for this flight — try "Enhance DJI Logs" first.',
                      type='warning')
            return

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

        filename = f"flight_{flight.get('id', 'unknown')}_airdata_style_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        ui.download(output.getvalue().encode('utf-8'), filename)
        ui.notify(f'Airdata-style telemetry exported to {filename}', type='positive')

    except Exception as e:
        ui.notify(f'Failed to export telemetry CSV: {e}', type='negative')


# ════════════════════════════════════════════════════════════════════
# Per-aircraft export — "beautiful" branded PDF of drone + pilot
# statistics, plus a lightweight CSV listing that aircraft's flights.
# ════════════════════════════════════════════════════════════════════

def _drone_stats(flights):
    """Compute aircraft-specific statistics from its flight list for the report."""
    from collections import Counter

    total_minutes = sum(f.get('duration_minutes', 0) or 0 for f in flights)
    longest = max(flights, key=lambda f: f.get('duration_minutes', 0) or 0)
    dated = sorted((f.get('flight_date') or '') for f in flights if f.get('flight_date'))
    months = Counter((f.get('flight_date') or '')[:7] for f in flights if f.get('flight_date'))
    most_active = months.most_common(1)[0] if months else None

    return {
        'total_flights':     len(flights),
        'total_hours':       round(total_minutes / 60, 1),
        'avg_minutes':       round(total_minutes / len(flights), 1),
        'longest_minutes':   longest.get('duration_minutes', 0) or 0,
        'longest_date':      (longest.get('flight_date') or '')[:10] or 'Unknown',
        'first_date':        dated[0][:10] if dated else 'N/A',
        'last_date':         dated[-1][:10] if dated else 'N/A',
        'most_active_month': most_active,
    }


def generate_drone_pdf(sn):
    """Generate a beautiful PDF report of a single aircraft's stats and pilot info."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

        drone = db.get_drone_alias(sn)
        if not drone:
            ui.notify('Aircraft not found', type='negative')
            return

        flights = db.get_flights_for_drone(sn)
        pilot_profile = db.get_pilot_profile()
        title_style, subtitle_style, heading_style, caption_style = _pdf_styles()

        name = drone.get('custom_name') or drone.get('default_model') or 'Unknown Aircraft'
        mfr  = drone.get('manufacturer') or ''

        output_dir = Path('data/reports')
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = output_dir / f'aircraft_{_safe_filename_part(name, "aircraft")}_{timestamp}.pdf'

        doc = SimpleDocTemplate(str(filename), pagesize=letter,
                                topMargin=0.7*inch, bottomMargin=0.6*inch)
        story = []

        story.append(Paragraph('Aircraft Report', title_style))
        story.append(Paragraph(f"{name}   —   {mfr}".rstrip(' —') if mfr else name, subtitle_style))

        story.append(Paragraph('Aircraft Information', heading_style))
        info_rows = [
            ['Aircraft:', name],
            ['Manufacturer / Model:', f"{mfr}  {drone.get('default_model') or ''}".strip()],
            ['Serial Number:', sn],
        ]
        if (drone.get('owner') or '').strip():
            info_rows.append(['Owner:', drone['owner'].strip()])
        if (drone.get('registration') or '').strip():
            info_rows.append(['Registration:', drone['registration'].strip()])
        story.append(_kv_table(info_rows))
        story.append(Spacer(1, 0.2*inch))

        if pilot_profile and pilot_profile.get('pilot_name'):
            story.append(Paragraph('Pilot Information', heading_style))
            story.append(_kv_table([
                ['Pilot:', pilot_profile.get('pilot_name', '')],
                ['Company:', pilot_profile.get('company_name') or 'N/A'],
                ['License / Cert #:', pilot_profile.get('license_number') or 'N/A'],
            ]))
            story.append(Spacer(1, 0.2*inch))

        story.append(Paragraph('Flight Statistics', heading_style))
        if flights:
            stats = _drone_stats(flights)
            stat_rows = [
                ['Total Flights:', str(stats['total_flights'])],
                ['Total Flight Hours:', f"{stats['total_hours']:.1f} hours"],
                ['Average Flight Duration:', f"{stats['avg_minutes']:.1f} minutes"],
                ['Longest Flight:', f"{stats['longest_minutes']:.1f} min   ({stats['longest_date']})"],
                ['First Flight:', stats['first_date']],
                ['Most Recent Flight:', stats['last_date']],
            ]
            if stats['most_active_month']:
                ym, cnt = stats['most_active_month']
                stat_rows.append(['Most Active Month:', f"{ym}   ({cnt} flights)"])
            story.append(_kv_table(stat_rows))
        else:
            story.append(Paragraph('No flights have been logged for this aircraft yet.', caption_style))

        if flights:
            story.append(PageBreak())
            story.append(Paragraph('Flight History', heading_style))
            header = ['Date', 'Duration', 'Max Alt', 'Max Speed', 'Distance']
            data_rows = []
            for f in flights:
                data_rows.append([
                    (f.get('flight_date') or '')[:10] or 'Unknown',
                    f"{f.get('duration_minutes', 0):.1f} min",
                    f"{f['max_altitude_m']:.0f} m"   if f.get('max_altitude_m') else 'N/A',
                    f"{f['max_speed_ms']:.1f} m/s"   if f.get('max_speed_ms')   else 'N/A',
                    f"{f['distance_km']:.2f} km"     if f.get('distance_km')    else 'N/A',
                ])
            story.append(_brand_table(header, data_rows,
                                      [1.3*inch, 1.1*inch, 1.1*inch, 1.2*inch, 1.1*inch]))

        doc.build(story)
        ui.notify(f'✓ Aircraft report generated: {filename.name}', type='positive')
        _open_file(filename)

    except Exception as e:
        ui.notify(f'Error generating aircraft report: {e}', type='negative')
        print(f"Aircraft PDF generation error: {e}")
        import traceback
        traceback.print_exc()


def export_drone_flights_csv(sn, drone_name):
    """Export a lightweight CSV listing one aircraft's flights with basic info."""
    try:
        import csv
        from io import StringIO

        flights = db.get_flights_for_drone(sn)
        if not flights:
            ui.notify('No flights to export for this aircraft', type='warning')
            return

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'date', 'duration_minutes', 'max_altitude_m', 'max_speed_ms', 'distance_km'
        ])
        writer.writeheader()
        for f in flights:
            writer.writerow({
                'id': f.get('id'),
                'date': (f.get('flight_date') or '')[:10],
                'duration_minutes': f.get('duration_minutes', 0),
                'max_altitude_m': f.get('max_altitude_m', ''),
                'max_speed_ms': f.get('max_speed_ms', ''),
                'distance_km': f.get('distance_km', ''),
            })

        filename = f"{_safe_filename_part(drone_name, 'aircraft')}_flights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        ui.download(output.getvalue().encode('utf-8'), filename)
        ui.notify(f'Flight list exported to {filename}', type='positive')

    except Exception as e:
        ui.notify(f'Failed to export flight list: {e}', type='negative')


def generate_pdf_report():
    """Generate a professional PDF flight report"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        
        # Get data
        stats = db.get_statistics()
        advanced_stats = db.get_advanced_statistics()
        pilot_profile = db.get_pilot_profile()
        recent_flights = db.get_all_flights()[:20]  # Last 20 flights
        
        # Create PDF
        output_dir = Path('data/reports')
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = output_dir / f'flight_report_{timestamp}.pdf'
        
        doc = SimpleDocTemplate(str(filename), pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Title
        story.append(Paragraph("Drone Flight Logbook Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Pilot Information
        if pilot_profile:
            story.append(Paragraph("Pilot Information", heading_style))
            pilot_data = [
                ['Pilot Name:', pilot_profile.get('pilot_name', 'N/A')],
                ['License Number:', pilot_profile.get('license_number', 'N/A')],
                ['Company:', pilot_profile.get('company_name', 'N/A')],
            ]
            pilot_table = Table(pilot_data, colWidths=[2*inch, 4*inch])
            pilot_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(pilot_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Report Details
        story.append(Paragraph("Report Details", heading_style))
        report_data = [
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Flight Hours:', f"{stats['total_hours']:.2f} hours"],
            ['Total Flights:', str(stats['total_flights'])],
            ['Aircraft Tracked:', str(advanced_stats['total_aircraft'])],
            ['Manufacturers:', str(advanced_stats['total_manufacturers'])],
        ]
        report_table = Table(report_data, colWidths=[2*inch, 4*inch])
        report_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ]))
        story.append(report_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Pilot Statistics
        story.append(Paragraph("Pilot Statistics", heading_style))
        pilot_stats_data = [
            ['Average Flight Duration:', f"{advanced_stats['average_duration_hours']:.2f} hours"],
        ]
        if advanced_stats['longest_flight']:
            lf = advanced_stats['longest_flight']
            pilot_stats_data.append(['Longest Flight:', f"{lf['duration_hours']:.2f} hours ({lf['drone']})"])
        if advanced_stats['most_flown_aircraft']:
            mf = advanced_stats['most_flown_aircraft']
            pilot_stats_data.append(['Most Flown Aircraft:', f"{mf['model']} ({mf['flights']} flights)"])
        
        pilot_stats_table = Table(pilot_stats_data, colWidths=[2*inch, 4*inch])
        pilot_stats_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(pilot_stats_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Aircraft Breakdown
        story.append(Paragraph("Aircraft Breakdown", heading_style))
        aircraft_data = [['Drone Model', 'Hours', 'Flights']]
        for drone in stats['by_drone']:
            aircraft_data.append([
                drone['model'],
                f"{drone['hours']:.1f}h",
                str(drone['flights'])
            ])
        
        aircraft_table = Table(aircraft_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        aircraft_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(aircraft_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Manufacturer Breakdown
        story.append(Paragraph("Manufacturer Breakdown", heading_style))
        mfr_data = [['Manufacturer', 'Hours', 'Flights']]
        for mfr in stats['by_manufacturer']:
            mfr_data.append([
                mfr['manufacturer'],
                f"{mfr['hours']:.1f}h",
                str(mfr['flights'])
            ])
        
        mfr_table = Table(mfr_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        mfr_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(mfr_table)
        story.append(PageBreak())
        
        # Recent Flight History
        story.append(Paragraph("Recent Flight History", heading_style))
        flight_data = [['Date', 'Drone Model', 'Duration', 'Max Alt']]
        for flight in recent_flights:
            date_str = flight.get('flight_date', '')[:10] if flight.get('flight_date') else 'Unknown'
            duration = flight.get('duration_minutes', 0)
            duration_str = f"{duration:.1f}m"
            alt = flight.get('max_altitude_m', 0)
            alt_str = f"{alt:.0f}m" if alt else 'N/A'
            
            flight_data.append([
                date_str,
                flight.get('drone_model', 'Unknown'),
                duration_str,
                alt_str
            ])
        
        flight_table = Table(flight_data, colWidths=[1.5*inch, 2.5*inch, 1*inch, 1*inch])
        flight_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        story.append(flight_table)
        
        # Build PDF
        doc.build(story)
        
        ui.notify(f'✓ Report generated: {filename.name}', type='positive')
        
        # Open the PDF
        import subprocess
        import platform
        if platform.system() == 'Windows':
            subprocess.Popen(['start', '', str(filename)], shell=True)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', str(filename)])
        else:  # Linux
            subprocess.Popen(['xdg-open', str(filename)])
            
    except Exception as e:
        ui.notify(f'Error generating report: {e}', type='negative')
        print(f"PDF generation error: {e}")
        import traceback
        traceback.print_exc()

@ui.page('/profile')
def profile_page():
    """Pilot profile management page"""
    apply_theme()
    create_header()
    
    colors = get_theme_colors()
    profile = db.get_pilot_profile()
    
    with ui.column().classes('w-full p-8 gap-6'):
        ui.label('Pilot Profile').classes('text-h4 font-bold')
        
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Personal Information').classes('text-h6 mb-4')
            ui.label('This information will be included in generated flight reports').classes('text-caption mb-4')
            
            pilot_name = ui.input(
                label='Pilot Name',
                value=profile.get('pilot_name', '') if profile else ''
            ).classes('w-full')
            
            license_number = ui.input(
                label='License/Certificate Number',
                value=profile.get('license_number', '') if profile else ''
            ).classes('w-full')
            
            company_name = ui.input(
                label='Company Name',
                value=profile.get('company_name', '') if profile else ''
            ).classes('w-full')
            
            notes = ui.textarea(
                label='Notes',
                value=profile.get('notes', '') if profile else ''
            ).classes('w-full')
            
            def save_profile():
                profile_data = {
                    'pilot_name': pilot_name.value,
                    'license_number': license_number.value,
                    'company_name': company_name.value,
                    'notes': notes.value
                }
                if db.save_pilot_profile(profile_data):
                    ui.notify('Profile saved successfully', type='positive')
                else:
                    ui.notify('Error saving profile', type='negative')
            
            ui.button('Save Profile', icon='save', on_click=save_profile, color='positive').classes('mt-4')

        # DJI API Key section
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('DJI Settings').classes('text-h6 mb-2')
            ui.label(
                'DJI Fly app v13+ logs use an encrypted format. Enter your DJI developer API key '
                'once and it will be stored securely on this device. The key is never sent anywhere.'
            ).classes('text-caption mb-4').style('color: #a0a0a0;')

            has_key = config.has_dji_api_key()
            key_status_label = ui.label(
                '✓ DJI API key is configured' if has_key else '✗ No DJI API key set'
            ).style(f'color: {"#10b981" if has_key else "#f59e0b"}; margin-bottom: 12px;')

            dji_key_input = ui.input(
                label='DJI Developer API Key',
                placeholder='Paste your API key here',
                password=True,
                password_toggle_button=True
            ).props('stack-label').classes('w-full')

            def save_dji_key():
                key = dji_key_input.value.strip()
                if not key:
                    ui.notify('Please enter an API key', type='warning')
                    return
                config.set_dji_api_key(key)
                parser_factory.set_dji_api_key(key)   # update live parser
                dji_key_input.value = ''
                key_status_label.text = '✓ DJI API key is configured'
                key_status_label.style('color: #10b981;')
                ui.notify('DJI API key saved — v13+ logs can now be parsed', type='positive')

            def clear_dji_key():
                config.clear_dji_api_key()
                parser_factory.set_dji_api_key(None)
                key_status_label.text = '✗ No DJI API key set'
                key_status_label.style('color: #f59e0b;')
                ui.notify('DJI API key removed', type='info')

            with ui.row().classes('gap-3 mt-2'):
                ui.button('Save Key', icon='vpn_key', on_click=save_dji_key, color='positive')
                ui.button('Remove Key', icon='delete', on_click=clear_dji_key, color='negative')


# Run the application
if __name__ in {"__main__", "__mp_main__"}:
    # Force a clean process exit when the window is closed so no keypress is needed
    app.on_shutdown(lambda: os._exit(0))

    try:
        ui.run(
            title='Skylogr - Professional Flight Logging',
            port=8080,
            reload=False,
            show=True,
            native=True,  # Run as native desktop app
            window_size=(1400, 900),
            fullscreen=False,
        )
    except Exception as e:
        print(f"\n{'='*60}")
        print("WebView2 Error Detected - Attempting Browser Fallback")
        print(f"{'='*60}\n")
        # Fallback to browser mode if native window fails
        ui.run(
            title='Skylogr - Professional Flight Logging',
            port=8080,
            reload=False,
            show=True,
            native=False,  # Use browser instead
        )

# Made with Bob