import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox, QScrollArea, QFrame, QComboBox, QHBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyATEMMax import ATEMMax
from flask import Flask

# Define the signals class for thread-safe communication
class Signals(QObject):
    connection_status = pyqtSignal(str)
    error_message = pyqtSignal(str, str)
    scan_results = pyqtSignal(list)  # New signal for scan results

class ATEMController(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ATEM Controller")
        self.connected = False
        self.signals = Signals()

        # Initialize the switcher
        self.switcher = ATEMMax()

        # Setup GUI elements
        self.init_ui()

        # Connect signals
        self.signals.connection_status.connect(self.update_connection_status)
        self.signals.error_message.connect(self.show_error_message)
        self.signals.scan_results.connect(self.handle_scan_results)  # Connect scan_results signal

        # Start scanning for ATEMs on startup
        QTimer.singleShot(0, self.scan_for_atems)  # Start scan after UI is shown

    def init_ui(self):
        # Create main layout
        layout = QVBoxLayout()

        # IP Address Label and Entry
        self.ip_label = QLabel("ATEM IP Address:")
        self.ip_entry = QLineEdit()
        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_entry)

        # Connect Button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_button_action)
        layout.addWidget(self.connect_button)

        # Connection Status
        self.connection_status_label = QLabel("Not Connected")
        # Initial style for the status label
        self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.connection_status_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Scan for ATEMs Label
        self.scan_label = QLabel("Available ATEMs:")
        layout.addWidget(self.scan_label)

        # Dropdown for ATEMs
        self.atem_dropdown = QComboBox()
        self.atem_dropdown.currentIndexChanged.connect(self.on_atem_selection_changed)
        layout.addWidget(self.atem_dropdown)

        # Horizontal layout for Scan and Use buttons
        h_layout_buttons = QHBoxLayout()
        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan_for_atems)
        h_layout_buttons.addWidget(self.scan_button)

        self.use_button = QPushButton("Use")
        self.use_button.setEnabled(False)
        self.use_button.clicked.connect(self.use_selected_atem)
        h_layout_buttons.addWidget(self.use_button)

        layout.addLayout(h_layout_buttons)

        # Scene List Label
        self.scene_label = QLabel("Available Scenes:")
        layout.addWidget(self.scene_label)

        # Scene List (Scroll Area)
        self.scene_list_widget = QScrollArea()
        self.scene_list_widget.setWidgetResizable(True)
        scene_list_content = QWidget()
        scene_list_layout = QVBoxLayout(scene_list_content)

        for scene_id, scene_info in scenes.items():
            scene_text = f"{scene_id} | {scene_info['name']}"
            label = QLabel(scene_text)
            scene_list_layout.addWidget(label)

        self.scene_list_widget.setWidget(scene_list_content)
        layout.addWidget(self.scene_list_widget)

        self.setLayout(layout)

    def connect_button_action(self):
        ip = self.ip_entry.text().strip()
        if ip:
            if self.connected:
                self.switcher.disconnect()
                self.connected = False
                self.connection_status_label.setText("Not Connected")

            # Start connection in a separate thread
            threading.Thread(target=self.connect_to_switcher, args=(ip,), daemon=True).start()
        else:
            QMessageBox.warning(self, "Input Required", "Please enter an IP address.")

    def connect_to_switcher(self, ip):
        print(f"[{time.ctime()}] Connecting to ATEM Switcher at {ip}...")
        self.switcher.connect(ip)

        if not self.switcher.waitForConnection(timeout=5000):
            print(f"[{time.ctime()}] ERROR: Cannot connect to ATEM Switcher at {ip}", file=sys.stderr)
            self.connected = False
            self.signals.connection_status.emit("Not Connected")
            self.signals.error_message.emit("Connection Error", f"Cannot connect to ATEM Switcher at {ip}")
        else:
            print(f"[{time.ctime()}] Connected to ATEM Switcher.")
            self.connected = True
            self.signals.connection_status.emit("Connected")

            # Start switcher's event loop
            threading.Thread(target=self.switcher._runLoop, daemon=True).start()

    def update_connection_status(self, status):
        self.connection_status_label.setText(status)
        if status == "Connected":
            # Set text green and bold
            self.connection_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            # Set text red and bold
            self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")

    def show_error_message(self, title, message):
        QMessageBox.critical(self, title, message)

    def scan_for_atems(self):
        # Disable the Scan button to prevent multiple clicks
        self.scan_button.setEnabled(False)
        print(f"[{time.ctime()}] Scanning network range 192.168.50.* for ATEM switchers")

        def scan():
            results = []
            lock = threading.Lock()

            def scan_ip(ip):
                switcher = ATEMMax()  # Create a new instance for each thread
                try:
                    switcher.ping(ip)
                    if switcher.waitForConnection():
                        print(f"[{time.ctime()}] ATEM switcher found at {ip}")
                        with lock:
                            results.append(ip)
                finally:
                    switcher.disconnect()

            with ThreadPoolExecutor(max_workers=20) as executor:
                ips = [f"192.168.50.{i}" for i in range(1, 255)]
                executor.map(scan_ip, ips)

            # Emit the results back to the main thread
            self.signals.scan_results.emit(results)

        # Start the scan in a separate thread
        threading.Thread(target=scan, daemon=True).start()

    def handle_scan_results(self, results):
        self.atem_dropdown.clear()
        self.atem_dropdown.addItems(results)
        print(f"[{time.ctime()}] FINISHED: {len(results)} ATEM switchers found.")

        # Re-enable the Scan button
        self.scan_button.setEnabled(True)

        # Enable or disable the Use button based on results
        if len(results) == 0:
            self.use_button.setEnabled(False)
        else:
            # Set the first item as selected and enable Use button
            self.atem_dropdown.setCurrentIndex(0)
            self.use_button.setEnabled(True)

        # Check if we found exactly one ATEM, connect automatically
        if len(results) == 1:
            # Update the IP entry with the found IP
            self.ip_entry.setText(results[0])
            # Start connection in a separate thread
            threading.Thread(target=self.connect_to_switcher, args=(results[0],), daemon=True).start()

    def on_atem_selection_changed(self, index):
        if self.atem_dropdown.count() > 0 and index >= 0:
            self.use_button.setEnabled(True)
        else:
            self.use_button.setEnabled(False)

    def use_selected_atem(self):
        selected_ip = self.atem_dropdown.currentText()
        if selected_ip:
            self.ip_entry.setText(selected_ip)
            QMessageBox.information(self, "IP Selected", f"IP {selected_ip} copied to the IP field.")
        else:
            QMessageBox.warning(self, "No Selection", "Please select an ATEM from the dropdown.")

