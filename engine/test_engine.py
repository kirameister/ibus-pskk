import unittest
from unittest.mock import patch, MagicMock
from unittest.mock import call
import engine
from unittest import TestCase
from gi.repository import IBus

import gi
gi.require_version("IBus", "1.0")
from gi.repository import IBus


import logging
logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

RELEASE_ACTION = IBus.ModifierType.RELEASE_MASK
PRESS_ACTION   = 0

# Defined set of constants
STATUS_SPACE        = 0x01
STATUS_SHIFT_L      = 0x02 # this value is currently not meant to be used directly
STATUS_SHIFT_R      = 0x04 # this value is currently not meant to be used directly
STATUS_CONTROL_L    = 0x08
STATUS_CONTROL_R    = 0x10
STATUS_ALT_L        = 0x20
STATUS_ALT_R        = 0x40
STATUS_SHIFTS       = STATUS_SHIFT_L | STATUS_SHIFT_R
STATUS_CONTROLS     = STATUS_CONTROL_L | STATUS_CONTROL_R
STATUS_MODIFIER     = STATUS_SHIFTS  | STATUS_CONTROLS | STATUS_ALT_L | STATUS_ALT_R | STATUS_SPACE

MODE_FORCED_PREEDIT_POSSIBLE                   = 0x001
MODE_IN_FORCED_PREEDIT                         = 0x002
MODE_IN_PREEDIT                                = 0x004
MODE_IN_KANCHOKU                               = 0x008
MODE_JUST_FINISHED_KANCHOKU                    = 0x010
MODE_IN_CONVERSION                             = 0x020
MODE_IN_FORCED_CONVERSION                      = 0x040
SWITCH_FIRST_SHIFT_PRESSED_IN_PREEDIT          = 0x080


