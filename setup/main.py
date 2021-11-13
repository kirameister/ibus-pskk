# ibus-pskk
#
# Copyright (c) 2020, 2021 Esrille Inc. (ibus-hiragana)
# Modifications Copyright (C) 2021 Akira K.
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

import util

import gi
from gi.repository import Gio
from gi.repository import GLib

GLib.set_prgname('ibus-setup-pskk')

gi.require_version("Gtk", '3.0')
from gi.repository import Gtk
from gi.repository import Gdk
gi.require_version("IBus", '1.0')
from gi.repository import IBus

import gettext
import locale
import os
import re
import sys



class SetupEnginePSKK:
    def __init__(self):
        #self._settings = Gio.Settings.new('org.freedesktop.ibus.engine.pskk')
        self._builder = Gtk.Builder()
        self._builder.set_translation_domain(util.get_package_name())
        self._builder.add_from_file(os.path.join(os.path.dirname(__file__), 'setup.glade'))
        self._builder.connect_signals(self)
        self._window = self._builder.get_object('SetupDialog')
        self._window.set_default_icon_name('ibus-setup-pskk')

        self._label3 = self._builder.get_object('label3')
        self._label3.set_text(util.get_user_configdir_relative_to_home())
        self._window.show()
        print(util.get_user_configdir_relative_to_home())


    def run(self):
        Gtk.main()

    def on_OK_clicked(self, *args):
        self.on_destroy()

    def on_destroy(self, *args):
        Gtk.main_quit()



def main():
    setup = SetupEnginePSKK()
    setup.run()

if __name__ == '__main__':
    main()



