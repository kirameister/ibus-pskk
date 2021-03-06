# はじめに

　「ひらがな￹IME￺アイエムイー￻」は、かながきの￹部分￺ぶぶん￻のおおくなった￹日本語￺にほんご￻を￹入力￺にゅうりょく￻しやすくした￹日本語￺にほんご￻￹Input Method Engine￺インプット メソッド エンジン￻です。
キーボードでうちこんだひらがなは、そのまな￹本文￺ほんぶん￻に￹挿入￺そうにゅう￻されていきます。
ひらがなの￹入力￺にゅうりょく￻をいちいち❲Enter❳キーで￹確定￺かくてい￻したりする￹必要￺ひつよう￻はありません。

　これまでのIMEでは、￹入力￺にゅうりょく￻したひらがなは、まず￹漢字￺かんじ￻のよみとして￹処理￺しょり￻されていました。
「ひらがなIME」ではそのようなことはありません。
￹漢字￺かんじ￻をつかいたいときは、￹本文￺ほんぶん￻￹中￺ちゅう￻のひらがなをあとからいつでも￹漢字￺かんじ￻におきかえることができます。

　「ひらがなIME」は、Fedora, Ubuntu, Raspberry Pi OSなど、[IBus](https://github.com/ibus/ibus/wiki)に￹対応￺たいおう￻したオペレーティング システム（￹OS￺オーエス￻）で￹利用￺りよう￻できます。

<video controls autoplay muted playsinline>
<source src='screenshot.mp4' type='video/mp4'>
スクリーンショット
</video>

## モードレス￹入力￺にゅうりょく￻￹方式￺ほうしき￻

　「ひらがなIME」のような￹入力￺にゅうりょく￻￹方式￺ほうしき￻は「モードレス￹入力￺にゅうりょく￻￹方式￺ほうしき￻」とよばれています。
￹従来￺じゅうらい￻のIMEにあった「よみの￹入力￺にゅうりょく￻モード」をなくしているためです。
　いまのIMEは、アプリケーション ソフトウェアが￹対応￺たいおう￻してれば、カーソルの￹前後￺ぜんご￻のテキスト（「￹周辺￺しゅうへん￻テキスト」といいます）をしらべることができます。
「ひらがなIME」は、それを￹利用￺りよう￻して、モードレス￹入力￺にゅうりょく￻を￹実現￺じつげん￻しています。
さいきんでは、geditや「[ふりがなパッド](https://github.com/esrille/furiganapad)」のようなテキスト エディターだけでなく、LibreOfficeやFirefoxなどでもモードレス￹入力￺にゅうりょく￻をつかえるようになっています。
　いっぽう、IMEのあたらしい￹機能￺きのう￻に￹対応￺たいおう￻していないソフトもまだまだあります。
そうしたソフトでは、「ひらがなIME」でも、￹従来￺じゅうらい￻のIMEとおなじように「よみの￹入力￺にゅうりょく￻モード」をつかって￹文字￺もじ￻を￹入力￺にゅうりょく￻します。

<hr>
<br><small>Copyright 2017-2021 Esrille Inc. </small>
