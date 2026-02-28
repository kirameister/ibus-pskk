#!/usr/bin/env python3
"""
crf_train_cli.py - Command-line interface for CRF bunsetsu segmentation training
CRF文節セグメンテーション訓練のコマンドラインインターフェース

================================================================================
OVERVIEW / 概要
================================================================================

This CLI tool provides command-line access to CRF model training and testing,
designed for power users who want to:

このCLIツールは、以下を望むパワーユーザー向けにCRFモデルの訓練と
テストへのコマンドラインアクセスを提供:

    1. Automate training in scripts/pipelines
       スクリプト/パイプラインで訓練を自動化
    2. Train models on headless servers
       ヘッドレスサーバーでモデルを訓練
    3. Batch test model predictions
       モデル予測をバッチテスト
    4. Integrate with other tools
       他のツールと統合

================================================================================
USAGE / 使用方法
================================================================================

    # Full training pipeline (load → extract → train)
    # 完全訓練パイプライン（読み込み → 抽出 → 訓練）
    python crf_train_cli.py train corpus.txt

    # Full training with custom output path
    # カスタム出力パスで完全訓練
    python crf_train_cli.py train corpus.txt --output model.crfsuite

    # Test prediction on text
    # テキストで予測テスト
    python crf_train_cli.py test "きょうはてんきがよい"

    # Test with N-best results
    # N-best結果でテスト
    python crf_train_cli.py test "きょうはてんきがよい" --nbest 10

    # Extract features only (for debugging)
    # 特徴量のみ抽出（デバッグ用）
    python crf_train_cli.py extract corpus.txt --output features.tsv

    # Show corpus statistics
    # コーパス統計を表示
    python crf_train_cli.py stats corpus.txt

================================================================================
"""

import argparse
import sys
import os
import logging

# Add src directory to path if needed
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import crf_core
import util


class ProgressCounter:
    """
    Simple progress counter with in-place terminal updates.
    ターミナルのインプレース更新によるシンプルな進捗カウンター。

    Usage:
        progress = ProgressCounter("Extracting features", total=1000)
        for i in range(1000):
            do_work()
            progress.update(i + 1)
        progress.finish()
    """

    def __init__(self, label, total=None, update_interval=100):
        """
        Initialize progress counter.

        Args:
            label: Description of the operation (e.g., "Extracting features")
            total: Total count (if known)
            update_interval: How often to update display (every N items)
        """
        self.label = label
        self.total = total
        self.update_interval = update_interval
        self.current = 0
        self._last_line_length = 0

    def update(self, current):
        """Update progress display."""
        self.current = current

        # Only update at intervals to avoid excessive I/O
        if current % self.update_interval != 0 and current != self.total:
            return

        if self.total:
            percent = current * 100 // self.total
            line = f"\r  {self.label}: {current:,}/{self.total:,} ({percent}%)"
        else:
            line = f"\r  {self.label}: {current:,}"

        # Clear previous line if it was longer
        padding = ' ' * max(0, self._last_line_length - len(line))
        print(line + padding, end='', flush=True)
        self._last_line_length = len(line)

    def finish(self, message=None):
        """Complete progress and move to new line."""
        if message:
            padding = ' ' * max(0, self._last_line_length - len(message) - 2)
            print(f"\r  {message}{padding}")
        else:
            print()  # Just move to new line


def setup_logging(verbose=False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%H:%M:%S'
    )


def progress_callback(message):
    """Print progress messages to stdout."""
    print(message)


