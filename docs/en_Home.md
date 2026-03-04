# IBus-PSKK Documentation

Welcome to the IBus-PSKK documentation!

PSKK (Personaliz(ed|able) SKK) is an input method engine (IME) for IBus that provides Japanese input with support for various input modes and dictionary-based conversion. It aims to be an easy yet effective implementation of a Japanese IME that is highly configurable.

## Quick Links

- [Background](en_Background.md) - How the PSKK got started
- [Getting Started](en_Getting-Started.md) - Installation and basic setup
- [User Guide](en_User-Guide.md) - How to use PSKK
- [Configuration](en_Configuration.md) - Settings and customization
- [Developer Guide](en_Developer-Guide.md) - Technical documentation

## Features

- Simultaneous Japanese typing support (新下駄配列 by default)
- Kanchoku (direct kanji input) support
- User dictionary management
- CRF (Conditional Random Field) based word-split detection for Kana-to-Kanji conversion
- Configurable keybindings
- SandS (Shift and Space) feature for easy mode switching
- Dictionary-driven conversion with optional bunsetsu prediction for multi-phrase input
- System and user dictionary support with on-demand dictionary generation

## Screenshots

<!-- Add screenshots here -->
<!-- ![Settings Panel](assets/screenshots/settings-panel.png) -->

## Technical Details

PSKK uses IBus as the input method framework and provides:
- Customizable keyboard layouts (新下駄配列 by default)
- CRF-based bunsetsu prediction for improved conversion accuracy
- Support for both system and user dictionaries
- On-demand dictionary generation through the IBus settings menu

## Getting Help

If you encounter issues or have questions:

- [GitHub Issues](https://github.com/kirameister/ibus-pskk/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/kirameister/ibus-pskk/discussions) - General questions and community help

---

[日本語版](Home.md)
