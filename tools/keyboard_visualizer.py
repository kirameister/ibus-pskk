#!/usr/bin/env python3
"""
Global Keyboard Visualizer
- Shows a QWERTY keyboard on screen (bottom center)
- Highlights keys on press AND release using global hooks (works even when other windows are focused)
- High contrast theme: black background, white keys, bright yellow highlight on press
- Window is resizable by mouse drag; keyboard scales proportionally
- Requires: pip install pynput
             sudo apt install python3-tk
"""

import argparse
import threading
import tkinter as tk
from pynput import keyboard

# ── Layout ───────────────────────────────────────────────────────────────────
ROWS = [
    ['Esc','F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11','F12'],
    ['`','1','2','3','4','5','6','7','8','9','0','-','=','Bksp'],
    ['Tab','Q','W','E','R','T','Y','U','I','O','P','[',']','\\'],
    ['Caps','A','S','D','F','G','H','J','K','L',';',"'",'Enter'],
    ['Shift','Z','X','C','V','B','N','M',',','.','/','Shift'],
    ['Ctrl','Super','Alt','Space','Alt','Ctrl'],
]

WIDE_KEYS = {
    'Bksp': 2.0, 'Tab': 1.5, '\\': 1.5, 'Caps': 1.8, 'Enter': 2.2,
    'Shift': 2.5, 'Space': 6.0, 'Ctrl': 1.5, 'Super': 1.5, 'Alt': 1.5,
}

# ── Theme ─────────────────────────────────────────────────────────────────────
BG       = '#0a0a0a'
KEY_BG   = '#1c1c1c'
KEY_FG   = '#e8e8e8'
KEY_BORDER = '#444444'
PRESS_BG = '#ffe600'
PRESS_FG = '#000000'

# ── Base key dimensions (reference scale = 1.0) ───────────────────────────────
KEY_W  = 46
KEY_H  = 42
PAD    = 5
RADIUS = 6

# ── Compute natural board size ────────────────────────────────────────────────
def _base_board_size():
    max_rw = max(
        sum(WIDE_KEYS.get(k, 1.0) * KEY_W + PAD for k in row) - PAD
        for row in ROWS
    )
    return int(max_rw + PAD * 2), int(len(ROWS) * (KEY_H + PAD) + PAD)

BASE_W, BASE_H = _base_board_size()

# ── pynput → label ────────────────────────────────────────────────────────────
def pynput_to_label(key):
    try:
        ch = key.char
        if ch is not None:
            return ch.upper()
    except AttributeError:
        pass
    name_map = {
        keyboard.Key.space:     'Space', keyboard.Key.enter:     'Enter',
        keyboard.Key.backspace: 'Bksp',  keyboard.Key.tab:       'Tab',
        keyboard.Key.caps_lock: 'Caps',
        keyboard.Key.shift:     'Shift', keyboard.Key.shift_l:   'Shift',
        keyboard.Key.shift_r:   'Shift',
        keyboard.Key.ctrl:      'Ctrl',  keyboard.Key.ctrl_l:    'Ctrl',
        keyboard.Key.ctrl_r:    'Ctrl',
        keyboard.Key.alt:       'Alt',   keyboard.Key.alt_l:     'Alt',
        keyboard.Key.alt_r:     'Alt',   keyboard.Key.alt_gr:    'Alt',
        keyboard.Key.cmd:       'Super', keyboard.Key.cmd_l:     'Super',
        keyboard.Key.cmd_r:     'Super', keyboard.Key.esc:       'Esc',
        keyboard.Key.f1:  'F1',  keyboard.Key.f2:  'F2',
        keyboard.Key.f3:  'F3',  keyboard.Key.f4:  'F4',
        keyboard.Key.f5:  'F5',  keyboard.Key.f6:  'F6',
        keyboard.Key.f7:  'F7',  keyboard.Key.f8:  'F8',
        keyboard.Key.f9:  'F9',  keyboard.Key.f10: 'F10',
        keyboard.Key.f11: 'F11', keyboard.Key.f12: 'F12',
        keyboard.Key.delete:    'Del',   keyboard.Key.home:      'Home',
        keyboard.Key.end:       'End',   keyboard.Key.page_up:   'PgUp',
        keyboard.Key.page_down: 'PgDn', keyboard.Key.insert:    'Ins',
        keyboard.Key.up:   '↑', keyboard.Key.down:  '↓',
        keyboard.Key.left: '←', keyboard.Key.right: '→',
    }
    return name_map.get(key, None)

CHAR_LABEL = {
    '`':'`', '-':'-', '=':'=', '[':'[', ']':']', '\\':'\\',
    ';':';', "'":"'", ',':',', '.':'.', '/':'/',
    '~':'`', '_':'-', '+':'=', '{':'[', '}':']', '|':'\\',
    ':':';', '"':"'", '<':',', '>':'.', '?':'/',
    '!':'1', '@':'2', '#':'3', '$':'4', '%':'5',
    '^':'6', '&':'7', '*':'8', '(':'9', ')':'0',
}

