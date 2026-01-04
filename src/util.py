# ibus-pskk - PSKK for IBus
#
# Copyright (c) 2020 Esrille Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This file is a template file processed by the configure script.
# The file name is listed in AC_CONFIG_FILES of configure.ac.

import codecs
import json
import os
from gi.repository import GLib
import logging

logger = logging.getLogger(__name__)


def get_package_name():
    '''
    returns 'ibus-pskk'
    '''
    return 'ibus-pskk'


def get_version():
    return '0.0.1'


def get_prefix():
    '''
    It is usually /usr/local/
    '''
    return '/usr/local'


def get_datadir():
    '''
    Return the path to the data directory under user-independent (central)
    location (= not under the HOME)
    '''
    return '/usr/local/share/ibus-pskk'


def get_user_datadir():
    '''
    Return the path to the data directory under /home/kira.
    Typically, it would be /home/kira/.local/share/pskk
    '''
    return os.path.join(GLib.get_user_data_dir(), 'ibus-pskk')


def get_libexecdir():
    return '/usr/local/libexec'


def get_localedir():
    return '/usr/local/share/locale'


def get_user_configdir():
    '''
    Return the path to the config directory under /home/kira.
    Typically, it would be /home/kira/.config/ibus-pskk
    '''
    return os.path.join(GLib.get_user_config_dir(), get_package_name())


def get_homedir():
    '''
    Return the path to the /home/kira directory.
    '''
    return GLib.get_home_dir()


def get_user_configdir_relative_to_home():
    return get_user_configdir().replace(get_homedir(), '$' + '{HOME}')


def get_config_data():
    '''
    This function is to load the config JSON file from the HOME/.config/ibus-pskk
    When the file is not present (e.g., after initial installation), it will copy 
    the deafult config.json from the central location. 
    '''
    configfile_path = os.path.join(get_user_configdir(), 'config.json')
    if(not os.path.exists(configfile_path)):
        logger.warning(f'config.json is not found under {get_user_configdir()} . Copying the default config.json from {get_datadir()} ..')
        default_config = json.load(codecs.open(os.path.join(get_datadir(), 'config.json')))
        with open(configfile_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False)
        return(default_config)
    try:
        return(json.load(codecs.open(configfile_path)))
    except json.decoder.JSONDecodeError as e:
        logger.error(f'Error loading the config.json under {get_user_configdir()}')
        logger.error(e)
        logger.error(f'Using (but not copying) the default config.json from {get_datadir()} ..')
        default_config = json.load(codecs.open(os.path.join(get_datadir(), 'config.json')))
        # not writing the config.json under HOME, in order to let the user inspect. 
        return(default_config)
    return None


def get_layout(config):
    layout_file_name = config['layout']
    layout_file_path = ''
    if os.path.exists(os.path.join(get_user_configdir(), layout_file_name)):
        layout_file_path = os.path.join(get_user_configdir(), layout_file_name)
    elif os.path.exists(os.path.join(get_datadir(), 'layouts', layout_file_name)):
        layout_file_path = os.path.join(get_datadir(), 'layouts', layout_file_name)
    else:
        layout_file_path = os.path.join(get_datadir(), 'layouts', 'roman.json')
    try:
        with open(layout_file_path) as layout_json:
            return json.load(layout_json)
    except: 
        logger.error(f'Error in loading layout file: {layout_file_path}')
    return None


def get_kanchoku_layout(config):
    kanchoku_layout_file_name = config['kanchoku_layout']
    kanchoku_layout_file_path = ''
    if os.path.exists(os.path.join(get_user_configdir(), kanchoku_layout_file_name)):
        kanchoku_layout_file_path = os.path.join(get_user_configdir(), kanchoku_layout_file_name)
    elif os.path.exists(os.path.join(get_datadir(), 'kanchoku_layouts', kanchoku_layout_file_name)):
        kanchoku_layout_file_path = os.path.join(get_datadir(), 'kanchoku_layouts', kanchoku_layout_file_name)
    else:
        kanchoku_layout_file_path = os.path.join(get_datadir(), 'kanchoku_layouts', 'aki_code.json')
    try:
        with open(kanchoku_layout_file_path) as kanchoku_layout_json:
            return json.load(kanchoku_layout_json)
    except: 
        logger.error(f'Error in loading kanchoku_layout file: {kanchoku_layout_file_path}')
    return None
