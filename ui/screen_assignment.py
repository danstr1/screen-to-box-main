import sys
import requests
from functools import partial
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout,
    QPushButton, QLabel
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
                timeout=5
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
        
        self.init_ui()
        self.reset_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle(f"Screen Assignment - Screen {self.screen_id}")
        self.setGeometry(100, 100, 600, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title
        title = QLabel(f"Enter User ID for Screen {self.screen_id}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)
        
        # Display area
        self.display = QLabel("")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        display_font = QFont()
        display_font.setPointSize(24)
        self.display.setFont(display_font)
        self.display.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px solid #333;
                border-radius: 10px;
                padding: 20px;
                min-height: 80px;
                color: #333333;
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
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
            
            if text == 'Clear':
                btn.clicked.connect(self.clear_input)
            elif text == 'Enter':
                btn.clicked.connect(self.on_enter)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2196F3;
                        color: white;
                        border: none;
                        border-radius: 10px;
                    }
                    QPushButton:hover {
                        background-color: #0b7dda;
                    }
                    QPushButton:pressed {
                        background-color: #0a6bc2;
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
        self.status_label.setFont(status_font)
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
            self.clear_input()
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
    
    def on_enter(self):
        """Handle enter button press"""
        if not self.user_id:
            self.status_label.setText("Please enter a user ID")
            self.status_label.setStyleSheet(COLOR_RED)
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
            # Start clear timer to clear status message after 30 seconds
            self.clear_timer.start(self.clear_seconds * 1000)
    
    def clear_display(self):
        """Clear display after timeout"""
        self.clear_timer.stop()
        self.reset_ui()


def main():
    """Main entry point"""
    import sys
    
    # Get screen_id from command line argument
    if len(sys.argv) < 2:
        print("Usage: python screen_assignment.py <screen_id>")
        sys.exit(1)
    
    try:
        screen_id = int(sys.argv[1])
    except ValueError:
        print("Error: screen_id must be a number")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = ScreenAssignmentUI(screen_id)
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

