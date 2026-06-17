"""
server.py — Chat Server (Flask-SocketIO + Eventlet)
Supports: text messages, image sharing, file sharing
Storage : Pickle files (data/users.pkl, data/messages.pkl)
"""

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import hashlib, os, pickle, threading, base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chatapp_discord_2024'
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    max_http_buffer_size=50 * 1024 * 1024   # 50 MB for file transfers
)

# ── Pickle Storage ────────────────────────────────────────────
DATA_DIR   = 'data'
USERS_FILE = os.path.join(DATA_DIR, 'users.pkl')
MSGS_FILE  = os.path.join(DATA_DIR, 'messages.pkl')
_lock      = threading.Lock()
os.makedirs(DATA_DIR, exist_ok=True)

def _load(path, default):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return pickle.load(f)
    return default

def _save(path, obj):
    with open(path, 'wb') as f:
        pickle.dump(obj, f)

users    = _load(USERS_FILE, {})
messages = _load(MSGS_FILE,  [])
_msg_ctr = max((m['id'] for m in messages), default=0)

online_users = {}
sid_to_user  = {}

def _next_id():
    global _msg_ctr
    _msg_ctr += 1
    return _msg_ctr

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── REST Auth ─────────────────────────────────────────────────

@app.route('/api/signup', methods=['POST'])
def signup():
    d  = request.json or {}
    u  = d.get('username', '').strip()
    pw = d.get('password', '').strip()
    if not u or not pw:
        return jsonify({'success': False, 'message': 'All fields required'}), 400
    if len(u) < 3:
        return jsonify({'success': False, 'message': 'Username must be at least 3 characters'}), 400
    if len(pw) < 4:
        return jsonify({'success': False, 'message': 'Password must be at least 4 characters'}), 400
    if u in users:
        return jsonify({'success': False, 'message': 'Username already taken'}), 409
    with _lock:
        users[u] = {'id': len(users) + 1, 'username': u, 'password': _hash(pw)}
        _save(USERS_FILE, users)
    return jsonify({'success': True, 'user': {'id': users[u]['id'], 'username': u}})

@app.route('/api/login', methods=['POST'])
def login():
    d  = request.json or {}
    u  = d.get('username', '').strip()
    pw = d.get('password', '').strip()
    rec = users.get(u)
    if rec and rec['password'] == _hash(pw):
        return jsonify({'success': True, 'user': {'id': rec['id'], 'username': u}})
    return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

@app.route('/api/users')
def get_users():
    me = request.args.get('exclude', '')
    return jsonify([
        {'id': v['id'], 'username': k, 'online': k in online_users}
        for k, v in users.items() if k != me
    ])

# ── REST Messages ─────────────────────────────────────────────

@app.route('/api/messages')
def get_messages():
    u1 = request.args.get('user1', '')
    u2 = request.args.get('user2', '')
    updated = False
    with _lock:
        for m in messages:
            if m['sender'] == u2 and m['receiver'] == u1 and m['status'] != 'seen':
                m['status'] = 'seen'
                updated = True
        if updated:
            _save(MSGS_FILE, messages)
    conv = [m for m in messages
            if (m['sender'] == u1 and m['receiver'] == u2)
            or (m['sender'] == u2 and m['receiver'] == u1)]
    return jsonify(conv)

@app.route('/api/conversations')
def get_conversations():
    me    = request.args.get('username', '')
    peers = {}
    for m in messages:
        if m['sender'] == me:
            peers.setdefault(m['receiver'], []).append(m)
        elif m['receiver'] == me:
            peers.setdefault(m['sender'],   []).append(m)
    result = []
    for peer, msgs in peers.items():
        last   = msgs[-1]
        unread = sum(1 for m in msgs if m['receiver'] == me and m['status'] != 'seen')
        # Display label for last message
        if last['type'] == 'image':
            preview = '📷 Image'
        elif last['type'] == 'file':
            preview = f"📎 {last.get('filename', 'File')}"
        else:
            preview = last['text']
        result.append({
            'username':     peer,
            'last_message': preview,
            'last_time':    last['timestamp'],
            'status':       last['status'],
            'sender':       last['sender'],
            'unread':       unread,
            'online':       peer in online_users,
        })
    result.sort(key=lambda x: x['last_time'], reverse=True)
    return jsonify(result)

