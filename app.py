from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, join_room, leave_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Predefined users
predefined_users = {"user1": None, "user2": None}

@app.route('/')
def index():
    return render_template('index.html', users=list(predefined_users.keys()))

@socketio.on('connect')
def handle_connect():
    print("User connected")

@socketio.on('disconnect')
def handle_disconnect():
    disconnected_user = None
    for user, sid in predefined_users.items():
        if sid == request.sid:
            disconnected_user = user
            predefined_users[user] = None
            break
    if disconnected_user:
        emit('update_users', {user: (sid is not None) for user, sid in predefined_users.items()}, broadcast=True)
    print("User disconnected")

@socketio.on('join')
def handle_join(data):
    username = data['username']
    if username in predefined_users:
        predefined_users[username] = request.sid
        emit('update_users', {user: (sid is not None) for user, sid in predefined_users.items()}, broadcast=True)

@socketio.on('private_message')
def handle_private_message(data):
    recipient = data['recipient']
    message = data['message']
    sender = data['sender']
    if recipient in predefined_users and predefined_users[recipient]:
        recipient_sid = predefined_users[recipient]
        emit('private_message', {'sender': sender, 'message': message}, room=recipient_sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
