"""
Configuration Manager
Handles encrypted storage of DJI API keys and app settings
"""
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
import base64

class ConfigManager:
    """Manages encrypted configuration and API keys"""
    
    def __init__(self, config_dir='data/config'):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / 'app_config.json'
        self.key_file = self.config_dir / '.key'
        self.encrypted_keys_file = self.config_dir / 'api_keys.enc'
        
        self._ensure_encryption_key()
        self.config = self._load_config()
    
    def _ensure_encryption_key(self):
        """Ensure encryption key exists"""
        if not self.key_file.exists():
            # Generate a new encryption key
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            # Make it read-only
            os.chmod(self.key_file, 0o600)
    
    def _get_cipher(self):
        """Get Fernet cipher for encryption/decryption"""
        key = self.key_file.read_bytes()
        return Fernet(key)
    
    def _load_config(self):
        """Load application configuration"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {
            'theme': 'dark',
            'dji_api_key_set': False,
            'auto_import_enabled': False,
            'watch_folder': None,
            'last_import_folder': None,
            'license_key': None,
            'premium_features_enabled': False
        }
    
    def _save_config(self):
        """Save application configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self._save_config()
    
    def set_dji_api_key(self, api_key: str):
        """Store DJI API key encrypted"""
        cipher = self._get_cipher()
        encrypted = cipher.encrypt(api_key.encode())
        self.encrypted_keys_file.write_bytes(encrypted)
        self.set('dji_api_key_set', True)
    
    def get_dji_api_key(self) -> str:
        """Retrieve DJI API key (decrypted)"""
        if not self.encrypted_keys_file.exists():
            return None
        
        try:
            cipher = self._get_cipher()
            encrypted = self.encrypted_keys_file.read_bytes()
            decrypted = cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            print(f"Error decrypting API key: {e}")
            return None
    
    def has_dji_api_key(self) -> bool:
        """Check if DJI API key is configured"""
        return self.get('dji_api_key_set', False) and self.encrypted_keys_file.exists()
    
    def clear_dji_api_key(self):
        """Remove DJI API key"""
        if self.encrypted_keys_file.exists():
            self.encrypted_keys_file.unlink()
        self.set('dji_api_key_set', False)
    
    def get_theme(self) -> str:
        """Get current theme"""
        return self.get('theme', 'dark')
    
    def set_theme(self, theme: str):
        """Set theme (light/dark)"""
        self.set('theme', theme)
    
    def toggle_theme(self) -> str:
        """Toggle between light and dark theme"""
        current = self.get_theme()
        new_theme = 'light' if current == 'dark' else 'dark'
        self.set_theme(new_theme)
        return new_theme
    
    def is_premium(self) -> bool:
        """Check if premium features are enabled"""
        return self.get('premium_features_enabled', False)
    
    def set_license_key(self, license_key: str) -> bool:
        """Set and validate license key"""
        # Placeholder for license validation
        # In production, this would validate against a license server or algorithm
        if license_key and len(license_key) >= 16:
            self.set('license_key', license_key)
            self.set('premium_features_enabled', True)
            return True
        return False
    
    def export_settings(self, export_path: str):
        """Export non-sensitive settings"""
        export_data = {
            'theme': self.get_theme(),
            'auto_import_enabled': self.get('auto_import_enabled'),
            'watch_folder': self.get('watch_folder')
        }
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    def import_settings(self, import_path: str):
        """Import settings from file"""
        with open(import_path, 'r') as f:
            imported = json.load(f)
        
        for key, value in imported.items():
            if key not in ['dji_api_key_set', 'license_key', 'premium_features_enabled']:
                self.set(key, value)

# Made with Bob