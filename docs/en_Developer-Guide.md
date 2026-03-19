# Developer Guide

This guide provides technical documentation for developers who want to understand, extend, or contribute to IBus-PSKK.

## Architecture Overview

IBus-PSKK is organized into several core modules that work together:

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                   │
│              Entry point, IBus registration                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        engine.py                                  │
│         Main IBus Engine (IBus.Engine interface)                  │
│    - Key event processing                                        │
│    - State machine management                                    │
│    - Mode switching                                              │
└─────────────────────────────────────────────────────────────────┘
         ↓              ↓              ↓              ↓
┌──────────────┐  ┌──────────┐  ┌────────────────┐  ┌─────────┐
│ henkan.py    │  │kanchoku  │  │simultaneous_   │  │ util.py │
│              │  │.py       │  │processor.py    │  │         │
│ Kana-Kanji   │  │          │  │                │  │ Config  │
│ conversion   │  │ Direct   │  │ Key combination│  │ Paths   │
│              │  │ kanji    │  │ detection      │  │ Utils   │
└──────────────┘  └──────────┘  └────────────────┘  └─────────┘
```

## Core Modules

### main.py - Entry Point

**Purpose**: Initializes the IBus connection and registers the PSKK engine.

**Key Components**:
- `IMApp` class: Manages IBus connection and engine registration
- Handles two execution modes:
  - `--ibus`: Normal mode (started by IBus daemon)
  - Standalone: For testing/development

**Key Responsibilities**:
- GTK initialization
- IBus bus connection
- Factory registration (`factory.add_engine("pskk", EnginePSKK)`)
- D-Bus name request

### engine.py - Main Engine

**Purpose**: Core IME logic implementing the IBus.Engine interface.

**Key Components**:

#### State Machine

The engine manages input through a sophisticated state machine:

```
┌──────────┐    space+key    ┌────────────┐
│   IDLE   │ ──────────────► │  BUNSETSU  │
│(通常入力) │                │ (文節入力)  │
└──────────┘ ◄────────────── └─────┬──────┘
     ↑                              │ Enter
     │         ESC/Backspace        │ continue
     │                              ▼
     │                       [Commit text]
     │                       ┌────────────┐
     └────────────────────── │   FORCED   │
           space tap         │  PREEDIT   │
                             │(強制入力)  │
                             └────────────┘
```

#### Input Modes

- **Mode 'A' (Alphanumeric)**: All keystrokes pass through unchanged
- **Mode 'あ' (Hiragana)**: Japanese input pipeline active

#### Marker Key State Machine

The marker key (typically Space) enables three behaviors:

1. **Kanchoku**: `space↓` → `key1↓↑` → `key2↓↑` → `space↑` → kanji output
2. **Bunsetsu**: `space↓` → `key1↓↑` → `space↑` → bunsetsu boundary
3. **Forced Preedit**: `space↓` → `f↓↑` → `space↑` → forced preedit mode

### henkan.py - Kana-Kanji Conversion

**Purpose**: Handles kana-to-kanji conversion using dictionary lookup and CRF-based bunsetsu segmentation.

**Two Conversion Modes**:

1. **Whole-Word Mode**: Dictionary lookup for exact match
2. **Bunsetsu Mode**: CRF-based phrase segmentation for multi-word input

**CRF Integration Flow**:
```
Input: きょうはてんきがよい
    ↓
Feature Extraction (util.py)
    ↓
CRF Prediction → Labels: B-L, I-L, B-P, B-L, I-L, B-P, B-L, I-L
    ↓
Bunsetsu Segmentation: [きょう|L, は|P, ていき|P, が|P, よい|L]
    ↓
Dictionary Lookup per Bunsetsu
    ↓
Output: 今日は天気が良い
```

### kanchoku.py - Direct Kanji Input

**Purpose**: Handles kanchoku (漢直) - direct kanji input via two-key combinations.

**Key Classes**:
- `KanchokuProcessor`: Manages kanchoku input and layout

### simultaneous_processor.py - Key Combination Detection

**Purpose**: Processes simultaneous key presses for efficient kana input (新下駄配列 support).

**Key Classes**:
- `SimultaneousInputProcessor`: Converts raw keystrokes to hiragana

### util.py - Utilities

**Purpose**: Core utility functions including:

#### Character Classification
```python
def char_type(c):
    # Returns: 'hiragana', 'katakana', 'kanji', 'ascii', 'other'
