import unittest
import engine
from unittest import TestCase
from gi.repository import IBus

import logging
logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

RELEASE_ACTION = IBus.ModifierType.RELEASE_MASK
PRESS_ACTION   = 0

""" Defined set of constants
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
"""

class Test_simplest_strokes(unittest.TestCase):
    """
    """
    def setUp(self):
        self.eq = engine.EnginePSKK()

    def test_process_key_event_1(self):
        exp_return_val = True
        exp_preedit = ''
        self.eq._modkey_status = 0
        self.eq._typing_mode = 0
        actual_return_val = self.eq.process_key_event(IBus.a, PRESS_ACTION)
        actual_return_val = self.eq.process_key_event(IBus.a, RELEASE_ACTION)
        actual_return_val = self.eq.process_key_event(IBus.k, PRESS_ACTION)
        actual_return_val = self.eq.process_key_event(IBus.k, RELEASE_ACTION)
        print(f'actual_return_val: {actual_return_val}')
        self.assertEqual(exp_return_val, actual_return_val)
        self.assertEqual(exp_preedit, self.eq._preedit_string)
        self.tn


if(__name__ == '__main__'):
    unittest.main()
