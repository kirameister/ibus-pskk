# ibus-pskk - PSKK for IBus
#
# Copyright (c) 2017-2021 Esrille Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
from gi.repository import GLib

logger = logging.getLogger(__name__)

keysyms = IBus

MODIFIERS = (keysyms.Shift_L, keysyms.Shift_R, keysyms.Control_L, keysyms.Control_R, keysyms.Alt_L, keysyms.Alt_R)

SHIFT_L_BIT = 0x01
SHIFT_R_BIT = 0x02
CONTROL_L_BIT = 0x04
CONTROL_R_BIT = 0x08
ALT_L_BIT = 0x10
ALT_R_BIT = 0x20
SPACE_BIT = 0x40
PREFIX_BIT = 0x80
SHIFT_BITS = SHIFT_L_BIT | SHIFT_R_BIT
MODIFIER_BITS = SHIFT_BITS | CONTROL_L_BIT | CONTROL_R_BIT | ALT_L_BIT | ALT_R_BIT | SPACE_BIT

DUAL_SHIFT_L_BIT = SHIFT_L_BIT << 8
DUAL_SHIFT_R_BIT = SHIFT_R_BIT << 8
DUAL_CONTROL_R_BIT = CONTROL_R_BIT << 8
DUAL_ALT_R_BIT = ALT_R_BIT << 8
DUAL_SPACE_BIT = SPACE_BIT << 8
DUAL_BITS = DUAL_SPACE_BIT | DUAL_SHIFT_L_BIT | DUAL_SHIFT_R_BIT | DUAL_CONTROL_R_BIT | DUAL_ALT_R_BIT

NOT_DUAL_SHIFT_L_BIT = SHIFT_L_BIT << 16
NOT_DUAL_SHIFT_R_BIT = SHIFT_R_BIT << 16
NOT_DUAL_CONTROL_R_BIT = CONTROL_R_BIT << 16
NOT_DUAL_ALT_R_BIT = ALT_R_BIT << 16
NOT_DUAL_SPACE_BIT = SPACE_BIT << 16


