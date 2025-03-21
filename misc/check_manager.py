#!/usr/bin/env python3
"""
アーカイブマネージャのテストユーティリティ

アーカイブマネージャの機能とパフォーマンスをテストするためのツール
"""
import os
import sys
import io
import argparse
import traceback
import time
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

# 親ディレクトリをPythonパスに追加して、プロジェクトのモジュールをインポートできるようにする
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if (project_root not in sys.path):
    sys.path.insert(0, project_root)
    print(f"Added {project_root} to Python path")

# モジュールをインポート - パス設定後にインポートするように移動
from logutils import setup_logging, log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL

from arc.interface import get_archive_manager  # interfaceモジュールからインポート
from arc.arc import EntryInfo, EntryType, EntryStatus
from arc.path_utils import normalize_path, try_decode_path, fix_garbled_filename

try:
    pass
except ImportError as e:
    log_print(ERROR, f"エラー: アーカイブマネージャーのインポートに失敗しました: {e}")
    sys.exit(1)

# グローバル変数
current_archive_path: str = None
manager = get_archive_manager()
debug_mode = False
all_entries: List[EntryInfo] = []

# 現在のログレベル（デフォルトはERROR）
current_log_level = ERROR

def toggle_log_level():
    """ログレベルを循環させる（ERROR → WARNING → INFO → DEBUG → ERROR ...）"""
    global current_log_level
    
    if current_log_level == ERROR:
        current_log_level = WARNING
        print("ログレベル: WARNING")
    elif current_log_level == WARNING:
        current_log_level = INFO
        print("ログレベル: INFO")
    elif current_log_level == INFO:
        current_log_level = DEBUG
        print("ログレベル: DEBUG")
    else:  # DEBUG
        current_log_level = ERROR
        print("ログレベル: ERROR")
    
    # ロギングシステムに新しいレベルを設定
    setup_logging(current_log_level)

def print_banner():
    """アプリケーションバナーを表示"""
    print("=" * 70)
    print("アーカイブマネージャー テストツール")
    print("このツールはアーカイブの操作と検証のためのコマンドラインインターフェースを提供します")
    print("=" * 70)


def print_help():
    """コマンドヘルプを表示"""
    print("\n使用可能なコマンド:")
    print("  S <path>      - アーカイブパスを設定（Set archive path）")
    print("                  空白を含むパスは \"path/to file.zip\" のように引用符で囲みます")
    print("  L [path]      - アーカイブ内のファイル/ディレクトリを一覧表示（List archive contents）")
    print("  R [path]      - アーカイブ内を再帰的に一覧表示（Recursive list all entries）")
    print("  RC            - キャッシュを持つエントリを表示（Show cached entries）")
    print("  RR            - キャッシュの全エントリのパスをダンプ（Dump all cached rel_paths）")
    print("  E <path>      - アーカイブからファイルを抽出（Extract file from archive）")
    print("                  空白を含むパスは引用符で囲みます")
    print("  I             - アーカイブ情報を表示（Information about archive）")
    print("  H             - ハンドラー情報を表示（Handlers information）")
    print("  D             - デバッグモードの切替（Toggle debug mode）")
    print("  ?             - このヘルプを表示")
    print("  Q             - 終了")
    print("")