def cmd_train(args):
    """
    Train a CRF model.
    CRFモデルを訓練。

    Supports three modes:
    3つのモードをサポート:
        1. No arguments: train from default TSV (~/.config/ibus-pskk/crf_model_training_data.tsv)
           引数なし: デフォルトTSVから訓練
        2. From corpus (one-shot): load → extract → train
           コーパスから（ワンショット）: 読み込み → 抽出 → 訓練
        3. From features (--features): load custom TSV → train
           特徴量から（--features）: カスタムTSVを読み込み → 訓練
    """
    if not crf_core.HAS_CRFSUITE:
        print("ERROR: pycrfsuite not installed. Install with: pip install python-crfsuite")
        return 1

    output_path = args.output

    print("=" * 60)
    print("CRF Bunsetsu Segmentation Training")
    print("=" * 60)
    print()

    # Determine training mode
    if args.features:
        # Explicit --features option: train from specified TSV
        features_path = args.features
    elif args.corpus:
        # Corpus provided: one-shot mode (extract + train)
        corpus_paths = args.corpus

        # Validate all files exist
        for path in corpus_paths:
            if not os.path.exists(path):
                print(f"ERROR: Corpus file not found: {path}")
                return 1

        if len(corpus_paths) == 1:
            print(f"Training from corpus (one-shot): {corpus_paths[0]}")
        else:
            print(f"Training from {len(corpus_paths)} corpus files (one-shot):")
            for path in corpus_paths:
                print(f"  - {path}")
        print()

        # Step 0: Regenerate dictionary features
        print("Regenerating dictionary features (crf_feature_materials.json)...")
        materials_path = util.generate_crf_feature_materials()
        if materials_path:
            print(f"Dictionary features updated: {materials_path}")
        else:
            print("Warning: Failed to regenerate dictionary features, using existing file")
        print()

        # Step 1: Load corpus file(s)
        all_sentences = []
        combined_stats = {
            'line_count': 0,
            'sentence_count': 0,
            'total_tokens': 0,
            'total_bunsetsu': 0,
            'lookup_bunsetsu': 0,
            'passthrough_bunsetsu': 0,
        }

        for corpus_path in corpus_paths:
            print(f"Loading corpus: {corpus_path}")
            sentences, stats = crf_core.load_corpus(corpus_path)
            all_sentences.extend(sentences)

            combined_stats['line_count'] += stats['line_count']
            combined_stats['sentence_count'] += stats['sentence_count']
            combined_stats['total_tokens'] += stats['total_tokens']
            combined_stats['total_bunsetsu'] += stats['total_bunsetsu']
            combined_stats['lookup_bunsetsu'] += stats['lookup_bunsetsu']
            combined_stats['passthrough_bunsetsu'] += stats['passthrough_bunsetsu']

            print(f"  Loaded {stats['sentence_count']:,} sentences, {stats['total_tokens']:,} tokens")

        if len(corpus_paths) > 1:
            print()
            print(f"Combined: {combined_stats['sentence_count']:,} sentences, {combined_stats['total_tokens']:,} tokens")

        # Step 1b: Load extended dictionary entries
        dict_sentences, dict_stats = crf_core.load_extended_dictionary_as_training_data()
        if dict_stats['dict_entries'] > 0:
            all_sentences.extend(dict_sentences)
            combined_stats['dict_entries'] = dict_stats['dict_entries']
            combined_stats['dict_tokens'] = dict_stats['total_tokens']
            combined_stats['sentence_count'] += dict_stats['dict_entries']
            combined_stats['total_tokens'] += dict_stats['total_tokens']
            combined_stats['total_bunsetsu'] += dict_stats['dict_entries']
            combined_stats['lookup_bunsetsu'] += dict_stats['dict_entries']
            print(f"Added {dict_stats['dict_entries']:,} dictionary entries as training data")

        print()

        # Step 2: Extract features
        print("Extracting features...")
        feature_progress = ProgressCounter("Extracting", update_interval=100)

        def feature_progress_callback(current, total):
            if feature_progress.total is None:
                feature_progress.total = total
            feature_progress.update(current)
            if current == total:
                feature_progress.finish(f"Extracted {total:,} sentences")

        crf_feature_materials = util.load_crf_feature_materials()
        features = crf_core.extract_features(all_sentences, crf_feature_materials,
                                             progress_callback=feature_progress_callback)
        print("Feature extraction complete")
        print()

        # Save TSV for reference
        tsv_path = os.path.join(util.get_user_config_dir(), 'crf_model_training_data.tsv')
        crf_core.save_training_data_tsv(all_sentences, features, tsv_path)
        print(f"Training data saved to: {tsv_path}")
        print()

        # Step 3: Train model
        result = crf_core.train_model(all_sentences, features, output_path,
                                      progress_callback=progress_callback)

        # Skip the features-based training below
        return _print_training_result(result, combined_stats)
    else:
        # No arguments: use default TSV path
        features_path = os.path.join(util.get_user_config_dir(), 'crf_model_training_data.tsv')
        print("No corpus specified. Using pre-extracted features from default path.")

    # Train from features (either explicit --features or default path)
    if not os.path.exists(features_path):
        print(f"ERROR: Features file not found: {features_path}")
        print()
        print("To create this file, either:")
        print("  1. Run feature extraction first:")
        print("     python crf_train_cli.py extract <corpus.txt>")
        print("  2. Or use one-shot training from corpus:")
        print("     python crf_train_cli.py train <corpus.txt>")
        return 1

    print(f"Training from pre-extracted features: {features_path}")
    print()

    result, stats = crf_core.run_training_from_features(
        features_path,
        model_path=output_path,
        progress_callback=progress_callback
    )

    return _print_training_result(result, stats)


