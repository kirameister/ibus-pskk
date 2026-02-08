#!/usr/bin/env python3
"""
Aozora Bunko Text Retrieval Script

This script extracts plain text from Aozora Bunko HTML files.
It handles ruby annotations by keeping only the base text (<rb>),
ignoring readings (<rt>) and parentheses (<rp>).

Usage:
    python aozora_bunko_retrieval.py https://www.aozora.gr.jp/cards/000148/files/789_14547.html
    python aozora_bunko_retrieval.py /path/to/local/789_14547.html

Output:
    Creates a text file named after the input HTML file (e.g., 789_14547.txt)
    in the same directory as this script.
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
    """Fetch HTML content from URL or local file.

    Args:
        source: URL or local file path

    Returns:
        HTML content as string
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
    """Recursively extract text from an element, handling ruby tags specially.

    Args:
        element: BeautifulSoup element

    Returns:
        Extracted text
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
    """Extract main text from Aozora Bunko HTML.

    Args:
        html_content: HTML content as string

    Returns:
        Extracted plain text
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
    """Generate output filename from source URL or path.

    Args:
        source: URL or local file path

    Returns:
        Output filename (e.g., "789_14547.txt")
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
        help='Output file path (default: <filename>.txt in the same directory as this script)'
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
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_filename = get_output_filename(args.source)
        output_path = os.path.join(script_dir, output_filename)

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
