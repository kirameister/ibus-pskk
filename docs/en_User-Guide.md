# User Guide

This guide covers the advanced features and usage patterns of IBus-PSKK beyond basic typing.

## Input Modes

PSKK supports two primary input modes:

### Alphanumeric Mode (A)

In this mode, all keystrokes pass directly to the application unchanged. Use this for:
- Typing English text
- Programming
- Entering passwords
- Any situation where you don't want Japanese input

### Hiragana Mode (あ)

This is the Japanese input mode. Keystrokes are processed through the Japanese input pipeline:
- Romaji input is converted to hiragana
- Space triggers kana-kanji conversion
- Special key sequences enable advanced features

## Switching Modes

- **Default toggle key**: Press `Alt+m` (configurable) to switch between Alphanumeric and Hiragana modes
- **From IBus menu**: Click the PSKK icon in the system tray and select your desired mode

## Basic Japanese Input

### Romaji to Hiragana

Type romaji and it automatically converts to hiragana:
- `konnichiwa` → こんにちは
- `nihon` → にほん

### Kana-Kanji Conversion

1. Type the hiragana you want to convert
2. Press `Space` to enter conversion mode
3. Use `Space` to cycle through candidates
4. Press `Enter` to confirm and commit the text

### Candidate Selection

- `Space` - Select next candidate
- `Arrow Up/Down` - Navigate through candidates
- `Enter` - Confirm selected candidate
- `ESC` or `Backspace` - Cancel conversion and return to input mode

## Advanced Features

### Kanchoku (Direct Kanji Input)

Kanchoku allows you to input kanji directly using two-key combinations, bypassing the need for kana-kanji conversion.

#### How to Use Kanchoku

1. Hold down the marker key (default: `Space`)
2. Press the first key of the kanchoku sequence
3. Press the second key
4. Release the marker key

Example: `Space` + `j` + `k` → 漢

#### Forced Preedit Mode

This feature allows you to mix kanchoku-input kanji with hiragana for subsequent conversion:

1. Hold `Space`
2. Press `f` (the trigger key)
3. Release `Space`
4. Type kanchoku kanji followed by hiragana
5. Press `Space` to convert the entire string

Example: Want to type "企業" (きぎょう)
- Enter forced preedit mode
- Type 企 (kanchoku) + ぎょう (hiragana)
- Convert: 企ぎょう → 企業

### Bunsetsu (Phrase Boundary) Marking

Mark phrase boundaries to improve conversion accuracy for longer sentences:

1. Hold `Space`
2. Type a character
3. Release `Space`

This marks the boundary between phrases, helping the converter understand sentence structure.

### Simultaneous Key Input (新下駄配列)

PSKK supports simultaneous key presses for efficient kana input. This is the default keyboard layout. Keys pressed together are processed as a single input:

- `k` + `a` together → か
- `s` + `u` together → す

This layout allows for faster typing by reducing the number of individual key presses.

### SandS (Space and Shift)

SandS (Shift and Space) allows the Space key to function as both a Space (when tapped) and a Shift key (when held). This is useful for:

- Mode switching without moving your hand
- Typing capital letters while in hiragana mode

Enable this feature in Settings → Input tab.

## Character Conversions

PSKK provides quick conversion for different character types:

| Action | Default Key |
|--------|-------------|
| To Hiragana | `Ctrl+j` |
| To Katakana | `Ctrl+k` |
| To ASCII | `Ctrl+l` |
| To Full-width | `Ctrl+o` |

### Examples

- こんにちは (hiragana) → コンニチハ (katakana)
- hello (ASCII) → ｈｅｌｌｏ (full-width)

## User Dictionary

Add custom words to personalize your input experience.

### Adding Words via Editor

1. Open Settings → User Dictionary tab
2. Click "User Dictionary Entries"
3. Enter the reading (hiragana) in the Reading field
4. Enter the kanji in the Kanji field
5. Click Add

### Quick Registration

You can quickly add words while typing:

1. Type the reading of the word you want to register
2. Press `Ctrl+Shift+R` (configurable)
3. The current text becomes the reading
4. If you have text in your clipboard, it becomes the candidate
5. Edit if needed and confirm

### Dictionary Format

The user dictionary is stored in JSON format at:
```
~/.config/ibus-pskk/user_dictionary.json
```

Structure:
```json
{
  "たなか": {
    "田中": 5,
    "棚下": 1
  },
  "ひろし": {
    "博": 3,
    "宏": 2
  }
}
```

The count value represents usage frequency - higher counts make candidates appear earlier in suggestions.

## Settings Panel

Access the settings panel from:
- IBus menu → PSKK → Settings
- Or right-click the PSKK icon in the panel

### General Tab

- **Input Layout**: Choose between different keyboard layouts (QWERTY, etc.)
- **Show Annotations**: Display candidate frequency and source dictionary
- **Candidates per Page**: Set how many candidates to show (5-15)
- **Preedit Colors**: Customize the colors for input display

### Input Tab

- **SandS**: Enable Space as Shift modifier
- **Learning Mode**: Remember your conversion choices

### System Dictionary Tab

- Enable/disable system dictionaries
- Adjust dictionary weights (priority)
- Convert SKK dictionaries to binary format

### User Dictionary Tab

- Manage personal dictionary files
- Open the User Dictionary Editor
- Set keybinding for quick editor access

### Ext-Dictionary Tab

- Add external dictionaries from custom locations
- Import SKK-JISYO format dictionaries

### 無連想配列 Tab (Murenso/Kanchoku)

- Select different kanchoku layouts
- Edit two-key to kanji mappings
- Load/save custom configurations

## Key Bindings Reference

| Function | Default Binding |
|----------|-----------------|
| Toggle Mode | `Alt+m` |
| Convert | `Space` |
| Cancel | `ESC` / `Backspace` |
| Commit | `Enter` |
| To Hiragana | `Ctrl+j` |
| To Katakana | `Ctrl+k` |
| To ASCII | `Ctrl+l` |
| To Full-width | `Ctrl+o` |
| User Dictionary Editor | `Ctrl+Shift+R` |

## Tips and Tricks

### Efficient Typing Flow

1. Type in romaji → hiragana appears
2. Continue typing the sentence in hiragana
3. Use bunsetsu marking (Space + key) for long sentences
4. Press Space to convert the entire phrase
5. Select the correct conversion from candidates
6. Press Enter to commit

### Using Kanchoku Effectively

- Frequently used kanji (your name, company, etc.) can be registered in kanchoku for instant input
- Combine with forced preedit for complex words containing kanchoku characters

### Improving Conversion Accuracy

- Use bunsetsu marking for longer sentences
- Add frequently used words to your user dictionary
- Adjust dictionary weights in the settings to prioritize certain dictionaries

## Troubleshooting

### Conversion Not Working

1. Check that you're in Hiragana mode (あ)
2. Verify dictionaries are enabled in Settings → System Dictionary
3. Try generating dictionaries if none are available

### Kanchoku Not Inputting Kanji

1. Verify kanchoku layout is loaded in Settings → 無連想配列
2. Check that the key sequence is correct (marker + key1 + key2)

### Mode Switching Not Working

1. Check the configured mode switch key in Settings → General
2. Ensure no other application is intercepting the key combination

---

For more information, see:
- [Getting Started](en_Getting-Started.md) - Installation guide
- [Background](en_Background.md) - Design philosophy and history
