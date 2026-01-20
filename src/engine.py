import util
import settings_panel
from simultaneous_processor import SimultaneousInputProcessor

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
        self._sands_key_set = set()
        self._first_kanchoku_stroke = ""

        self._preedit_string = ''
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
        # Alphanumeric mode: pass everything through (no modkey tracking needed)
        if self._mode == 'A':
            return False

        # Determine if this is a key press or release
        is_pressed = not (state & IBus.ModifierType.RELEASE_MASK)

        # Process the key event
        result = self._process_key_event(keyval, keycode, state, is_pressed)

        # Update modifier key status before returning
        self._update_modkey_status(keyval, is_pressed)

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

        # TODO: Modifier key handling (Shift, Ctrl, etc.)

        # TODO: Special key handling (Enter, Backspace, Escape)

        # =====================================================================
        # REGULAR CHARACTER INPUT
        # =====================================================================

        # Only process printable ASCII characters (0x20 space to 0x7e tilde)
        if keyval < 0x20 or keyval > 0x7e:
            return False

        # Convert keyval to character
        input_char = chr(keyval)

        # Update pressed key set (non-modifier keys only)
        # This tracks which main keys are currently held, used for combo-key detection.
        # Modifiers are tracked separately in _modkey_status.
        if is_pressed:
            self._pressed_key_set.add(input_char)
        else:
            self._pressed_key_set.discard(input_char)

        # Get output from simultaneous processor
        output, pending = self._simul_processor.get_layout_output(
            self._preedit_string, input_char, is_pressed
        )

        logger.debug(f'Processor result: output="{output}", pending="{pending}"')

        # Commit output if any
        if output:
            self._commit_string(output)

        # Update preedit with pending (or clear if None)
        self._preedit_string = pending if pending else ''
        self._update_preedit()

        return True

    # =========================================================================
    # MODIFIER KEY STATUS TRACKING
    # =========================================================================

    def _update_modkey_status(self, keyval, is_pressed):
        """
        Update self._modkey_status based on modifier key press/release.

        This tracks which modifier keys are currently held down using
        bitwise flags (STATUS_SPACE, STATUS_SHIFT_L, etc.).

        Args:
            keyval: The key value
            is_pressed: True if key press, False if key release
        """
        # Map IBus keyvals to our STATUS_* constants
        keyval_to_status = {
            IBus.KEY_space: STATUS_SPACE,
            IBus.KEY_Shift_L: STATUS_SHIFT_L,
            IBus.KEY_Shift_R: STATUS_SHIFT_R,
            IBus.KEY_Control_L: STATUS_CONTROL_L,
            IBus.KEY_Control_R: STATUS_CONTROL_R,
            IBus.KEY_Alt_L: STATUS_ALT_L,
            IBus.KEY_Alt_R: STATUS_ALT_R,
            IBus.KEY_Super_L: STATUS_SUPER_L,
            IBus.KEY_Super_R: STATUS_SUPER_R,
        }

        status_bit = keyval_to_status.get(keyval)
        if status_bit is None:
            return  # Not a tracked modifier key

        if is_pressed:
            # Set the bit (key is now held)
            self._modkey_status |= status_bit
        else:
            # Clear the bit (key is released)
            self._modkey_status &= ~status_bit

        logger.debug(f'_update_modkey_status: keyval={keyval}, is_pressed={is_pressed}, '
                     f'status=0x{self._modkey_status:03x}')

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _commit_string(self, text):
        """Commit text to the application"""
        if text:
            logger.debug(f'Committing: "{text}"')
            self.commit_text(IBus.Text.new_from_string(text))

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

