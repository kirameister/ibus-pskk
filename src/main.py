"""
main.py - Entry point for the PSKK IME engine
PSKK IMEエンジンのエントリーポイント

================================================================================
WHAT THIS FILE DOES / このファイルの役割
================================================================================

This is the STARTING POINT of the PSKK input method engine. When you select
PSKK as your input method, THIS is the program that runs.

これはPSKK入力メソッドエンジンの起動点。PSKKを入力メソッドとして選択すると、
このプログラムが実行される。

    User selects PSKK in system settings
    ユーザーがシステム設定でPSKKを選択
            ↓
    IBus daemon starts this script
    IBusデーモンがこのスクリプトを起動
            ↓
    This script registers the PSKK engine with IBus
    このスクリプトがPSKKエンジンをIBusに登録
            ↓
    Engine handles all keyboard input
    エンジンが全てのキーボード入力を処理

================================================================================
WHAT IS IBUS? / IBusとは？
================================================================================

IBus (Intelligent Input Bus) is the standard input method framework for
Linux desktop environments. Think of it as a "middleman" between:

IBus（Intelligent Input Bus）はLinuxデスクトップ環境の標準入力メソッド
フレームワーク。以下の間の「仲介者」と考えられる:

    ┌──────────────┐         ┌──────────┐         ┌─────────────────┐
    │   Keyboard   │ ──────► │   IBus   │ ──────► │  Applications   │
    │  キーボード   │         │  Daemon  │         │  アプリケーション │
    └──────────────┘         └────┬─────┘         └─────────────────┘
                                  │
                                  ▼
                           ┌────────────┐
                           │ PSKK Engine │  ← THIS is what we register
                           │ (engine.py) │    これが登録するもの
                           └────────────┘

IBus allows multiple input methods to coexist and be switched easily.
IBusは複数の入力メソッドの共存と簡単な切り替えを可能にする。

================================================================================
TWO EXECUTION MODES / 2つの実行モード
================================================================================

1. NORMAL MODE (--ibus flag) / 通常モード（--ibusフラグ）
   ─────────────────────────────────────────────────────────
   Started by IBus daemon automatically when user selects PSKK.
   ユーザーがPSKKを選択した時にIBusデーモンが自動的に起動。

   This is the NORMAL way the engine runs.
   これがエンジンの通常の実行方法。

2. STANDALONE MODE (no flags) / スタンドアロンモード（フラグなし）
   ──────────────────────────────────────────────────────────
   For TESTING/DEVELOPMENT - runs independently of IBus daemon.
   テスト/開発用 - IBusデーモンとは独立して実行。

   Useful for debugging without restarting IBus.
   IBusを再起動せずにデバッグするのに便利。

================================================================================
FILE RELATIONSHIPS / ファイルの関係
================================================================================

    main.py (THIS FILE)          ← Entry point, IBus registration
    このファイル                    エントリーポイント、IBus登録
        │
        └──► engine.py           ← The actual IME logic
             (EnginePSKK class)    実際のIMEロジック
                  │
                  ├──► henkan.py           (kana-kanji conversion)
                  ├──► kanchoku.py         (direct kanji input)
                  ├──► simultaneous_processor.py  (key combination detection)
                  └──► util.py             (configuration, utilities)

================================================================================
FOR NEWCOMERS / 初心者向け
================================================================================

If you're new to this project, here's the recommended reading order:
このプロジェクトが初めてなら、以下の順番で読むことを推奨:

1. This file (main.py) - Understand how the engine starts
   このファイル - エンジンの起動方法を理解

2. engine.py - The core IME logic (most important!)
   engine.py - コアIMEロジック（最重要！）

3. util.py - Configuration and helper functions
   util.py - 設定とヘルパー関数

4. henkan.py - Kana-to-kanji conversion
   henkan.py - かな漢字変換

================================================================================
"""

from engine import EnginePSKK
import util

import argparse
import getopt
import gettext
import os
import locale
import logging
import sys
from shutil import copyfile

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, GObject, IBus, Gtk


_ = lambda a : gettext.dgettext(util.get_package_name(), a)


