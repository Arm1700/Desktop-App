import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QDialog, QComboBox, QHBoxLayout, QListWidget
from PyQt6.QtCore import QTimer, QTime
import psutil
import sqlite3
import os
os.environ["DISPLAY"] = ":0"

class SystemMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Monitor")
        self.setGeometry(100, 100, 400, 400)

        self.conn = sqlite3.connect("system_data.db")
        self.create_table()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.cpu_label = QLabel("CPU: ")
        self.ram_label = QLabel("RAM: ")
        self.swap_label = QLabel("Swap: ")

        self.start_button = QPushButton("Start Recording")
        self.stop_button = QPushButton("Stop Recording")
        self.history_button = QPushButton("View History")

        self.stop_button.setEnabled(False)

        layout.addWidget(self.cpu_label)
        layout.addWidget(self.ram_label)
        layout.addWidget(self.swap_label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.history_button)

        self.unit_selector = QComboBox()
        self.unit_selector.addItems(["B", "KB", "MB", "GB", "TB"])
        self.unit_selector.setCurrentText("GB")
        self.unit_selector.currentTextChanged.connect(self.update_units)
        layout.addWidget(self.unit_selector)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)

        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_recording_time)
        self.recording_time = QTime(0, 0)

        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        self.history_button.clicked.connect(self.view_history)

        self.is_recording = False
        self.session_id = None

    def update_stats(self):
        cpu_percent = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()

        unit = self.unit_selector.currentText()

        self.cpu_label.setText(f"CPU: {cpu_percent}%")
        self.ram_label.setText(f"RAM: {self.format_bytes(ram.free, unit)} (Total: {self.format_bytes(ram.total, unit)})")
        self.swap_label.setText(f"Swap: {self.format_bytes(swap.free, unit)} (Total: {self.format_bytes(swap.total, unit)})")

        if self.is_recording:
            self.record_to_db(cpu_percent, ram.free, ram.total, swap.free, swap.total)

    def update_units(self):
        self.update_stats()
    
    def format_bytes(self, bytes, unit='GB'):
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        if unit not in units:
            unit = 'GB'
        idx = units.index(unit)
        for _ in range(idx):
            bytes /= 1024
        return f"{max(bytes, 0.01):.2f} {unit}"

    def start_recording(self):
        self.is_recording = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.recording_time.setHMS(0, 0, 0)
        self.recording_timer.start(1000)

        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO sessions (start_time) VALUES (datetime('now'))")
        self.conn.commit()
        self.session_id = cursor.lastrowid

    def stop_recording(self):
        self.is_recording = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.recording_timer.stop()

        cursor = self.conn.cursor()
        cursor.execute("UPDATE sessions SET end_time = datetime('now') WHERE id = ?", (self.session_id,))
        self.conn.commit()

    def update_recording_time(self):
        self.recording_time = self.recording_time.addSecs(1)
        self.stop_button.setText(f"Stop Recording ({self.recording_time.toString('hh:mm:ss')})")


    def record_to_db(self, cpu, ram_free, ram_total, swap_free, swap_total):
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO system_data (session_id, timestamp, cpu, ram_free, ram_total, swap_free, swap_total) 
            VALUES (?, datetime('now'), ?, ?, ?, ?, ?)""",
            (self.session_id, cpu, ram_free, ram_total, swap_free, swap_total)
        )
        self.conn.commit()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT,
                end_time TEXT
            )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS system_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TEXT,
                cpu REAL,
                ram_free REAL,
                ram_total REAL,
                swap_free REAL,
                swap_total REAL,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )"""
        )
        self.conn.commit()

    def view_history(self):
        history_window = HistoryWindow(self.conn)
        history_window.exec()


class HistoryWindow(QDialog):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("Recording History")
        self.setGeometry(150, 150, 800, 600)

        layout = QVBoxLayout(self)

        self.session_list = QListWidget()
        self.session_list.itemClicked.connect(self.load_session_data)
        layout.addWidget(self.session_list)

        self.unit_selector = QComboBox()
        self.unit_selector.addItems(["B", "KB", "MB", "GB", "TB"])
        self.unit_selector.setCurrentText("GB")
        self.unit_selector.currentTextChanged.connect(self.update_units)
        layout.addWidget(self.unit_selector)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Timestamp", "CPU (%)", "RAM Free", "RAM Total", "Swap Free", "Swap Total"])
        layout.addWidget(self.table)

        self.load_sessions()

    def load_sessions(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, start_time, end_time FROM sessions")
        rows = cursor.fetchall()
        for row in rows:
            session_text = f"Session {row[0]}: {row[1]} - {row[2] or 'Ongoing'}"
            self.session_list.addItem(session_text)

    def load_session_data(self, item):
        session_id = int(item.text().split()[1].strip(':'))
        cursor = self.conn.cursor()
        cursor.execute("SELECT timestamp, cpu, ram_free, ram_total, swap_free, swap_total FROM system_data WHERE session_id = ?", (session_id,))
        rows = cursor.fetchall()

        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, col_data in enumerate(row_data):
                if col_idx > 1:
                    col_data = self.format_bytes(col_data, self.unit_selector.currentText())
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))

    def update_units(self):
        current_item = self.session_list.currentItem()
        if current_item:
            self.load_session_data(current_item)
    
    def format_bytes(self, bytes, unit='GB'):
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        if unit not in units:
            unit = 'GB'
        idx = units.index(unit)
        for _ in range(idx):
            bytes /= 1024
        return f"{max(bytes, 0.01):.2f} {unit}"

    
def main():
    try:
        app = QApplication.instance() or QApplication([])
        window = SystemMonitor()
        window.show()
        exit_code = app.exec()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == '__main__':
    sys.exit(main())