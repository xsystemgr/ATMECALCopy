from flask import Flask, render_template
from flask_socketio import SocketIO
import sqlite3
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app)

# Function to execute when a change in the database file is detected
def on_database_change(event):
    print(f"Detected change in {event.src_path}")
    data = read_data_from_database()
    current_time = datetime.now()
    emit_update_data(data, current_time)

# Subclass FileSystemEventHandler and override on_modified
class MyFileSystemEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        on_database_change(event)

# Function to read data from the SQLite database
def read_data_from_database():
    connection = sqlite3.connect('copy_results.db')
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM copyres')
    columns = [column[0] for column in cursor.description]
    result = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return result

# Function to emit update_data event with data and timestamp
def emit_update_data(data, timestamp):
    socketio.emit('update_data', {'data': data, 'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')}, namespace='/')

@app.route('/')
def index():
    return render_template('index.html')

# WebSocket event handler
@socketio.on('connect')
def handle_connect():
    print('Client connected')

# Start the observer in a separate thread
def observer_thread():
    observer = Observer()
    observer.schedule(MyFileSystemEventHandler(), path='.')
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# Start the Flask application and the WebSocket server
if __name__ == '__main__':
    threading.Thread(target=observer_thread, daemon=True).start()
    socketio.run(app, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
