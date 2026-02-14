import util
import settings_panel
import conversion_model
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
from gi.repository import Gtk, IBus, GLib
# http://lazka.github.io/pgi-docs/IBus-1.0/index.html?fbclid=IwY2xjawG9hapleHRuA2FlbQIxMAABHXaZwlJVVZEl9rr2SWsvIy2x85xW-XJuu32OZYxQ3gxF-E__9kWOUqGNzA_aem_2zw0hES6WqJcXPds_9CEdA
# http://lazka.github.io/pgi-docs/Gtk-4.0/index.html?fbclid=IwY2xjawG9hatleHRuA2FlbQIxMAABHVsKSY24bv9C75Mweq54yhLsePdGA25YfLnwMwCx7vEq03oV61qn_qEntg_aem_3k1P3ltIMb17cBH0fdPr4w
# http://lazka.github.io/pgi-docs/GLib-2.0/index.html?fbclid=IwY2xjawG9hatleHRuA2FlbQIxMAABHXaZwlJVVZEl9rr2SWsvIy2x85xW-XJuu32OZYxQ3gxF-E__9kWOUqGNzA_aem_2zw0hES6WqJcXPds_9CEdA

logger = logging.getLogger(__name__)

APPLICABLE_STROKE_SET_FOR_JAPANESE = set(list('1234567890qwertyuiopasdfghjk;lzxcvbnm,./'))

KANCHOKU_KEY_SET = set(list('qwertyuiopasdfghjkl;zxcvbnm,./'))
MISSING_KANCHOKU_KANJI = '無'

# modifier mask-bit segment
STATUS_SPACE        = 0x001
#STATUS_SHIFT_L      = 0x002 # this value is currently not meant to be used directly
#STATUS_SHIFT_R      = 0x004 # this value is currently not meant to be used directly
#STATUS_CONTROL_L    = 0x008
#STATUS_CONTROL_R    = 0x010
#STATUS_ALT_L        = 0x020
#STATUS_ALT_R        = 0x040
#STATUS_SUPER_L      = 0x080
#STATUS_SUPER_R      = 0x100
#STATUS_SHIFTS       = STATUS_SHIFT_L | STATUS_SHIFT_R
#STATUS_CONTROLS     = STATUS_CONTROL_L | STATUS_CONTROL_R
#STATUS_ALTS         = STATUS_ALT_L | STATUS_ALT_R
#STATUS_SUPERS       = STATUS_SUPER_L | STATUS_SUPER_R
#STATUS_MODIFIER     = STATUS_SHIFTS  | STATUS_CONTROLS | STATUS_ALTS | STATUS_SPACE | STATUS_SUPERS

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


