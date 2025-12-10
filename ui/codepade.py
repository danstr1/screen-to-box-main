import sys
import requests
import serial
import serial.tools.list_ports
from datetime import datetime
from functools import partial
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGridLayout, QMessageBox
)
from PySide6.QtCore import QTimer, Qt, Signal, QObject, QThread
from PySide6.QtGui import QFont, QKeyEvent, QPixmap, QPalette

# Color constants
COLOR_RED = "color: red;"
COLOR_BLUE = "color: blue;"
COLOR_GREEN = "color: green;"
COLOR_GRAY = "color: gray;"
COLOR_ORANGE = "color: orange;"


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


class BoxClient(QObject):
    """Client for communicating with the box server"""
    
    def __init__(self, base_url="http://localhost:5000"):
        super().__init__()
        self.base_url = base_url
    
    def check_user_box(self, user_id):
        """Check if user has a box assigned"""
        try:
            response = requests.get(f"{self.base_url}/boxes/user/{str(user_id)}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error checking user box: {e}")
            return None
    
    def assign_box(self, user_id):
        """Assign a box to user"""
        try:
            response = requests.post(
                f"{self.base_url}/boxes/assign",
                json={"user_id": str(user_id)}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error assigning box: {e}")
            return None
    
    def unassign_box(self, user_id):
        """Unassign box from user"""
        try:
            response = requests.post(
                f"{self.base_url}/boxes/unassign",
                json={"user_id": str(user_id)}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error unassigning box: {e}")
            return False


class BoxUI(QMainWindow):
    """Main UI window for box management"""
    
    def __init__(self):
        super().__init__()
        self.client = BoxClient()
        self.user_id = ""
        self.current_box = None
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self.on_timeout)
        self.timeout_seconds = 30
        
        # Clock timer
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        
        # Serial port reader
        self.serial_reader = None
        self.init_serial_port()
        
        self.init_ui()
        self.update_clock()  # Initial clock update
        self.clock_timer.start(60000)  # Update every minute
        self.reset_to_keypad()
    
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
        self.setWindowTitle("Box Management System")
        
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
        title = QLabel("Enter User ID")
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
        
        # Action buttons container (initially hidden)
        self.action_container = QWidget()
        self.action_layout = QHBoxLayout()
        self.action_container.setLayout(self.action_layout)
        main_layout.addWidget(self.action_container)
        self.action_container.hide()
        
        # Action buttons
        action_button_font = QFont()
        action_button_font.setPointSize(14)
        action_button_font.setBold(True)
        
        self.remove_btn = QPushButton("Remove Assignment")
        self.remove_btn.setFont(action_button_font)
        self.remove_btn.setMinimumHeight(45)
        self.remove_btn.setStyleSheet("""
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
        self.remove_btn.clicked.connect(self.on_remove_assignment)
        self.action_layout.addWidget(self.remove_btn)
        
        self.assign_new_btn = QPushButton("Assign New Box")
        self.assign_new_btn.setFont(action_button_font)
        self.assign_new_btn.setMinimumHeight(45)
        self.assign_new_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #f57c00, stop:1 #e65100);
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #fb8c00, stop:1 #f57c00);
                border: 2px solid #ffb74d;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #bf360c, stop:1 #9c2700);
            }
        """)
        self.assign_new_btn.clicked.connect(self.on_assign_new)
        self.action_layout.addWidget(self.assign_new_btn)
        
        self.do_nothing_btn = QPushButton("Do Nothing")
        self.do_nothing_btn.setFont(action_button_font)
        self.do_nothing_btn.setMinimumHeight(45)
        self.do_nothing_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #546e7a, stop:1 #37474f);
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #607d8b, stop:1 #546e7a);
                border: 2px solid #90a4ae;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #263238, stop:1 #1a2328);
            }
        """)
        self.do_nothing_btn.clicked.connect(self.on_do_nothing)
        self.action_layout.addWidget(self.do_nothing_btn)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(12)
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
    
    def clear_input(self):
        """Clear the user ID input"""
        self.user_id = ""
        self.display.setText("")
        self.status_label.setText("")
        self.reset_to_keypad()
    
    def reset_to_keypad(self):
        """Reset UI to keypad state"""
        self.action_container.hide()
        self.current_box = None
        self.user_id = ""
        self.display.setText("")
        self.status_label.setText("")
        self.timeout_timer.stop()
    
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
        
        # Validate user_id is numeric (but keep as string)
        if not self.user_id.isdigit():
            self.status_label.setText("Invalid user ID")
            self.status_label.setStyleSheet(COLOR_RED)
            return
        
        # Check if user has a box (user_id is already a string)
        result = self.client.check_user_box(self.user_id)
        
        if result and result.get('has_box'):
            # User has a box - show action options
            self.current_box = result
            self.show_action_options(result)
        else:
            # User doesn't have a box - assign one
            self.assign_box_to_user(self.user_id)
    
    def show_action_options(self, box_info):
        """Show action options when user has a box"""
        box_number = box_info.get('box_number', 'N/A')
        self.display.setText(f"User ID: {self.user_id}\nCurrent Box: {box_number}")
        self.status_label.setText(f"You are assigned to Box {box_number}")
        self.status_label.setStyleSheet(COLOR_BLUE)
        self.action_container.show()
        
        # Start timeout timer
        self.start_timeout()
    
    def assign_box_to_user(self, user_id):
        """Assign a box to a user"""
        self.status_label.setText("Assigning box...")
        self.status_label.setStyleSheet(COLOR_BLUE)
        
        # Ensure user_id is a string
        result = self.client.assign_box(str(user_id))
        
        if result:
            box_number = result.get('box_number', 'N/A')
            self.display.setText(f"User ID: {self.user_id}\nAssigned Box: {box_number}")
            self.status_label.setText(f"Box {box_number} assigned successfully!")
            self.status_label.setStyleSheet(COLOR_GREEN)
            self.current_box = result
            
            # Start timeout timer
            self.start_timeout()
        else:
            self.status_label.setText("Error: No free boxes available")
            self.status_label.setStyleSheet(COLOR_RED)
            QTimer.singleShot(2000, self.reset_to_keypad)
    
    def on_remove_assignment(self):
        """Handle remove assignment button"""
        if not self.user_id:
            return
        
        # user_id is already a string
        success = self.client.unassign_box(self.user_id)
        
        if success:
            self.display.setText(f"User ID: {self.user_id}\nAssignment Removed")
            self.status_label.setText("Assignment removed successfully!")
            self.status_label.setStyleSheet(COLOR_GREEN)
            self.current_box = None
            self.start_timeout()
        else:
            self.status_label.setText("Error removing assignment")
            self.status_label.setStyleSheet(COLOR_RED)
    
    def on_assign_new(self):
        """Handle assign new box button"""
        if not self.user_id:
            return
        
        # user_id is already a string
        self.assign_box_to_user(self.user_id)
    
    def on_do_nothing(self):
        """Handle do nothing button"""
        if self.current_box:
            box_number = self.current_box.get('box_number', 'N/A')
            self.display.setText(f"User ID: {self.user_id}\nBox: {box_number}\nNo changes made")
            self.status_label.setText("No changes made")
            self.status_label.setStyleSheet(COLOR_GRAY)
            self.start_timeout()
    
    def start_timeout(self):
        """Start the 30-second timeout timer"""
        self.timeout_timer.stop()
        self.timeout_timer.start(self.timeout_seconds * 1000)
    
    def on_timeout(self):
        """Handle timeout"""
        self.timeout_timer.stop()
        if self.current_box:
            box_number = self.current_box.get('box_number', 'N/A')
            self.display.setText(f"User ID: {self.user_id}\nBox: {box_number}\n(Timeout)")
            self.status_label.setText("Session timed out after 30 seconds")
            self.status_label.setStyleSheet(COLOR_ORANGE)
        
        # Reset after showing timeout message
        QTimer.singleShot(2000, self.reset_to_keypad)
    
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
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = BoxUI()
    window.showFullScreen()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

