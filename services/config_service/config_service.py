from tinydb import TinyDB, Query
from typing import Optional, Dict


class ConfigService:
    """Service layer for configuration management database operations"""
    
    def __init__(self, db_path: str = 'boxes.json'):
        """Initialize the service with database connection"""
        self.db = TinyDB(db_path)
        self.config_table = self.db.table('config')
        self.config_query = Query()
    
    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a configuration value by key
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        result = self.config_table.search(self.config_query.key == key)
        if result:
            return result[0].get('value', default)
        return default
    
    def set_config(self, key: str, value: str) -> bool:
        """
        Set a configuration value
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            True if successful
        """
        # Remove existing entry if it exists
        self.config_table.remove(self.config_query.key == key)
        # Insert new entry
        self.config_table.insert({'key': key, 'value': value})
        return True
    
    def get_serial_port(self, default: str = 'COM4') -> str:
        """
        Get the serial port configuration
        
        Args:
            default: Default serial port if not configured
            
        Returns:
            Serial port string
        """
        return self.get_config('cisco_serial_port', default) or default
    
    def set_serial_port(self, serial_port: str) -> bool:
        """
        Set the serial port configuration
        
        Args:
            serial_port: Serial port string (e.g., 'COM4', '/dev/ttyUSB0')
            
        Returns:
            True if successful
        """
        return self.set_config('cisco_serial_port', serial_port)
    
    def get_all_config(self) -> Dict[str, str]:
        """
        Get all configuration values
        
        Returns:
            Dictionary of all configuration key-value pairs
        """
        all_config = self.config_table.all()
        return {item['key']: item['value'] for item in all_config}

