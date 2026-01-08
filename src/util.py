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
    try:
        # Try to import the auto-generated paths from installation
        from . import paths
        return paths.INSTALL_ROOT
    except ImportError:
        # Fallback for development environment
        return '/opt/ibus-pskk'


def get_default_config_path():
    '''
    Return the path to the default config file in the system installation.
    This is the config.json that gets copied to user's home on first run.
    '''
    return os.path.join(get_datadir(), 'config.json')


def get_user_datadir():
    '''
    Return the path to the data directory under /home/kira.
    Typically, it would be $HOME/.local/share/pskk
    '''
    return os.path.join(GLib.get_user_data_dir(), 'ibus-pskk')


def get_libexecdir():
    return '/usr/local/libexec'


def get_localedir():
    return '/usr/local/share/locale'


def get_user_configdir():
    '''
    Return the path to the config directory under $HOME.
    Typically, it would be $HOME/.config/ibus-pskk
    '''
    return os.path.join(GLib.get_user_config_dir(), get_package_name())


def get_homedir():
    '''
    Return the path to the $HOME directory.
    '''
    return GLib.get_home_dir()


def get_user_configdir_relative_to_home():
    return get_user_configdir().replace(get_homedir(), '$' + '{HOME}')


def get_config_data():
    '''
    This function is to load the config JSON file from the HOME/.config/ibus-pskk
    When the file is not present (e.g., after initial installation), it will copy
    the deafult config.json from the central location.

    Returns:
        tuple: (config_data, warnings_string) where warnings_string is empty if no warnings
    '''
    configfile_path = os.path.join(get_user_configdir(), 'config.json')
    default_config_path = get_default_config_path()
    default_config = json.load(codecs.open(default_config_path))
    warnings = ""

    if(not os.path.exists(configfile_path)):
        warning_msg = f'config.json is not found under {get_user_configdir()} . Copying the default config.json from {default_config_path} ..'
        logger.warning(warning_msg)
        warnings = warning_msg
        with open(configfile_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False)
        return(default_config, warnings)
    try:
        config_data = json.load(codecs.open(configfile_path))
    except json.decoder.JSONDecodeError as e:
        logger.error(f'Error loading the config.json under {get_user_configdir()}')
        logger.error(e)
        logger.error(f'Using (but not copying) the default config.json from {default_config_path} ..')
        return get_default_config_data(), warnings

    for k in default_config:
        if k not in config_data:
            warning_msg = f'The key "{k}" was not found in the config.json under {get_user_configdir()} . Copying the default key-value'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            config_data[k] = default_config[k]
        if type(config_data[k]) != type(default_config[k]):
            warning_msg = f'Type mismatch found for the key "{k}" between config.json under {get_user_configdir()} and default config.json. Replacing the value of this key with the value in default config.json'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            config_data[k] = default_config[k]
    return config_data, warnings


def save_config_data(config_data):
    '''
    Save config data to the user config directory.

    Args:
        config_data: Dictionary containing configuration data to save

    Returns:
        bool: True if save was successful, False otherwise
    '''
    configfile_path = os.path.join(get_user_configdir(), 'config.json')

    try:
        # Ensure the config directory exists
        os.makedirs(get_user_configdir(), exist_ok=True)

        # Write the config file with proper formatting
        with open(configfile_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        logger.info(f'Configuration saved successfully to {configfile_path}')
        return True
    except Exception as e:
        logger.error(f'Error saving config.json to {configfile_path}')
        logger.error(e)
        return False


def get_default_config_data():
    default_config_path = get_default_config_path()
    if not os.path.exists(default_config_path):
        logger.error(f'config.json is not found under {get_default_config_path()}. Please check that installation was done without problem!')
        return None
    default_config = json.load(codecs.open(default_config_path))
    return default_config


def get_layout(config):
    layout_file_name = config['layout']
    layout_file_path = ''
    if os.path.exists(os.path.join(get_user_configdir(), 'layouts', layout_file_name)):
        layout_file_path = os.path.join(get_user_configdir(), 'layouts', layout_file_name)
    elif os.path.exists(os.path.join(get_datadir(), 'layouts', layout_file_name)):
        layout_file_path = os.path.join(get_datadir(), 'layouts', layout_file_name)
    else:
        layout_file_path = os.path.join(get_datadir(), 'layouts', 'shingeta.json')
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
