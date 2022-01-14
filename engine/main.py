# ibus-pskk - PSKK for IBus
#
# Using source code derived from
#   ibus-tmpl - The Input Bus template project
#
# Copyright (c) 2017-2021 Esrille Inc. (ibus-hiragana)
# Modifications Copyright (C) 2022 Akira K.
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
import getopt
import gettext
import os
import locale
import logging
import sys
from shutil import copyfile

import gi
gi.require_version('IBus', '1.0')
from gi.repository import GLib, GObject, IBus

_ = lambda a : gettext.dgettext(util.get_name(), a)


class IMApp:
    def __init__(self, exec_by_ibus):
        self._mainloop = GLib.MainLoop()
        self._bus = IBus.Bus()
        self._bus.connect("disconnected", self._bus_disconnected_cb)
        self._factory = IBus.Factory(self._bus)
        self._factory.add_engine("pskk", GObject.type_from_name("EnginePSKK"))
        if exec_by_ibus:
            self._bus.request_name("org.freedesktop.IBus.PSKK", 0)
        else:
            self._component = IBus.Component(
                name="org.freedesktop.IBus.PSKK",
                description="PSKK",
                version=util.get_version(),
                license="Apache",
                author="Akira K.",
                homepage="https://github.com/kirameister/" + util.get_name(),
                textdomain=util.get_name())
            engine = IBus.EngineDesc(
                name="pskk",
                longname="PSKK",
                description="PSKK",
                language="ja",
                license="Apache",
                author="Akira K.",
                icon=util.get_name(),
                layout="default")
            self._component.add_engine(engine)
            self._bus.register_component(self._component)
            self._bus.set_global_engine_async("pskk", -1, None, None, None)

    def run(self):
        self._mainloop.run()

    def _bus_disconnected_cb(self, bus):
        self._mainloop.quit()


def print_help(v=0):
    print("-i, --ibus             executed by IBus.")
    print("-h, --help             show this message.")
    print("-d, --daemonize        daemonize ibus")
    sys.exit(v)


def main():
    os.umask(0o077)

    # Create user specific data directory
    user_configdir = util.get_user_configdir()
    os.makedirs(user_configdir, 0o700, True)
    os.chmod(user_configdir, 0o700)   # For logfile created by v0.2.0 or earlier

    # check the config file and copy it from installed directory if it does not exist
    configfile_name = os.path.join(user_configdir, 'config.json')
    if not os.path.exists(configfile_name):
        copyfile(os.path.join(util.get_datadir(), 'config.json'), configfile_name)

    # logging settings
    logfile_name = os.path.join(user_configdir, util.get_name() + '.log')
    logging.basicConfig(filename = logfile_name, filemode='w', level=logging.DEBUG)

    exec_by_ibus = False
    daemonize = False

    shortopt = "ihd"
    longopt = ["ibus", "help", "daemonize"]

    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopt, longopt)
    except getopt.GetoptError as err:
        print_help(1)

    for o, a in opts:
        if o in ("-h", "--help"):
            print_help(0)
        elif o in ("-d", "--daemonize"):
            daemonize = True
        elif o in ("-i", "--ibus"):
            exec_by_ibus = True
        else:
            sys.stderr.write("Unknown argument: %s\n" % o)
            print_help(1)

    if daemonize:
        if os.fork():
            sys.exit()
    IMApp(exec_by_ibus).run()


if __name__ == "__main__":
    try:
        locale.bindtextdomain(util.get_name(), util.get_localedir())
    except Exception:
        pass
    gettext.bindtextdomain(util.get_name(), util.get_localedir())
    main()