def set_key1(on=bool):
    atem_controller.switcher.setKeyerOnAirEnabled(0, 0, on)

def turn_key1(on=bool):

    isonair = atem_controller.switcher.keyer[0][0].onAir.enabled

    print(f"is On Air State: {isonair}")
    print(f"Should be on: {on}")
    # Check if the current state is different from the desired state
    if (isonair != on):
        print(f"Switching Key 1")
        set_key1(on)
    else:
        print("No change needed. The downstream key 1 is already in the desired state.")

# Define your scene functions
def switch_to_speaker():
    if atem_controller.connected:
        turn_key1(on=False)
        atem_controller.switcher.setPreviewInputVideoSource(0, 6)
        atem_controller.switcher.execAutoME(0)
        print("Switched to Speaker")
    else:
        print("Not connected to ATEM Switcher.")

def switch_to_slides_and_key1():
    if atem_controller.connected:
        turn_key1(on=True)
        atem_controller.switcher.setPreviewInputVideoSource(0, 1)
        atem_controller.switcher.execAutoME(0)
        print("Switched Slides with Speaker")
    else:
        print("Not connected to ATEM Switcher.")

def switch_to_music():
    if atem_controller.connected:
        turn_key1(on=False)
        atem_controller.switcher.setPreviewInputVideoSource(0, 4)
        atem_controller.switcher.execAutoME(0)
        print("Switched to Music")
    else:
        print("Not connected to ATEM Switcher.")

def switch_to_slides():
    if atem_controller.connected:
        turn_key1(on=False)
        atem_controller.switcher.setPreviewInputVideoSource(0, 1)
        atem_controller.switcher.execAutoME(0)
        print("Switched to Slides")
    else:
        print("Not connected to ATEM Switcher.")

def toggle_key_on():
    if atem_controller.connected:
        set_key1(True)
    else:
        print("Not connected to ATEM Switcher.")

def toggle_key_off():
    if atem_controller.connected:
        set_key1(False)
    else:
        print("Not connected to ATEM Switcher.")

# A dictionary of scene IDs to functions and names
scenes = {
    0: {'name': 'Speaker', 'function': switch_to_speaker},
    1: {'name': 'Music', 'function': switch_to_music},
    2: {'name': 'Slides', 'function': switch_to_slides},
    3: {'name': 'Slides and Speaker', 'function': switch_to_slides_and_key1},
    4: {'name': 'Toggle Key On', 'function': toggle_key_on},
    5: {'name': 'Toggle Key Off', 'function': toggle_key_off},
    # Add more scenes as needed
}

# Setup Flask web interface
app = Flask(__name__)

@app.route('/scene/<int:scene_id>')
def run_scene(scene_id):
    if scene_id in scenes:
        if atem_controller.connected:
            scenes[scene_id]['function']()
            return f"Executed scene {scene_id}: {scenes[scene_id]['name']}"
        else:
            return "Not connected to ATEM switcher", 500
    else:
        return "Scene not found", 404

def run_flask():
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Create the Qt Application
    app_qt = QApplication(sys.argv)
    atem_controller = ATEMController()
    atem_controller.show()

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run the main Qt loop
    sys.exit(app_qt.exec_())
