"""
client.py — Discord-style dark theme chat client
Fixes:
  1. Users always visible in sidebar (no search needed)
  2. Input text in black (on light input background)
  3. Image & file sending via base64
  4. Polished Discord-inspired dark UI
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import socketio, threading, requests, base64, os, io
from datetime import datetime
from PIL import Image, ImageTk   # pip install Pillow

SERVER = "http://127.0.0.1:5000"

# ── Discord Dark Palette ──────────────────────────────────────
C = {
    # Backgrounds
    'bg_darkest':   '#1E2124',   # outermost bg
    'bg_dark':      '#282B30',   # sidebar
    'bg_mid':       '#36393F',   # main chat area
    'bg_light':     '#3F4248',   # message hover / input
    'bg_input':     '#FFFFFF',   # input box — white so text is black
    'bg_card':      '#2F3136',   # message cards

    # Accent
    'accent':       '#7289DA',   # Discord blurple
    'accent2':      '#5B6EAE',   # darker blurple
    'accent_green': '#43B581',   # online green
    'accent_red':   '#F04747',   # danger red
    'accent_gold':  '#FAA61A',   # warning gold

    # Text
    'text':         '#DCDDDE',   # primary
    'text_bright':  '#FFFFFF',
    'text_muted':   '#72767D',
    'text_input':   '#000000',   # black text in input

    # Bubbles
    'bubble_me':    '#5865F2',   # blurple for self
    'bubble_other': '#2F3136',   # dark card for others

    # Misc
    'border':       '#202225',
    'divider':      '#40444B',
    'unread_badge': '#ED4245',
    'online_dot':   '#3BA55D',
    'offline_dot':  '#747F8D',
    'hover':        '#34373C',
    'selected':     '#393C43',
}

TICK  = {'sent': '✓', 'delivered': '✓✓', 'seen': '✓✓'}
TCLR  = {'sent': C['text_muted'], 'delivered': C['text_muted'], 'seen': '#00AFF4'}


# ── Helpers ───────────────────────────────────────────────────

def api(method, path, **kw):
    try:
        r = getattr(requests, method)(SERVER + path, timeout=6, **kw)
        return r.json()
    except Exception as e:
        return {'success': False, 'message': str(e)}

def center(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth()  - w) // 2
    y = (win.winfo_screenheight() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

def lbl(parent, text, size=10, bold=False, fg=None, bg=None):
    return tk.Label(parent, text=text,
                    font=('Segoe UI', size, 'bold' if bold else 'normal'),
                    fg=fg or C['text'], bg=bg or C['bg_darkest'])

def flat_btn(parent, text, cmd, bg=None, fg=None, pady=9, font_size=10, width=None):
    kw = dict(text=text, command=cmd,
              bg=bg or C['accent'], fg=fg or C['text_bright'],
              activebackground=C['accent2'],
              activeforeground=C['text_bright'],
              font=('Segoe UI', font_size, 'bold'),
              relief='flat', bd=0, cursor='hand2', pady=pady)
    if width:
        kw['width'] = width
    return tk.Button(parent, **kw)

def styled_entry(parent, show='', bg=None):
    var = tk.StringVar()
    e = tk.Entry(parent,
                 textvariable=var,
                 font=('Segoe UI', 11),
                 bg=bg or C['bg_input'],
                 fg=C['text_input'],
                 insertbackground=C['accent'],
                 relief='flat', bd=0,
                 highlightthickness=2,
                 highlightbackground=C['border'],
                 highlightcolor=C['accent'])
    if show:
        e.config(show=show)
    e._var = var
    return e

def section_label(parent, text):
    """Small uppercase section header like Discord."""
    f = tk.Frame(parent, bg=C['bg_dark'])
    f.pack(fill='x', padx=10, pady=(14, 2))
    tk.Label(f, text=text.upper(),
             font=('Segoe UI', 8, 'bold'),
             bg=C['bg_dark'], fg=C['text_muted']).pack(side='left')
    return f


# ═════════════════════════════════════════════════════════════
# AUTH WINDOW
# ═════════════════════════════════════════════════════════════

class AuthWindow:
    def __init__(self, on_success):
        self.on_success = on_success
        self.root = tk.Tk()
        self.root.title("ChatApp")
        self.root.configure(bg=C['bg_darkest'])
        self.root.resizable(False, False)
        center(self.root, 420, 620)
        self._build()
        self.root.mainloop()

    def _build(self):
        # Gradient-feel header
        header = tk.Frame(self.root, bg=C['accent'], height=6)
        header.pack(fill='x')

        tk.Label(self.root, text="💬",
                 font=('Segoe UI Emoji', 52),
                 bg=C['bg_darkest'], fg=C['accent']).pack(pady=(28, 4))

        lbl(self.root, "Welcome to ChatApp", 20, bold=True,
            fg=C['text_bright'], bg=C['bg_darkest']).pack()
        lbl(self.root, "We're so excited to see you again!",
            10, fg=C['text_muted'], bg=C['bg_darkest']).pack(pady=(2, 20))

        # Tab strip
        tab_row = tk.Frame(self.root, bg=C['bg_dark'])
        tab_row.pack(fill='x', padx=40)
        self.tab_btns = {}
        for mode, txt in [('login', 'Log In'), ('signup', 'Register')]:
            b = tk.Button(tab_row, text=txt,
                          font=('Segoe UI', 10, 'bold'),
                          relief='flat', bd=0,
                          cursor='hand2', pady=10,
                          command=lambda m=mode: self._switch(m))
            b.pack(side='left', fill='x', expand=True)
            self.tab_btns[mode] = b

        # Card
        self.card = tk.Frame(self.root, bg=C['bg_card'])
        self.card.pack(fill='x', padx=40, pady=(0, 8))

        # Status
        self.status_lbl = tk.Label(self.root, text='',
                                   font=('Segoe UI', 9),
                                   bg=C['bg_darkest'],
                                   fg=C['accent_red'])
        self.status_lbl.pack()

        self._switch('login')

    def _switch(self, mode):
        for m, b in self.tab_btns.items():
            if m == mode:
                b.config(bg=C['accent'], fg=C['text_bright'])
            else:
                b.config(bg=C['bg_mid'], fg=C['text_muted'])

        for w in self.card.winfo_children():
            w.destroy()
        self.status_lbl.config(text='')

        pad = dict(padx=24, pady=(14, 0), fill='x')

        tk.Label(self.card, text="USERNAME",
                 font=('Segoe UI', 8, 'bold'),
                 bg=C['bg_card'], fg=C['text_muted']).pack(**pad)
        self.e_user = styled_entry(self.card, bg=C['bg_light'])
        self.e_user.config(fg=C['text_input'])
        self.e_user.pack(padx=24, pady=(4, 0), fill='x', ipady=9)

        tk.Label(self.card, text="PASSWORD",
                 font=('Segoe UI', 8, 'bold'),
                 bg=C['bg_card'], fg=C['text_muted']).pack(**pad)
        self.e_pass = styled_entry(self.card, show='•', bg=C['bg_light'])
        self.e_pass.config(fg=C['text_input'])
        self.e_pass.pack(padx=24, pady=(4, 0), fill='x', ipady=9)

        self.e_confirm = None
        if mode == 'signup':
            tk.Label(self.card, text="CONFIRM PASSWORD",
                     font=('Segoe UI', 8, 'bold'),
                     bg=C['bg_card'], fg=C['text_muted']).pack(**pad)
            self.e_confirm = styled_entry(self.card, show='•', bg=C['bg_light'])
            self.e_confirm.config(fg=C['text_input'])
            self.e_confirm.pack(padx=24, pady=(4, 0), fill='x', ipady=9)

        action  = self._do_signup if mode == 'signup' else self._do_login
        btn_txt = "Continue" if mode == 'signup' else "Log In"
        flat_btn(self.card, btn_txt, action, font_size=11
                 ).pack(padx=24, pady=(20, 24), fill='x')

        link_txt  = "Already have an account?" if mode == 'signup' \
                    else "Need an account?"
        link_mode = 'login' if mode == 'signup' else 'signup'
        link_act  = "Log In" if mode == 'signup' else "Register"

        link_row = tk.Frame(self.root, bg=C['bg_darkest'])
        link_row.pack()
        tk.Label(link_row, text=link_txt,
                 font=('Segoe UI', 9),
                 bg=C['bg_darkest'], fg=C['text_muted']).pack(side='left')
        tk.Button(link_row, text=f"  {link_act}",
                  font=('Segoe UI', 9),
                  bg=C['bg_darkest'], fg=C['accent'],
                  activeforeground=C['accent2'],
                  activebackground=C['bg_darkest'],
                  relief='flat', bd=0, cursor='hand2',
                  command=lambda: self._switch(link_mode)).pack(side='left')

        self.e_user.focus_set()
        self.e_pass.bind('<Return>', lambda e: action())

    def _do_login(self):
        u  = self.e_user.get().strip()
        pw = self.e_pass.get().strip()
        if not u or not pw:
            self.status_lbl.config(text="⚠  Please fill in all fields.")
            return
        self.status_lbl.config(text="Logging in…", fg=C['accent'])
        self.root.update()
        res = api('post', '/api/login', json={'username': u, 'password': pw})
        if res.get('success'):
            self.root.destroy()
            self.on_success(res['user'])
        else:
            self.status_lbl.config(
                text=f"⚠  {res.get('message','Login failed')}",
                fg=C['accent_red'])

    def _do_signup(self):
        u  = self.e_user.get().strip()
        pw = self.e_pass.get().strip()
        c  = self.e_confirm.get().strip() if self.e_confirm else ''
        if not u or not pw or not c:
            self.status_lbl.config(text="⚠  Please fill in all fields.", fg=C['accent_red'])
            return
        if pw != c:
            self.status_lbl.config(text="⚠  Passwords do not match.", fg=C['accent_red'])
            return
        self.status_lbl.config(text="Creating account…", fg=C['accent'])
        self.root.update()
        res = api('post', '/api/signup', json={'username': u, 'password': pw})
        if res.get('success'):
            self.root.destroy()
            self.on_success(res['user'])
        else:
            self.status_lbl.config(
                text=f"⚠  {res.get('message','Signup failed')}",
                fg=C['accent_red'])


# ═════════════════════════════════════════════════════════════
# CHAT WINDOW
# ═════════════════════════════════════════════════════════════

class ChatWindow:
    def __init__(self, user):
        self.me           = user['username']
        self.active_chat  = None
        self.msg_widgets  = {}
        self.typing_timer = None
        self.is_typing    = False
        self._photo_refs  = []   # keep image refs alive
        self.sio          = socketio.Client(reconnection=True, reconnection_attempts=10)

        self.root = tk.Tk()
        self.root.title(f"ChatApp  —  {self.me}")
        self.root.configure(bg=C['bg_darkest'])
        center(self.root, 1060, 700)
        self.root.minsize(800, 520)

        self._build_ui()
        self._bind_socket_events()
        self._connect()
        self._load_sidebar()

        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.mainloop()

    # ── UI ────────────────────────────────────────────────────

    def _build_ui(self):
        # ════ FAR LEFT — server icon strip (Discord-style) ════
        icon_strip = tk.Frame(self.root, bg=C['bg_darkest'], width=72)
        icon_strip.pack(side='left', fill='y')
        icon_strip.pack_propagate(False)

        # App logo pill
        logo_frame = tk.Frame(icon_strip, bg=C['accent'],
                              width=48, height=48)
        logo_frame.pack(pady=(16, 0), padx=12)
        logo_frame.pack_propagate(False)
        tk.Label(logo_frame, text="💬",
                 font=('Segoe UI Emoji', 22),
                 bg=C['accent'], fg=C['text_bright']).place(relx=0.5, rely=0.5, anchor='center')

        tk.Frame(icon_strip, bg=C['divider'], height=2,
                 width=32).pack(pady=10, padx=20)

        # User avatar pill
        av_frame = tk.Frame(icon_strip, bg=C['accent2'],
                            width=48, height=48)
        av_frame.pack(padx=12)
        av_frame.pack_propagate(False)
        tk.Label(av_frame, text=self.me[0].upper(),
                 font=('Segoe UI', 18, 'bold'),
                 bg=C['accent2'], fg=C['text_bright']).place(relx=0.5, rely=0.5, anchor='center')

        tk.Label(icon_strip, text=self.me[:8],
                 font=('Segoe UI', 7),
                 bg=C['bg_darkest'], fg=C['text_muted'],
                 wraplength=64).pack(pady=(4, 0))

        # ════ SIDEBAR — user list ══════════════════════════════
        self.sidebar = tk.Frame(self.root, bg=C['bg_dark'], width=240)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        # Sidebar header
        hdr = tk.Frame(self.sidebar, bg=C['bg_dark'])
        hdr.pack(fill='x', padx=12, pady=(16, 8))
        tk.Label(hdr, text="Direct Messages",
                 font=('Segoe UI', 13, 'bold'),
                 bg=C['bg_dark'], fg=C['text_bright']).pack(side='left')
        # New chat button
        tk.Button(hdr, text="+",
                  font=('Segoe UI', 14, 'bold'),
                  bg=C['bg_dark'], fg=C['text_muted'],
                  activebackground=C['bg_mid'],
                  activeforeground=C['text_bright'],
                  relief='flat', bd=0, cursor='hand2',
                  command=self._toggle_mode).pack(side='right')

        # Search box — placeholder text is NOT tied to search_var
        sf = tk.Frame(self.sidebar, bg=C['bg_mid'], highlightthickness=0)
        sf.pack(fill='x', padx=10, pady=(0, 8))
        self.search_var = tk.StringVar(value='')
        PLACEHOLDER = "Find a conversation"
        se = tk.Entry(sf, font=('Segoe UI', 10),
                      bg=C['bg_mid'], fg=C['text_muted'],
                      relief='flat', bd=0,
                      insertbackground=C['accent'])
        se.insert(0, PLACEHOLDER)
        se.pack(fill='x', ipady=6, padx=8)

        def _search_in(_):
            if se.get() == PLACEHOLDER:
                se.delete(0, 'end')
                se.config(fg=C['text'])
        def _search_out(_):
            if not se.get().strip():
                se.delete(0, 'end')
                se.insert(0, PLACEHOLDER)
                se.config(fg=C['text_muted'])
                self.search_var.set('')
                self._load_sidebar()
        def _search_key(_):
            val = se.get().strip()
            self.search_var.set('' if val == PLACEHOLDER else val)
            self._load_sidebar()

        se.bind('<FocusIn>',   _search_in)
        se.bind('<FocusOut>',  _search_out)
        se.bind('<KeyRelease>', _search_key)

        # Tab mode
        self.list_mode = 'users'   # default: show all users

        # Scrollable list
        outer = tk.Frame(self.sidebar, bg=C['bg_dark'])
        outer.pack(fill='both', expand=True)
        self.c_canvas = tk.Canvas(outer, bg=C['bg_dark'],
                                  highlightthickness=0, bd=0)
        csb = tk.Scrollbar(outer, orient='vertical',
                           command=self.c_canvas.yview,
                           bg=C['bg_dark'], troughcolor=C['bg_dark'])
        self.c_canvas.configure(yscrollcommand=csb.set)
        csb.pack(side='right', fill='y')
        self.c_canvas.pack(fill='both', expand=True)
        self.c_frame = tk.Frame(self.c_canvas, bg=C['bg_dark'])
        self._cwin   = self.c_canvas.create_window(
            (0, 0), window=self.c_frame, anchor='nw')
        self.c_frame.bind('<Configure>',
            lambda e: self.c_canvas.configure(
                scrollregion=self.c_canvas.bbox('all')))
        self.c_canvas.bind('<Configure>',
            lambda e: self.c_canvas.itemconfig(self._cwin, width=e.width))
        self.c_canvas.bind_all('<MouseWheel>',
            lambda e: self.c_canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

        # ════ RIGHT — chat area ════════════════════════════════
        self.right = tk.Frame(self.root, bg=C['bg_mid'])
        self.right.pack(side='left', fill='both', expand=True)

        # Welcome screen
        self.welcome = tk.Frame(self.right, bg=C['bg_mid'])
        self.welcome.place(relx=0.5, rely=0.5, anchor='center')
        tk.Label(self.welcome, text="💬",
                 font=('Segoe UI Emoji', 64),
                 bg=C['bg_mid'], fg=C['bg_light']).pack()
        lbl(self.welcome, "Your Direct Messages",
            16, bold=True, fg=C['text_bright'], bg=C['bg_mid']).pack(pady=(8, 4))
        lbl(self.welcome, "Select someone from the left to start chatting.",
            11, fg=C['text_muted'], bg=C['bg_mid']).pack()

        # Chat panel
        self.chat_panel = tk.Frame(self.right, bg=C['bg_mid'])

        # Chat header bar
        self.chat_hdr = tk.Frame(self.chat_panel, bg=C['bg_dark'],
                                 highlightthickness=1,
                                 highlightbackground=C['border'])
        self.chat_hdr.pack(fill='x')

        self.hdr_av = tk.Label(self.chat_hdr,
                               font=('Segoe UI', 16, 'bold'),
                               bg=C['accent'], fg=C['text_bright'],
                               width=2, padx=6, pady=4)
        self.hdr_av.pack(side='left', padx=(14, 8), pady=10)

        hdr_info = tk.Frame(self.chat_hdr, bg=C['bg_dark'])
        hdr_info.pack(side='left')
        self.hdr_name   = tk.Label(hdr_info, text="",
                                   font=('Segoe UI', 12, 'bold'),
                                   bg=C['bg_dark'], fg=C['text_bright'])
        self.hdr_name.pack(anchor='w')
        self.hdr_status = tk.Label(hdr_info, text="",
                                   font=('Segoe UI', 9),
                                   bg=C['bg_dark'], fg=C['text_muted'])
        self.hdr_status.pack(anchor='w')

        # Messages scroll area
        msg_outer = tk.Frame(self.chat_panel, bg=C['bg_mid'])
        msg_outer.pack(fill='both', expand=True)
        self.msg_canvas = tk.Canvas(msg_outer, bg=C['bg_mid'],
                                    highlightthickness=0, bd=0)
        msb = tk.Scrollbar(msg_outer, orient='vertical',
                           command=self.msg_canvas.yview)
        self.msg_canvas.configure(yscrollcommand=msb.set)
        msb.pack(side='right', fill='y')
        self.msg_canvas.pack(fill='both', expand=True)
        self.msg_frame = tk.Frame(self.msg_canvas, bg=C['bg_mid'])
        self._mwin     = self.msg_canvas.create_window(
            (0, 0), window=self.msg_frame, anchor='nw')
        self.msg_frame.bind('<Configure>',
            lambda e: self.msg_canvas.configure(
                scrollregion=self.msg_canvas.bbox('all')))
        self.msg_canvas.bind('<Configure>',
            lambda e: self.msg_canvas.itemconfig(self._mwin, width=e.width))

        # Typing indicator
        self.typing_lbl = tk.Label(self.chat_panel, text="",
                                   font=('Segoe UI', 9, 'italic'),
                                   bg=C['bg_mid'], fg=C['text_muted'])
        self.typing_lbl.pack(anchor='w', padx=16, pady=(2, 0))

        # ── Input bar ──────────────────────────────────────────
        input_wrap = tk.Frame(self.chat_panel, bg=C['bg_mid'])
        input_wrap.pack(fill='x', side='bottom', padx=16, pady=(4, 16))

        input_bar = tk.Frame(input_wrap, bg=C['bg_light'],
                             highlightthickness=0)
        input_bar.pack(fill='x')

        # Attach button (📎)
        attach_btn = tk.Button(input_bar, text="📎",
                               font=('Segoe UI Emoji', 14),
                               bg=C['bg_light'], fg=C['text_muted'],
                               activebackground=C['bg_light'],
                               activeforeground=C['accent'],
                               relief='flat', bd=0, cursor='hand2',
                               command=self._attach_file)
        attach_btn.pack(side='left', padx=(10, 4), pady=8)

        # Image button (🖼)
        img_btn = tk.Button(input_bar, text="🖼",
                            font=('Segoe UI Emoji', 14),
                            bg=C['bg_light'], fg=C['text_muted'],
                            activebackground=C['bg_light'],
                            activeforeground=C['accent'],
                            relief='flat', bd=0, cursor='hand2',
                            command=self._attach_image)
        img_btn.pack(side='left', padx=(0, 6), pady=8)

        # Text entry
        self.msg_var = tk.StringVar()
        self.msg_entry = tk.Entry(input_bar,
                                  textvariable=self.msg_var,
                                  font=('Segoe UI', 12),
                                  bg=C['bg_light'],
                                  fg=C['text_input'],
                                  insertbackground=C['accent'],
                                  relief='flat', bd=0)
        self.msg_entry.pack(side='left', fill='both', expand=True,
                            padx=4, pady=10, ipady=6)
        self.msg_entry.bind('<Return>',     self._send_text)
        self.msg_entry.bind('<KeyRelease>', self._on_key)

        # Send button
        flat_btn(input_bar, "Send ➤", self._send_text,
                 pady=7, font_size=10
                 ).pack(side='right', padx=(4, 10), pady=8, ipadx=12)

    # ── Sidebar ───────────────────────────────────────────────

    def _toggle_mode(self):
        self.list_mode = 'chats' if self.list_mode == 'users' else 'users'
        self._load_sidebar()

    def _load_sidebar(self):
        q = self.search_var.get().strip().lower()
        for w in self.c_frame.winfo_children():
            w.destroy()

        # Always show ALL users by default
        res  = api('get', f'/api/users?exclude={self.me}')
        rows = res if isinstance(res, list) else []

        # Also fetch recent conversations for unread counts + last msg
        convs_raw = api('get', f'/api/conversations?username={self.me}')
        convs = {c['username']: c for c in convs_raw} \
                if isinstance(convs_raw, list) else {}

        if not rows:
            lbl(self.c_frame,
                "No other users yet.\nAsk someone to register!",
                9, fg=C['text_muted'], bg=C['bg_dark']).pack(pady=30, padx=10)
            return

        # Separate online vs offline
        online_rows  = [r for r in rows if r.get('online')]
        offline_rows = [r for r in rows if not r.get('online')]

        if online_rows:
            section_label(self.c_frame, f"Online — {len(online_rows)}")
            for r in online_rows:
                if q and q not in r['username'].lower():
                    continue
                c = convs.get(r['username'], {})
                self._user_row(r['username'], online=True,
                               last=c.get('last_message', ''),
                               unread=c.get('unread', 0),
                               time=c.get('last_time', ''))

        if offline_rows:
            section_label(self.c_frame, f"Offline — {len(offline_rows)}")
            for r in offline_rows:
                if q and q not in r['username'].lower():
                    continue
                c = convs.get(r['username'], {})
                self._user_row(r['username'], online=False,
                               last=c.get('last_message', ''),
                               unread=c.get('unread', 0),
                               time=c.get('last_time', ''))

    def _user_row(self, username, online=False, last='', unread=0, time=''):
        is_active = username == self.active_chat
        row_bg = C['selected'] if is_active else C['bg_dark']

        row = tk.Frame(self.c_frame, bg=row_bg, cursor='hand2')
        row.pack(fill='x', padx=6, pady=1)

        def on_enter(_): row.config(bg=C['hover'])
        def on_leave(_): row.config(bg=C['selected'] if username == self.active_chat else C['bg_dark'])
        row.bind('<Enter>', on_enter)
        row.bind('<Leave>', on_leave)
        row.bind('<Button-1>', lambda e: self._open_chat(username))

        # Avatar
        av_wrap = tk.Frame(row, bg=row_bg)
        av_wrap.pack(side='left', padx=(8, 6), pady=6)
        av_wrap.bind('<Button-1>', lambda e: self._open_chat(username))

        av = tk.Label(av_wrap, text=username[0].upper(),
                      font=('Segoe UI', 13, 'bold'),
                      bg=C['accent'] if online else C['bg_light'],
                      fg=C['text_bright'], width=2, pady=3)
        av.pack()
        av.bind('<Button-1>', lambda e: self._open_chat(username))

        # Online dot
        dot_color = C['online_dot'] if online else C['offline_dot']
        tk.Label(av_wrap, text="●",
                 font=('Segoe UI', 7),
                 bg=row_bg, fg=dot_color).pack()

        # Info
        info = tk.Frame(row, bg=row_bg)
        info.pack(side='left', fill='both', expand=True, pady=6)
        info.bind('<Button-1>', lambda e: self._open_chat(username))

        top = tk.Frame(info, bg=row_bg)
        top.pack(fill='x')
        top.bind('<Button-1>', lambda e: self._open_chat(username))

        tk.Label(top, text=username,
                 font=('Segoe UI', 10, 'bold'),
                 bg=row_bg,
                 fg=C['text_bright'] if is_active else C['text']).pack(side='left')

        if time:
            t = time[11:16] if len(time) > 10 else time
            tk.Label(top, text=t,
                     font=('Segoe UI', 7),
                     bg=row_bg, fg=C['text_muted']).pack(side='right', padx=8)

        if last:
            preview = (last[:30] + '…') if len(last) > 30 else last
            bot = tk.Frame(info, bg=row_bg)
            bot.pack(fill='x')
            tk.Label(bot, text=preview,
                     font=('Segoe UI', 9),
                     bg=row_bg, fg=C['text_muted']).pack(side='left')
            if unread:
                tk.Label(bot, text=str(unread),
                         font=('Segoe UI', 8, 'bold'),
                         bg=C['unread_badge'], fg=C['text_bright'],
                         padx=5, pady=1).pack(side='right', padx=8)

    # ── Open Chat ─────────────────────────────────────────────

    def _open_chat(self, username):
        self.active_chat = username
        self.welcome.place_forget()
        self.chat_panel.pack(fill='both', expand=True)

        self.hdr_av.config(text=username[0].upper())
        self.hdr_name.config(text=f"@{username}")
        self.typing_lbl.config(text="")
        self._refresh_header(username)

        for w in self.msg_frame.winfo_children():
            w.destroy()
        self.msg_widgets.clear()
        self._photo_refs.clear()

        def load():
            msgs = api('get', f'/api/messages?user1={self.me}&user2={username}')
            def render():
                if isinstance(msgs, list):
                    for m in msgs:
                        self._add_bubble(m)
                    self._scroll_bottom()
                try:
                    self.sio.emit('message_seen', {'sender': username, 'receiver': self.me})
                except Exception:
                    pass
            self.root.after(0, render)

        threading.Thread(target=load, daemon=True).start()
        self._load_sidebar()
        self.msg_entry.focus_set()

    def _refresh_header(self, username):
        def fetch():
            res = api('get', f'/api/users?exclude={self.me}')
            for u in (res if isinstance(res, list) else []):
                if u['username'] == username:
                    if u.get('online'):
                        self.root.after(0, lambda: self.hdr_status.config(
                            text="● Online", fg=C['accent_green']))
                    else:
                        self.root.after(0, lambda: self.hdr_status.config(
                            text="● Offline", fg=C['text_muted']))
        threading.Thread(target=fetch, daemon=True).start()

    # ── Message Bubbles ───────────────────────────────────────

    def _add_bubble(self, msg):
        is_me = msg['sender'] == self.me
        ts    = msg['timestamp'][11:16] if len(msg['timestamp']) > 10 \
                else msg['timestamp']
        mtype = msg.get('type', 'text')

        # Outer row — full width, aligns bubble left or right
        outer = tk.Frame(self.msg_frame, bg=C['bg_mid'])
        outer.pack(fill='x', pady=3, padx=12)

        bub_bg = C['bubble_me'] if is_me else C['bubble_other']
        bubble = tk.Frame(outer, bg=bub_bg,
                          highlightthickness=1,
                          highlightbackground=C['border'] if not is_me else bub_bg)
        # Use pack anchor to push bubble left or right
        bubble.pack(side='right' if is_me else 'left',
                    anchor='e' if is_me else 'w',
                    padx=(60 if not is_me else 0, 0 if not is_me else 60))

        # ── Sender name (for received messages)
        if not is_me:
            tk.Label(bubble, text=msg['sender'],
                     font=('Segoe UI', 8, 'bold'),
                     bg=bub_bg, fg=C['accent'],
                     padx=12, pady=6).pack(anchor='w')

        # ── Content
        if mtype == 'text':
            tk.Label(bubble, text=msg['text'],
                     font=('Segoe UI', 11),
                     bg=bub_bg, fg=C['text_bright'],
                     wraplength=420, justify='left',
                     padx=12, pady=6).pack(anchor='w')

        elif mtype == 'image':
            try:
                raw = base64.b64decode(msg['file_data'])
                img = Image.open(io.BytesIO(raw))
                img.thumbnail((320, 240), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._photo_refs.append(photo)
                img_lbl = tk.Label(bubble, image=photo,
                                   bg=bub_bg, cursor='hand2',
                                   padx=8, pady=6)
                img_lbl.pack(anchor='w')
                # Click to save
                img_lbl.bind('<Button-1>',
                    lambda e, d=msg['file_data'], n=msg.get('filename','image.png'):
                    self._save_file(d, n))
                tk.Label(bubble, text=f"📷  {msg.get('filename','image')}",
                         font=('Segoe UI', 8),
                         bg=bub_bg, fg=C['text_muted'],
                         padx=12).pack(anchor='w')
            except Exception:
                tk.Label(bubble, text="[Image — could not load]",
                         font=('Segoe UI', 10),
                         bg=bub_bg, fg=C['text_muted'],
                         padx=12, pady=6).pack(anchor='w')

        elif mtype == 'file':
            file_row = tk.Frame(bubble, bg=bub_bg)
            file_row.pack(anchor='w', padx=10, pady=8)
            tk.Label(file_row, text="📄",
                     font=('Segoe UI Emoji', 28),
                     bg=bub_bg, fg=C['text']).pack(side='left', padx=(0, 8))
            info_col = tk.Frame(file_row, bg=bub_bg)
            info_col.pack(side='left')
            fname = msg.get('filename', 'file')
            tk.Label(info_col, text=fname,
                     font=('Segoe UI', 10, 'bold'),
                     bg=bub_bg, fg=C['text_bright']).pack(anchor='w')
            dl_btn = tk.Button(info_col, text="⬇  Download",
                               font=('Segoe UI', 8),
                               bg=C['accent'], fg=C['text_bright'],
                               activebackground=C['accent2'],
                               relief='flat', bd=0, cursor='hand2',
                               padx=6, pady=2,
                               command=lambda d=msg['file_data'], n=fname:
                               self._save_file(d, n))
            dl_btn.pack(anchor='w', pady=(3, 0))

        # ── Footer: time + tick + delete button
        foot = tk.Frame(bubble, bg=bub_bg)
        foot.pack(fill='x', padx=10, pady=(0, 5))
        tk.Label(foot, text=ts,
                 font=('Segoe UI', 7),
                 bg=bub_bg, fg=C['text_muted']).pack(side='left')

        tick_lbl = None
        if is_me:
            st = msg.get('status', 'sent')
            tick_lbl = tk.Label(foot, text=TICK[st],
                                font=('Segoe UI', 8),
                                bg=bub_bg, fg=TCLR[st])
            tick_lbl.pack(side='right')
            # Delete button — always visible on own messages
            if msg.get('id'):
                mid = msg['id']
                del_btn = tk.Label(foot, text="🗑",
                                   font=('Segoe UI Emoji', 9),
                                   bg=bub_bg, fg=C['text_muted'],
                                   cursor='hand2')
                del_btn.pack(side='right', padx=(0, 4))
                del_btn.bind('<Button-1>',
                    lambda e, m=mid: self._confirm_delete(m))
                del_btn.bind('<Enter>',
                    lambda e: e.widget.config(fg=C['accent_red']))
                del_btn.bind('<Leave>',
                    lambda e, b=bub_bg: e.widget.config(fg=C['text_muted']))

        if msg.get('id'):
            self.msg_widgets[msg['id']] = (outer, tick_lbl)
            # Right-click to delete (only own messages)
            if is_me:
                mid = msg['id']
                def _bind_delete(w, m=mid):
                    w.bind('<Button-2>', lambda e, x=m: self._show_delete_menu(e, x))
                    w.bind('<Button-3>', lambda e, x=m: self._show_delete_menu(e, x))
                    for child in w.winfo_children():
                        _bind_delete(child, m)
                _bind_delete(outer)

    def _show_delete_menu(self, event, msg_id):
        """Show right-click context menu with Delete option."""
        menu = tk.Menu(self.root, tearoff=0,
                       bg=C['bg_card'], fg=C['text_bright'],
                       activebackground=C['accent_red'],
                       activeforeground=C['text_bright'],
                       font=('Segoe UI', 10),
                       relief='flat', bd=0)
        menu.add_command(label="🗑  Delete for Everyone",
                         command=lambda: self._delete_message(msg_id))
        menu.tk_popup(event.x_root, event.y_root)

    def _confirm_delete(self, msg_id):
        """Ask for confirmation then delete."""
        if messagebox.askyesno("Delete Message",
                               "Delete this message for everyone?"):
            self._delete_message(msg_id)

    def _delete_message(self, msg_id):
        """Send delete request to server."""
        try:
            self.sio.emit('delete_message', {
                'msg_id':    msg_id,
                'requester': self.me,
            })
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _scroll_bottom(self):
        def do_scroll():
            self.msg_frame.update_idletasks()
            self.msg_canvas.configure(scrollregion=self.msg_canvas.bbox('all'))
            self.msg_canvas.yview_moveto(1.0)
        self.root.after(100, do_scroll)

    # ── File / Image helpers ──────────────────────────────────

    def _attach_image(self):
        if not self.active_chat:
            messagebox.showinfo("No chat", "Open a chat first.")
            return
        path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if not path:
            return
        self._send_file_path(path, 'image')

    def _attach_file(self):
        if not self.active_chat:
            messagebox.showinfo("No chat", "Open a chat first.")
            return
        path = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("All files", "*.*")])
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        img_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        ftype = 'image' if ext in img_exts else 'file'
        self._send_file_path(path, ftype)

    def _send_file_path(self, path, ftype):
        max_mb = 10
        size   = os.path.getsize(path)
        if size > max_mb * 1024 * 1024:
            messagebox.showerror("Too large",
                                 f"File must be under {max_mb} MB.")
            return

        def do_send():
            with open(path, 'rb') as f:
                raw = f.read()
            b64      = base64.b64encode(raw).decode('utf-8')
            filename = os.path.basename(path)
            import mimetypes
            mime, _  = mimetypes.guess_type(path)
            mime     = mime or 'application/octet-stream'
            try:
                self.sio.emit('send_file', {
                    'sender':    self.me,
                    'receiver':  self.active_chat,
                    'file_data': b64,
                    'filename':  filename,
                    'file_type': ftype,
                    'mime_type': mime,
                })
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=do_send, daemon=True).start()

    def _save_file(self, b64_data, filename):
        path = filedialog.asksaveasfilename(
            initialfile=filename,
            title="Save file as")
        if not path:
            return
        try:
            raw = base64.b64decode(b64_data)
            with open(path, 'wb') as f:
                f.write(raw)
            messagebox.showinfo("Saved", f"File saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Sending text ──────────────────────────────────────────

    def _send_text(self, event=None):
        text = self.msg_var.get().strip()
        if not text or not self.active_chat:
            return
        self.msg_var.set("")
        self._stop_typing()
        try:
            self.sio.emit('send_message', {
                'sender':   self.me,
                'receiver': self.active_chat,
                'text':     text,
            })
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_key(self, event):
        if event.keysym == 'Return' or not self.active_chat:
            return
        if self.msg_var.get().strip() and not self.is_typing:
            self.is_typing = True
            try:
                self.sio.emit('typing', {'sender': self.me,
                                    'receiver': self.active_chat,
                                    'is_typing': True})
            except Exception:
                pass
        elif not self.msg_var.get().strip():
            self._stop_typing()
        if self.typing_timer:
            self.root.after_cancel(self.typing_timer)
        self.typing_timer = self.root.after(2000, self._stop_typing)

    def _stop_typing(self):
        if self.is_typing and self.active_chat:
            self.is_typing = False
            try:
                self.sio.emit('typing', {'sender': self.me,
                                    'receiver': self.active_chat,
                                    'is_typing': False})
            except Exception:
                pass
        if self.typing_timer:
            self.root.after_cancel(self.typing_timer)
            self.typing_timer = None

    # ── Socket events ─────────────────────────────────────────

    def _bind_socket_events(self):

        @self.sio.event
        def connect():
            self.sio.emit('user_online', {'username': self.me})

        @self.sio.event
        def disconnect():
            self.root.after(0, lambda: self.hdr_status.config(
                text="Reconnecting…", fg=C['accent_red']))

        @self.sio.on('new_message')
        def on_new_message(msg):
            self.root.after(0, lambda: self._on_new_msg(msg))

        @self.sio.on('messages_seen')
        def on_seen(data):
            self.root.after(0, self._mark_all_seen)

        @self.sio.on('typing')
        def on_typing(data):
            self.root.after(0, lambda: self._show_typing(data))

        @self.sio.on('user_status')
        def on_user_status(data):
            self.root.after(0, lambda: self._on_user_status(data))

        @self.sio.on('message_deleted')
        def on_message_deleted(data):
            self.root.after(0, lambda: self._remove_bubble(data['msg_id']))

    def _connect(self):
        def go():
            try:
                self.sio.connect(SERVER)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Connection Error",
                    f"Cannot reach server at {SERVER}\n\nStart server.py first!\n\n{e}"))
        threading.Thread(target=go, daemon=True).start()

    def _remove_bubble(self, msg_id):
        """Remove a message bubble from the chat UI."""
        if msg_id in self.msg_widgets:
            outer_frame, _ = self.msg_widgets.pop(msg_id)
            outer_frame.destroy()
            # Refresh scroll region
            self.msg_frame.update_idletasks()
            self.msg_canvas.configure(
                scrollregion=self.msg_canvas.bbox('all'))
        self._load_sidebar()

    def _on_new_msg(self, msg):
        sender   = msg.get('sender', '')
        receiver = msg.get('receiver', '')
        msg_id   = msg.get('id')

        # Avoid rendering duplicate messages
        if msg_id and msg_id in self.msg_widgets:
            self._load_sidebar()
            return

        # The other person in this conversation
        peer = receiver if sender == self.me else sender

        # Show bubble if this conversation is currently open
        if peer == self.active_chat:
            self._add_bubble(msg)
            self._scroll_bottom()
            if sender != self.me:
                try:
                    self.sio.emit('message_seen',
                                  {'sender': sender, 'receiver': self.me})
                except Exception:
                    pass
        self._load_sidebar()

    def _mark_all_seen(self):
        for _, (frame, tick_lbl) in self.msg_widgets.items():
            if tick_lbl:
                tick_lbl.config(text=TICK['seen'], fg=TCLR['seen'])
        self._load_sidebar()

    def _show_typing(self, data):
        if data['sender'] == self.active_chat:
            if data['is_typing']:
                self.typing_lbl.config(
                    text=f"  {data['sender']} is typing…")
            else:
                self.typing_lbl.config(text="")

    def _on_user_status(self, data):
        uname = data['username']
        if uname == self.active_chat:
            if data['online']:
                self.hdr_status.config(text="● Online",
                                       fg=C['accent_green'])
            else:
                self.hdr_status.config(text="● Offline",
                                       fg=C['text_muted'])
        self._load_sidebar()

    def _quit(self):
        try:
            self.sio.disconnect()
        except Exception:
            pass
        self.root.destroy()


# ═════════════════════════════════════════════════════════════
# Entry Point
# ═════════════════════════════════════════════════════════════

def main():
    def on_login(user):
        ChatWindow(user)
    AuthWindow(on_success=on_login)

if __name__ == '__main__':
    main()