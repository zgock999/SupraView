#!/usr/bin/env python3
"""
ZIPハンドラのテスト用コマンドラインツール

このツールはZIPファイルの操作とエンコーディング問題の確認を行うためのCLIを提供します。
"""
import os
import sys
import zipfile
import argparse
import time
import io
import traceback
from typing import List, Optional, Dict, Any, Tuple

# パスの追加（親ディレクトリをインポートパスに含める）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    # ZIP関連のモジュールをインポート
    from arc.handler.zip_handler import ZipHandler
    from arc.arc import EntryInfo, EntryType
except ImportError as e:
    print(f"エラー: モジュールのインポートに失敗しました: {e}")
    sys.exit(1)

# 必要なインポートを追加
import tempfile
from PIL import Image, UnidentifiedImageError

# グローバル変数
current_archive: bytes = None
current_archive_path: str = None
handler = ZipHandler()
debug_mode = False
# 全エントリリストを保持する変数を追加
all_entries_from_file: List[EntryInfo] = []
all_entries_from_memory: List[EntryInfo] = []


def print_banner():
    """アプリケーションバナーを表示"""
    print("=" * 70)
    print("ZIPハンドラ テストツール")
    print("このツールはZIPファイルの操作とエンコーディング問題の検証用CLIを提供します")
    print("=" * 70)


