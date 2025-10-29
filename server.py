import sqlite3
# session and request are now very important
from flask import Flask, render_template, g, session, request, jsonify
from flask_socketio import SocketIO, send, emit

# --- App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-goes-here'
socketio = SocketIO(app, async_mode='eventlet')

# --- Database Setup (Unchanged) ---
DATABASE = 'chat.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    print("Database initialized.")

# --- New: User & Message Functions ---

# This dictionary will map usernames to their unique connection ID (sid)
# Example: users = {'akhi': 'aBcDeFg12345', 'friend': 'xYzAeDb6789'}
users = {}

def save_private_message(sender, recipient, content):
    """New: Save a private message to the DB."""
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO messages (sender_username, recipient_username, content) VALUES (?, ?, ?)',
            (sender, recipient, content)
        )
        db.commit()

def get_chat_history(user1, user2):
    """New: Get all messages between two specific users."""
    with app.app_context():
        db = get_db()
        cursor = db.execute(
            """
            SELECT sender_username, content, timestamp 
            FROM messages 
            WHERE (sender_username = ? AND recipient_username = ?) 
               OR (sender_username = ? AND recipient_username = ?)
            ORDER BY timestamp ASC
            """,
            (user1, user2, user2, user1)
        )
        messages = cursor.fetchall()
        return [dict(msg) for msg in messages]

# --- Routes ---
@app.route('/')
def index():
    """
    Serve the main chat page.
    The history is now loaded dynamically, not here.
    """
    return render_template('index.html')

@app.route('/get_history/<recipient_name>')
def get_history(recipient_name):
    """New: A route to fetch the chat history with a specific user."""
    sender_name = session.get('username')
    if not sender_name:
        return jsonify({"error": "Not logged in"}), 401
    
    history = get_chat_history(sender_name, recipient_name)
    return jsonify(history)

# --- SocketIO Event Handlers ---

@socketio.on('join')
def handle_join(username):
    """Update: Handle a user joining."""
    # Store username in session and in our global 'users' dict
    session['username'] = username
    users[username] = request.sid  # request.sid is the unique ID
    
    print(f"User {username} joined with sid {request.sid}")
    print(f"Current users: {users}")
    
    # Send the updated user list to EVERYONE
    emit('user_list', list(users.keys()), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    """New: Handle a user disconnecting."""
    username = session.get('username')
    if username:
        print(f"User {username} disconnected.")
        # Remove user from our dict
        if username in users:
            del users[username]
        
        # Send the updated user list to EVERYONE
        emit('user_list', list(users.keys()), broadcast=True)

@socketio.on('private_message')
def handle_private_message(data):
    """New: Handle a private message."""
    sender_username = session.get('username')
    recipient_username = data['recipient']
    message_content = data['msg']

    if not sender_username:
        return # Not logged in

    # 1. Save to Database
    save_private_message(sender_username, recipient_username, message_content)

    # 2. Get the recipient's unique ID (sid)
    recipient_sid = users.get(recipient_username)

    # Prepare the message data to send
    message_packet = {
        'sender': sender_username,
        'msg': message_content
    }

    # 3. Send the message to the recipient *only*
    if recipient_sid:
        emit('private_message', message_packet, room=recipient_sid)

    # 4. Send the message back to the sender *only*
    emit('private_message', message_packet, room=request.sid)

@socketio.on('request_call')
def handle_request_call(data):
    """New: Handle a call request."""
    sender_username = session.get('username')
    recipient_username = data['recipient']
    
    recipient_sid = users.get(recipient_username)
    if recipient_sid:
        print(f"{sender_username} is calling {recipient_username}")
        # Emit to the recipient *only*
        emit('incoming_call', {'sender': sender_username}, room=recipient_sid)

@socketio.on('accept_call')
def handle_accept_call(data):
    """New: Handle a call acceptance."""
    sender_username = session.get('username')
    recipient_username = data['recipient']
    
    recipient_sid = users.get(recipient_username)
    if recipient_sid:
        print(f"{sender_username} accepted call from {recipient_username}")
        # Tell the original caller the call was accepted
        emit('call_accepted', {'sender': sender_username}, room=recipient_sid)

# --- Run the App (for local testing) ---
if __name__ == '__main__':
    init_db()
    print("Database initialized.")
    print("Starting server on http://127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)
