import sys
import requests
from functools import partial
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGridLayout, QMessageBox
)
from PySide6.QtCore import QTimer, Qt, Signal, QObject
from PySide6.QtGui import QFont, QKeyEvent

# Color constants
COLOR_RED = "color: red;"
COLOR_BLUE = "color: blue;"
COLOR_GREEN = "color: green;"
COLOR_GRAY = "color: gray;"
COLOR_ORANGE = "color: orange;"


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
        
        self.init_ui()
        self.reset_to_keypad()
    
    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("Box Management System")
        self.setGeometry(100, 100, 600, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("""
            QWidget {
                background-color: #26007F;
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title
        title = QLabel("Enter User ID")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("""
            QLabel {
                color: #C1E7F5;
                background-color: transparent;
                padding: 10px;
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
                background-color: #1A0055;
                border: 3px solid #C1E7F5;
                border-radius: 15px;
                padding: 20px;
                min-height: 80px;
                color: #C1E7F5;
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
            btn.setMinimumHeight(60)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #C1E7F5;
                    color: #26007F;
                    border: none;
                    border-radius: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #A8D5E8;
                    transform: scale(1.02);
                }
                QPushButton:pressed {
                    background-color: #8FC3DB;
                }
            """)
            
            if text == 'Clear':
                btn.clicked.connect(self.clear_input)
            elif text == 'Enter':
                btn.clicked.connect(self.on_enter)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #35063E;
                        color: #C1E7F5;
                        border: 2px solid #C1E7F5;
                        border-radius: 12px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #4A0856;
                        border: 2px solid #FFFFFF;
                    }
                    QPushButton:pressed {
                        background-color: #250430;
                    }
                """)
            else:
                btn.clicked.connect(partial(self.add_digit, text))
            
            keypad_layout.addWidget(btn, row, col)
        
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
        self.remove_btn.setMinimumHeight(50)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #E63946;
                color: white;
                border: 2px solid #C1E7F5;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #D62828;
                transform: scale(1.02);
            }
            QPushButton:pressed {
                background-color: #BA181B;
            }
        """)
        self.remove_btn.clicked.connect(self.on_remove_assignment)
        self.action_layout.addWidget(self.remove_btn)
        
        self.assign_new_btn = QPushButton("Assign New Box")
        self.assign_new_btn.setFont(action_button_font)
        self.assign_new_btn.setMinimumHeight(50)
        self.assign_new_btn.setStyleSheet("""
            QPushButton {
                background-color: #F77F00;
                color: white;
                border: 2px solid #C1E7F5;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #D97000;
                transform: scale(1.02);
            }
            QPushButton:pressed {
                background-color: #BB6100;
            }
        """)
        self.assign_new_btn.clicked.connect(self.on_assign_new)
        self.action_layout.addWidget(self.assign_new_btn)
        
        self.do_nothing_btn = QPushButton("Do Nothing")
        self.do_nothing_btn.setFont(action_button_font)
        self.do_nothing_btn.setMinimumHeight(50)
        self.do_nothing_btn.setStyleSheet("""
            QPushButton {
                background-color: #6C757D;
                color: white;
                border: 2px solid #C1E7F5;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #5A6268;
                transform: scale(1.02);
            }
            QPushButton:pressed {
                background-color: #4E555B;
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


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = BoxUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

