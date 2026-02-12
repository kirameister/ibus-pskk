# PSKK

IME, the final frontier.

IME、それは最後のフロンティア。

`PSKK` stands for `Personaliz(ed|able) SKK` and is meant/aimed to provide an easy, but effective, implementation of IME, which is highly configurable.

`PSKK`は「`Personaliz(ed|able) SKK`」の略で、簡単かつ効果的で、高度にカスタマイズ可能なIMEの実装を目指しています。

## Features of `PSKK` / PSKKの特徴

* Dictionary-driven conversion with optional CRF-based bunsetsu prediction for multi-phrase input.
* Highly customizable -- `PSKK` has SandS feature。
* 漢直 -- Support for Kanchoku (漢直), also as part of the input to Kana-to-Kanji conversion

* 辞書ベースの変換機能に加え、複数文節入力のためのCRFベースの文節予測機能をオプションで搭載。
* 高度にカスタマイズ可能 -- SandS機能を搭載。
* 漢直 -- (漢字変換の入力の一部としても) 漢直をサポート。


## Requirement and Installation / 必要なパッケージとインストール

Install the following system packages before running `just install`:

`just install`を実行する前に、以下のシステムパッケージをインストールしてください：

### Debian/Ubuntu:

1. Run the following commands in the terminal:
```
  sudo apt install just python3-venv pip curl
  git clone https://github.com/kirameister/ibus-pskk.git
  cd ibus-pskk
  sudo just install
```

2. Under the `settings`, select `keyboard, and click "Add Input Source". In the dialog, select "Japanese" and "Japanese (PSKK)". 

3. Restart the machine.




### Fedora:
```
  sudo dnf install python3 python3-pip ibus gtk3 glib2-devel python3-gobject gtk3-devel
```

Third-party components
======================

This product includes UniDic.

UniDic is a Japanese morphological dictionary developed by
the National Institute for Japanese Language and Linguistics (NINJAL).

Copyright (c) National Institute for Japanese Language and Linguistics (NINJAL)

UniDic is distributed under a triple license:
  • BSD License
  • GNU General Public License v2
  • GNU Lesser General Public License v2.1

This product uses UniDic under the terms of the BSD License.

