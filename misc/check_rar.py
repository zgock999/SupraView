#!/usr/bin/env python3
"""
RARハンドラのテスト用コマンドラインツール

このツールはRARファイルの操作をテストするための簡易的なCLIを提供します。
"""

import os
import sys
import io
import argparse
import traceback
import time
from typing import List, Optional, Dict, Any

# パスの追加（親ディレクトリをインポートパスに含める）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

#try:
# RARハンドラクラスをインポート
from arc.handler.rar_handler import RarHandler, RARFILE_AVAILABLE
from arc.arc import EntryInfo, EntryType
from arc.path_utils import normalize_path, try_decode_path, fix_garbled_filename
#except ImportError as e:
#    print(f"エラー: RARハンドラのインポートに失敗しました: {e}")
#    sys.exit(1)

# グローバル変数
current_archive: bytes = None
current_archive_path: str = None
handler = RarHandler()
debug_mode = False
# 全エントリリストを保持する変数を追加
all_entries_from_file: List[EntryInfo] = []
all_entries_from_memory: List[EntryInfo] = []


def print_banner():
    """アプリケーションバナーを表示"""
    print("=" * 70)
    print("RARハンドラ テストツール")
    print("このツールはRARファイルの操作と検証のためのコマンドラインインターフェースを提供します")
    print("=" * 70)


def print_help():
    """コマンドヘルプを表示"""
    print("\n使用可能なコマンド:")
    print("  S <path>      - アーカイブパスを設定（Set archive path）")
    print("                  空白を含むパスは \"path/to file.rar\" のように引用符で囲みます")
    print("  L [path]      - アーカイブ内のファイル/ディレクトリを一覧表示（List archive contents）")
    print("  E <path>      - アーカイブからファイルを抽出（Extract file from archive）")
    print("                  空白を含むパスは引用符で囲みます")
    print("  B [path]      - バイトモードテスト（bytes-mode test）")
    print("                  オプションでパスを指定すると、そのファイルに対してファイル/メモリ比較テスト実行")
    print("  D             - デバッグモードの切替（Toggle debug mode）")
    print("  H             - このヘルプを表示")
    print("  Q             - 終了")
    print("")


def check_rarfile_availability():
    """rarfileパッケージが利用可能かチェックする"""
    if not RARFILE_AVAILABLE:
        print("エラー: rarfileパッケージがインストールされていません。")
        print("pip install rarfile を実行してインストールしてください。")
        return False
    return True


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