class IMApp:
    """
    IBus Application Wrapper - Manages the connection between PSKK and IBus.
    IBusアプリケーションラッパー - PSKKとIBus間の接続を管理。

    ============================================================================
    WHAT THIS CLASS DOES / このクラスの役割
    ============================================================================

    This class is the "glue" that connects our PSKK engine to the IBus system.
    It handles:
    このクラスはPSKKエンジンとIBusシステムを繋ぐ「接着剤」。以下を担当:

        1. Connecting to the IBus daemon (the system's input method manager)
           IBusデーモン（システムの入力メソッドマネージャ）への接続

        2. Registering our engine so IBus knows PSKK exists
           エンジンの登録（IBusがPSKKの存在を認識できるように）

        3. Running the main event loop (waiting for keyboard input)
           メインイベントループの実行（キーボード入力を待機）

    ============================================================================
    HOW IBUS REGISTRATION WORKS / IBus登録の仕組み
    ============================================================================

    When IBus starts our engine, the following happens:
    IBusがエンジンを起動すると、以下が発生:

        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. Create IBus.Bus() - Connect to the IBus daemon                  │
        │     IBus.Bus()を作成 - IBusデーモンに接続                             │
        │                              ↓                                      │
        │  2. Create IBus.Factory() - Factory creates engine instances        │
        │     IBus.Factory()を作成 - ファクトリがエンジンインスタンスを作成      │
        │                              ↓                                      │
        │  3. factory.add_engine("pskk", EnginePSKK)                          │
        │     Tell factory: "when asked for 'pskk', create EnginePSKK"        │
        │     ファクトリに指示:「'pskk'を要求されたらEnginePSKKを作成」          │
        │                              ↓                                      │
        │  4. bus.request_name() - Claim our D-Bus name                       │
        │     bus.request_name() - D-Bus名を取得                               │
        │                              ↓                                      │
        │  5. mainloop.run() - Wait for events (keystrokes, etc.)             │
        │     mainloop.run() - イベント（キー入力など）を待機                    │
        └─────────────────────────────────────────────────────────────────────┘

    ============================================================================
    TWO MODES EXPLAINED / 2つのモードの説明
    ============================================================================

    exec_by_ibus=True (Normal Operation):
    exec_by_ibus=True（通常動作）:
        - IBus daemon starts us, so we just request our D-Bus name
        - IBusデーモンが起動するので、D-Bus名を要求するだけ
        - Simpler setup, IBus already knows about us
        - より単純な設定、IBusは既に我々を認識している

    exec_by_ibus=False (Standalone/Development):
    exec_by_ibus=False（スタンドアロン/開発用）:
        - We're running independently, so we must register ourselves
        - 独立して実行しているため、自分自身を登録する必要がある
        - Creates IBus.Component and IBus.EngineDesc manually
        - IBus.ComponentとIBus.EngineDescを手動で作成
        - Useful for testing without restarting the IBus daemon
        - IBusデーモンを再起動せずにテストするのに便利

    ============================================================================
    ATTRIBUTES / 属性
    ============================================================================

    exec_by_ibus : bool
        True if started by IBus daemon, False if running standalone.
        IBusデーモンによる起動ならTrue、スタンドアロン実行ならFalse。

    _mainloop : GLib.MainLoop
        The GTK main event loop that keeps the application running.
        アプリケーションを実行し続けるGTKメインイベントループ。

    _bus : IBus.Bus
        Connection to the IBus daemon via D-Bus.
        D-Bus経由でのIBusデーモンへの接続。

    _factory : IBus.Factory
        Factory that creates EnginePSKK instances when requested.
        要求時にEnginePSKKインスタンスを作成するファクトリ。

    _component : IBus.Component (standalone mode only)
        Component descriptor for self-registration.
        自己登録用のコンポーネント記述子（スタンドアロンモードのみ）。

    ============================================================================
    """

    def __init__(self, exec_by_ibus: bool) -> None:
        """
        Initialize the IBus application and register the PSKK engine.
        IBusアプリケーションを初期化し、PSKKエンジンを登録。

        This constructor:
        このコンストラクタは:
            1. Initializes GTK (required for IBus GUI integration)
               GTKを初期化（IBus GUI統合に必要）
            2. Creates the main event loop
               メインイベントループを作成
            3. Connects to the IBus daemon
               IBusデーモンに接続
            4. Registers the PSKK engine factory
               PSKKエンジンファクトリを登録
            5. Either requests D-Bus name (IBus mode) or self-registers (standalone)
               D-Bus名を要求（IBusモード）または自己登録（スタンドアロン）

        Args:
            exec_by_ibus (bool): True if started by IBus daemon, False for standalone.
                                 IBusデーモンによる起動ならTrue、スタンドアロンならFalse。

        Raises:
            TypeError: If exec_by_ibus is not a boolean.
                       exec_by_ibusがブール値でない場合。
        """
        if not isinstance(exec_by_ibus, bool):
            raise TypeError("The `exec_by_ibus` parameter must be a boolean value.")
        self.exec_by_ibus = exec_by_ibus

        # Initialize GTK (this is important for --ibus mode)
        Gtk.init(None)

        self._mainloop = GLib.MainLoop()
        self._bus = IBus.Bus()
        # http://lazka.github.io/pgi-docs/GObject-2.0/classes/Object.html#GObject.Object.connect
        self._bus.connect("disconnected", self._bus_disconnected_cb)
        self._factory = IBus.Factory(self._bus)
        self._factory.add_engine("pskk", GObject.type_from_name("EnginePSKK"))
        if exec_by_ibus:
            # http://lazka.github.io/pgi-docs/IBus-1.0/classes/Bus.html#IBus.Bus.request_name
            self._bus.request_name("org.freedesktop.IBus.PSKK", 0)
        else:
            self._component = IBus.Component(
                name="org.freedesktop.IBus.PSKK",
                description="PSKK",
                version=util.get_version(),
                license="MIT",
                author="Akira K.",
                homepage="https://github.com/kirameister/" + util.get_package_name(),
                textdomain=util.get_package_name())
            engine = IBus.EngineDesc(
                name="pskk",
                longname="PSKK",
                description="PSKK",
                language="ja",
                license="MIT",
                author="Akira K.",
                icon=util.get_package_name(),
                layout="default")
            # http://lazka.github.io/pgi-docs/IBus-1.0/classes/Component.html#IBus.Component.add_engine
            self._component.add_engine(engine)
            # http://lazka.github.io/pgi-docs/IBus-1.0/classes/Bus.html#IBus.Bus.register_component
            self._bus.register_component(self._component)
            # http://lazka.github.io/pgi-docs/IBus-1.0/classes/Bus.html#IBus.Bus.set_global_engine_async
            self._bus.set_global_engine_async("pskk", -1, None, None, None)

    def run(self):
        """
        Start the main event loop and begin processing input.
        メインイベントループを開始し、入力処理を開始。

        This method blocks until the IBus daemon disconnects or the application
        is otherwise terminated. All keyboard events are processed within this loop.

        このメソッドはIBusデーモンが切断されるか、アプリケーションが終了するまで
        ブロックする。全てのキーボードイベントはこのループ内で処理される。
        """
        self._mainloop.run()

    def _bus_disconnected_cb(self, bus=None):
        """
        Callback: Handle IBus daemon disconnection.
        コールバック: IBusデーモン切断を処理。

        Called when the IBus daemon disconnects (e.g., IBus restart, logout).
        Cleanly exits the main loop to allow graceful shutdown.

        IBusデーモンが切断された時に呼ばれる（例: IBus再起動、ログアウト）。
        正常なシャットダウンのためにメインループを終了する。

        Args:
            bus: The IBus.Bus instance (provided by signal, may be None).
                 IBus.Busインスタンス（シグナルから提供、Noneの場合あり）。
        """
        self._mainloop.quit()


