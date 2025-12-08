import sys
import requests
from functools import partial
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QInputDialog
)
from PySide6.QtCore import QTimer, Qt, QObject
from PySide6.QtGui import QFont, QKeyEvent

# Color constants
COLOR_RED = "color: red;"
COLOR_BLUE = "color: blue;"
COLOR_GREEN = "color: green;"


class ScreenAssignmentClient(QObject):
    """Client for communicating with the box server"""
    
    def __init__(self, base_url="http://localhost:5000"):
        super().__init__()
        self.base_url = base_url
    
    def assign_user_to_screen(self, user_id, screen_id):
        """Assign a user to a screen"""
        try:
            response = requests.post(
                f"{self.base_url}/screens/assign_user",
                json={"user_id": str(user_id), "screen_id": int(screen_id)},
                timeout=35
            )
            if response.status_code == 200:
                return response.json(), None
            else:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
                return None, error_msg
        except requests.exceptions.RequestException as e:
            return None, f"Connection error: {str(e)}"


class ScreenAssignmentUI(QMainWindow):
    """UI for assigning users to screens"""
    
    def __init__(self, screen_id):
        super().__init__()
        self.client = ScreenAssignmentClient()
        self.screen_id = screen_id
        self.user_id = ""
        self.clear_timer = QTimer()
        self.clear_timer.timeout.connect(self.clear_display)
        self.clear_seconds = 30
        
        # Status check timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_screen_status)
        self.status_check_interval = 10000  # Check every 10 seconds
        
        self.is_connected = False
        self.connected_box_number = None
        
        self.init_ui()
        self.reset_ui()
        
        # Start checking screen status
        self.check_screen_status()
        self.status_timer.start(self.status_check_interval)
    
    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle(f"Screen Assignment - Screen {self.screen_id}")
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #f5f7fa, stop:0.5 #e8eef5, stop:1 #dfe6f0);
            }
        """)
        
        # Main layout with horizontal centering
        outer_layout = QHBoxLayout()
        central_widget.setLayout(outer_layout)
        
        # Add stretches to center content
        outer_layout.addStretch()
        
        # Content container with max width
        content_widget = QWidget()
        content_widget.setMaximumWidth(800)
        content_widget.setStyleSheet("background: transparent;")
        outer_layout.addWidget(content_widget)
        
        outer_layout.addStretch()
        
        # Main layout
        main_layout = QVBoxLayout()
        content_widget.setLayout(main_layout)
        main_layout.addStretch()
        
        # Title
        title = QLabel(f"Enter User ID for Screen {self.screen_id}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("""
            QLabel {
                color: #2d1b69;
                background-color: transparent;
                padding: 10px;
                font-weight: 600;
            }
        """)
        main_layout.addWidget(title)
        
        # Connection status label
        self.connection_status_label = QLabel("Checking connection...")
        self.connection_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(14)
        status_font.setBold(True)
        self.connection_status_label.setFont(status_font)
        self.connection_status_label.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 3px solid #2d1b69;
                border-radius: 10px;
                padding: 10px;
                margin: 5px;
                color: #2d1b69;
            }
        """)
        main_layout.addWidget(self.connection_status_label)
        
        # Disconnect button (initially hidden)
        self.disconnect_btn = QPushButton("Disconnect")
        disconnect_font = QFont()
        disconnect_font.setPointSize(14)
        disconnect_font.setBold(True)
        self.disconnect_btn.setFont(disconnect_font)
        self.disconnect_btn.setMinimumHeight(50)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #e53935, stop:1 #c62828);
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #ef5350, stop:1 #e53935);
                border: 2px solid #ef9a9a;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #b71c1c, stop:1 #8e0000);
            }
        """)
        self.disconnect_btn.clicked.connect(self.on_disconnect)
        self.disconnect_btn.hide()
        main_layout.addWidget(self.disconnect_btn)
        
        # Display area
        self.display = QLabel("")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        display_font = QFont()
        display_font.setPointSize(24)
        self.display.setFont(display_font)
        self.display.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 3px solid #2d1b69;
                border-radius: 15px;
                padding: 20px;
                min-height: 100px;
                max-height: 100px;
                color: #2d1b69;
            }
        """)
        main_layout.addWidget(self.display)
        
        # Keypad layout
        keypad_layout = QGridLayout()
        keypad_layout.setSpacing(10)
        
        # Number buttons (1-9)
        buttons = [
            ('1', 0, 0), ('2', 0, 1), ('3', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('7', 2, 0), ('8', 2, 1), ('9', 2, 2),
            ('Clear', 3, 0), ('0', 3, 1), ('Enter', 3, 2),
        ]
        
        button_font = QFont()
        button_font.setPointSize(16)
        button_font.setBold(True)
        
        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setFont(button_font)
            btn.setMinimumHeight(70)
            btn.setMaximumHeight(70)
            btn.setMinimumWidth(100)
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                              stop:0 #4a2c7e, stop:1 #2d1b69);
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: bold;
                    padding: 5px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                              stop:0 #5e3a9c, stop:1 #4a2c7e);
                    border: 2px solid #7c5cba;
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                              stop:0 #1f0f4d, stop:1 #160a36);
                }
            """)
            
            if text == 'Clear':
                btn.clicked.connect(self.clear_input)
            elif text == 'Enter':
                btn.clicked.connect(self.on_enter)
                btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                  stop:0 #00c853, stop:1 #00a844);
                        color: white;
                        border: none;
                        border-radius: 12px;
                        font-weight: bold;
                        padding: 5px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                  stop:0 #00e676, stop:1 #00c853);
                        border: 2px solid #69f0ae;
                    }
                    QPushButton:pressed {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                  stop:0 #00963f, stop:1 #007d34);
                    }
                """)
            else:
                btn.clicked.connect(partial(self.add_digit, text))
            
            keypad_layout.addWidget(btn, row, col)
        
        main_layout.addLayout(keypad_layout)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(14)
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                padding: 10px;
            }
        """)
        main_layout.addWidget(self.status_label)
        main_layout.addStretch()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard input - accept number keys"""
        key = event.key()
        
        # Handle number keys (0-9)
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            digit = str(key - Qt.Key.Key_0)
            self.add_digit(digit)
            return
        
        # Handle Enter/Return key
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.on_enter()
            return
        
        # Handle Backspace/Delete
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if self.user_id:
                self.user_id = self.user_id[:-1]
                self.display.setText(self.user_id)
            return
        
        # Call parent handler for other keys
        super().keyPressEvent(event)
    
    def add_digit(self, digit):
        """Add a digit to the user ID input"""
        if len(self.user_id) < 20:  # Limit input length
            self.user_id += digit
            self.display.setText(self.user_id)
            self.status_label.setText("")
            self.status_label.setStyleSheet("")
            # Stop any existing timer when user types
            self.clear_timer.stop()
    
    def clear_input(self):
        """Clear the user ID input"""
        self.user_id = ""
        self.display.setText("")
        self.status_label.setText("")
        self.status_label.setStyleSheet("")
        self.clear_timer.stop()
    
    def reset_ui(self):
        """Reset UI to initial state"""
        self.user_id = ""
        self.display.setText("")
        self.status_label.setText("")
        self.status_label.setStyleSheet("")
        self.clear_timer.stop()
        self.update_connection_status()
    
    def check_screen_status(self):
        """Check if screen is connected to a box"""
        screen_data, error = self.client.get_screen_status(self.screen_id)
        
        if error:
            self.is_connected = False
            self.connected_box_number = None
        elif screen_data:
            box_id = screen_data.get('box_id')
            self.is_connected = box_id is not None
            self.connected_box_number = screen_data.get('box_number') if self.is_connected else None
        
        self.update_connection_status()
    
    def update_connection_status(self):
        """Update the connection status label and disconnect button visibility"""
        if self.is_connected:
            box_text = f"Box {self.connected_box_number}" if self.connected_box_number else "a box"
            self.connection_status_label.setText(f"✓ Connected to {box_text}")
            self.connection_status_label.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                              stop:0 #00e676, stop:1 #00c853);
                    color: white;
                    border: 3px solid #69f0ae;
                    border-radius: 10px;
                    padding: 10px;
                    margin: 5px;
                    font-weight: bold;
                }
            """)
            self.disconnect_btn.show()
        else:
            self.connection_status_label.setText("○ Not Connected")
            self.connection_status_label.setStyleSheet("""
                QLabel {
                    background-color: white;
                    color: #546e7a;
                    border: 3px solid #90a4ae;
                    border-radius: 10px;
                    padding: 10px;
                    margin: 5px;
                }
            """)
            self.disconnect_btn.hide()
    
    def on_disconnect(self):
        """Handle disconnect button click"""
        if not self.is_connected:
            return
        
        # Show confirmation in status label
        box_text = f"Box {self.connected_box_number}" if self.connected_box_number else "box"
        self.status_label.setText(f"Disconnecting from {box_text}...")
        self.status_label.setStyleSheet(COLOR_BLUE)
        
        # Make API call to disconnect
        result, error = self.client.disconnect_screen(self.screen_id)
        
        if error:
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet(COLOR_RED)
            # Start clear timer
            self.clear_timer.start(self.clear_seconds * 1000)
        else:
            self.status_label.setText("Disconnected successfully")
            self.status_label.setStyleSheet(COLOR_GREEN)
            # Update connection status immediately
            self.is_connected = False
            self.connected_box_number = None
            self.update_connection_status()
            # Start clear timer
            self.clear_timer.start(self.clear_seconds * 1000)
    
    def on_enter(self):
        """Handle enter button press"""
        if not self.user_id:
            self.status_label.setText("Please enter a user ID")
            self.status_label.setStyleSheet(COLOR_RED)
            return
        
        # Check for exit code
        if self.user_id == "99999":
            QApplication.quit()
            return
        
        # Validate user_id is numeric
        if not self.user_id.isdigit():
            self.status_label.setText("Invalid user ID - numbers only")
            self.status_label.setStyleSheet(COLOR_RED)
            return
        
        # Disable input during request
        self.status_label.setText("Assigning user to screen...")
        self.status_label.setStyleSheet(COLOR_BLUE)
        
        # Make API call
        result, error = self.client.assign_user_to_screen(self.user_id, self.screen_id)
        
        if error:
            # Show error message
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet(COLOR_RED)
            # Start clear timer
            self.clear_timer.start(self.clear_seconds * 1000)
        else:
            # Show success message
            screen_number = result.get('screen_number', self.screen_id)
            success_msg = f"ID {self.user_id} is successfully assigned to screen {screen_number}, your phone will be shown up in few seconds"
            self.status_label.setText(success_msg)
            self.status_label.setStyleSheet(COLOR_GREEN)
            # Clear the user input display
            self.display.setText("")
            self.user_id = ""
            # Update connection status immediately
            self.check_screen_status()
            # Start clear timer to clear status message after 30 seconds
            self.clear_timer.start(self.clear_seconds * 1000)
    
    def clear_display(self):
        """Clear display after timeout"""
        self.clear_timer.stop()
        self.reset_ui()


def main():
    """Main entry point"""
    import sys
    
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    screen_id = None
    
    # Get screen_id from command line argument if provided
    if len(sys.argv) >= 2:
        try:
            screen_id = int(sys.argv[1])
        except ValueError:
            print("Error: screen_id must be a number")
    
    # If no screen_id provided, ask user to enter it
    if screen_id is None:
        screen_id, ok = QInputDialog.getInt(
            None,
            "Screen ID Required",
            "Please enter the Screen ID:",
            1,
            1,
            9999
        )
        
        if not ok:
            # User cancelled
            print("Screen ID input cancelled")
            sys.exit(0)
    
    window = ScreenAssignmentUI(screen_id)
    window.showFullScreen()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

