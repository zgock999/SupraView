#!/usr/bin/env python3
"""
ファイルシステムハンドラのテスト用コマンドラインツール

このツールはファイルシステムハンドラの操作とパス問題の確認を行うためのCLIを提供します。
"""
import os
import sys
import argparse
import time
import io
import traceback
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

# パスの追加（親ディレクトリをインポートパスに含める）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    # ハンドラ関連のモジュールをインポート
    from arc.handler.fs_handler import FileSystemHandler
    from arc.handler.mfs_handler import MultiThreadedFileSystemHandler
    from arc.arc import EntryInfo, EntryType
except ImportError as e:
    print(f"エラー: モジュールのインポートに失敗しました: {e}")
    sys.exit(1)

# 必要なインポートを追加
import tempfile
from PIL import Image, UnidentifiedImageError

# グローバル変数
current_path: str = None
debug_mode = False
# 現在のハンドラをFS (FileSystemHandler)かMFS (MultiThreadedFileSystemHandler)か選択可能にする
handler_type = "FS"  # デフォルトはFS
handler = FileSystemHandler()
# 全エントリリストを保持する変数を追加
all_entries: List[EntryInfo] = []


def print_banner():
    """アプリケーションバナーを表示"""
    print("=" * 70)
    print("ファイルシステムハンドラ テストツール")
    print("このツールはファイルシステムハンドラの操作とパス問題の検証用CLIを提供します")
    print("=" * 70)


def print_help():
    """コマンドヘルプを表示"""
    print("\n使用可能なコマンド:")
    print("  S <path>      - ディレクトリパスを設定（Set directory path）")
    print("                  空白を含むパスは \"path/to folder\" のように引用符で囲みます")
    print("  L [subpath]   - ディレクトリ内のファイル/サブディレクトリを一覧表示（List directory contents）")
    print("  E <path>      - ファイルを読み込み表示/抽出（Extract/show file contents）")
    print("                  空白を含むパスは引用符で囲みます")
    print("  I <name>      - 指定した名前のファイルを現在のディレクトリから検索（find In directory）")
    print("  A <path>      - 指定したパスの絶対パスを表示（display Absolute path）")
    print("  U <path>      - パスを正規化して表示（show normalized/Unified path）")
    print("  M             - ハンドラタイプの切替（FS <-> MFS）（switch handler Mode）")
    print("  D             - デバッグモードの切替（Toggle debug mode）")
    print("  R             - ルートディレクトリの一覧を表示（show Root directories）")
    print("  H             - このヘルプを表示")
    print("  Q             - 終了")
    print("")


def normalize_path(path: str) -> str:
    """
    各OSのパスを一般的なフォーマットに正規化する
    
    Args:
        path: 正規化するパス文字列
        
    Returns:
        正規化されたパス文字列
    """
    # バックスラッシュをスラッシュに変換
    normalized = path.replace('\\', '/')
    
    # 連続するスラッシュを1つに
    while '//' in normalized:
        normalized = normalized.replace('//', '/')
        
    return normalized


