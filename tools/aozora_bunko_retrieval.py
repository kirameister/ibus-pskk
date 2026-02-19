#!/usr/bin/env python3
"""
aozora_bunko_retrieval.py - Extract plain text from Aozora Bunko HTML files
青空文庫HTMLファイルからプレーンテキストを抽出

================================================================================
WHAT IS AOZORA BUNKO? / 青空文庫とは？
================================================================================

Aozora Bunko (青空文庫, "Blue Sky Library") is a Japanese digital library
that hosts literary works whose copyrights have expired in Japan. Think of
it as "Project Gutenberg for Japanese literature."

青空文庫は、日本で著作権が消滅した文学作品をホストする日本のデジタル
ライブラリ。「日本文学版プロジェクト・グーテンベルク」と考えてよい。

Website / ウェブサイト: https://www.aozora.gr.jp/

Contents include / 収録内容:
• Classic Japanese literature (Natsume Soseki, Akutagawa Ryunosuke, etc.)
  日本の古典文学（夏目漱石、芥川龍之介など）
• Over 17,000 works freely available / 17,000作品以上が無料で利用可能
• High-quality digitized texts / 高品質にデジタル化されたテキスト

================================================================================
WHY THIS SCRIPT? / このスクリプトの目的
================================================================================

PURPOSE / 目的:
────────────────
This script extracts CLEAN PLAIN TEXT from Aozora Bunko HTML pages.
The extracted text can be used for:

このスクリプトは青空文庫のHTMLページからクリーンなプレーンテキストを抽出。
抽出されたテキストは以下に使用できる:

1. TRAINING DATA for Japanese NLP models (CRF, neural networks, etc.)
   日本語NLPモデルの訓練データ（CRF、ニューラルネットワークなど）

2. TESTING IME conversion accuracy on real literary text
   実際の文学テキストでIME変換精度をテスト

3. BUILDING DICTIONARIES from natural Japanese text
   自然な日本語テキストから辞書を構築

4. LINGUISTIC RESEARCH and analysis
   言語学的研究と分析

PROBLEM THIS SOLVES / 解決する問題:
────────────────────────────────────
Aozora Bunko HTML files contain complex markup that makes direct text
extraction difficult:

青空文庫のHTMLファイルには複雑なマークアップがあり、直接テキスト抽出が困難:

    Original HTML / 元のHTML:
    ─────────────────────────
    <ruby><rb>吾輩</rb><rp>（</rp><rt>わがはい</rt><rp>）</rp></ruby>は猫である

    What we want / 欲しいもの:
    ───────────────────────────
    吾輩は猫である

    What we DON'T want / 欲しくないもの:
    ────────────────────────────────────
    吾輩（わがはい）は猫である  ← Reading annotations mixed in!
                                  読み仮名が混在！

================================================================================
WHAT ARE RUBY ANNOTATIONS? / ルビ注釈とは？
================================================================================

In Japanese text, RUBY (ルビ) refers to small reading aids placed above
(or beside) kanji characters. In HTML, this uses the <ruby> tag:

日本語テキストでは、ルビは漢字の上（または横）に配置される小さな読み補助。
HTMLでは <ruby> タグを使用:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                     わがはい                                         │
    │                       ↓                                              │
    │   Visual:           吾輩                                             │
    │                                                                      │
    │   HTML structure:                                                    │
    │   <ruby>                                                             │
    │       <rb>吾輩</rb>        ← Base text (what we keep)               │
    │       <rp>（</rp>          ← Parenthesis (fallback, we discard)     │
    │       <rt>わがはい</rt>    ← Reading (furigana, we discard)         │
    │       <rp>）</rp>          ← Closing parenthesis (we discard)       │
    │   </ruby>                                                            │
    └─────────────────────────────────────────────────────────────────────┘

WHY DISCARD READINGS? / なぜ読みを破棄？
───────────────────────────────────────
For IME training/testing, we want the TEXT AS USERS WOULD TYPE IT.
Users type readings and convert to kanji - they don't type "吾輩（わがはい）".

IME訓練/テスト用には、ユーザーが入力する通りのテキストが欲しい。
ユーザーは読みを入力して漢字に変換する - 「吾輩（わがはい）」とは入力しない。

================================================================================
STANDALONE SCRIPT / スタンドアロンスクリプト
================================================================================

This script is a STANDALONE UTILITY - it is NOT required for the IME to
function. It's a development tool for obtaining training/testing data.

このスクリプトはスタンドアロンユーティリティ - IMEの動作には不要。
訓練/テストデータを取得するための開発ツール。

DEPENDENCIES / 依存関係:
────────────────────────
• beautifulsoup4 - HTML parsing / HTML解析
• requests - URL fetching (optional, for remote files)
              URL取得（オプション、リモートファイル用）

Install with / インストール:
    pip install beautifulsoup4 requests

================================================================================
USAGE / 使用方法
================================================================================

From URL / URLから:
───────────────────
    python aozora_bunko_retrieval.py \\
        https://www.aozora.gr.jp/cards/000148/files/789_14547.html

    # Downloads "I Am a Cat" by Natsume Soseki
    # 夏目漱石「吾輩は猫である」をダウンロード

From local file / ローカルファイルから:
──────────────────────────────────────
    python aozora_bunko_retrieval.py /path/to/789_14547.html

With custom output / カスタム出力先:
────────────────────────────────────
    python aozora_bunko_retrieval.py input.html -o output.txt

OUTPUT / 出力:
──────────────
Creates a UTF-8 encoded text file with:
UTF-8エンコードのテキストファイルを作成:
• Clean plain text without ruby annotations
  ルビ注釈のないクリーンなプレーンテキスト
• Preserved paragraph breaks
  保持された段落区切り
• Statistics printed to console
  コンソールに統計情報を出力

================================================================================
ENCODING NOTES / エンコーディングに関する注意
================================================================================

Aozora Bunko files historically use SHIFT_JIS encoding (a legacy Japanese
encoding from the 1980s), not UTF-8. This script handles this automatically:

青空文庫ファイルは歴史的にSHIFT_JISエンコーディング（1980年代のレガシー
日本語エンコーディング）を使用し、UTF-8ではない。このスクリプトは自動処理:

• Input: Tries Shift_JIS first, then UTF-8, then EUC-JP
  入力: まずShift_JIS、次にUTF-8、次にEUC-JPを試行
• Output: Always UTF-8 (modern standard)
  出力: 常にUTF-8（現代の標準）

================================================================================
"""