# ── Socket.IO ─────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    print(f"  [+] Connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    uname = sid_to_user.pop(request.sid, None)
    if uname:
        online_users.pop(uname, None)
        emit('user_status', {'username': uname, 'online': False}, broadcast=True)
        print(f"  [-] {uname} disconnected")

@socketio.on('user_online')
def on_user_online(data):
    uname = data.get('username')
    if uname and uname in users:
        online_users[uname]      = request.sid
        sid_to_user[request.sid] = uname
        join_room(f"user_{uname}")
        emit('user_status', {'username': uname, 'online': True}, broadcast=True)
        print(f"  [✓] {uname} online")

@socketio.on('send_message')
def on_send_message(data):
    sender   = data.get('sender', '')
    receiver = data.get('receiver', '')
    text     = data.get('text', '').strip()
    if not sender or not receiver or not text:
        return
    status = 'delivered' if receiver in online_users else 'sent'
    msg = {
        'id':        _next_id(),
        'sender':    sender,
        'receiver':  receiver,
        'text':      text,
        'type':      'text',
        'status':    status,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    with _lock:
        messages.append(msg)
        _save(MSGS_FILE, messages)
    emit('new_message', msg, room=f"user_{sender}")
    if receiver in online_users:
        emit('new_message', msg, room=f"user_{receiver}")

@socketio.on('send_file')
def on_send_file(data):
    """Handle image and file transfers via base64."""
    sender    = data.get('sender', '')
    receiver  = data.get('receiver', '')
    file_data = data.get('file_data', '')   # base64 string
    filename  = data.get('filename', 'file')
    file_type = data.get('file_type', 'file')  # 'image' or 'file'
    mime_type = data.get('mime_type', 'application/octet-stream')

    if not sender or not receiver or not file_data:
        return

    status = 'delivered' if receiver in online_users else 'sent'
    msg = {
        'id':        _next_id(),
        'sender':    sender,
        'receiver':  receiver,
        'text':      '',
        'type':      file_type,
        'filename':  filename,
        'mime_type': mime_type,
        'file_data': file_data,
        'status':    status,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    with _lock:
        messages.append(msg)
        _save(MSGS_FILE, messages)

    emit('new_message', msg, room=f"user_{sender}")
    if receiver in online_users:
        emit('new_message', msg, room=f"user_{receiver}")
    print(f"  [📎] {sender} → {receiver}: {filename}")

@socketio.on('message_seen')
def on_message_seen(data):
    sender   = data.get('sender')
    receiver = data.get('receiver')
    updated  = False
    with _lock:
        for m in messages:
            if m['sender'] == sender and m['receiver'] == receiver and m['status'] != 'seen':
                m['status'] = 'seen'
                updated = True
        if updated:
            _save(MSGS_FILE, messages)
    if updated and sender in online_users:
        emit('messages_seen', {'by': receiver}, room=f"user_{sender}")

@socketio.on('delete_message')
def on_delete_message(data):
    """Delete a message for both sender and receiver."""
    msg_id    = data.get('msg_id')
    requester = data.get('requester')   # who requested delete

    if not msg_id or not requester:
        return

    target = None
    with _lock:
        for i, m in enumerate(messages):
            if m['id'] == msg_id:
                # Only sender can delete
                if m['sender'] != requester:
                    emit('error', {'message': 'You can only delete your own messages'})
                    return
                target = messages.pop(i)
                break
        if target:
            _save(MSGS_FILE, messages)

    if target:
        payload = {'msg_id': msg_id}
        # Notify both sender and receiver to remove the bubble
        emit('message_deleted', payload, room=f"user_{target['sender']}")
        if target['receiver'] in online_users:
            emit('message_deleted', payload, room=f"user_{target['receiver']}")
        print(f"  [🗑] Message {msg_id} deleted by {requester}")


@socketio.on('typing')
def on_typing(data):
    receiver  = data.get('receiver')
    sender    = data.get('sender')
    is_typing = data.get('is_typing', False)
    if receiver in online_users:
        emit('typing', {'sender': sender, 'is_typing': is_typing},
             room=f"user_{receiver}")

# ── Entry Point ───────────────────────────────────────────────

if __name__ == '__main__':
    print()
    print("=" * 52)
    print("   💬  ChatApp Server  (Discord Dark Theme)")
    print("   Event Bus : localhost:5000")
    print("   Storage   : data/users.pkl + data/messages.pkl")
    print("   Features  : Text + Images + Files")
    print("=" * 52)
    print()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)