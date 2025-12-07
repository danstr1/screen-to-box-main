import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QLineEdit,
    QLabel, QMessageBox, QDialog, QFormLayout, QComboBox, QGroupBox,
    QTextEdit, QHeaderView, QSplitter, QCheckBox, QProgressDialog
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from typing import Optional, Dict, List


class BaseURL:
    """Base URL for API requests"""
    BASE_URL = "http://localhost:5000"


class SwitchStatusThread(QThread):
    """Background thread for checking switch status"""
    status_updated = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.running = True
    
    def run(self):
        """Run the background thread"""
        try:
            response = requests.get(
                f"{self.base_url}/switch/info",
                timeout=2
            )
            if response.status_code == 200:
                self.status_updated.emit(response.json())
            else:
                self.error_occurred.emit("Failed to get switch status")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Timeout")
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def stop(self):
        """Stop the thread"""
        self.running = False


class SyncVLANsThread(QThread):
    """Background thread for syncing VLANs from switch"""
    sync_completed = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
    
    def run(self):
        """Run the sync operation"""
        try:
            response = requests.get(
                f"{self.base_url}/switch/ports_vlans",
                timeout=180
            )
            if response.status_code == 200:
                self.sync_completed.emit(response.json())
            else:
                self.error_occurred.emit(f"Failed to sync VLANs: {response.status_code}")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Operation timed out after 3 minutes")
        except Exception as e:
            self.error_occurred.emit(f"Error syncing VLANs: {str(e)}")


class ResetVLANsThread(QThread):
    """Background thread for resetting all screen VLANs"""
    reset_completed = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
    
    def run(self):
        """Run the reset operation"""
        try:
            response = requests.post(
                f"{self.base_url}/screens/reset_all_vlans",
                timeout=120
            )
            if response.status_code == 200:
                self.reset_completed.emit(response.json())
            else:
                self.error_occurred.emit(f"Failed to reset VLANs: {response.status_code}")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Operation timed out after 2 minutes")
        except Exception as e:
            self.error_occurred.emit(f"Error resetting VLANs: {str(e)}")


class AddEditBoxDialog(QDialog):
    """Dialog for adding or editing a box"""
    
    def __init__(self, parent=None, box_data: Optional[Dict] = None):
        super().__init__(parent)
        self.box_data = box_data
        self.setWindowTitle("Edit Box" if box_data else "Add Box")
        self.setModal(True)
        self.setup_ui()
        
        if box_data:
            self.load_box_data()
    
    def setup_ui(self):
        layout = QFormLayout()
        
        self.box_number_input = QLineEdit()
        self.port_number_input = QLineEdit()
        self.vlan_number_input = QLineEdit()
        
        layout.addRow("Box Number:", self.box_number_input)
        layout.addRow("Port Number:", self.port_number_input)
        layout.addRow("VLAN Number:", self.vlan_number_input)
        
        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        
        layout.addRow(buttons)
        self.setLayout(layout)
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
    
    def load_box_data(self):
        if self.box_data:
            self.box_number_input.setText(str(self.box_data.get('box_number', '')))
            self.port_number_input.setText(str(self.box_data.get('port_number', '')))
            if self.box_data.get('vlan_number'):
                self.vlan_number_input.setText(str(self.box_data.get('vlan_number', '')))
    
    def get_data(self) -> Dict:
        return {
            'box_number': self.box_number_input.text().strip(),
            'port_number': self.port_number_input.text().strip(),
            'vlan_number': self.vlan_number_input.text().strip()
        }


class AddEditScreenDialog(QDialog):
    """Dialog for adding or editing a screen"""
    
    def __init__(self, parent=None, screen_data: Optional[Dict] = None):
        super().__init__(parent)
        self.screen_data = screen_data
        self.setWindowTitle("Edit Screen" if screen_data else "Add Screen")
        self.setModal(True)
        self.setup_ui()
        
        if screen_data:
            self.load_screen_data()
    
    def setup_ui(self):
        layout = QFormLayout()
        
        self.screen_number_input = QLineEdit()
        self.port_number_input = QLineEdit()
        
        layout.addRow("Screen Number:", self.screen_number_input)
        layout.addRow("Port Number:", self.port_number_input)
        
        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        
        layout.addRow(buttons)
        self.setLayout(layout)
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
    
    def load_screen_data(self):
        if self.screen_data:
            if self.screen_data.get('screen_number'):
                self.screen_number_input.setText(str(self.screen_data.get('screen_number', '')))
            self.port_number_input.setText(str(self.screen_data.get('port_number', '')))
    
    def get_data(self) -> Dict:
        return {
            'screen_number': self.screen_number_input.text().strip() or None,
            'port_number': self.port_number_input.text().strip()
        }


