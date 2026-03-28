#!/usr/bin/env python3
"""
Global Keyboard Visualizer
- Shows a QWERTY keyboard on screen (bottom center)
- Highlights keys on press AND release using global hooks (works even when other windows are focused)
- High contrast theme: black background, white keys, bright yellow highlight on press
- Requires: pip install pynput
             sudo apt install python3-tk
"""

import argparse
import tkinter as tk
from pynput import keyboard
import threading

# ── Layout ──────────────────────────────────────────────────────────────────
ROWS = [
    ['Esc','F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11','F12'],
    ['`','1','2','3','4','5','6','7','8','9','0','-','=','Bksp'],
    ['Tab','Q','W','E','R','T','Y','U','I','O','P','[',']','\\'],
    ['Caps','A','S','D','F','G','H','J','K','L',';',"'",'Enter'],
    ['Shift','Z','X','C','V','B','N','M',',','.','/','Shift'],
    ['Ctrl','Super','Alt','Space','Alt','Ctrl'],
]

# Wide keys get extra width multiplier
WIDE_KEYS = {
    'Bksp': 2.0, 'Tab': 1.5, '\\': 1.5, 'Caps': 1.8, 'Enter': 2.2,
    'Shift': 2.5, 'Space': 6.0, 'Ctrl': 1.5, 'Super': 1.5, 'Alt': 1.5,
}

# ── Theme ────────────────────────────────────────────────────────────────────
BG          = '#0a0a0a'   # window / board background
KEY_BG      = '#1c1c1c'   # key face (unpressed)
KEY_FG      = '#e8e8e8'   # key label (unpressed)
KEY_BORDER  = '#444444'
PRESS_BG    = '#ffe600'   # bright yellow when pressed
PRESS_FG    = '#000000'
FONT        = ('Courier New', 9, 'bold')

KEY_W   = 46   # base key width  (px)
KEY_H   = 42   # key height      (px)
PAD     = 5    # gap between keys
RADIUS  = 6    # corner radius

# ── pynput → label name mapping ──────────────────────────────────────────────
def pynput_to_label(key):
    """Convert a pynput key object to the label string used in our layout."""
    try:
        # Regular character keys
        ch = key.char
        if ch is not None:
            return ch.upper()
    except AttributeError:
        pass

    name_map = {
        keyboard.Key.space:       'Space',
        keyboard.Key.enter:       'Enter',
        keyboard.Key.backspace:   'Bksp',
        keyboard.Key.tab:         'Tab',
        keyboard.Key.caps_lock:   'Caps',
        keyboard.Key.shift:       'Shift',
        keyboard.Key.shift_l:     'Shift',
        keyboard.Key.shift_r:     'Shift',
        keyboard.Key.ctrl:        'Ctrl',
        keyboard.Key.ctrl_l:      'Ctrl',
        keyboard.Key.ctrl_r:      'Ctrl',
        keyboard.Key.alt:         'Alt',
        keyboard.Key.alt_l:       'Alt',
        keyboard.Key.alt_r:       'Alt',
        keyboard.Key.alt_gr:      'Alt',
        keyboard.Key.cmd:         'Super',
        keyboard.Key.cmd_l:       'Super',
        keyboard.Key.cmd_r:       'Super',
        keyboard.Key.esc:         'Esc',
        keyboard.Key.f1:  'F1',  keyboard.Key.f2:  'F2',
        keyboard.Key.f3:  'F3',  keyboard.Key.f4:  'F4',
        keyboard.Key.f5:  'F5',  keyboard.Key.f6:  'F6',
        keyboard.Key.f7:  'F7',  keyboard.Key.f8:  'F8',
        keyboard.Key.f9:  'F9',  keyboard.Key.f10: 'F10',
        keyboard.Key.f11: 'F11', keyboard.Key.f12: 'F12',
        keyboard.Key.delete:      'Del',
        keyboard.Key.home:        'Home',
        keyboard.Key.end:         'End',
        keyboard.Key.page_up:     'PgUp',
        keyboard.Key.page_down:   'PgDn',
        keyboard.Key.insert:      'Ins',
        keyboard.Key.up:          '↑',
        keyboard.Key.down:        '↓',
        keyboard.Key.left:        '←',
        keyboard.Key.right:       '→',
    }
    return name_map.get(key, None)