```

#### CRF Feature Extraction
- `add_feature_ctype()`: Character type feature
- `add_feature_char()`: Character identity
- `add_feature_bigram_left/right()`: Adjacent character features
- `add_feature_trigram_left/right()`: Trigram features
- `add_features_per_line()`: Combine all features

#### Dictionary Management
- `get_dictionary_files()`: Get active dictionary paths
- `generate_system_dictionary()`: Create system dictionary from SKK files
- `generate_extended_dictionary()`: Create hybrid kanchoku-conversion dictionary

### crf_core.py - CRF Training Logic

**Purpose**: Core logic for CRF-based bunsetsu segmentation, separated from GUI.

**Key Functions**:
- `train_model()`: Train CRF model with pycrfsuite
- `load_corpus()`: Load training data from MeCab-processed files
- `parse_annotated_line()`: Parse training data format

**Constants**:
- `JOSHI`: Japanese particles (助詞)
- `JODOUSHI`: Auxiliary verbs (助動詞)

### conversion_model.py - CRF Training GUI

**Purpose**: GTK interface for training and testing CRF models.

**Tabs**:
1. **Test Tab**: Test predictions on arbitrary input
2. **Train Tab**: 3-step training pipeline

## Data Flow

### Key Event Processing

```
Keyboard Event (keyval, keycode, state)
    ↓
do_process_key_event() [engine.py]
    ↓
┌─ Check enable_hiragana_key (mode toggle)
├─ If mode 'A': pass through
└─ _process_key_event()
    │
    ├─ Kanchoku/Bunsetsu marker handling (highest priority)
    ├─ Config-driven key bindings
    ├─ Combo keys (Ctrl+X, etc.)
    ├─ Special keys (Enter, Backspace, ESC)
    └─ Regular character → SimultaneousInputProcessor
```

### Conversion Flow

```
Preedit String (hiragana)
    ↓
HenkanProcessor.henkan()
    ├─ Try whole-word dictionary lookup
    │   └─ Success → Return candidates
    │
    └─ Fall back to bunsetsu mode
        ├─ CRF predicts bunsetsu boundaries
        ├─ Lookup each bunsetsu in dictionary
        └─ Combine results
```

## File Structure

```
ibus-pskk/
├── src/
│   ├── main.py                 # Entry point
│   ├── engine.py               # Main engine (IBus.Engine)
│   ├── henkan.py               # Kana-kanji conversion
│   ├── kanchoku.py             # Direct kanji input
│   ├── simultaneous_processor.py # Simultaneous key processing
│   ├── settings_panel.py       # GTK settings UI
│   ├── user_dictionary_editor.py # Dictionary editor GUI
│   ├── conversion_model.py      # CRF training GUI
│   ├── crf_core.py             # CRF training logic
│   ├── crf_train_cli.py        # CLI training tool
│   ├── util.py                 # Utilities
│   ├── katsuyou.py             # conjugation support
│   └── paths.py                # Auto-generated paths
├── data/
│   ├── pskk.xml                # IBus component XML
│   ├── default_user_config.json # Default config
│   ├── layouts/                # Input layouts
│   │   └── shingeta.json       # 新下駄配列
│   ├── kanchoku_layouts/       # Kanchoku layouts
│   │   └── aki_code.json       # Aki code
│   ├── crf_training/           # CRF training data
│   │   └── bunsetsu.crfsuite  # Trained model
│   └── skk_dict/               # SKK dictionaries
├── locales/                    # i18n files
├── tests/                      # Unit tests
├── justfile                    # Build automation
└── docs/                       # Documentation
```

## Configuration System

### Config File Location
```
~/.config/ibus-pskk/config.json
```

### Key Config Options

```json
{
    "layout": "shingeta.json",
    "kanchoku_layout": "aki_code.json",
    "enable_hiragana_key": ["Henkan"],
    "kanchoku_bunsetsu_marker": ["space"],
    "conversion_keys": {
        "to_katakana": ["Ctrl+K"],
        "to_hiragana": ["Ctrl+J"],
        "to_ascii": ["Ctrl+L"],
        "to_zenkaku": ["Ctrl+Shift+L"]
    },
    "dictionaries": {
        "system": {},
        "user": {}
    }
}
```

## Dictionary System

### Dictionary Format (JSON)
```json
{
    "読み": {
        "候補1": 頻度,
        "候補2": 頻度
    }
}
```

### Dictionary Priority
1. `user_dictionary.json` (highest - user's own entries)
2. `imported_user_dictionary.json` (converted from SKK files)
3. `system_dictionary.json` (from system SKK dictionaries)
4. `extended_dictionary.json` (kanchoku-conversion bridge)

### SKK Dictionary Format
```
かな [候補1/候補2/...] 頻度
```
Example: `とうきょう /東京/東京駅/東鏡/等極/糖硬/東協/倒鏡/搭業/闘形/桃姜/
```

## CRF Model System

### Label Meanings
- `B-L`: Beginning of Lookup bunsetsu (should convert)
- `I-L`: Inside Lookup bunsetsu
- `B-P`: Beginning of Passthrough bunsetsu (no conversion)
- `I-P`: Inside Passthrough bunsetsu

### Feature Types
1. **Character features**: char, char_left, char_right
2. **N-gram features**: bigram_left/right, trigram_left/right
3. **Type features**: ctype (hira/non-hira)
4. **Dictionary features**: dict_max_kl_*, dict_entry_ct_*

### Training Data Format
```
き B-L ょ I-L う I-L は B-P て I-L ん I-L き I-L が B-P よ I-L い I-L
```

## Building and Installation

### Development Setup
```bash
# Install dependencies
just install-deps