def _print_training_result(result, stats):
    """Print training results and return exit code."""

    print()
    if stats:
        print("-" * 60)
        print("Corpus Statistics:")
        print(f"  Sentences:      {stats.get('sentence_count', 'N/A'):,}")
        print(f"  Total tokens:   {stats.get('total_tokens', 'N/A'):,}")
        if 'total_bunsetsu' in stats:
            print(f"  Total bunsetsu: {stats['total_bunsetsu']:,}")
            print(f"    Lookup:       {stats['lookup_bunsetsu']:,}")
            print(f"    Passthrough:  {stats['passthrough_bunsetsu']:,}")
        if 'dict_entries' in stats:
            print(f"  Dictionary entries added: {stats['dict_entries']:,} ({stats.get('dict_tokens', 0):,} tokens)")
        print()

    if result.success:
        print("-" * 60)
        print("Training Results:")
        print(f"  Model path:     {result.model_path}")
        print(f"  Model size:     {result.model_size:,} bytes")
        print(f"  Training time:  {result.training_time:.2f}s")
        if result.last_iteration:
            print(f"  Iterations:     {result.last_iteration}")
        if result.loss:
            print(f"  Final loss:     {result.loss}")
        if result.feature_count:
            print(f"  Feature count:  {result.feature_count}")
        print()
        print("Training complete!")
        return 0
    else:
        print(f"ERROR: {result.error_message}")
        return 1


def cmd_test(args):
    """
    Test bunsetsu segmentation on input text.
    入力テキストで文節セグメンテーションをテスト。
    """
    input_text = args.text
    n_best = args.nbest
    model_path = args.model

    if model_path and not os.path.exists(model_path):
        print(f"ERROR: Model file not found: {model_path}")
        return 1

    default_model = util.get_crf_model_path()
    if not model_path and not os.path.exists(default_model):
        print(f"ERROR: No model found at {default_model}")
        print("Train a model first with: python crf_train_cli.py train <corpus.txt>")
        return 1

    print("=" * 60)
    print("CRF Bunsetsu Segmentation Test")
    print("=" * 60)
    print()
    print(f"Input: {input_text}")
    print()

    try:
        results = crf_core.test_prediction(input_text, model_path=model_path, n_best=n_best)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    tokens = util.tokenize_line(input_text)

    print(f"N-best predictions (top {len(results)}):")
    print("-" * 60)

    for i, (labels, score) in enumerate(results):
        formatted = crf_core.format_bunsetsu_output(tokens, labels, markup=False)
        print(f"  #{i+1} (score: {score:.4f})")
        print(f"      {formatted}")

        # Show label details if verbose
        if args.verbose:
            label_str = ' '.join(labels)
            print(f"      Labels: {label_str}")
        print()

    return 0