def set_current_path(path: str) -> bool:
    """
    現在のディレクトリパスを設定する
    
    Args:
        path: ディレクトリへのパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_path, all_entries, handler
    
    # パスを正規化
    path = normalize_path(path)
    
    try:
        # パスの存在確認
        if not os.path.exists(path):
            print(f"エラー: パスが見つかりません: {path}")
            return False
            
        # 絶対パスに変換
        abs_path = os.path.abspath(path).replace('\\', '/')
        
        # ディレクトリの場合
        if os.path.isdir(abs_path):
            current_path = abs_path
            handler.current_path = current_path  # ハンドラの現在のパスも設定
            print(f"現在のディレクトリを設定: {current_path}")
            
            # 全エントリリストを更新
            print("ディレクトリ内のすべてのエントリを取得しています...")
            all_entries = handler.list_all_entries(current_path)
            print(f"{len(all_entries)}個のエントリを取得しました")
            
            # ルートディレクトリの情報を表示
            entry_info = handler.get_entry_info(current_path)
            if entry_info:
                print(f"ディレクトリ情報: 名前={entry_info.name}, パス={entry_info.path}, タイプ={entry_info.type}")
            
            return True
        # ファイルの場合は親ディレクトリを設定
        elif os.path.isfile(abs_path):
            # 親ディレクトリを取得して設定
            parent_dir = os.path.dirname(abs_path)
            current_path = parent_dir
            handler.current_path = current_path  # ハンドラの現在のパスも設定
            print(f"ファイルの親ディレクトリを設定: {current_path}")
            
            # 全エントリリストを更新
            print("ディレクトリ内のすべてのエントリを取得しています...")
            all_entries = handler.list_all_entries(current_path)
            print(f"{len(all_entries)}個のエントリを取得しました")
            
            # ファイル自体の情報も表示
            file_info = handler.get_entry_info(abs_path)
            if file_info:
                print(f"ファイル情報: 名前={file_info.name}, サイズ={file_info.size}, 更新日時={file_info.modified_time}")
            
            return True
        else:
            print(f"エラー: 指定されたパスはファイルでもディレクトリでもありません: {path}")
            return False
    except Exception as e:
        print(f"エラー: パスの設定中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def list_directory_contents(internal_path: str = "") -> bool:
    """
    ディレクトリの内容を一覧表示する
    
    Args:
        internal_path: ディレクトリ内のパス（指定しない場合は現在のディレクトリ）
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_path, all_entries, handler
    
    if not current_path:
        print("エラー: ディレクトリパスが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        # 内部パスを正規化
        if internal_path:
            internal_path = normalize_path(internal_path)
            
        # 一覧表示するパスを構築
        list_path = current_path if not internal_path else os.path.join(current_path, internal_path).replace('\\', '/')
            
        print(f"ディレクトリの内容を一覧表示: {list_path}")
        
        # ハンドラを使用してエントリを取得
        entries = handler.list_entries(list_path)
        
        if not entries:
            print(f"ディレクトリ内にエントリがないか、指定されたパス '{internal_path}' が見つかりません。")
            
            # 部分一致で検索を試みる
            if internal_path:
                print("部分一致で検索を試みます...")
                for entry in all_entries:
                    if entry.name.lower().find(internal_path.lower()) != -1:
                        print(f"一致するエントリを見つけました: {entry.path} (タイプ: {entry.type})")
            
            return False
        
        # エントリを表示
        print("\nディレクトリの内容:")
        print("{:<40} {:>10} {:>20} {}".format("名前", "サイズ", "更新日時", "種類"))
        print("-" * 80)
        
        for entry in sorted(entries, key=lambda e: (e.type.value, e.name)):
            type_str = "DIR" if entry.type == EntryType.DIRECTORY else "ARC" if entry.type == EntryType.ARCHIVE else "FILE"
            size_str = "-" if entry.type == EntryType.DIRECTORY else f"{entry.size:,}"
            date_str = "-" if entry.modified_time is None else entry.modified_time.strftime("%Y-%m-%d %H:%M:%S")
            
            print("{:<40} {:>10} {:>20} {}".format(
                entry.name[:39], size_str, date_str, type_str
            ))
            
        print(f"\n合計: {len(entries)} エントリ")
        return True
    except Exception as e:
        print(f"エラー: ディレクトリ内容の一覧取得に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def find_entry_by_path(entries: List[EntryInfo], file_path: str) -> Optional[EntryInfo]:
    """
    全エントリリストから特定パスのエントリを検索する
    
    Args:
        entries: 検索対象のエントリリスト
        file_path: 検索するファイルパス
    
    Returns:
        見つかったエントリ情報、または見つからない場合はNone
    """
    if not entries:
        return None
        
    # パスを正規化
    norm_path = normalize_path(file_path)
    file_name = os.path.basename(norm_path)
    
    # デバッグ出力
    print(f"エントリ検索: パス={norm_path}, ファイル名={file_name}")
    
    # 1. 正確なパス一致を試行
    for entry in entries:
        if normalize_path(entry.path) == norm_path:
            print(f"完全パス一致でエントリを見つけました: {entry.path}")
            return entry
            
    # 2. 相対パスで一致するか確認
    if current_path and norm_path.startswith(current_path):
        rel_path = norm_path[len(current_path):].lstrip('/')
        for entry in entries:
            if hasattr(entry, 'rel_path') and entry.rel_path == rel_path:
                print(f"相対パス一致でエントリを見つけました: {entry.path}")
                return entry
    
    # 3. ファイル名だけの一致を試行
    for entry in entries:
        if entry.name == file_name:
            print(f"ファイル名一致でエントリを見つけました: {entry.path}")
            return entry
    
    # 4. 部分文字列一致を試行（ファイル名の一部が一致する場合）
    for entry in entries:
        if file_name.lower() in entry.name.lower():
            print(f"部分文字列一致でエントリを見つけました: {entry.path}")
            return entry
    
    print(f"一致するエントリが見つかりませんでした: {file_path}")
    return None


def extract_file(file_path: str) -> bool:
    """
    ファイルを読み込んで表示/抽出する
    
    Args:
        file_path: ファイルパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_path, all_entries, handler
    
    if not current_path:
        print("エラー: ディレクトリパスが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        # ファイルパスを正規化
        file_path = normalize_path(file_path)
        
        # 絶対パスか相対パスかを判定
        if os.path.isabs(file_path):
            full_path = file_path
        else:
            full_path = os.path.join(current_path, file_path).replace('\\', '/')
            
        print(f"ファイル '{full_path}' を読み込み中...")
        
        # 全エントリリストから対象のエントリを見つける
        entry_info = find_entry_by_path(all_entries, full_path)
        
        if not entry_info:
            print(f"ファイル '{file_path}' に一致するエントリが見つかりません")
            print(f"全エントリ数: {len(all_entries)}")
            
            # 部分一致検索を試みる
            possibles = []
            search_name = os.path.basename(file_path).lower()
            for entry in all_entries:
                if search_name in entry.name.lower() and entry.type == EntryType.FILE:
                    possibles.append(entry)
                    
            if possibles:
                print(f"\n類似ファイル候補が見つかりました ({len(possibles)}件):")
                for i, entry in enumerate(possibles, 1):
                    print(f"{i}. {entry.path} ({entry.size:,} バイト)")
                
                choice = input("\n抽出するファイル番号を選択してください (キャンセルはEnter): ")
                if choice.isdigit() and 1 <= int(choice) <= len(possibles):
                    entry_info = possibles[int(choice) - 1]
                    print(f"ファイル '{entry_info.path}' を選択しました")
                else:
                    print("操作をキャンセルしました")
                    return False
            else:
                print("類似するファイルも見つかりませんでした")
                return False
        
        if entry_info.type == EntryType.DIRECTORY:
            print(f"指定されたパスはディレクトリです: {file_path}")
            print(f"ディレクトリの内容を表示するには 'L {file_path}' コマンドを使用してください。")
            return False
        
        # ファイルの内容を読み込む
        start_time = time.time()
        content = handler.read_archive_file(current_path, entry_info.rel_path)
        read_time = time.time() - start_time
        
        if content is None:
            print(f"エラー: ファイル '{file_path}' が見つからないか、読み込めませんでした。")
            return False
            
        # ファイルのバイナリデータに関する情報を表示
        print(f"ファイルサイズ: {len(content):,} バイト (読み込み時間: {read_time:.3f}秒)")
        
        # エンコーディング推定
        encoding = None
        is_text = True
        
        # バイナリデータの最初の数バイトを確認
        if len(content) > 2:
            # BOMでエンコーディングをチェック
            if content.startswith(b'\xef\xbb\xbf'):
                encoding = 'utf-8-sig'
                print(f"エンコーディング検出: UTF-8 BOMあり")
            elif content.startswith(b'\xff\xfe'):
                encoding = 'utf-16-le'
                print(f"エンコーディング検出: UTF-16 LE")
            elif content.startswith(b'\xfe\xff'):
                encoding = 'utf-16-be'
                print(f"エンコーディング検出: UTF-16 BE")
                
        # バイナリか判定
        binary_bytes = 0
        ascii_bytes = 0
        for byte in content[:min(1000, len(content))]:
            # ASCII範囲外のバイト値が多い場合やNULLバイトがあればバイナリとみなす
            if byte < 9 or (byte > 13 and byte < 32) or byte >= 127:
                binary_bytes += 1
            elif 32 <= byte <= 126:
                ascii_bytes += 1
        
        # バイナリ判定の基準: 非ASCII文字が一定割合以上
        binary_ratio = binary_bytes / max(1, binary_bytes + ascii_bytes)
        is_text = binary_ratio < 0.1  # 10%以下なら文字列と判断
                
        # テキストファイルとして読み込めるか試す
        if is_text:
            if not encoding:
                # 一般的なエンコーディングでの変換を試みる
                encodings = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp932']
                for enc in encodings:
                    try:
                        content.decode(enc)
                        encoding = enc
                        print(f"エンコーディング自動検出: {encoding}")
                        break
                    except:
                        pass
        
        # 抽出したファイルを保存するか尋ねる
        save_path = os.path.basename(file_path)
        answer = input(f"ファイルをローカルに保存しますか？ (Y/n, デフォルト: {save_path}): ")
        
        if answer.lower() != 'n':
            if answer and answer.lower() != 'y' and answer != save_path:
                save_path = answer
                
            # ファイルを保存
            with open(save_path, 'wb') as f:
                f.write(content)
                
            print(f"ファイルを保存しました: {save_path} ({len(content):,} バイト)")
            
        # テキストの場合は内容を表示
        if is_text and encoding:
            print(f"\n===== ファイル内容 (エンコーディング: {encoding}) =====")
            
            try:
                text_content = content.decode(encoding)
                # 長いテキストは省略表示
                max_chars = 500
                if len(text_content) > max_chars:
                    print(text_content[:max_chars] + "...(省略)")
                else:
                    print(text_content)
            except Exception as e:
                print(f"テキスト表示エラー: {e}")
        # 画像ファイルの場合は追加情報を表示
        elif os.path.splitext(file_path)[1].lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            print("\n===== 画像情報 =====")
            try:
                # 一時ファイルに保存して画像として開く
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_path)[1]) as temp_file:
                    temp_path = temp_file.name
                    temp_file.write(content)
                
                try:
                    with Image.open(temp_path) as img:
                        print(f"画像形式: {img.format}")
                        print(f"サイズ: {img.width} x {img.height} ピクセル")
                        print(f"モード: {img.mode}")
                        
                        # EXIF情報があれば表示
                        if hasattr(img, '_getexif') and img._getexif():
                            print("EXIF情報:")
                            exif = img._getexif()
                            exif_tags = {
                                271: "メーカー",
                                272: "機種",
                                306: "撮影日時",
                                36867: "撮影日時(デジタル)",
                                33434: "露出時間",
                                33437: "F値",
                            }
                            for tag_id, tag_name in exif_tags.items():
                                if tag_id in exif:
                                    print(f"  {tag_name}: {exif[tag_id]}")
                except UnidentifiedImageError:
                    print("画像として読み込めませんでした。データが破損しているか、サポートされていない形式です。")
                except Exception as e:
                    print(f"画像分析中にエラーが発生しました: {e}")
                finally:
                    # 一時ファイルを削除
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
            except Exception as e:
                print(f"画像ファイル処理でエラーが発生しました: {e}")
        
        return True
    except Exception as e:
        print(f"エラー: ファイルの抽出に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def find_file_in_directory(name: str) -> bool:
    """
    ファイル名またはパターンでディレクトリ内を検索
    
    Args:
        name: 検索するファイル名またはパターン
        
    Returns:
        ファイルが見つかった場合はTrue、そうでない場合はFalse
    """
    global current_path, all_entries, handler
    
    if not current_path:
        print("エラー: ディレクトリパスが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        print(f"ディレクトリ内で '{name}' を検索中...")
        
        # 検索条件に一致するファイルを検索
        found_files = []
        search_lower = name.lower()
        
        for entry in all_entries:
            # ファイル名が検索パターンを含むか確認
            if search_lower in entry.name.lower():
                found_files.append(entry)
                
        # 結果を表示
        if found_files:
            print(f"\n検索結果: {len(found_files)} 件のファイルが見つかりました")
            print("{:<60} {:<10} {:<20}".format("パス", "サイズ", "種類"))
            print("-" * 90)
            
            for entry in found_files:
                type_str = "DIR" if entry.type == EntryType.DIRECTORY else "ARC" if entry.type == EntryType.ARCHIVE else "FILE"
                size_str = "-" if entry.type == EntryType.DIRECTORY else f"{entry.size:,}"
                
                # パスを表示（長すぎる場合は省略）
                if len(entry.path) > 59:
                    display_path = "..." + entry.path[-56:]
                else:
                    display_path = entry.path
                
                print("{:<60} {:<10} {:<20}".format(
                    display_path, size_str, type_str
                ))
                
            # ファイルを抽出するか尋ねる
            if len(found_files) == 1:
                answer = input("\nこのファイルを抽出/表示しますか？ (y/N): ")
                if answer.lower() == 'y':
                    return extract_file(found_files[0].path)
            else:
                # 複数ファイルの場合は選択できるようにする
                answer = input("\nファイルを選択して抽出/表示しますか？ (y/N): ")
                if answer.lower() == 'y':
                    file_index = input(f"ファイル番号を入力してください (1-{len(found_files)}): ")
                    try:
                        index = int(file_index) - 1
                        if 0 <= index < len(found_files):
                            return extract_file(found_files[index].path)
                        else:
                            print(f"無効なインデックス: {index + 1}")
                    except ValueError:
                        print("数値を入力してください")
                
            return True
        else:
            print(f"検索条件に一致するファイルが見つかりませんでした: {name}")
            return False
                
    except Exception as e:
        print(f"エラー: ファイル検索中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_absolute_path(path: str) -> bool:
    """
    パスの絶対パスを表示する
    
    Args:
        path: 絶対パスを取得するパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_path, handler
    
    try:
        # 空のパスの場合は現在のパスを使用
        if not path:
            if current_path:
                path = current_path
            else:
                path = os.getcwd()
        
        # パスを正規化
        norm_path = normalize_path(path)
        
        # 絶対パスを取得
        if os.path.isabs(norm_path):
            abs_path = norm_path
        else:
            # 現在のパスからの相対パスを絶対パスに変換
            if current_path:
                abs_path = os.path.join(current_path, norm_path).replace('\\', '/')
            else:
                abs_path = os.path.abspath(norm_path).replace('\\', '/')
        
        print(f"\n入力パス: {path}")
        print(f"正規化パス: {norm_path}")
        print(f"絶対パス: {abs_path}")
        
        # パスが存在するか確認
        if os.path.exists(abs_path):
            print(f"パスの状態: 存在します")
            
            if os.path.isdir(abs_path):
                print(f"パスの種類: ディレクトリ")
                # ディレクトリの場合は内容を数える
                try:
                    count = len(os.listdir(abs_path))
                    print(f"内容: {count} 個のエントリを含みます")
                except PermissionError:
                    print("内容: アクセス権限がありません")
            elif os.path.isfile(abs_path):
                print(f"パスの種類: ファイル")
                print(f"サイズ: {os.path.getsize(abs_path):,} バイト")
                mtime = os.path.getmtime(abs_path)
                print(f"更新日時: {datetime.fromtimestamp(mtime)}")
            else:
                print(f"パスの種類: その他 (シンボリックリンクなど)")
        else:
            print(f"パスの状態: 存在しません")
        
        return True
    except Exception as e:
        print(f"エラー: パスの処理中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_normalized_path(path: str) -> bool:
    """
    パスを正規化して表示する
    
    Args:
        path: 正規化するパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_path, handler
    
    try:
        # 空のパスの場合は現在のパスを使用
        if not path:
            if current_path:
                path = current_path
            else:
                path = os.getcwd()
        
        print(f"\n入力パス: {path}")
        
        # パスの各種表現を表示 - バックスラッシュの処理を修正
        forward_slash = path.replace('\\', '/')
        backslash = path.replace('/', '\\')
        print(f"正規化パス (スラッシュ): {forward_slash}")
        print(f"正規化パス (バックスラッシュ): {backslash}")
        
        # Pathオブジェクトを使用した正規化
        try:
            pathobj = Path(path)
            print(f"Pathオブジェクト: {pathobj}")
            print(f"正規化Pathオブジェクト: {pathobj.resolve()}")
        except:
            pass
        
        # OS依存のパス操作
        print(f"os.path.normpath: {os.path.normpath(path)}")
        
        # 絶対パス
        if not os.path.isabs(path):
            # 現在のパスから絶対パスを計算
            if current_path:
                abs_path = os.path.join(current_path, path)
            else:
                abs_path = os.path.abspath(path)
            print(f"絶対パス: {abs_path}")
        
        # ハンドラの正規化メソッドを使用
        norm_path = handler.normalize_path(path)
        print(f"ハンドラ正規化パス: {norm_path}")
        
        return True
    except Exception as e:
        print(f"エラー: パスの正規化中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def switch_handler_mode() -> bool:
    """
    ハンドラモードを切り替える (FS <-> MFS)
    
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global handler_type, handler, current_path, all_entries
    
    try:
        # 現在のハンドラ情報を表示
        print(f"\n現在のハンドラタイプ: {handler_type}")
        print(f"ハンドラクラス: {handler.__class__.__name__}")
        
        # 現在と異なるハンドラタイプに切り替え
        if handler_type == "FS":
            # FSからMFSに切り替え
            print("\nMultiThreadedFileSystemHandlerに切り替えます...")
            handler = MultiThreadedFileSystemHandler()
            handler_type = "MFS"
            
            # マルチスレッド設定情報を表示
            if hasattr(handler, 'max_workers'):
                print(f"最大ワーカー数: {handler.max_workers}")
            if hasattr(handler, 'MIN_ENTRIES_FOR_THREADING'):
                print(f"スレッド化最小エントリ数: {handler.MIN_ENTRIES_FOR_THREADING}")
        else:
            # MFSからFSに切り替え
            print("\nFileSystemHandlerに切り替えます...")
            handler = FileSystemHandler()
            handler_type = "FS"
        
        # 現在のパスが設定されていれば、新しいハンドラにも設定
        if current_path:
            handler.current_path = current_path
            print(f"現在のパスを設定: {current_path}")
            
            # 全エントリリストを更新
            print("ディレクトリ内のすべてのエントリを取得しています...")
            start_time = time.time()
            all_entries = handler.list_all_entries(current_path)
            elapsed_time = time.time() - start_time
            print(f"{len(all_entries)}個のエントリを取得しました (所要時間: {elapsed_time:.2f}秒)")
        
        # ハンドラの情報表示
        supported_ext = handler.supported_extensions
        can_arch = handler.can_archive()
        print(f"サポートする拡張子: {supported_ext}")
        print(f"アーカイバ機能: {'あり' if can_arch else 'なし'}")
        
        # ハンドラ固有の情報を表示
        if handler_type == "MFS" and hasattr(handler, 'get_performance_stats'):
            stats = handler.get_performance_stats()
            print("\nパフォーマンス設定:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        
        print(f"\nハンドラタイプを {handler_type} に切り替えました")
        return True
        
    except Exception as e:
        print(f"エラー: ハンドラの切り替え中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_root_directories() -> bool:
    """
    ルートディレクトリ（ドライブ一覧）を表示する
    
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    try:
        print("\nルートディレクトリ/ドライブ一覧:")
        
        # Windowsの場合はドライブ一覧を表示
        if os.name == 'nt':
            import ctypes
            
            drives = []
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in range(65, 91):  # A-Z
                if bitmask & 1:
                    drives.append(chr(letter) + ":\\")
                bitmask >>= 1
                
            print("{:<10} {:<15} {:<15} {:<15}".format(
                "ドライブ", "種類", "ラベル", "空き容量/合計"
            ))
            print("-" * 60)
            
            for drive in drives:
                try:
                    # ドライブの種類を取得
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                    type_names = {
                        0: "不明",
                        1: "ルート無し",
                        2: "リムーバブル",
                        3: "固定ディスク",
                        4: "ネットワーク",
                        5: "CD-ROM",
                        6: "RAM ディスク"
                    }
                    type_name = type_names.get(drive_type, "不明")
                    
                    # ドライブ情報（ラベルと空き容量）を取得
                    drive_label = ""
                    free_bytes = 0
                    total_bytes = 0
                    
                    if os.path.exists(drive):
                        # ボリュームラベルを取得
                        buf = ctypes.create_unicode_buffer(1024)
                        filesys_buf = ctypes.create_unicode_buffer(1024)
                        ctypes.windll.kernel32.GetVolumeInformationW(
                            drive, buf, 1024, None, None, None, filesys_buf, 1024
                        )
                        drive_label = buf.value
                        
                        # 空き容量を取得
                        free_bytes = ctypes.c_ulonglong(0)
                        total_bytes = ctypes.c_ulonglong(0)
                        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                            drive, None, ctypes.byref(total_bytes), ctypes.byref(free_bytes)
                        )
                        free_gb = free_bytes.value / (1024**3)
                        total_gb = total_bytes.value / (1024**3)
                        space_info = f"{free_gb:.1f}GB/{total_gb:.1f}GB"
                    else:
                        drive_label = "アクセス不可"
                        space_info = "-"
                        
                    print("{:<10} {:<15} {:<15} {:<15}".format(
                        drive, type_name, drive_label, space_info
                    ))
                    
                except:
                    print("{:<10} {:<15} {:<15} {:<15}".format(
                        drive, "エラー", "-", "-"
                    ))
        else:
            # UNIXライクなシステムの場合は/を表示
            print("/ (ルートディレクトリ)")
            
            # マウントポイント情報があれば表示
            try:
                with open('/proc/mounts', 'r') as f:
                    print("\nマウントポイント:")
                    print("{:<30} {:<15} {:<20}".format(
                        "パス", "ファイルシステム", "オプション"
                    ))
                    print("-" * 70)
                    
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 3:
                            device, mount_point, fs_type = parts[0], parts[1], parts[2]
                            options = parts[3] if len(parts) > 3 else ""
                            
                            # 一般的なファイルシステムのみ表示
                            if fs_type in ['ext4', 'ext3', 'ext2', 'xfs', 'btrfs', 'ntfs', 'vfat', 'exfat', 'nfs']:
                                print("{:<30} {:<15} {:<20}".format(
                                    mount_point[:29], fs_type, options[:19]
                                ))
            except:
                # /proc/mountsがない場合
                pass
                
        return True
    except Exception as e:
        print(f"エラー: ルートディレクトリの取得中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


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
    if (args_str.startswith('"') and args_str.endswith('"')) or (args_str.startswith("'") and args_str.endswith("'")):
        # 引用符を除去
        return args_str[1:-1]
    
    return args_str


def main():
    """メインのCLIループ"""
    global debug_mode, current_path, handler_type
    
    print_banner()
    print_help()
    
    # コマンドループ
    while True:
        try:
            # ハンドラタイプをプロンプトに含める
            cmd_line = input(f"\nコマンド({handler_type})> ").strip()
            
            if not cmd_line:
                continue
                
            cmd = cmd_line[0].upper()
            args = cmd_line[1:].strip()
            
            if cmd == 'Q':  # 終了
                print("プログラムを終了します...")
                break
                
            elif cmd == 'H':  # ヘルプ表示
                print_help()
                
            elif cmd == 'S':  # ディレクトリパス設定
                path = parse_command_args(args)
                if not path:
                    print("エラー: ディレクトリパスが指定されていません。\n使用法: S <path>")
                else:
                    set_current_path(path)
                    
            elif cmd == 'L':  # ディレクトリ内容一覧表示
                path = parse_command_args(args)
                list_directory_contents(path)
                
            elif cmd == 'E':  # ファイル抽出/表示
                path = parse_command_args(args)
                if not path:
                    print("エラー: ファイルパスが指定されていません。\n使用法: E <path>")
                else:
                    extract_file(path)
                    
            elif cmd == 'I':  # ファイル検索
                name = parse_command_args(args)
                if not name:
                    print("エラー: 検索文字列が指定されていません。\n使用法: I <name>")
                else:
                    find_file_in_directory(name)
                    
            elif cmd == 'A':  # 絶対パス表示
                path = parse_command_args(args)
                show_absolute_path(path)
                
            elif cmd == 'U':  # パス正規化表示
                path = parse_command_args(args)
                show_normalized_path(path)
                    
            elif cmd == 'M':  # ハンドラモード切替
                switch_handler_mode()
                    
            elif cmd == 'D':  # デバッグモード切替
                debug_mode = not debug_mode
                print(f"デバッグモード: {'オン' if debug_mode else 'オフ'}")
                
            elif cmd == 'R':  # ルートディレクトリ一覧表示
                show_root_directories()
                
            else:
                print(f"未知のコマンド: {cmd}。'H'と入力してヘルプを表示してください。")
                
        except KeyboardInterrupt:
            print("\n中断されました。終了するには 'Q' を入力してください。")
        except EOFError:
            print("\n終了します。")
            break
        except Exception as e:
            print(f"エラー: {e}")
            if debug_mode:
                traceback.print_exc()


if __name__ == "__main__":
    # コマンドライン引数があれば処理
    parser = argparse.ArgumentParser(description="ファイルシステムハンドラのテストツール")
    parser.add_argument('-p', '--path', help="開始ディレクトリのパス")
    parser.add_argument('-d', '--debug', action='store_true', help="デバッグモードを有効化")
    parser.add_argument('-m', '--mfs', action='store_true', help="MultiThreadedFileSystemHandlerを使用")
    
    args = parser.parse_args()
    
    if args.debug:
        debug_mode = True
        print("デバッグモードを有効化しました。")
    
    # MFSハンドラの使用が指定されていれば切り替え
    if args.mfs:
        try:
            handler = MultiThreadedFileSystemHandler()
            handler_type = "MFS"
            print("MultiThreadedFileSystemHandlerを使用します。")
        except Exception as e:
            print(f"MFSハンドラの初期化に失敗しました: {e}")
            print("FileSystemHandlerを使用します。")
    
    # パスが指定されていれば設定
    if args.path: 
        set_current_path(args.path)
    
    # メインループを実行
    main()