class Event:
    #def __init__(self, engine, delay, layout):
    def __init__(self, engine, layout):
        self._engine = engine

        # Set to the default values
        self._OnOffByCaps = True               # or False
        self._SandS = False                    # True if SandS is used
        self._Henkan = keysyms.VoidSymbol      # or keysyms.Henkan, keysyms.space
        self._Muhenkan = keysyms.VoidSymbol    # or keysyms.Muhenkan
        self._Eisuu = keysyms.VoidSymbol       # or keysyms.Eisu_toggle
        self._Kana = keysyms.VoidSymbol        # or keysyms.Hiragana_Katakana, keysyms.Control_R
        self._Space = keysyms.VoidSymbol       # Extra space key
        self._Prefix = False                   # True if Shift is to be prefixed
        self._HasYen = False
        self._DualBits = DUAL_SHIFT_L_BIT

        if layout.get("Keyboard") == "109":
            self._Kana = keysyms.Hiragana_Katakana
            self._Eisuu = keysyms.Eisu_toggle

        self._OnOffByCaps = layout.get("OnOffByCaps", self._OnOffByCaps)
        self._HasYen = layout.get("HasYen", self._HasYen)

        self._SandS = layout.get("SandS", False)
        if self._SandS:
            self._DualBits |= DUAL_SPACE_BIT
        else:
            self._Prefix = layout.get("Prefix", False)
            if self._Prefix:
                self._DualBits |= DUAL_SPACE_BIT

        if "Space" in layout:
            self._Space = IBus.keyval_from_name(layout["Space"])
        if "Henkan" in layout:
            self._Henkan = IBus.keyval_from_name(layout["Henkan"])
        if "Muhenkan" in layout:
            self._Muhenkan = IBus.keyval_from_name(layout["Muhenkan"])
        if "Katakana" in layout:
            self._Kana = IBus.keyval_from_name(layout["Katakana"])

        # Check dual role modifiers
        self._capture_alt_r = False
        for k in (self._Henkan, self._Muhenkan, self._Kana, self._Space):
            if k in MODIFIERS:
                self._DualBits |= DUAL_SHIFT_L_BIT << MODIFIERS.index(k)
            if k == keysyms.Alt_R:
                self._capture_alt_r = True

        # Current event
        self._keyval = keysyms.VoidSymbol
        self._keycode = 0
        self.reset()

    def reset(self):
        self._state = 0
        self._modifiers = 0

    def is_key(self, keyval):
        if keyval == keysyms.VoidSymbol:
            return False
        if not self.is_modifier() and keyval == self._keyval:
            return True
        if keyval == keysyms.Shift_L and (self._modifiers & DUAL_SHIFT_L_BIT):
            return True
        if keyval == keysyms.Shift_R and (self._modifiers & DUAL_SHIFT_R_BIT):
            return True
        if keyval == keysyms.Control_R and (self._modifiers & DUAL_CONTROL_R_BIT):
            return True
        if keyval == keysyms.Alt_R and (self._modifiers & DUAL_ALT_R_BIT):
            return True
        return False

    def is_space(self):
        if self.is_key(self._Space):
            return True
        return self._keyval == keysyms.space

    def is_backspace(self):
        return self._keyval == keysyms.BackSpace

    def is_ascii(self):
        # keysyms.yen is treated as '¥' for Japanese 109 keyboard.
        return keysyms.exclam <= self._keyval and self._keyval <= keysyms.asciitilde or \
               self._keyval == keysyms.yen or self.is_space()

    def is_modifier(self):
        return self._keyval in MODIFIERS

    def is_shift(self):
        mask = SHIFT_BITS
        if self._SandS and (self._modifiers & SPACE_BIT):
            return True
        if self._Prefix and (self._modifiers & (SPACE_BIT | PREFIX_BIT)):
            return True
        if self._keyval == keysyms.Shift_R and (self._modifiers & DUAL_SHIFT_R_BIT):
            mask &= ~SHIFT_R_BIT
        if self._keyval == keysyms.Shift_L and (self._modifiers & DUAL_SHIFT_L_BIT):
            mask &= ~SHIFT_L_BIT
        if self._modifiers & mask:
            return True
        return False

    def is_katakana(self):
        return self.is_key(self._Kana)

    def is_henkan(self):
        if self.is_key(self._Henkan) or self.is_key(keysyms.Henkan) or self.is_key(keysyms.Hangul):
            return not self.is_shift()
        return False

    def is_muhenkan(self):
        if self.is_key(self._Muhenkan):
            return True
        if self.is_key(self._Henkan) or self.is_key(keysyms.Henkan) or self.is_key(keysyms.Hangul):
            return self.is_shift()
        return False

    def is_suffix(self):
        return self._modifiers & DUAL_SHIFT_L_BIT

    def is_dual_role(self):
        return self._modifiers & DUAL_BITS

    def process_key_event(self, keyval, keycode, state):
        '''
        This function is called from Engine.do_process_key_event()
        '''
        logger.debug(f'process_key_event("{IBus.keyval_name(keyval)}", {keyval:#04x}, {keycode:#04x}, {state:#010x}) {self._modifiers:#07x}')
        alt_gr = False

        # Ignore XFree86 anomaly.
        if keyval == keysyms.ISO_Left_Tab:
            keyval = keysyms.Tab
        elif keyval == keysyms.Meta_L:
            # [Shift]-[Alt_L]
            keyval = keysyms.Alt_L
        elif keyval in (keysyms.Meta_R, keysyms.ISO_Level3_Shift):
            # [Shift]-[Alt_R] or [AltGr]
            alt_gr = True
            keyval = keysyms.Alt_R

        self._modifiers &= ~DUAL_BITS
        is_press = ((state & IBus.ModifierType.RELEASE_MASK) == 0)
        if(not is_press):
            logger.debug(f'process_key_event -- key released {IBus.keyval_name(keyval)}')
        if is_press:
            if keyval == keysyms.space:
                if self._modifiers & MODIFIER_BITS:
                    self._modifiers |= NOT_DUAL_SPACE_BIT
                else:
                    self._modifiers &= ~NOT_DUAL_SPACE_BIT
                self._modifiers |= SPACE_BIT
            elif keyval == keysyms.Shift_L:
                if self._modifiers & MODIFIER_BITS:
                    self._modifiers |= NOT_DUAL_SHIFT_L_BIT
                else:
                    self._modifiers &= ~NOT_DUAL_SHIFT_L_BIT
                self._modifiers |= SHIFT_L_BIT
            elif keyval == keysyms.Shift_R:
                if self._modifiers & MODIFIER_BITS:
                    self._modifiers |= NOT_DUAL_SHIFT_R_BIT
                else:
                    self._modifiers &= ~NOT_DUAL_SHIFT_R_BIT
                self._modifiers |= SHIFT_R_BIT
            elif keyval == keysyms.Control_L:
                self._modifiers |= CONTROL_L_BIT
            elif keyval == keysyms.Control_R:
                if self._modifiers & MODIFIER_BITS:
                    self._modifiers |= NOT_DUAL_CONTROL_R_BIT
                else:
                    self._modifiers &= ~NOT_DUAL_CONTROL_R_BIT
                self._modifiers |= CONTROL_R_BIT
            elif keyval == keysyms.Alt_R:
                if self._modifiers & MODIFIER_BITS:
                    self._modifiers |= NOT_DUAL_ALT_R_BIT
                else:
                    self._modifiers &= ~NOT_DUAL_ALT_R_BIT
                self._modifiers |= ALT_R_BIT

            if (self._modifiers & SPACE_BIT) and keyval != keysyms.space:
                self._modifiers |= NOT_DUAL_SPACE_BIT
            if (self._modifiers & SHIFT_L_BIT) and keyval != keysyms.Shift_L:
                self._modifiers |= NOT_DUAL_SHIFT_L_BIT
            if (self._modifiers & SHIFT_R_BIT) and keyval != keysyms.Shift_R:
                self._modifiers |= NOT_DUAL_SHIFT_R_BIT
            if (self._modifiers & CONTROL_R_BIT) and keyval != keysyms.Control_R:
                self._modifiers |= NOT_DUAL_CONTROL_R_BIT
            if (self._modifiers & ALT_R_BIT) and keyval != keysyms.Alt_R:
                self._modifiers |= NOT_DUAL_ALT_R_BIT

            # Check CAPS LOCK for IME on/off
            '''
            if self._OnOffByCaps:
                if keyval == keysyms.Caps_Lock:
                    # Note CAPS LOCK LED is turned off after the key release event.
                    if state & IBus.ModifierType.LOCK_MASK:
                        logger.debug(f'process_key_event -- state')
                        self._engine.disable_ime()
                    else:
                        self._engine.enable_ime()
                    return True
                elif not self._engine.is_overridden():
                    if state & IBus.ModifierType.LOCK_MASK:
                        self._engine.enable_ime()
                    else:
                        logger.debug(f'process_key_event -- engine is_overridden')
                        self._engine.disable_ime()
            '''

            if keyval in (keysyms.Muhenkan, keysyms.Hangul_Hanja):
                # [無変換], [A]
                if self._modifiers & SHIFT_BITS:
                    mode = 'Ａ'
                elif self._modifiers & (CONTROL_L_BIT | CONTROL_R_BIT):
                    mode = {
                        'ア': 'ｱ',
                        'ｱ': 'あ',
                        'あ': 'ア'
                    }.get(self._engine.get_mode(), 'あ')
                else:
                    mode = 'A'
                if self._engine.set_mode(mode, True):
                    return True
            elif keyval in (keysyms.Henkan, keysyms.Hangul, keysyms.Hiragana_Katakana):
                # [変換], [あ], [ひらがな]
                if not self._engine.is_lookup_table_visible():
                    mode = 'あ'
                    if keyval == keysyms.Hiragana_Katakana and (self._modifiers & SHIFT_BITS):
                        mode = 'ア'
                    if self._engine.set_mode(mode, True):
                        return True
            elif keyval in (self._Eisuu, keysyms.Zenkaku_Hankaku):
                # [英数], [全角/半角]
                mode = 'A' if self._engine.get_mode() != 'A' else 'あ'
                self._engine.set_mode(mode)
                return True

        else: # NOT is_press

            if keyval == keysyms.space:
                if not (self._modifiers & NOT_DUAL_SPACE_BIT):
                    self._modifiers |= DUAL_SPACE_BIT
                self._modifiers &= ~SPACE_BIT
            elif keyval == keysyms.Shift_L:
                if not (self._modifiers & NOT_DUAL_SHIFT_L_BIT):
                    self._modifiers |= DUAL_SHIFT_L_BIT
                self._modifiers &= ~SHIFT_L_BIT
            elif keyval == keysyms.Shift_R:
                if not (self._modifiers & NOT_DUAL_SHIFT_R_BIT):
                    self._modifiers |= DUAL_SHIFT_R_BIT
                self._modifiers &= ~SHIFT_R_BIT
            elif keyval == keysyms.Control_L:
                self._modifiers &= ~CONTROL_L_BIT
            elif keyval == keysyms.Control_R:
                if not (self._modifiers & NOT_DUAL_CONTROL_R_BIT):
                    self._modifiers |= DUAL_CONTROL_R_BIT
                self._modifiers &= ~CONTROL_R_BIT
            elif keyval == keysyms.Alt_R:
                if not (self._modifiers & NOT_DUAL_ALT_R_BIT):
                    self._modifiers |= DUAL_ALT_R_BIT
                self._modifiers &= ~ALT_R_BIT

        if self._engine.is_enabled():
            if self._SandS:
                if (self._modifiers & SPACE_BIT) and keyval == keysyms.space:
                    return True
            elif self._Prefix:
                if (self._modifiers & SPACE_BIT) and keyval == keysyms.space:
                    return True
                if self._modifiers & DUAL_SPACE_BIT:
                    self._modifiers ^= PREFIX_BIT
                    return True

        # Ignore normal key release events
        if not is_press and not (self._modifiers & self._DualBits):
            self._modifiers &= ~PREFIX_BIT
            return False

        if self._engine.is_enabled():
            #if 0 < self._delay:
            #    GLib.timeout_add(self._delay, self.handle_key_event_timeout, keyval, keycode, state)
            #    return True
            return self.handle_key_event(keyval, keycode, state)

        if self.is_dual_role() and alt_gr:
            pass
        elif state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK):
            return False
        self.update_key_event(keyval, keycode, state)
        c = self.chr()
        if c:
            if self._modifiers & ALT_R_BIT:
                # AltGr
                graph = self._engine.handle_alt_graph(keyval, keycode, state, self._modifiers)
                if graph:
                    self._engine.commit_text(IBus.Text.new_from_string(graph))
                return True
            # Commit a remapped character
            if c == '¥' and not self._HasYen:
                c = '\\'
            if c != chr(self._keyval):
                # Note self._engine.forward_key_event does not seem to work with Qt applications.
                self._engine.commit_text(IBus.Text.new_from_string(c))
                return True
        return False

    def handle_key_event_timeout(self, keyval, keycode, state):
        if not self.handle_key_event(keyval, keycode, state):
            self._engine.forward_key_event(keyval, keycode, state)
        # Stop timer by returning False
        return False

    def update_key_event(self, keyval, keycode, state):
        if keyval == keysyms.backslash and keycode == 0x7c:
            # Treat Yen key separately for Japanese 109 keyboard.
            keyval = keysyms.yen
        elif self.is_suffix():
            keyval = keysyms.hyphen
        self._keyval = keyval
        self._keycode = keycode
        self._state = state
        return self._keyval

    def handle_key_event(self, keyval, keycode, state):
        keyval = self.update_key_event(keyval, keycode, state)
        processed = self._engine.handle_key_event(keyval, keycode, state, self._modifiers)
        if state & IBus.ModifierType.RELEASE_MASK:
            self._modifiers &= ~PREFIX_BIT
        if(keyval == keysyms.Alt_R and self._capture_alt_r):
            return True
        if self.is_dual_role():
            # Modifiers have to be further processed.
            return False
        return processed

    def chr(self):
        '''
        This function is returning the chr value of
        the current keyval, which is originally
        given by the Engine.do_process_key_event()
        '''
        c = ''
        if self.is_ascii():
            if self.is_space():
                keyval = keysyms.space
            else:
                keyval = self._keyval
            if keyval == keysyms.yen:
                c = '¥'
            elif keyval == keysyms.asciitilde and self._keycode == 0x0b:
                c = '_'
            else:
                c = chr(keyval)
        return c