# Punctuation char → label mapping
CHAR_LABEL = {
    '`':'`', '-':'-', '=':'=', '[':'[', ']':']', '\\':'\\',
    ';':';', "'":"'", ',':',', '.':'.', '/':'/',
    '~':'`', '_':'-', '+':'=', '{':'[', '}':']', '|':'\\',
    ':':';', '"':"'", '<':',', '>':'.', '?':'/',
    '!':'1', '@':'2', '#':'3', '$':'4', '%':'5',
    '^':'6', '&':'7', '*':'8', '(':'9', ')':'0',
}


# ── Rounded-rectangle helper ──────────────────────────────────────────────────
def rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    pts = [
        x1+r, y1,   x2-r, y1,
        x2,   y1,   x2,   y1+r,
        x2,   y2-r, x2,   y2,
        x2-r, y2,   x1+r, y2,
        x1,   y2,   x1,   y2-r,
        x1,   y1+r, x1,   y1,
        x1+r, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kwargs)


# ── Main App ─────────────────────────────────────────────────────────────────
class KeyboardVisualizer:
    def __init__(self, root, always_on_top=False):
        self.root = root
        self.root.title("Keyboard Visualizer")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        if always_on_top:
            self.root.attributes('-topmost', True)

        # Map: label → list of (canvas, rect_id, text_id)
        # (some labels like Shift appear more than once)
        self.key_widgets: dict[str, list] = {}

        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)

        self._build_keyboard()
        self._position_window()
        self._start_listener()

    # ── Build visual keyboard ────────────────────────────────────────────────
    def _build_keyboard(self):
        max_row_w = 0
        row_data = []

        for row in ROWS:
            total = sum(WIDE_KEYS.get(k, 1.0) * KEY_W + PAD for k in row) - PAD
            max_row_w = max(max_row_w, total)
            row_data.append((row, total))

        board_w = int(max_row_w + PAD * 2)
        board_h = int(len(ROWS) * (KEY_H + PAD) + PAD)

        self.canvas.config(width=board_w, height=board_h)

        y = PAD
        for row, row_w in row_data:
            x = PAD + (max_row_w - row_w) / 2   # center each row
            for label in row:
                w = int(WIDE_KEYS.get(label, 1.0) * KEY_W)
                rid = rounded_rect(self.canvas, x, y, x+w, y+KEY_H, RADIUS,
                                   fill=KEY_BG, outline=KEY_BORDER, width=1)
                tid = self.canvas.create_text(x + w/2, y + KEY_H/2,
                                              text=label, fill=KEY_FG,
                                              font=FONT)
                entry = (self.canvas, rid, tid)
                self.key_widgets.setdefault(label, []).append(entry)
                x += w + PAD
            y += KEY_H + PAD

    # ── Position at bottom center ────────────────────────────────────────────
    def _position_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ww = self.root.winfo_reqwidth()
        wh = self.root.winfo_reqheight()
        x = (sw - ww) // 2
        y = sh - wh - 48   # 48 px above taskbar
        self.root.geometry(f"+{x}+{y}")

    # ── Highlight helpers (called from listener thread via after) ────────────
    def _set_key(self, label, pressed: bool):
        widgets = self.key_widgets.get(label, [])
        bg = PRESS_BG if pressed else KEY_BG
        fg = PRESS_FG if pressed else KEY_FG
        for (canvas, rid, tid) in widgets:
            canvas.itemconfig(rid, fill=bg)
            canvas.itemconfig(tid, fill=fg)

    def highlight(self, label, pressed: bool):
        if label:
            self.root.after(0, self._set_key, label, pressed)

    # ── pynput listener ──────────────────────────────────────────────────────
    def _start_listener(self):
        def on_press(key):
            label = pynput_to_label(key)
            if label is None:
                # Try char-based fallback
                try:
                    label = CHAR_LABEL.get(key.char, key.char.upper() if key.char else None)
                except AttributeError:
                    pass
            self.highlight(label, True)

        def on_release(key):
            label = pynput_to_label(key)
            if label is None:
                try:
                    label = CHAR_LABEL.get(key.char, key.char.upper() if key.char else None)
                except AttributeError:
                    pass
            self.highlight(label, False)

        t = threading.Thread(
            target=lambda: keyboard.Listener(
                on_press=on_press, on_release=on_release
            ).run(),
            daemon=True,
        )
        t.start()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Global Keyboard Visualizer')
    parser.add_argument(
        '--on-top', action='store_true',
        help='Keep the visualizer window always on top of other windows'
    )
    args = parser.parse_args()

    root = tk.Tk()
    app = KeyboardVisualizer(root, always_on_top=args.on_top)
    root.mainloop()
