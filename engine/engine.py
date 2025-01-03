# ibus-pskk - PSKK for IBus
#
# Using source code derived from
#   ibus-tmpl - The Input Bus template project
#
# Copyright (c) 2017-2021 Esrille Inc. (ibus-hiragana)
# Modifications Copyright (C) 2021-2024 Akira K.
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
# http://lazka.github.io/pgi-docs/IBus-1.0/index.html?fbclid=IwY2xjawG9hapleHRuA2FlbQIxMAABHXaZwlJVVZEl9rr2SWsvIy2x85xW-XJuu32OZYxQ3gxF-E__9kWOUqGNzA_aem_2zw0hES6WqJcXPds_9CEdA
# http://lazka.github.io/pgi-docs/Gtk-4.0/index.html?fbclid=IwY2xjawG9hatleHRuA2FlbQIxMAABHVsKSY24bv9C75Mweq54yhLsePdGA25YfLnwMwCx7vEq03oV61qn_qEntg_aem_3k1P3ltIMb17cBH0fdPr4w
# http://lazka.github.io/pgi-docs/GLib-2.0/index.html?fbclid=IwY2xjawG9hatleHRuA2FlbQIxMAABHXaZwlJVVZEl9rr2SWsvIy2x85xW-XJuu32OZYxQ3gxF-E__9kWOUqGNzA_aem_2zw0hES6WqJcXPds_9CEdA

logger = logging.getLogger(__name__)

_ = lambda a: gettext.dgettext(util.get_package_name(), a)

KANCHOKU_KEY_SET = set(list('qwertyuiopasdfghjkl;zxcvbnm,./'))
MISSING_KANCHOKU_KANJI = '無'

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

NAME_TO_LOGGING_LEVEL = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

