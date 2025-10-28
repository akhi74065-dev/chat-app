import sqlite3
# Import 'session' and 'request'
from flask import Flask, render_template, g, session, request
from flask_socketio import SocketIO, send

# --- App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-goes-here' # Make sure this is set!
# Use 'eventlet' for production
socketio = SocketIO(app, async_mode='eventlet') 

# --- Database Setup ---
DATABASE = 'chat.db'

def get_db():
    """Get a connection to the database."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close the database connection."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize the database."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    print("Database initialized.")

def save_message(username, content):
    """Update: Save a new message with username."""
    with app.app_context():
        db = get_db()
        # Update: Insert username and content
        db.execute('INSERT INTO messages (username, content) VALUES (?, ?)', (username, content))
        db.commit()

def get_all_messages():
    """Update: Get all messages with usernames."""
    with app.app_context():
        db = get_db()
        # Update: Select username and content
        cursor = db.execute('SELECT username, content, timestamp FROM messages ORDER BY timestamp ASC')
        messages = cursor.fetchall()
        return [dict(msg) for msg in messages]

# --- Routes ---
@app.route('/')
def index():
    """Serve the index.html file and pass in all chat history."""
    messages = get_all_messages()
    return render_template('index.html', history=messages)

# --- SocketIO Event Handlers ---

@socketio.on('join')
def handle_join(username):
    """New: Handle a user joining the chat."""
    # 'request.sid' is the unique ID for the user's connection
    print(f"User {username} joined with sid {request.sid}")
    # Store the username in the user's session
    session['username'] = username
    # Announce to everyone that a user has joined
    send(f"{username} has joined the chat.", broadcast=True)

@socketio.on('message')
def handle_message(msg_content):
    """Update: Handle a new message from a known user."""
    
    # Get the username from their session
    username = session.get('username')
    
    # If the user isn't in a session (e.g., disconnected), do nothing
    if not username:
        return

    print(f'Received message from {username}: {msg_content}')
    
    # 1. Save to DB (with username)
    save_message(username, msg_content)
    
    # 2. Create a data packet to send
    data = {
        'name': username,
        'msg': msg_content
    }
    
    # 3. Broadcast the data packet to all connected clients
    send(data, broadcast=True)

# Note: The init.py file doesn't need to change!
