# PSKK

IME, the final frontier. 

`PSKK` stands for `Personaliz(ed|able) SKK` and is meant/aimed to provide an easy, but effective, implementation of IME, which is highly configuable. 

## Features of `PSKK`

* No statistical model, or training model for predicting the Kanji -- instead, it is heavily reliant upon the dictionary contents. 
* Highly customizable -- `PSKK` has SandS feature, which should be considered more like `XandY` features. 


## Requirement and installation

### Arch Linux:
```
  sudo pacman -S python python-pip ibus gtk3 glib2 python-gobject
```

### Debian/Ubuntu:
```
  sudo apt install python3 python3-pip python3-venv ibus libgtk-3-0 python3-gi gir1.2-ibus-1.0 libglib2.0-dev libgtk-3-dev
```

### Fedora:
```
  sudo dnf install python3 python3-pip ibus gtk3 glib2-devel python3-gobject gtk3-devel
```

