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

from engine import EnginePSKK
import util

import argparse
import gettext
import os
import locale
import logging
import sys
from shutil import copyfile

import gi
gi.require_version('IBus', '1.0')
from gi.repository import GLib, GObject, IBus

_ = lambda a : gettext.dgettext(package.get_name(), a)


class IMApp:
    def __init__(self, exec_by_ibus):
        self._mainloop = GLib.MainLoop()
        self._bus = IBus.Bus()
        self._bus.connect("disconnected", self._bus_disconnected_cb)
        self._factory = IBus.Factory(self._bus)
        self._factory.add_engine("pskk", GObject.type_from_name("EnginePSKK"))
        if exec_by_ibus:
            self._bus.request_name("org.freedesktop.ibus.pskk", 0)
        else:
            self._component = IBus.Component(
                    name="org.freedesktop.ibus.pskk",
                    description='PSKK',
                    version=util.get_version(),
                    license='Apache',
                    author='Akira K. (kirameister)',
                    homepage='https://github.com/kirameister/ibus-pskk',
                    textdomain=util.get_package_name())
            engine = IBus.EngineDesc(
                    name='pskk',
                    longname='Personaliz(ed|able) SKK',
                    description="PSKK",
                    language='ja',
                    license='Apache',
                    author='Akira K. (kirameister)',
                    icon=util.get_package_name(),
                    layout='default')
            self._component.add_engine(engine)
            self._bus.register_component(self._component)
            self._bus.set_global_engine_async("pskk", -1, None, None, None)

    def run(self):
        self._mainloop.run()

    def _bus_disconnected_cb(self, bus):
        self._mainloop.quit()


def main():
    os.umask(0o077)

    # check the config directory and create it if it does not exist
    user_configdir = util.get_user_configdir()
    os.makedirs(user_configdir, 0o700, True)
    os.chmod(user_configdir, 0o700) 

    # check the config file and copy it from installed directory if it does not exist
    configfile_name = os.path.join(user_configdir, 'config.json')
    if not os.path.exists(configfile_name):
        copyfile(os.path.join(util.get_engine_pkgdir(), 'config.json'), configfile_name)

    # logging settings
    logfile_name = os.path.join(user_configdir, util.get_package_name() + '.log')
    logging.basicConfig(filename = logfile_name, filemode='w', level=logging.DEBUG)

    parser = argparse.ArgumentParser(description="Personaliz(ed|able) SKK")
    parser.add_argument('--daemonize', action='store_true')
    parser.add_argument('--ibus', action='store_true')
    args = parser.parse_args()

    if args.daemonize:
        if os.fork():
            sys.exit()
    IMApp(args.ibus).run()



if __name__ == "__main__":
    main()