def cmd_extract(args):
    """
    Extract features from corpus file(s) and save to TSV for later training.
    コーパスファイルから特徴量を抽出し、後の訓練用にTSVに保存。

    This is Step 1 of the two-step training workflow:
    これは2ステップ訓練ワークフローのステップ1:
        1. extract: corpus → features.tsv (human-readable, can inspect/edit)
           抽出: コーパス → features.tsv（人間が読める、検査/編集可能）
        2. train --features features.tsv → model.crfsuite
           訓練: --features features.tsv → model.crfsuite

    Multiple corpus files can be provided and will be combined.
    複数のコーパスファイルを指定でき、結合される。
    """
    corpus_paths = args.corpus
    output_path = args.output

    # Validate all input files exist
    for path in corpus_paths:
        if not os.path.exists(path):
            print(f"ERROR: Corpus file not found: {path}")
            return 1

    print("=" * 60)
    print("CRF Feature Extraction")
    print("=" * 60)
    print()

    # Step 0: Regenerate dictionary features
    print("Regenerating dictionary features (crf_feature_materials.json)...")
    materials_path = util.generate_crf_feature_materials()
    if materials_path:
        print(f"Dictionary features updated: {materials_path}")
    else:
        print("Warning: Failed to regenerate dictionary features, using existing file")
    print()

    # Step 1: Load corpus file(s)
    all_sentences = []
    combined_stats = {
        'line_count': 0,
        'sentence_count': 0,
        'total_tokens': 0,
        'total_bunsetsu': 0,
        'lookup_bunsetsu': 0,
        'passthrough_bunsetsu': 0,
    }

    for corpus_path in corpus_paths:
        print(f"Loading corpus: {corpus_path}")
        sentences, stats = crf_core.load_corpus(corpus_path)
        all_sentences.extend(sentences)

        # Accumulate stats
        combined_stats['line_count'] += stats['line_count']
        combined_stats['sentence_count'] += stats['sentence_count']
        combined_stats['total_tokens'] += stats['total_tokens']
        combined_stats['total_bunsetsu'] += stats['total_bunsetsu']
        combined_stats['lookup_bunsetsu'] += stats['lookup_bunsetsu']
        combined_stats['passthrough_bunsetsu'] += stats['passthrough_bunsetsu']

        print(f"  Loaded {stats['sentence_count']:,} sentences, {stats['total_tokens']:,} tokens")

    if len(corpus_paths) > 1:
        print()
        print(f"Combined: {combined_stats['sentence_count']:,} sentences, {combined_stats['total_tokens']:,} tokens")

    # Step 1b: Load extended dictionary entries as additional training data
    dict_sentences, dict_stats = crf_core.load_extended_dictionary_as_training_data()
    if dict_stats['dict_entries'] > 0:
        all_sentences.extend(dict_sentences)
        combined_stats['dict_entries'] = dict_stats['dict_entries']
        combined_stats['dict_tokens'] = dict_stats['total_tokens']
        combined_stats['sentence_count'] += dict_stats['dict_entries']
        combined_stats['total_tokens'] += dict_stats['total_tokens']
        combined_stats['total_bunsetsu'] += dict_stats['dict_entries']
        combined_stats['lookup_bunsetsu'] += dict_stats['dict_entries']
        print(f"Added {dict_stats['dict_entries']:,} dictionary entries as training data")

    print()

    # Step 2: Extract features
    print("Extracting features...")
    feature_progress = ProgressCounter("Extracting", update_interval=100)

    def feature_progress_callback(current, total):
        if feature_progress.total is None:
            feature_progress.total = total
        feature_progress.update(current)
        if current == total:
            feature_progress.finish(f"Extracted {total:,} sentences")

    crf_feature_materials = util.load_crf_feature_materials()
    features = crf_core.extract_features(all_sentences, crf_feature_materials,
                                         progress_callback=feature_progress_callback)
    print("Feature extraction complete")
    print()

    # Step 3: Save to TSV
    if output_path is None:
        output_path = os.path.join(util.get_user_config_dir(), 'crf_model_training_data.tsv')

    crf_core.save_training_data_tsv(all_sentences, features, output_path)
    print(f"Features saved to: {output_path}")

    print()
    print("-" * 60)
    print("Corpus Statistics:")
    print(f"  Corpus files:   {len(corpus_paths)}")
    print(f"  Sentences:      {combined_stats['sentence_count']:,}")
    print(f"  Total tokens:   {combined_stats['total_tokens']:,}")
    print(f"  Total bunsetsu: {combined_stats['total_bunsetsu']:,}")
    print(f"    Lookup:       {combined_stats['lookup_bunsetsu']:,}")
    print(f"    Passthrough:  {combined_stats['passthrough_bunsetsu']:,}")
    if 'dict_entries' in combined_stats:
        print(f"  Dictionary entries added: {combined_stats['dict_entries']:,} ({combined_stats.get('dict_tokens', 0):,} tokens)")
    print()
    print(f"Feature extraction complete!")
    print(f"  Features saved to: {output_path}")
    print()
    print("You can inspect/edit the TSV file before training.")
    print("To train a model from these features, run:")
    print(f"  python crf_train_cli.py train --features {output_path}")
    return 0