class EnginePSKK(IBus.Engine):
    '''
    http://lazka.github.io/pgi-docs/IBus-1.0/classes/Engine.html
    '''
    __gtype_name__ = 'EnginePSKK'

    def __init__(self):
        super().__init__()
        # setting the initial input mode
        self._mode = 'A'  # _mode must be one of _input_mode_names
        #self._mode = 'あ'  # DEBUG I do not like to click extra...
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
        self._marker_had_input = False          # True if any key was pressed during this marker hold
        self._preedit_before_marker = ''        # Preedit snapshot to restore if kanchoku
        self._in_forced_preedit = False         # True when in forced preedit mode (Case C)

        # Henkan (kana-kanji conversion) state variables
        self._bunsetsu_active = False           # True when bunsetsu mode is active (yomi input)
        self._in_conversion = False             # True when showing conversion candidates
        self._conversion_yomi = ''              # The yomi string being converted

        self._preedit_string = ''    # Display buffer (can be hiragana, katakana, ascii, or zenkaku)
        self._preedit_hiragana = ''  # Source of truth: hiragana output from simul_processor
        self._preedit_ascii = ''     # Source of truth: raw ASCII input characters
        self._conversion_disabled = False  # Set True after backspace; disables Ctrl+K/J/L conversions
        self._converted = False  # Set True after Ctrl+K/J/L; next char input auto-commits
        self._previous_text = ''

        # This property is for confirming the kanji-kana converted string
        # LookupTable.new(page_size, cursor_pos, cursor_visible, round)
        # round=True enables wrap-around when cycling candidates
        self._lookup_table = IBus.LookupTable.new(10, 0, True, True)
        self._lookup_table.set_orientation(IBus.Orientation.VERTICAL)

        self._init_props()
        #self.register_properties(self._prop_list)

        # load configs
        self._load_configs()
        self._layout_data = util.get_layout_data(self._config)
        self._simul_processor = SimultaneousInputProcessor(self._layout_data)
        self._kanchoku_layout = self._load_kanchoku_layout()
        self._kanchoku_processor = KanchokuProcessor(self._kanchoku_layout)
        # Initialize henkan (kana-kanji conversion) processor with dictionaries
        dictionary_files = util.get_dictionary_files(self._config)
        self._henkan_processor = HenkanProcessor(dictionary_files)

        # Input mode defaults to 'A' (set in self._mode above)
        # For debugging, uncomment: self.set_mode('あ')

        self.connect('set-cursor-location', self.set_cursor_location_cb)

        self._about_dialog = None
        self._settings_panel = None
        self._conversion_model_panel = None
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
        self._preedit_string = ''
        self._preedit_hiragana = ''
        self._preedit_ascii = ''

        # Reset marker state
        self._marker_state = MarkerState.IDLE
        self._marker_first_key = None
        self._marker_keys_held.clear()
        self._marker_had_input = False


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
        conversion_model_prop = IBus.Property(
            key='ConversionModel',
            prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("Conversion Model..."),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        self._prop_list.append(conversion_model_prop)
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

    def _show_conversion_model_panel(self):
        if self._conversion_model_panel:
            self._conversion_model_panel.present()
            return False  # Don't repeat this idle callback

        panel = conversion_model.ConversionModelPanel()
        panel.connect("destroy", self.conversion_model_panel_closed_callback)
        self._conversion_model_panel = panel
        panel.show_all()

        return False  # Don't repeat this idle callback


    def do_property_activate(self, prop_name, state):
        logger.info(f'property_activate({prop_name}, {state})')
        if prop_name == 'Settings':
            # Schedule settings panel creation on the main loop
            GLib.idle_add(self._show_settings_panel)
            return
        elif prop_name == 'ConversionModel':
            # Schedule conversion model panel creation on the main loop
            GLib.idle_add(self._show_conversion_model_panel)
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

    def conversion_model_panel_closed_callback(self, panel):
        self._conversion_model_panel = None

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

        # Pass through unrecognized combo-keys (e.g. Ctrl+0, Ctrl+C, Alt+F4)
        # so the application can handle them.  Shift is excluded since it is
        # part of normal typing (Shift+a → 'A').
        combo_mask = (IBus.ModifierType.CONTROL_MASK |
                      IBus.ModifierType.MOD1_MASK |
                      IBus.ModifierType.SUPER_MASK)
        if state & combo_mask and key_name not in modifier_key_names:
            # Before passing through the combo-key back to IBus, commit the preedit buffer.
            self._commit_string()
            self._in_forced_preedit = False
            self._bunsetsu_active = False
            self._in_conversion = False
            self._conversion_yomi = ''
            self._lookup_table.clear()
            self.hide_lookup_table()
            return False

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
                elif self._in_forced_preedit and self._preedit_string:
                    # Forced preedit: commit and consume Enter (Action 2)
                    logger.debug('Enter pressed in FORCED_PREEDIT: committing')
                    self._commit_string()
                    self._in_forced_preedit = False
                    return True
                elif self._bunsetsu_active and self._preedit_string:
                    # Bunsetsu mode: commit and consume Enter
                    logger.debug('Enter pressed in BUNSETSU: committing')
                    self._commit_string()
                    self._bunsetsu_active = False
                    return True
                elif self._preedit_string:
                    # IDLE mode with preedit: commit and pass Enter through
                    logger.debug('Enter pressed in IDLE with preedit: committing and passing through')
                    self._commit_string()
                    return False  # Pass Enter to application
                return False  # No preedit, pass through

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
                elif keyval == IBus.KEY_Right or keyval == IBus.KEY_KP_Right:
                    # Right arrow: move to next bunsetsu (bunsetsu mode only)
                    if self._henkan_processor.is_bunsetsu_mode():
                        self._henkan_processor.next_bunsetsu()
                        self._update_preedit()  # Update display with new selection
                        logger.debug(f'Right arrow: moved to bunsetsu {self._henkan_processor.get_selected_bunsetsu_index()}')
                        return True
                    return False  # Pass through in whole-word mode
                elif keyval == IBus.KEY_Left or keyval == IBus.KEY_KP_Left:
                    # Left arrow: move to previous bunsetsu (bunsetsu mode only)
                    if self._henkan_processor.is_bunsetsu_mode():
                        self._henkan_processor.previous_bunsetsu()
                        self._update_preedit()  # Update display with new selection
                        logger.debug(f'Left arrow: moved to bunsetsu {self._henkan_processor.get_selected_bunsetsu_index()}')
                        return True
                    return False  # Pass through in whole-word mode

            # Arrow keys in IDLE mode: commit preedit and pass through
            if keyval in (IBus.KEY_Left, IBus.KEY_KP_Left,
                          IBus.KEY_Right, IBus.KEY_KP_Right,
                          IBus.KEY_Up, IBus.KEY_KP_Up,
                          IBus.KEY_Down, IBus.KEY_KP_Down):
                if self._preedit_string:
                    self._commit_string()
                return False

            # Escape / Delete - cancel conversion or clear preedit
            if keyval == IBus.KEY_Escape or keyval == IBus.KEY_Delete:
                if self._in_conversion:
                    logger.debug('Escape/Delete in CONVERTING: cancelling, reverting to yomi')
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
                    # _preedit_hiragana is in 1:1 correspondence with _preedit_string,
                    # so trim both to keep conversion yomi in sync.
                    # Disable Ctrl+K/J/L conversions after backspace because we can't
                    # reliably track the many-to-one mapping from keystrokes to hiragana
                    # in _preedit_ascii. User must ESC and retype, or commit and start fresh.
                    self._preedit_string = self._preedit_string[:-1]
                    self._preedit_hiragana = self._preedit_hiragana[:-1]
                    # Disable conversion after backspace because we can't reliably track
                    # the many-to-one mapping from keystrokes to hiragana in _preedit_ascii.
                    # However, re-enable if preedit is now empty (fresh start for next input).
                    if self._preedit_string:
                        self._conversion_disabled = True
                    else:
                        self._conversion_disabled = False
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
            # Reset state - new char confirms conversion and exits forced preedit
            self._in_conversion = False
            self._in_forced_preedit = False  # Exit forced preedit mode (Action 1)
            self._conversion_yomi = ''
            self._lookup_table.clear()
            self.hide_lookup_table()
            # Clear preedit for new input
            self._preedit_string = ''
            self._preedit_hiragana = ''
            self._preedit_ascii = ''
            # Continue to process the new character below

        # If preedit was converted (e.g., to katakana via Ctrl+K), commit it
        # before starting fresh input. Unlike _in_conversion, this flag does NOT
        # affect Escape/Enter/arrow behavior (they treat it as normal IDLE preedit).
        elif is_pressed and self._converted:
            logger.debug(f'Char input after conversion: committing "{self._preedit_string}"')
            self._commit_string()
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

        # Check bunsetsu_prediction_cycle_key
        if self._check_bunsetsu_prediction_key(key_name, state, is_pressed):
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
            self._update_input_mode()  # Update IBus icon
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
            self._update_input_mode()  # Update IBus icon
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
        # When preedit is empty, let the key pass through to the application
        # (e.g., Ctrl+L should reach the browser to select the URL bar)
        if not self._preedit_string:
            return False

        for conversion_type, binding in conversion_keys.items():
            if self._matches_key_binding(key_name, state, binding):
                logger.debug(f'conversion_key matched: {conversion_type} = {binding}')
                self._handle_conversion(conversion_type)
                self._handled_config_keys.add(key_name)
                return True

        return False

    def _check_bunsetsu_prediction_key(self, key_name, state, is_pressed):
        """
        Check and handle bunsetsu_prediction_cycle_key binding.

        This key cycles through N-best bunsetsu prediction candidates.
        """
        binding = self._config.get('bunsetsu_prediction_cycle_key', '')
        if not binding:
            return False

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # On press: check if key matches the binding
        if self._matches_key_binding(key_name, state, binding):
            logger.debug(f'bunsetsu_prediction_cycle_key matched: {binding}')
            self._cycle_bunsetsu_prediction()
            self._handled_config_keys.add(key_name)
            return True

        return False

    def _cycle_bunsetsu_prediction(self):
        """
        Cycle to the next N-best bunsetsu prediction candidate.

        This is triggered by bunsetsu_prediction_cycle_key and cycles through:
        - Whole-word dictionary match (if available)
        - CRF N-best #1 (if multi-bunsetsu)
        - CRF N-best #2 (if multi-bunsetsu)
        - ... and wraps around
        """
        if not self._in_conversion:
            logger.debug('_cycle_bunsetsu_prediction: not in conversion mode')
            return

        # Cycle to next prediction
        changed = self._henkan_processor.cycle_bunsetsu_prediction()
        if not changed:
            logger.debug('_cycle_bunsetsu_prediction: no change (no predictions available)')
            return

        # Update preedit with new prediction
        self._preedit_string = self._henkan_processor.get_display_surface()
        self._update_preedit()

        # Update lookup table if not in bunsetsu mode (whole-word mode has lookup table)
        if not self._henkan_processor.is_bunsetsu_mode():
            # Back to whole-word mode - restore lookup table
            self._lookup_table.set_cursor_pos(0)
            self.update_lookup_table(self._lookup_table, True)
        else:
            # In bunsetsu mode - hide whole-word lookup table
            self.hide_lookup_table()

        logger.debug(f'_cycle_bunsetsu_prediction: bunsetsu_mode={self._henkan_processor.is_bunsetsu_mode()}, '
                    f'surface="{self._preedit_string}"')

    def _handle_conversion(self, conversion_type):
        """
        Perform the actual conversion of preedit string.

        Uses source-of-truth buffers:
        - _preedit_hiragana: for to_katakana and to_hiragana
        - _preedit_ascii: for to_ascii and to_zenkaku

        Note: All conversions are disabled after backspace is used, because we can't
        reliably track the many-to-one mapping from keystrokes to hiragana.
        User must ESC and retype, or commit and start fresh to re-enable.

        Args:
            conversion_type: One of 'to_katakana', 'to_hiragana', 'to_ascii', 'to_zenkaku'
        """
        if not self._preedit_string:
            return

        # All conversions disabled after backspace
        if self._conversion_disabled:
            logger.debug(f'Conversion {conversion_type} skipped: disabled after backspace')
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

        # Exit bunsetsu/conversion mode when doing character conversion
        # (user explicitly wants katakana/hiragana/ascii/zenkaku, not kanji)
        if self._in_conversion:
            self._in_conversion = False
            self._henkan_processor.reset()
            self.hide_lookup_table()
            logger.debug(f'Exited conversion mode for {conversion_type}')

        # Mark as converted so the next character input auto-commits this preedit.
        # Escape/Enter/arrow keys ignore this flag and treat it as normal IDLE preedit.
        self._converted = True

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
                # DON'T clear preedit - keep candidate visible so it can be committed
                # directly when we confirm it's space+key (in MARKER_HELD key-press handler)
                self._preedit_before_marker = self._preedit_string
                # Note: Keep _in_conversion = True so tap can cycle candidates
                logger.debug(f'Marker pressed in CONVERTING: candidate "{self._preedit_string}"')
            elif self._bunsetsu_active or self._in_forced_preedit:
                # BUNSETSU_ACTIVE or FORCED_PREEDIT: save current yomi for potential implicit conversion
                self._preedit_before_marker = self._preedit_string
                logger.debug(f'Marker pressed in BUNSETSU/FORCED_PREEDIT: saved yomi "{self._preedit_before_marker}"')
            else:
                # IDLE state: commit any existing preedit before starting marker sequence
                self._commit_string()
                self._preedit_before_marker = ''

            self._marker_state = MarkerState.MARKER_HELD
            self._marker_first_key = None
            self._marker_keys_held.clear()
            self._marker_had_input = False
            logger.debug('Marker pressed: entering MARKER_HELD state')
            return True

        # Marker released
        logger.debug(f'Marker released in state: {self._marker_state.name}, '
                    f'bunsetsu_active={self._bunsetsu_active}, in_conversion={self._in_conversion}')

        if self._marker_state == MarkerState.MARKER_HELD:
            if self._marker_had_input:
                # Keys were pressed during this space hold (e.g. kanchoku completed
                # and returned to MARKER_HELD). This is NOT a tap — just release cleanly.
                logger.debug('Space released after input (not a tap), no action')
            elif self._in_conversion:
                # CONVERTING state: cycle to next candidate
                logger.debug('Space tap in CONVERTING: cycling candidate')
                self._cycle_candidate()
            elif self._bunsetsu_active or self._in_forced_preedit:
                # BUNSETSU_ACTIVE or FORCED_PREEDIT state: trigger conversion
                logger.debug('Space tap in BUNSETSU/FORCED_PREEDIT: triggering conversion')
                self._trigger_conversion()
            else:
                # IDLE state: commit preedit + output space
                logger.debug('Space tap in IDLE: committing preedit + space')
                self._commit_string()
                self.commit_text(IBus.Text.new_from_string(' '))
                # Ensure conversion is re-enabled for next input (fresh start)
                self._conversion_disabled = False
        elif self._marker_state == MarkerState.FIRST_RELEASED:
            # Decision point: was this bunsetsu or forced preedit?
            self._handle_marker_release_decision()
        elif self._marker_state == MarkerState.KANCHOKU_SECOND_PRESSED:
            # Kanchoku was completed, just clean up
            pass
        elif self._marker_state == MarkerState.FIRST_PRESSED:
            # First key is still held when marker released - this is bunsetsu mode
            # (User typed quickly: space down → key down → space up → key up)
            # Treat this the same as FIRST_RELEASED - activate bunsetsu mode
            logger.debug('Marker released while first key held: treating as bunsetsu')
            self._handle_marker_release_decision()

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

        # Commit previous bunsetsu content via implicit conversion
        if self._bunsetsu_active or self._in_forced_preedit:
            # In BUNSETSU_ACTIVE or FORCED_PREEDIT: perform implicit conversion on the saved yomi
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
        self._in_forced_preedit = False  # Exit forced preedit when starting new bunsetsu
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
                self._marker_had_input = True

                # If in CONVERTING state, now we know it's space+key (not a tap),
                # so commit the current candidate directly and exit conversion mode
                if self._in_conversion:
                    logger.debug(f'Committing candidate for new bunsetsu: "{self._preedit_string}"')
                    self.commit_text(IBus.Text.new_from_string(self._preedit_string))
                    self._preedit_string = ''
                    self._preedit_hiragana = ''
                    self._preedit_ascii = ''
                    self._preedit_before_marker = ''  # Clear to prevent double commit in release handler
                    self._in_conversion = False
                    self._lookup_table.clear()
                    self.hide_lookup_table()
                else:
                    # Normal case: save current preedit
                    self._preedit_before_marker = self._preedit_string

                # Let simultaneous processor handle this key (tentative output)
                self._process_simultaneous_input(keyval, is_pressed)
                self._marker_state = MarkerState.FIRST_PRESSED
                logger.debug(f'First key pressed: "{key_char}" → FIRST_PRESSED')
            else:
                # Key release while waiting for first key - this can happen when user
                # releases a key from previous input after pressing marker (space).
                # Process the release to finalize the character in simultaneous processor.
                logger.debug(f'Key released in MARKER_HELD (prior input): "{key_char}"')
                self._process_simultaneous_input(keyval, is_pressed)
                # Update saved preedit to include the finalized character
                self._preedit_before_marker = self._preedit_string
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
                # Check if kanchoku is allowed in current state
                # Kanchoku is BLOCKED in normal bunsetsu mode (but allowed in forced preedit)
                if self._bunsetsu_active and not self._in_forced_preedit:
                    # In normal bunsetsu mode - kanchoku is NOT allowed
                    # Ignore this key press and stay in FIRST_RELEASED state
                    logger.debug(f'Kanchoku blocked in bunsetsu mode, ignoring key: "{key_char}"')
                    return True

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
        Uses HenkanProcessor to look up candidates and converts the preedit
        to the first candidate. The lookup table is NOT shown on this first
        conversion - it only appears on the 2nd space press (via _cycle_candidate).

        Behavior:
        - Dictionary match: update preedit with 1st candidate (lookup table hidden)
        - No match: automatically enter bunsetsu mode with CRF prediction
        """
        if not self._preedit_string:
            logger.debug('_trigger_conversion: empty preedit, nothing to convert')
            return

        # Use hiragana as yomi for conversion
        self._conversion_yomi = self._preedit_hiragana if self._preedit_hiragana else self._preedit_string
        logger.debug(f'_trigger_conversion: yomi="{self._conversion_yomi}"')

        # Get candidates from HenkanProcessor
        # This will automatically enter bunsetsu mode if no dictionary match
        candidates = self._henkan_processor.convert(self._conversion_yomi)

        if not candidates:
            # No candidates found - keep yomi as-is
            logger.debug('_trigger_conversion: no candidates found')
            return

        # Enter conversion mode
        self._in_conversion = True
        self._bunsetsu_active = False

        # Check if we're in bunsetsu mode (automatic fallback when no dictionary match)
        if self._henkan_processor.is_bunsetsu_mode():
            # Bunsetsu mode: display combined surface, hide lookup table
            self._preedit_string = self._henkan_processor.get_display_surface()
            self._update_preedit()
            self.hide_lookup_table()
            logger.debug(f'_trigger_conversion: bunsetsu mode, surface="{self._preedit_string}", '
                        f'{self._henkan_processor.get_bunsetsu_count()} bunsetsu')
        else:
            # Whole-word mode: populate and show lookup table
            self._lookup_table.clear()
            for candidate in candidates:
                self._lookup_table.append_candidate(
                    IBus.Text.new_from_string(candidate['surface'])
                )

            self._preedit_string = candidates[0]['surface']
            self._update_preedit()

            # Don't show lookup table on first conversion
            # Lookup table will be shown on 2nd space (in _cycle_candidate)
            self.hide_lookup_table()
            logger.debug(f'_trigger_conversion: {len(candidates)} candidate(s), lookup table hidden')

    def _cycle_candidate(self):
        """
        Cycle to the next conversion candidate.

        Called when space is tapped or Down arrow is pressed in CONVERTING state.
        In bunsetsu mode, cycles candidates for the currently selected bunsetsu.
        """
        if not self._in_conversion:
            return

        if self._henkan_processor.is_bunsetsu_mode():
            # Bunsetsu mode: cycle candidates for selected bunsetsu
            new_candidate = self._henkan_processor.next_bunsetsu_candidate()
            if new_candidate:
                # Update combined display surface
                self._preedit_string = self._henkan_processor.get_display_surface()
                self._update_preedit()
                logger.debug(f'_cycle_candidate (bunsetsu): selected "{new_candidate["surface"]}" '
                           f'for bunsetsu {self._henkan_processor.get_selected_bunsetsu_index()}')
            else:
                # Passthrough bunsetsu has no alternatives
                logger.debug('_cycle_candidate (bunsetsu): passthrough bunsetsu, no alternatives')
        else:
            # Whole-word mode: use lookup table
            self._lookup_table.cursor_down()

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
        In bunsetsu mode, cycles candidates backward for the currently selected bunsetsu.
        """
        if not self._in_conversion:
            return

        if self._henkan_processor.is_bunsetsu_mode():
            # Bunsetsu mode: cycle candidates backward for selected bunsetsu
            new_candidate = self._henkan_processor.previous_bunsetsu_candidate()
            if new_candidate:
                # Update combined display surface
                self._preedit_string = self._henkan_processor.get_display_surface()
                self._update_preedit()
                logger.debug(f'_cycle_candidate_backward (bunsetsu): selected "{new_candidate["surface"]}" '
                           f'for bunsetsu {self._henkan_processor.get_selected_bunsetsu_index()}')
            else:
                # Passthrough bunsetsu has no alternatives
                logger.debug('_cycle_candidate_backward (bunsetsu): passthrough bunsetsu, no alternatives')
        else:
            # Whole-word mode: use lookup table
            self._lookup_table.cursor_up()

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

        Behavior differs based on mode:
        - Normal bunsetsu: Revert to yomi and stay in bunsetsu mode for editing
        - Forced preedit: Exit entirely (Escape cancels forced preedit completely)
        """
        if not self._in_conversion:
            return

        if self._in_forced_preedit:
            # In forced preedit mode: Escape exits entirely (per user spec)
            logger.debug('_cancel_conversion: exiting forced preedit mode entirely')
            self._reset_henkan_state()
        else:
            # Normal bunsetsu: revert to yomi and stay in bunsetsu mode
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
        self._in_forced_preedit = False
        self._conversion_disabled = False  # Re-enable Ctrl+K/J/L conversions
        self._converted = False
        self._conversion_yomi = ''
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
            # Save the text to commit before clearing buffers
            text_to_commit = self._preedit_string
            # Clear preedit display FIRST to avoid race condition:
            # commit_text() does not auto-clear the COMMIT-mode preedit,
            # so a forwarded key event (return False) could arrive at the
            # client before the preedit-clear signal, causing the client
            # to auto-commit the preedit as well (double output).
            self._preedit_string = ""
            self._preedit_hiragana = ""
            self._preedit_ascii = ""
            self._conversion_disabled = False  # Re-enable Ctrl+K/J/L for next input
            self._converted = False
            self._update_preedit()
            self.commit_text(IBus.Text.new_from_string(text_to_commit))

    def _parse_hex_color(self, color_str):
        """
        Parse a hex color string to an integer value for IBus attributes.

        Args:
            color_str: Color string in format "0xRRGGBB" or "RRGGBB"

        Returns:
            int: Color value as integer, or None if parsing fails
        """
        if not color_str:
            return None
        try:
            # Strip "0x" or "0X" prefix if present
            color_str = color_str.strip()
            if color_str.lower().startswith('0x'):
                color_str = color_str[2:]
            return int(color_str, 16)
        except (ValueError, AttributeError):
            logger.warning(f'Failed to parse color value: {color_str}')
            return None

    def _update_preedit(self):
        """Update the preedit display in the application with configured colors.

        In bunsetsu mode, shows each bunsetsu with the selected one highlighted
        using a double underline, while non-selected bunsetsu have single underline.
        """
        if self._preedit_string:
            preedit_text = IBus.Text.new_from_string(self._preedit_string)
            attrs = IBus.AttrList()
            preedit_len = len(self._preedit_string)

            # In IDLE mode (not bunsetsu, forced-preedit, or conversion) with
            # log-level above DEBUG, render the preedit without any visual
            # styling so it appears as if already committed.  In DEBUG mode
            # the underline/background is kept for development visibility.
            is_idle = (not self._bunsetsu_active
                       and not self._in_forced_preedit
                       and not self._in_conversion)
            stealth = is_idle and self._logging_level != 'DEBUG'

            # Check if we're in bunsetsu mode for special display handling
            in_bunsetsu_mode = (self._in_conversion and
                               self._henkan_processor.is_bunsetsu_mode())

            if stealth:
                # Explicitly set UNDERLINE_NONE to override the default
                # preedit underline that GTK/IBus clients add automatically.
                attrs.append(IBus.Attribute.new(
                    IBus.AttrType.UNDERLINE,
                    IBus.AttrUnderline.NONE,
                    0,
                    preedit_len
                ))
                logger.debug('Stealth preedit: no styling in IDLE mode')
            elif in_bunsetsu_mode:
                # Bunsetsu mode: show selected bunsetsu with double underline,
                # non-selected bunsetsu with single underline
                bunsetsu_segments = self._henkan_processor.get_display_surface_with_selection()
                pos = 0
                for surface, is_selected in bunsetsu_segments:
                    segment_len = len(surface)
                    if segment_len == 0:
                        continue

                    # Set underline style based on selection
                    underline_style = (IBus.AttrUnderline.DOUBLE if is_selected
                                      else IBus.AttrUnderline.SINGLE)
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.UNDERLINE,
                        underline_style,
                        pos,
                        pos + segment_len
                    ))

                    # Apply background color to selected bunsetsu for better visibility
                    if is_selected:
                        selected_bg = self._parse_hex_color(
                            self._config.get('preedit_background_color', '0xd1eaff')
                        )
                        if selected_bg is not None:
                            attrs.append(IBus.Attribute.new(
                                IBus.AttrType.BACKGROUND,
                                selected_bg,
                                pos,
                                pos + segment_len
                            ))

                    pos += segment_len

                logger.debug(f'Bunsetsu mode preedit: {len(bunsetsu_segments)} segments, '
                           f'selected={self._henkan_processor.get_selected_bunsetsu_index()}')
            elif self._config.get('use_ibus_hint_colors', False):
                # Use IBus AttrType.HINT for theme-based styling (requires IBus >= 1.5.33)
                # AttrPreedit.WHOLE (1) indicates the entire preedit text
                try:
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.HINT,
                        1,  # IBus.AttrPreedit.WHOLE
                        0,
                        preedit_len
                    ))
                    logger.debug('Using IBus HINT styling for preedit')
                except Exception as e:
                    logger.warning(f'Failed to apply HINT attribute (IBus >= 1.5.33 required): {e}')
                    # Fall back to underline
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.UNDERLINE,
                        IBus.AttrUnderline.SINGLE,
                        0,
                        preedit_len
                    ))
            else:
                # Use explicit foreground and background colors from config
                fg_color = self._parse_hex_color(
                    self._config.get('preedit_foreground_color', '0x000000')
                )
                bg_color = self._parse_hex_color(
                    self._config.get('preedit_background_color', '0xd1eaff')
                )

                # Add foreground color attribute
                if fg_color is not None:
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.FOREGROUND,
                        fg_color,
                        0,
                        preedit_len
                    ))

                # Add background color attribute
                if bg_color is not None:
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.BACKGROUND,
                        bg_color,
                        0,
                        preedit_len
                    ))

                # Also add underline for better visibility
                attrs.append(IBus.Attribute.new(
                    IBus.AttrType.UNDERLINE,
                    IBus.AttrUnderline.SINGLE,
                    0,
                    preedit_len
                ))

                logger.debug(f'Using explicit preedit colors: fg=0x{fg_color:06x}, bg=0x{bg_color:06x}')

            preedit_text.set_attributes(attrs)

            # Use COMMIT mode so preedit is committed on focus change (e.g., clicking elsewhere)
            self.update_preedit_text_with_mode(
                preedit_text,
                preedit_len,  # cursor at end
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