# Only the direct input- and Hiragana-mode are supported (and that's intentional).
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
    '''
    http://lazka.github.io/pgi-docs/IBus-1.0/classes/Engine.html
    '''
    __gtype_name__ = 'EnginePSKK'

    def __init__(self):
        super().__init__()
        self._mode = 'A'  # _mode must be one of _input_mode_names
        self._mode = 'あ'  # I do not like to click extra...
        self._override = False
        self._layout_data = dict() # this is complete data of layout JSON
        self._layout = dict() # this is the modified layout of JSON
        # _layout[INPUT]: {"output": OUTPUT_STR, "pending": PENDING_STR, "simul_limit_ms": INT}
        self._simul_candidate_char_set = set()
        self._if_simul_condition_met = False

        self._origin_timestamp = time.perf_counter()
        self._previous_typed_timestamp = time.perf_counter()
        # SandS vars
        self._sands_key_set = set()
        self._space_pressed = False # this is to hold the SandS state

        self._preedit_string = ''
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
        self._dict = self._load_dictionary(self._settings)
        self._layout_data = self._load_layout() # this will also update self._layout
        self._kanchoku_layout = self._load_kanchoku_layout()
        # This will create an object defined in event.py
        self._event = Event(self, self._layout_data)

        self.set_mode(self._load_input_mode(self._settings))
        self.set_mode('あ')
        #self.character_after_n = "aiueo'wy"

        self.connect('set-cursor-location', self.set_cursor_location_cb)

        self._about_dialog = None
        self._q = queue.Queue()

    def _init_props(self):
        '''
        This function is called as part of the instantiation (__init__). 
        This function creates the GUI menu list (typically top-right corner).

        http://lazka.github.io/pgi-docs/IBus-1.0/classes/PropList.html
        http://lazka.github.io/pgi-docs/IBus-1.0/classes/Property.html
        '''
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
        # This is to add the options for different modes in separate function
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
        '''
        This is a function to produce GUI (sub) component for
        different input modes.
        This function is meant to be only called from _init_props()
        '''
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
        '''
        '''
        logger.info(f'property_activate({prop_name}, {state})')
        if prop_name == 'About':
            if self._about_dialog:
                self._about_dialog.present()
                return
            dialog = Gtk.AboutDialog()
            dialog.set_program_name(_("PSKK"))
            dialog.set_copyright("Copyright 2021-2024 Akira K.")
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
                # At this point, we only support direct input and Hiragana. Nothing else..
                mode = {
                    'InputMode.Alphanumeric': 'A',
                    'InputMode.Hiragana': 'あ',
                }.get(prop_name, 'A')
                self.set_mode(mode, True)

    def _load_configs(self):
        '''
        This function loads the necessary (and optional) configs from the config JSON file
        The logging level value would be set to WARNING, if it's absent in the config JSON.
        '''
        self._config = util.get_config_data()
        self._logging_level = self._load_logging_level(self._config)
        logger.debug('config.json loaded')
        logger.debug(self._config)
        # loading layout should be part of (re-)loading config
        self._layout_data = self._load_layout()
        self._event = Event(self, self._layout_data)

    def about_response_callback(self, dialog, response):
        dialog.destroy()
        self._about_dialog = None

    def _load_input_mode(self, settings):
        # FIXME this should be coming from the config file, not settings...
        mode = settings.get_string('mode')
        if mode not in INPUT_MODE_NAMES:
            mode = 'A'
            settings.reset('mode')
        logger.info(f'input mode: {mode}')
        return mode

    def _load_logging_level(self, config):
        '''
        This function sets the logging level
        which can be obtained from the config.json
        When the value is not present (or incorrect) in config.json,
        warning is used as default.
        '''
        level = 'WARNING' # default value
        if('logging_level' in config):
            level = config['logging_level']
        if(level not in NAME_TO_LOGGING_LEVEL):
            logger.warning(f'Specified logging level {level} is not recognized. Using the default WARNING level.')
            level = 'WARNING'
        logger.info(f'logging_level: {level}')
        logging.getLogger().setLevel(NAME_TO_LOGGING_LEVEL[level])
        return level

    def _load_dictionary(self, settings, clear_history=False):
        path = settings.get_string('dictionary')
        user = settings.get_string('user-dictionary')
        return Dictionary(path, user, clear_history)

    def _load_layout(self):
        """
        This function loads the keyboard layout, which is expected
        to be stored in the JSON format.
        This function first tries to load the JSON file specified
        in the config file; if not specified, it defaults back to the
        "default_layout" JSON file.
        All the layouts are meant to be stored as Romazi-like layout,
        meaning that it consists of input, output, pending, and optional
        simul_limit_ms values. However, the layout is assumed to be simultaneous
        layout, as opposed to the sequential-typing layout like the normal Romazi.
        Therefore, the max len of input char is 2. 

        This method returns a dict, which is the complete JSON data of specified layout file.
        However, it also stores dict-type layout property.
        """
        path = ""
        if('layout' in self._config):
            if(os.path.exists(os.path.join(util.get_user_configdir(), self._config['layout']))):
                path = os.path.join(util.get_user_configdir(), self._config['layout'])
                logger.debug(f"Specified layout {self._config['layout']} found in {util.get_user_configdir()}")
            elif(os.path.exists(os.path.join(util.get_datadir(), 'layouts', self._config['layout']))):
                path = os.path.join(util.get_datadir(), 'layouts', self._config['layout'])
                logger.debug(f"Specified layout {self._config['layout']} found in {util.get_datadir()}")
            else:
                path = os.path.join(util.get_datadir(), 'layouts', 'shingeta.json')
            logger.info(f'layout: {path}')
        default_layout_path = os.path.join(util.get_datadir(), 'layouts', 'shingeta.json')
        layout_data = dict()
        try:
            with open(path) as f:
                layout_data = json.load(f)
                logger.info(f'layout JSON file loaded: {path}')
        except Exception as error:
            logger.error(error)
        if(len(layout_data) == 0):
            try:
                with open(default_layout_path) as f:
                    layout_data = json.load(f)
                    logger.info(f'default layout JSON file loaded: {default_layout_path}')
            except Exception as error:
                logger.error(error)
        # add simultaneous chars..
        for l in layout_data['layout']:
            # l is a list where the 0th element is input
            input_len = len(l[0])
            input_str = l[0]
            list_values = dict()
            if(input_len == 0):
                logger.warning('input str len == 0 detected; skipping..')
                continue
            if(input_len > 3):
                logger.warning(f'len of input str is bigger than 3; skipping.. : {l}')
                continue
            list_values["output"] = str(l[1])
            list_values["pending"] = str(l[2])
            if(len(l) == 4 and type(l[3]) == int):
                list_values["simul_limit_ms"] = l[3]
            else:
                list_values["simul_limit_ms"] = 0
            self._layout[input_str] = list_values
            logger.debug(f'_load_layout -- layout element added {input_str} => {list_values}')
            if(input_len >= 2):
                self._simul_candidate_char_set.add(input_str[:-1])
        if("sands_keys" in layout_data):
            # Note that element/s of this set is str, not keyval
            self._sands_key_set = set(layout_data['sands_keys'])
        else:
            # By default, we apply SandS because it is cool
            self._sands_key_set.add('space')
        logger.debug(f'_simul_candidate_char_set:  {self._simul_candidate_char_set}')
        return layout_data

    def _load_kanchoku_layout(self):
        """
        Purpose of this function is to load the kanchoku (漢直) layout
        as form of dict. 
        The term "layout" may not be very accurate, but I haven't found
        a better term for this concept yet (people say "漢直配列").
        """
        return_dict = dict()
        path = ""
        if('kanchoku_layout' in self._config):
            if(os.path.exists(os.path.join(util.get_user_configdir(), self._config['kanchoku_layout']))):
                path = os.path.join(util.get_user_configdir(), self._config['kanchoku_layout'])
                logger.debug(f"Specified kanchoku layout {self._config['kanchokulayout']} found in {util.get_user_configdir()}")
            elif(os.path.exists(os.path.join(util.get_datadir(), 'layouts', self._config['layout']))):
                path = os.path.join(util.get_datadir(), 'layouts', self._config['kanchoku_layout'])
                logger.debug(f"Specified layout {self._config['kanchoku_layout']} found in {util.get_datadir()}")
            else:
                path = os.path.join(util.get_datadir(), 'layouts', 'aki_code.json')
            logger.info(f'kanchoku-layout: {path}')
        default_kanchoku_layout_path = os.path.join(util.get_datadir(), 'layouts', 'aki_code.json')
        kanchoku_layout_data = dict()
        try:
            with open(path) as f:
                kanchoku_layout_data = json.load(f)
                logger.info(f'kanchoku-layout JSON file loaded: {path}')
        except Exception as error:
            logger.error(f'Error loading the kanchoku data {path} : {error}')
        if(len(kanchoku_layout_data) == 0):
            try:
                with open(default_kanchoku_layout_path) as f:
                    kanchoku_layout_data = json.load(f)
                    logger.info(f'default kanchoku layout JSON file loaded: {default_kanchoku_layout_path}')
            except Exception as error:
                logger.error(f'Error loading the default kanchoku data {default_kanchoku_layout_path}: {error}')
        # initialize the layout first..
        for first in KANCHOKU_KEY_SET:
            return_dict[first] = dict()
            for second in KANCHOKU_KEY_SET:
                return_dict[first][second] = kanchoku_layout_data[first][second]
        # actually loading the layout..
        for first in kanchoku_layout_data.keys():
            if(first not in KANCHOKU_KEY_SET):
                continue
            for second in kanchoku_layout_data[first].keys():
                if(second not in KANCHOKU_KEY_SET):
                    continue
                return_dict[first][second] = kanchoku_layout_data[first][second]
        #logger.debug(f'Loaded kanchoku data: {return_dict}')
        return(return_dict)

    def _handle_input_to_yomi(self, preedit, keyval):
        """
        purpose of this function is to update the given preedit str
        with a given event char ("self._event.chr()").
        This should not be dependent whether the input mode is in
        hiragana or in kanji-conversion (to be implemented).

        This function also takes care of the simultaneous input,
        which is achieved by checking and updating the value of
        self._if_simul_condition_met.

        This function returns the Yomi output and preedit char/s, 
        depending on the _layout_dict_array and value of c.
        """
        current_typed_time = time.perf_counter()
        stroke_timing_diff = int((current_typed_time - self._previous_typed_timestamp)*1000)
        c = self._event.chr().lower() # FIXME : this line could be ignored and replaced by something fancier
        logger.debug(f'_handle_input_to_yomi -- preedit: "{preedit}", char: "{c}"')
        # sanity-check -- make the whole string committed if it's not found in the layout
        if(c not in self._layout):
            logger.debug(f'_handle_input_to_yomi -- "{c}" not found in layout input at all => committing {preedit} + {c}')
            return(preedit + c, "")
        # following implementation is very much goofy, but is probably easier to understand as we only consider max of len(preedit)==2
        preedit_prefix = ""
        preedit_and_c = preedit + c
        # first, we do the simultaneous check (from longest to shortest)
        if(len(preedit)==2):
            if(preedit in self._simul_candidate_char_set and preedit_and_c in self._layout):
                logger.debug(f'_handle_input_to_yomi -- simul-check : {stroke_timing_diff} vs ' + str(self._layout[preedit_and_c]['simul_limit_ms']))
                if(stroke_timing_diff < self._layout[preedit_and_c]['simul_limit_ms']):
                    logger.debug(f'{preedit_and_c} => {self._layout[preedit_and_c]}')
                    self._previous_typed_timestamp = current_typed_time
                    return(self._layout[preedit_and_c]['output'], self._layout[preedit_and_c]['pending'])
            # at this point, 3-key-stroke simul-check was negative, we now go for 2-key-stroke simul-check
            # the following code is to handle cases like /abc/ => "aB" where we only have /bc/=>"B" simul rule
            preedit_prefix = preedit[0]
            preedit_and_c = preedit[1] + c
            if(preedit in self._simul_candidate_char_set and preedit_and_c in self._layout):
                logger.debug(f'_handle_input_to_yomi -- simul-check : {stroke_timing_diff} vs ' + str(self._layout[preedit_and_c]['simul_limit_ms']))
                if(stroke_timing_diff < self._layout[preedit_and_c]['simul_limit_ms']):
                    logger.debug(f'{preedit_and_c} => {self._layout[preedit_and_c]}')
                    self._previous_typed_timestamp = current_typed_time
                    return(preedit_prefix + self._layout[preedit_and_c]['output'], self._layout[preedit_and_c]['pending'])
        if(len(preedit)==1):
            # this is still simul-check in case we only have 1-char preedit (which should be most of the case)
            if(preedit in self._simul_candidate_char_set and preedit_and_c in self._layout):
                logger.debug(f'_handle_input_to_yomi -- simul-check : {stroke_timing_diff} vs ' + str(self._layout[preedit_and_c]['simul_limit_ms']))
                if(stroke_timing_diff < self._layout[preedit_and_c]['simul_limit_ms']):
                    logger.debug(f'{preedit_and_c} => {self._layout[preedit_and_c]}')
                    self._previous_typed_timestamp = current_typed_time
                    return(self._layout[preedit_and_c]['output'], self._layout[preedit_and_c]['pending'])
        # at this point, all the simul-check is completed (and got negative)
        # because we do not need to think of changing the preedit value
        # outside of the simultaneous strokes in shingeta context, the rest should be simple
        preedit_and_c = preedit + c
        logger.debug(f'_handle_input_to_yomi -- "{preedit_and_c}" not found in layout or simul rejected => ' + preedit + self._layout[c]["output"] +' / '+ self._layout[c]["pending"])
        self._previous_typed_timestamp = current_typed_time
        return(preedit + self._layout[c]["output"], self._layout[c]["pending"])


    # is this function really used at all?
    def _preedit_to_yomi(self, preedit, keyval, state=0, modifiers=0):
        yomi = ''
        c = self._evnet.chr().lower()
        preedit += c
        if(preedit in self._layout):
            # FIXME why += instead of = ?
            yomi += self._layout[preedit]
            preedit = ''
        return(yomi, preedit)

    def _config_value_changed_cb(self, settings, key):
        logger.debug(f'config_value_changed("{key}")')
        if key == 'mode':
            self.set_mode(self._load_input_mode(settings), True)

    # it seems like a way to passthrough the ascii (and similar) chars to the output?
    def _handle_default_layout(self, preedit, keyval, state=0, modifiers=0):
        # this is just about returning the entered char as is..
        return self._event.chr(), ''

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
        if(0 < preedit_len and preedit_len <= pos and text[pos - preedit_len:pos] == self._preedit_string):
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
        return(self.get_mode() != 'A')

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
        '''
        This is the function to set the IME mode
        This function is supposed to be called from
        multiple places.
        '''
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
        """
        This function is called when there is a key-storke event from IBus.
        This is almost a wrapper function to process_key_event()
        """
        #return self._event.process_key_event(keyval, keycode, state)
        is_press_action = ((state & IBus.ModifierType.RELEASE_MASK) == 0)
        if(is_press_action):
            logger.debug(f'do_process_key_event -- press ("{IBus.keyval_name(keyval)}", {keyval:#04x}, {keycode:#04x}, {state:#010x})')
        else:
            logger.debug(f'do_process_key_event -- release ("{IBus.keyval_name(keyval)}", {keyval:#04x}, {keycode:#04x}, {state:#010x})')
        # 変換 / 無変換
        if(keyval == IBus.Muhenkan):
            if(is_press_action): # this extra if-clause is necessary not to cascade release signal to further function.
                logger.debug(f'do_process_key_event -- IME set disabled via Muhenkan')
                self.set_mode('A', True)
            return(True)
        if(keyval == IBus.Henkan or keyval == IBus.Henkan_Mode):
            if(is_press_action):
                logger.debug(f'do_process_key_event -- IME set enabled via Henkan')
                self.set_mode('あ', True)
            self._space_pressed = False # when the IME is newly enabled, this value needs to be False
            return(True)
        # If the IME is supposed to be disabled (direct mode), do not cascade the keyval any further
        if(not self.is_enabled()):
            # this block is for direct-mode (no Japanese char)
            return(False)
        return(self.process_key_event(keyval, keycode, state))

    def process_key_event(self, keyval, keycode, state):
        """
        This function is the actual implementation of the do_process_key_event()
        This function could be considered as the core part of the IME
        This function not only detects the type/state of the key, but also identify 
        which (internal) state the IME is supposed to be. 
        """
        logger.debug(f'process_key_event -- ("{IBus.keyval_name(keyval)}", {keyval:#04x}, {keycode:#04x}, {state:#010x})')
        is_press_action = ((state & IBus.ModifierType.RELEASE_MASK) == 0)
        # first check/update the status of SandS
        if(IBus.keyval_name(keyval) in self._sands_key_set):
            # please note that this implementation has a limitation that would not allow multiple
            # SandS keys to be pressed and released as if "shift" is still being pressed.
            # This is a known limitation and is not planned to be addressed unless someone really
            # wishes so.
            if(is_press_action):
                logger.debug('process_key_event -- SandS-key pressed')
                self._space_pressed = True
                # at this point, you cannot simply return(true) because *pressing* the space action could have an impact as well
            else:
                logger.debug('process_key_event -- SandS-key released')
                self._space_pressed = False
        # check for the shift..
        if(keyval == IBus.Shift_L or keyval == IBus.Shift_R):
            if(is_press_action):
                logger.debug('process_key_event -- Shift-key pressed')
                self._space_pressed = True
            else:
                logger.debug('process_key_event -- Shift-key released')
                self._space_pressed = False
        '''
            self._commit_string(IBus.keyval_name(keyval))
            return(True)
        '''
        # the real deal with Japanese typing starts...
        # State0
        # State1
        # State2
        # State3
        '''
        else:
            self._commit_string(chr(keyval))
            return(True)
        '''
        return(False)


    def handle_alt_graph(self, keyval, keycode, state, modifiers):
        logger.debug(f'handle_alt_graph("{self._event.chr()}")')
        c = self._event.chr().lower()
        if not c:
            return c
        if not self._event.is_shift():
            return self._layout_data['\\Normal'].get(c, '')
        if '\\Shift' in self._layout_data:
            return self._layout_data['\\Shift'].get(c, '')
        if modifiers & event.SHIFT_L_BIT:
            return self._layout_data['\\ShiftL'].get(c, '')
        if modifiers & event.SHIFT_R_BIT:
            return self._layout_data['\\ShiftR'].get(c, '')

    def handle_key_event(self, keyval, keycode, state, modifiers):
        """
        This function handles almost all sorts of key-events.
        This is called from Event.handle_key_event(), which is called from
        Event.process_key_event(), which is again called from
        Engine.do_process_key_event(), which is override of IBus class.
        """
        logger.debug(f'handle_key_event("{IBus.keyval_name(keyval)}", {keyval:#04x}, {keycode:#04x}, {state:#010x}, {modifiers:#07x})')
        if self._event.is_dual_role():
            # dual_role = SandS-like functionality? 
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
            if keyval in (IBus.Page_Up, IBus.KP_Page_Up):
                return self.do_page_up()
            elif keyval in (IBus.Page_Down, IBus.KP_Page_Down):
                return self.do_page_down()
            elif keyval == IBus.Up or self._event.is_muhenkan():
                return self.do_cursor_up()
            elif keyval == IBus.Down or self._event.is_henkan():
                return self.do_cursor_down()

        if self._preedit_string:
            if keyval == IBus.Return:
                if self._preedit_string == 'n':
                    self._preedit_string = 'ん'
                    # FIXME: instead of this if-clause, more generic handing of pending char(s) should be used
                self._commit_string(self._preedit_string)
                self._preedit_string = ''
                self._update_preedit()
                return True
            if keyval == IBus.Escape:
                self._preedit_string = ''
                self._update_preedit()
                return True

        if self._dict.current():
            if keyval == IBus.Tab:
                if not self._event.is_shift():
                    return self.handle_shrink()
                else:
                    return self.handle_expand()
            if keyval == IBus.Escape:
                self._handle_escape()
                self._update_preedit()
                return True
            if keyval == IBus.Return:
                self._commit()
                return True

        # Handle Japanese text
        if((self._event.is_henkan() or self._event.is_muhenkan()) and not(modifiers & event.ALT_R_BIT)):
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
            # the real char typed..
            if modifiers & event.ALT_R_BIT:
                yomi = self.handle_alt_graph(keyval, keycode, state, modifiers)
                if yomi:
                    self._preedit_string = ''
            else: # possible ASCII-to-hiragana
                yomi, self._preedit_string = self._handle_input_to_yomi(self._preedit_string, keyval)
        elif keyval == IBus.hyphen:
            yomi = '―'
        elif self._previous_text:
            if keyval == IBus.Escape:
                self._previous_text = ''
            else:
                self._commit()
            self._update_preedit()
            return True
        else:
            return False
        if(yomi):
            logger.debug(f'handle_key_event -- if(yomi): {yomi}')
            # This is where the yomi is sent to the IBus as committed string.
            self._commit_string(yomi)
        self._update_preedit()
        return True

    def lookup_dictionary(self, yomi, pos):
        logger.debug(f'lookup_dictionary called: yomi: {yomi}, pos: {pos}')
        # FIXME : are following lines really necessary? Should it not be handled more comprehensively? 
        if self._preedit_string == 'n':
            yomi = yomi[:pos] + 'ん'
            pos += 1
        self._lookup_table.clear()
        cand = self._dict.lookup(yomi, pos)
        size = len(self._dict.reading())
        if 0 < size:
            # FIXME same as above..
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
        ## FIXME some hard-coded modifications..
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
        # hard-coded modification ended

        if self._surrounding in (SURROUNDING_NOT_SUPPORTED, SURROUNDING_BROKEN):
            #self._previous_text += text
            self.commit_text(IBus.Text.new_from_string(text))
            logger.debug(f'_commit_string({text}): legacy ({self._previous_text})')
        else:
            if self._surrounding != SURROUNDING_SUPPORTED:
                self._surrounding = SURROUNDING_COMMITTED
                #self._previous_text += text
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
        """
        Updates the preedit text with the given candidate string.
        Args:
            cand (str): The candidate string to update the preedit text with. Defaults to an empty string.
        Returns:
            None
        Raises:
            TypeError: If the input candidate is not a string.
        This method updates the preedit text with the given candidate string. The preedit text is the text that is currently being composed by the user, and the candidate string is a suggestion for what the user might want to type next. If the candidate string is empty, the preedit text is cleared.
        If the input candidate is not a string, a TypeError is raised.
        """
        logger.debug('_update_preedit --')
        if(not isinstance(cand, str)):
            raise TypeError("The `cand` parameter must be a str value.")
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
            # Follownig version is to suppress the underline in the preedit string. We do not use this for the time being for debug purpose. 
            #attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.NONE, previous_len, previous_len + preedit_len))
        if attrs:
            text.set_attributes(attrs)
        # Note self.hide_preedit_text() does not seem to work as expected with Kate.
        # cf. "Qt5 IBus input context does not implement hide_preedit_text()",
        #     https://bugreports.qt.io/browse/QTBUG-48412
        #self.update_preedit_text(text, text_len, 0 < text_len)
        self.update_preedit_text_with_mode(text, text_len, 0 < text_len, IBus.PreeditFocusMode.COMMIT)
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
        """
        This function (presumably) detects the location of (new) position
        of mouse pointer..
        This would most likely be helpful when detecting a "pause" in the 
        typing.. (i.e., typing intervened by mouse move)
        ...It seems taht this function is called periodically. It may be an idea to store the position of the mouse pointer and commit(?) the hiragana only with pointer-position value mismatch? 
        """
        logger.debug(f'set_cursor_location_cb({x}, {y}, {w}, {h})')
        self._update_lookup_table()

    def _forward_backspaces(self, size):
        logger.debug(f'_forward_backspaces({size})')
        for i in range(size):
            self.forward_key_event(IBus.BackSpace, 14, 0)
            time.sleep(EVENT_DELAY)
            self.forward_key_event(IBus.BackSpace, 14, IBus.ModifierType.RELEASE_MASK)