def cmd_stats(args):
    """
    Show statistics for training corpus file(s).
    訓練コーパスファイルの統計を表示。
    """
    corpus_paths = args.corpus

    # Validate all files exist
    for path in corpus_paths:
        if not os.path.exists(path):
            print(f"ERROR: Corpus file not found: {path}")
            return 1

    print("=" * 60)
    print("Corpus Statistics")
    print("=" * 60)
    print()

    all_sentences = []
    combined_stats = {
        'line_count': 0,
        'sentence_count': 0,
        'total_tokens': 0,
        'total_bunsetsu': 0,
        'lookup_bunsetsu': 0,
        'passthrough_bunsetsu': 0,
    }

    for corpus_path in corpus_paths:
        sentences, stats = crf_core.load_corpus(corpus_path)
        all_sentences.extend(sentences)

        print(f"File:             {corpus_path}")
        print(f"  Lines:          {stats['line_count']:,}")
        print(f"  Sentences:      {stats['sentence_count']:,}")
        print(f"  Total tokens:   {stats['total_tokens']:,}")
        print(f"  Total bunsetsu: {stats['total_bunsetsu']:,}")
        print(f"    Lookup (L):   {stats['lookup_bunsetsu']:,}")
        print(f"    Passthrough:  {stats['passthrough_bunsetsu']:,}")
        print()

        combined_stats['line_count'] += stats['line_count']
        combined_stats['sentence_count'] += stats['sentence_count']
        combined_stats['total_tokens'] += stats['total_tokens']
        combined_stats['total_bunsetsu'] += stats['total_bunsetsu']
        combined_stats['lookup_bunsetsu'] += stats['lookup_bunsetsu']
        combined_stats['passthrough_bunsetsu'] += stats['passthrough_bunsetsu']

    # Show combined stats if multiple files
    if len(corpus_paths) > 1:
        print("-" * 60)
        print("Combined Statistics:")
        print(f"  Files:          {len(corpus_paths)}")
        print(f"  Lines:          {combined_stats['line_count']:,}")
        print(f"  Sentences:      {combined_stats['sentence_count']:,}")
        print(f"  Total tokens:   {combined_stats['total_tokens']:,}")
        print(f"  Total bunsetsu: {combined_stats['total_bunsetsu']:,}")
        print(f"    Lookup (L):   {combined_stats['lookup_bunsetsu']:,}")
        print(f"    Passthrough:  {combined_stats['passthrough_bunsetsu']:,}")
        print()

    # Show some examples
    if args.examples and all_sentences:
        print("-" * 60)
        print("Sample sentences:")
        print()
        for i, (tokens, tags) in enumerate(all_sentences[:args.examples]):
            formatted = crf_core.format_bunsetsu_output(tokens, tags, markup=False)
            print(f"  {i+1}. {formatted}")
        print()

    return 0


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="CRF bunsetsu segmentation training and testing CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # One-shot training (extract + train in one step)
  python crf_train_cli.py train corpus.txt

  # One-shot training with multiple corpus files
  python crf_train_cli.py train corpus1.txt corpus2.txt corpus3.txt

  # Two-step training workflow:
  # Step 1: Extract features to TSV (inspect/edit if needed)
  python crf_train_cli.py extract corpus.txt

  # Step 1 with multiple files (combined into single TSV)
  python crf_train_cli.py extract wiki.txt news.txt novels.txt

  # Step 2: Train from default TSV (no arguments needed!)
  python crf_train_cli.py train

  # Or train from a custom TSV file
  python crf_train_cli.py train --features custom_features.tsv

  # Test prediction
  python crf_train_cli.py test "きょうはてんきがよい"

  # Show corpus statistics
  python crf_train_cli.py stats corpus.txt

For more information, see the documentation in crf_core.py.
"""
    )

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Train command
    train_parser = subparsers.add_parser('train', help='Train a CRF model')
    train_parser.add_argument('corpus', nargs='*', help='Path(s) to training corpus file(s) (for one-shot training)')
    train_parser.add_argument('-f', '--features', help='Path to pre-extracted features TSV file (for two-step training)')
    train_parser.add_argument('-o', '--output', help='Output model path (default: auto)')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test prediction on text')
    test_parser.add_argument('text', help='Hiragana text to segment')
    test_parser.add_argument('-n', '--nbest', type=int, default=5,
                             help='Number of N-best results (default: 5)')
    test_parser.add_argument('-m', '--model', help='Path to model file (default: auto)')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract features from corpus (Step 1 of two-step training)')
    extract_parser.add_argument('corpus', nargs='+', help='Path(s) to corpus file(s) - multiple files will be combined')
    extract_parser.add_argument('-o', '--output', default=None,
                                help='Output TSV file path (default: ~/.config/ibus-pskk/crf_model_training_data.tsv)')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show corpus statistics')
    stats_parser.add_argument('corpus', nargs='+', help='Path(s) to corpus file(s)')
    stats_parser.add_argument('-e', '--examples', type=int, default=5,
                              help='Number of example sentences to show (default: 5)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    setup_logging(args.verbose)

    # Dispatch to command handler
    if args.command == 'train':
        return cmd_train(args)
    elif args.command == 'test':
        return cmd_test(args)
    elif args.command == 'extract':
        return cmd_extract(args)
    elif args.command == 'stats':
        return cmd_stats(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
