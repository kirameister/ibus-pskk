# Configuration Guide

This guide explains all configuration options available in IBus-PSKK and how to customize them.

## Configuration File Location

The configuration is stored in:
```
~/.config/ibus-pskk/config.json
```

You can edit this file directly or use the Settings Panel (recommended).

## Accessing Settings

Open the Settings Panel via:
- IBus menu → PSKK → Settings
- Or right-click the PSKK icon in the system tray

## Settings Panel Tabs

### General Tab

**Input Layout**
- **Description**: Select the keyboard layout for romaji-to-hiragana conversion
- **Default**: `shingeta.json` (新下駄配列)
- **Options**: Available layouts are stored in:
  - User: `~/.config/ibus-pskk/layouts/`
  - System: `/opt/ibus-pskk/layout/`

**Show Annotations**
- **Description**: Display candidate frequency and source dictionary information
- **Default**: Enabled

**Candidates per Page**
- **Description**: Number of conversion candidates shown at once
- **Range**: 5-15
- **Default**: 9

**Preedit Colors**
- **Foreground Color**: Text color for unconverted input (hex format, e.g., `000000` for black)
- **Background Color**: Background color for unconverted input (e.g., `d1eaff` for light blue)
- **Format**: 6-digit hex without `0x` or `#` prefix

**Use IBus Theme Colors**
- **Description**: Let the desktop theme/IBus panel determine preedit appearance
- **Requirement**: IBus 1.5.33 or newer
- **Default**: Disabled

---

### Key Configs Tab

Configure keybindings for various actions. Multiple keys can be assigned to the same action.

#### Available Actions

| Action | Description | Default Key |
|--------|-------------|-------------|
| Enable Hiragana Mode | Switch to Japanese input mode | `Henkan` (変換) |
| Disable Hiragana Mode | Switch to alphanumeric mode | `Muhenkan` (無変換) |
| Forced Preedit Trigger | Enter forced preedit mode for kanchoku+kana mixing | `f` |
| Convert to Katakana | Convert preedit to katakana | `Ctrl+K` |
| Convert to Hiragana | Convert preedit to hiragana | `Ctrl+J` |
| Convert to ASCII | Convert preedit to ASCII characters | `Ctrl+L` |
| Convert to Zenkaku | Convert preedit to full-width characters | `Ctrl+Shift+L` |
| Kanchoku/Bunsetsu Marker | Key for kanchoku input and bunsetsu marking | `Space` |
| Pure Kanchoku Trigger | Key for pure kanchoku (kanji-only) input | (none) |
| Bunsetsu Prediction Cycle | Cycle through CRF bunsetsu split candidates | `Shift+Space` |
| User Dictionary Editor | Open the user dictionary editor | `Ctrl+Shift+R` |
| Force Commit | Commit preedit without conversion | `Ctrl+O` |

#### Adding a Keybinding

1. Click the **Add** button
2. Select an action from the dropdown
3. Click the key button and press your desired key combination
4. Click **Save Settings**

#### Removing a Keybinding

1. Click the **✕** button on the row, or select the row and click **Remove**
2. Click **Save Settings**

#### Key Format

Keys are specified as modifier+key combinations:
- Single keys: `Space`, `Enter`, `Escape`
- With modifiers: `Ctrl+K`, `Shift+Space`, `Alt+m`
- Special keys: `Henkan`, `Muhenkan`, `F1-F12`

---

### System Dictionary Tab

Manage system dictionaries for kana-kanji conversion.

**Dictionary List**
- Enable/disable individual dictionaries using checkboxes
- Adjust priority using the weight column (higher = higher priority)
- Refresh button rescans the dictionary directory

**Convert Dictionaries**
- Converts SKK dictionaries to binary format for faster loading
- Run this after adding new system dictionaries

**Dictionary Location**
```
/opt/ibus-pskk/dictionaries/
```

---

### User Dictionary Tab

Manage personal dictionary files and entries.

**Dictionary Files**
- Place SKK-format `.txt` files in:
  ```
  ~/.config/ibus-pskk/dictionaries/
  ```
- Enable/disable individual files
- Adjust priority with weight column
- Click **Convert** to generate `imported_user_dictionary.json`

**User Dictionary Entries**
- Click **User Dictionary Entries** to open the dictionary editor
- Add, edit, search, and delete entries directly

**Editor Launch Key Binding**
- Set a hotkey (requires Ctrl+Shift+<key>) for quick access to the editor
- Default: `Ctrl+Shift+R`

---

### Ext-Dictionary Tab

Generate an extended dictionary that bridges kanchoku with normal kana-kanji conversion.

**Purpose**
Creates hybrid dictionary entries by:
1. Reading the kanchoku layout to find all produceable kanji
2. Extracting yomi→single-kanji mappings from source dictionaries
3. Matching those yomi against dictionary readings
4. Creating hybrid keys with matched yomi replaced by kanji

**Usage**
1. Select source dictionaries (system and/or user)
2. Click **Convert** to generate `extended_dictionary.json`
3. The extended dictionary is automatically used for conversion

**Note**: Requires system/user dictionaries to be converted first.

---

### 無連想配列 Tab (Murenso/Kanchoku)

