import sqlite3
from flask import Flask, render_template, g
from flask_socketio import SocketIO, send

# --- App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-goes-here'
socketio = SocketIO(app)

# --- Database Setup ---
DATABASE = 'chat.db'

def get_db():
    """Get a connection to the database."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        # Return rows as dictionaries (easier to work with)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize the database and create the 'messages' table if it doesn't exist."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    print("Database initialized.")

def save_message(content):
    """Save a new message to the database."""
    with app.app_context():
        db = get_db()
        db.execute('INSERT INTO messages (content) VALUES (?)', (content,))
        db.commit()

def get_all_messages():
    """Get all messages from the database, oldest first."""
    with app.app_context():
        db = get_db()
        cursor = db.execute('SELECT content, timestamp FROM messages ORDER BY timestamp ASC')
        messages = cursor.fetchall()
        # Convert row objects to simple dictionaries for the template
        return [dict(msg) for msg in messages]

# --- Routes ---
@app.route('/')
def index():
    """Serve the index.html file and pass in all chat history."""
    messages = get_all_messages()
    return render_template('index.html', history=messages)

# --- SocketIO Event Handlers ---
@socketio.on('connect')
def handle_connect():
    """Event handler for new connections."""
    print('Client connected!')

@socketio.on('message')
def handle_message(msg_content):
    """
    Event handler for new messages.
    1. Save the message to the database.
    2. Broadcast the message to all clients.
    """
    print(f'Received message: {msg_content}')
    
    # 1. Save to DB
    save_message(msg_content)
    
    # 2. Broadcast to all connected clients
    send(msg_content, broadcast=True)

# --- Run the App ---
if __name__ == '__main__':
    # Initialize the database first
    init_db()
    
    # We've added host='0.0.0.0'
    print("Starting server on http://0.0.0.0:5000") 
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)