import argparse
import os
import re
import sys
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup, NavigableString
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def fetch_html(source: str) -> str:
    """
    Fetch HTML content from URL or local file.
    URLまたはローカルファイルからHTMLコンテンツを取得

    ─────────────────────────────────────────────────────────────────────────
    INPUT SOURCES / 入力ソース
    ─────────────────────────────────────────────────────────────────────────

    This function accepts two types of input:
    この関数は2種類の入力を受け付ける:

    1. URL (http:// or https://)
       → Uses 'requests' library to download
       → 'requests'ライブラリを使用してダウンロード

    2. Local file path
       → Reads directly from filesystem
       → ファイルシステムから直接読み込み

    ─────────────────────────────────────────────────────────────────────────
    ENCODING HANDLING / エンコーディング処理
    ─────────────────────────────────────────────────────────────────────────

    Japanese text encoding is historically messy. Aozora Bunko files may use:
    日本語テキストのエンコーディングは歴史的に混乱している。青空文庫ファイルは:

    • Shift_JIS (シフトJIS) - Most common for Aozora Bunko
      青空文庫で最も一般的
    • UTF-8 - Modern standard, some newer files
      現代の標準、一部の新しいファイル
    • EUC-JP - Older Unix-based encoding
      古いUnixベースのエンコーディング

    This function tries each encoding in order until one succeeds.
    この関数は成功するまで各エンコーディングを順に試す。

    Args:
        source: URLまたはローカルファイルパス

    Returns:
        HTML content as string (decoded to Python str)
        HTMLコンテンツを文字列として（Pythonのstrにデコード済み）

    Raises:
        ValueError: If file cannot be decoded with any known encoding
                    既知のエンコーディングでファイルをデコードできない場合
    """
    # Check if it's a URL
    parsed = urlparse(source)
    if parsed.scheme in ('http', 'https'):
        if not HAS_REQUESTS:
            print("Error: 'requests' library is required for URL fetching.")
            print("Install with: pip install requests")
            sys.exit(1)

        print(f"Fetching URL: {source}")
        response = requests.get(source)
        response.raise_for_status()
        # Aozora Bunko uses Shift_JIS encoding
        response.encoding = 'shift_jis'
        return response.text
    else:
        # Local file
        print(f"Reading file: {source}")
        # Try Shift_JIS first (Aozora Bunko standard), fallback to UTF-8
        for encoding in ['shift_jis', 'utf-8', 'euc-jp']:
            try:
                with open(source, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode file with any known encoding: {source}")


def extract_text_from_element(element) -> str:
    """
    Recursively extract text from an element, handling ruby tags specially.
    要素からテキストを再帰的に抽出し、rubyタグを特別に処理

    ─────────────────────────────────────────────────────────────────────────
    THE CORE ALGORITHM / コアアルゴリズム
    ─────────────────────────────────────────────────────────────────────────

    This function walks through the HTML tree and extracts text while:
    この関数はHTMLツリーを走査し、以下を行いながらテキストを抽出:

    1. KEEPING plain text nodes / プレーンテキストノードを保持
    2. KEEPING base text from <ruby> tags / <ruby>タグから基本テキストを保持
    3. DISCARDING reading annotations (<rt>) / 読み注釈（<rt>）を破棄
    4. DISCARDING parentheses (<rp>) / 括弧（<rp>）を破棄
    5. PRESERVING line breaks (<br>) / 改行（<br>）を保持
    6. IGNORING <div> contents (metadata, etc.) / <div>内容を無視（メタデータなど）

    ─────────────────────────────────────────────────────────────────────────
    RUBY TAG HANDLING / RUBYタグの処理
    ─────────────────────────────────────────────────────────────────────────

    Ruby tags can appear in two formats:
    Rubyタグは2つの形式で出現する:

    Format 1: With explicit <rb> tag / 明示的な<rb>タグあり
    ───────────────────────────────────────────────────────
        <ruby>
            <rb>漢字</rb>           ← We extract THIS
            <rp>（</rp>
            <rt>かんじ</rt>         ← We skip this
            <rp>）</rp>
        </ruby>

    Format 2: Base text directly in <ruby> / 基本テキストが<ruby>内に直接
    ───────────────────────────────────────────────────────────────────────
        <ruby>
            漢字                    ← We extract THIS (it's a text node)
            <rt>かんじ</rt>         ← We skip this
        </ruby>

    This function handles BOTH formats correctly.
    この関数は両方の形式を正しく処理する。

    Args:
        element: BeautifulSoup element to process
                 処理するBeautifulSoup要素

    Returns:
        Extracted text with readings removed
        読みを削除した抽出テキスト
    """
    result = []

    for child in element.children:
        if isinstance(child, NavigableString):
            # Plain text node
            result.append(str(child))
        elif child.name == 'div':
            # Ignore div tags and their contents
            continue
        elif child.name == 'ruby':
            # For ruby tags, only extract text from <rb> tags
            rb_tag = child.find('rb')
            if rb_tag:
                result.append(rb_tag.get_text())
            else:
                # Some ruby tags don't have explicit <rb>, the base text is direct
                # Get text nodes that are not inside <rt> or <rp>
                for ruby_child in child.children:
                    if isinstance(ruby_child, NavigableString):
                        result.append(str(ruby_child))
                    elif ruby_child.name not in ('rt', 'rp'):
                        result.append(ruby_child.get_text())
        elif child.name in ('rt', 'rp'):
            # Skip ruby reading and parentheses
            continue
        elif child.name == 'br':
            # Preserve line breaks
            result.append('\n')
        elif child.name is not None:
            # Recursively process other tags
            result.append(extract_text_from_element(child))

    return ''.join(result)


def extract_main_text(html_content: str) -> str:
    """
    Extract main text from Aozora Bunko HTML.
    青空文庫HTMLからメインテキストを抽出

    ─────────────────────────────────────────────────────────────────────────
    AOZORA BUNKO HTML STRUCTURE / 青空文庫のHTML構造
    ─────────────────────────────────────────────────────────────────────────

    Aozora Bunko HTML files have a specific structure:
    青空文庫のHTMLファイルには特定の構造がある:

        <html>
          <head>...</head>
          <body>
            <div class="metadata">...</div>     ← Title, author info (skip)
            <div class="main_text">             ← THE ACTUAL STORY (extract)
              <ruby>吾輩<rt>わがはい</rt></ruby>は猫である...
            </div>
            <div class="bibliographical_info">  ← Publishing info (skip)
              ...
            </div>
          </body>
        </html>

    This function finds <div class="main_text"> and extracts only that content.
    この関数は <div class="main_text"> を見つけ、その内容のみを抽出する。

    ─────────────────────────────────────────────────────────────────────────
    FALLBACK SELECTORS / フォールバックセレクタ
    ─────────────────────────────────────────────────────────────────────────

    Some older or alternative formatted files may use different structures.
    This function tries these selectors in order:
    古いまたは別形式のファイルは異なる構造を使用する場合がある。
    この関数は以下のセレクタを順に試す:

    1. <div class="main_text">  ← Standard Aozora format
    2. <div class="main-text">  ← Alternative with hyphen
    3. <body>                   ← Last resort fallback

    ─────────────────────────────────────────────────────────────────────────
    TEXT CLEANUP / テキストクリーンアップ
    ─────────────────────────────────────────────────────────────────────────

    After extraction, the text is cleaned:
    抽出後、テキストはクリーンアップされる:

    • Multiple blank lines → single blank line (paragraph separator)
      複数の空行 → 単一の空行（段落区切り）
    • Trailing whitespace on lines removed
      行末の空白を削除
    • Leading/trailing whitespace from entire text removed
      テキスト全体の先頭/末尾の空白を削除

    Args:
        html_content: HTML content as string
                      HTMLコンテンツ（文字列として）

    Returns:
        Clean plain text ready for processing
        処理可能なクリーンなプレーンテキスト

    Raises:
        ValueError: If main text content cannot be found
                    メインテキストコンテンツが見つからない場合
    """
    if not HAS_BS4:
        print("Error: 'beautifulsoup4' library is required.")
        print("Install with: pip install beautifulsoup4")
        sys.exit(1)

    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the main text div
    main_text_div = soup.find('div', class_='main_text')

    if not main_text_div:
        print("Warning: Could not find <div class='main_text'>. Trying alternative selectors...")
        # Try alternative: some older files might use different structure
        main_text_div = soup.find('div', class_='main-text')
        if not main_text_div:
            # Last resort: try to find the body content
            main_text_div = soup.find('body')
            if not main_text_div:
                raise ValueError("Could not find main text content in HTML")

    # Extract text
    text = extract_text_from_element(main_text_div)

    # Clean up: normalize whitespace but preserve paragraph breaks
    # Replace multiple consecutive newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove trailing whitespace on each line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    # Strip leading/trailing whitespace from entire text
    text = text.strip()

    return text


def get_output_filename(source: str) -> str:
    """
    Generate output filename from source URL or path.
    ソースURLまたはパスから出力ファイル名を生成

    ─────────────────────────────────────────────────────────────────────────
    NAMING CONVENTION / 命名規則
    ─────────────────────────────────────────────────────────────────────────

    Aozora Bunko URLs follow a predictable pattern:
    青空文庫のURLは予測可能なパターンに従う:

        https://www.aozora.gr.jp/cards/000148/files/789_14547.html
                                   └──────┘       └────────────┘
                                   Author ID      Work ID + variant

    We extract the filename and change .html → .txt:
    ファイル名を抽出し、.html → .txt に変更:

        789_14547.html → 789_14547.txt

    This preserves the Aozora work ID for later reference.
    これにより後で参照するための青空文庫作品IDが保持される。

    Args:
        source: URLまたはローカルファイルパス

    Returns:
        Output filename (e.g., "789_14547.txt")
        出力ファイル名（例: "789_14547.txt"）
    """
    # Extract the filename from URL or path
    parsed = urlparse(source)
    if parsed.scheme in ('http', 'https'):
        path = parsed.path
    else:
        path = source

    # Get the base filename
    basename = os.path.basename(path)

    # Replace .html extension with .txt
    if basename.lower().endswith('.html'):
        return basename[:-5] + '.txt'
    elif basename.lower().endswith('.htm'):
        return basename[:-4] + '.txt'
    else:
        return basename + '.txt'


def main():
    parser = argparse.ArgumentParser(
        description='Extract plain text from Aozora Bunko HTML files.'
    )
    parser.add_argument(
        'source',
        help='URL or local path to Aozora Bunko HTML file'
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output file path (default: <filename>.txt in current working directory)'
    )
    args = parser.parse_args()

    # Fetch HTML content
    html_content = fetch_html(args.source)

    # Extract main text
    print("Extracting text...")
    text = extract_main_text(html_content)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Output to current working directory
        output_path = get_output_filename(args.source)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)

    # Count statistics
    char_count = len(text)
    line_count = text.count('\n') + 1

    print(f"Extraction complete:")
    print(f"  Characters: {char_count:,}")
    print(f"  Lines:      {line_count:,}")
    print(f"  Output:     {output_path}")


if __name__ == '__main__':
    main()
