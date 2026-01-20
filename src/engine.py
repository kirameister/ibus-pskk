import util
import settings_panel
from simultaneous_processor import SimultaneousInputProcessor

import json
import logging
import os
import queue

import gi
gi.require_version('IBus', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, IBus, GLib
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

# =============================================================================
# CHARACTER CONVERSION TABLES
# =============================================================================

# Hiragana characters (ぁ to ゖ)
HIRAGANA_CHARS = (
    'ぁあぃいぅうぇえぉお'
    'かがきぎくぐけげこご'
    'さざしじすずせぜそぞ'
    'ただちぢっつづてでとど'
    'なにぬねの'
    'はばぱひびぴふぶぷへべぺほぼぽ'
    'まみむめも'
    'ゃやゅゆょよ'
    'らりるれろ'
    'ゎわゐゑをん'
    'ゔゕゖ'
)

# Katakana characters (ァ to ヶ) - same order as hiragana
KATAKANA_CHARS = (
    'ァアィイゥウェエォオ'
    'カガキギクグケゲコゴ'
    'サザシジスズセゼソゾ'
    'タダチヂッツヅテデトド'
    'ナニヌネノ'
    'ハバパヒビピフブプヘベペホボポ'
    'マミムメモ'
    'ャヤュユョヨ'
    'ラリルレロ'
    'ヮワヰヱヲン'
    'ヴヵヶ'
)

# Half-width ASCII (printable: space to tilde)
ASCII_HALFWIDTH = (
    ' !"#$%&\'()*+,-./'
    '0123456789'
    ':;<=>?@'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '[\\]^_`'
    'abcdefghijklmnopqrstuvwxyz'
    '{|}~'
)

# Full-width ASCII (Zenkaku) - same order as half-width
ASCII_FULLWIDTH = (
    '　！"＃＄％＆＇（）＊＋，－．／'
    '０１２３４５６７８９'
    '：；＜＝＞？＠'
    'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
    '［＼］＾＿｀'
    'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
    '｛｜｝～'
)

# Translation tables
HIRAGANA_TO_KATAKANA = str.maketrans(HIRAGANA_CHARS, KATAKANA_CHARS)
KATAKANA_TO_HIRAGANA = str.maketrans(KATAKANA_CHARS, HIRAGANA_CHARS)
ASCII_TO_FULLWIDTH = str.maketrans(ASCII_HALFWIDTH, ASCII_FULLWIDTH)
FULLWIDTH_TO_ASCII = str.maketrans(ASCII_FULLWIDTH, ASCII_HALFWIDTH)

# Japanese typing mode segment
#MODE_FORCED_PREEDIT_POSSIBLE                   = 0x001
#MODE_IN_FORCED_PREEDIT                         = 0x002
#MODE_IN_PREEDIT                                = 0x004
#MODE_IN_KANCHOKU                               = 0x008
#MODE_JUST_FINISHED_KANCHOKU                    = 0x010
#MODE_IN_CONVERSION                             = 0x020
#MODE_IN_FORCED_CONVERSION                      = 0x040
#SWITCH_FIRST_SHIFT_PRESSED_IN_PREEDIT          = 0x080
#SWITCH_FIRST_SHIFT_PRESSED_IN_FORCED_PREEDIT   = 0x100

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
        super().__init__()
        # setting the initial input mode
        self._mode = 'A'  # _mode must be one of _input_mode_names
        self._mode = 'あ'  # DEBUG I do not like to click extra...
        self._override = True
        # loading the layout
        self._layout_data = None  # raw layout JSON data
        self._simul_processor = None  # SimultaneousInputProcessor instance
        self._kanchoku_layout = dict()
        # SandS vars
        self._modkey_status = 0 # This is supposed to be bitwise status
        self._typing_mode = 0 # This is to indicate which state the stroke is supposed to be
        self._pressed_key_set = set()
        self._handled_config_keys = set()  # Keys handled by config bindings (to consume releases)
        self._sands_key_set = set()
        self._first_kanchoku_stroke = ""

        self._preedit_string = ''    # Display buffer (can be hiragana, katakana, ascii, or zenkaku)
        self._preedit_hiragana = ''  # Source of truth: hiragana output from simul_processor
        self._preedit_ascii = ''     # Source of truth: raw ASCII input characters
        self._previous_text = ''

        # This property is for confirming the kanji-kana converted string
        self._lookup_table = IBus.LookupTable.new(10, 0, True, False)
        self._lookup_table.set_orientation(IBus.Orientation.VERTICAL)

        self._init_props()
        #self.register_properties(self._prop_list)

        self._settings = Gio.Settings.new('org.freedesktop.ibus.engine.pskk')
        self._settings.connect('changed', self._config_value_changed_cb)
        logger.debug(f'Engine init -- settings: {self._settings}')

        # load configs
        self._load_configs()
        self._layout_data = util.get_layout_data(self._config)
        self._simul_processor = SimultaneousInputProcessor(self._layout_data)
        self._kanchoku_layout = self._load_kanchoku_layout()

        self.set_mode(self._load_input_mode(self._settings))
        #self.set_mode('あ')

        self.connect('set-cursor-location', self.set_cursor_location_cb)

        self._about_dialog = None
        self._settings_panel = None
        self._q = queue.Queue()


    def do_focus_in(self):
        self.register_properties(self._prop_list)
        #self._update_preedit()
        # Request the initial surrounding-text in addition to the "enable" handler.
        self.get_surrounding_text()


    def _init_props(self):
        '''
        This function is called as part of the instantiation (__init__).
        This function creates the GUI menu list (typically top-right corner).

        http://lazka.github.io/pgi-docs/IBus-1.0/classes/PropList.html
        http://lazka.github.io/pgi-docs/IBus-1.0/classes/Property.html
        '''
        logger.debug('_init_props()')
        self._prop_list = IBus.PropList()
        self._input_mode_prop = IBus.Property(
            key='InputMode',
            prop_type=IBus.PropType.MENU,
            symbol=IBus.Text.new_from_string(self._mode),
            #label=IBus.Text.new_from_string("Input mode (" + self._mode + ")"),
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
        settings_prop = IBus.Property(
            key='Settings',
            prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("Settings..."),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        self._prop_list.append(settings_prop)
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
        logger.debug('_init_props() -- end')

    def _init_input_mode_props(self):
        '''
        This is a function to produce GUI (sub) component for
        different input modes.
        This function is meant to be only called from _init_props()
        '''
        logger.debug('_init_input_mode_props()')
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
        logger.debug('_init_input_mode_props() -- end')
        return props



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
                logger.debug(f"Specified kanchoku layout {self._config['kanchoku_layout']} found in {util.get_user_configdir()}")
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


    def _load_configs(self):
        '''
        This function loads the necessary (and optional) configs from the config JSON file
        The logging level value would be set to WARNING, if it's absent in the config JSON.
        '''
        self._config = util.get_config_data()[0] # the 2nd element of tuple is list of warning messages
        self._logging_level = self._load_logging_level(self._config)
        logger.debug('config.json loaded')
        # loading layout should be part of (re-)loading config
        self._layout_data = util.get_layout_data(self._config)
        self._simul_processor = SimultaneousInputProcessor(self._layout_data)
        self._kanchoku_layout = self._load_kanchoku_layout()

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
        logger.debug(f'_load_input_mode(); mode = {mode}')
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
        #self._update_preedit()
        #self._update_lookup_table()
        self._update_input_mode()
        return True

    def _commit(self):
        pass
        """
        current = self._dict.current()
        if current:
            self._dict.confirm(''.join(self._shrunk))
            self._dict.reset()
            self._lookup_table.clear()
        text = self._previous_text + current
        self._previous_text = ''
        #self._update_preedit()
        if text:
            logger.debug(f'_commit(): "{text}"')
            self.commit_text(IBus.Text.new_from_string(text))
        """

    def _show_about_dialog(self):
        if self._about_dialog:
          self._about_dialog.present()
          return False  # Don't repeat this idle callback

        dialog = Gtk.AboutDialog()
        dialog.set_program_name("PSKK")
        dialog.set_copyright("Copyright 2021-2026 Akira K.")
        dialog.set_authors(["Akira K."])
        dialog.set_documenters(["Akira K."])
        dialog.set_website("file://" + os.path.join(util.get_datadir(), "help/index.html"))
        dialog.set_website_label("Introduction to PSKK")
        dialog.set_logo_icon_name(util.get_package_name())
        dialog.set_default_icon_name(util.get_package_name())
        dialog.set_version(util.get_version())
        dialog.set_comments("config files location : ${HOME}/.config/ibus-pskk")

        # Make dialog modal and keep it on top
        dialog.set_modal(True)
        dialog.set_keep_above(True)

        dialog.connect("response", self.about_response_callback)
        self._about_dialog = dialog
        dialog.show()

        return False  # Don't repeat this idle callback

    def _show_settings_panel(self):
        if self._settings_panel:
            self._settings_panel.present()
            return False  # Don't repeat this idle callback

        panel = settings_panel.SettingsPanel()
        panel.connect("destroy", self.settings_panel_closed_callback)
        self._settings_panel = panel
        panel.show_all()

        return False  # Don't repeat this idle callback


    def do_property_activate(self, prop_name, state):
        logger.info(f'property_activate({prop_name}, {state})')
        if prop_name == 'Settings':
            # Schedule settings panel creation on the main loop
            GLib.idle_add(self._show_settings_panel)
            return
        elif prop_name == 'About':
            # Schedule dialog creation on the main loop
            GLib.idle_add(self._show_about_dialog)
            return
        elif prop_name.startswith('InputMode.'):
            if state == IBus.PropState.CHECKED:
                # At this point, we only support direct input and Hiragana. Nothing else..
                mode = {
                    'InputMode.Alphanumeric': 'A',
                    'InputMode.Hiragana': 'あ',
                }.get(prop_name, 'A')
                self.set_mode(mode, True)


    def about_response_callback(self, dialog, response):
        dialog.destroy()
        self._about_dialog = None

    def settings_panel_closed_callback(self, panel):
        self._settings_panel = None

    def _update_input_mode(self):
        self._input_mode_prop.set_symbol(IBus.Text.new_from_string(self._mode))
        self._input_mode_prop.set_label(IBus.Text.new_from_string("Input mode (" + self._mode + ")"))
        self.update_property(self._input_mode_prop)

    def set_cursor_location_cb(self, engine, x, y, w, h):
        """
        This function (presumably) detects the location of (new) position
        of mouse pointer..
        This would most likely be helpful when detecting a "pause" in the
        typing.. (i.e., typing intervened by mouse move)
        ...It seems taht this function is called periodically. It may be an idea to store the position of the mouse pointer and commit(?) the hiragana only with pointer-position value mismatch?
        """
        logger.debug(f'set_cursor_location_cb({x}, {y}, {w}, {h})')
        #self._update_lookup_table()

    # =========================================================================
    # KEY EVENT PROCESSING
    # =========================================================================

    def do_process_key_event(self, keyval, keycode, state):
        """
        Main entry point for handling keyboard input from IBus.

        Args:
            keyval: The key value (e.g., ord('a'), IBus.KEY_BackSpace)
            keycode: The hardware keycode
            state: Modifier state (Shift, Ctrl, etc. and RELEASE_MASK)

        Returns:
            True if we handled the key, False to pass through to application
        """
        # Determine if this is a key press or release
        is_pressed = not (state & IBus.ModifierType.RELEASE_MASK)

        # Check enable_hiragana_key BEFORE mode check (must work from any mode)
        key_name = IBus.keyval_name(keyval)
        logger.debug(f'do_process_key_event: key_name={key_name}, mode={self._mode}, is_pressed={is_pressed}')
        if key_name and self._check_enable_hiragana_key(key_name, state, is_pressed):
            return True

        # Alphanumeric mode: pass everything through (except enable_hiragana_key above)
        if self._mode == 'A':
            return False

        # Process the key event
        result = self._process_key_event(keyval, keycode, state, is_pressed)

        # Update SandS (Space as modifier) tracking
        self._update_sands_status(keyval, is_pressed)

        return result

    def _process_key_event(self, keyval, keycode, state, is_pressed):
        """
        Intermediate handler for key events (non-Alphanumeric mode).

        This function handles:
        - Modifier key press/release (SandS, etc.)
        - Special keys (Enter, Backspace, Escape) with conditional handling
        - Regular character input via SimultaneousInputProcessor

        Args:
            keyval: The key value
            keycode: The hardware keycode
            state: Modifier state
            is_pressed: True if key press, False if key release

        Returns:
            True if we handled the key, False to pass through
        """
        logger.debug(f'_process_key_event: keyval={keyval}, keycode={keycode}, '
                     f'state={state}, is_pressed={is_pressed}')

        # Get key name for all key types (e.g., "a", "Henkan", "Alt_R", "F1")
        key_name = IBus.keyval_name(keyval)
        if not key_name:
            return False

        # =====================================================================
        # CONFIG-DRIVEN KEY BINDINGS (checked first, for all key types)
        # =====================================================================

        # Define modifier key names (already tracked by IBus via 'state' parameter)
        modifier_key_names = {
            'Control_L', 'Control_R', 'Shift_L', 'Shift_R',
            'Alt_L', 'Alt_R', 'Super_L', 'Super_R'
        }

        # Update pressed key set (non-modifier keys only)
        # Modifiers are excluded because IBus tracks them via 'state' bitmask.
        if key_name not in modifier_key_names:
            if is_pressed:
                self._pressed_key_set.add(key_name)
            else:
                self._pressed_key_set.discard(key_name)

        # Check config-driven key bindings (enable/disable hiragana, conversions)
        # Called for both press and release to properly consume the entire key sequence
        if self._check_config_key_bindings(key_name, state, is_pressed):
            return True

        # =====================================================================
        # SPECIAL KEY HANDLING
        # =====================================================================

        # TODO: Special key handling (Enter, Backspace, Escape)

        # =====================================================================
        # REGULAR CHARACTER INPUT (simultaneous typing)
        # =====================================================================

        # Only process printable ASCII characters (0x20 space to 0x7e tilde)
        if keyval < 0x20 or keyval > 0x7e:
            return False

        # Convert keyval to character for simultaneous processor
        input_char = chr(keyval)

        # Accumulate ASCII input on key press (source of truth for to_ascii/to_zenkaku)
        if is_pressed:
            self._preedit_ascii += input_char

        # Get output from simultaneous processor
        # Pass current display buffer (hiragana + pending) for lookup
        output, pending = self._simul_processor.get_layout_output(
            self._preedit_string, input_char, is_pressed
        )

        logger.debug(f'Processor result: output="{output}", pending="{pending}"')

        # Update hiragana buffer (source of truth for to_katakana/to_hiragana)
        # output includes accumulated hiragana via dropped_prefix mechanism
        self._preedit_hiragana = output if output else ''

        # Build display buffer: hiragana output + pending ASCII
        new_preedit = self._preedit_hiragana + (pending if pending else '')
        self._preedit_string = new_preedit
        self._update_preedit()

        return True

    # =========================================================================
    # CONFIG-DRIVEN KEY BINDINGS
    # =========================================================================

    def _check_config_key_bindings(self, key_name, state, is_pressed):
        """
        Check if the current key event matches any config-driven key binding.

        Checks in order:
        1. enable_hiragana_key - switch to hiragana mode
        2. disable_hiragana_key - switch to direct/alphanumeric mode
        3. conversion_keys - convert preedit (to_katakana, to_hiragana, etc.)

        Args:
            key_name: The key name from IBus.keyval_name() (e.g., "a", "Henkan", "F1")
            state: Modifier state bitmask from IBus
            is_pressed: True if key press, False if key release

        Returns:
            True if key was handled (caller should return), False otherwise
        """
        # Check enable_hiragana_key
        if self._check_enable_hiragana_key(key_name, state, is_pressed):
            return True

        # Check disable_hiragana_key
        if self._check_disable_hiragana_key(key_name, state, is_pressed):
            self._commit_string()  # Commit and clear preedit before switching mode
            return True

        # Check conversion_keys
        if self._check_conversion_keys(key_name, state, is_pressed):
            return True

        return False

    def _parse_key_binding(self, binding_str):
        """
        Parse a key binding string like "Ctrl+K" or "Henkan" into components.

        Args:
            binding_str: Key binding string (e.g., "k", "Ctrl+K", "Henkan", "Ctrl+Shift+L")

        Returns:
            tuple: (main_key, required_modifiers_mask) or (None, 0) if invalid
        """
        if not binding_str:
            return None, 0

        parts = binding_str.split('+')
        main_key = parts[-1]  # Last part is the main key

        modifiers = 0
        for part in parts[:-1]:
            part_lower = part.lower()
            if part_lower in ('ctrl', 'control'):
                modifiers |= IBus.ModifierType.CONTROL_MASK
            elif part_lower == 'shift':
                modifiers |= IBus.ModifierType.SHIFT_MASK
            elif part_lower == 'alt':
                modifiers |= IBus.ModifierType.MOD1_MASK
            elif part_lower == 'super':
                modifiers |= IBus.ModifierType.SUPER_MASK

        return main_key, modifiers

    def _matches_key_binding(self, key_name, state, binding_str):
        """
        Check if key_name + state matches a key binding string.

        Args:
            key_name: The key name from IBus.keyval_name()
            state: Modifier state bitmask from IBus
            binding_str: Key binding string from config (e.g., "Ctrl+K", "Henkan")

        Returns:
            True if the input matches the binding exactly
        """
        main_key, required_mods = self._parse_key_binding(binding_str)
        if main_key is None:
            return False

        # Check main key matches (case-insensitive for single letters)
        if len(main_key) == 1 and len(key_name) == 1:
            if main_key.lower() != key_name.lower():
                return False
        else:
            # For special keys like "Henkan", exact match required
            if main_key != key_name:
                return False

        # Check required modifiers (exact match)
        mod_mask = (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK |
                    IBus.ModifierType.MOD1_MASK | IBus.ModifierType.SUPER_MASK)
        current_mods = state & mod_mask

        return current_mods == required_mods

    def _check_enable_hiragana_key(self, key_name, state, is_pressed):
        """
        Check and handle enable_hiragana_key binding.

        Switches mode to hiragana ('あ') when the configured key is pressed.
        """
        binding = self._config.get('enable_hiragana_key', '')

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # On press: check if binding matches
        if self._matches_key_binding(key_name, state, binding):
            logger.debug(f'enable_hiragana_key matched: {binding}')
            self._mode = 'あ'
            self._handled_config_keys.add(key_name)
            return True

        return False

    def _check_disable_hiragana_key(self, key_name, state, is_pressed):
        """
        Check and handle disable_hiragana_key binding.

        Switches mode to alphanumeric ('A') when the configured key is pressed.
        """
        binding = self._config.get('disable_hiragana_key', '')

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # On press: check if binding matches
        if self._matches_key_binding(key_name, state, binding):
            logger.debug(f'disable_hiragana_key matched: {binding}')
            self._mode = 'A'
            self._handled_config_keys.add(key_name)
            return True

        return False

    def _check_conversion_keys(self, key_name, state, is_pressed):
        """
        Check and handle conversion_keys bindings.

        Converts the preedit string to different character representations:
        - to_katakana: Convert to katakana
        - to_hiragana: Convert to hiragana
        - to_ascii: Convert to ASCII/romaji
        - to_zenkaku: Convert to full-width characters
        """
        conversion_keys = self._config.get('conversion_keys', {})
        if not isinstance(conversion_keys, dict):
            return False

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # On press: check each conversion key binding
        for conversion_type, binding in conversion_keys.items():
            if self._matches_key_binding(key_name, state, binding):
                logger.debug(f'conversion_key matched: {conversion_type} = {binding}')
                self._handle_conversion(conversion_type)
                self._handled_config_keys.add(key_name)
                return True

        return False

    def _handle_conversion(self, conversion_type):
        """
        Perform the actual conversion of preedit string.

        Uses source-of-truth buffers:
        - _preedit_hiragana: for to_katakana and to_hiragana
        - _preedit_ascii: for to_ascii and to_zenkaku

        Args:
            conversion_type: One of 'to_katakana', 'to_hiragana', 'to_ascii', 'to_zenkaku'
        """
        if not self._preedit_string:
            return

        original = self._preedit_string

        if conversion_type == 'to_katakana':
            # Convert hiragana source to katakana
            self._preedit_string = self._preedit_hiragana.translate(HIRAGANA_TO_KATAKANA)
        elif conversion_type == 'to_hiragana':
            # Use hiragana source directly
            self._preedit_string = self._preedit_hiragana
        elif conversion_type == 'to_ascii':
            # Use ASCII source directly
            self._preedit_string = self._preedit_ascii
        elif conversion_type == 'to_zenkaku':
            # Convert ASCII source to full-width
            self._preedit_string = self._preedit_ascii.translate(ASCII_TO_FULLWIDTH)
        else:
            logger.warning(f'Unknown conversion type: {conversion_type}')
            return

        logger.debug(f'Conversion {conversion_type}: "{original}" → "{self._preedit_string}"')
        self._update_preedit()

    # =========================================================================
    # SANDS (SPACE AND SHIFT) TRACKING
    # =========================================================================

    def _update_sands_status(self, keyval, is_pressed):
        """
        Update self._modkey_status for SandS (Space and Shift) feature.

        SandS allows Space to act as a modifier (Shift) when held and pressed
        with another key, while still producing a space when tapped alone.

        IBus doesn't track Space as a modifier, so we need custom tracking.
        Other modifiers (Ctrl, Shift, Alt, Super) are already tracked by IBus
        via the 'state' parameter.

        Args:
            keyval: The key value
            is_pressed: True if key press, False if key release
        """
        if keyval != IBus.KEY_space:
            return

        if is_pressed:
            self._modkey_status |= STATUS_SPACE
        else:
            self._modkey_status &= ~STATUS_SPACE

        logger.debug(f'SandS status: space_held={bool(self._modkey_status & STATUS_SPACE)}')

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _commit_string(self):
        """Commit preedit to the application and clear all buffers."""
        if self._preedit_string:
            logger.debug(f'Committing: "{self._preedit_string}"')
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))
            self._preedit_string = ""
            self._preedit_hiragana = ""
            self._preedit_ascii = ""
            self._update_preedit()

    def _update_preedit(self):
        """Update the preedit display in the application"""
        if self._preedit_string:
            # Show preedit with underline
            preedit_text = IBus.Text.new_from_string(self._preedit_string)
            preedit_text.set_attributes(IBus.AttrList())
            # Add underline attribute for the entire preedit
            attr = IBus.Attribute.new(
                IBus.AttrType.UNDERLINE,
                IBus.AttrUnderline.SINGLE,
                0,
                len(self._preedit_string)
            )
            preedit_text.get_attributes().append(attr)
            self.update_preedit_text(
                preedit_text,
                len(self._preedit_string),  # cursor at end
                True  # visible
            )
        else:
            # Hide preedit when empty
            self.update_preedit_text(
                IBus.Text.new_from_string(''),
                0,
                False  # not visible
            )

