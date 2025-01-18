import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from unittest.mock import MagicMock, patch
from src.main import SystemMonitor, HistoryWindow
import sqlite3
import pytest
from src.main import main

@pytest.fixture(scope="function")
def app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()

@pytest.fixture
def monitor(app, mock_db_connection):
    monitor = SystemMonitor()
    monitor.conn = mock_db_connection
    monitor.create_table() 
    return monitor

@pytest.fixture
def mock_db_connection():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()

def test_initial_state(monitor):
    assert not monitor.is_recording
    assert monitor.session_id is None
    assert monitor.start_button.isEnabled()
    assert not monitor.stop_button.isEnabled()

def test_start_recording(monitor, qtbot):
    qtbot.mouseClick(monitor.start_button, Qt.MouseButton.LeftButton)
    assert monitor.is_recording
    assert not monitor.start_button.isEnabled()
    assert monitor.stop_button.isEnabled()
    assert monitor.session_id is not None

def test_stop_recording(monitor, qtbot):
    qtbot.mouseClick(monitor.start_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(monitor.stop_button, Qt.MouseButton.LeftButton)
    assert not monitor.is_recording
    assert monitor.start_button.isEnabled()
    assert not monitor.stop_button.isEnabled()

    cursor = monitor.conn.cursor()
    cursor.execute("SELECT end_time FROM sessions WHERE id = ?", (monitor.session_id,))
    end_time = cursor.fetchone()[0]
    assert end_time is not None

def test_update_stats_with_recording(monitor):
    monitor.is_recording = True  # Активируем запись
    with patch.object(monitor, 'record_to_db') as mock_record_to_db:
        monitor.update_stats()
        # Проверяем, что record_to_db был вызван с правильными аргументами
        mock_record_to_db.assert_called_once()
        
        args = mock_record_to_db.call_args[0]  # Аргументы вызова
        assert isinstance(args[0], float)  # cpu_percent
        assert isinstance(args[1], int)    # ram.free
        assert isinstance(args[2], int)    # ram.total
        assert isinstance(args[3], int)    # swap.free
        assert isinstance(args[4], int)    # swap.total

def test_record_to_db(monitor, qtbot):
    qtbot.mouseClick(monitor.start_button, Qt.MouseButton.LeftButton)
    monitor.record_to_db(50.0, 1000000, 8000000, 500000, 2000000)

    cursor = monitor.conn.cursor()
    cursor.execute("SELECT cpu, ram_free, ram_total, swap_free, swap_total FROM system_data WHERE session_id = ?", 
                   (monitor.session_id,))
    row = cursor.fetchone()
    assert row == (50.0, 1000000, 8000000, 500000, 2000000)

def test_update_units(monitor, qtbot):
    monitor.unit_selector.setCurrentText("MB")
    qtbot.wait(100)  # Ждем обновления статистики
    assert "MB" in monitor.ram_label.text()

def test_format_bytes(monitor):
    assert monitor.format_bytes(1024, "KB") == "1.00 KB"
    assert monitor.format_bytes(1048576, "MB") == "1.00 MB"
    assert monitor.format_bytes(1073741824, "GB") == "1.00 GB"
    assert monitor.format_bytes(1099511627776, "TB") == "1.00 TB"

def test_format_bytes_invalid_unit(monitor):
    assert monitor.format_bytes(1024, "INVALID") == "0.01 GB"

def test_view_history(monitor, qtbot):
    original_exec = HistoryWindow.exec
    HistoryWindow.exec = MagicMock()

    qtbot.mouseClick(monitor.history_button, Qt.MouseButton.LeftButton)

    HistoryWindow.exec.assert_called_once()

    # Восстановить оригинальный метод
    HistoryWindow.exec = original_exec

def test_update_recording_time(monitor, qtbot):
    # Start recording to initialize the timer
    qtbot.mouseClick(monitor.start_button, Qt.MouseButton.LeftButton)
    # Simulate the timer triggering the update_recording_time method
    monitor.update_recording_time()
    # Check if the stop button's text includes the updated time
    expected_time = "00:00:01"
    assert expected_time in monitor.stop_button.text()
    # Stop the recording to clean up
    qtbot.mouseClick(monitor.stop_button, Qt.MouseButton.LeftButton)

def test_main():
    with patch.object(QApplication, 'exec', return_value=0):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0  # Check that the exit code is 0

def test_main_keyboard_interrupt():
    with patch('sys.exit') as mock_exit:
        with patch.object(QApplication, 'exec', side_effect=KeyboardInterrupt):
            main()
            mock_exit.assert_called_once_with(1)

