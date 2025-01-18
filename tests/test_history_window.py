import pytest
from PyQt6.QtWidgets import QApplication
from src.main import HistoryWindow

@pytest.fixture(scope="function")
def app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()

@pytest.fixture
def mock_db_connection():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, start_time TEXT, end_time TEXT)")
    cursor.execute("""
        CREATE TABLE system_data (
            id INTEGER PRIMARY KEY, 
            session_id INTEGER, 
            timestamp TEXT, 
            cpu REAL, 
            ram_free REAL, 
            ram_total REAL, 
            swap_free REAL, 
            swap_total REAL
        )
    """)
    conn.commit()
    yield conn
    conn.close()

@pytest.fixture
def history_window(app, mock_db_connection):
    window = HistoryWindow(mock_db_connection)
    yield window
    window.close()

# Тест загрузки сессий
def test_load_sessions(history_window, mock_db_connection):
    cursor = mock_db_connection.cursor()
    cursor.execute("INSERT INTO sessions (start_time, end_time) VALUES ('2025-01-01 12:00:00', '2025-01-01 12:10:00')")
    mock_db_connection.commit()

    history_window.load_sessions()  # Предполагается, что этот метод существует
    assert history_window.session_list.count() == 1
    assert "2025-01-01 12:00:00" in history_window.session_list.item(0).text()

def test_load_session_data(history_window, mock_db_connection):
    cursor = mock_db_connection.cursor()
    cursor.execute("INSERT INTO sessions (start_time, end_time) VALUES ('2025-01-01 12:00:00', '2025-01-01 12:10:00')")
    session_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO system_data (session_id, timestamp, cpu, ram_free, ram_total, swap_free, swap_total)
        VALUES (?, '2025-01-01 12:05:00', 10.5, 2048 * 1024 * 1024, 4096 * 1024 * 1024, 1024 * 1024 * 1024, 2048 * 1024 * 1024)
    """, (session_id,))
    mock_db_connection.commit()

    history_window.load_sessions()

    item = history_window.session_list.item(0)
    history_window.load_session_data(item)

    assert history_window.table.rowCount() == 1
    assert history_window.table.item(0, 0).text() == '2025-01-01 12:05:00'
    assert history_window.table.item(0, 1).text() == '10.5'  # Проверка CPU
    assert history_window.table.item(0, 2).text() == history_window.format_bytes(2048 * 1024 * 1024, 'GB')  # RAM Free
    assert history_window.table.item(0, 3).text() == history_window.format_bytes(4096 * 1024 * 1024, 'GB')  # RAM Total
    assert history_window.table.item(0, 4).text() == history_window.format_bytes(1024 * 1024 * 1024, 'GB')  # Swap Free
    assert history_window.table.item(0, 5).text() == history_window.format_bytes(2048 * 1024 * 1024, 'GB')  # Swap Total


from unittest.mock import patch

def test_update_units_with_item(history_window, mock_db_connection):
    # Добавляем тестовые данные в mock_db_connection
    cursor = mock_db_connection.cursor()
    cursor.execute("INSERT INTO sessions (start_time, end_time) VALUES ('2025-01-01 12:00:00', '2025-01-01 12:10:00')")
    session_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO system_data (session_id, timestamp, cpu, ram_free, ram_total, swap_free, swap_total)
        VALUES (?, '2025-01-01 12:05:00', 10.5, 2048 * 1024 * 1024, 4096 * 1024 * 1024, 1024 * 1024 * 1024, 2048 * 1024 * 1024)
    """, (session_id,))
    mock_db_connection.commit()

    # Загружаем сессии и проверяем наличие элемента
    history_window.load_sessions()
    item = history_window.session_list.item(0)

    # Подключаем mock для проверки вызова load_session_data
    with patch.object(history_window, 'load_session_data') as mock_load_session_data:
        history_window.session_list.setCurrentItem(item)
        history_window.update_units()
        
        # Проверяем, что load_session_data был вызван
        mock_load_session_data.assert_called_once_with(item)



def test_format_bytes_invalid_unit(history_window):
    # Проверка с недопустимой единицей измерения
    assert history_window.format_bytes(1024, 'INVALID') == "0.01 GB"
    assert history_window.format_bytes(1073741824, 'UNKNOWN') == "1.00 GB"

    # Проверка, что допустимые единицы измерения работают корректно
    assert history_window.format_bytes(1024, 'KB') == "1.00 KB"
    assert history_window.format_bytes(1048576, 'MB') == "1.00 MB"