def print_help(v: int = 0) -> None:
    """
    Print command-line usage help and exit.
    コマンドライン使用方法のヘルプを表示して終了。

    Args:
        v (int): Exit code. 0 for normal help request, 1 for error.
                 終了コード。通常のヘルプ要求は0、エラーは1。
    """
    print("-i, --ibus             executed by IBus.")
    print("-h, --help             show this message.")
    print("-d, --daemonize        daemonize ibus")
    sys.exit(v)


def main():
    """
    Main entry point - Initialize environment and start the PSKK engine.
    メインエントリーポイント - 環境を初期化し、PSKKエンジンを起動。

    ============================================================================
    STARTUP SEQUENCE / 起動シーケンス
    ============================================================================

    This function performs the following steps:
    この関数は以下のステップを実行:

        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. SECURITY: Set umask to 077 (files readable only by owner)       │
        │     セキュリティ: umaskを077に設定（ファイルは所有者のみ読み取り可）   │
        │                              ↓                                      │
        │  2. CONFIG DIRECTORY: Create ~/.config/ibus-pskk/ if needed         │
        │     設定ディレクトリ: ~/.config/ibus-pskk/を必要に応じて作成          │
        │                              ↓                                      │
        │  3. CONFIG FILE: Copy default config.json if user doesn't have one  │
        │     設定ファイル: ユーザーにない場合はデフォルトconfig.jsonをコピー    │
        │                              ↓                                      │
        │  4. LOGGING: Set up logging to ~/.config/ibus-pskk/ibus-pskk.log    │
        │     ログ設定: ~/.config/ibus-pskk/ibus-pskk.logにログを設定          │
        │                              ↓                                      │
        │  5. PARSE ARGS: Handle --ibus, --daemonize, --help flags            │
        │     引数解析: --ibus, --daemonize, --helpフラグを処理                │
        │                              ↓                                      │
        │  6. DAEMONIZE: Fork to background if --daemonize was specified      │
        │     デーモン化: --daemonize指定時にバックグラウンドにフォーク          │
        │                              ↓                                      │
        │  7. RUN: Create IMApp and start the main loop                       │
        │     実行: IMAppを作成しメインループを開始                             │
        └─────────────────────────────────────────────────────────────────────┘

    ============================================================================
    COMMAND LINE OPTIONS / コマンドラインオプション
    ============================================================================

    -i, --ibus       : Started by IBus daemon (normal operation)
                       IBusデーモンによる起動（通常動作）

    -d, --daemonize  : Fork to background (for manual startup)
                       バックグラウンドにフォーク（手動起動用）

    -h, --help       : Show help message and exit
                       ヘルプメッセージを表示して終了

    ============================================================================
    USER DATA LOCATIONS / ユーザーデータの場所
    ============================================================================

    All user-specific data is stored in: ~/.config/ibus-pskk/
    全てのユーザー固有データは以下に保存: ~/.config/ibus-pskk/

        config.json     - User settings (key bindings, modes, etc.)
                          ユーザー設定（キーバインド、モードなど）

        ibus-pskk.log   - Debug log file (useful for troubleshooting)
                          デバッグログファイル（トラブルシューティングに有用）

        user_dict/      - User's personal dictionary entries
                          ユーザーの個人辞書エントリ

    ============================================================================
    """
    os.umask(0o077)

    # Create user specific data directory
    user_configdir = util.get_user_config_dir()
    os.makedirs(user_configdir, 0o700, True)
    os.chmod(user_configdir, 0o700)   # For logfile created by v0.2.0 or earlier

    # check the config file and copy it from installed directory if it does not exist
    configfile_name = os.path.join(user_configdir, 'config.json')
    if not os.path.exists(configfile_name):
        copyfile(os.path.join(util.get_datadir(), 'config.json'), configfile_name)

    # logging settings
    logfile_name = os.path.join(user_configdir, util.get_package_name() + '.log')
    # it's intentionally set to DEBUG during the development. This value should be replaced by WARNING when the product is mature enough
    logging.basicConfig(filename=logfile_name, level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger()
    logger.info(f'engine/main.py user_configdir: {user_configdir}')
    logger.info(f'engine/main.py util.get_package_name(): {util.get_package_name()}')
    logger.info(f'engine/main.py util.get_datadir(): {util.get_datadir()}')

    exec_by_ibus = False
    daemonize = False

    shortopt = "ihd"
    longopt = ["ibus", "help", "daemonize"]

    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopt, longopt)
    except getopt.GetoptError as err:
        logger.error(err)
        # print_help(1)
        sys.exit(1)

    # this is still required as argparse is having problem with IBus
    for o, a in opts:
        if o in ("-h", "--help"):
            print_help(0)
        elif o in ("-d", "--daemonize"):
            daemonize = True
        elif o in ("-i", "--ibus"):
            exec_by_ibus = True
        else:
            sys.stderr.write("Unknown argument: %s\n" % o)
            print_help(1)
    logger.info(f'daemonize? : {daemonize}')
    logger.info(f'IBus exec? : {exec_by_ibus}')

    if daemonize:
        if os.fork():
            sys.exit()
    IMApp(exec_by_ibus).run()


if __name__ == "__main__":
    try:
        locale.bindtextdomain(util.get_package_name(), util.get_localedir())
    except Exception:
        pass
    gettext.bindtextdomain(util.get_package_name(), util.get_localedir())
    main()
