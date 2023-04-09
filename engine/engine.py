# ibus-pskk - PSKK for IBus
#
# Using source code derived from
#   ibus-tmpl - The Input Bus template project
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

from dictionary import Dictionary
import event
from event import Event
import util

import gettext
import json
import logging
import os
import queue
import re
import subprocess
import threading
import time

import gi
gi.require_version('IBus', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, IBus

keysyms = IBus

logger = logging.getLogger(__name__)

_ = lambda a: gettext.dgettext(util.get_package_name(), a)

HIRAGANA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんゔがぎぐげござじずぜぞだぢづでどばびぶべぼぁぃぅぇぉゃゅょっぱぴぷぺぽゎゐゑ・ーゝゞ"
KATAKANA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンヴガギグゲゴザジズゼゾダヂヅデドバビブベボァィゥェォャュョッパピプペポヮヰヱ・ーヽヾ"

TO_KATAKANA = str.maketrans(HIRAGANA, KATAKANA)

NON_DAKU = 'あいうえおかきくけこさしすせそたちつてとはひふへほやゆよアイウエオカキクケコサシスセソタチツテトハヒフヘホヤユヨぁぃぅぇぉがぎぐげござじずぜぞだぢづでどばびぶべぼゃゅょァィゥェォガギグゲゴザジズゼゾダヂヅデドバビブベボャュョゔヴゝヽゞヾ'
DAKU = 'ぁぃぅぇぉがぎぐげござじずぜぞだぢづでどばびぶべぼゃゅょァィゥェォガギグゲゴザジズゼゾダヂヅデドバビブベボャュョあいゔえおかきくけこさしすせそたちつてとはひふへほやゆよアイヴエオカキクケコサシスセソタチツテトハヒフヘホヤユヨうウゞヾゝヽ'

NON_HANDAKU = 'はひふへほハヒフヘホぱぴぷぺぽパピプペポ'
HANDAKU = 'ぱぴぷぺぽパピプペポはひふへほハヒフヘホ'

ZENKAKU = ''.join(chr(i) for i in range(0xff01, 0xff5f)) + '　〔〕［］￥？'
HANKAKU = ''.join(chr(i) for i in range(0x21, 0x7f)) + ' ❲❳[]¥?'

TO_HANKAKU = str.maketrans(ZENKAKU, HANKAKU)
TO_ZENKAKU = str.maketrans(HANKAKU, ZENKAKU)

RE_SOKUON = re.compile(r'[kstnhmyrwgzdbpfjv]')

NAME_TO_LOGGING_LEVEL = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

INPUT_MODE_NAMES = ('A', 'あ')

CANDIDATE_FOREGROUND_COLOR = 0x000000
CANDIDATE_BACKGROUND_COLOR = 0xd1eaff

# There are several applications that claim to support
# IBus.Capabilite.SURROUNDING_TEXT but actually don't;
# e.g. Google Chrome v93.0.
# Those applications are marked as SURROUNDING_BROKEN.
# 'focus_in', 'focus_out' and 'reset' signals from those
# applications need to be ignored for Kana-Kanji
# conversion in the legacy mode.
SURROUNDING_RESET = 0
SURROUNDING_COMMITTED = 1
SURROUNDING_SUPPORTED = 2
SURROUNDING_NOT_SUPPORTED = -1
SURROUNDING_BROKEN = -2

# Web applications running on web browsers sometimes need a short delay
# between delete_surrounding_text() and commit_text(), and between
# multiple forward_key_event().
# Gmail running on Firefox 91.0.2 is an example of such an application.
EVENT_DELAY = 0.02


def to_katakana(kana):
    return kana.translate(TO_KATAKANA)


def to_hankaku(kana):
    s = ''
    for c in kana:
        c = c.translate(TO_HANKAKU)
        s += {
            '。': '｡', '「': '｢', '」': '｣', '、': '､', '・': '･',
            'ヲ': 'ｦ',
            'ァ': 'ｧ', 'ィ': 'ｨ', 'ゥ': 'ｩ', 'ェ': 'ｪ', 'ォ': 'ｫ',
            'ャ': 'ｬ', 'ュ': 'ｭ', 'ョ': 'ｮ',
            'ッ': 'ｯ', 'ー': 'ｰ',
            'ア': 'ｱ', 'イ': 'ｲ', 'ウ': 'ｳ', 'エ': 'ｴ', 'オ': 'ｵ',
            'カ': 'ｶ', 'キ': 'ｷ', 'ク': 'ｸ', 'ケ': 'ｹ', 'コ': 'ｺ',
            'サ': 'ｻ', 'シ': 'ｼ', 'ス': 'ｽ', 'セ': 'ｾ', 'ソ': 'ｿ',
            'タ': 'ﾀ', 'チ': 'ﾁ', 'ツ': 'ﾂ', 'テ': 'ﾃ', 'ト': 'ﾄ',
            'ナ': 'ﾅ', 'ニ': 'ﾆ', 'ヌ': 'ﾇ', 'ネ': 'ﾈ', 'ノ': 'ﾉ',
            'ハ': 'ﾊ', 'ヒ': 'ﾋ', 'フ': 'ﾌ', 'ヘ': 'ﾍ', 'ホ': 'ﾎ',
            'マ': 'ﾏ', 'ミ': 'ﾐ', 'ム': 'ﾑ', 'メ': 'ﾒ', 'モ': 'ﾓ',
            'ヤ': 'ﾔ', 'ユ': 'ﾕ', 'ヨ': 'ﾖ',
            'ラ': 'ﾗ', 'リ': 'ﾘ', 'ル': 'ﾙ', 'レ': 'ﾚ', 'ロ': 'ﾛ',
            #'ワ': 'ﾜ', 'ン': 'ﾝ', '゙': 'ﾞ', '゚': 'ﾟ',
            'ガ': 'ｶﾞ', 'ギ': 'ｷﾞ', 'グ': 'ｸﾞ', 'ゲ': 'ｹﾞ', 'ゴ': 'ｺﾞ',
            'ザ': 'ｻﾞ', 'ジ': 'ｼﾞ', 'ズ': 'ｽﾞ', 'ゼ': 'ｾﾞ', 'ゾ': 'ｿﾞ',
            'ダ': 'ﾀﾞ', 'ヂ': 'ﾁﾞ', 'ヅ': 'ﾂﾞ', 'デ': 'ﾃﾞ', 'ド': 'ﾄﾞ',
            'バ': 'ﾊﾞ', 'ビ': 'ﾋﾞ', 'ブ': 'ﾌﾞ', 'ベ': 'ﾍﾞ', 'ボ': 'ﾎﾞ',
            'パ': 'ﾊﾟ', 'ピ': 'ﾋﾟ', 'プ': 'ﾌﾟ', 'ペ': 'ﾍﾟ', 'ポ': 'ﾎﾟ',
            'ヴ': 'ｳﾞ'
        }.get(c, c)
    return s


def to_zenkaku(asc):
    return asc.translate(TO_ZENKAKU)


class EnginePSKK(IBus.Engine):
    __gtype_name__ = 'EnginePSKK'

    def __init__(self):
        super().__init__()
        self._mode = 'A'  # _mode must be one of _input_mode_names
        self._override = False

        self._layout = dict()
        self._to_kana = self._handle_default_layout

        self._preedit_string = ''   # in rômazi
        self._previous_text = ''
        self._shrunk = []
        self._surrounding = SURROUNDING_RESET

        # This property is for confirming the kanji-kana converted string
        self._lookup_table = IBus.LookupTable.new(10, 0, True, False)
        self._lookup_table.set_orientation(IBus.Orientation.VERTICAL)

        self._init_props()

        self._settings = Gio.Settings.new('org.freedesktop.ibus.engine.pskk')
        self._settings.connect('changed', self._config_value_changed_cb)

        # load configs
        self._load_configs()
        #self._config = util.get_config_data()
        #self._logging_level = self._load_logging_level(self._config)
        self._dict = self._load_dictionary(self._settings)
        self._layout = self._load_layout(self._settings)
        self._event = Event(self, self._layout)

        self.set_mode(self._load_input_mode(self._settings))
        #self.character_after_n = "aiueo'wy"

        self.connect('set-cursor-location', self.set_cursor_location_cb)

        self._about_dialog = None
        self._q = queue.Queue()

    def _init_props(self):
        self._prop_list = IBus.PropList()
        self._input_mode_prop = IBus.Property(
            key='InputMode',
            prop_type=IBus.PropType.MENU,
            symbol=IBus.Text.new_from_string(self._mode),
            label=IBus.Text.new_from_string(_("Input mode (%s)") % self._mode),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        self._input_mode_prop.set_sub_props(self._init_input_mode_props())
        self._prop_list.append(self._input_mode_prop)
        prop = IBus.Property(
            key='About',
            prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string(_("About PSKK...")),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        self._prop_list.append(prop)

    def _init_input_mode_props(self):
        props = IBus.PropList()
        props.append(IBus.Property(key='InputMode.Alphanumeric',
                                   prop_type=IBus.PropType.RADIO,
                                   label=IBus.Text.new_from_string(_("Alphanumeric (A)")),
                                   icon=None,
                                   tooltip=None,
                                   sensitive=True,
                                   visible=True,
                                   state=IBus.PropState.CHECKED,
                                   sub_props=None))
        props.append(IBus.Property(key='InputMode.Hiragana',
                                   prop_type=IBus.PropType.RADIO,
                                   label=IBus.Text.new_from_string(_("Hiragana (あ)")),
                                   icon=None,
                                   tooltip=None,
                                   sensitive=True,
                                   visible=True,
                                   state=IBus.PropState.UNCHECKED,
                                   sub_props=None))
        return props

    def _update_input_mode(self):
        self._input_mode_prop.set_symbol(IBus.Text.new_from_string(self._mode))
        self._input_mode_prop.set_label(IBus.Text.new_from_string(_("Input mode (%s)") % self._mode))
        self.update_property(self._input_mode_prop)

    def do_property_activate(self, prop_name, state):
        logger.info(f'property_activate({prop_name}, {state})')
        if prop_name == 'About':
            if self._about_dialog:
                self._about_dialog.present()
                return
            dialog = Gtk.AboutDialog()
            dialog.set_program_name(_("PSKK"))
            dialog.set_copyright("Copyright 2021-2022 Akira K.")
            dialog.set_authors(["Akira K."])
            dialog.set_documenters(["Akira K."])
            dialog.set_website("file://" + os.path.join(util.get_datadir(), "help/index.html"))
            dialog.set_website_label(_("Introduction to PSKK"))
            dialog.set_logo_icon_name(util.get_package_name())
            dialog.set_default_icon_name(util.get_package_name())
            dialog.set_version(util.get_version())
            dialog.set_comments(_("config files location : ${HOME}/.config/ibus-pskk"))
            # To close the dialog when "close" is clicked, e.g. on RPi,
            # we connect the "response" signal to about_response_callback
            dialog.connect("response", self.about_response_callback)
            self._about_dialog = dialog
            dialog.show()
        elif prop_name.startswith('InputMode.'):
            if state == IBus.PropState.CHECKED:
                mode = {
                    'InputMode.Alphanumeric': 'A',
                    'InputMode.Hiragana': 'あ',
                }.get(prop_name, 'A')
                self.set_mode(mode, True)

    def _load_configs(self):
        self._config = util.get_config_data()
        self._logging_level = self._load_logging_level(self._config)
        # loading layout should be part of (re-)loading config
        self._layout = self._load_layout(self._settings)
        self._event = Event(self, self._layout)

    def about_response_callback(self, dialog, response):
        dialog.destroy()
        self._about_dialog = None

    def _load_input_mode(self, settings):
        mode = settings.get_string('mode')
        if mode not in INPUT_MODE_NAMES:
            mode = 'A'
            settings.reset('mode')
        logger.info(f'input mode: {mode}')
        return mode

    def _load_logging_level(self, config):
        level = 'WARNING' # default value
        if 'logging_level' in config:
            level = config['logging_level']
        if level not in NAME_TO_LOGGING_LEVEL:
            level = 'WARNING'
        logger.info(f'logging_level: {level}')
        logging.getLogger().setLevel(NAME_TO_LOGGING_LEVEL[level])
        return level

    def _load_dictionary(self, settings, clear_history=False):
        path = settings.get_string('dictionary')
        user = settings.get_string('user-dictionary')
        return Dictionary(path, user, clear_history)

    def _load_layout(self, settings):
        default_layout = os.path.join(util.get_datadir(), 'layouts')
        default_layout = os.path.join(default_layout, 'roomazi.json')
        path = settings.get_string('layout')
        logger.info(f'layout: {path}')
        layout = dict()
        try:
            with open(path) as f:
                layout = json.load(f)
        except Exception as error:
            logger.error(error)
        if not layout:
            try:
                with open(default_layout) as f:
                    layout = json.load(f)
            except Exception as error:
                logger.error(error)
        return layout

    def _preedit_to_yomi(self, preedit, keyval, state=0, modifiers=0):
        yomi = ''
        c = self._evnet.chr().lower()
        preedit += c
        if(preedit in self._layout['layout']):
            # FIXME why += instead of = ?
            yomi += self._layout['layout'][preedit]
            preedit = ''
        return(yomi, preedit)


    def _config_value_changed_cb(self, settings, key):
        logger.debug(f'config_value_changed("{key}")')
        if key == 'mode':
            self.set_mode(self._load_input_mode(settings), True)

    def _handle_default_layout(self, preedit, keyval, state=0, modifiers=0):
        return self._event.chr(), ''

    def _handle_roomazi_layout(self, preedit, keyval, state=0, modifiers=0):
        yomi = ''
        c = self._event.chr().lower()
        # most probably this part could be handled by some sort of
        # smart algorithm..
        #if preedit == 'n' and self.character_after_n.find(c) < 0:
        #    yomi = 'ん'
        #    preedit = preedit[1:]
        preedit += c
        if preedit in self._layout['Roomazi']:
            yomi += self._layout['Roomazi'][preedit]
            preedit = ''
        elif 2 <= len(preedit) and preedit[0] == preedit[1] and RE_SOKUON.search(preedit[1]):
            yomi += 'っ'
            preedit = preedit[1:]
        return yomi, preedit

    def _get_surrounding_text(self):
        if not (self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT):
            self._surrounding = SURROUNDING_NOT_SUPPORTED

        if self._surrounding != SURROUNDING_SUPPORTED:
            # Call get_surrounding_text() anyway to see if the surrounding
            # text is supported in the current client.
            self.get_surrounding_text()
            logger.debug(f'surrounding text: "{self._previous_text}"')
            return self._previous_text, len(self._previous_text)

        tuple = self.get_surrounding_text()
        text = tuple[0].get_text()
        pos = tuple[1]

        # Qt reports pos as if text is in UTF-16 while GTK reports pos in sane manner.
        # If you're using primarily Qt, use the following code to amend the issue
        # when a character in Unicode supplementary planes is included in text.
        #
        # Deal with surrogate pair manually. (Qt bug?)
        # for i in range(len(text)):
        #     if pos <= i:
        #         break
        #     if 0x10000 <= ord(text[i]):
        #         pos -= 1

        # Qt seems to insert self._preedit_string to the text, while GTK doesn't.
        # We mimic GTK's behavior here.
        preedit_len = len(self._preedit_string)
        if 0 < preedit_len and preedit_len <= pos and text[pos - preedit_len:pos] == self._preedit_string:
            text = text[:-preedit_len]
            pos -= preedit_len
        logger.debug(f'surrounding text: "{text}", {pos}, "{self._previous_text}"')
        return text, pos

    def _delete_surrounding_text(self, size):
        if self._surrounding == SURROUNDING_SUPPORTED:
            self.delete_surrounding_text(-size, size)
        else:
            self._previous_text = self._previous_text[:-size]

    def is_overridden(self):
        return self._override

    def is_enabled(self):
        return self.get_mode() != 'A'

    def enable_ime(self, override=False):
        if not self.is_enabled():
            self.set_mode('あ', override)
            return True
        return False

    def disable_ime(self, override=False):
        if self.is_enabled():
            self.set_mode('A', override)
            return True
        return False

    def get_mode(self):
        return self._mode

    def set_mode(self, mode, override=False):
        self._override = override
        if self._mode == mode:
            return False
        logger.debug(f'set_mode({mode})')
        self._preedit_string = ''
        self._commit()
        self._mode = mode
        self._update_preedit()
        self._update_lookup_table()
        self._update_input_mode()
        return True

    def do_process_key_event(self, keyval, keycode, state):
        return self._event.process_key_event(keyval, keycode, state)

    def handle_alt_graph(self, keyval, keycode, state, modifiers):
        logger.debug(f'handle_alt_graph("{self._event.chr()}")')
        c = self._event.chr().lower()
        if not c:
            return c
        if not self._event.is_shift():
            return self._layout['\\Normal'].get(c, '')
        if '\\Shift' in self._layout:
            return self._layout['\\Shift'].get(c, '')
        if modifiers & event.SHIFT_L_BIT:
            return self._layout['\\ShiftL'].get(c, '')
        if modifiers & event.SHIFT_R_BIT:
            return self._layout['\\ShiftR'].get(c, '')

    def handle_key_event(self, keyval, keycode, state, modifiers):
        logger.debug(f'handle_key_event("{IBus.keyval_name(keyval)}", {keyval:#04x}, {keycode:#04x}, {state:#010x}, {modifiers:#07x})')
        if self._event.is_dual_role():
            pass
        elif self._event.is_modifier():
            # Ignore modifier keys
            return False
        elif state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK):
            self._commit()
            return False

        self._check_surrounding_support()

        # Handle Candidate window
        if 0 < self._lookup_table.get_number_of_candidates():
            if keyval in (keysyms.Page_Up, keysyms.KP_Page_Up):
                return self.do_page_up()
            elif keyval in (keysyms.Page_Down, keysyms.KP_Page_Down):
                return self.do_page_down()
            elif keyval == keysyms.Up or self._event.is_muhenkan():
                return self.do_cursor_up()
            elif keyval == keysyms.Down or self._event.is_henkan():
                return self.do_cursor_down()

        if self._preedit_string:
            if keyval == keysyms.Return:
                if self._preedit_string == 'n':
                    self._preedit_string = 'ん'
                self._commit_string(self._preedit_string)
                self._preedit_string = ''
                self._update_preedit()
                return True
            if keyval == keysyms.Escape:
                self._preedit_string = ''
                self._update_preedit()
                return True

        if self._dict.current():
            if keyval == keysyms.Tab:
                if not self._event.is_shift():
                    return self.handle_shrink()
                else:
                    return self.handle_expand()
            if keyval == keysyms.Escape:
                self._handle_escape()
                self._update_preedit()
                return True
            if keyval == keysyms.Return:
                self._commit()
                return True

        # Handle Japanese text
        if (self._event.is_henkan() or self._event.is_muhenkan()) and not(modifiers & event.ALT_R_BIT):
            return self.handle_replace()
        if self._dict.current():
            self._commit()
        yomi = ''
        if self._event.is_katakana():
            self.handle_katakana()
            return True
        if self._event.is_backspace():
            if 1 <= len(self._preedit_string):
                self._preedit_string = self._preedit_string[:-1]
                self._update_preedit()
                return True
            if self._previous_text:
                self._previous_text = self._previous_text[:-1]
                self._update_preedit()
                return True
            return False
        if self._event.is_ascii():
            if modifiers & event.ALT_R_BIT:
                yomi = self.handle_alt_graph(keyval, keycode, state, modifiers)
                if yomi:
                    if self.get_mode() != 'ｱ':
                        yomi = to_zenkaku(yomi)
                    self._preedit_string = ''
            elif self.get_mode() == 'Ａ':
                yomi = to_zenkaku(self._event.chr())
            else:
                yomi, self._preedit_string = self._to_kana(self._preedit_string, keyval, state, modifiers)
        elif keyval == keysyms.hyphen:
            yomi = '―'
        elif self._previous_text:
            if keyval == keysyms.Escape:
                self._previous_text = ''
            else:
                self._commit()
            self._update_preedit()
            return True
        else:
            return False
        if yomi:
            if self.get_mode() == 'ア':
                yomi = to_katakana(yomi)
            elif self.get_mode() == 'ｱ':
                yomi = to_hankaku(to_katakana(yomi))
            self._commit_string(yomi)
        self._update_preedit()
        return True

    def lookup_dictionary(self, yomi, pos):
        if self._preedit_string == 'n':
            yomi = yomi[:pos] + 'ん'
            pos += 1
        self._lookup_table.clear()
        cand = self._dict.lookup(yomi, pos)
        size = len(self._dict.reading())
        if 0 < size:
            if self._preedit_string == 'n':
                # For FuriganaPad, yomi has to be committed anyway.
                self._commit_string('ん')
            self._preedit_string = ''
            if 1 < len(self._dict.cand()):
                for c in self._dict.cand():
                    self._lookup_table.append_candidate(IBus.Text.new_from_string(c))
        return (cand, size)

    def handle_katakana(self):
        text, pos = self._get_surrounding_text()
        if self._preedit_string == 'n':
            self._preedit_string = ''
            text = text[:pos] + 'ん'
            pos += 1
            self._commit_string('ん')
        for i in reversed(range(pos)):
            if 0 <= KATAKANA.find(text[i]):
                continue
            found = HIRAGANA.find(text[i])
            if 0 <= found:
                self._delete_surrounding_text(pos - i)
                time.sleep(EVENT_DELAY)
                self._commit_string(KATAKANA[found] + text[i + 1:pos])
                self._update_preedit()
            break
        return True

    def handle_replace(self):
        if self._dict.current():
            return True
        text, pos = self._get_surrounding_text()
        if self._event.is_henkan():
            cand, size = self.lookup_dictionary(text, pos)
        elif 1 <= pos:
            assert self._event.is_muhenkan()
            suffix = text[:pos].rfind('―')
            if 0 < suffix:
                cand, size = self.lookup_dictionary(text[suffix - 1:], pos - suffix + 1)
            else:
                cand, size = self.lookup_dictionary(text[pos - 1], 1)
        if self._dict.current():
            self._shrunk = []
            self._delete_surrounding_text(size)
            self._update_preedit(cand)
        return True

    def handle_expand(self):
        assert self._dict.current()
        if not self._shrunk:
            return True
        kana = self._shrunk[-1]
        yomi = self._dict.reading()
        text, pos = self._get_surrounding_text()
        (cand, size) = self.lookup_dictionary(kana + yomi + text[pos:], len(kana + yomi))
        assert 0 < size
        self._delete_surrounding_text(len(kana))
        self._shrunk.pop(-1)
        self._update_preedit(cand)
        return True

    def handle_shrink(self):
        logger.debug(f'handle_shrink: "{self._dict.current()}"')
        assert self._dict.current()
        yomi = self._dict.reading()
        if len(yomi) <= 1 or yomi[1] == '―':
            return True
        text, pos = self._get_surrounding_text()
        (cand, size) = self.lookup_dictionary(yomi[1:] + text[pos:], len(yomi) - 1)
        kana = yomi
        if 0 < size:
            kana = kana[:-size]
            self._shrunk.append(kana)
            self._commit_string(kana)
        else:
            (cand, size) = self.lookup_dictionary(yomi + text[pos:], len(yomi))
        self._update_preedit(cand)
        return True

    def _handle_escape(self):
        assert self._dict.current()
        yomi = self._dict.reading()
        self._reset(False)
        self._commit_string(yomi)

    def _commit(self):
        current = self._dict.current()
        if current:
            self._dict.confirm(''.join(self._shrunk))
            self._dict.reset()
            self._lookup_table.clear()
        text = self._previous_text + current
        self._previous_text = ''
        self._update_preedit()
        if text:
            logger.debug(f'_commit(): "{text}"')
            self.commit_text(IBus.Text.new_from_string(text))

    def _check_surrounding_support(self):
        if self._surrounding == SURROUNDING_COMMITTED:
            logger.debug(f'_check_surrounding_support(): "{self._previous_text}"')
            self._surrounding = SURROUNDING_BROKEN
            # Hide preedit text for a moment so that the current client can
            # process the backspace keys.
            self.update_preedit_text(IBus.Text.new_from_string(''), 0, 0)
            # Note delete_surrounding_text() doesn't work here.
            self._forward_backspaces(len(self._previous_text))

    def _commit_string(self, text):
        if text == '゛':
            prev, pos = self._get_surrounding_text()
            if 0 < pos:
                found = NON_DAKU.find(prev[pos - 1])
                if 0 <= found:
                    self._delete_surrounding_text(1)
                    text = DAKU[found]
                    time.sleep(EVENT_DELAY)
        elif text == '゜':
            prev, pos = self._get_surrounding_text()
            if 0 < pos:
                found = NON_HANDAKU.find(prev[pos - 1])
                if 0 <= found:
                    self._delete_surrounding_text(1)
                    text = HANDAKU[found]
                    time.sleep(EVENT_DELAY)

        if self._surrounding in (SURROUNDING_NOT_SUPPORTED, SURROUNDING_BROKEN):
            self._previous_text += text
            logger.debug(f'_commit_string({text}): legacy ({self._previous_text})')
        else:
            if self._surrounding != SURROUNDING_SUPPORTED:
                self._surrounding = SURROUNDING_COMMITTED
                self._previous_text += text
            self.commit_text(IBus.Text.new_from_string(text))
            logger.debug(f'_commit_string({text}): modeless ({self._surrounding}, {self._previous_text})')

    def _reset(self, full=True):
        self._dict.reset()
        self._lookup_table.clear()
        self._update_lookup_table()
        if full:
            self._previous_text = ''
            self._preedit_string = ''
            self._surrounding = SURROUNDING_RESET
        self._update_preedit()
        assert not self._dict.current()

    def _update_candidate(self):
        index = self._lookup_table.get_cursor_pos()
        self._dict.set_current(index)
        self._update_preedit(self._dict.current())

    def do_page_up(self):
        if self._lookup_table.page_up():
            self._update_candidate()
        return True

    def do_page_down(self):
        if self._lookup_table.page_down():
            self._update_candidate()
        return True

    def do_cursor_up(self):
        if self._lookup_table.cursor_up():
            self._update_candidate()
        return True

    def do_cursor_down(self):
        if self._lookup_table.cursor_down():
            self._update_candidate()
        return True

    def _update_preedit(self, cand=''):
        previous_text = self._previous_text if self._surrounding != SURROUNDING_COMMITTED else ''
        text = IBus.Text.new_from_string(previous_text + cand + self._preedit_string)
        previous_len = len(previous_text)
        cand_len = len(cand)
        preedit_len = len(self._preedit_string)
        text_len = previous_len + cand_len + preedit_len
        attrs = IBus.AttrList() if 0 < text_len else None
        if 0 < previous_len:
            attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE, 0, previous_len))
        if 0 < cand_len:
            assert preedit_len == 0
            attrs.append(IBus.Attribute.new(IBus.AttrType.FOREGROUND, CANDIDATE_FOREGROUND_COLOR, previous_len, previous_len + cand_len))
            attrs.append(IBus.Attribute.new(IBus.AttrType.BACKGROUND, CANDIDATE_BACKGROUND_COLOR, previous_len, previous_len + cand_len))
        if 0 < preedit_len:
            assert cand_len == 0
            attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE, previous_len, previous_len + preedit_len))
        if attrs:
            text.set_attributes(attrs)
        # Note self.hide_preedit_text() does not seem to work as expected with Kate.
        # cf. "Qt5 IBus input context does not implement hide_preedit_text()",
        #     https://bugreports.qt.io/browse/QTBUG-48412
        self.update_preedit_text(text, text_len, 0 < text_len)
        self._update_lookup_table()

    def _update_lookup_table(self):
        if self.is_enabled():
            visible = 0 < self._lookup_table.get_number_of_candidates()
            self.update_lookup_table(self._lookup_table, visible)

    def is_lookup_table_visible(self):
        return 0 < self._lookup_table.get_number_of_candidates()

    def do_focus_in(self):
        logger.info(f'focus_in: {self._surrounding}')
        self._event.reset()
        self.register_properties(self._prop_list)
        self._update_preedit()
        # Request the initial surrounding-text in addition to the "enable" handler.
        if not self._previous_text:
            self._surrounding = SURROUNDING_RESET
        self.get_surrounding_text()

    def do_focus_out(self):
        logger.info(f'focus_out: {self._surrounding}')
        if self._surrounding != SURROUNDING_BROKEN:
            self._reset()
            self._dict.save_orders()

    def do_enable(self):
        logger.info('enable')
        # Request the initial surrounding-text when enabled as documented.
        self.get_surrounding_text()

    def do_disable(self):
        logger.info('disable')
        self._reset()
        self._mode = 'A'
        self._dict.save_orders()

    def do_reset(self):
        logger.info(f'reset: {self._surrounding}')
        if self._surrounding != SURROUNDING_BROKEN:
            self._reset()
        else:
            self._update_preedit()

    def _readline(self, process: subprocess.Popen):
        for line in iter(process.stdout.readline, ''):
            self._q.put(line.strip())
            if process.poll() is not None:
                return

    def set_cursor_location_cb(self, engine, x, y, w, h):
        # On Raspbian, at least till Buster, the candidate window does not
        # always follow the cursor position. The following code is not
        # necessary on Ubuntu 18.04 or Fedora 30.
        logger.debug(f'set_cursor_location_cb({x}, {y}, {w}, {h})')
        self._update_lookup_table()

    def _forward_backspaces(self, size):
        logger.debug(f'_forward_backspaces({size})')
        for i in range(size):
            self.forward_key_event(IBus.BackSpace, 14, 0)
            time.sleep(EVENT_DELAY)
            self.forward_key_event(IBus.BackSpace, 14, IBus.ModifierType.RELEASE_MASK)