class AssignBoxToScreenDialog(QDialog):
    """Dialog for assigning a box to a screen"""
    
    def __init__(self, parent=None, boxes: List[Dict] = None, screens: List[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Assign Box to Screen")
        self.setModal(True)
        self.setup_ui(boxes or [], screens or [])
    
    def setup_ui(self, boxes: List[Dict], screens: List[Dict]):
        layout = QFormLayout()
        
        self.box_combo = QComboBox()
        self.screen_combo = QComboBox()
        
        # Populate boxes (show free boxes or all boxes)
        for box in boxes:
            user_info = f" (User: {box.get('user_id')})" if box.get('user_id') else " (Free)"
            self.box_combo.addItem(f"Box {box.get('box_number', box.get('box_id'))} - {box.get('port_number')}{user_info}", box.get('box_id'))
        
        # Populate screens (show free screens or all screens)
        for screen in screens:
            box_info = f" (Box: {screen.get('box_id')})" if screen.get('box_id') else " (Free)"
            screen_num = screen.get('screen_number', screen.get('screen_id'))
            self.screen_combo.addItem(f"Screen {screen_num} - {screen.get('port_number')}{box_info}", screen.get('screen_id'))
        
        layout.addRow("Box:", self.box_combo)
        layout.addRow("Screen:", self.screen_combo)
        
        buttons = QHBoxLayout()
        self.assign_btn = QPushButton("Assign")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.assign_btn)
        buttons.addWidget(self.cancel_btn)
        
        layout.addRow(buttons)
        self.setLayout(layout)
        
        self.assign_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
    
    def get_selection(self) -> tuple:
        box_id = self.box_combo.currentData()
        screen_id = self.screen_combo.currentData()
        return box_id, screen_id


class BackofficeUI(QMainWindow):
    """Main backoffice UI window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Server - Backoffice")
        self.setGeometry(100, 100, 1400, 900)
        
        # Switch status cache
        self.last_switch_status = None
        self.switch_refresh_enabled = False
        self.switch_status_thread = None
        
        self.setup_ui()
        
        # Setup non-blocking refresh timer for switch (disabled by default)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_switch_status_background)
        # Don't start timer by default - user must enable it
        
        # Load initial data (without switch)
        self.refresh_all()
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Create tab widget
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Screens tab
        screens_tab = self.create_screens_tab()
        tabs.addTab(screens_tab, "Screens")
        
        # Boxes tab
        boxes_tab = self.create_boxes_tab()
        tabs.addTab(boxes_tab, "Boxes")
        
        # Assignments tab
        assignments_tab = self.create_assignments_tab()
        tabs.addTab(assignments_tab, "Assignments")
        
        # Switch Status tab
        switch_tab = self.create_switch_tab()
        tabs.addTab(switch_tab, "Switch Status")
        
        # Overview tab
        overview_tab = self.create_overview_tab()
        tabs.addTab(overview_tab, "Overview")
    
    def create_screens_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.add_screen_btn = QPushButton("Add Screen")
        self.edit_screen_btn = QPushButton("Edit Screen")
        self.delete_screen_btn = QPushButton("Delete Screen")
        self.reconfigure_screen_vlan_btn = QPushButton("Reconfigure Screen VLAN")
        self.reset_screen_vlans_btn = QPushButton("Reset All VLANs to 101")
        self.sync_switch_vlans_btn = QPushButton("Sync Switch VLANs")
        self.refresh_screens_btn = QPushButton("Refresh")
        
        btn_layout.addWidget(self.add_screen_btn)
        btn_layout.addWidget(self.edit_screen_btn)
        btn_layout.addWidget(self.delete_screen_btn)
        btn_layout.addWidget(self.reconfigure_screen_vlan_btn)
        btn_layout.addWidget(self.reset_screen_vlans_btn)
        btn_layout.addWidget(self.sync_switch_vlans_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_screens_btn)
        
        layout.addLayout(btn_layout)
        
        # Table
        self.screens_table = QTableWidget()
        self.screens_table.setColumnCount(6)
        self.screens_table.setHorizontalHeaderLabels(["ID", "Screen Number", "Port Number", "VLAN Number", "Actual VLAN in SW", "Box ID"])
        self.screens_table.horizontalHeader().setStretchLastSection(True)
        self.screens_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.screens_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        layout.addWidget(self.screens_table)
        
        # Connect buttons
        self.add_screen_btn.clicked.connect(self.add_screen)
        self.edit_screen_btn.clicked.connect(self.edit_screen)
        self.delete_screen_btn.clicked.connect(self.delete_screen)
        self.reconfigure_screen_vlan_btn.clicked.connect(self.reconfigure_screen_vlan)
        self.reset_screen_vlans_btn.clicked.connect(self.reset_all_screen_vlans)
        self.sync_switch_vlans_btn.clicked.connect(self.sync_switch_vlans)
        self.refresh_screens_btn.clicked.connect(self.refresh_screens)
        
        return widget
    
    def create_boxes_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.add_box_btn = QPushButton("Add Box")
        self.edit_box_btn = QPushButton("Edit Box")
        self.delete_box_btn = QPushButton("Delete Box")
        self.refresh_boxes_btn = QPushButton("Refresh")
        
        btn_layout.addWidget(self.add_box_btn)
        btn_layout.addWidget(self.edit_box_btn)
        btn_layout.addWidget(self.delete_box_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_boxes_btn)
        
        layout.addLayout(btn_layout)
        
        # Table
        self.boxes_table = QTableWidget()
        self.boxes_table.setColumnCount(6)
        self.boxes_table.setHorizontalHeaderLabels(["ID", "Box Number", "Port Number", "VLAN Number", "Actual VLAN in SW", "User ID"])
        self.boxes_table.horizontalHeader().setStretchLastSection(True)
        self.boxes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.boxes_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        layout.addWidget(self.boxes_table)
        
        # Connect buttons
        self.add_box_btn.clicked.connect(self.add_box)
        self.edit_box_btn.clicked.connect(self.edit_box)
        self.delete_box_btn.clicked.connect(self.delete_box)
        self.refresh_boxes_btn.clicked.connect(self.refresh_boxes)
        
        return widget
    
    def create_assignments_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.assign_btn = QPushButton("Assign Box to Screen")
        self.unassign_btn = QPushButton("Unassign")
        self.refresh_assignments_btn = QPushButton("Refresh")
        
        btn_layout.addWidget(self.assign_btn)
        btn_layout.addWidget(self.unassign_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_assignments_btn)
        
        layout.addLayout(btn_layout)
        
        # Table
        self.assignments_table = QTableWidget()
        self.assignments_table.setColumnCount(6)
        self.assignments_table.setHorizontalHeaderLabels(["Screen ID", "Screen Number", "Screen Port", "Box ID", "Box Number", "Box Port"])
        self.assignments_table.horizontalHeader().setStretchLastSection(True)
        self.assignments_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.assignments_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        layout.addWidget(self.assignments_table)
        
        # Connect buttons
        self.assign_btn.clicked.connect(self.assign_box_to_screen)
        self.unassign_btn.clicked.connect(self.unassign_box_from_screen)
        self.refresh_assignments_btn.clicked.connect(self.refresh_assignments)
        
        return widget
    
    def create_switch_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # COM Port Configuration
        com_port_group = QGroupBox("Serial Port Configuration")
        com_port_layout = QFormLayout()
        self.com_port_input = QLineEdit()
        self.com_port_save_btn = QPushButton("Save COM Port")
        self.com_port_refresh_btn = QPushButton("Refresh")
        
        com_port_layout.addRow("COM Port:", self.com_port_input)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.com_port_save_btn)
        btn_layout.addWidget(self.com_port_refresh_btn)
        com_port_layout.addRow(btn_layout)
        com_port_group.setLayout(com_port_layout)
        
        layout.addWidget(com_port_group)
        
        # Status info
        status_group = QGroupBox("Switch Connection Status")
        status_layout = QVBoxLayout()
        self.switch_status_label = QLabel("Status: Not Connected")
        
        # Auto-refresh checkbox
        self.auto_refresh_checkbox = QCheckBox("Enable Auto-Refresh (every 10 seconds)")
        self.auto_refresh_checkbox.setChecked(False)
        self.auto_refresh_checkbox.stateChanged.connect(self.toggle_auto_refresh)
        
        self.switch_connect_btn = QPushButton("Connect")
        self.switch_disconnect_btn = QPushButton("Disconnect")
        self.switch_refresh_btn = QPushButton("Refresh Status")
        self.switch_sync_btn = QPushButton("Sync with Database")
        
        status_layout.addWidget(self.switch_status_label)
        status_layout.addWidget(self.auto_refresh_checkbox)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.switch_connect_btn)
        btn_layout.addWidget(self.switch_disconnect_btn)
        btn_layout.addWidget(self.switch_refresh_btn)
        btn_layout.addWidget(self.switch_sync_btn)
        status_layout.addLayout(btn_layout)
        status_group.setLayout(status_layout)
        
        layout.addWidget(status_group)
        
        # Ports table
        ports_label = QLabel("Switch Ports:")
        layout.addWidget(ports_label)
        
        self.switch_ports_table = QTableWidget()
        self.switch_ports_table.setColumnCount(3)
        self.switch_ports_table.setHorizontalHeaderLabels(["Port", "Status", "VLAN"])
        self.switch_ports_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.switch_ports_table)
        
        # Connect buttons
        self.switch_connect_btn.clicked.connect(self.connect_switch)
        self.switch_disconnect_btn.clicked.connect(self.disconnect_switch)
        self.switch_refresh_btn.clicked.connect(self.refresh_switch_status_manual)
        self.switch_sync_btn.clicked.connect(self.sync_switch)
        self.com_port_save_btn.clicked.connect(self.save_com_port)
        self.com_port_refresh_btn.clicked.connect(self.refresh_com_port)
        
        return widget
    
    def create_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Refresh button
        btn_layout = QHBoxLayout()
        self.refresh_overview_btn = QPushButton("Refresh Overview")
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_overview_btn)
        layout.addLayout(btn_layout)
        
        # Overview text
        self.overview_text = QTextEdit()
        self.overview_text.setReadOnly(True)
        layout.addWidget(self.overview_text)
        
        # Connect button
        self.refresh_overview_btn.clicked.connect(self.refresh_overview)
        
        return widget
    
    def toggle_auto_refresh(self, state):
        """Toggle automatic switch status refresh"""
        if state == Qt.CheckState.Checked.value:
            self.switch_refresh_enabled = True
            self.refresh_timer.start(10000)  # Refresh every 10 seconds
            self.refresh_switch_status_background()
        else:
            self.switch_refresh_enabled = False
            self.refresh_timer.stop()
    
    # API Methods
    def api_request(self, method: str, endpoint: str, data: Optional[Dict] = None, show_error: bool = True, timeout: int = 5) -> Optional[Dict]:
        """Make API request and return response"""
        try:
            url = f"{BaseURL.BASE_URL}{endpoint}"
            # Use shorter timeout for switch operations to prevent blocking
            timeout = 3 if '/switch/' in endpoint else 5
            timeout = 30 if '/ports_vlan' in endpoint else timeout
            
            if method == "GET":
                response = requests.get(url, timeout=timeout)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=timeout)
            elif method == "PUT":
                response = requests.put(url, json=data, timeout=timeout)
            elif method == "PATCH":
                response = requests.patch(url, json=data, timeout=timeout)
            elif method == "DELETE":
                response = requests.delete(url, timeout=timeout)
            else:
                return None
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                error_msg = response.json().get('error', 'Unknown error')
                if show_error:
                    QMessageBox.warning(self, "Error", f"API Error: {error_msg}")
                return None
        except requests.exceptions.Timeout:
            if show_error and '/switch/' not in endpoint:
                QMessageBox.warning(self, "Timeout", f"Request to {endpoint} timed out")
            return None
        except requests.exceptions.RequestException as e:
            if show_error and '/switch/' not in endpoint:
                QMessageBox.warning(self, "Connection Error", f"Failed to connect to server: {str(e)}")
            return None
    
    # Screen methods
    def refresh_screens(self):
        screens = self.api_request("GET", "/screens")
        if screens:
            self.screens_table.setRowCount(len(screens))
            for row, screen in enumerate(screens):
                self.screens_table.setItem(row, 0, QTableWidgetItem(str(screen.get('screen_id', ''))))
                self.screens_table.setItem(row, 1, QTableWidgetItem(str(screen.get('screen_number', ''))))
                self.screens_table.setItem(row, 2, QTableWidgetItem(str(screen.get('port_number', ''))))
                self.screens_table.setItem(row, 3, QTableWidgetItem(str(screen.get('vlan_number', '') or '')))
                self.screens_table.setItem(row, 4, QTableWidgetItem(''))  # Actual VLAN - will be filled by sync
                self.screens_table.setItem(row, 5, QTableWidgetItem(str(screen.get('box_id', '') or '')))
    
    def add_screen(self):
        dialog = AddEditScreenDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data.get('port_number'):
                QMessageBox.warning(self, "Validation Error", "Port number is required")
                return
            
            result = self.api_request("POST", "/screens", data)
            if result:
                QMessageBox.information(self, "Success", "Screen added successfully")
                self.refresh_screens()
                self.refresh_assignments()
                self.refresh_overview()
    
    def edit_screen(self):
        selected = self.screens_table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a screen to edit")
            return
        
        screen_id = int(self.screens_table.item(selected, 0).text())
        screen_data = None
        
        # Get current screen data
        result = self.api_request("GET", f"/screens/{screen_id}")
        if result:
            screen_data = result
        
        dialog = AddEditScreenDialog(self, screen_data)
        if dialog.exec():
            data = dialog.get_data()
            result = self.api_request("PUT", f"/screens/{screen_id}", data)
            if result:
                QMessageBox.information(self, "Success", "Screen updated successfully")
                self.refresh_screens()
                self.refresh_assignments()
                self.refresh_overview()
    
    def delete_screen(self):
        selected = self.screens_table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a screen to delete")
            return
        
        screen_id = int(self.screens_table.item(selected, 0).text())
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete screen {screen_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = self.api_request("DELETE", f"/screens/{screen_id}")
            if result:
                QMessageBox.information(self, "Success", "Screen deleted successfully")
                self.refresh_screens()
                self.refresh_assignments()
                self.refresh_overview()
    
    def reconfigure_screen_vlan(self):
        """Reconfigure selected screen's VLAN on the switch based on its assigned box"""
        selected = self.screens_table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a screen to reconfigure")
            return
        
        screen_id = int(self.screens_table.item(selected, 0).text())
        screen_port = self.screens_table.item(selected, 2).text()
        
        # Get screen data
        screen = None
        screens = self.api_request("GET", "/screens")
        if screens:
            for s in screens:
                if s.get('screen_id') == screen_id:
                    screen = s
                    break
        
        if not screen:
            QMessageBox.warning(self, "Error", "Screen not found")
            return
        
        box_id = screen.get('box_id')
        
        # Determine target VLAN
        if box_id:
            # Screen is assigned to a box, use box's VLAN
            boxes = self.api_request("GET", "/boxes")
            box = None
            if boxes:
                for b in boxes:
                    if b.get('box_id') == box_id:
                        box = b
                        break
            
            if not box:
                QMessageBox.warning(self, "Error", "Assigned box not found")
                return
            
            target_vlan = box.get('vlan_number')
            if not target_vlan:
                QMessageBox.warning(self, "Error", "Box has no VLAN configured")
                return
            
            message = f"Reconfigure screen {screen_id} (port {screen_port}) to use box's VLAN {target_vlan}?"
        else:
            # Screen is not assigned, use default screen VLAN (101)
            target_vlan = "101"
            message = f"Screen {screen_id} is not assigned to any box.\nReconfigure port {screen_port} to default screen VLAN {target_vlan}?"
        
        reply = QMessageBox.question(
            self, "Confirm Reconfigure",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Make API call to reconfigure the port
            result = self.api_request(
                "POST",
                "/switch/reconfigure_port",
                {"port": screen_port, "vlan": target_vlan},
                timeout=30
            )
            
            if result:
                QMessageBox.information(self, "Success", 
                    f"Screen {screen_id} port {screen_port} reconfigured to VLAN {target_vlan}")
                # Refresh to show updated actual VLAN
                self.sync_switch_vlans()
            else:
                QMessageBox.warning(self, "Error", "Failed to reconfigure screen VLAN")
    
    def reset_all_screen_vlans(self):
        """Reset all screen ports to default VLAN 101"""
        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Are you sure you want to reset all screen ports to VLAN 101?\nThis will affect all screens regardless of their current assignment.\n\nThis operation may take several minutes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Create progress dialog
            progress = QProgressDialog("Resetting all screen VLANs to 101...", "Cancel", 0, 0, self)
            progress.setWindowTitle("Resetting VLANs")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)  # Cannot cancel this operation
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()
            
            # Create and start worker thread
            self.reset_thread = ResetVLANsThread(BaseURL.BASE_URL)
            self.reset_thread.reset_completed.connect(lambda result: self._on_reset_completed(result, progress))
            self.reset_thread.error_occurred.connect(lambda error: self._on_reset_error(error, progress))
            self.reset_thread.start()
    
    def sync_switch_vlans(self):
        """Sync actual VLANs from switch and display in tables"""
        # Create progress dialog
        progress = QProgressDialog("Syncing VLANs from switch...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Syncing VLANs")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)  # Cannot cancel this operation
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        
        # Create and start worker thread
        self.sync_thread = SyncVLANsThread(BaseURL.BASE_URL)
        self.sync_thread.sync_completed.connect(lambda result: self._on_sync_completed(result, progress))
        self.sync_thread.error_occurred.connect(lambda error: self._on_sync_error(error, progress))
        self.sync_thread.start()
    
    def _on_sync_completed(self, result, progress):
        """Handle sync completion"""
        progress.close()
        
        boxes_vlans = result.get('boxes', {})
        screens_vlans = result.get('screens', {})
        
        print(f"[DEBUG] Received boxes_vlans: {boxes_vlans}")
        print(f"[DEBUG] Received screens_vlans: {screens_vlans}")
        
        # Update screens table
        updated_screens = 0
        for row in range(self.screens_table.rowCount()):
            screen_id_item = self.screens_table.item(row, 0)
            if screen_id_item:
                screen_id = int(screen_id_item.text())
                # Try both integer and string keys
                actual_vlan = screens_vlans.get(screen_id) or screens_vlans.get(str(screen_id))
                if actual_vlan:
                    self.screens_table.setItem(row, 4, QTableWidgetItem(str(actual_vlan)))
                    updated_screens += 1
                    print(f"[DEBUG] Updated screen {screen_id} with VLAN {actual_vlan}")
                else:
                    self.screens_table.setItem(row, 4, QTableWidgetItem('N/A'))
                    print(f"[DEBUG] No VLAN found for screen {screen_id}")
        
        # Update boxes table
        updated_boxes = 0
        for row in range(self.boxes_table.rowCount()):
            box_id_item = self.boxes_table.item(row, 0)
            if box_id_item:
                box_id = int(box_id_item.text())
                # Try both integer and string keys
                actual_vlan = boxes_vlans.get(box_id) or boxes_vlans.get(str(box_id))
                if actual_vlan:
                    self.boxes_table.setItem(row, 4, QTableWidgetItem(str(actual_vlan)))
                    updated_boxes += 1
                    print(f"[DEBUG] Updated box {box_id} with VLAN {actual_vlan}")
                else:
                    self.boxes_table.setItem(row, 4, QTableWidgetItem('N/A'))
                    print(f"[DEBUG] No VLAN found for box {box_id}")
        
        QMessageBox.information(self, "Success", 
            f"Synced VLANs from switch:\n{updated_screens} screens updated\n{updated_boxes} boxes updated")
    
    def _on_sync_error(self, error, progress):
        """Handle sync error"""
        progress.close()
        QMessageBox.warning(self, "Error", f"Failed to sync VLANs from switch:\n{error}")
    
    def _on_reset_completed(self, result, progress):
        """Handle reset completion"""
        progress.close()
        
        message = result.get('message', 'Operation completed')
        warning = result.get('warning')
        if warning:
            QMessageBox.warning(self, "Partial Success", f"{message}\n\n{warning}")
        else:
            QMessageBox.information(self, "Success", message)
        self.refresh_screens()
    
    def _on_reset_error(self, error, progress):
        """Handle reset error"""
        progress.close()
        QMessageBox.warning(self, "Error", f"Failed to reset VLANs:\n{error}")
    
    # Box methods
    def refresh_boxes(self):
        boxes = self.api_request("GET", "/boxes")
        if boxes:
            self.boxes_table.setRowCount(len(boxes))
            for row, box in enumerate(boxes):
                self.boxes_table.setItem(row, 0, QTableWidgetItem(str(box.get('box_id', ''))))
                self.boxes_table.setItem(row, 1, QTableWidgetItem(str(box.get('box_number', ''))))
                self.boxes_table.setItem(row, 2, QTableWidgetItem(str(box.get('port_number', ''))))
                self.boxes_table.setItem(row, 3, QTableWidgetItem(str(box.get('vlan_number', '') or '')))
                self.boxes_table.setItem(row, 4, QTableWidgetItem(''))  # Actual VLAN - will be filled by sync
                self.boxes_table.setItem(row, 5, QTableWidgetItem(str(box.get('user_id', '') or '')))
    
    def add_box(self):
        dialog = AddEditBoxDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data.get('port_number') or not data.get('box_number'):
                QMessageBox.warning(self, "Validation Error", "Port number and box number are required")
                return
            if not data.get('vlan_number'):
                QMessageBox.warning(self, "Validation Error", "VLAN number is required")
                return
            
            result = self.api_request("POST", "/boxes", data)
            if result:
                QMessageBox.information(self, "Success", "Box added successfully")
                self.refresh_boxes()
                self.refresh_assignments()
                self.refresh_overview()
    
    def edit_box(self):
        selected = self.boxes_table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a box to edit")
            return
        
        box_id = int(self.boxes_table.item(selected, 0).text())
        box_data = None
        
        # Get current box data
        boxes = self.api_request("GET", "/boxes")
        if boxes:
            for box in boxes:
                if box.get('box_id') == box_id:
                    box_data = box
                    break
        
        dialog = AddEditBoxDialog(self, box_data)
        if dialog.exec():
            data = dialog.get_data()
            result = self.api_request("PUT", f"/boxes/{box_id}", data)
            if result:
                QMessageBox.information(self, "Success", "Box updated successfully")
                self.refresh_boxes()
                self.refresh_assignments()
                self.refresh_overview()
    
    def delete_box(self):
        selected = self.boxes_table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a box to delete")
            return
        
        box_id = int(self.boxes_table.item(selected, 0).text())
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete box {box_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = self.api_request("DELETE", f"/boxes/{box_id}")
            if result:
                QMessageBox.information(self, "Success", "Box deleted successfully")
                self.refresh_boxes()
                self.refresh_assignments()
                self.refresh_overview()
    
    # Assignment methods
    def refresh_assignments(self):
        screens = self.api_request("GET", "/screens")
        if screens:
            assignments = [s for s in screens if s.get('box_id') is not None]
            self.assignments_table.setRowCount(len(assignments))
            
            boxes = self.api_request("GET", "/boxes")
            boxes_dict = {box.get('box_id'): box for box in boxes} if boxes else {}
            
            for row, screen in enumerate(assignments):
                box_id = screen.get('box_id')
                box = boxes_dict.get(box_id, {})
                
                self.assignments_table.setItem(row, 0, QTableWidgetItem(str(screen.get('screen_id', ''))))
                self.assignments_table.setItem(row, 1, QTableWidgetItem(str(screen.get('screen_number', '') or '')))
                self.assignments_table.setItem(row, 2, QTableWidgetItem(str(screen.get('port_number', ''))))
                self.assignments_table.setItem(row, 3, QTableWidgetItem(str(box_id)))
                self.assignments_table.setItem(row, 4, QTableWidgetItem(str(box.get('box_number', '') or '')))
                self.assignments_table.setItem(row, 5, QTableWidgetItem(str(box.get('port_number', '') or '')))
    
    def assign_box_to_screen(self):
        boxes = self.api_request("GET", "/boxes")
        screens = self.api_request("GET", "/screens")
        
        if not boxes or not screens:
            QMessageBox.warning(self, "Error", "Failed to load boxes or screens")
            return
        
        dialog = AssignBoxToScreenDialog(self, boxes, screens)
        if dialog.exec():
            box_id, screen_id = dialog.get_selection()
            if box_id and screen_id:
                result = self.api_request("POST", "/screens/assign", {
                    'box_id': box_id,
                    'screen_id': screen_id
                })
                if result:
                    QMessageBox.information(self, "Success", "Box assigned to screen successfully")
                    self.refresh_assignments()
                    self.refresh_screens()
                    self.refresh_boxes()
                    self.refresh_overview()
                    self.refresh_switch_status()
    
    def unassign_box_from_screen(self):
        selected = self.assignments_table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Selection Error", "Please select an assignment to unassign")
            return
        
        screen_id = int(self.assignments_table.item(selected, 0).text())
        
        reply = QMessageBox.question(
            self, "Confirm Unassign",
            f"Are you sure you want to unassign this box from screen {screen_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = self.api_request("POST", "/screens/unassign", {'screen_id': screen_id})
            if result:
                QMessageBox.information(self, "Success", "Unassigned successfully")
                self.refresh_assignments()
                self.refresh_screens()
                self.refresh_boxes()
                self.refresh_overview()
                self.refresh_switch_status()
    
    # Switch methods
    def refresh_switch_status_background(self):
        """Start background thread to refresh switch status (non-blocking)"""
        if self.switch_status_thread and self.switch_status_thread.isRunning():
            return  # Don't start new thread if one is already running
        
        self.switch_status_thread = SwitchStatusThread(BaseURL.BASE_URL)
        self.switch_status_thread.status_updated.connect(self.update_switch_status_ui)
        self.switch_status_thread.error_occurred.connect(self.handle_switch_error)
        self.switch_status_thread.start()
    
    def update_switch_status_ui(self, info: dict):
        """Update UI with switch status from background thread"""
        self.last_switch_status = info
        connected = info.get('connected', False)
        status_text = "Connected" if connected else "Not Connected"
        self.switch_status_label.setText(f"Status: {status_text}")
        
        # Update ports table
        ports = info.get('ports', [])
        self.switch_ports_table.setRowCount(len(ports))
        for row, port in enumerate(ports):
            self.switch_ports_table.setItem(row, 0, QTableWidgetItem(str(port.get('port', ''))))
            self.switch_ports_table.setItem(row, 1, QTableWidgetItem(str(port.get('status', ''))))
            self.switch_ports_table.setItem(row, 2, QTableWidgetItem(str(port.get('vlan', '') or '')))
    
    def handle_switch_error(self, error: str):
        """Handle switch status error from background thread"""
        if error != "Timeout":
            self.switch_status_label.setText(f"Status: Error ({error})")
        else:
            self.switch_status_label.setText("Status: Not Connected (Timeout)")
        
        # Don't clear the table, keep last known state
    
    def refresh_switch_status_manual(self):
        """Manual refresh of switch status (with user feedback)"""
        self.switch_status_label.setText("Status: Refreshing...")
        QApplication.processEvents()  # Update UI immediately
        
        info = self.api_request("GET", "/switch/info", show_error=True, timeout=10)
        if info:
            self.update_switch_status_ui(info)
        else:
            self.switch_status_label.setText("Status: Not Connected (API Error)")
            self.switch_ports_table.setRowCount(0)
    
    def connect_switch(self, show_message=True):
        result = self.api_request("POST", "/switch/connect", timeout=15)
        if result and show_message:
            QMessageBox.information(self, "Success", "Connected to switch")
            self.refresh_switch_status_manual()
        elif not result and show_message:
            QMessageBox.warning(self, "Error", "Failed to connect to switch")
        else:
            self.refresh_switch_status_manual()
    
    def disconnect_switch(self):
        result = self.api_request("POST", "/switch/disconnect")
        if result:
            QMessageBox.information(self, "Success", "Disconnected from switch")
            self.refresh_switch_status_manual()
    
    def sync_switch(self):
        result = self.api_request("POST", "/switch/sync")
        if result:
            QMessageBox.information(self, "Success", "Switch synchronized with database")
            self.refresh_switch_status_manual()
    
    # COM Port methods
    def refresh_com_port(self):
        """Load current COM port configuration"""
        result = self.api_request("GET", "/config/serial_port", show_error=False)
        if result and 'serial_port' in result:
            self.com_port_input.setText(result['serial_port'])
        else:
            self.com_port_input.setText("")
    
    def save_com_port(self):
        """Save new COM port configuration"""
        com_port = self.com_port_input.text().strip()
        if not com_port:
            QMessageBox.warning(self, "Validation Error", "COM port cannot be empty")
            return
        
        result = self.api_request("PUT", "/config/serial_port", {'serial_port': com_port})
        if result:
            QMessageBox.information(self, "Success", f"COM port updated to {com_port}\nPlease reconnect to the switch.")
            # Refresh switch status to show updated connection state
            self.refresh_switch_status()
    
    # Overview methods
    def refresh_overview(self):
        boxes = self.api_request("GET", "/boxes", show_error=False)
        screens = self.api_request("GET", "/screens", show_error=False)
        switch_info = self.api_request("GET", "/switch/info", show_error=False)
        
        if not boxes or not screens:
            self.overview_text.setText("Failed to load data")
            return
        
        overview = "=== BOX SERVER OVERVIEW ===\n\n"
        
        # Switch status
        if switch_info:
            connected = switch_info.get('connected', False)
            overview += f"Switch Status: {'Connected' if connected else 'Not Connected'}\n"
            overview += f"Total Ports: {len(switch_info.get('ports', []))}\n\n"
        else:
            overview += "Switch Status: Not Connected (Unable to retrieve status)\n\n"
        
        # Boxes summary
        overview += "=== BOXES ===\n"
        overview += f"Total Boxes: {len(boxes)}\n"
        free_boxes = [b for b in boxes if not b.get('user_id')]
        overview += f"Free Boxes: {len(free_boxes)}\n"
        overview += f"Assigned Boxes: {len(boxes) - len(free_boxes)}\n\n"
        
        for box in boxes:
            overview += f"Box {box.get('box_number', box.get('box_id'))} (ID: {box.get('box_id')})\n"
            overview += f"  Port: {box.get('port_number')}\n"
            if box.get('vlan_number'):
                overview += f"  VLAN: {box.get('vlan_number')}\n"
            if box.get('user_id'):
                overview += f"  User ID: {box.get('user_id')}\n"
            else:
                overview += "  Status: Free\n"
            overview += "\n"
        
        # Screens summary
        overview += "\n=== SCREENS ===\n"
        overview += f"Total Screens: {len(screens)}\n"
        free_screens = [s for s in screens if not s.get('box_id')]
        overview += f"Free Screens: {len(free_screens)}\n"
        overview += f"Assigned Screens: {len(screens) - len(free_screens)}\n\n"
        
        for screen in screens:
            overview += f"Screen {screen.get('screen_number', screen.get('screen_id'))} (ID: {screen.get('screen_id')})\n"
            overview += f"  Port: {screen.get('port_number')}\n"
            if screen.get('vlan_number'):
                overview += f"  VLAN: {screen.get('vlan_number')}\n"
            if screen.get('box_id'):
                overview += f"  Assigned to Box ID: {screen.get('box_id')}\n"
            else:
                overview += "  Status: Free\n"
            overview += "\n"
        
        # Assignments
        overview += "\n=== ASSIGNMENTS ===\n"
        assignments = [s for s in screens if s.get('box_id') is not None]
        if assignments:
            boxes_dict = {box.get('box_id'): box for box in boxes}
            for screen in assignments:
                box_id = screen.get('box_id')
                box = boxes_dict.get(box_id, {})
                overview += f"Screen {screen.get('screen_number', screen.get('screen_id'))} (Port: {screen.get('port_number')}) "
                overview += f"<-> Box {box.get('box_number', box_id)} (Port: {box.get('port_number')})\n"
                if box.get('user_id'):
                    overview += f"  User ID: {box.get('user_id')}\n"
                overview += "\n"
        else:
            overview += "No assignments\n"
        
        self.overview_text.setText(overview)
    
    def refresh_all(self):
        """Refresh all tabs - load critical data first, switch status is optional"""
        # Load critical data first (these should always work)
        self.refresh_screens()
        self.refresh_boxes()
        self.refresh_assignments()
        self.refresh_overview()
        
        # Load COM port configuration
        self.refresh_com_port()
        
        # Don't auto-refresh switch on startup - user must enable it or click refresh manually
        # This prevents the UI from being slow on startup


def main():
    app = QApplication(sys.argv)
    window = BackofficeUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

