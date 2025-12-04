import serial
import time
import re
from typing import Optional, List, Dict, Tuple
from services.box_service.box_service import BoxService
from services.screen_service.screen_service import ScreenService
from services.cisco_worker.cisco_worker_constants import VIEWER_PORT, VIEWER_VLAN, DEFAULT_BOX_VLAN, DEFAULT_SCREEN_VLAN

# Constants
CONFIG_INDICATOR = "(config)"


class CiscoWorker:
    """Worker for managing Cisco 9300 switch via serial connection"""
    
    def __init__(self, serial_port: str = "COM4", baudrate: int = 9600, 
                 timeout: float = 2.0, db_path: str = 'boxes.json'):
        """
        Initialize Cisco worker
        
        Args:
            serial_port: Serial port name (e.g., 'COM4' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate: Serial communication baudrate
            timeout: Serial read timeout in seconds
            db_path: Path to the database file
        """
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None
        self.box_service = BoxService(db_path)
        self.screen_service = ScreenService(db_path)
        self.default_box_vlan = DEFAULT_BOX_VLAN
        self.default_screen_vlan = DEFAULT_SCREEN_VLAN
        
    def connect(self) -> bool:
        """Establish serial connection to the switch"""
        try:
            self.connection = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            time.sleep(0.5)  # Give the connection time to establish
            # Clear any initial data
            self.connection.flushInput()
            self.connection.flushOutput()
            return True
        except Exception as e:
            print(f"Failed to connect to serial port {self.serial_port}: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.connection = None
    
    def send_command(self, command: str, wait_time: float = 0.5) -> str:
        """
        Send a command to the switch and return the response
        
        Args:
            command: Cisco IOS command to send
            wait_time: Time to wait after sending command (seconds)
            
        Returns:
            Response from the switch
        """
        if not self.connection or not self.connection.is_open:
            raise ConnectionError("Not connected to switch")
        
        # Clear input buffer
        self.connection.flushInput()
        
        # Send command with newline
        command_bytes = (command + '\r\n').encode('utf-8')
        self.connection.write(command_bytes)
        time.sleep(wait_time)
        
        # Read response
        response = b''
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if self.connection.in_waiting > 0:
                response += self.connection.read(self.connection.in_waiting)
                time.sleep(0.1)
            else:
                break
        
        return response.decode('utf-8', errors='ignore')
    
    def enable_mode(self, enable_password: Optional[str] = None) -> bool:
        """
        Enter enable mode (privileged EXEC mode)
        
        Args:
            enable_password: Enable password if required
            
        Returns:
            True if successful, False otherwise
        """
        response = self.send_command("enable")
        if "Password:" in response or "password:" in response.lower():
            if enable_password:
                self.send_command(enable_password)
            else:
                return False
        
        # Verify we're in enable mode
        response = self.send_command("")
        return "#" in response
    
    def configure_terminal(self) -> bool:
        """Enter global configuration mode"""
        response = self.send_command("configure terminal")
        return "config" in response.lower() or CONFIG_INDICATOR in response.lower()
    
    def exit_config_mode(self):
        """Exit configuration mode"""
        self.send_command("end")
        self.send_command("")  # Return to enable prompt
    
    def vlan_exists(self, vlan_id: str) -> bool:
        """
        Check if a VLAN exists on the switch
        
        Args:
            vlan_id: VLAN ID to check
            
        Returns:
            True if VLAN exists, False otherwise
        """
        response = self.send_command(f"show vlan id {vlan_id}")

        if f"VLAN {vlan_id} not found" in response or f"VLAN{vlan_id} not found" in response:
            return False
        else:
            return True
    
    def create_vlan(self, vlan_id: str, vlan_name: Optional[str] = None) -> bool:
        """
        Create a VLAN on the switch
        
        Args:
            vlan_id: VLAN ID to create
            vlan_name: Optional VLAN name
            
        Returns:
            True if successful, False otherwise
        """
        if self.vlan_exists(vlan_id):
            return True  # VLAN already exists
        
        was_in_config = False
        try:
            # Enter config mode if not already
            response = self.send_command("")
            if "#" not in response:
                if not self.enable_mode():
                    return False
            
            response = self.send_command("")
            if CONFIG_INDICATOR not in response.lower():
                self.configure_terminal()
                was_in_config = True
            
            # Create VLAN
            if vlan_name:
                cmd = f"vlan {vlan_id}\nname {vlan_name}"
            else:
                cmd = f"vlan {vlan_id}"
            
            response = self.send_command(cmd, wait_time=0.3)
            
            if was_in_config:
                self.exit_config_mode()
            
            # Verify VLAN was created
            return self.vlan_exists(vlan_id)
        except Exception as e:
            print(f"Error creating VLAN {vlan_id}: {e}")
            if was_in_config:
                self.exit_config_mode()
            return False
    
    def assign_port_to_vlan(self, port: str, vlan_id: str) -> bool:
        """
        Assign a port to a VLAN
        
        Args:
            port: Port identifier (e.g., 'Gi1/0/35')
            vlan_id: VLAN ID to assign
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure VLAN exists
            if not self.create_vlan(vlan_id):
                print(f"Failed to create VLAN {vlan_id}")
                return False
            
            was_in_config = False
            # Enter config mode if not already
            response = self.send_command("")
            if "#" not in response:
                if not self.enable_mode():
                    return False
            
            response = self.send_command("")
            if CONFIG_INDICATOR not in response.lower():
                self.configure_terminal()
                was_in_config = True
            
            # Configure port
            self.send_command(f"interface {port}", wait_time=0.3)
            self.send_command("switchport mode access", wait_time=0.3)
            self.send_command(f"switchport access vlan {vlan_id}", wait_time=0.3)
            self.send_command("no shutdown", wait_time=0.3)
            
            if was_in_config:
                self.exit_config_mode()
            else:
                self.send_command("end")
            
            return True
        except Exception as e:
            print(f"Error assigning port {port} to VLAN {vlan_id}: {e}")
            try:
                self.exit_config_mode()
            except Exception:
                pass
            return False
    
    def get_port_vlan(self, port: str) -> Optional[str]:
        """
        Get the VLAN assigned to a port
        
        Args:
            port: Port identifier (e.g., 'Gi1/0/35')
            
        Returns:
            VLAN ID if found, None otherwise
        """
        response = self.send_command(f"show interfaces {port} switchport")
        
        # Parse VLAN from output
        # Look for "Access Mode VLAN: X" or similar
        match = re.search(r'Access Mode VLAN:\s*(\d+)', response, re.IGNORECASE)
        if match:
            return match.group(1)
        
        match = re.search(r'VLAN\s+(\d+)', response, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def get_port_status(self, port: str) -> Dict[str, str]:
        """
        Get port status information
        
        Args:
            port: Port identifier (e.g., 'Gi1/0/35')
            
        Returns:
            Dictionary with port status information
        """
        response = self.send_command(f"show interfaces {port} status")
        
        status_info = {
            'port': port,
            'status': 'unknown',
            'vlan': None,
            'duplex': None,
            'speed': None,
            'type': None
        }
        
        # Parse status
        if 'connected' in response.lower() or 'up' in response.lower():
            status_info['status'] = 'active'
        elif 'notconnect' in response.lower() or 'down' in response.lower():
            status_info['status'] = 'inactive'
        
        # Get VLAN
        vlan = self.get_port_vlan(port)
        if vlan:
            status_info['vlan'] = vlan
        
        # Try to get more details from switchport command
        switchport_response = self.send_command(f"show interfaces {port} switchport")
        vlan_match = re.search(r'Access Mode VLAN:\s*(\d+)', switchport_response, re.IGNORECASE)
        if vlan_match:
            status_info['vlan'] = vlan_match.group(1)
        
        return status_info
    
    def get_all_ports_status(self) -> List[Dict[str, str]]:
        """
        Get status of all ports on the switch
        
        Returns:
            List of dictionaries with port status information
        """
        response = self.send_command("show interfaces status")
        
        ports = []
        lines = response.split('\n')
        
        for line in lines:
            # Parse port status line
            # Format typically: Gi1/0/1  connected  trunk    a-full  a-1000  10/100/1000BaseTX
            parts = line.split()
            if len(parts) >= 2 and ('Gi' in parts[0] or 'Fa' in parts[0] or 'Te' in parts[0]):
                port = parts[0]
                status = 'active' if 'connected' in line.lower() or 'up' in line.lower() else 'inactive'
                
                port_info = {
                    'port': port,
                    'status': status,
                    'vlan': None
                }
                
                # Get VLAN for this port
                vlan = self.get_port_vlan(port)
                if vlan:
                    port_info['vlan'] = vlan
                
                ports.append(port_info)
        
        return ports
    
    def sync_with_db(self) -> bool:
        """
        Synchronize switch configuration with database state
        This is called on server startup to align switch with DB
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.connection or not self.connection.is_open:
                if not self.connect():
                    return False
            
            if not self.enable_mode():
                print("Failed to enter enable mode")
                return False
            
            # Get all boxes and screens from DB
            boxes = self.box_service.get_all_boxes()
            screens = self.screen_service.get_all_screens()
            
            # Process screens (fixed VLANs)
            for screen in screens:
                port = screen.get('port_number')
                vlan = screen.get('vlan_number')
                
                if port and vlan:
                    print(f"Syncing screen port {port} to VLAN {vlan}")
                    if not self.assign_port_to_vlan(port, vlan):
                        print(f"Failed to sync screen port {port}")
            
            # Process boxes (dynamic VLANs, default to 1)
            for box in boxes:
                port = box.get('port_number')
                vlan = box.get('vlan_number') or self.default_box_vlan
                
                if port:
                    print(f"Syncing box port {port} to VLAN {vlan}")
                    if not self.assign_port_to_vlan(port, vlan):
                        print(f"Failed to sync box port {port}")
            
            return True
        except Exception as e:
            print(f"Error syncing with DB: {e}")
            return False
    
    def assign_box_to_screen_vlan(self, box_port: str, screen_vlan: str) -> bool:
        """
        Assign a box port to a screen's VLAN (for physical connection)
        
        Args:
            box_port: Box port identifier
            screen_vlan: Screen VLAN ID
            
        Returns:
            True if successful, False otherwise
        """
        return self.assign_port_to_vlan(box_port, screen_vlan)
    
    def get_switch_info(self) -> Dict:
        """
        Get comprehensive switch information
        
        Returns:
            Dictionary with switch information
        """
        info = {
            'connected': self.connection is not None and self.connection.is_open,
            'ports': [],
            'vlans': []
        }
        
        if not info['connected']:
            return info
        
        try:
            # Get all ports
            info['ports'] = self.get_all_ports_status()
            
            # Get VLAN list
            response = self.send_command("show vlan brief")
            vlan_lines = response.split('\n')
            for line in vlan_lines:
                # Parse VLAN line
                parts = line.split()
                if len(parts) >= 2 and parts[0].isdigit():
                    vlan_id = parts[0]
                    vlan_name = parts[1] if len(parts) > 1 else f"VLAN{vlan_id}"
                    info['vlans'].append({
                        'id': vlan_id,
                        'name': vlan_name
                    })
        except Exception as e:
            print(f"Error getting switch info: {e}")
        
        return info

