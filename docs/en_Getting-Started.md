# Getting Started

This guide will help you install and set up IBus-PSKK.

## Prerequisites

- Linux with IBus installed
- Python 3.8 or later
- GTK 3

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/kirameister/ibus-pskk.git
cd ibus-pskk

# Install dependencies and build
just install

# Restart IBus
ibus restart
```

### Arch Linux (AUR)

```bash
# Using yay or paru
yay -S ibus-pskk
```

## First Run

1. Open your system's IBus preferences
2. Add "PSKK" to your input methods
3. Switch to PSKK using your configured input method switcher (usually `Super+Space`)

## Basic Usage

- Type romanji to input hiragana
- Press `Space` to convert to kanji
- Press `Enter` to confirm

## Next Steps

- [User Guide](en_User-Guide.md) - Learn more features
- [Configuration](en_Configuration.md) - Customize your setup

---

[日本語版](Getting-Started.md)