class TestSimplestStrokes(unittest.TestCase):
    def _init_for_null(self):
        self.eq._modkey_status = 0
        self.eq._typing_mode = 0
        return()

    def setUp(self):
        '''Let the _commit_string() and _update_preedit() functions do nothing'''
        # Initialize the object under test after mocking
        self.eq = engine.EnginePSKK()
        # Mock _commit_string and _update_preedit to avoid real execution
        self.eq._commit_string = MagicMock(return_value=None)
        self.eq._update_preedit = MagicMock(return_value=None)
        self.eq.commit_text = MagicMock(return_value=None)
        return(None)

    def tearDown(self):
        '''Nothing to be done by this function'''
        #self.patcher.stop()
        pass
        return(None)

    def test_S0_1(self):
        ''' +a => "" / "の" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.a, PRESS_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'の')
        self.assertEqual(self.eq._modkey_status, 0)
        self.assertEqual(self.eq._typing_mode, 0)
        self.eq._update_preedit.assert_called() # Fails if never called
        self.eq._commit_string.assert_called()

    def test_S0_2(self):
        ''' +a -a => "" / "の" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.a, PRESS_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.a, RELEASE_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'の')
        self.assertEqual(self.eq._modkey_status, 0)
        self.assertEqual(self.eq._typing_mode, 0)
        self.eq._update_preedit.assert_called()
        self.eq._commit_string.assert_called()

    def test_S0_3(self):
        ''' +space -space => "" / "space" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.space, PRESS_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.space, RELEASE_ACTION), True)
        self.assertEqual(self.eq._preedit_string, '')
        self.assertEqual(self.eq._modkey_status, 0)
        self.assertEqual(self.eq._typing_mode, SWITCH_FIRST_SHIFT_PRESSED_IN_PREEDIT)
        self.eq.commit_text.assert_called()
        self.eq._update_preedit.assert_not_called()
        self.eq._commit_string.assert_not_called()
        #assert self.eq.commit_text.call_args_list == [call(IBus.Text.new_from_string(' '))]

    def test_S0_4(self):
        ''' +a +k -a -k => "ほ" / "" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.a, PRESS_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'の')
        self.assertEqual(self.eq.process_key_event(IBus.k, PRESS_ACTION), True)
        self.assertEqual(self.eq._preedit_string, '')
        self.assertEqual(self.eq.process_key_event(IBus.a, RELEASE_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.k, RELEASE_ACTION), True)
        self.assertEqual(self.eq._preedit_string, '')
        self.assertEqual(self.eq._modkey_status, 0)
        self.assertEqual(self.eq._typing_mode, 0)
        self.eq._update_preedit.assert_called()
        self.eq._commit_string.assert_called()
        self.eq.commit_text.assert_not_called()
        assert self.eq._commit_string.call_args_list == [call(''), call('ほ')]

    def test_S0_5(self):
        ''' +z +d +l -z -d -l => "→" / "" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.z, PRESS_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'す')
        self.assertEqual(self.eq.process_key_event(IBus.d, PRESS_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'すか')
        self.assertEqual(self.eq.process_key_event(IBus.l, PRESS_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.z, RELEASE_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.d, RELEASE_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.l, RELEASE_ACTION), True)
        self.assertEqual(self.eq._preedit_string, '')
        self.assertEqual(self.eq._modkey_status, 0)
        self.assertEqual(self.eq._typing_mode, 0)
        self.eq._update_preedit.assert_called()
        self.eq._commit_string.assert_called()
        self.eq.commit_text.assert_not_called()
        assert self.eq._commit_string.call_args_list == [call(''), call(''), call('→')]

    def test_S0_6(self):
        ''' +z +d -z -d +l -l  => "すか" / "し" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.z, PRESS_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'す')
        self.assertEqual(self.eq.process_key_event(IBus.d, PRESS_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'すか')
        self.assertEqual(self.eq.process_key_event(IBus.z, RELEASE_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.d, RELEASE_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.l, PRESS_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.l, RELEASE_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'し')
        self.assertEqual(self.eq._modkey_status, 0)
        self.assertEqual(self.eq._typing_mode, 0)
        assert self.eq._commit_string.call_args_list == [call(''), call(''), call('すか')] # "すか" is pushed out to committed as /l/ is given.

    def test_S0_7(self):
        ''' +return -return => "NEW_LINE" / "" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.Return, PRESS_ACTION), False)
        self.assertEqual(self.eq.process_key_event(IBus.Return, RELEASE_ACTION), False)
        self.assertEqual(self.eq._preedit_string, '')
        self.assertEqual(self.eq._modkey_status, 0)
        self.assertEqual(self.eq._typing_mode, 0)
        assert self.eq._commit_string.call_args_list == [call('')]

    def test_S0_8(self):
        ''' +a === +k -a -k => "の" / "い" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.a, PRESS_ACTION), True)
        self.eq._previous_typed_timestamp -= 1000 * self.eq._max_simul_limit_ms # this is to ensure simul-check to always fail
        self.assertEqual(self.eq.process_key_event(IBus.k, PRESS_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.a, RELEASE_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.k, RELEASE_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'い') # preedit value is still there..
        assert self.eq._commit_string.call_args_list == [call(''),call('の')] # commit confirmed at the 2nd stroke

    def test_S0toS1_1(self):
        ''' +space => "" / "" (漢直モード) '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.space, PRESS_ACTION), True)
        self.assertEqual(self.eq._preedit_string, '')
        self.assertEqual(self.eq._modkey_status, STATUS_SPACE)
        self.assertEqual(self.eq._typing_mode, MODE_IN_PREEDIT | SWITCH_FIRST_SHIFT_PRESSED_IN_PREEDIT)
        self.eq.commit_text.assert_not_called()
        self.eq._update_preedit.assert_not_called()
        self.eq._commit_string.assert_not_called()

    def test_S1_0(self):
        ''' +space +a -space -a +s -s => "のと" / "" '''
        self._init_for_null()
        self.assertEqual(self.eq.process_key_event(IBus.space, PRESS_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.a, PRESS_ACTION), True)
        self.assertEqual(self.eq._typing_mode, MODE_IN_PREEDIT | SWITCH_FIRST_SHIFT_PRESSED_IN_PREEDIT)
        self.assertEqual(self.eq.process_key_event(IBus.space, RELEASE_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.a, RELEASE_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.s, PRESS_ACTION), True)
        self.assertEqual(self.eq.process_key_event(IBus.s, RELEASE_ACTION), True)
        self.assertEqual(self.eq._preedit_string, 'のと')
        self.assertEqual(self.eq._typing_mode, MODE_IN_PREEDIT)
        self.eq._commit_string.assert_not_called()



if(__name__ == '__main__'):
    unittest.main()
