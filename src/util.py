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

    # Deep validation for nested structures like "dictionaries"
    if "dictionaries" in config_data and isinstance(config_data["dictionaries"], dict):
        dictionaries = config_data["dictionaries"]
        default_dictionaries = default_config.get("dictionaries", {"system": [], "user": []})
        needs_fix = False

        # Ensure "system" key exists and is a list
        if "system" not in dictionaries:
            needs_fix = True
        elif not isinstance(dictionaries["system"], list):
            warning_msg = f'The "dictionaries.system" key has invalid type (expected list). Resetting to default.'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            dictionaries["system"] = default_dictionaries.get("system", [])

        # Ensure "user" key exists and is a list
        if "user" not in dictionaries:
            needs_fix = True
        elif not isinstance(dictionaries["user"], list):
            warning_msg = f'The "dictionaries.user" key has invalid type (expected list). Resetting to default.'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            dictionaries["user"] = default_dictionaries.get("user", [])

        if needs_fix:
            warning_msg = f'The "dictionaries" key is missing required sub-keys (system/user). Adding defaults.'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            if "system" not in dictionaries:
                dictionaries["system"] = default_dictionaries.get("system", [])
            if "user" not in dictionaries:
                dictionaries["user"] = default_dictionaries.get("user", [])

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


def get_layout_data(config):
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
    if os.path.exists(os.path.join(get_user_configdir(), 'kanchoku_layouts', kanchoku_layout_file_name)):
        kanchoku_layout_file_path = os.path.join(get_user_configdir(), 'kanchoku_layouts', kanchoku_layout_file_name)
    elif os.path.exists(os.path.join(get_user_configdir(), kanchoku_layout_file_name)):
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


def get_user_dictionaries_dir():
    """
    Return the path to the user dictionaries directory.
    Typically: $HOME/.config/ibus-pskk/dictionaries/
    """
    return os.path.join(get_user_configdir(), 'dictionaries')


def get_dictionary_files(config=None):
    """
    Obtain the list of JSON dictionary file paths to be used for kana-kanji conversion.

    The returned list contains:
    1. system_dictionary.json (generated from system SKK dictionaries)
    2. user_dictionary.json (generated from user SKK files in dictionaries/)

    Args:
        config: Configuration dictionary. If None, will be loaded via get_config_data().
                (Currently unused, kept for API compatibility)

    Returns:
        list: List of absolute paths to JSON dictionary files that exist.
              Returns empty list if no dictionaries are found.
    """
    dictionary_files = []
    config_dir = get_user_config_dir()

    # 1. Check for system_dictionary.json
    system_dict_path = os.path.join(config_dir, 'system_dictionary.json')
    if os.path.exists(system_dict_path):
        dictionary_files.append(system_dict_path)
        logger.debug(f'Found system dictionary: {system_dict_path}')
    else:
        logger.debug(f'System dictionary not found: {system_dict_path}')

    # 2. Check for user_dictionary.json
    user_dict_path = os.path.join(config_dir, 'user_dictionary.json')
    if os.path.exists(user_dict_path):
        dictionary_files.append(user_dict_path)
        logger.debug(f'Found user dictionary: {user_dict_path}')
    else:
        logger.debug(f'User dictionary not found: {user_dict_path}')

    logger.info(f'Dictionary files to use: {len(dictionary_files)} file(s)')
    return dictionary_files


def get_skk_dicts_dir():
    """
    Return the path to the system SKK dictionaries directory.
    Typically: /opt/ibus-pskk/dictionaries/skk_dict/
    """
    return os.path.join(get_datadir(), 'dictionaries', 'skk_dict')


