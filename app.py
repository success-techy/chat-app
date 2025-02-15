from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Predefined users with passwords
users = {"gun": "password1", "rose": "password2"}

# Database setup
def init_db():
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender TEXT,
                        recipient TEXT,
                        message TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()  # Initialize the database

# Track online users
online_users = {}

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['username'] = username
            return redirect(url_for('chat'))
        return "Invalid username or password"
    return render_template('login.html')

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    return render_template('chat.html', users=list(users.keys()), username=username)

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    if username and username in online_users:
        del online_users[username]
        emit('update_users', online_users, broadcast=True)
    return redirect(url_for('login'))

# SocketIO event handlers
@socketio.on('join')
def handle_join(data):
    username = data['username']
    online_users[username] = request.sid
    join_room(username)

    # Fetch all messages for this user (both sent and received)
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sender, message FROM messages WHERE recipient=? OR sender=? ORDER BY timestamp", (username, username))
    messages = cursor.fetchall()
    conn.close()

    # Send previous chat history to the user
    for msg in messages:
        emit('private_message', {'sender': msg[0], 'message': msg[1]}, room=username)

    emit('update_users', online_users, broadcast=True)

@socketio.on('private_message')
def handle_private_message(data):
    sender = data['sender']
    recipient = data['recipient']
    message = data['message']

    # Store the message in the database
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (sender, recipient, message) VALUES (?, ?, ?)", (sender, recipient, message))
    conn.commit()
    conn.close()

    msg_data = {'sender': sender, 'message': message}

    # Deliver message to recipient if they are online
    if recipient in online_users:
        emit('private_message', msg_data, room=recipient)

    # Show sender's message in their chat
    emit('private_message', msg_data, room=sender)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if username and username in online_users:
        del online_users[username]
        emit('update_users', online_users, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