Configure kanchoku (direct kanji input) layouts and mappings.

**Layout Selection**
- Choose from available kanchoku layouts
- User layouts: `~/.config/ibus-pskk/kanchoku_layouts/`
- System layouts: `/opt/ibus-pskk/kanchoku_layouts/`
- Default: `aki_code.json`

**Mapping Table**
- View all two-key to kanji mappings
- Filter by 1st key, 2nd key, or kanji character
- Edit mappings directly in the table
- Changes are saved to a custom kanchoku layout file

**Loading and Saving**
- **Load from File**: Import a custom kanchoku configuration
- **Save to File**: Export current mappings to a file

---

## Advanced Configuration Options

These options can be set directly in `config.json`:

### Logging

```json
"logging_level": "DEBUG"
```
- Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- Default: `WARNING`

### Input Mode Keys

```json
"enable_hiragana_key": ["Henkan"],
"disable_hiragana_key": ["Muhenkan"]
```
- Keys to toggle hiragana mode on/off
- Common options: `Henkan`, `Muhenkan`, `Alt+m`, `Ctrl+Shift+m`

### Forced Preedit Trigger

```json
"forced_preedit_trigger_key": ["f"]
```
- Key to trigger forced preedit mode for mixing kanchoku with kana
- Default: `f`

### Bunsetsu Prediction

```json
"bunsetsu_prediction_n_best": 3
```
- Maximum number of bunsetsu-split predictions from CRF model
- Higher values provide more options but may slow conversion

```json
"bunsetsu_prediction_cycle_key": ["Shift+space"]
```
- Key to cycle through bunsetsu split candidates

### Dictionary Configuration

```json
"dictionaries": {
    "system": {
        "/opt/ibus-pskk/dictionaries/SKK-JISYO.L": 1,
        "/opt/ibus-pskk/dictionaries/SKK-JISYO.M": 2
    },
    "user": {
        "my_dictionary.json": 1
    }
}
```
- Format: `{path: weight}`
- Higher weight = higher priority during merge

### Kanchoku/Bunsetsu Marker

```json
"kanchoku_bunsetsu_marker": ["space"]
```
- Key used for typing kanchoku strokes while held
- Marks bunsetsu boundary when tapped

### Pure Kanchoku Trigger

```json
"kanchoku_pure_trigger_key": []
```
- Key for pure kanchoku input (kanji-only, no bunsetsu marking)
- Keys not in the kanchoku layout pass through normally

### Character Conversion Keys

```json
"conversion_keys": {
    "to_katakana": ["Ctrl+K"],
    "to_hiragana": ["Ctrl+J"],
    "to_ascii": ["Ctrl+L"],
    "to_zenkaku": ["Ctrl+Shift+L"]
}
```

### Force Commit Key

```json
"force_commit_key": ["Ctrl+O"]
```
- Commits preedit as-is without kana-kanji conversion
- If buffer is empty, passes the key to the application

---

## Custom Layouts

### Creating a Custom Input Layout

1. Create a JSON file with the following structure:
```json
{
    "name": "My Custom Layout",
    "description": "My custom romaji layout",
    "mappings": {
        "a": "あ",
        "i": "い",
        ...
    }
}
```

2. Place it in:
   - `~/.config/ibus-pskk/layouts/` (user)
   - `/opt/ibus-pskk/layout/` (system)

3. Select it in Settings → General → Input Layout

### Creating a Custom Kanchoku Layout

1. Create a JSON file:
```json
{
    "a": {
        "k": "漢"
    },
    ...
}
```

2. Place it in:
   - `~/.config/ibus-pskk/kanchoku_layouts/` (user)
   - `/opt/ibus-pskk/kanchoku_layouts/` (system)

3. Select it in Settings → 無連想配列 → Kanchoku Layout

---

## Importing SKK Dictionaries

SKK dictionaries can be imported as user dictionaries:

1. Obtain an SKK dictionary file (`.txt` or `.SKK-JISYO.*`)
2. Place it in:
   ```
   ~/.config/ibus-pskk/dictionaries/
   ```
3. Open Settings → User Dictionary tab
4. Click **Refresh List** to detect the new file
5. Enable the dictionary and set its weight
6. Click **Convert** to generate the binary dictionary

---

## Resetting to Defaults

To reset all settings to their default values:

1. Delete or rename the configuration file:
   ```bash
   mv ~/.config/ibus-pskk/config.json ~/.config/ibus-pskk/config.json.bak
   ```
2. Restart IBus or re-login

---

## Troubleshooting Configuration Issues

### Changes Not Taking Effect
- Settings take effect on the next keystroke
- Try switching to alphanumeric mode ('A') and back to hiragana mode
- As a last resort, restart IBus: `ibus restart`

### Invalid Keybindings
- Ensure no conflicting keybindings (same key assigned to multiple actions)
- The Settings Panel will warn you if conflicts are detected

### Dictionary Not Loading
- Verify the dictionary file exists at the specified path
- Check file permissions (must be readable)
- Try clicking **Refresh List** in the settings

---

## See Also

- [User Guide](en_User-Guide.md) - How to use PSKK features
- [Getting Started](en_Getting-Started.md) - Installation guide