def set_archive_path(path: str) -> bool:
    """
    現在のアーカイブパスを設定
    
    Args:
        path: アーカイブファイルへのパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive_path, all_entries
    
    # パスを正規化（先頭の/は物理パスとして保持する）
    path = normalize_path(path)
    
    if not os.path.exists(path):
        log_print(ERROR, f"エラー: ファイルが見つかりません: {path}")
        return False
        
    if not os.path.isfile(path) and not os.path.isdir(path):
        log_print(ERROR, f"エラー: 指定されたパスはファイルまたはディレクトリではありません: {path}")
        return False
        
    try:
        # 古い全エントリリストをクリア
        all_entries = {}
        
        # アーカイブファイルパスを設定
        current_archive_path = path
        log_print(INFO, f"アーカイブを設定: {path}")
        
        if os.path.isfile(path):
            log_print(INFO, f"ファイルサイズ: {os.path.getsize(path):,} バイト")
        
        # マネージャーにカレントパスを設定
        manager.set_current_path(path)
        all_entries = manager.get_entry_cache()
        log_print(INFO, f"エントリ数: {len(all_entries.keys())}/{len(all_entries.values())}")
        # マネージャーがこのファイルを処理できるか確認
        handler_info = manager.get_handler(path)
        if handler_info:
            handler_name = handler_info.__class__.__name__
            log_print(INFO, f"このファイルは '{handler_name}' で処理可能です")          
            return True
        else:
            log_print(ERROR, f"エラー: アーカイブマネージャーはこのファイルを処理できません: {path}")
            return False
    except Exception as e:
        log_print(ERROR, f"エラー: アーカイブの設定に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def list_archive_contents(internal_path: str = "") -> bool:
    """
    アーカイブの内容を一覧表示する
    
    Args:
        internal_path: アーカイブ内の相対パス（指定しない場合はルート）
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive_path
    
    if not current_archive_path:
        log_print(ERROR, "エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        # 内部パスが指定された場合は正規化
        if internal_path:
            internal_path = normalize_path(internal_path)
            log_print(INFO, f"パスの内容を取得中: {internal_path}")
            
            # 相対パスを使用してマネージャーから直接エントリを取得
            try:
                entries = manager.list_entries(internal_path)
            except FileNotFoundError as e:
                log_print(ERROR, f"エラー: 指定されたパスが見つかりません: {internal_path}")
                return False
        else:
            # ルートの場合は空のパスを使用
            log_print(INFO, f"アーカイブルートの内容を取得中")
            entries = manager.list_entries("")
        
        if not entries:
            log_print(INFO, f"アーカイブ内にエントリが見つかりません")
            return False
        
        # エントリを表示
        print("\nアーカイブの内容:")
        print("{:<36} {:>10} {:>17} {:<8} {}".format("名前", "サイズ", "更新日時", "ステータス", "種類"))
        print("-" * 90)
        
        for entry in sorted(entries, key=lambda e: (e.type.value, e.name)):
            type_str = "DIR" if entry.type == EntryType.DIRECTORY else "ARC" if entry.type == EntryType.ARCHIVE else "FILE"
            size_str = "-" if entry.type == EntryType.DIRECTORY else f"{entry.size:,}"
            date_str = "-" if entry.modified_time is None else entry.modified_time.strftime("%Y-%m-%d %H:%M")
            
            # ステータスの表示を追加
            status_str = "不明"
            if hasattr(entry, 'status'):
                if entry.status == EntryStatus.READY:
                    status_str = "READY"
                elif entry.status == EntryStatus.BROKEN:
                    status_str = "BROKEN"
                elif entry.status == EntryStatus.SCANNING:
                    status_str = "SCANNING"
            
            print("{:<36} {:>10} {:>17} {:<8} {}".format(
                entry.name[:35], size_str, date_str, status_str, type_str
            ))
            
        print(f"\n合計: {len(entries)} エントリ")
        return True
    except Exception as e:
        log_print(ERROR, f"エラー: アーカイブ内容の一覧取得に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def recursive_list_archive_contents(internal_path: str = "") -> bool:
    """
    アーカイブの内容を再帰的に一覧表示する
    
    Args:
        internal_path: アーカイブ内の相対パス（指定しない場合はルート）
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive_path
    
    if not current_archive_path:
        log_print(ERROR, "エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    try:       
        all_entries_dict = manager.get_entry_cache()
        if not all_entries_dict:
            log_print(INFO, f"アーカイブ内にエントリが見つかりませんでした") 
            return False

        # 辞書の値（EntryInfo）をリストに収集
        all_entries = list(all_entries_dict.values())
        if not all_entries:
            log_print(INFO, f"アーカイブ内にエントリが見つかりませんでした")
            return False
        
        # エントリの種類を分類
        directories = [e for e in all_entries if e.type == EntryType.DIRECTORY]
        files = [e for e in all_entries if e.type == EntryType.FILE]
        archives = [e for e in all_entries if e.type == EntryType.ARCHIVE]
        
        # 結果を表示
        print(f"ディレクトリ: {len(directories)}, ファイル: {len(files)}, アーカイブ: {len(archives)}")
        
        # すべてのエントリを一覧表示
        print("\nすべてのエントリ一覧:")
        print("{:<50} {:>12} {:>20} {}".format("パス", "サイズ", "更新日時", "種類"))
        print("-" * 90)
        
        # 現在のパスをベースパスとして使用
        base_path = current_archive_path
        if os.path.isdir(base_path) and not base_path.endswith('/'):
            base_path += '/'
        
        for entry in sorted(all_entries, key=lambda e: e.path):
            type_str = "DIR" if entry.type == EntryType.DIRECTORY else "ARC" if entry.type == EntryType.ARCHIVE else "FILE"
            size_str = "-" if entry.type == EntryType.DIRECTORY else f"{entry.size:,}"
            date_str = "-" if entry.modified_time is None else entry.modified_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 絶対パスから相対パスを計算
            path_str = entry.rel_path
            
            # 長いパスは省略
            if len(path_str) > 48:
                path_str = "..." + path_str[-45:]
                
            print("{:<50} {:>12} {:>20} {}".format(
                path_str, size_str, date_str, type_str
            ))
        
        # ツリー表示オプション
        show_tree = input("\nエントリをツリー表示しますか？ (y/N): ").lower() == 'y'
        if show_tree:
            # パスコンポーネントをキーとした辞書ツリーを構築
            tree = {}
            # ...existing code for tree building and display...
        
        return True
    except Exception as e:
        log_print(ERROR, f"エラー: 再帰的なアーカイブ内容の探索に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def extract_archive_file(file_path: str) -> bool:
    """
    アーカイブからファイルを抽出する
    
    Args:
        file_path: アーカイブ内の相対ファイルパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive_path
    
    if not current_archive_path:
        log_print(ERROR, "エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        file_path = normalize_path(file_path)
        log_print(INFO, f"ファイル '{file_path}' を抽出中...")
        
        # 相対パスを使用
        content = manager.read_file(file_path)
        
        if content is None:
            log_print(ERROR, f"エラー: ファイル '{file_path}' の読み込みに失敗しました")
            return False
        
        log_print(INFO, f"ファイルを読み込みました: {len(content):,} バイト")
        
        # ファイル解析（バイナリ/テキスト判定）
        binary_bytes = 0
        ascii_bytes = 0
        for byte in content[:min(1000, len(content))]:
            if byte < 9 or (byte > 13 and byte < 32) or byte >= 127:
                binary_bytes += 1
            elif 32 <= byte <= 126:
                ascii_bytes += 1
        
        # バイナリ判定の基準: 非ASCII文字が一定割合以上
        binary_ratio = binary_bytes / max(1, binary_bytes + ascii_bytes)
        is_text = binary_ratio < 0.1  # 10%以下なら文字列と判断
        
        # ファイルのタイプを判定して表示
        if is_text:
            # テキストファイルのエンコーディング判定
            encoding = None
            if len(content) > 2:
                # BOMでエンコーディングをチェック
                if content.startswith(b'\xef\xbb\xbf'):
                    encoding = 'utf-8-sig'
                elif content.startswith(b'\xff\xfe'):
                    encoding = 'utf-16-le'
                elif content.startswith(b'\xfe\xff'):
                    encoding = 'utf-16-be'
            
            if not encoding:
                # 一般的なエンコーディングを試す
                for enc in ['utf-8', 'cp932', 'euc-jp', 'latin-1']:
                    try:
                        content.decode(enc)
                        encoding = enc
                        log_print(INFO, f"エンコーディング検出: {encoding}")
                        break
                    except UnicodeDecodeError:
                        pass
            
            log_print(INFO, f"ファイルタイプ: テキストファイル ({encoding or '不明なエンコーディング'})")
        else:
            # バイナリファイルのタイプ判定
            file_type = "バイナリファイル"
            
            # ファイルの種類を判定
            if content.startswith(b'\xff\xd8\xff'):
                file_type = "JPEGイメージ"
            elif content.startswith(b'\x89PNG\r\n\x1a\n'):
                file_type = "PNGイメージ"
            elif content.startswith(b'GIF8'):
                file_type = "GIFイメージ"
            elif content.startswith(b'BM'):
                file_type = "BMPイメージ"
            elif content.startswith(b'\x1f\x8b'):
                file_type = "GZIPアーカイブ"
            elif content.startswith(b'PK\x03\x04'):
                file_type = "ZIPアーカイブ"
            elif content.startswith(b'Rar!\x1a\x07'):
                file_type = "RARアーカイブ"
                
            log_print(INFO, f"ファイルタイプ: {file_type}")
            
            # 画像ファイルの場合は、Pillowで追加情報を表示
            if "イメージ" in file_type:
                show_image_info(content)
        
        # ファイルを保存するか確認
        save_path = os.path.basename(file_path)
        answer = input(f"ファイルを保存しますか？ (Y/n, デフォルト: {save_path}): ")
        
        if answer.lower() != 'n':
            # 保存パスの指定があれば使用
            if answer and answer.lower() != 'y' and answer != save_path:
                save_path = answer
                
            # ファイルを保存
            try:
                with open(save_path, 'wb') as f:
                    f.write(content)
                log_print(INFO, f"ファイルを保存しました: {save_path} ({len(content):,} バイト)")
            except Exception as e:
                log_print(ERROR, f"ファイル保存エラー: {e}")
                if debug_mode:
                    traceback.print_exc()
                
        # テキストの場合は内容を表示
        if is_text and encoding:
            print(f"\n===== ファイル内容 (エンコーディング: {encoding}) =====")
            
            try:
                text = content.decode(encoding)
                # 長いテキストは省略表示
                max_chars = 500
                if (len(text) > max_chars):
                    print(text[:max_chars] + "...(省略)")
                else:
                    print(text)
            except Exception as e:
                log_print(ERROR, f"テキスト表示エラー: {e}")
        else:
            log_print(INFO, "バイナリファイルのため、内容表示はスキップします。")
                
        # テスト完了
        log_print(INFO, "\n抽出テスト完了！")
        return True
    except Exception as e:
        log_print(ERROR, f"エラー: ファイルの抽出に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_image_info(content: bytes) -> None:
    """
    画像ファイルの情報を表示する
    
    Args:
        content: 画像ファイルのバイトデータ
    """
    try:
        # PILをインポート
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            from io import BytesIO
        except ImportError:
            log_print(ERROR, "PIL(Pillow)がインストールされていません。画像情報を表示できません。")
            log_print(INFO, "pip install Pillow でインストールできます。")
            return
        
        # バイトデータから画像を開く
        img = Image.open(BytesIO(content))
        
        # 画像情報を表示
        print("\n[画像情報]")
        print(f"形式: {img.format}")
        print(f"サイズ: {img.width}x{img.height} ピクセル")
        print(f"カラーモード: {img.mode}")
        
        # DPI情報があれば表示
        if 'dpi' in img.info:
            log_print(INFO, f"解像度: {img.info['dpi']} DPI")
            
        # EXIF情報があれば表示
        if hasattr(img, '_getexif') and img._getexif():
            exif = img._getexif()
            if exif:
                log_print(INFO, "\n[EXIF情報]")
                
                # 主要なEXIF情報を表示
                exif_data = {}
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = value
                
                # 主要な情報を優先表示
                important_tags = ['Make', 'Model', 'DateTime', 'ExposureTime', 'FNumber', 'ISOSpeedRatings']
                for tag in important_tags:
                    if tag in exif_data:
                        log_print(INFO, f"{tag}: {exif_data[tag]}")
        
    except Exception as e:
        log_print(ERROR, f"画像情報の取得に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()


def show_archive_info() -> bool:
    """
    アーカイブの情報を表示する
    
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive_path
    
    if not current_archive_path:
        log_print(ERROR, "エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        log_print(INFO, f"\nアーカイブ情報:")
        log_print(INFO, f"パス: {current_archive_path}")
        
        # ファイル情報を取得
        if os.path.isfile(current_archive_path):
            log_print(INFO, f"サイズ: {os.path.getsize(current_archive_path):,} バイト")
            log_print(INFO, f"更新日時: {time.ctime(os.path.getmtime(current_archive_path))}")
            
            # アーカイブエントリ数を取得
            entry_info = manager.get_entry_info(current_archive_path)
            if entry_info:
                log_print(INFO, f"タイプ: {entry_info.type}")
        
        # キャッシュされたエントリ一覧の統計
        if all_entries:
            log_print(INFO, f"\nエントリ統計:")
            log_print(INFO, f"合計エントリ数: {len(all_entries)}")
            
            # エントリタイプごとの集計
            type_counts = {}
            for entry in all_entries:
                type_name = entry.type.name
                if type_name not in type_counts:
                    type_counts[type_name] = 0
                type_counts[type_name] += 1
                
            for type_name, count in sorted(type_counts.items()):
                log_print(INFO, f"  {type_name}: {count} エントリ")
                
            # サイズ統計（ファイルのみ）
            file_sizes = [entry.size for entry in all_entries if entry.type == EntryType.FILE]
            if file_sizes:
                total_size = sum(file_sizes)
                avg_size = total_size / len(file_sizes)
                max_size = max(file_sizes)
                min_size = min(file_sizes)
                log_print(INFO, f"\nファイルサイズ統計:")
                log_print(INFO, f"  合計サイズ: {total_size:,} バイト")
                log_print(INFO, f"  平均サイズ: {avg_size:,.2f} バイト")
                log_print(INFO, f"  最大サイズ: {max_size:,} バイト")
                log_print(INFO, f"  最小サイズ: {min_size:,} バイト")
                
                # 最大サイズのファイルを表示
                largest_file = next((entry for entry in all_entries if entry.size == max_size), None)
                if largest_file:
                    log_print(INFO, f"  最大ファイル: {largest_file.name} ({max_size:,} バイト)")
        
        return True
    except Exception as e:
        log_print(ERROR, f"エラー: アーカイブ情報の取得に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_handlers_info() -> bool:
    """
    登録されているハンドラーの情報を表示する
    
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    try:
        log_print(INFO, "\nハンドラー情報:")
        handlers = manager.handlers
        
        if not handlers:
            log_print(INFO, "登録されているハンドラーがありません")
            return True
            
        # 各ハンドラーの情報を表示
        log_print(INFO, "登録ハンドラー数:", len(handlers))
        log_print(INFO, "-" * 50)
        
        for i, handler in enumerate(handlers):
            handler_name = handler.__class__.__name__
            log_print(INFO, f"{i+1}. {handler_name}")
            
            # サポートしている拡張子
            if hasattr(handler, 'supported_extensions'):
                exts = ", ".join(handler.supported_extensions)
                log_print(INFO, f"   サポート拡張子: {exts}")
                
            # モジュール情報
            module_name = handler.__class__.__module__
            log_print(INFO, f"   モジュール: {module_name}")
            
            # ハンドラーの機能を確認
            caps = []
            if hasattr(handler, 'list_entries'):
                caps.append("list_entries")
            if hasattr(handler, 'list_entries_from_bytes'):
                caps.append("list_entries_from_bytes")
            if hasattr(handler, 'list_all_entries'):
                caps.append("list_all_entries")
            if hasattr(handler, 'read_file'):
                caps.append("read_file")
            if hasattr(handler, 'read_archive_file'):
                caps.append("read_archive_file")
            if hasattr(handler, 'read_file_from_bytes'):
                caps.append("read_file_from_bytes")
            
            log_print(INFO, f"   機能: {', '.join(caps)}")
            log_print(INFO, "-" * 50)
        
        return True
    except Exception as e:
        log_print(ERROR, f"エラー: ハンドラー情報の取得に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_cached_entries() -> bool:
    """
    キャッシュ属性を持つエントリを一覧表示する
    
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive_path, manager
    
    if not current_archive_path:
        log_print(ERROR, "エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        # キャッシュからエントリを取得
        all_entries_dict = manager.get_entry_cache()
        if not all_entries_dict:
            log_print(INFO, f"キャッシュにエントリが見つかりませんでした。")
            return False
        
        # キャッシュを持つエントリを集める
        cached_entries = []
        for path, entry in all_entries_dict.items():
            if hasattr(entry, 'cache') and entry.cache is not None:
                cached_entries.append(entry)
        
        if not cached_entries:
            log_print(INFO, "キャッシュを持つエントリはありません。")
            return False
        
        # キャッシュを持つエントリを表示
        print("\nキャッシュを持つエントリ一覧:")
        print("{:<50} {:<12} {:<20}".format("パス", "キャッシュタイプ", "サイズ"))
        print("-" * 85)
        
        for entry in sorted(cached_entries, key=lambda e: e.rel_path):
            # キャッシュの種類とサイズを取得
            cache_type = type(entry.cache).__name__
            cache_size = ""
            
            if isinstance(entry.cache, bytes):
                cache_size = f"{len(entry.cache):,} バイト"
            elif isinstance(entry.cache, str) and os.path.exists(entry.cache):
                try:
                    cache_size = f"{os.path.getsize(entry.cache):,} バイト (ファイル)"
                except:
                    cache_size = "(一時ファイル)"
            
            # 長いパスは省略
            path_str = entry.rel_path
            if len(path_str) > 48:
                path_str = "..." + path_str[-45:]
            
            print("{:<50} {:<12} {:<20}".format(path_str, cache_type, cache_size))
        
        print(f"\n合計: {len(cached_entries)} エントリ")
        return True
    except Exception as e:
        log_print(ERROR, f"エラー: キャッシュエントリ表示に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_cached_entry_paths(manager):
    """キャッシュされているエントリのパスを表示する"""
    missmatch_count = 0
    if hasattr(manager, 'get_entry_cache'):
        cache = manager.get_entry_cache()
        log_print(INFO, f"キャッシュされているエントリ数: {len(cache)}")
        
        # キャッシュキーをソート - 空文字列は最後に表示する
        sorted_keys = sorted(cache.keys(), key=lambda k: (k == "", k))
        
        # 連番を付けてすべてのエントリを表示
        for idx, path in enumerate(sorted_keys, 1):
            entry = cache[path]
            
            # すべてのエントリに対して同じフォーマットで表示（rel_pathの情報も含める）
            # 空文字列キーも他のエントリと同じく一貫した形式で表示
            if path == "":
                display_path = '""'  # 空文字列キーを視覚的に表現
            else:
                display_path = path
                
            log_print(INFO, f"  {idx:3d}. {display_path}: {entry.name} ({entry.type.name}) [rel_path=\"{entry.rel_path}\"]")
            
            # キャッシュキーとrel_pathの不一致をチェック（末尾の/を考慮）
            normalized_rel_path = entry.rel_path.rstrip('/')
            if path != normalized_rel_path:
                log_print(ERROR, f"      ERROR: キーとrel_pathの不一致: キー=\"{path}\" vs rel_path=\"{entry.rel_path}\" (正規化後=\"{normalized_rel_path}\")")
                missmatch_count += 1
        
        log_print(INFO, f"\nキャッシュキーとrel_pathの不一致数: {missmatch_count}")
    else:
        log_print(INFO, "キャッシュ機能が利用できません")


def show_cached_recursive(manager, path="", prefix=""):
    """
    キャッシュを使って再帰的にファイルツリーを表示する
    キャッシュ形式（dict[str, EntryInfo]）に対応
    """
    if not hasattr(manager, 'get_entry_cache'):
        log_print(INFO, "このマネージャーはキャッシュ機能を持っていません")
        return
    
    cache = manager.get_entry_cache()
    if not cache:
        log_print(INFO, "キャッシュが空です")
        return
    
    # 検索パスの準備（末尾のスラッシュを確保）
    search_path = path if path.endswith('/') or not path else path + '/'
    search_path_len = len(search_path) if search_path != '/' else 0
    
    # 現在のディレクトリのエントリを収集
    current_dir_entries = []
    
    # キャッシュから直接の子エントリを検索
    for entry_path, entry in cache.items():
        if path == '':  # ルート
            if '/' not in entry_path:
                current_dir_entries.append(entry)
        else:  # 特定のディレクトリ
            if entry_path.startswith(search_path):
                remaining_path = entry_path[search_path_len:]
                if '/' not in remaining_path:  # 直接の子のみ
                    current_dir_entries.append(entry)
    
    # エントリを表示
    for entry in sorted(current_dir_entries, key=lambda e: e.name):
        if entry.type.name == "DIRECTORY":
            log_print(INFO, f"{prefix}{entry.name}/")
            # 再帰的に子を表示
            next_path = f"{path}/{entry.name}" if path else entry.name
            show_cached_recursive(manager, next_path, prefix + "  ")
        elif entry.type.name == "ARCHIVE":
            log_print(INFO, f"{prefix}{entry.name} [アーカイブ]")
        else:
            log_print(INFO, f"{prefix}{entry.name}")


def parse_command_args(args_str: str) -> str:
    """
    コマンド引数を解析して、引用符で囲まれた文字列を適切に処理する
    
    Args:
        args_str: コマンドの引数文字列
        
    Returns:
        解析された引数
    """
    args_str = args_str.strip()
    
    # 引数がない場合
    if not args_str:
        return ""
    
    # 引用符で囲まれた引数を処理
    if (args_str.startswith('"') and args_str.endswith('"')) or \
       (args_str.startswith("'") and args_str.endswith("'")):
        # 引用符を除去
        return args_str[1:-1]
    
    return args_str


def main():
    """メインのCLIループ"""
    global debug_mode
    
    print_banner()
    print_help()
    
    # ロギングを設定（デフォルトはERRORレベル）
    setup_logging(current_log_level)
    
    # 現在のログレベルを表示（起動時のレベル確認用）
    level_names = {
        ERROR: "ERROR",
        WARNING: "WARNING", 
        INFO: "INFO",
        DEBUG: "DEBUG"
    }
    print(f"起動時のログレベル: {level_names.get(current_log_level, 'UNKNOWN')}")
    
    # コマンドループ
    while True:
        try:
            cmd_input = input("\nコマンド> ").strip()
            
            if not cmd_input:
                continue
                
            cmd = cmd_input.upper()
            
            # コマンド処理
            if cmd == 'Q':
                log_print(INFO, "終了します。")
                break
            elif cmd == '?':
                print_help()
            elif cmd == 'RR':
                show_cached_entry_paths(manager)
                continue
            elif cmd == 'RC':
                show_cached_entries()
                continue
            elif cmd == 'D':
                # dコマンドでログレベル切り替え
                toggle_log_level()
                continue
                
            # 単一文字コマンドとその引数の処理
            cmd = cmd_input[0].upper()
            args_str = cmd_input[1:].strip() if len(cmd_input) > 1 else ""
            
            # 引数を解析（引用符で囲まれたパスを適切に処理）
            args = parse_command_args(args_str)
            
            if cmd == 'S':
                if not args:
                    log_print(ERROR, "エラー: アーカイブパスを指定してください。例: S /path/to/archive.zip")
                    log_print(INFO, "       空白を含むパスは S \"C:/Program Files/file.zip\" のように指定してください")
                else:
                    set_archive_path(args)
            elif cmd == 'L':
                list_archive_contents(args)
            elif cmd == 'R':
                recursive_list_archive_contents(args)
            elif cmd == 'E':
                if not args:
                    log_print(ERROR, "エラー: 抽出するファイルのパスを指定してください。例: E document.txt")
                    log_print(INFO, "       空白を含むパスは E \"folder/my document.txt\" のように指定してください")
                else:
                    extract_archive_file(args)
            elif cmd == 'I':
                show_archive_info()
            elif cmd == 'H':
                show_handlers_info()
            else:
                log_print(ERROR, f"未知のコマンド: {cmd_input}。'?'と入力してヘルプを表示してください。")
                
        except KeyboardInterrupt:
            log_print(INFO, "\n中断されました。終了するには 'Q' を入力してください。")
        except EOFError:
            log_print(INFO, "\n終了します。")
            break
        except Exception as e:
            log_print(ERROR, f"エラー: {e}")
            if debug_mode:
                traceback.print_exc()


if __name__ == "__main__":
    # コマンドライン引数があれば処理
    parser = argparse.ArgumentParser(description="アーカイブマネージャーのテストツール")
    parser.add_argument('archive', nargs='?', help="開くアーカイブファイルのパス")
    parser.add_argument('-d', '--debug', action='store_true', help="デバッグモードを有効化")
    
    args = parser.parse_args()
    
    if args.debug:
        debug_mode = True
        log_print(INFO, "デバッグモードを有効化しました。")
    
    # ファイルが指定されていれば開く
    if args.archive:
        set_archive_path(args.archive)
    
    # メインループを実行
    main()
