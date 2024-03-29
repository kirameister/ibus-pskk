# ibus-pskk - PSKK for IBus
#
# Copyright (c) 2020, 2021 Esrille Inc.
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

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
gi.require_version('IBus', '1.0')
from gi.repository import IBus

import gettext
import locale
import os
import sys

_ = lambda a : gettext.dgettext(util.get_package_name(), a)


class SetupEnginePSKK:
    def __init__(self):
        self._settings = Gio.Settings.new('org.freedesktop.ibus.engine.pskk')
        self._settings.connect('changed', self.on_value_changed)
        self._builder = Gtk.Builder()
        self._builder.set_translation_domain(util.get_package_name())
        self._builder.add_from_file(os.path.join(os.path.dirname(__file__), 'setup.glade'))
        self._builder.connect_signals(self)
        self._init_keyboard_layout()
        self._init_keyboard_type()
        self._init_dictionary()
        self._set_current_keyboard(self._settings.get_string('layout'))
        self._window = self._builder.get_object('SetupDialog')
        self._window.set_default_icon_name('ibus-setup-pskk')
        self._window.show()

    def _init_keyboard_layout(self):
        self._keyboard_layouts = self._builder.get_object('KeyboardLayout')
        model = Gtk.ListStore(str, str, int)
        model.append([_('Rōmaji'), 'roomazi', 0])
        model.append([_('Kana (JIS Layout)'), 'jis', 1])
        model.append([_('Kana (New Stickney Layout)'), 'new_stickney', 2])
        self._keyboard_layouts.set_model(model)
        renderer = Gtk.CellRendererText()
        self._keyboard_layouts.pack_start(renderer, True)
        self._keyboard_layouts.add_attribute(renderer, 'text', 0)

    def _init_keyboard_type(self):
        self._keyboard_types = self._builder.get_object('KeyboardType')
        model = Gtk.ListStore(str, str, int)
        model.append([_('Japanese Keyboard'), '.109', 0])
        model.append([_('US Keyboard'), '', 1])
        self._keyboard_types.set_model(model)
        renderer = Gtk.CellRendererText()
        self._keyboard_types.pack_start(renderer, True)
        self._keyboard_types.add_attribute(renderer, 'text', 0)

    def _set_current_keyboard(self, layout: str):
        layout = os.path.basename(layout)
        # types
        if layout.endswith('.109.json'):
            type = '.109'
        else:
            type = ''
        model = self._keyboard_types.get_model()
        for i in model:
            if i[1] == type:
                self._keyboard_types.set_active(i[2])
                break
        # layouts
        pos = layout.find('.')
        if pos == -1:
            layout = 'roomazi'
        else:
            layout = layout[:pos]
        model = self._keyboard_layouts.get_model()
        for i in model:
            if i[1] == layout:
                self._keyboard_layouts.set_active(i[2])
                break

    def _init_dictionary(self):
        self._kanzi_dictionaries = self._builder.get_object('KanjiDictionary')
        model = Gtk.ListStore(str, str, int)
        model.append([_('1st grade'), 'restrained.1.dic', 0])
        model.append([_('2nd grade'), 'restrained.2.dic', 1])
        model.append([_('3rd grade'), 'restrained.3.dic', 2])
        model.append([_('4th grade'), 'restrained.4.dic', 3])
        model.append([_('5th grade'), 'restrained.5.dic', 4])
        model.append([_('6th grade'), 'restrained.6.dic', 5])
        model.append([_('7-9th grade'), 'restrained.7.dic', 6])
        model.append([_('10th+ grade (Okurigana: general)'), 'restrained.dic', 7])
        model.append([_('10th+ grade (Okurigana: general + permissible)'), 'restrained.9.dic', 8])
        self._kanzi_dictionaries.set_model(model)
        renderer = Gtk.CellRendererText()
        self._kanzi_dictionaries.pack_start(renderer, True)
        self._kanzi_dictionaries.add_attribute(renderer, 'text', 0)
        self._kanzi_dictionaries.set_active(7)
        current = self._settings.get_string('dictionary')
        current = os.path.basename(current)
        for i in model:
            if i[1] == current:
                self._kanzi_dictionaries.set_active(i[2])
                break

        self._user_dictionary = self._builder.get_object('UserDictionary')
        current = self._settings.get_string('user-dictionary')
        self._user_dictionary.set_text(current)
        self._default_user_dictionary = self._settings.get_default_value('user-dictionary').get_string()

        self._reload_dictionaries = self._builder.get_object('ReloadDictionaries')
        self._clear_input_history = self._builder.get_object('ClearInputHistory')

    def run(self):
        Gtk.main()

    def apply(self):
        # layout
        model = self._keyboard_layouts.get_model()
        i = self._keyboard_layouts.get_active()
        layout = model[i][1]
        if layout == 'jis':
            layout += '.109'
        else:
            model = self._keyboard_types.get_model()
            i = self._keyboard_types.get_active()
            layout += model[i][1]
        layout = os.path.join(util.get_datadir(), 'layouts/' + layout + '.json')
        self._settings.set_string('layout', layout)

        # dictionary
        model = self._kanzi_dictionaries.get_model()
        i = self._kanzi_dictionaries.get_active()
        dictionary = os.path.join(util.get_datadir(), model[i][1])
        self._settings.set_string('dictionary', dictionary)

        # user-dictionary
        user = self._user_dictionary.get_text().strip()
        if user == self._default_user_dictionary:
            self._settings.reset('user-dictionary')
        else:
            self._settings.set_string('user-dictionary', user)

        if self._clear_input_history.get_active():
            # clear_input_history also reloads dictionaries
            print('clear_input_history', flush=True)
        elif self._reload_dictionaries.get_active():
            print('reload_dictionaries', flush=True)

    def on_value_changed(self, settings, key):
        value = settings.get_value(key)
        if key == 'layout':
            self._set_current_keyboard(value.get_string())
        elif key == 'dictionary':
            current = value.get_string()
            current = os.path.basename(current)
            model = self._kanzi_dictionaries.get_model()
            for i in model:
                if i[1] == current:
                    self._kanzi_dictionaries.set_active(i[2])
                    break
        elif key == 'user-dictionary':
            current = value.get_string()
            self._user_dictionary.set_text(current)

    #
    # Glade signal handlers. The signal names are declared in Glade
    #
    def on_apply(self, *args):
        self.apply()

    def on_cancel(self, *args):
        self._window.destroy()

    def on_ok(self, *args):
        self.apply()
        self._window.destroy()

    def on_edit(self, *args):
        path = self._user_dictionary.get_text().strip()
        path = os.path.join(util.get_user_datadir(), path)
        with open(path, 'a+') as f:
            pass
        try:
            Gtk.show_uri_on_window(None, 'file://' + path, Gdk.CURRENT_TIME)
        except Exception:
            pass

    def on_destroy(self, *args):
        Gtk.main_quit()


def main():
    setup = SetupEnginePSKK()
    setup.run()


if __name__ == '__main__':
    try:
        locale.bindtextdomain(util.get_package_name(), util.get_localedir())
    except Exception:
        pass
    gettext.bindtextdomain(util.get_package_name(), util.get_localedir())
    main()