def parse_skk_dictionary_line(line):
    """
    Parse a single line from an SKK dictionary file.

    SKK format: reading /candidate1/candidate2/.../
    Example: あやこ /亜矢子/彩子/

    Args:
        line: A single line from the SKK dictionary

    Returns:
        tuple: (reading, candidates_list) or (None, None) if line is invalid/comment
    """
    # Skip empty lines and comments
    line = line.strip()
    if not line or line.startswith(';'):
        return None, None

    # Split on first space to separate reading from candidates
    parts = line.split(' ', 1)
    if len(parts) != 2:
        return None, None

    reading = parts[0]
    candidates_part = parts[1]

    # Parse candidates: /candidate1/candidate2/.../
    # Remove leading and trailing slashes, then split
    candidates_part = candidates_part.strip('/')
    if not candidates_part:
        return None, None

    # Split by '/' and filter out empty strings
    # Also handle annotations in SKK format: candidate;annotation
    candidates = []
    for candidate in candidates_part.split('/'):
        if candidate:
            # Remove annotation if present (e.g., "候補;注釈" -> "候補")
            candidate_surface = candidate.split(';')[0]
            if candidate_surface:
                candidates.append(candidate_surface)

    if not candidates:
        return None, None

    return reading, candidates


def convert_skk_to_json(skk_file_path, json_file_path=None):
    """
    Convert an SKK dictionary file to JSON format.

    Args:
        skk_file_path: Path to the SKK dictionary file
        json_file_path: Path for the output JSON file.
                       If None, will be auto-generated in user dictionaries dir.

    Returns:
        tuple: (success: bool, output_path: str or None, entry_count: int)
    """
    if not os.path.exists(skk_file_path):
        logger.error(f'SKK dictionary file not found: {skk_file_path}')
        return False, None, 0

    # Determine output path
    if json_file_path is None:
        # Create output path in user dictionaries directory
        dict_dir = get_user_dictionaries_dir()
        os.makedirs(dict_dir, exist_ok=True)

        # Use same filename but with .json extension
        base_name = os.path.basename(skk_file_path)
        # Remove common SKK extensions if present
        for ext in ['.utf8', '.txt', '.dic', '.SKK']:
            if base_name.endswith(ext):
                base_name = base_name[:-len(ext)]
                break
        json_file_path = os.path.join(dict_dir, base_name + '.json')

    # Parse SKK dictionary
    dictionary = {}
    entry_count = 0

    # Try different encodings (SKK dictionaries are typically EUC-JP or UTF-8)
    encodings = ['utf-8', 'euc-jp', 'shift-jis']
    file_content = None

    for encoding in encodings:
        try:
            with open(skk_file_path, 'r', encoding=encoding) as f:
                file_content = f.readlines()
            logger.debug(f'Successfully read {skk_file_path} with encoding {encoding}')
            break
        except UnicodeDecodeError:
            continue

    if file_content is None:
        logger.error(f'Failed to read {skk_file_path} with any supported encoding')
        return False, None, 0

    # Process each line
    for line in file_content:
        reading, candidates = parse_skk_dictionary_line(line)
        if reading and candidates:
            if reading in dictionary:
                # Merge candidates, incrementing count for existing ones
                existing = dictionary[reading]
                for candidate in candidates:
                    if candidate in existing:
                        existing[candidate] += 1
                    else:
                        existing[candidate] = 1
            else:
                # Initialize each candidate with count of 1
                dictionary[reading] = {candidate: 1 for candidate in candidates}
            entry_count += 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

    # Write JSON file
    try:
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=2)
        logger.info(f'Converted SKK dictionary to JSON: {json_file_path} ({entry_count} entries)')
        return True, json_file_path, entry_count
    except Exception as e:
        logger.error(f'Failed to write JSON dictionary: {e}')
        return False, None, 0


def convert_all_skk_dictionaries():
    """
    Convert all SKK dictionaries from the system directory to JSON format
    in the user dictionaries directory.

    Returns:
        list: List of tuples (filename, success, entry_count) for each file processed
    """
    skk_dir = get_skk_dicts_dir()
    results = []

    if not os.path.exists(skk_dir):
        logger.warning(f'SKK dictionaries directory not found: {skk_dir}')
        return results

    # Process all files in the SKK dictionaries directory
    for filename in os.listdir(skk_dir):
        skk_path = os.path.join(skk_dir, filename)
        if os.path.isfile(skk_path):
            success, output_path, entry_count = convert_skk_to_json(skk_path)
            results.append((filename, success, entry_count))

    return results