def print_help():
    """コマンドヘルプを表示"""
    print("\n使用可能なコマンド:")
    print("  S <path>      - ZIPファイルのパスを設定（Set archive path）")
    print("                  空白を含むパスは \"path/to file.zip\" のように引用符で囲みます")
    print("  L [path]      - アーカイブ内のファイル/ディレクトリを一覧表示（List archive contents）")
    print("  E <path>      - アーカイブからファイルを抽出（Extract file from archive）")
    print("                  空白を含むパスは引用符で囲みます")
    print("  I <name>      - 指定した名前のファイルをエントリリストから検索（find In archive）")
    print("  B <path>      - メモリ上のバイトデータからファイルを読み込み（Bytes test）")
    print("  D             - デバッグモードの切替（Toggle debug mode）")
    print("  R             - 生のZIPエントリ一覧を表示（Raw entry list）")
    print("  M             - マッピングテーブルを表示（show Mapping table）")
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
    
    # 拡張子のチェック
    _, ext = os.path.splitext(path.lower())
    if ext not in ['.zip', '.cbz', '.epub']:
        print(f"警告: 指定されたファイルはZIPではない可能性があります: {path}")
        
    try:
        # 古い全エントリリストをクリア
        all_entries_from_file = []
        all_entries_from_memory = []
        
        # アーカイブファイルを読み込む
        with open(path, 'rb') as f:
            current_archive = f.read()
        current_archive_path = path
        print(f"アーカイブを設定: {path} ({len(current_archive)} バイト)")
        
        # ZIP形式の検証
        if current_archive[:4] != b'PK\x03\x04':
            print("警告: ファイルはZIPシグネチャを持っていません")
        else:
            print("ZIPシグネチャを検出: PK\\x03\\x04")
            
        # ZIPとして開けるかテスト
        try:
            with zipfile.ZipFile(io.BytesIO(current_archive)) as zf:
                files = zf.namelist()
                print(f"ZIPファイルの検証成功: {len(files)} エントリを含みます")
                
                # 重要: ここでZIP構造を事前に構築（後続のすべての操作に必要）
                print("ZIPファイル構造を構築しています...")
                structure = handler._get_zip_structure(path, zf)
                
                if structure:
                    print(f"構造の構築に成功: {len(structure)} ディレクトリエントリ")
                    
                    # マッピング情報の存在をチェック
                    total_mappings = 0
                    for dir_path, contents in structure.items():
                        for display_name, original_name in contents.get('file_map', {}).items():
                            if display_name != original_name:
                                total_mappings += 1
                    
                    if total_mappings > 0:
                        print(f"エンコーディング変換されたファイル名があります: {total_mappings}個")
                        print(f"詳細は 'M' コマンドで確認できます。")
                else:
                    print("警告: 構造の構築に失敗しました")
                
                # 新機能: アーカイブ内の全エントリを取得して保持
                print("アーカイブ内の全エントリを取得しています...")
                all_entries_from_file = handler.list_all_entries(path)
                print(f"ファイルから {len(all_entries_from_file)}個のエントリを取得しました")
                
                # メモリからも全エントリを取得
                print("メモリからも全エントリを取得しています...")
                all_entries_from_memory = handler.list_all_entries_from_bytes(current_archive, "")
                print(f"メモリから {len(all_entries_from_memory)}個のエントリを取得しました")
                
                # ファイルとメモリからの結果を比較
                if len(all_entries_from_file) == len(all_entries_from_memory):
                    print("ファイルとメモリからのエントリ数が一致しています")
                else:
                    print(f"警告: エントリ数が一致しません (ファイル: {len(all_entries_from_file)}, メモリ: {len(all_entries_from_memory)})")
        except Exception as e:
            print(f"警告: ZIPファイルとして開けませんでした: {e}")
            
        return True
    except Exception as e:
        print(f"エラー: ファイルの読み込みに失敗しました: {e}")
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
            print(f"全エントリ数: {len(all_entries_from_file)} (ファイル), {len(all_entries_from_memory)} (メモリ)")
        
        # 内部パスを正規化
        if internal_path:
            internal_path = normalize_path(internal_path)
            
            # 内部パスがディレクトリかどうかを確認し、必要に応じて末尾にスラッシュを追加
            if not internal_path.endswith('/'):
                # 既存のエントリ情報からディレクトリかどうかを判定
                dir_entry = None
                test_path = f"{internal_path}/"
                for entry in all_entries_from_file:
                    if entry.path.endswith(test_path):
                        dir_entry = entry
                        break
                
                if dir_entry:
                    internal_path += '/'
                    print(f"内部パスをディレクトリとして正規化: {internal_path}")
        
        # エントリ情報の取得（既存コードで取得していた情報）
        full_path = f"{current_archive_path}/{internal_path}" if internal_path else current_archive_path
        entry_info = handler.get_entry_info(full_path)
        
        if entry_info:
            print(f"エントリ情報: 名前={entry_info.name}, パス={entry_info.path}, タイプ={entry_info.type}")
        
        # internal_pathから実際のフィルタリング用パスを構築
        filter_path = f"{current_archive_path}/{internal_path}" if internal_path else current_archive_path
        print(f"フィルタパス: {filter_path}")
        
        # 全エントリリストからフィルタリング
        entries = []
        dir_seen = set()  # 既に処理したディレクトリを記録
        
        for entry in all_entries_from_file:
            # ルートパスの場合（ZIPファイル自体）
            if not internal_path:
                # ZIPのルートディレクトリの直下のエントリのみを対象
                path_parts = entry.path.replace(current_archive_path, '').strip('/').split('/')
                
                if len(path_parts) == 1 and path_parts[0]:  # ルート直下の要素
                    if entry.type == EntryType.DIRECTORY:
                        dir_name = path_parts[0]
                        if dir_name not in dir_seen:
                            dir_seen.add(dir_name)
                            entries.append(entry)
                    else:
                        entries.append(entry)
            else:
                # 指定されたディレクトリ内のエントリを対象
                if entry.path.startswith(filter_path):
                    # 相対パスを計算
                    rel_path = entry.path[len(filter_path):].strip('/')
                    
                    if not rel_path:
                        # 指定したディレクトリ自体は除外
                        continue
                        
                    # 直下のみ対象（サブディレクトリの中は含めない）
                    path_parts = rel_path.split('/')
                    
                    if len(path_parts) == 1:
                        # 直下のファイル
                        entries.append(entry)
                    elif len(path_parts) > 1 and entry.type == EntryType.DIRECTORY:
                        # サブディレクトリ（ディレクトリとして追加）
                        dir_name = path_parts[0]
                        if dir_name not in dir_seen:
                            dir_seen.add(dir_name)
                            
                            # ディレクトリエントリを作成（実際のエントリを置き換え）
                            dir_path = os.path.join(filter_path, dir_name).replace('\\', '/')
                            entries.append(EntryInfo(
                                name=dir_name,
                                path=dir_path,
                                size=0,
                                modified_time=None,
                                type=EntryType.DIRECTORY
                            ))
        
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
            
            # name_in_arc があればそれも表示
            name_display = entry.name
            if debug_mode and hasattr(entry, 'name_in_arc') and entry.name_in_arc is not None and entry.name_in_arc != entry.name:
                name_display = f"{entry.name} -> [{entry.name_in_arc}]"
                
            print("{:<40} {:>10} {:>20} {}".format(
                name_display[:39], size_str, date_str, type_str
            ))
            
        print(f"\n合計: {len(entries)} エントリ")
        return True
    except Exception as e:
        print(f"エラー: アーカイブ内容の一覧取得に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


# 新しい共通関数を追加
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
        if normalize_path(entry.path).endswith(norm_path):
            print(f"完全パス一致でエントリを見つけました: {entry.path}")
            return entry
    
    # 2. ファイル名だけの一致を試行
    for entry in entries:
        if entry.name == file_name:
            print(f"ファイル名一致でエントリを見つけました: {entry.path}")
            return entry
    
    # 3. 文字化け対応: ZIP内の実際のファイル名とのマッピングを確認
    for entry in entries:
        if hasattr(entry, 'name_in_arc') and entry.name_in_arc:
            # エンコード前の名前の末尾がファイル名と一致するか確認
            orig_filename = os.path.basename(entry.name_in_arc)
            if orig_filename == file_name:
                print(f"name_in_arcファイル名一致でエントリを見つけました: {entry.path} -> {entry.name_in_arc}")
                return entry
    
    # 4. 部分文字列一致を試行（ファイル名の一部が一致する場合）
    for entry in entries:
        if file_name in entry.name or (hasattr(entry, 'name_in_arc') and 
                                       entry.name_in_arc and file_name in entry.name_in_arc):
            print(f"部分文字列一致でエントリを見つけました: {entry.path}")
            return entry
    
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
    global current_archive, current_archive_path, all_entries_from_file, all_entries_from_memory
    
    if not current_archive_path:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        # ファイルパスを正規化
        file_path = normalize_path(file_path)
        
        print(f"ファイル '{file_path}' を抽出中...")
        
        # 全エントリリストから対象のエントリを見つける
        entry_info = find_entry_by_path(all_entries_from_file, file_path)
        
        if not entry_info:
            print(f"ファイル '{file_path}' に一致するエントリが見つかりません")
            print(f"全エントリ数: {len(all_entries_from_file)}")
            # メモリエントリからも試す
            if all_entries_from_memory:
                print(f"メモリエントリからの検索を試みます...")
                entry_info = find_entry_by_path(all_entries_from_memory, file_path)
            
            if not entry_info:
                print(f"すべての検索方法でエントリが見つかりませんでした")
                return False
            else:
                print(f"メモリエントリから一致するものを発見: {entry_info.path}")
        
        if entry_info.type == EntryType.DIRECTORY:
            print(f"指定されたパスはディレクトリです: {file_path}")
            print(f"ディレクトリの内容を表示するには 'L {file_path}' コマンドを使用してください。")
            return False
        
        # name_in_arcを使って適切な内部パスを構築
        actual_internal_path = file_path
        if entry_info and hasattr(entry_info, 'name_in_arc') and entry_info.name_in_arc:
            # 内部ファイル名を記録
            original_name = entry_info.name_in_arc
            print(f"内部ファイル名: {original_name}")
            
            # name_in_arcの形式によって処理を分ける
            if '/' in original_name:
                # 完全パスの形式の場合はそのまま使用
                actual_internal_path = original_name
                print(f"内部パスに完全パスを使用: {file_path} -> {actual_internal_path}")
            else:
                # ファイル名のみの場合は、元のパスのディレクトリ部分を保持
                dir_path = os.path.dirname(file_path)
                if dir_path:
                    dir_path += '/'
                actual_internal_path = dir_path + original_name
                print(f"内部パス修正（レガシーモード）: {file_path} -> {actual_internal_path}")
        
        # 解決したパスでファイルを読み込み
        print(f"ファイルからの抽出: {current_archive_path} -> {actual_internal_path}")
        content = handler.read_archive_file(current_archive_path, actual_internal_path)
        
        # メモリからも試す
        memory_content = None
        if current_archive:
            print(f"メモリからの抽出: {len(current_archive)} バイト -> {actual_internal_path}")
            memory_content = handler.read_file_from_bytes(current_archive, actual_internal_path)
            
            if content and memory_content:
                if content == memory_content:
                    print(f"ファイルとメモリからの読み込み結果が一致: {len(content)} バイト")
                else:
                    print(f"警告: ファイル ({len(content)} バイト) とメモリ ({len(memory_content)} バイト) からの読み込み結果が異なります")
            elif content:
                print(f"ファイルからの読み込みには成功しましたが、メモリからは失敗しました")
            elif memory_content:
                print(f"ファイルからの読み込みに失敗しましたが、メモリからは成功しました")
        
        # いずれかの方法で成功した内容を使用
        final_content = content if content is not None else memory_content
        
        if final_content is None:
            print(f"エラー: ファイル '{file_path}' が見つからないか、読み込めませんでした。")
            return False
            
        # ファイルのバイナリデータに関する情報を表示
        print(f"ファイルサイズ: {len(final_content):,} バイト")
        
        # エンコーディング推定
        encoding = None
        is_text = True
        
        # バイナリデータの最初の数バイトを確認
        if len(final_content) > 2:
            # BOMでエンコーディングをチェック
            if final_content.startswith(b'\xef\xbb\xbf'):
                encoding = 'utf-8-sig'
                print(f"エンコーディング検出: UTF-8 BOMあり")
            elif final_content.startswith(b'\xff\xfe'):
                encoding = 'utf-16-le'
                print(f"エンコーディング検出: UTF-16 LE")
            elif final_content.startswith(b'\xfe\xff'):
                encoding = 'utf-16-be'
                print(f"エンコーディング検出: UTF-16 BE")
                
        # バイナリか判定
        binary_bytes = 0
        ascii_bytes = 0
        for byte in final_content[:min(1000, len(final_content))]:
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
                        final_content.decode(enc)
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
                f.write(final_content)
                
            print(f"ファイルを保存しました: {save_path} ({len(final_content):,} バイト)")
            
        # テキストの場合は内容を表示
        if is_text and encoding:
            print(f"\n===== ファイル内容 (エンコーディング: {encoding}) =====")
            
            try:
                text_content = final_content.decode(encoding)
                # 長いテキストは省略表示
                max_chars = 500
                if len(text_content) > max_chars:
                    print(text_content[:max_chars] + "...(省略)")
                else:
                    print(text_content)
            except Exception as e:
                print(f"テキスト表示エラー: {e}")
                
        return True
    except Exception as e:
        print(f"エラー: ファイルの抽出に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def find_file_in_archive(name: str) -> bool:
    """
    ファイル名またはパターンでアーカイブ内を検索
    
    Args:
        name: 検索するファイル名またはパターン
        
    Returns:
        ファイルが見つかった場合はTrue、そうでない場合はFalse
    """
    global current_archive, current_archive_path
    
    if not current_archive_path:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        print(f"アーカイブ内で '{name}' を検索中...")
        
        # ZIPファイルを直接開いて探索
        with zipfile.ZipFile(current_archive_path) as zf:
            found_files = []
            
            # すべてのエントリをチェック
            for file_info in zf.infolist():
                file_path = file_info.filename
                
                # Macの隠しフォルダなどをスキップ
                if '__MACOSX' in file_path:
                    continue
                
                # ファイル名のみを取得
                file_name = os.path.basename(file_path)
                
                # 検索パターンにマッチするか確認
                if name.lower() in file_name.lower():
                    # 元のファイル名とエンコーディング変換結果の両方を表示
                    original_name = file_path
                    converted_name = None
                    
                    # エンコーディング変換を試みる
                    if hasattr(file_info, 'orig_filename'):
                        try:
                            # CP437からShift-JIS（CP932）に変換
                            converted_name = file_info.orig_filename.encode('cp437').decode('cp932', errors='replace')
                        except:
                            pass
                        
                    # 結果をリストに追加
                    found_files.append((file_path, converted_name, file_info.file_size))
                    
            # 結果を表示
            if found_files:
                print(f"\n検索結果: {len(found_files)} 件のファイルが見つかりました")
                print("{:<60} {:<60} {:<10}".format("元のパス", "変換後のパス", "サイズ"))
                print("-" * 120)
                
                for orig_path, conv_path, size in found_files:
                    display_conv = conv_path if conv_path else "-"
                    print("{:<60} {:<60} {:<10}".format(
                        orig_path[:59], display_conv[:59], f"{size:,}"
                    ))
                    
                # ファイルを抽出するか尋ねる
                if len(found_files) == 1:
                    answer = input("\nこのファイルを抽出しますか？ (y/N): ")
                    if answer.lower() == 'y':
                        # 変換後のパスがあればそれを、なければ元のパスを使用
                        path_to_extract = conv_path if conv_path else orig_path
                        return extract_archive_file(path_to_extract)
                        
                return True
            else:
                print(f"検索条件に一致するファイルが見つかりませんでした: {name}")
                return False
                
    except Exception as e:
        print(f"エラー: ファイル検索中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_raw_entries() -> bool:
    """
    生のZIPエントリ一覧を表示
    
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive, current_archive_path
    
    if not current_archive_path:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        print(f"ZIPファイル {current_archive_path} の生のエントリ一覧:")
        
        # ZIPファイルを直接開いて探索
        with zipfile.ZipFile(current_archive_path) as zf:
            print("\n{:<60} {:<20} {:<10} {:<10}".format(
                "ファイル名", "更新日時", "圧縮サイズ", "元サイズ"
            ))
            print("-" * 100)
            
            for file_info in zf.infolist():
                file_path = file_info.filename
                
                # 日時情報の変換
                if file_info.date_time != (0, 0, 0, 0, 0, 0):
                    date_str = f"{file_info.date_time[0]}-{file_info.date_time[1]:02d}-{file_info.date_time[2]:02d} " \
                             f"{file_info.date_time[3]:02d}:{file_info.date_time[4]:02d}"
                else:
                    date_str = "-"
                    
                print("{:<60} {:<20} {:<10} {:<10}".format(
                    file_path[:59], date_str, f"{file_info.compress_size:,}", f"{file_info.file_size:,}"
                ))
                
                # エンコーディング変換も試みる
                if hasattr(file_info, 'orig_filename'):
                    try:
                        # CP437からShift-JIS（CP932）に変換
                        converted = file_info.orig_filename.encode('cp437').decode('cp932', errors='replace')
                        if converted != file_path:
                            print(f"  → {converted}")
                    except:
                        pass
            
            print(f"\n合計: {len(zf.filelist)} エントリ")
            
            # CRC情報も表示
            print("\n{:<60} {:<10} {:<10}".format(
                "ファイル名", "CRC", "フラグ"
            ))
            print("-" * 80)
            
            for file_info in zf.filelist[:10]:  # 最初の10件だけ表示
                print("{:<60} {:<10} {:<10}".format(
                    file_info.filename[:59], f"{file_info.CRC:08x}", f"{file_info.flag_bits:08b}"
                ))
            
            if len(zf.filelist) > 10:
                print("...")
                
        return True
        
    except Exception as e:
        print(f"エラー: 生のエントリ一覧表示中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def show_mapping_table() -> bool:
    """
    ZIPハンドラのマッピングテーブルを表示
    
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive_path, handler
    
    if not current_archive_path:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        print(f"ZIPファイル {current_archive_path} のマッピングテーブル:")
        
        # 構造キャッシュからマッピングを取得
        if current_archive_path in handler.structure_cache:
            structure = handler.structure_cache[current_archive_path]
            
            # 各ディレクトリのマッピング情報を表示
            print("\n{:<30} {:<40} {:<40}".format(
                "ディレクトリ", "表示名", "内部ファイル名"
            ))
            print("-" * 110)
            
            total_mappings = 0
            
            for dir_path, contents in structure.items():
                # このディレクトリのマッピング情報を取得
                file_map = contents.get('file_map', {})
                
                # マッピングがあるエントリだけ表示
                for display_name, original_name in file_map.items():
                    if display_name != original_name:
                        print("{:<30} {:<40} {:<40}".format(
                            dir_path[:29], display_name[:39], original_name[:39]
                        ))
                        total_mappings += 1
            
            if total_mappings == 0:
                print("マッピング情報がありません（表示名と内部ファイル名が同一）")
            else:
                print(f"\n合計: {total_mappings} 件のマッピング")
        else:
            print("現在のアーカイブの構造キャッシュが見つかりません")
            
            # 新しく構造を取得してみる
            print("構造情報を取得中...")
            
            try:
                with zipfile.ZipFile(current_archive_path) as zf:
                    structure = handler._get_zip_structure(current_archive_path, zf)
                    
                    if structure:
                        print("構造情報の取得に成功しました")
                        
                        # マッピング情報の表示処理を再実行
                        total_mappings = 0
                        print("\n{:<30} {:<40} {:<40}".format(
                            "ディレクトリ", "表示名", "内部ファイル名"
                        ))
                        print("-" * 110)
                        
                        for dir_path, contents in structure.items():
                            # このディレクトリのマッピング情報を取得
                            file_map = contents.get('file_map', {})
                            
                            # マッピングがあるエントリだけ表示
                            for display_name, original_name in file_map.items():
                                if display_name != original_name:
                                    print("{:<30} {:<40} {:<40}".format(
                                        dir_path[:29], display_name[:39], original_name[:39]
                                    ))
                                    total_mappings += 1
                        
                        if total_mappings == 0:
                            print("マッピング情報がありません（表示名と内部ファイル名が同一）")
                        else:
                            print(f"\n合計: {total_mappings} 件のマッピング")
                    else:
                        print("構造情報が取得できませんでした")
            except Exception as e:
                print(f"構造情報取得中にエラーが発生しました: {e}")
                
        return True
        
    except Exception as e:
        print(f"エラー: マッピングテーブル表示中に問題が発生しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def binary_dump(file_path: str) -> bool:
    """
    アーカイブ内のファイルのバイナリダンプを表示する
    
    Args:
        file_path: アーカイブ内のファイルパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive, current_archive_path, all_entries_from_file, all_entries_from_memory
    
    if not current_archive_path:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        # ファイルパスを正規化
        file_path = normalize_path(file_path)
        
        print(f"ファイル '{file_path}' のバイナリダンプを表示します...")
        
        # 全エントリリストから対象のエントリを見つける
        entry_info = find_entry_by_path(all_entries_from_file, file_path)
        
        if not entry_info:
            print(f"ファイル '{file_path}' に一致するエントリが見つかりません")
            # メモリエントリからも試す
            if all_entries_from_memory:
                print(f"メモリエントリからの検索を試みます...")
                entry_info = find_entry_by_path(all_entries_from_memory, file_path)
            
            if not entry_info:
                print(f"すべての検索方法でエントリが見つかりませんでした")
                return False
            else:
                print(f"メモリエントリから一致するものを発見: {entry_info.path}")
        
        if entry_info.type == EntryType.DIRECTORY:
            print(f"指定されたパスはディレクトリです: {file_path}")
            return False
        
        # name_in_arcが設定されている場合は使用
        internal_path = file_path
        if entry_info and hasattr(entry_info, 'name_in_arc') and entry_info.name_in_arc:
            original_name = entry_info.name_in_arc
            print(f"内部ファイル名: {original_name}")
            
            # name_in_arcは完全パスが格納されているため、適切に処理
            if '/' in original_name:
                internal_path = original_name
                print(f"内部パスに完全パスを使用: {file_path} -> {internal_path}")
            else:
                # 古いバージョン互換のフォールバック
                dir_path = os.path.dirname(file_path)
                if dir_path:
                    dir_path += '/'
                internal_path = dir_path + original_name
                print(f"内部パス修正（レガシーモード）: {file_path} -> {internal_path}")
        
        # ファイルの内容を読み込む
        content = handler.read_archive_file(current_archive_path, internal_path)
        
        if content is None and current_archive:
            # ファイル読み込みに失敗した場合はメモリから試行
            print(f"ファイルからの読み込みに失敗したため、メモリから試行します")
            content = handler.read_file_from_bytes(current_archive, internal_path)
        
        if content is None:
            print(f"エラー: ファイル '{file_path}' の読み込みに失敗しました。")
            return False
            
        # バイナリダンプを表示
        print(f"\nファイル '{os.path.basename(file_path)}' のバイナリダンプ ({len(content):,} バイト):")
        print("-" * 70)
        
        # 1. ダンプをバッチサイズで表示（16バイトx8行 = 128バイト）
        BYTES_PER_LINE = 16
        LINES_PER_BATCH = 8
        
        offset = 0
        batch_count = 0
        total_batches = (len(content) + (BYTES_PER_LINE * LINES_PER_BATCH - 1)) // (BYTES_PER_LINE * LINES_PER_BATCH)
        
        while offset < len(content):
            # 1バッチ（8行）表示
            for _ in range(LINES_PER_BATCH):
                if offset >= len(content):
                    break
                    
                # 1行（16バイト）の内容を取得
                line_bytes = content[offset:offset + BYTES_PER_LINE]
                
                # 16進数表示用の文字列を作成
                hex_values = ' '.join(f"{b:02x}" for b in line_bytes)
                hex_display = hex_values.ljust(BYTES_PER_LINE * 3 - 1)  # 空白も含めて調整
                
                # ASCII文字表示用の文字列を作成
                ascii_values = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in line_bytes)
                
                # オフセット、16進数値、ASCII文字を表示
                print(f"{offset:08x}: {hex_display} | {ascii_values}")
                
                # 次の行へ
                offset += BYTES_PER_LINE
                
            # バッチカウントを増加
            batch_count += 1
            
            # まだ表示するデータがあれば続けるか確認
            if offset < len(content) and batch_count < total_batches:
                user_input = input(f"続けて表示しますか？ ({batch_count}/{total_batches}バッチ表示済) [Y/n]: ")
                if user_input.lower() == 'n':
                    break
                    
        print("\nバイナリダンプ表示完了")
        return True
        
    except Exception as e:
        print(f"エラー: バイナリダンプの表示に失敗しました: {e}")
        if debug_mode:
            traceback.print_exc()
        return False


def test_read_from_bytes(file_path: str) -> bool:
    """
    メモリ上のバイトデータからファイルを読み込むテスト
    
    Args:
        file_path: アーカイブ内のファイルパス
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive, current_archive_path, all_entries_from_file, all_entries_from_memory
    
    if not current_archive or not current_archive_path:
        print("エラー: アーカイブが設定されていません。先に 'S <path>' コマンドを実行してください。")
        return False
    
    try:
        # ファイルパスを正規化
        file_path = normalize_path(file_path)
        
        print(f"ファイル '{file_path}' のバイトデータからの読み込みテストを実行中...")
        
        # 全エントリリストから対象のエントリを見つける
        entry_info = find_entry_by_path(all_entries_from_file, file_path)
        
        if not entry_info:
            print(f"ファイル '{file_path}' に一致するエントリが見つかりません")
            # メモリエントリからも試す
            if all_entries_from_memory:
                print(f"メモリエントリからの検索を試みます...")
                entry_info = find_entry_by_path(all_entries_from_memory, file_path)
            
            if not entry_info:
                print(f"すべての検索方法でエントリが見つかりませんでした")
                return False
            else:
                print(f"メモリエントリから一致するものを発見: {entry_info.path}")
        
        if entry_info.type == EntryType.DIRECTORY:
            print(f"指定されたパスはディレクトリです: {file_path}")
            return False
        
        # name_in_arcを使って適切な内部パスを構築
        actual_internal_path = file_path
        if entry_info and hasattr(entry_info, 'name_in_arc') and entry_info.name_in_arc:
            original_name = entry_info.name_in_arc
            print(f"内部ファイル名: {original_name}")
            
            # name_in_arcの形式によって処理を分ける
            if '/' in original_name:
                # 完全パスの形式の場合はそのまま使用
                actual_internal_path = original_name
                print(f"内部パスに完全パスを使用: {file_path} -> {actual_internal_path}")
            else:
                # ファイル名のみの場合は、元のパスのディレクトリ部分を保持
                dir_path = os.path.dirname(file_path)
                if dir_path:
                    dir_path += '/'
                actual_internal_path = dir_path + original_name
                print(f"内部パス修正（レガシーモード）: {file_path} -> {actual_internal_path}")
        
        # 1. バイトデータからの読み込みをベンチマーク
        start_time = time.time()
        
        print("1. バイトデータからの読み込みテスト:")
        bytes_content = handler.read_file_from_bytes(current_archive, actual_internal_path)
        bytes_time = time.time() - start_time
        
        if bytes_content is None:
            print(f"  結果: 失敗 (バイトデータからファイルを読み込めませんでした)")
            bytes_success = False
        else:
            print(f"  結果: 成功 ({len(bytes_content):,} バイト, {bytes_time:.6f} 秒)")
            bytes_success = True
        
        # 2. 通常のファイルからの読み込みをベンチマーク
        start_time = time.time()
        print("\n2. 通常のファイルからの読み込みテスト:")
        file_content = handler.read_archive_file(current_archive_path, actual_internal_path)
        file_time = time.time() - start_time
        
        if file_content is None:
            print(f"  結果: 失敗 (ファイルから読み込めませんでした)")
            file_success = False
        else:
            print(f"  結果: 成功 ({len(file_content):,} バイト, {file_time:.6f} 秒)")
            file_success = True
        
        # 3. メモリからの読み込みとファイルからの読み込みを比較
        content_for_analysis = None
        if bytes_success and file_success:
            print("\n3. 内容比較:")
            if bytes_content == file_content:
                print(f"  結果: 一致 ({len(bytes_content):,} バイト)")
                content_for_analysis = bytes_content
            else:
                print(f"  結果: 不一致 (バイトデータ: {len(bytes_content):,} バイト, ファイル: {len(file_content):,} バイト)")
                # 片方しか成功していない場合は、成功した方を使用
                content_for_analysis = bytes_content if bytes_success else file_content
                
            # 速度比較
            print("\n4. 速度比較:")
            if bytes_time < file_time:
                speedup = (file_time / bytes_time) - 1.0
                print(f"  バイトデータからの読み込みが {speedup:.1%} 速い ({bytes_time:.6f} vs {file_time:.6f} 秒)")
            elif file_time < bytes_time:
                speedup = (bytes_time / file_time) - 1.0
                print(f"  ファイルからの読み込みが {speedup:.1%} 速い ({file_time:.6f} vs {bytes_time:.6f} 秒)")
            else:
                print(f"  同じ速度 ({bytes_time:.6f} 秒)")
        elif bytes_success:
            content_for_analysis = bytes_content
        elif file_success:
            content_for_analysis = file_content
        
        # 5. 画像ファイルの場合は追加情報を表示
        if content_for_analysis and (os.path.splitext(file_path)[1].lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            print("\n5. 画像情報の分析:")
            try:
                # 一時ファイルに保存して画像として開く
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_path)[1]) as temp_file:
                    temp_path = temp_file.name
                    temp_file.write(content_for_analysis)
                
                try:
                    with Image.open(temp_path) as img:
                        print(f"  画像形式: {img.format}")
                        print(f"  サイズ: {img.width} x {img.height} ピクセル")
                        print(f"  モード: {img.mode}")
                        
                        # EXIF情報があれば表示
                        if hasattr(img, '_getexif') and img._getexif():
                            print("  EXIF情報:")
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
                                    print(f"    {tag_name}: {exif[tag_id]}")
                except UnidentifiedImageError:
                    print("  画像として読み込めませんでした。データが破損しているか、サポートされていない形式です。")
                except Exception as e:
                    print(f"  画像分析中にエラーが発生しました: {e}")
                finally:
                    # 一時ファイルを削除
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
            except Exception as e:
                print(f"  画像ファイル処理でエラーが発生しました: {e}")
        
        return bytes_success or file_success
    
    except Exception as e:
        print(f"エラー: バイトデータ読み込みテスト中に例外が発生しました: {e}")
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
    global debug_mode
    
    print_banner()
    print_help()
    
    # コマンドループ
    while True:
        try:
            cmd_line = input("\nコマンド> ").strip()
            
            if not cmd_line:
                continue
                
            cmd = cmd_line[0].upper()
            args = cmd_line[1:].strip()
            
            if cmd == 'Q':  # 終了
                print("プログラムを終了します...")
                break
                
            elif cmd == 'H':  # ヘルプ表示
                print_help()
                
            elif cmd == 'S':  # アーカイブパス設定
                path = parse_command_args(args)
                if not path:
                    print("エラー: アーカイブパスが指定されていません。\n使用法: S <path>")
                else:
                    set_archive_path(path)
                    
            elif cmd == 'L':  # エントリ一覧表示
                path = parse_command_args(args)
                list_archive_contents(path)
                
            elif cmd == 'E':  # ファイル抽出
                path = parse_command_args(args)
                if not path:
                    print("エラー: ファイルパスが指定されていません。\n使用法: E <path>")
                else:
                    extract_archive_file(path)
            
            elif cmd == 'B':  # バイトデータからの読み込みテスト
                path = parse_command_args(args)
                if not path:
                    print("エラー: ファイルパスが指定されていません。\n使用法: B <path>")
                else:
                    test_read_from_bytes(path)
                    
            elif cmd == 'I':  # ファイル検索
                name = parse_command_args(args)
                if not name:
                    print("エラー: 検索文字列が指定されていません。\n使用法: I <name>")
                else:
                    find_file_in_archive(name)
                    
            elif cmd == 'D':  # デバッグモード切替
                debug_mode = not debug_mode
                print(f"デバッグモード: {'オン' if debug_mode else 'オフ'}")
                
            elif cmd == 'R':  # 生のエントリ一覧表示
                show_raw_entries()
                
            elif cmd == 'M':  # マッピングテーブル表示
                show_mapping_table()
                
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
    parser = argparse.ArgumentParser(description="ZIPハンドラのテストツール")
    parser.add_argument('-f', '--file', help="開くZIPファイルのパス")
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


