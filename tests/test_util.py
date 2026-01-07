#!/usr/bin/env python3
# tests/test_util.py - Unit tests for util.py

import pytest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import util


class TestGetConfigData:
    """Test suite for get_config_data() function"""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        temp_home = tempfile.mkdtemp()
        temp_data = tempfile.mkdtemp()

        yield {
            'home': temp_home,
            'data': temp_data,
            'config_dir': os.path.join(temp_home, '.config', 'ibus-pskk'),
            'config_file': os.path.join(temp_home, '.config', 'ibus-pskk', 'config.json'),
            'default_config': os.path.join(temp_data, 'config.json')
        }

        # Cleanup
        shutil.rmtree(temp_home, ignore_errors=True)
        shutil.rmtree(temp_data, ignore_errors=True)

    @pytest.fixture
    def default_config_data(self):
        """Sample default configuration"""
        return {
            "layout": "roman.json",
            "kanchoku_layout": "aki_code.json",
            "dictionaries": {
                "system": [],
                "user": []
            },
            "learning": {
                "enabled": True,
                "priority_file": "candidate_priority.json"
            },
            "sands": {
                "enabled": True
            },
            "murenso": {
                "enabled": False
            }
        }

    def test_no_warnings_when_config_exists_and_valid(self, temp_dirs, default_config_data):
        """Test that no warnings are returned when config exists and is valid"""
        # Create config directory
        os.makedirs(temp_dirs['config_dir'], exist_ok=True)

        # Write default config
        with open(temp_dirs['default_config'], 'w', encoding='utf-8') as f:
            json.dump(default_config_data, f)

        # Write user config (same as default)
        with open(temp_dirs['config_file'], 'w', encoding='utf-8') as f:
            json.dump(default_config_data, f)

        # Mock the directory functions
        with patch('util.get_user_configdir', return_value=temp_dirs['config_dir']):
            with patch('util.get_default_config_path', return_value=temp_dirs['default_config']):
                config, warnings = util.get_config_data()

        assert warnings == ""
        assert config is not None
        assert config["layout"] == "roman.json"

    def test_warning_when_config_not_found(self, temp_dirs, default_config_data):
        """Test that a warning is returned when config.json is not found"""
        # Create config directory but no config file
        os.makedirs(temp_dirs['config_dir'], exist_ok=True)

        # Write default config
        with open(temp_dirs['default_config'], 'w', encoding='utf-8') as f:
            json.dump(default_config_data, f)

        # Mock the directory functions
        with patch('util.get_user_configdir', return_value=temp_dirs['config_dir']):
            with patch('util.get_default_config_path', return_value=temp_dirs['default_config']):
                config, warnings = util.get_config_data()

        assert warnings != ""
        assert "config.json is not found" in warnings
        assert "Copying the default config.json" in warnings
        assert config is not None
        # Verify config file was created
        assert os.path.exists(temp_dirs['config_file'])

    def test_warning_when_key_missing(self, temp_dirs, default_config_data):
        """Test that a warning is returned when a key is missing from user config"""
        # Create config directory
        os.makedirs(temp_dirs['config_dir'], exist_ok=True)

        # Write default config
        with open(temp_dirs['default_config'], 'w', encoding='utf-8') as f:
            json.dump(default_config_data, f)

        # Write user config with missing key
        user_config = default_config_data.copy()
        del user_config['sands']
        with open(temp_dirs['config_file'], 'w', encoding='utf-8') as f:
            json.dump(user_config, f)

        # Mock the directory functions
        with patch('util.get_user_configdir', return_value=temp_dirs['config_dir']):
            with patch('util.get_default_config_path', return_value=temp_dirs['default_config']):
                config, warnings = util.get_config_data()

        assert warnings != ""
        assert '"sands"' in warnings
        assert "was not found" in warnings
        assert "Copying the default key-value" in warnings
        # Verify the missing key was added
        assert "sands" in config
        assert config["sands"]["enabled"] == True

    def test_warning_when_type_mismatch(self, temp_dirs, default_config_data):
        """Test that a warning is returned when there's a type mismatch"""
        # Create config directory
        os.makedirs(temp_dirs['config_dir'], exist_ok=True)

        # Write default config
        with open(temp_dirs['default_config'], 'w', encoding='utf-8') as f:
            json.dump(default_config_data, f)

        # Write user config with type mismatch (layout should be string, not dict)
        user_config = default_config_data.copy()
        user_config['layout'] = {"type": "roman"}  # Wrong type (dict instead of string)
        with open(temp_dirs['config_file'], 'w', encoding='utf-8') as f:
            json.dump(user_config, f)

        # Mock the directory functions
        with patch('util.get_user_configdir', return_value=temp_dirs['config_dir']):
            with patch('util.get_default_config_path', return_value=temp_dirs['default_config']):
                config, warnings = util.get_config_data()

        assert warnings != ""
        assert "Type mismatch" in warnings
        assert '"layout"' in warnings

    def test_multiple_warnings(self, temp_dirs, default_config_data):
        """Test that multiple warnings are returned when multiple issues exist"""
        # Create config directory
        os.makedirs(temp_dirs['config_dir'], exist_ok=True)

        # Write default config
        with open(temp_dirs['default_config'], 'w', encoding='utf-8') as f:
            json.dump(default_config_data, f)

        # Write user config with multiple issues
        user_config = default_config_data.copy()
        del user_config['sands']  # Missing key
        del user_config['murenso']  # Another missing key
        with open(temp_dirs['config_file'], 'w', encoding='utf-8') as f:
            json.dump(user_config, f)

        # Mock the directory functions
        with patch('util.get_user_configdir', return_value=temp_dirs['config_dir']):
            with patch('util.get_default_config_path', return_value=temp_dirs['default_config']):
                config, warnings = util.get_config_data()

        assert warnings != ""
        # Check that multiple warnings are present (separated by newlines)
        assert warnings.count('\n') >= 1
        assert '"sands"' in warnings
        assert '"murenso"' in warnings
        # Verify both missing keys were added
        assert "sands" in config
        assert "murenso" in config

    def test_json_decode_error_returns_default_config(self, temp_dirs, default_config_data):
        """Test that JSONDecodeError triggers fallback to default config"""
        # Create config directory
        os.makedirs(temp_dirs['config_dir'], exist_ok=True)

        # Write default config
        with open(temp_dirs['default_config'], 'w', encoding='utf-8') as f:
            json.dump(default_config_data, f)

        # Write invalid JSON to user config
        with open(temp_dirs['config_file'], 'w', encoding='utf-8') as f:
            f.write("{ invalid json }")

        # Mock the directory functions
        with patch('util.get_user_configdir', return_value=temp_dirs['config_dir']):
            with patch('util.get_default_config_path', return_value=temp_dirs['default_config']):
                config, warnings = util.get_config_data()

        # Should return default config with no warnings (errors are logged, not returned as warnings)
        assert warnings == ""
        assert config is not None
        assert config["layout"] == "roman.json"

    def test_config_file_created_with_correct_content(self, temp_dirs, default_config_data):
        """Test that config file is created with correct content when not found"""
        # Create config directory
        os.makedirs(temp_dirs['config_dir'], exist_ok=True)

        # Write default config
        with open(temp_dirs['default_config'], 'w', encoding='utf-8') as f:
            json.dump(default_config_data, f)

        # Mock the directory functions
        with patch('util.get_user_configdir', return_value=temp_dirs['config_dir']):
            with patch('util.get_default_config_path', return_value=temp_dirs['default_config']):
                config, warnings = util.get_config_data()

        # Verify file was created
        assert os.path.exists(temp_dirs['config_file'])

        # Verify content matches default
        with open(temp_dirs['config_file'], 'r', encoding='utf-8') as f:
            created_config = json.load(f)

        assert created_config == default_config_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