def generate_system_dictionary(output_path=None, source_weights=None):
    """
    Generate a merged system dictionary from SKK dictionary files.

    Reads SKK dictionaries and merges them into a single JSON file.
    The count for each candidate is weighted by the source dictionary's weight.

    Args:
        output_path: Path for the output JSON file.
                    If None, defaults to ~/.config/ibus-pskk/system_dictionary.json
        source_weights: Dict mapping full file paths to integer weights.
                       If None, all files in skk_dicts directory are used with weight 1.

    Returns:
        tuple: (success: bool, output_path: str or None, stats: dict)
               stats contains 'files_processed', 'total_readings', 'total_candidates'
    """
    skk_dir = get_skk_dicts_dir()
    stats = {'files_processed': 0, 'total_readings': 0, 'total_candidates': 0}

    # Determine output path (system_dictionary.json goes in config dir, not dictionaries subdir)
    if output_path is None:
        config_dir = get_user_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        output_path = os.path.join(config_dir, 'system_dictionary.json')

    # If no weights specified, scan all files in skk_dicts with weight 1
    if source_weights is None:
        if not os.path.exists(skk_dir):
            logger.warning(f'SKK dictionaries directory not found: {skk_dir}')
            return False, None, stats
        source_weights = {}
        for filename in os.listdir(skk_dir):
            skk_path = os.path.join(skk_dir, filename)
            if os.path.isfile(skk_path):
                source_weights[skk_path] = 1

    if not source_weights:
        logger.warning('No dictionaries specified for conversion')
        return False, None, stats

    # Merged dictionary: {reading: {candidate: count}}
    merged_dictionary = {}

    # Process each SKK dictionary file
    for skk_path, weight in source_weights.items():
        if not os.path.isfile(skk_path):
            logger.warning(f'Dictionary file not found: {skk_path}')
            continue

        # Try different encodings
        encodings = ['utf-8', 'euc-jp', 'shift-jis']
        file_content = None

        for encoding in encodings:
            try:
                with open(skk_path, 'r', encoding=encoding) as f:
                    file_content = f.readlines()
                logger.debug(f'Successfully read {skk_path} with encoding {encoding}')
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            logger.warning(f'Failed to read {skk_path} with any supported encoding, skipping')
            continue

        # Track candidates seen in this file to avoid double-counting within same file
        seen_in_this_file = {}  # {reading: set(candidates)}

        # Process each line
        for line in file_content:
            reading, candidates = parse_skk_dictionary_line(line)
            if not reading or not candidates:
                continue

            # Initialize tracking for this reading if needed
            if reading not in seen_in_this_file:
                seen_in_this_file[reading] = set()

            # Initialize merged dictionary entry if needed
            if reading not in merged_dictionary:
                merged_dictionary[reading] = {}

            # Add candidates, incrementing by weight (only once per file)
            for candidate in candidates:
                if candidate not in seen_in_this_file[reading]:
                    seen_in_this_file[reading].add(candidate)
                    if candidate in merged_dictionary[reading]:
                        merged_dictionary[reading][candidate] += weight
                    else:
                        merged_dictionary[reading][candidate] = weight

        stats['files_processed'] += 1
        logger.debug(f'Processed {os.path.basename(skk_path)} with weight {weight}')

    # Calculate stats
    stats['total_readings'] = len(merged_dictionary)
    stats['total_candidates'] = sum(len(candidates) for candidates in merged_dictionary.values())

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged_dictionary, f, ensure_ascii=False, indent=2)
        logger.info(f'Generated system dictionary: {output_path}')
        logger.info(f'Stats: {stats["files_processed"]} files, {stats["total_readings"]} readings, {stats["total_candidates"]} candidates')
        return True, output_path, stats
    except Exception as e:
        logger.error(f'Failed to write system dictionary: {e}')
        return False, None, stats


