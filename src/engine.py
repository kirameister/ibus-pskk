import util
import settings_panel
from simultaneous_processor import SimultaneousInputProcessor
from kanchoku import KanchokuProcessor
from henkan import HenkanProcessor

from enum import IntEnum
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


# =============================================================================
# KANCHOKU / BUNSETSU STATE MACHINE
# =============================================================================

class MarkerState(IntEnum):
    """
    State machine for kanchoku_bunsetsu_marker key sequences.

    The marker key (e.g., Space) enables three different behaviors:
    - Kanchoku: marker held → key1↓↑ → key2↓↑ → kanji output
    - Bunsetsu: marker held → key1↓↑ → marker↑ → bunsetsu boundary (if key1 can start bunsetsu)
    - Forced preedit: marker held → key1↓↑ → marker↑ → enter forced preedit (if key1 is "ん" etc.)
    """
    IDLE = 0                    # Marker not held
    MARKER_HELD = 1             # Marker pressed, waiting for first key
    FIRST_PRESSED = 2           # First key pressed (not yet released)
    FIRST_RELEASED = 3          # First key released - decision point:
                                #   key2↓ → kanchoku, marker↑ → bunsetsu/forced-preedit
    KANCHOKU_SECOND_PRESSED = 4 # Second key pressed (kanchoku confirmed)

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

        # Kanchoku / Bunsetsu state machine variables
        self._marker_state = MarkerState.IDLE
        self._marker_first_key = None           # Raw key char for kanchoku lookup
        self._marker_keys_held = set()          # Track keys currently pressed while marker held
        self._preedit_before_marker = ''        # Preedit snapshot to restore if kanchoku
        self._in_forced_preedit = False         # True when in forced preedit mode (Case C)

        # Henkan (kana-kanji conversion) state variables
        self._bunsetsu_active = False           # True when bunsetsu mode is active (yomi input)
        self._in_conversion = False             # True when showing conversion candidates
        self._conversion_yomi = ''              # The yomi string being converted
        self._pending_commit = ''               # Candidate to commit when starting new bunsetsu

        self._preedit_string = ''    # Display buffer (can be hiragana, katakana, ascii, or zenkaku)
        self._preedit_hiragana = ''  # Source of truth: hiragana output from simul_processor
        self._preedit_ascii = ''     # Source of truth: raw ASCII input characters
        self._previous_text = ''

        # This property is for confirming the kanji-kana converted string
        # LookupTable.new(page_size, cursor_pos, cursor_visible, round)
        # round=True enables wrap-around when cycling candidates
        self._lookup_table = IBus.LookupTable.new(10, 0, True, True)
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
        self._kanchoku_processor = KanchokuProcessor(self._kanchoku_layout)
        # Initialize henkan (kana-kanji conversion) processor with dictionaries
        dictionary_files = util.get_dictionary_files(self._config)
        self._henkan_processor = HenkanProcessor(dictionary_files)

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

    def do_focus_out(self):
        """
        Called when input focus leaves the engine.

        Explicitly commit any preedit/candidate before resetting state.
        This handles both normal preedit and conversion mode with lookup table.
        """
        logger.debug(f'do_focus_out: bunsetsu={self._bunsetsu_active}, '
                    f'converting={self._in_conversion}, preedit="{self._preedit_string}"')

        # Explicitly commit preedit if present
        # This is needed because IBus may not auto-commit when lookup table is visible
        if self._preedit_string:
            logger.debug(f'do_focus_out: committing "{self._preedit_string}"')
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))

        # Hide lookup table if visible
        self._lookup_table.clear()
        self.hide_lookup_table()

        # Clear preedit display
        self.update_preedit_text_with_mode(
            IBus.Text.new_from_string(''),
            0,
            False,
            IBus.PreeditFocusMode.CLEAR
        )

        # Reset henkan state
        self._bunsetsu_active = False
        self._in_conversion = False
        self._conversion_yomi = ''
        self._pending_commit = ''
        self._preedit_string = ''
        self._preedit_hiragana = ''
        self._preedit_ascii = ''

        # Reset marker state
        self._marker_state = MarkerState.IDLE
        self._marker_first_key = None
        self._marker_keys_held.clear()


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

        Returns:
            dict: A nested dictionary mapping first-key -> second-key -> kanji character
                  for all keys in KANCHOKU_KEY_SET
        """
        return_dict = dict()

        # Use utility function to load the kanchoku layout JSON data
        kanchoku_layout_data = util.get_kanchoku_layout(self._config)

        if kanchoku_layout_data is None:
            logger.error('Failed to load kanchoku layout data')
            # Initialize empty structure as fallback
            for first in KANCHOKU_KEY_SET:
                return_dict[first] = dict()
                for second in KANCHOKU_KEY_SET:
                    return_dict[first][second] = MISSING_KANCHOKU_KANJI
            return return_dict

        # Initialize and populate the layout for all keys in KANCHOKU_KEY_SET
        for first in KANCHOKU_KEY_SET:
            return_dict[first] = dict()
            for second in KANCHOKU_KEY_SET:
                # Use the loaded data if available, otherwise use placeholder
                if first in kanchoku_layout_data and second in kanchoku_layout_data[first]:
                    return_dict[first][second] = kanchoku_layout_data[first][second]
                else:
                    return_dict[first][second] = MISSING_KANCHOKU_KANJI

        return return_dict


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
        self._kanchoku_processor = KanchokuProcessor(self._kanchoku_layout)
        # Reload henkan processor with updated dictionary list
        dictionary_files = util.get_dictionary_files(self._config)
        self._henkan_processor = HenkanProcessor(dictionary_files)

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
        # KANCHOKU / BUNSETSU MARKER HANDLING (highest priority)
        # =====================================================================
        # Must be checked before other bindings since the marker key (e.g., Space)
        # triggers a state machine that consumes subsequent key events.
        if self._handle_kanchoku_bunsetsu_marker(key_name, keyval, state, is_pressed):
            return True

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

        # Handle special keys only on key press
        if is_pressed:
            # Enter key - confirm conversion or commit preedit
            if keyval == IBus.KEY_Return or keyval == IBus.KEY_KP_Enter:
                if self._in_conversion:
                    logger.debug('Enter pressed in CONVERTING: confirming')
                    self._confirm_conversion()
                    return True
                elif self._preedit_string:
                    logger.debug('Enter pressed with preedit: committing')
                    self._commit_string()
                    return True
                return False  # Pass through if no preedit

            # Arrow keys for candidate cycling (only in CONVERTING state)
            if self._in_conversion:
                if keyval == IBus.KEY_Down or keyval == IBus.KEY_KP_Down:
                    logger.debug('Down arrow in CONVERTING: next candidate')
                    self._cycle_candidate()
                    return True
                elif keyval == IBus.KEY_Up or keyval == IBus.KEY_KP_Up:
                    logger.debug('Up arrow in CONVERTING: previous candidate')
                    self._cycle_candidate_backward()
                    return True

            # Escape - cancel conversion
            if keyval == IBus.KEY_Escape:
                if self._in_conversion:
                    logger.debug('Escape in CONVERTING: cancelling, reverting to yomi')
                    self._cancel_conversion()
                    return True
                elif self._preedit_string:
                    # Clear preedit
                    self._reset_henkan_state()
                    return True
                return False

            # Backspace - delete character or cancel conversion
            if keyval == IBus.KEY_BackSpace:
                if self._in_conversion:
                    # Cancel conversion and go back to yomi
                    logger.debug('Backspace in CONVERTING: reverting to yomi')
                    self._cancel_conversion()
                    return True
                elif self._preedit_string:
                    # Delete last character from preedit
                    # TODO: Implement proper backspace handling with simul_processor
                    self._preedit_string = self._preedit_string[:-1]
                    self._preedit_hiragana = self._preedit_hiragana[:-1] if self._preedit_hiragana else ''
                    self._preedit_ascii = self._preedit_ascii[:-1] if self._preedit_ascii else ''
                    self._update_preedit()
                    return True
                return False

        # =====================================================================
        # REGULAR CHARACTER INPUT (simultaneous typing)
        # =====================================================================

        # Only process printable ASCII characters (0x20 space to 0x7e tilde)
        if keyval < 0x20 or keyval > 0x7e:
            return False

        # If in CONVERTING state and typing a new character, confirm and continue
        if is_pressed and self._in_conversion:
            logger.debug(f'Char input in CONVERTING: confirming and adding "{chr(keyval)}"')
            # Commit the selected candidate
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))
            # Reset state but keep bunsetsu mode if it was active
            self._in_conversion = False
            self._conversion_yomi = ''
            self._lookup_table.clear()
            self.hide_lookup_table()
            # Clear preedit for new input
            self._preedit_string = ''
            self._preedit_hiragana = ''
            self._preedit_ascii = ''
            # Continue to process the new character below

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
        If in CONVERTING state, commits the selected candidate first.
        If in BUNSETSU_ACTIVE state, commits the preedit as-is.
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

            # If in CONVERTING state, commit the selected candidate
            if self._in_conversion:
                logger.debug('disable_hiragana_key in CONVERTING: committing candidate')
                self._confirm_conversion()
            elif self._bunsetsu_active or self._preedit_string:
                # Commit any preedit as-is (no conversion)
                logger.debug('disable_hiragana_key with preedit: committing')
                self._commit_string()

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
    # KANCHOKU / BUNSETSU MARKER HANDLING
    # =========================================================================

    def _handle_kanchoku_bunsetsu_marker(self, key_name, keyval, state, is_pressed):
        """
        Handle kanchoku_bunsetsu_marker key and related sequences.

        This implements a state machine that distinguishes between:
        - Kanchoku: marker held → key1↓↑ → key2↓↑ → produces kanji
        - Bunsetsu: marker held → key1↓↑ → marker↑ → marks boundary (valid bunsetsu start)
        - Forced preedit: marker held → key1↓↑ → marker↑ → enter mode (if key is forced_preedit_trigger)

        Args:
            key_name: The key name from IBus.keyval_name()
            keyval: The key value
            state: Modifier state bitmask from IBus
            is_pressed: True if key press, False if key release

        Returns:
            bool: True if the key was consumed, False otherwise
        """
        marker_binding = self._config.get('kanchoku_bunsetsu_marker', '')
        if not marker_binding:
            return False

        is_marker_key = self._matches_key_binding(key_name, state, marker_binding)

        # === MARKER KEY HANDLING ===
        if is_marker_key:
            return self._handle_marker_key_event(is_pressed)

        # === OTHER KEYS WHILE MARKER HELD ===
        if self._marker_state != MarkerState.IDLE:
            return self._handle_key_while_marker_held(key_name, keyval, is_pressed)

        return False

    def _handle_marker_key_event(self, is_pressed):
        """
        Handle press/release of the marker key itself.

        On press: Commit existing preedit, enter MARKER_HELD state
        On release: Determine if this was bunsetsu marking or forced preedit trigger

        Returns:
            bool: True (marker key is always consumed)
        """
        if is_pressed:
            # Behavior on marker press depends on current henkan state
            if self._in_conversion:
                # CONVERTING state: prepare for potential space+key (new bunsetsu)
                # DON'T change _in_conversion yet - wait for release to know if tap or space+key
                # DON'T clear preedit - keep candidate visible
                self._pending_commit = self._preedit_string  # Save selected candidate for potential commit
                self._preedit_before_marker = self._preedit_string
                # Note: Keep _in_conversion = True so tap can cycle candidates
                logger.debug(f'Marker pressed in CONVERTING: saved candidate "{self._pending_commit}"')
            elif self._bunsetsu_active:
                # BUNSETSU_ACTIVE: save current yomi for potential implicit conversion
                self._preedit_before_marker = self._preedit_string
                logger.debug(f'Marker pressed in BUNSETSU_ACTIVE: saved yomi "{self._preedit_before_marker}"')
            else:
                # IDLE state: commit any existing preedit before starting marker sequence
                self._commit_string()
                self._preedit_before_marker = ''

            self._marker_state = MarkerState.MARKER_HELD
            self._marker_first_key = None
            self._marker_keys_held.clear()
            logger.debug('Marker pressed: entering MARKER_HELD state')
            return True

        # Marker released
        logger.debug(f'Marker released in state: {self._marker_state.name}, '
                    f'bunsetsu_active={self._bunsetsu_active}, in_conversion={self._in_conversion}')

        if self._marker_state == MarkerState.MARKER_HELD:
            # Marker was just tapped (pressed and released without other keys)
            # Behavior depends on current henkan state
            if self._in_conversion:
                # CONVERTING state: cycle to next candidate
                logger.debug('Space tap in CONVERTING: cycling candidate')
                self._pending_commit = ''  # Clear - it was only needed for space+key
                self._cycle_candidate()
            elif self._bunsetsu_active:
                # BUNSETSU_ACTIVE state: trigger conversion
                logger.debug('Space tap in BUNSETSU_ACTIVE: triggering conversion')
                self._trigger_conversion()
            else:
                # IDLE state: commit preedit + output space
                logger.debug('Space tap in IDLE: committing preedit + space')
                self._commit_string()
                self.commit_text(IBus.Text.new_from_string(' '))
        elif self._marker_state == MarkerState.FIRST_RELEASED:
            # Decision point: was this bunsetsu or forced preedit?
            self._handle_marker_release_decision()
        elif self._marker_state == MarkerState.KANCHOKU_SECOND_PRESSED:
            # Kanchoku was completed, just clean up
            pass
        # else: FIRST_PRESSED - incomplete sequence (key still held), just reset

        self._marker_state = MarkerState.IDLE
        self._marker_first_key = None
        self._marker_keys_held.clear()
        return True

    def _handle_marker_release_decision(self):
        """
        Handle the decision when marker is released after first key was pressed and released.

        If there's a pending commit (from CONVERTING state):
        - Commit the saved candidate first
        - Then proceed with the normal bunsetsu/forced-preedit/kanchoku logic

        If in BUNSETSU_ACTIVE state:
        - Perform implicit conversion and commit first candidate
        - Then proceed with new bunsetsu

        Check if first key was the forced_preedit_trigger_key:
        - If yes: Enter forced preedit mode (Case C)
        - If no: This was bunsetsu marking (Case B)
        """
        # Save the new bunsetsu content that was typed during space+key
        new_bunsetsu_preedit = self._preedit_string
        new_bunsetsu_hiragana = self._preedit_hiragana
        new_bunsetsu_ascii = self._preedit_ascii

        # Commit pending candidate from CONVERTING state
        if self._pending_commit:
            logger.debug(f'Committing pending candidate: "{self._pending_commit}"')
            self.commit_text(IBus.Text.new_from_string(self._pending_commit))
            self._pending_commit = ''
        elif self._bunsetsu_active:
            # In BUNSETSU_ACTIVE: perform implicit conversion on the saved yomi
            yomi = self._preedit_before_marker
            if yomi:
                candidates = self._henkan_processor.convert(yomi)
                if candidates:
                    surface = candidates[0]['surface']
                    logger.debug(f'Implicit conversion: "{yomi}" → "{surface}"')
                    self.commit_text(IBus.Text.new_from_string(surface))
                else:
                    logger.debug(f'No candidates for implicit conversion, committing yomi: "{yomi}"')
                    self.commit_text(IBus.Text.new_from_string(yomi))

        # Reset henkan state but preserve the new bunsetsu content
        self._bunsetsu_active = False
        self._in_conversion = False
        self._conversion_yomi = ''
        self._lookup_table.clear()
        self.hide_lookup_table()

        # Restore the new bunsetsu content
        self._preedit_string = new_bunsetsu_preedit
        self._preedit_hiragana = new_bunsetsu_hiragana
        self._preedit_ascii = new_bunsetsu_ascii

        forced_preedit_key = self._config.get('forced_preedit_trigger_key', 'f')

        if self._marker_first_key == forced_preedit_key:
            # Case (C): Forced preedit mode
            # Clear the tentative output (e.g., "ん") since it's not part of bunsetsu
            self._preedit_string = ''
            self._preedit_hiragana = ''
            self._preedit_ascii = ''
            self._update_preedit()
            self._in_forced_preedit = True
            logger.debug('Entering forced preedit mode (Case C)')
        else:
            # Case (B): Bunsetsu marking - start new bunsetsu
            # Keep the tentative output (e.g., "い") and mark boundary
            self._mark_bunsetsu_boundary()
            self._update_preedit()
            logger.debug(f'Bunsetsu started with "{self._preedit_string}" (Case B)')

    def _handle_key_while_marker_held(self, key_name, keyval, is_pressed):
        """
        Handle key events while marker is held.

        This processes the state machine transitions for kanchoku/bunsetsu sequences.

        Returns:
            bool: True if key was consumed, False otherwise
        """
        # Only process printable ASCII characters
        if keyval < 0x20 or keyval > 0x7e:
            return False

        key_char = chr(keyval).lower()

        if self._marker_state == MarkerState.MARKER_HELD:
            # Waiting for first key
            if is_pressed:
                self._marker_first_key = key_char
                self._marker_keys_held.add(key_char)

                # If we have a pending commit (from CONVERTING state), now we know
                # it's space+key (not a tap), so clear preedit and exit conversion mode
                if self._pending_commit:
                    # _preedit_before_marker was already set when space was pressed
                    self._preedit_string = ''
                    self._preedit_hiragana = ''
                    self._preedit_ascii = ''
                    self._in_conversion = False  # Now exit conversion mode
                    self._lookup_table.clear()
                    self.hide_lookup_table()
                    logger.debug(f'Clearing preedit for new bunsetsu (pending: "{self._pending_commit}")')
                else:
                    # Normal case: save current preedit
                    self._preedit_before_marker = self._preedit_string

                # Let simultaneous processor handle this key (tentative output)
                self._process_simultaneous_input(keyval, is_pressed)
                self._marker_state = MarkerState.FIRST_PRESSED
                logger.debug(f'First key pressed: "{key_char}" → FIRST_PRESSED')
            return True

        elif self._marker_state == MarkerState.FIRST_PRESSED:
            # First key is pressed, waiting for release
            if is_pressed:
                # Another key pressed while first is held (could be simultaneous)
                self._marker_keys_held.add(key_char)
                self._process_simultaneous_input(keyval, is_pressed)
            else:
                # A key released
                self._marker_keys_held.discard(key_char)
                self._process_simultaneous_input(keyval, is_pressed)
                if len(self._marker_keys_held) == 0:
                    # All keys released - transition to decision point
                    self._marker_state = MarkerState.FIRST_RELEASED
                    logger.debug('All keys released → FIRST_RELEASED (decision point)')
            return True

        elif self._marker_state == MarkerState.FIRST_RELEASED:
            # Decision point: waiting for key2 (kanchoku) or marker release (bunsetsu)
            if is_pressed:
                # Second key pressed - this is KANCHOKU (Case A)!
                logger.debug(f'Second key pressed: "{key_char}" → KANCHOKU')
                # Undo the tentative simultaneous output
                self._preedit_string = self._preedit_before_marker
                # Look up and emit kanchoku kanji
                kanji = self._kanchoku_processor._lookup_kanji(self._marker_first_key, key_char)
                self._emit_kanchoku_output(kanji)
                self._marker_keys_held.add(key_char)
                self._marker_state = MarkerState.KANCHOKU_SECOND_PRESSED
            return True

        elif self._marker_state == MarkerState.KANCHOKU_SECOND_PRESSED:
            # Second key pressed, waiting for release (then ready for another kanchoku)
            if is_pressed:
                # Another key while second is held - ignore or handle as needed
                pass
            else:
                # Key released
                self._marker_keys_held.discard(key_char)
                if len(self._marker_keys_held) == 0:
                    # Ready for another kanchoku sequence
                    self._marker_state = MarkerState.MARKER_HELD
                    self._marker_first_key = None
                    self._preedit_before_marker = self._preedit_string
                    logger.debug('Kanchoku complete, ready for next → MARKER_HELD')
            return True

        return False

    def _process_simultaneous_input(self, keyval, is_pressed):
        """
        Process a key through the simultaneous input processor.

        This is used during marker-held sequences to get tentative output
        that may be kept (bunsetsu) or discarded (kanchoku).
        """
        if keyval < 0x20 or keyval > 0x7e:
            return

        input_char = chr(keyval)

        # Get output from simultaneous processor
        output, pending = self._simul_processor.get_layout_output(
            self._preedit_string, input_char, is_pressed
        )

        logger.debug(f'Simultaneous processor: output="{output}", pending="{pending}"')

        # Update preedit with simultaneous output
        self._preedit_hiragana = output if output else ''
        new_preedit = self._preedit_hiragana + (pending if pending else '')
        self._preedit_string = new_preedit
        self._update_preedit()

    def _mark_bunsetsu_boundary(self):
        """
        Mark the start of a bunsetsu (phrase) for kana-kanji conversion.

        This activates bunsetsu mode where the preedit content becomes
        the yomi (reading) for conversion when space is tapped.
        """
        self._bunsetsu_active = True
        self._conversion_yomi = ''  # Will be populated from preedit when conversion triggers
        logger.debug(f'Bunsetsu started. Current preedit: "{self._preedit_string}"')

    def _emit_kanchoku_output(self, kanji):
        """
        Output a kanji from kanchoku input.

        In normal mode: Add to preedit
        In forced preedit mode: Add to preedit (for later kana-kanji conversion)
        """
        logger.debug(f'Kanchoku output: "{kanji}"')
        self._preedit_string += kanji
        self._update_preedit()

    # =========================================================================
    # HENKAN (KANA-KANJI CONVERSION) METHODS
    # =========================================================================

    def _trigger_conversion(self):
        """
        Trigger kana-kanji conversion on the current preedit (yomi).

        Called when space is tapped in BUNSETSU_ACTIVE state.
        Uses HenkanProcessor to look up candidates and either:
        - Single candidate: auto-replace in preedit
        - Multiple candidates: show lookup table for selection
        """
        if not self._preedit_string:
            logger.debug('_trigger_conversion: empty preedit, nothing to convert')
            return

        # Use hiragana as yomi for conversion
        self._conversion_yomi = self._preedit_hiragana if self._preedit_hiragana else self._preedit_string
        logger.debug(f'_trigger_conversion: yomi="{self._conversion_yomi}"')

        # Get candidates from HenkanProcessor
        candidates = self._henkan_processor.convert(self._conversion_yomi)

        if not candidates:
            # No candidates found - keep yomi as-is
            logger.debug('_trigger_conversion: no candidates found')
            return

        # Clear and populate lookup table
        self._lookup_table.clear()
        for candidate in candidates:
            self._lookup_table.append_candidate(
                IBus.Text.new_from_string(candidate['surface'])
            )

        if len(candidates) == 1:
            # Single candidate: auto-select and update preedit (but stay in conversion mode)
            self._preedit_string = candidates[0]['surface']
            self._update_preedit()
            self._in_conversion = True
            self._bunsetsu_active = False
            # Don't show lookup table for single candidate
            self.hide_lookup_table()
            logger.debug(f'_trigger_conversion: single candidate "{candidates[0]["surface"]}"')
        else:
            # Multiple candidates: show lookup table
            self._in_conversion = True
            self._bunsetsu_active = False
            self._preedit_string = candidates[0]['surface']  # Show first candidate in preedit
            self._update_preedit()
            self.update_lookup_table(self._lookup_table, True)
            logger.debug(f'_trigger_conversion: {len(candidates)} candidates, showing lookup table')

    def _cycle_candidate(self):
        """
        Cycle to the next conversion candidate.

        Called when space is tapped in CONVERTING state.
        """
        if not self._in_conversion:
            return

        # Move to next candidate (wraps around)
        self._lookup_table.cursor_down()

        # Update preedit with currently selected candidate
        cursor_pos = self._lookup_table.get_cursor_pos()
        candidate = self._lookup_table.get_candidate(cursor_pos)
        if candidate:
            self._preedit_string = candidate.get_text()
            self._update_preedit()
            # Show lookup table if multiple candidates
            if self._lookup_table.get_number_of_candidates() > 1:
                self.update_lookup_table(self._lookup_table, True)
            logger.debug(f'_cycle_candidate: selected "{self._preedit_string}" (index {cursor_pos})')

    def _cycle_candidate_backward(self):
        """
        Cycle to the previous conversion candidate.

        Called when Up arrow is pressed in CONVERTING state.
        """
        if not self._in_conversion:
            return

        # Move to previous candidate (wraps around)
        self._lookup_table.cursor_up()

        # Update preedit with currently selected candidate
        cursor_pos = self._lookup_table.get_cursor_pos()
        candidate = self._lookup_table.get_candidate(cursor_pos)
        if candidate:
            self._preedit_string = candidate.get_text()
            self._update_preedit()
            # Show lookup table if multiple candidates
            if self._lookup_table.get_number_of_candidates() > 1:
                self.update_lookup_table(self._lookup_table, True)
            logger.debug(f'_cycle_candidate_backward: selected "{self._preedit_string}" (index {cursor_pos})')

    def _cancel_conversion(self):
        """
        Cancel conversion and revert to the original yomi.

        Called when Escape or Backspace is pressed in CONVERTING state.
        """
        if not self._in_conversion:
            return

        # Restore the original yomi
        self._preedit_string = self._conversion_yomi
        self._preedit_hiragana = self._conversion_yomi
        self._in_conversion = False
        self._bunsetsu_active = True  # Go back to bunsetsu mode
        self._lookup_table.clear()
        self.hide_lookup_table()
        self._update_preedit()
        logger.debug(f'_cancel_conversion: reverted to yomi "{self._conversion_yomi}"')

    def _confirm_conversion(self):
        """
        Confirm the currently selected conversion candidate.

        Commits the selected candidate and resets henkan state.
        """
        if self._in_conversion and self._preedit_string:
            logger.debug(f'_confirm_conversion: committing "{self._preedit_string}"')
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))

        # Reset all henkan state
        self._reset_henkan_state()

    def _commit_with_implicit_conversion(self):
        """
        Perform implicit conversion and commit.

        Called when user performs an action that should commit the current state:
        - In BUNSETSU_ACTIVE: convert and commit first candidate
        - In CONVERTING: commit the currently selected candidate

        This implements "Option B" behavior where space+key implicitly
        converts and commits before starting a new action.
        """
        if self._in_conversion:
            # Already in conversion - commit the selected candidate
            logger.debug(f'_commit_with_implicit_conversion: committing selected "{self._preedit_string}"')
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))
        elif self._bunsetsu_active:
            # In bunsetsu mode - perform conversion and commit first candidate
            yomi = self._preedit_hiragana if self._preedit_hiragana else self._preedit_string
            if yomi:
                candidates = self._henkan_processor.convert(yomi)
                if candidates:
                    # Commit first candidate
                    surface = candidates[0]['surface']
                    logger.debug(f'_commit_with_implicit_conversion: converting "{yomi}" → "{surface}"')
                    self.commit_text(IBus.Text.new_from_string(surface))
                else:
                    # No candidates - commit yomi as-is
                    logger.debug(f'_commit_with_implicit_conversion: no candidates, committing yomi "{yomi}"')
                    self.commit_text(IBus.Text.new_from_string(yomi))

        # Reset henkan state
        self._reset_henkan_state()

    def _reset_henkan_state(self):
        """
        Reset all henkan-related state variables.

        Called after conversion is confirmed or cancelled.
        """
        self._bunsetsu_active = False
        self._in_conversion = False
        self._conversion_yomi = ''
        self._pending_commit = ''
        self._preedit_string = ''
        self._preedit_hiragana = ''
        self._preedit_ascii = ''
        self._lookup_table.clear()
        self.hide_lookup_table()
        self._update_preedit()
        logger.debug('_reset_henkan_state: state cleared')

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
            # Use COMMIT mode so preedit is committed on focus change (e.g., clicking elsewhere)
            self.update_preedit_text_with_mode(
                preedit_text,
                len(self._preedit_string),  # cursor at end
                True,  # visible
                IBus.PreeditFocusMode.COMMIT
            )
        else:
            # Hide preedit when empty
            self.update_preedit_text_with_mode(
                IBus.Text.new_from_string(''),
                0,
                False,  # not visible
                IBus.PreeditFocusMode.CLEAR
            )

