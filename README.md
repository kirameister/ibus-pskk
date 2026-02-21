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

1. Run the following commands in the terminal -- ターミナルにて以下のコマンドを入力する:
```
  sudo apt install just python3-venv pip curl git
  git clone https://github.com/kirameister/ibus-pskk.git
  cd ibus-pskk
  sudo just install
```

2. (In case you've installed non-Japanese languages) Under the `settings`, select `Regino & Languages`, and select `Manage installed languages`. In the popup, click `Install/Remove Languages` button, and install "Japanese". After installation, you'd need to restart the machine. 

3. Under the `settings`, select `keyboard`, and click "Add Input Source". In the dialog, select "Japanese" and "Japanese (PSKK)".  -- `設定` にて `キーボード` を選択し、`入力ソースを追加` をクリックする。ダイアログにて「日本語」を選択し、「日本語 (PSKK)」を選択する。

4. Restart the machine. -- コンピューターを再起動する。

Notes:
* CRF のモデルをトレーニングすることもできますが、その場合、Mecab をインストールする必要があります。
* (デフォルトの) CRF モデルはインストール時にインスストールされます。
* インストール時には辞書を `$HOME` 以下に生成する必要があります。IBus のメニューから `Settings...` を開き、`System Dictionary` と `User Dictionary` のタブから辞書を生成してください。
