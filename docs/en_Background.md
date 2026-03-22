# Background

## What is PSKK?

**PSKK** stands for **Personaliz(ed|able) SKK**. It is an Japanese Input Method Engine (IME) designed for users who seek a highly customizable and complete control over the typing experience. While inspired by the classic SKK (Simple Kana to Kanji conversion) method, PSKK expands upon its foundations by integrating modern techniques and features like Kanchoku (direct Kanji input), simultaneous key input, and SandS.

## Design Philosophy

The development of PSKK is driven by three core principles:

1.  **Control over perfection**: PSKK does not aim for the perfect conversion on sentence basis. Instead, it aims (and intended strength is) to let the end-user take full control over the IME conversion. 
2.  **Personalization**: Every aspect of the input experience should be configurable. From key bindings and keyboard layouts to the conversion logic itself, PSKK aims to be "your" personal IME.
3.  **Efficiency**: By supporting simultaneous key presses and direct Kanji input, PSKK reduces the number of keystrokes required for common Japanese text, enabling faster and more fluid typing.
4.  **Simplicity in Implementation, Power in Features**: PSKK is implemented in Python for ease of development and extensibility, while utilizing robust libraries like `crfsuite` for advanced features like phrase boundary prediction.

## Core Features and Technologies

### 1. Dictionary-Driven Conversion with CRF
Unlike traditional IMEs that rely on complex heuristic-based morphological analysis, PSKK uses a dictionary-driven approach. To handle multi-phrase input effectively, it optionally employs **Conditional Random Fields (CRF)** to predict bunsetsu (phrase unit) boundaries, facilitating more accurate conversion of longer sentences.

### 2. Kanchoku (漢直 - Direct Kanji Input)
PSKK supports direct Kanji input, allowing users to output specific Kanji characters through predefined key combinations (typically two keys held with a marker key). This bypasses the usual Kana-to-Kanji conversion process for frequently used words.

### 3. Simultaneous Key Input
The engine supports simultaneous key presses (often called "同時打鍵" in Japanese), which is a key component of specialized Japanese keyboard layouts like **Shin-Geta (新下駄配列)**. This allows for a more ergonomic and rapid input of Kana characters.

### 4. SandS (Space and Shift)
A popular feature among power users, SandS allows the Space key to act as a Shift key when held down, and as a regular Space key when tapped. This minimizes finger movement and enhances typing speed.

### 5. Unique Input States
PSKK manages input through a sophisticated state machine, including:
- **Stealth Mode (IDLE)**: Input appears as if already committed, reducing visual distraction.
- **Bunsetsu Mode**: Explicitly marking text for conversion.
- **Forced Preedit**: A unique mode that allows mixing Kanchoku-produced Kanji with Kana for subsequent dictionary conversion, enabling flexible input strategies.

## Project History

PSKK started as an attempt to create a "maintenance-free" IME. This is coming from the concern that the Japanese IME has been under-appreciated and under-invested despite the fact people (who would like to type in Japanese) on daily basis. 

The (most of) existing Japanese IMEs rely on the statistical model for its kana-to-kanji conversion. As natural language is a living entity, such statistical models require constant maintenance. This project got started to address this particular issue by shifting both the maintenance effort and control of the IME to each end user. 

In order to achieve this goal, SKK was selected as a starting point, as it does not rely on any statistical model. In order to compete with the existing Japanese IMEs with statistical model, simultaneous typing and SandS and Kanchoku was implemented. Later, the optional statistical model was introduced, but it was intended to be nothing but a supporting mechanism in case an exact kana-to-kanji conversion wasn't found in the dictionary. 



