import sys
import requests
import serial
import serial.tools.list_ports
from datetime import datetime
from functools import partial
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QInputDialog
)
from PySide6.QtCore import QTimer, Qt, QObject, QThread, Signal
from PySide6.QtGui import QFont, QKeyEvent, QPixmap, QPalette

# Color constants
COLOR_RED = "color: red;"
COLOR_BLUE = "color: blue;"
COLOR_GREEN = "color: green;"


class SerialReaderThread(QThread):
    """Thread for reading data from serial port"""
    data_received = Signal(str)
    
    def __init__(self, port, baudrate=9600):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.serial_connection = None
    
    def run(self):
        """Run the serial reader thread"""
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            self.running = True
            buffer = ""
            print(f"Serial port {self.port} opened successfully")
            
            while self.running:
                try:
                    if self.serial_connection and self.serial_connection.is_open:
                        # Read available data
                        waiting = self.serial_connection.in_waiting
                        if waiting > 0:
                            data = self.serial_connection.read(waiting).decode('utf-8', errors='ignore')
                            buffer += data
                            print(f"Received data: {repr(data)}, buffer: {repr(buffer)}")
                            
                            # Process complete lines
                            while '\n' in buffer or '\r' in buffer:
                                if '\n' in buffer:
                                    line, _, buffer = buffer.partition('\n')
                                else:
                                    line, _, buffer = buffer.partition('\r')
                                
                                line = line.strip()
                                print(f"Processing line: {repr(line)}")
                                
                                # Remove control characters (like \x03\x02)
                                line = ''.join(char for char in line if char.isprintable())
                                
                                # Convert letters to digits and keep existing digits
                                result = ""
                                for char in line:
                                    if char.isdigit():
                                        result += char
                                    elif char.isalpha():
                                        # Map A/a=1, B/b=2, ..., Z/z=26
                                        char_upper = char.upper()
                                        digit_value = ord(char_upper) - ord('A') + 1
                                        result += str(digit_value)
                                
                                print(f"After filtering and mapping: {repr(result)}")
                                
                                if result:
                                    print(f"Emitting valid ID: {result}")
                                    self.data_received.emit(result)
                                    buffer = ""  # Clear buffer after valid ID
                                    break
                    else:
                        break
                        
                except Exception as e:
                    print(f"Error reading serial data: {e}")
                    break
                
                self.msleep(50)  # Small delay to prevent CPU overload
                
        except Exception as e:
            print(f"Error opening serial port {self.port}: {e}")
        finally:
            self._cleanup_serial()
    
    def _cleanup_serial(self):
        """Clean up serial connection properly"""
        try:
            if self.serial_connection:
                if self.serial_connection.is_open:
                    self.serial_connection.cancel_read()
                    self.serial_connection.cancel_write()
                    self.serial_connection.close()
                self.serial_connection = None
        except Exception as e:
            print(f"Error during serial cleanup: {e}")
    
    def stop(self):
        """Stop the serial reader thread"""
        print("Stopping serial reader...")
        self.running = False
        self.wait(2000)  # Wait up to 2 seconds for thread to finish


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
    
    def get_screen_status(self, screen_id):
        """Get screen connection status"""
        try:
            response = requests.get(
                f"{self.base_url}/screens/{int(screen_id)}",
                timeout=10
            )
            if response.status_code == 200:
                return response.json(), None
            else:
                return None, "Failed to get screen status"
        except requests.exceptions.RequestException as e:
            return None, f"Connection error: {str(e)}"
    
    def disconnect_screen(self, screen_id):
        """Disconnect screen from box"""
        try:
            response = requests.post(
                f"{self.base_url}/screens/disconnect",
                json={"screen_id": int(screen_id)},
                timeout=10
            )
            if response.status_code == 200:
                return response.json(), None
            else:
                error_data = response.json()
                error_msg = error_data.get('error', 'Failed to disconnect')
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
        
        # Clock timer
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        
        self.is_connected = False
        self.connected_box_number = None
        
        # Serial port reader
        self.serial_reader = None
        self.init_serial_port()
        
        self.init_ui()
        self.update_clock()  # Initial clock update
        self.clock_timer.start(60000)  # Update every minute
        self.reset_ui()
        
        # Start checking screen status
        self.check_screen_status()
        self.status_timer.start(self.status_check_interval)
    
    def init_serial_port(self):
        """Initialize serial port reader if device is connected"""
        try:
            # Look for USB serial devices
            ports = serial.tools.list_ports.comports()
            for port in ports:
                # Check for USB serial devices (ttyUSB on Linux, COM on Windows)
                if 'USB' in port.device or 'ttyUSB' in port.device:
                    print(f"Found USB serial device: {port.device}")
                    self.serial_reader = SerialReaderThread(port.device)
                    self.serial_reader.data_received.connect(self.handle_serial_data)
                    self.serial_reader.start()
                    return
            print("No USB serial device found")
        except Exception as e:
            print(f"Error initializing serial port: {e}")
    
    def handle_serial_data(self, data):
        """Handle data received from serial port"""
        print(f"Received from serial: {data}")
        # Set the user ID and trigger enter
        self.user_id = data
        self.display.setText(self.user_id)
        # Auto-submit after a short delay
        QTimer.singleShot(500, self.on_enter)
    
    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle(f"Screen Assignment - Screen {self.screen_id}")
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Set background image
        try:
            pixmap = QPixmap("background.jpg")
            if not pixmap.isNull():
                # Scale to window size
                scaled_pixmap = pixmap.scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                palette = QPalette()
                palette.setBrush(QPalette.ColorRole.Window, scaled_pixmap)
                central_widget.setAutoFillBackground(True)
                central_widget.setPalette(palette)
        except Exception as e:
            print(f"Could not load background image: {e}")
            # Fallback to gradient
            central_widget.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                              stop:0 #f5f7fa, stop:0.5 #e8eef5, stop:1 #dfe6f0);
                }
            """)
        
        # Clock label (bottom-left corner of screen)
        self.clock_label = QLabel(central_widget)
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        clock_font = QFont()
        clock_font.setPointSize(16)
        clock_font.setBold(True)
        self.clock_label.setFont(clock_font)
        self.clock_label.setStyleSheet("""
            QLabel {
                color: #2d1b69;
                background-color: transparent;
                padding: 10px;
                font-weight: 600;
            }
        """)
        self.clock_label.setGeometry(0, 0, 150, 40)  # Will be repositioned in resizeEvent
        
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
                padding: 5px;
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
                padding: 8px;
                margin: 3px;
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
        self.disconnect_btn.setMinimumHeight(45)
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
                padding: 15px;
                min-height: 80px;
                max-height: 80px;
                color: #2d1b69;
            }
        """)
        main_layout.addWidget(self.display)
        
        # Keypad layout
        keypad_layout = QGridLayout()
        keypad_layout.setSpacing(8)
        
        # Number buttons in 2-row layout for low resolution screens
        buttons = [
            ('1', 0, 0), ('2', 0, 1), ('3', 0, 2), ('4', 0, 3), ('5', 0, 4), ('6', 0, 5),
            ('7', 1, 0), ('8', 1, 1), ('9', 1, 2), ('0', 1, 3), ('Clear', 1, 4), ('Enter', 1, 5),
        ]
        
        button_font = QFont()
        button_font.setPointSize(16)
        button_font.setBold(True)
        
        # Store enter button reference to set as default
        enter_button = None
        
        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setFont(button_font)
            btn.setMinimumHeight(60)
            btn.setMaximumHeight(60)
            btn.setMinimumWidth(90)
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
                btn.setDefault(True)
                enter_button = btn
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
        
        # Set focus to Enter button by default
        if enter_button:
            enter_button.setFocus()
        
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
    
    def resizeEvent(self, event):
        """Handle window resize to rescale background and reposition clock"""
        super().resizeEvent(event)
        try:
            pixmap = QPixmap("background.jpg")
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                palette = QPalette()
                palette.setBrush(QPalette.ColorRole.Window, scaled_pixmap)
                self.centralWidget().setPalette(palette)
        except Exception as e:
            pass
        
        # Reposition clock at bottom-left
        clock_height = 40
        self.clock_label.setGeometry(0, self.height() - clock_height, 150, clock_height)
    
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
                    padding: 8px;
                    margin: 3px;
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
                    padding: 8px;
                    margin: 3px;
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
    
    def update_clock(self):
        """Update the clock display"""
        current_time = datetime.now().strftime("%H:%M")
        self.clock_label.setText(current_time)
    
    def closeEvent(self, event):
        """Clean up serial reader on close"""
        if self.serial_reader and self.serial_reader.isRunning():
            self.serial_reader.stop()
        event.accept()


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