def set_archive_path(path: str) -> bool:
    """
    現在のアーカイブパスを設定する
    
    Args:
        path: アーカイブファイルへのパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive, current_archive_path, all_entries_from_file, all_entries_from_memory
    
    # パスを正規化
    path = normalize_path(path)
    
    if not os.path.exists(path):
        print(f"エラー: ファイルが見つかりません: {path}")
        return False
        
    if not os.path.isfile(path):
        print(f"エラー: 指定されたパスはファイルではありません: {path}")
        return False
        
    try:
        # 古い全エントリリストをクリア
        all_entries_from_file = []
        all_entries_from_memory = []
        
        # アーカイブファイルを読み込む
        with open(path, 'rb') as f:
            current_archive = f.read()
        current_archive_path = path
        print(f"アーカイブを設定: {path} ({len(current_archive)} バイト)")
        
        # RARファイルとして開けるかテスト
        if not RARFILE_AVAILABLE:
            print("警告: rarfileパッケージがインストールされていないため、詳細検証ができません")
        else:
            # RARハンドラの基本機能をテスト
            can_handle = handler.can_handle(path)
            print(f"RARハンドラがこのファイルを処理できるか: {can_handle}")
            
            if can_handle:
                # エントリリストを取得してキャッシュ
                all_entries_from_file = handler.list_entries(path)
                print(f"エントリ検出: {len(all_entries_from_file)} 個")
                
                # メモリからも試す
                if handler.can_handle_bytes(current_archive, path):
                    print(f"バイトデータからの処理も可能です")
                    all_entries_from_memory = handler.list_entries_from_bytes(current_archive)
                    print(f"メモリからのエントリ検出: {len(all_entries_from_memory)} 個")
                else:
                    print(f"バイトデータからの処理はサポートされていません")
        
        return True
    except Exception as e:
        print(f"エラー: ファイルの読み込みに失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def list_archive_contents(internal_path: str = "") -> bool:
    """
    アーカイブの内容を一覧表示する
    
    Args:
        internal_path: アーカイブ内のパス（指定しない場合はルート）
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive, current_archive_path, all_entries_from_file, all_entries_from_memory
    
    if not current_archive_path:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        if debug_mode:
            print(f"キャッシュされたエントリ数: {len(all_entries_from_file)} (ファイル), {len(all_entries_from_memory)} (メモリ)")
        
        # 内部パスを正規化
        if internal_path:
            internal_path = normalize_path(internal_path)
            
            # 内部パスがディレクトリかどうかを確認し、必要に応じて末尾にスラッシュを追加
            if not internal_path.endswith('/'):
                # 既存のエントリ情報からディレクトリかどうかを判定
                dir_entry = None
                test_path = f"{internal_path}/"
                for entry in all_entries_from_file:
                    if entry.path.endswith(test_path) or entry.name == internal_path and entry.type == EntryType.DIRECTORY:
                        dir_entry = entry
                        break
                
                if dir_entry:
                    internal_path += '/'
                    if debug_mode:
                        print(f"内部パスをディレクトリとして正規化: {internal_path}")
        
        # キャッシュされたエントリリストを使用してフィルタリング
        entries = []
        dir_seen = set()  # 既に処理したディレクトリを記録
        
        # 対象ディレクトリのパスを構築
        target_path = internal_path if internal_path else ""
        
        if debug_mode:
            print(f"検索対象パス: '{target_path}'")
            
        for entry in all_entries_from_file:
            if debug_mode:
                print(f"処理中のエントリ: パス={entry.path}, 名前={entry.name}, タイプ={entry.type}")
                
            # ルートの場合はすべてのトップレベルエントリを表示
            if not target_path:
                # パスの最初の部分だけを抽出
                parts = entry.path.split('/')
                if len(parts) == 1:  # トップレベルファイル
                    entries.append(entry)
                elif len(parts) > 1:  # サブディレクトリ内のファイル
                    dir_name = parts[0]
                    if dir_name and dir_name not in dir_seen:
                        dir_seen.add(dir_name)
                        # ディレクトリエントリを作成
                        dir_entry = EntryInfo(
                            name=dir_name,
                            path=dir_name,
                            size=0,
                            modified_time=None,
                            type=EntryType.DIRECTORY
                        )
                        entries.append(dir_entry)
            else:
                # 特定のディレクトリ内のエントリを表示
                if entry.path.startswith(target_path):
                    # 相対パスを計算 (ターゲットパスより後の部分)
                    rel_path = entry.path[len(target_path):]
                    
                    if not rel_path:
                        # 指定したディレクトリ自体は除外
                        continue
                        
                    # 直下のみ対象（サブディレクトリの中は含めない）
                    path_parts = rel_path.split('/')
                    
                    if len(path_parts) == 1:  # 直下のファイル
                        entries.append(entry)
                    elif len(path_parts) > 1:  # サブディレクトリ内のファイル
                        dir_name = path_parts[0]
                        if dir_name and dir_name not in dir_seen:
                            dir_seen.add(dir_name)
                            
                            # ディレクトリエントリを作成
                            dir_path = f"{target_path}{dir_name}" if target_path.endswith('/') else f"{target_path}/{dir_name}"
                            dir_entry = EntryInfo(
                                name=dir_name,
                                path=dir_path,
                                size=0,
                                modified_time=None,
                                type=EntryType.DIRECTORY
                            )
                            entries.append(dir_entry)
        
        if not entries:
            # キャッシュからエントリが見つからない場合、ハンドラに直接問い合わせてみる
            if debug_mode:
                print("キャッシュからエントリが見つからないため、ハンドラに直接問い合わせます")
            
            # 内部パスのみを使用して問い合わせ
            entries = handler.list_entries(current_archive_path, internal_path)
            
            if not entries:
                print(f"アーカイブ内にエントリがないか、指定されたパス '{internal_path}' が見つかりません。")
                return False
        
        # エントリを表示
        print("\nアーカイブの内容:")
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
        print(f"エラー: アーカイブ内容の一覧取得に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


# 新しい共通関数を追加
def find_entry_by_path(file_path: str) -> Optional[EntryInfo]:
    """
    全エントリリストから特定パスのエントリを検索する
    
    Args:
        file_path: 検索するファイルパス
    
    Returns:
        見つかったエントリ情報、または見つからない場合はNone
    """
    global all_entries_from_file, all_entries_from_memory
    
    if not all_entries_from_file and not all_entries_from_memory:
        return None
        
    # パスを正規化
    norm_path = normalize_path(file_path)
    file_name = os.path.basename(norm_path)
    
    # デバッグ出力
    if debug_mode:
        print(f"エントリ検索: パス={norm_path}, ファイル名={file_name}")
    
    # まずはファイルから取得したエントリリストで検索
    if all_entries_from_file:
        # 1. 正確なパス一致を試行
        for entry in all_entries_from_file:
            if normalize_path(entry.path) == norm_path:
                if debug_mode:
                    print(f"完全パス一致でエントリを見つけました: {entry.path}")
                return entry
        
        # 2. ファイル名だけの一致を試行
        for entry in all_entries_from_file:
            if entry.name == file_name and entry.type == EntryType.FILE:
                if debug_mode:
                    print(f"ファイル名一致でエントリを見つけました: {entry.path}")
                return entry
    
    # メモリから取得したエントリリストでも検索
    if all_entries_from_memory:
        # 1. 正確なパス一致を試行
        for entry in all_entries_from_memory:
            if normalize_path(entry.path) == norm_path:
                if debug_mode:
                    print(f"メモリ: 完全パス一致でエントリを見つけました: {entry.path}")
                return entry
        
        # 2. ファイル名だけの一致を試行
        for entry in all_entries_from_memory:
            if entry.name == file_name and entry.type == EntryType.FILE:
                if debug_mode:
                    print(f"メモリ: ファイル名一致でエントリを見つけました: {entry.path}")
                return entry
    
    if debug_mode:
        print(f"一致するエントリが見つかりませんでした: {file_path}")
        
    return None


def extract_archive_file(file_path: str) -> bool:
    """
    アーカイブからファイルを抽出する
    
    Args:
        file_path: アーカイブ内のファイルパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive, current_archive_path
    
    if not current_archive_path:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        # ファイルパスを正規化
        file_path = normalize_path(file_path)
        
        print(f"ファイル '{file_path}' を抽出中...")
        
        # 1. 直接read_archive_fileを試す
        print("1. read_archive_fileでの直接読み込みを試行...")
        content = None
        success_path = None
        
        try:
            content = handler.read_archive_file(current_archive_path, file_path)
            if content is not None:
                print(f"✅ read_archive_file での読み込みに成功しました！")
                success_path = file_path
            else:
                print("❌ read_archive_fileでの読み込みに失敗しました")
        except Exception as e:
            print(f"❌ read_archive_fileでの読み込みエラー: {e}")
            if debug_mode:
                traceback.print_exc()
        
        # 2. 失敗した場合は、エントリリストから一致するものを探して再試行
        if content is None:
            print("\n2. エントリリストから一致するファイルを検索...")
            
            basename = os.path.basename(file_path)
            matching_entries = []
            
            for entry in all_entries_from_file:
                if entry.name == basename or entry.path.endswith(file_path):
                    matching_entries.append(entry)
            
            if matching_entries:
                print(f"{len(matching_entries)}個の一致するエントリが見つかりました")
                
                for i, entry in enumerate(matching_entries):
                    print(f"エントリ候補 {i+1}: 名前={entry.name}, パス={entry.path}")
                    
                    # このエントリのパスで再試行
                    try:
                        entry_content = handler.read_archive_file(current_archive_path, entry.path)
                        if entry_content is not None:
                            print(f"✅ エントリパス '{entry.path}' での読み込みに成功しました！")
                            content = entry_content
                            success_path = entry.path
                            break
                        else:
                            print(f"❌ エントリパス '{entry.path}' での読み込みに失敗")
                    except Exception as e:
                        print(f"❌ エントリパス '{entry.path}' での読み込みエラー: {e}")
            else:
                print("一致するエントリが見つかりませんでした")
        
        # 3. それでも失敗する場合はバックアップとしてメモリからの読み込みを試す
        # このステップはディバッグ目的でのみ実行し、成功/失敗を明確に表示
        if content is None and current_archive:
            print("\n3. バックアップ手段: メモリからの読み込みを試行...")
            
            try:
                # メモリからファイルを読み込む
                memory_content = handler.read_file_from_bytes(current_archive, file_path)
                if memory_content is not None:
                    print(f"✅ メモリから読み込みに成功しました！（※これはバックアップ手段です）")
                    content = memory_content
                    success_path = file_path + " (メモリから)"
                else:
                    print("❌ メモリからの読み込みも失敗しました")
            except Exception as e:
                print(f"❌ メモリからの読み込みエラー: {e}")
                if debug_mode:
                    traceback.print_exc()
        
        if content is None:
            print("❌ エラー: すべての方法でファイル読み込みに失敗しました。")
            return False
            
        # 成功したパスとファイルサイズを表示
        print(f"\n最終的に使用したパス: '{success_path}'")
        print(f"ファイルサイズ: {len(content):,} バイト")
        
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
                        print(f"エンコーディング検出: {encoding}")
                        break
                    except UnicodeDecodeError:
                        pass
            
            print(f"ファイルタイプ: テキストファイル ({encoding or '不明なエンコーディング'})")
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
                
            print(f"ファイルタイプ: {file_type}")
        
        # 抽出したファイルを保存するか尋ねる
        save_path = os.path.basename(file_path)
        answer = input(f"ファイルをローカルに保存しますか？ (Y/n, デフォルト: {save_path}): ")
        
        if answer.lower() != 'n':
            # 保存パスの指定があれば使用
            if answer and answer.lower() != 'y' and answer != save_path:
                save_path = answer
                
            # ファイルを保存
            try:
                with open(save_path, 'wb') as f:
                    f.write(content)
                print(f"✅ ファイルを保存しました: {save_path} ({len(content):,} バイト)")
            except Exception as e:
                print(f"❌ ファイル保存エラー: {e}")
                if debug_mode:
                    traceback.print_exc()
                
        # テキストの場合は内容を表示
        if is_text and encoding:
            print(f"\n===== ファイル内容 (エンコーディング: {encoding}) =====")
            
            try:
                text = content.decode(encoding)
                # 長いテキストは省略表示
                max_chars = 500
                if len(text) > max_chars:
                    print(text[:max_chars] + "...(省略)")
                else:
                    print(text)
            except Exception as e:
                print(f"テキスト表示エラー: {e}")
                
        # テスト完了
        print("\n抽出テスト完了！")
        return True
    except Exception as e:
        print(f"エラー: ファイルの抽出に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def test_bytes_mode(file_path: str = None):
    """
    バイトモードのテスト
    
    Args:
        file_path: テスト対象のファイルパス（オプション）
    """
    global current_archive, current_archive_path
    
    if file_path:
        # ファイルパスが存在するファイルなら通常のテスト
        if os.path.exists(file_path) and os.path.isfile(file_path):
            test_specific_file(file_path)
            return
        # アーカイブ内のパスの場合
        elif current_archive_path:
            test_archive_file(file_path)
            return
        else:
            print(f"エラー: 指定されたパス '{file_path}' は存在しないか、アーカイブが設定されていません。")
            return
    
    if not current_archive:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    print("\nバイトモードテスト開始")
    print("バイトデータからの処理ベンチマーク")
    print("-" * 40)
    
    try:
        # バイトデータからの処理をテスト
        import time
        
        # 1. ハンドラがバイトデータを処理できるか確認
        start_time = time.time()
        can_handle = handler.can_handle_bytes(current_archive, current_archive_path)
        handle_time = time.time() - start_time
        
        print(f"バイトデータの処理可否: {can_handle} ({handle_time:.6f}秒)")
        
        if not can_handle:
            print("このハンドラはバイトデータを直接処理できません。")
            return False
            
        # 2. エントリ一覧のテスト
        start_time = time.time()
        entries = handler.list_entries_from_bytes(current_archive)
        list_time = time.time() - start_time
        
        print(f"エントリ数: {len(entries)} ({list_time:.6f}秒)")
        
        # 3. ファイル読み込みテスト
        if entries:
            # テスト用のファイルを選択（最初に見つかったファイル）
            test_file = None
            for entry in entries:
                if entry.type == EntryType.FILE:
                    test_file = entry.name
                    break
            
            if test_file:
                start_time = time.time()
                content = handler.read_file_from_bytes(current_archive, test_file)
                read_time = time.time() - start_time
                
                if content:
                    print(f"テストファイル読み込み: {test_file} ({len(content)} バイト, {read_time:.6f}秒)")
                else:
                    print(f"テストファイル読み込み失敗: {test_file}")
        
        print("\nバイトモードテスト完了")
        return True
    except Exception as e:
        print(f"エラー: バイトモードテストに失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def test_archive_file(internal_path: str):
    """
    指定されたアーカイブ内のファイルに対してファイル/メモリ比較テストを実行する
    
    Args:
        internal_path: アーカイブ内のファイルパス
    """
    global current_archive, current_archive_path
    
    print(f"\nアーカイブ内ファイルのバイトモードテスト開始: {internal_path}")
    print("-" * 50)
    
    try:
        # ファイルパスを正規化
        internal_path = normalize_path(internal_path)
        
        # アーカイブが設定されているか確認
        if not current_archive_path or not current_archive:
            print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
            return
        
        print(f"対象アーカイブ: {current_archive_path}")
        print(f"内部ファイルパス: {internal_path}")
        
        # 1. 直接read_archive_fileを試す
        print("1. read_archive_fileでの直接読み込みを試行...")
        file_content = None
        success_path = None
        
        import time
        # ファイルからの読み込み速度計測
        file_read_start = time.time()
        try:
            file_content = handler.read_archive_file(current_archive_path, internal_path)
            file_read_time = time.time() - file_read_start
            if file_content is not None:
                print(f"✅ read_archive_file での読み込みに成功しました！({file_read_time:.6f}秒)")
                success_path = internal_path
            else:
                print("❌ read_archive_fileでの読み込みに失敗しました")
        except Exception as e:
            file_read_time = time.time() - file_read_start
            print(f"❌ read_archive_fileでの読み込みエラー: {e} ({file_read_time:.6f}秒)")
            if debug_mode:
                traceback.print_exc()
        
        # 2. 失敗した場合は、エントリリストから一致するものを探して再試行
        if file_content is None:
            print("\n2. エントリリストから一致するファイルを検索...")
            
            basename = os.path.basename(internal_path)
            matching_entries = []
            
            for entry in all_entries_from_file:
                if entry.name == basename or entry.path.endswith(internal_path):
                    matching_entries.append(entry)
            
            if matching_entries:
                print(f"{len(matching_entries)}個の一致するエントリが見つかりました")
                
                for i, entry in enumerate(matching_entries):
                    print(f"エントリ候補 {i+1}: 名前={entry.name}, パス={entry.path}")
                    
                    # このエントリのパスで再試行
                    file_read_start = time.time()
                    try:
                        entry_content = handler.read_archive_file(current_archive_path, entry.path)
                        file_read_time = time.time() - file_read_start
                        if entry_content is not None:
                            print(f"✅ エントリパス '{entry.path}' での読み込みに成功しました！({file_read_time:.6f}秒)")
                            file_content = entry_content
                            success_path = entry.path
                            break
                        else:
                            print(f"❌ エントリパス '{entry.path}' での読み込みに失敗")
                    except Exception as e:
                        file_read_time = time.time() - file_read_start
                        print(f"❌ エントリパス '{entry.path}' での読み込みエラー: {e} ({file_read_time:.6f}秒)")
            else:
                print("一致するエントリが見つかりませんでした")
                file_read_time = 0
        
        # 3. エントリ情報を取得（ファイルサイズなどの情報用）
        entry_info = None
        if success_path:
            # 完全なパスを構築
            full_path = f"{current_archive_path}/{success_path}"
            entry_info = handler.get_entry_info(full_path)
            if entry_info:
                print(f"\nエントリ情報:")
                print(f"  名前: {entry_info.name}")
                print(f"  パス: {entry_info.path}")
                print(f"  サイズ: {entry_info.size}")
                print(f"  タイプ: {entry_info.type}")
        
                if entry_info.type == EntryType.DIRECTORY:
                    print(f"指定されたパスはディレクトリです。ファイル比較テストはスキップします。")
                    return
        
        # 4. メモリからの読み込みを試す（速度比較用）
        print("\n3. メモリからの読み込みを試行...")
        memory_content = None
        
        # メモリからの読み込み速度計測
        memory_read_start = time.time()
        try:
            memory_content = handler.read_file_from_bytes(current_archive, internal_path)
            memory_read_time = time.time() - memory_read_start
            
            if memory_content is not None:
                print(f"✅ メモリから読み込みに成功しました！({memory_read_time:.6f}秒)")
                
                # ファイル読み込みに失敗していた場合はメモリの内容を使用
                if file_content is None:
                    file_content = memory_content
                    success_path = internal_path + " (メモリから)"
            else:
                memory_read_time = time.time() - memory_read_start
                print(f"❌ メモリからの読み込みに失敗 ({memory_read_time:.6f}秒)")
        except Exception as e:
            memory_read_time = time.time() - memory_read_start
            print(f"❌ メモリからの読み込みエラー: {e} ({memory_read_time:.6f}秒)")
            if debug_mode:
                traceback.print_exc()
        
        # 5. ファイルとメモリからの読み込み結果の比較と表示
        if file_content and memory_content:
            print("\n4. 読み込み結果の比較:")
            
            # サイズ比較
            print(f"  ファイル読み込みサイズ: {len(file_content):,} バイト")
            print(f"  メモリ読み込みサイズ: {len(memory_content):,} バイト")
            
            # 内容比較
            if file_content == memory_content:
                print("  ✅ ファイルとメモリの内容は一致しています")
            else:
                print("  ⚠️ ファイルとメモリの内容が一致しません！")
                
                # 最初の不一致箇所を表示
                first_mismatch = -1
                min_len = min(len(file_content), len(memory_content))
                for i in range(min_len):
                    if file_content[i] != memory_content[i]:
                        first_mismatch = i
                        break
                
                if first_mismatch >= 0:
                    print(f"  最初の不一致: {first_mismatch}バイト目")
                    # 不一致部分の前後10バイトをHEX表示
                    start = max(0, first_mismatch - 10)
                    end = min(min_len, first_mismatch + 10)
                    
                    print(f"  ファイル[{start}:{end}]: {file_content[start:end].hex()}")
                    print(f"  メモリ[{start}:{end}]: {memory_content[start:end].hex()}")
            
            # 速度比較
            print("\n5. 読み込み速度の比較:")
            print(f"  ファイルからの読み込み時間: {file_read_time:.6f}秒")
            print(f"  メモリからの読み込み時間: {memory_read_time:.6f}秒")
            
            if file_read_time > 0 and memory_read_time > 0:
                if memory_read_time < file_read_time:
                    speedup = (file_read_time - memory_read_time) / file_read_time * 100
                    print(f"  ⚡ メモリからの読み込みは {speedup:.1f}% 高速です")
                elif file_read_time < memory_read_time:
                    speedup = (memory_read_time - file_read_time) / memory_read_time * 100
                    print(f"  ⚡ ファイルからの読み込みは {speedup:.1f}% 高速です")
                else:
                    print("  読み込み速度は同じです")
        
        if file_content is None:
            print("❌ エラー: すべての方法でファイル読み込みに失敗しました。")
            return
        
        # 6. ファイル情報表示
        print("\n[ファイル情報]")
        print(f"ファイルサイズ: {len(file_content):,} バイト")
        
        # 画像ファイルかどうか判定
        is_image = internal_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'))
        
        if is_image:
            # 画像情報を表示
            try:
                from io import BytesIO
                from PIL import Image
                
                # ファイルデータから画像を読み込む
                img = Image.open(BytesIO(file_content))
                print(f"画像形式: {img.format}")
                print(f"画像サイズ: {img.width}x{img.height} ピクセル")
                print(f"カラーモード: {img.mode}")
                
                # 画像を表示するか確認
                answer = input("\n画像をローカルに保存しますか？ (Y/n, デフォルト: preview.jpg): ")
                
                if answer.lower() != 'n':
                    save_path = "preview.jpg" if not answer or answer.lower() == 'y' else answer
                    try:
                        with open(save_path, 'wb') as f:
                            f.write(file_content)
                        print(f"✅ 画像を保存しました: {save_path}")
                    except Exception as e:
                        print(f"❌ 画像保存エラー: {e}")
            
            except ImportError:
                print("PIL/Pillowモジュールがインストールされていないため、画像情報を表示できません。")
                print("pip install Pillow でインストールできます。")
            except Exception as e:
                print(f"画像処理エラー: {e}")
        
        # バイナリ/テキスト判別
        binary_bytes = 0
        ascii_bytes = 0
        for byte in file_content[:min(1000, len(file_content))]:
            if byte < 9 or (byte > 13 and byte < 32) or byte >= 127:
                binary_bytes += 1
            elif 32 <= byte <= 126:
                ascii_bytes += 1
        
        # バイナリ判定の基準: 非ASCII文字が一定割合以上
        binary_ratio = binary_bytes / max(1, binary_bytes + ascii_bytes)
        is_text = binary_ratio < 0.1  # 10%以下なら文字列と判断
        
        # テキストファイルとして読み込めるか試す
        if is_text:
            encoding = None
            # BOMでエンコーディングをチェック
            if len(file_content) > 2:
                if file_content.startswith(b'\xef\xbb\xbf'):
                    encoding = 'utf-8-sig'
                elif file_content.startswith(b'\xff\xfe'):
                    encoding = 'utf-16-le'
                elif file_content.startswith(b'\xfe\xff'):
                    encoding = 'utf-16-be'
            
            # エンコーディングを検出
            if not encoding:
                for enc in ['utf-8', 'cp932', 'euc-jp', 'latin-1']:
                    try:
                        file_content.decode(enc)
                        encoding = enc
                        print(f"エンコーディング検出: {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue
            
            # テキストの場合は内容を表示
            if encoding:
                print(f"\n===== ファイル内容 (エンコーディング: {encoding}) =====")
                
                try:
                    text_content = file_content.decode(encoding)
                    # 最初の20行または2000文字を表示
                    lines = text_content.splitlines()
                    display_lines = min(20, len(lines))
                    displayed_text = '\n'.join(lines[:display_lines])
                    
                    if len(displayed_text) > 2000:
                        displayed_text = displayed_text[:2000] + "...(省略)..."
                        
                    print(displayed_text)
                        
                    if display_lines < len(lines):
                        print(f"\n(表示制限: {display_lines}/{len(lines)} 行)")
                except Exception as e:
                    print(f"テキスト表示エラー: {e}")
        else:
            # バイナリファイルのタイプ判定
            file_type = "バイナリファイル"
            
            # ファイルの種類を判定
            if file_content.startswith(b'\xff\xd8\xff'):
                file_type = "JPEGイメージ"
            elif file_content.startswith(b'\x89PNG\r\n\x1a\n'):
                file_type = "PNGイメージ"
            elif file_content.startswith(b'GIF8'):
                file_type = "GIFイメージ"
            elif file_content.startswith(b'BM'):
                file_type = "BMPイメージ"
            elif file_content.startswith(b'\x1f\x8b'):
                file_type = "GZIPアーカイブ"
            elif file_content.startswith(b'PK\x03\x04'):
                file_type = "ZIPアーカイブ"
            elif file_content.startswith(b'Rar!\x1a\x07'):
                file_type = "RARアーカイブ"
                
            print(f"ファイルタイプ: {file_type}")
        
        print("\nアーカイブ内ファイルのバイトモードテスト完了")
        
    except Exception as e:
        print(f"エラー: アーカイブ内ファイル比較テストに失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()


def test_specific_file(file_path: str):
    """
    指定されたファイルに対してファイル/メモリ比較テストを実行する
    
    Args:
        file_path: テスト対象のファイルパス
    """
    print(f"\nファイル/メモリ比較テスト開始: {file_path}")
    print("-" * 50)
    
    try:
        # パスを正規化
        file_path = normalize_path(file_path)
        
        # 1. ファイルが存在するか確認
        if not os.path.exists(file_path):
            print(f"エラー: ファイルが見つかりません: {file_path}")
            return
        
        # 2. ファイルを読み込む
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
                print(f"ファイルを読み込みました: {len(file_content):,} バイト")
        except Exception as e:
            print(f"エラー: ファイルの読み込みに失敗しました: {e}")
            return
        
        # 3. ハンドラーがこのファイルを処理できるか確認
        import time
        
        # 3.1 通常のcan_handleチェック
        start_time = time.time()
        can_handle_file = handler.can_handle(file_path)
        file_check_time = time.time() - start_time
        
        # 3.2 バイトデータのcan_handle_bytesチェック
        start_time = time.time()
        can_handle_bytes = handler.can_handle_bytes(file_content, file_path)
        bytes_check_time = time.time() - start_time
        
        print(f"ファイル処理可否: {can_handle_file} ({file_check_time:.6f}秒)")
        print(f"バイト処理可否: {can_handle_bytes} ({bytes_check_time:.6f}秒)")
        
        if not can_handle_file and not can_handle_bytes:
            print(f"このハンドラは '{file_path}' を処理できません。")
            return
        
        # 4. エントリリスト取得テスト
        
        # 4.1 ファイルからエントリリスト取得
        if can_handle_file:
            print("\n[ファイルからのエントリ一覧取得テスト]")
            file_entries_start = time.time()
            file_entries = handler.list_entries(file_path)
            file_entries_time = time.time() - file_entries_start
            
            print(f"エントリ数: {len(file_entries)} ({file_entries_time:.6f}秒)")
            
            # エントリの種類をカウント
            file_dirs = sum(1 for e in file_entries if e.type == EntryType.DIRECTORY)
            file_archives = sum(1 for e in file_entries if e.type == EntryType.ARCHIVE)
            file_files = sum(1 for e in file_entries if e.type == EntryType.FILE)
            
            print(f"内訳: ディレクトリ {file_dirs}, アーカイブ {file_archives}, ファイル {file_files}")
        else:
            file_entries = []
            file_entries_time = 0
            print("\n[ファイルからのエントリ一覧取得テスト: 非対応]")
        
        # 4.2 メモリからエントリリスト取得
        if can_handle_bytes:
            print("\n[メモリからのエントリ一覧取得テスト]")
            memory_entries_start = time.time()
            memory_entries = handler.list_entries_from_bytes(file_content)
            memory_entries_time = time.time() - memory_entries_start
            
            print(f"エントリ数: {len(memory_entries)} ({memory_entries_time:.6f}秒)")
            
            # エントリの種類をカウント
            memory_dirs = sum(1 for e in memory_entries if e.type == EntryType.DIRECTORY)
            memory_archives = sum(1 for e in memory_entries if e.type == EntryType.ARCHIVE)
            memory_files = sum(1 for e in memory_entries if e.type == EntryType.FILE)
            
            print(f"内訳: ディレクトリ {memory_dirs}, アーカイブ {memory_archives}, ファイル {memory_files}")
        else:
            memory_entries = []
            memory_entries_time = 0
            print("\n[メモリからのエントリ一覧取得テスト: 非対応]")
        
        # 4.3 エントリ数の比較
        if file_entries and memory_entries:
            entries_match = (len(file_entries) == len(memory_entries))
            
            if entries_match:
                print("\n✅ エントリ数は一致しています")
                
                # 速度比較
                speed_diff = file_entries_time - memory_entries_time
                if speed_diff > 0:
                    print(f"⚡ メモリからの取得が {speed_diff:.6f}秒 ({(speed_diff/file_entries_time)*100:.1f}%) 速いです")
                else:
                    print(f"⚡ ファイルからの取得が {-speed_diff:.6f}秒 ({(-speed_diff/memory_entries_time)*100:.1f}%) 速いです")
            else:
                print(f"\n⚠️ エントリ数が一致しません: ファイル {len(file_entries)} vs メモリ {len(memory_entries)}")
        
        # 5. エントリ名とタイプの比較（オプション）
        if file_entries and memory_entries and debug_mode:
            print("\n[エントリの詳細比較]")
            
            # 名前をキーにしたマップを作成
            file_entries_map = {e.name: e for e in file_entries}
            memory_entries_map = {e.name: e for e in memory_entries}
            
            # 共通のエントリを比較
            common_entries = set(file_entries_map.keys()) & set(memory_entries_map.keys())
            only_in_file = set(file_entries_map.keys()) - set(memory_entries_map.keys())
            only_in_memory = set(memory_entries_map.keys()) - set(file_entries_map.keys())
            
            print(f"共通エントリ: {len(common_entries)}, ファイルのみ: {len(only_in_file)}, メモリのみ: {len(only_in_memory)}")
            
            # 不一致があるかチェック
            type_mismatches = 0
            for name in common_entries:
                if file_entries_map[name].type != memory_entries_map[name].type:
                    type_mismatches += 1
                    if type_mismatches <= 5:  # 最初の5件のみ表示
                        print(f"タイプ不一致: {name}: ファイル {file_entries_map[name].type} vs メモリ {memory_entries_map[name].type}")
            
            if type_mismatches:
                print(f"合計 {type_mismatches} 件のタイプ不一致があります")
            else:
                print("すべての共通エントリのタイプは一致しています")
                
            # 不一致エントリの詳細（最初の5件のみ）
            if only_in_file and debug_mode:
                print("\nファイルのみに存在するエントリ (最初の5件):")
                for name in list(only_in_file)[:5]:
                    entry = file_entries_map[name]
                    print(f"  {name} ({entry.type})")
            
            if only_in_memory and debug_mode:
                print("\nメモリのみに存在するエントリ (最初の5件):")
                for name in list(only_in_memory)[:5]:
                    entry = memory_entries_map[name]
                    print(f"  {name} ({entry.type})")
        
        # 6. ファイル読み込みテスト
        # 最初のファイルを選んでテスト
        test_file = None
        
        # 両方に共通するファイルを選ぶ
        if file_entries and memory_entries:
            file_entries_files = [(e.name, e.path) for e in file_entries if e.type == EntryType.FILE]
            memory_entries_files = [(e.name, e.path) for e in memory_entries if e.type == EntryType.FILE]
            
            # 共通するファイル名を探す
            common_files = set(name for name, _ in file_entries_files) & set(name for name, _ in memory_entries_files)
            
            if common_files:
                test_file = next(iter(common_files))
                # パスを検索
                test_file_path = next((path for name, path in file_entries_files if name == test_file), "")
                print(f"\n[ファイル読み込みテスト: {test_file}]")
                
                # ファイルから読み込み
                if can_handle_file:
                    file_read_start = time.time()
                    file_content = handler.read_file(test_file_path)
                    file_read_time = time.time() - file_read_start
                    
                    if file_content:
                        print(f"ファイルからの読み込み: {len(file_content):,} バイト ({file_read_time:.6f}秒)")
                    else:
                        print("ファイルからの読み込みに失敗しました")
                        file_content = None
                else:
                    file_content = None
                    file_read_time = 0
                    print("ファイルからの読み込み: 非対応")
                
                # メモリから読み込み
                if can_handle_bytes:
                    memory_read_start = time.time()
                    memory_content = handler.read_file_from_bytes(file_content, test_file)
                    memory_read_time = time.time() - memory_read_start
                    
                    if memory_content:
                        print(f"メモリからの読み込み: {len(memory_content):,} バイト ({memory_read_time:.6f}秒)")
                    else:
                        print("メモリからの読み込みに失敗しました")
                        memory_content = None
                else:
                    memory_content = None
                    memory_read_time = 0
                    print("メモリからの読み込み: 非対応")
                
                # 内容の比較
                if file_content and memory_content:
                    if file_content == memory_content:
                        print("\n✅ ファイル内容は一致しています")
                        
                        # 速度比較
                        speed_diff = file_read_time - memory_read_time
                        if speed_diff > 0:
                            print(f"⚡ メモリからの読み込みが {speed_diff:.6f}秒 ({(speed_diff/file_read_time)*100:.1f}%) 速いです")
                        else:
                            print(f"⚡ ファイルからの読み込みが {-speed_diff:.6f}秒 ({(-speed_diff/memory_read_time)*100:.1f}%) 速いです")
                    else:
                        print("\n⚠️ ファイル内容が一致しません!")
                        print(f"  ファイル: {len(file_content):,} バイト, メモリ: {len(memory_content):,} バイト")
                        
                        # 先頭100バイトを比較
                        first_mismatch = -1
                        min_len = min(len(file_content), len(memory_content))
                        for i in range(min_len):
                            if file_content[i] != memory_content[i]:
                                first_mismatch = i
                                break
                        
                        if first_mismatch >= 0:
                            print(f"  最初の不一致: {first_mismatch}バイト目")
                            # 不一致部分の前後10バイトをHEX表示
                            start = max(0, first_mismatch - 10)
                            end = min(min_len, first_mismatch + 10)
                            
                            print(f"  ファイル[{start}:{end}]: {file_content[start:end].hex()}")
                            print(f"  メモリ[{start}:{end}]: {memory_content[start:end].hex()}")
            else:
                print("\nテスト用の共通ファイルが見つかりません")
        
        print("\nファイル/メモリ比較テスト完了")
    except Exception as e:
        print(f"エラー: ファイル/メモリ比較テストに失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()


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
    
    # rarfileが利用可能かチェック
    if not check_rarfile_availability():
        print("警告: rarfileパッケージがインポートできません。機能が制限されます。")
    
    print_help()
    
    # コマンドループ
    while True:
        try:
            cmd_input = input("\nコマンド> ").strip()
            
            if not cmd_input:
                continue
                
            cmd = cmd_input[0].upper()
            args_str = cmd_input[1:].strip() if len(cmd_input) > 1 else ""
            
            # 引数を解析（引用符で囲まれたパスを適切に処理）
            args = parse_command_args(args_str)
            
            if cmd == 'Q':
                print("終了します。")
                break
            elif cmd == 'H':
                print_help()
            elif cmd == 'S':
                if not args:
                    print("エラー: アーカイブパスを指定してください。例: S /path/to/archive.rar")
                    print("       空白を含むパスは S \"C:/Program Files/file.rar\" のように指定してください")
                else:
                    set_archive_path(args)
            elif cmd == 'L':
                list_archive_contents(args)
            elif cmd == 'E':
                if not args:
                    print("エラー: 抽出するファイルのパスを指定してください。例: E document.txt")
                    print("       空白を含むパスは E \"folder/my document.txt\" のように指定してください")
                else:
                    extract_archive_file(args)
            elif cmd == 'D':
                debug_mode = not debug_mode
                print(f"デバッグモード: {'オン' if debug_mode else 'オフ'}")
            elif cmd == 'B':
                test_bytes_mode(args if args else None)
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
    parser = argparse.ArgumentParser(description="RARハンドラのテストツール")
    parser.add_argument('-f', '--file', help="開くRARファイルのパス")
    parser.add_argument('-d', '--debug', action='store_true', help="デバッグモードを有効化")
    
    args = parser.parse_args()
    
    if args.debug:
        debug_mode = True
        print("デバッグモードを有効化しました。")
    
    # ファイルが指定されていれば開く
    if args.file:
        set_archive_path(args.file)
    
    # メインループを実行
    main()

