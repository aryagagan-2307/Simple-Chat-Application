# 💬 ChatApp — Windows Setup Guide

## 📁 Project Files
```
chatapp/
├── server.py           ← Flask backend
├── client.py           ← Tkinter GUI
├── requirements.txt    ← Dependencies
├── setup.bat           ← Run this FIRST (one time only)
├── start_server.bat    ← Start the server
├── start_client.bat    ← Open chat window
└── data/               ← Auto-created (users + messages)
```

---

## ⚙️ First Time Setup

### Step 1 — Install Python
- Download from **https://python.org** (Python 3.10 or above)
- ✅ Check **"Add Python to PATH"** during install

### Step 2 — Run Setup (one time only)
Double-click **`setup.bat`**
It will install all dependencies automatically.

---

## 🚀 Running the App

### Step 1 — Start the Server
Double-click **`start_server.bat`**
Keep this window open!

### Step 2 — Open Client Windows
Double-click **`start_client.bat`** → Login as User 1
Double-click **`start_client.bat`** again → Login as User 2

---

## ✨ Features
- Sign Up & Login with password
- Private 1-on-1 messaging
- ✓ Sent  ✓✓ Delivered  ✓✓ Seen (blue)
- Typing indicator
- Send images (🖼) and files (📎)
- Delete messages (🗑 button on your messages)
- Online/Offline status
- Discord dark theme UI

---

## ❗ Common Issues on Windows

| Problem | Fix |
|---|---|
| `python` not recognized | Reinstall Python, check "Add to PATH" |
| `setup.bat` closes instantly | Right-click → Run as Administrator |
| Port 5000 in use | Change `port=5000` to `port=5001` in server.py and `SERVER` in client.py |
| Tkinter missing | Reinstall Python with tcl/tk option checked |
| Pillow install fails | Run `pip install Pillow` manually in terminal |

---

*Built with Python 🐍 — Flask + SocketIO + Tkinter*