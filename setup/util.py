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

import os
import gi
from gi.repository import GLib
# https://lazka.github.io/pgi-docs/GLib-2.0/functions.html

version = '0.01'


def get_package_name() -> str:
    '''
    returns 'ibus-pskk'
    '''
    return '@PACKAGE_NAME@'


def get_version():
    return version


def get_user_datadir() -> str:
    '''
    Return the path to the data directory under $HOME.
    Typically, it would be $HOME/.local/share/pskk

    http://lazka.github.io/pgi-docs/GLib-2.0/functions.html#GLib.get_user_data_dir
    '''
    return os.path.join(GLib.get_user_data_dir(), get_package_name())


def get_homedir() -> str:
    '''
    Return the path to the $HOME directory.

    http://lazka.github.io/pgi-docs/GLib-2.0/functions.html#GLib.get_home_dir
    '''
    return GLib.get_home_dir()


def get_user_configdir() -> str:
    '''
    Return the path to the config directory under $HOME.
    Typically, it would be $HOME/.config/pskk

    http://lazka.github.io/pgi-docs/GLib-2.0/functions.html#GLib.get_user_config_dir
    '''
    return os.path.join(GLib.get_user_config_dir(), get_package_name())


def get_user_configdir_relative_to_home():
    return get_user_configdir().replace(get_homedir(), '${HOME}')


def get_localedir():
    return '${localedir}'