# Generate paths.py for development
just generate-paths

# Run in development mode
python src/main.py

# Run tests
just test
```

### Full Installation
```bash
just install
ibus restart
```

### i18n Workflow
```bash
# Extract strings
just i18n-extract

# Initialize new language
just i18n-init ja

# Update translations
just i18n-update

# Compile
just i18n-compile
```

## Testing

### Run Tests
```bash
just test
```

### Test Coverage Areas
- `test_util.py`: Configuration and utility functions
- `test_kanchoku.py`: Kanchoku input processing
- `test_simultaneous_processor.py`: Key combination detection
- `test_skk_dictionary.py`: Dictionary parsing
- `test_katsuyou.py`: Conjugation handling

## Contributing

### Code Style
- Follow existing patterns in the codebase
- Add bilingual docstrings (English/Japanese)
- Run linting: `ruff check src/`

### Key Conventions
1. **State Machine Documentation**: Document state transitions clearly
2. **Bilingual Comments**: Include Japanese translations for key concepts
3. **Error Handling**: Use logging for debugging, graceful fallbacks for missing features

### Submitting Changes
1. Create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation (this guide, docstrings)
5. Submit a pull request

## Debugging

### Enable Debug Logging
Edit `config.json`:
```json
"logging_level": "DEBUG"
```

### View Logs
```bash
tail -f ~/.config/ibus-pskk/ibus-pskk.log
```

### Common Issues

#### Dictionary Not Loading
- Check file permissions: `ls -la ~/.config/ibus-pskk/`
- Verify dictionaries exist: `ls ~/.config/ibus-pskk/*.json`

#### Kanchoku Not Working
- Verify layout file exists
- Check key codes match layout format

#### CRF Not Working
- Verify pycrfsuite is installed: `pip show python-crfsuite`
- Check model file exists: `ls ~/.config/ibus-pskk/bunsetsu.crfsuite`

## External Dependencies

### Required
- Python 3.8+
- IBus (libibus-1.0-dev)
- GTK 3.0 (libgtk-3-dev)
- GLib

### Optional
- `pycrfsuite`: For CRF bunsetsu prediction
- `mecab`: For training data preparation

## References

- [IBus API Documentation](http://lazka.github.io/pgi-docs/IBus-1.0/)
- [GTK Documentation](http://lazka.github.io/pgi-docs/Gtk-4.0/)
- [pycrfsuite Documentation](https://python-crfsuite.readthedocs.io/)
- [SKK Dictionary](https://github.com/skk-dev/dict)
