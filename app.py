from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
socketio = SocketIO(app, cors_allowed_origins="*")

# Predefined users
users = {"ngt": "Admin@123", "mar": "password2"}

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize database
def init_db():
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender TEXT,
                        recipient TEXT,
                        message TEXT,
                        image TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

online_users = {}

@app.route('/send_message', methods=['POST'])
def send_message():
    sender = session.get('username')
    recipient = request.form.get('recipient')
    message = request.form.get('message')
    image_file = request.files.get('image')

    image_url = None
    if image_file:
        filename = secure_filename(str(uuid.uuid4()) + "_" + image_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
        image_url = f"/uploads/{filename}"

    msg_data = {
        'sender': sender,
        'recipient': recipient,
        'message': message,
        'image_url': image_url
    }

    # Save message to DB
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (sender, recipient, message, image) VALUES (?, ?, ?, ?)",
                   (sender, recipient, message, image_url))
    conn.commit()
    conn.close()

    # Emit to both sender and recipient
    socketio.emit('private_message', msg_data, room=sender)
    if recipient != sender:
        socketio.emit('private_message', msg_data, room=recipient)

    return jsonify({'status': 'sent'})

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
    return render_template('chat.html', users=list(users.keys()), username=session['username'])

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    if username and username in online_users:
        del online_users[username]
        emit('update_users', online_users, broadcast=True)
    return redirect(url_for('login'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('join')
def handle_join(data):
    username = data['username']
    online_users[username] = request.sid
    join_room(username)

    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sender, message, image FROM messages WHERE recipient=? OR sender=? ORDER BY timestamp",
                   (username, username))
    messages = cursor.fetchall()
    conn.close()

    for msg in messages:
        emit('private_message', {'sender': msg[0], 'message': msg[1], 'image_url': msg[2]}, room=username)

    emit('update_users', online_users, broadcast=True)

@socketio.on('private_message')
def handle_private_message(data):
    sender = data['sender']
    recipient = data['recipient']
    message = data.get('message', '')
    image_url = data.get('image_url', None)

    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (sender, recipient, message, image) VALUES (?, ?, ?, ?)",
                   (sender, recipient, message, image_url))
    conn.commit()
    conn.close()

    msg_data = {'sender': sender, 'message': message, 'image_url': image_url}

    if recipient in online_users:
        emit('private_message', msg_data, room=recipient)

    emit('private_message', msg_data, room=sender)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if username and username in online_users:
        del online_users[username]
        emit('update_users', online_users, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