def generate_user_dictionary(output_path=None, source_weights=None):
    """
    Generate a merged user dictionary from SKK-format files in the user dictionaries directory.

    Reads SKK-format text files from ~/.config/ibus-pskk/dictionaries/ and merges them
    into a single JSON file. The count for each candidate is weighted by the source file's weight.

    Args:
        output_path: Path for the output JSON file.
                    If None, defaults to ~/.config/ibus-pskk/user_dictionary.json
        source_weights: Dict mapping filenames to integer weights.
                       If None, all .txt files in dictionaries/ are used with weight 1.

    Returns:
        tuple: (success: bool, output_path: str or None, stats: dict)
               stats contains 'files_processed', 'total_readings', 'total_candidates'
    """
    user_dict_dir = get_user_dictionaries_dir()
    stats = {'files_processed': 0, 'total_readings': 0, 'total_candidates': 0}

    if not os.path.exists(user_dict_dir):
        logger.info(f'User dictionaries directory not found: {user_dict_dir}')
        # Create the directory for user convenience
        os.makedirs(user_dict_dir, exist_ok=True)
        logger.info(f'Created user dictionaries directory: {user_dict_dir}')
        return True, None, stats  # Success but no files to process

    # Determine output path (user_dictionary.json goes in config dir)
    if output_path is None:
        config_dir = get_user_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        output_path = os.path.join(config_dir, 'user_dictionary.json')

    # If no weights specified, scan all .txt files with weight 1
    if source_weights is None:
        source_weights = {}
        for filename in os.listdir(user_dict_dir):
            if filename.endswith('.txt'):
                source_weights[filename] = 1

    # Merged dictionary: {reading: {candidate: count}}
    merged_dictionary = {}

    # Process each file in the user dictionaries directory
    for filename, weight in source_weights.items():
        file_path = os.path.join(user_dict_dir, filename)
        if not os.path.isfile(file_path):
            logger.warning(f'User dictionary file not found: {file_path}')
            continue

        # Try different encodings (SKK files may use various encodings)
        encodings = ['utf-8', 'euc-jp', 'shift-jis']
        file_content = None

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    file_content = f.readlines()
                logger.debug(f'Successfully read {file_path} with encoding {encoding}')
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            logger.warning(f'Failed to read {file_path} with any supported encoding, skipping')
            continue

        # Track candidates seen in this file to avoid double-counting within same file
        seen_in_this_file = {}  # {reading: set(candidates)}

        # Process each line
        for line in file_content:
            reading, candidates = parse_skk_dictionary_line(line)
            if not reading or not candidates:
                continue

            # Initialize tracking for this reading if needed
            if reading not in seen_in_this_file:
                seen_in_this_file[reading] = set()

            # Initialize merged dictionary entry if needed
            if reading not in merged_dictionary:
                merged_dictionary[reading] = {}

            # Add candidates, incrementing by weight (only once per file)
            for candidate in candidates:
                if candidate not in seen_in_this_file[reading]:
                    seen_in_this_file[reading].add(candidate)
                    if candidate in merged_dictionary[reading]:
                        merged_dictionary[reading][candidate] += weight
                    else:
                        merged_dictionary[reading][candidate] = weight

        stats['files_processed'] += 1
        logger.debug(f'Processed user dictionary: {filename} with weight {weight}')

    # Calculate stats
    stats['total_readings'] = len(merged_dictionary)
    stats['total_candidates'] = sum(len(candidates) for candidates in merged_dictionary.values())

    # Only write if there are entries (don't create empty file)
    if not merged_dictionary:
        logger.info('No user dictionary entries found, skipping JSON generation')
        return True, None, stats

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged_dictionary, f, ensure_ascii=False, indent=2)
        logger.info(f'Generated user dictionary: {output_path}')
        logger.info(f'Stats: {stats["files_processed"]} files, {stats["total_readings"]} readings, {stats["total_candidates"]} candidates')
        return True, output_path, stats
    except Exception as e:
        logger.error(f'Failed to write user dictionary: {e}')
        return False, None, stats
