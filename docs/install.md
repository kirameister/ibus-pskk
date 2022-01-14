# インストール￹方法￺ほうほう￻

## ソフトウェア パッケージのインストール

　つかっているOSが、Fedora, Ubuntu, Raspberry Pi OSのどれかであれば、インストール￹用￺よう￻のソフトウェア パッケージを「[Releases](https://github.com/esrille/ibus-hiragana/releases)」ページからダウンロードできます。
　ダウンロードができたら、「Releases」ページの￹記載￺きさい￻にしたがって、パッケージをインストールしてください。
また、インストールが完了したら、いちどコンピューターを再起動してください。

### Waylandを￹使用￺しよう￻するばあい

　Ubuntu 21.04￹以降￺いこう￻やFedora 25￹以降￺いこう￻では、デフォルトで￹画面￺がめん￻の￹描画￺びょうが￻にWaylandをつかうようになっています。
Waylandは、ながくつかわれてきたXサーバーをおきかえるものです。
Waylandはまだまだあたらしく、きちんと￹対応￺たいおう￻できていないソフトウェアものこっています。
　IBusをWaylandで使用するばあいは、￹環境￺かんきょう￻￹変数￺へんすう￻GTK_IM_MODULEにibusを￹指定￺してい￻してください。
そうしないと、ただしい￹周辺￺しゅうへん￻テキストの￹情報￺じょうほう￻がIBusからIMEにおくられてきません。
そのためには、つぎの行を ~/.bash_profile (Fedoraなど)か ~/.profile (Ubuntuなど)に追加してください。

```
export GTK_IM_MODULE=ibus
```

### ￹参考￺さんこう￻: じぶんでビルドしたいばあい

　「ひらがなIME」をじぶんでビルドしてインストールしたいときは、つぎの￹手順￺てじゅん￻でできます。

```
git clone https://github.com/esrille/ibus-hiragana.git
./autogen.sh
make
sudo make install
```

## ￹入力￺にゅうりょく￻￹環境￺かんきょう￻のセットアップ

　パッケージのインストールができたら、￹入力￺にゅうりょく￻￹環境￺かんきょう￻に「ひらがなIME」をセットアップしていきます。
￹入力￺にゅうりょく￻￹環境￺かんきょう￻のセットアップ￹方法￺ほうほう￻は、デスクトップ￹環境￺かんきょう￻によってすこし￹異￺こと￻なります。

### GNOMEのばあい

　FedoraやUbuntuでは、GNOMEが￹標準￺ひょうじゅん￻のデスクトップ￹環境￺かんきょう￻になっています。GNOMEでは、「￹設定￺せってい￻」をひらいて、「￹地域￺ちいき￻と￹言語￺げんご￻」もしくは「キーボード」の「￹入力￺にゅうりょく￻ソース」に、
<br><br>
　　￹日本語￺にほんご￻(Hiragana IME)
<br><br>
を￹追加￺ついか￻します。

### GNOME￹以外￺いがい￻のばあい

　「IBusの￹設定￺せってい￻」ウィンドウをひらいて、「￹入力￺にゅうりょく￻メソッド」タブの「￹入力￺にゅうりょく￻メソッド」に、
<br><br>
　　![アイコン](icon.png) ￹日本語￺にほんご￻ - Hiragana IME
<br><br>
を￹追加￺ついか￻します。

## 「ひらがなIME」を￹有効￺ゆうこう￻にする

　IBusでは、￹複数￺ふくすう￻のインプットメソッドエンジンをつかうことができるようになっています。
　「ひらがなIME」を￹有効￺ゆうこう￻するには、トップバーの￹現在￺げんざい￻の￹入力￺にゅうりょく￻メソッドを￹表示￺ひょうじ￻している￹部分￺ぶぶん￻（「<nobr>ja ▼</nobr>」、「<nobr>en ▼</nobr>」など）をクリックして、
<br><br>
　　￹日本語￺にほんご￻(Hiragana IME)
<br><br>
をえらびます。
　「ひらがなIME」の￹基本的￺きほんてき￻なセットアップはこれで￹完了￺かんりょう￻です。
さらにこまかな￹設定￺せってい￻は、「[ひらがなIMEの￹設定￺せってい￻](settings.html)」ウィンドウでおこなえます。