# ── Rounded rectangle ─────────────────────────────────────────────────────────
def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [
        x1+r, y1,   x2-r, y1,
        x2,   y1,   x2,   y1+r,
        x2,   y2-r, x2,   y2,
        x2-r, y2,   x1+r, y2,
        x1,   y2,   x1,   y2-r,
        x1,   y1+r, x1,   y1,
        x1+r, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)

# ── App ───────────────────────────────────────────────────────────────────────
class KeyboardVisualizer:
    def __init__(self, root, always_on_top=False):
        self.root = root
        self.root.title("Keyboard Visualizer")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(320, 120)

        if always_on_top:
            self.root.attributes('-topmost', True)

        self.key_widgets: dict[str, list] = {}
        self._pressed: set[str] = set()
        self._resize_job = None

        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        self._position_window()
        self._build_keyboard()
        self.canvas.bind('<Configure>', self._on_resize)
        self._start_listener()

    # ── Draw keyboard scaled to current canvas size ───────────────────────────
    def _build_keyboard(self):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10: cw = BASE_W
        if ch < 10: ch = BASE_H

        scale = min(cw / BASE_W, ch / BASE_H)
        kw    = KEY_W  * scale
        kh    = KEY_H  * scale
        pad   = max(2, PAD    * scale)
        r     = max(2, RADIUS * scale)
        fsize = max(6, int(9  * scale))
        font  = ('Courier New', fsize, 'bold')

        self.canvas.delete('all')
        self.key_widgets.clear()

        row_data, max_rw = [], 0
        for row in ROWS:
            rw = sum(WIDE_KEYS.get(k, 1.0) * kw + pad for k in row) - pad
            max_rw = max(max_rw, rw)
            row_data.append((row, rw))

        board_w = max_rw + pad * 2
        board_h = len(ROWS) * (kh + pad) + pad
        ox = (cw - board_w) / 2
        oy = (ch - board_h) / 2

        y = oy + pad
        for row, rw in row_data:
            x = ox + pad + (max_rw - rw) / 2
            for label in row:
                w   = WIDE_KEYS.get(label, 1.0) * kw
                bg  = PRESS_BG if label in self._pressed else KEY_BG
                fg  = PRESS_FG if label in self._pressed else KEY_FG
                rid = rounded_rect(self.canvas, x, y, x+w, y+kh, r,
                                   fill=bg, outline=KEY_BORDER, width=1)
                tid = self.canvas.create_text(x+w/2, y+kh/2,
                                              text=label, fill=fg, font=font)
                self.key_widgets.setdefault(label, []).append(
                    (self.canvas, rid, tid))
                x += w + pad
            y += kh + pad

    # ── Debounced resize ──────────────────────────────────────────────────────
    def _on_resize(self, _event):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(60, self._build_keyboard)

    # ── Initial window position ───────────────────────────────────────────────
    def _position_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - BASE_W) // 2
        y  = sh - BASE_H - 48
        self.root.geometry(f"{BASE_W}x{BASE_H}+{x}+{y}")

    # ── Key highlight ─────────────────────────────────────────────────────────
    def _set_key(self, label, pressed: bool):
        if pressed:
            self._pressed.add(label)
        else:
            self._pressed.discard(label)
        bg = PRESS_BG if pressed else KEY_BG
        fg = PRESS_FG if pressed else KEY_FG
        for (canvas, rid, tid) in self.key_widgets.get(label, []):
            canvas.itemconfig(rid, fill=bg)
            canvas.itemconfig(tid, fill=fg)

    def highlight(self, label, pressed: bool):
        if label:
            self.root.after(0, self._set_key, label, pressed)

    # ── Global keyboard listener ──────────────────────────────────────────────
    def _start_listener(self):
        def resolve(key):
            label = pynput_to_label(key)
            if label is None:
                try:
                    label = CHAR_LABEL.get(key.char,
                                           key.char.upper() if key.char else None)
                except AttributeError:
                    pass
            return label

        def on_press(key):   self.highlight(resolve(key), True)
        def on_release(key): self.highlight(resolve(key), False)

        threading.Thread(
            target=lambda: keyboard.Listener(
                on_press=on_press, on_release=on_release).run(),
            daemon=True,
        ).start()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Global Keyboard Visualizer')
    parser.add_argument('--on-top', action='store_true',
                        help='Keep the window always on top of other windows')
    args = parser.parse_args()

    root = tk.Tk()
    KeyboardVisualizer(root, always_on_top=args.on_top)
    root.mainloop()
