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
import subprocess
import time

import gi
gi.require_version('IBus', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, IBus
# http://lazka.github.io/pgi-docs/IBus-1.0/index.html?fbclid=IwY2xjawG9hapleHRuA2FlbQIxMAABHXaZwlJVVZEl9rr2SWsvIy2x85xW-XJuu32OZYxQ3gxF-E__9kWOUqGNzA_aem_2zw0hES6WqJcXPds_9CEdA
# http://lazka.github.io/pgi-docs/Gtk-4.0/index.html?fbclid=IwY2xjawG9hatleHRuA2FlbQIxMAABHVsKSY24bv9C75Mweq54yhLsePdGA25YfLnwMwCx7vEq03oV61qn_qEntg_aem_3k1P3ltIMb17cBH0fdPr4w
# http://lazka.github.io/pgi-docs/GLib-2.0/index.html?fbclid=IwY2xjawG9hatleHRuA2FlbQIxMAABHXaZwlJVVZEl9rr2SWsvIy2x85xW-XJuu32OZYxQ3gxF-E__9kWOUqGNzA_aem_2zw0hES6WqJcXPds_9CEdA

logger = logging.getLogger(__name__)

APPLICABLE_STROKE_SET_FOR_JAPANESE = set(list('1234567890qwertyuiopasdfghjk;lzxcvbnm,./'))

KANCHOKU_KEY_SET = set(list('qwertyuiopasdfghjkl;zxcvbnm,./'))
MISSING_KANCHOKU_KANJI = '無'

# modifier mask-bit segment
STATUS_SPACE        = 0x001
STATUS_SHIFT_L      = 0x002 # this value is currently not meant to be used directly
STATUS_SHIFT_R      = 0x004 # this value is currently not meant to be used directly
STATUS_CONTROL_L    = 0x008
STATUS_CONTROL_R    = 0x010
STATUS_ALT_L        = 0x020
STATUS_ALT_R        = 0x040
STATUS_SUPER_L      = 0x080
STATUS_SUPER_R      = 0x100
STATUS_SHIFTS       = STATUS_SHIFT_L | STATUS_SHIFT_R
STATUS_CONTROLS     = STATUS_CONTROL_L | STATUS_CONTROL_R
STATUS_ALTS         = STATUS_ALT_L | STATUS_ALT_R
STATUS_SUPERS       = STATUS_SUPER_L | STATUS_SUPER_R
STATUS_MODIFIER     = STATUS_SHIFTS  | STATUS_CONTROLS | STATUS_ALTS | STATUS_SPACE | STATUS_SUPERS

# Japanese typing mode segment
MODE_FORCED_PREEDIT_POSSIBLE                   = 0x001
MODE_IN_FORCED_PREEDIT                         = 0x002
MODE_IN_PREEDIT                                = 0x004
MODE_IN_KANCHOKU                               = 0x008
MODE_JUST_FINISHED_KANCHOKU                    = 0x010
MODE_IN_CONVERSION                             = 0x020
MODE_IN_FORCED_CONVERSION                      = 0x040
SWITCH_FIRST_SHIFT_PRESSED_IN_PREEDIT          = 0x080
SWITCH_FIRST_SHIFT_PRESSED_IN_FORCED_PREEDIT   = 0x100

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


class EnginePSKK(IBus.Engine):
    '''
    http://lazka.github.io/pgi-docs/IBus-1.0/classes/Engine.html
    '''
    __gtype_name__ = 'EnginePSKK'

    def __init__(self):
        logger.error(f'started')
        super().__init__()
        # setting the initial input mode
        self._mode = 'A'  # _mode must be one of _input_mode_names
        self._mode = 'あ'  # DEBUG I do not like to click extra...
        # loading the layout
        self._layout_data = dict() # this is complete data of layout JSON
        self._kanchoku_layout = dict()
        # _layout[INPUT]: {"output": OUTPUT_STR, "pending": PENDING_STR, "simul_limit_ms": INT}
        self._simul_candidate_char_set = set()
        self._max_simul_limit_ms = 0

        # as part of init, set the timestamp anchor
        self._origin_timestamp = time.perf_counter()
        self._previous_typed_timestamp = time.perf_counter()
        self._stroke_timing_diff = time.perf_counter()
        # SandS vars
        self._modkey_status = 0 # This is supposed to be bitwise status
        self._typing_mode = 0 # This is to indicate which state the stroke is supposed to be
        self._sands_key_set = set()
        self._first_kanchoku_stroke = ""

        self._preedit_string = ''
        self._previous_text = ''
        self._shrunk = []

        # This property is for confirming the kanji-kana converted string
        self._lookup_table = IBus.LookupTable.new(10, 0, True, False)
        self._lookup_table.set_orientation(IBus.Orientation.VERTICAL)

        self._init_props()

        self._settings = Gio.Settings.new('org.freedesktop.ibus.engine.pskk')
        self._settings.connect('changed', self._config_value_changed_cb)
        logger.debug(f'Engine init -- settings: {self._settings}')

        # load configs
        self._load_configs()
        #self._layout_data = self._load_layout() # this will also update self._layout
        #self._kanchoku_layout = self._load_kanchoku_layout()
        # This will create an object defined in event.py
        self._event = Event(self, self._layout_data)

        self.set_mode(self._load_input_mode(self._settings))
        self.set_mode('あ')
        #self.character_after_n = "aiueo'wy"

        #self.connect('set-cursor-location', self.set_cursor_location_cb)

        self._about_dialog = None
        self._q = queue.Queue()

    def _load_configs(self):
        pass

    def _config_value_changed_cb(self, settings, key):
        logger.debug(f'config_value_changed("{key}")')
        if key == 'mode':
            self.set_mode(self._load_input_mode(settings), True)

    def _load_input_mode(self, settings):
        # FIXME this should be coming from the config file, not settings...
        mode = settings.get_string('mode')
        if mode not in INPUT_MODE_NAMES:
            mode = 'A'
            settings.reset('mode')
        logger.info(f'input mode: {mode}')
        return mode

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
            label=IBus.Text.new_from_string(f"Input mode ({self._mode})"),
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
            label=IBus.Text.new_from_string("About PSKK..."),
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
                                   label=IBus.Text.new_from_string("Alphanumeric (A)"),
                                   icon=None,
                                   tooltip=None,
                                   sensitive=True,
                                   visible=True,
                                   state=IBus.PropState.CHECKED,
                                   sub_props=None))
        props.append(IBus.Property(key='InputMode.Hiragana',
                                   prop_type=IBus.PropType.RADIO,
                                   label=IBus.Text.new_from_string("Hiragana (あ)"),
                                   icon=None,
                                   tooltip=None,
                                   sensitive=True,
                                   visible=True,
                                   state=IBus.PropState.UNCHECKED,
                                   sub_props=None))
        return props


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
                self._max_simul_limit_ms = max(l[3], self._max_simul_limit_ms)
                list_values["simul_limit_ms"] = l[3]
            else:
                list_values["simul_limit_ms"] = 0
            self._layout[input_str] = list_values
            #logger.debug(f'_load_layout -- layout element added {input_str} => {list_values}')
            if(input_len >= 2):
                self._simul_candidate_char_set.add(input_str[:-1])
        logger.debug(f'_load_layout -- _max_simul_limit_ms: {self._max_simul_limit_ms}')
        self._stroke_timing_diff = self._max_simul_limit_ms
        if("sands_keys" in layout_data):
            # Note that element/s of this set is str, not keyval
            self._sands_key_set = set(layout_data['sands_keys'])
        else:
            # By default, we apply SandS because it is cool
            self._sands_key_set.add('space')
        logger.debug(f'_simul_candidate_char_set:  {self._simul_candidate_char_set}')
        return layout_data


    def _is_simul_condition_met(self, keyval, preedit, stroke_timing_diff):
        """
        This function is to return the boolean value
        if the given keycode (given the loaded layout)
        is supposed to be captured as simultaneous stroke. 

        In order to have the modularity, preedit value is 
        also deined as argument.
        """
        c = chr(keyval)
        preedit_and_c = preedit + c
        if(preedit in self._simul_candidate_char_set and preedit_and_c in self._layout):
            logger.debug(f'_is_simul_condition_met -- simul-check : {stroke_timing_diff} vs ' + str(self._layout[preedit_and_c]['simul_limit_ms']))
            if(stroke_timing_diff < self._layout[preedit_and_c]['simul_limit_ms']):
                return(True)
        return(False)

