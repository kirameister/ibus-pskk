# Background

## What is PSKK?

**PSKK** stands for **Personaliz(ed|able) SKK**. It is an Japanese Input Method Engine (IME) designed for users who seek a highly customizable and efficient typing experience. While inspired by the classic SKK (Simple Kana to Kanji conversion) method, PSKK expands upon its foundations by integrating modern techniques and features like Kanchoku (direct Kanji input), simultaneous key processing, and CRF-based phrase segmentation.

## Design Philosophy

The development of PSKK is driven by three core principles:

1.  **Personalization**: Every aspect of the input experience should be configurable. From key bindings and keyboard layouts to the conversion logic itself, PSKK aims to be "your" personal IME.
2.  **Efficiency**: By supporting simultaneous key presses and direct Kanji input, PSKK reduces the number of keystrokes required for common Japanese text, enabling faster and more fluid typing.
3.  **Simplicity in Implementation, Power in Features**: PSKK is implemented in Python for ease of development and extensibility, while utilizing robust libraries like `crfsuite` for advanced features like phrase boundary prediction.

## Core Features and Technologies

### 1. Dictionary-Driven Conversion with CRF
Unlike traditional IMEs that rely on complex heuristic-based morphological analysis, PSKK uses a dictionary-driven approach. To handle multi-phrase input effectively, it optionally employs **Conditional Random Fields (CRF)** to predict bunsetsu (phrase unit) boundaries, facilitating more accurate conversion of longer sentences.

### 2. Kanchoku (漢直 - Direct Kanji Input)
PSKK supports direct Kanji input, allowing users to output specific Kanji characters through predefined key combinations (typically two keys held with a marker key). This bypasses the usual Kana-to-Kanji conversion process for frequently used words.

### 3. Simultaneous Key Input
The engine supports simultaneous key presses (often called "simultaneous打鍵" in Japanese), which is a key component of specialized Japanese keyboard layouts like **Shin-Geta (新下駄配列)**. This allows for a more ergonomic and rapid input of Kana characters.

### 4. SandS (Space and Shift)
A popular feature among power users, SandS allows the Space key to act as a Shift key when held down, and as a regular Space key when tapped. This minimizes finger movement and enhances typing speed.

### 5. Unique Input States
PSKK manages input through a sophisticated state machine, including:
- **Stealth Mode (IDLE)**: Input appears as if already committed, reducing visual distraction.
- **Bunsetsu Mode**: Explicitly marking text for conversion.
- **Forced Preedit**: A unique mode that allows mixing Kanchoku-produced Kanji with Kana for subsequent dictionary conversion, enabling flexible input strategies.

## Project History

PSKK started as a quest for the "final frontier" of Japanese input methods. It aims to bridge the gap between traditional conversion-heavy IMEs and ultra-specialized direct input methods, providing a platform where users can experiment and find their own optimal typing style.

To ensure high conversion accuracy on real-world text, PSKK utilizes training data sourced from diverse corpora, including the **Wikipedia Annotated Corpus** and classic Japanese literature from **Aozora Bunko**. This allows the CRF model to understand natural phrasing and sentence structures, particularly for users who prefer typing longer passages before converting.
