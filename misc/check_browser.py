#!/usr/bin/env python3
"""
アーカイブブラウザのテストユーティリティ

arc.browserモジュールの機能をテストするためのツール
"""
import os
import sys
import argparse
import traceback
from typing import List, Optional, Dict, Any

# 親ディレクトリをPythonパスに追加して、プロジェクトのモジュールをインポートできるようにする
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if (project_root not in sys.path):
    sys.path.insert(0, project_root)
    print(f"Added {project_root} to Python path")

# モジュールをインポート - パス設定後にインポートするように移動
from logutils import setup_logging, log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL

from arc.interface import get_archive_manager  # interfaceモジュールからインポート
from arc.browser import ArchiveBrowser, get_browser  # browserモジュールをインポート
from arc.arc import EntryType
from arc.path_utils import normalize_path

try:
    pass
except ImportError as e:
    log_print(ERROR, f"エラー: アーカイブブラウザのインポートに失敗しました: {e}")
    sys.exit(1)

# グローバル変数
current_archive_path: str = None
manager = get_archive_manager()
browser = None  # ブラウザインスタンス
debug_mode = False

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
    print("アーカイブブラウザ テストツール")
    print("このツールはarc.browserモジュールの機能をテストするためのコマンドラインインターフェースを提供します")
    print("=" * 70)


def print_help():
    """コマンドヘルプを表示"""
    print("\n使用可能なコマンド:")
    print("  S <path>      - アーカイブパスを設定（Set archive path）")
    print("                  空白を含むパスは \"path/to file.zip\" のように引用符で囲みます")
    print("  j <path>      - 指定したパスに直接ジャンプ（jump）")
    print("  l <prefix>    - 指定された接頭辞に一致するエントリを表示（List entries）")
    print("  lf            - 現在のフォルダ内のエントリのみを表示（List folder entries）")
    print("  c             - カレントエントリを表示（Current entry）")
    print("  n             - 次のエントリに移動（next）")
    print("  p             - 前のエントリに移動（prev）")
    print("  nn            - 次のフォルダの先頭へ移動（next_folder）")
    print("  pp            - 前のフォルダの末尾へ移動（prev_folder）")
    print("  gf            - リストの先頭へ移動（go_first）")
    print("  gl            - リストの末尾へ移動（go_last）") 
    print("  gt            - フォルダ内の先頭へ移動（go_top）")
    print("  ge            - フォルダ内の末尾へ移動（go_end）")
    print("  A             - pagesの値を1と2の間で切り替え（Toggle pages）")
    print("  T             - shiftの値をtrue/falseの間で切り替え（Toggle shift）")
    print("  D             - デバッグモードの切替（Toggle debug mode）")
    print("  ?             - このヘルプを表示")
    print("  Q             - 終了")
    print("")


def set_archive_path(path: str, pages: int = None, shift: bool = None) -> bool:
    """
    現在のアーカイブパスを設定
    
    Args:
        path: アーカイブファイルへのパス
        pages: ページ数（省略可）
        shift: シフトフラグ（省略可）
        
    Returns:
        成功した場合はTrue、失敗した場合はFalse
    """
    global current_archive_path, manager, browser
    
    # 現在のブラウザの状態を保存（再初期化用）
    current_path = None
    if browser and browser._entries:
        try:
            current_path = browser._entries[browser._current_idx]
        except:
            pass
    
    # 現在のpagesとshift設定を取得（再初期化用）
    current_pages = 1
    current_shift = False
    if browser:
        current_pages = getattr(browser, '_pages', 1)
        current_shift = getattr(browser, '_shift', False)
    
    # 新しい設定が指定されていればそれを使用
    if pages is not None:
        current_pages = pages
    if shift is not None:
        current_shift = shift
    
    # パスを正規化（先頭の/は物理パスとして保持する）
    path = normalize_path(path)
    
    if not os.path.exists(path):
        log_print(ERROR, f"エラー: ファイルが見つかりません: {path}")
        return False
        
    if not os.path.isfile(path) and not os.path.isdir(path):
        log_print(ERROR, f"エラー: 指定されたパスはファイルまたはディレクトリではありません: {path}")
        return False
        
    try:
        # アーカイブファイルパスを設定
        current_archive_path = path
        log_print(INFO, f"アーカイブを設定: {path}")
        
        if os.path.isfile(path):
            log_print(INFO, f"ファイルサイズ: {os.path.getsize(path):,} バイト")
        
        # マネージャーにカレントパスを設定
        manager.set_current_path(path)
        entry_cache = manager.get_entry_cache()
        log_print(INFO, f"エントリ数: {len(entry_cache)}")
        
        # マネージャーがこのファイルを処理できるか確認
        handler_info = manager.get_handler(path)
        if handler_info:
            handler_name = handler_info.__class__.__name__
            log_print(INFO, f"このファイルは '{handler_name}' で処理可能です")          
            
            # ブラウザを初期化（pagesとshift設定を適用）
            # 引数順序を修正: manager, path, exts, pages, shift
            browser = get_browser(manager, current_path or "", None, current_pages, current_shift)
            if browser and browser._entries:
                log_print(INFO, f"ブラウザを初期化しました。エントリ数: {len(browser._entries)}")
                log_print(INFO, f"設定: pages={current_pages}, shift={current_shift}")
                current_entries = browser.get_current()
                current_path_info = current_entries[0] if current_entries else "N/A"
                log_print(INFO, f"カレントパス: {current_path_info}")
                return True
            else:
                log_print(WARNING, "ブラウザは初期化されましたが、エントリが見つかりませんでした")
                return False
        else:
            log_print(ERROR, f"エラー: アーカイブマネージャーはこのファイルを処理できません: {path}")
            return False
    except Exception as e:
        log_print(ERROR, f"エラー: アーカイブの設定に失敗しました: {e}")
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
    if (args_str.startswith('"') and args_str.endswith('"')) or \
       (args_str.startswith("'") and args_str.endswith("'")):
        # 引用符を除去
        return args_str[1:-1]
    
    return args_str


def list_matching_entries(prefix: str) -> bool:
    """
    指定された接頭辞に一致するエントリを表示
    
    Args:
        prefix: 検索する接頭辞
        
    Returns:
        一致するエントリがある場合はTrue、ない場合はFalse
    """
    global browser
    
    if not browser or not browser._entries:
        log_print(ERROR, "エラー: ブラウザが初期化されていないか、エントリがありません")
        return False
    
    # 接頭辞が空の場合は全エントリを表示
    if not prefix:
        print("\n全エントリ一覧:")
    else:
        print(f"\n接頭辞 '{prefix}' に一致するエントリ:")
    
    # 前方一致するエントリを検索
    matching_entries = []
    for entry in browser._entries:
        if not prefix or entry.startswith(prefix):
            matching_entries.append(entry)
    
    # 結果を表示
    if not matching_entries:
        print("一致するエントリがありません")
        return False
    
    # エントリを表示
    print("-" * 80)
    for i, entry in enumerate(matching_entries, 1):
        print(f"{i:4d}: {entry}")
    print("-" * 80)
    print(f"合計: {len(matching_entries)} エントリ")
    
    return True


def list_folder_entries() -> bool:
    """
    現在のフォルダ内のエントリだけを表示する
    
    Returns:
        エントリがある場合はTrue、ない場合はFalse
    """
    global browser
    
    if not browser or not browser._entries:
        log_print(ERROR, "エラー: ブラウザが初期化されていないか、エントリがありません")
        return False
    
    # 現在のフォルダを取得
    current_folder = browser._get_current_folder()
    print(f"\n現在のフォルダ '{current_folder}' のエントリ一覧:")
    
    # 同じフォルダのエントリを検索
    folder_entries = []
    for entry in browser._entries:
        if os.path.dirname(entry) == current_folder:
            folder_entries.append(entry)
    
    # 結果を表示
    if not folder_entries:
        print("フォルダ内にエントリがありません")
        return False
    
    # エントリを表示
    print("-" * 80)
    for i, entry in enumerate(folder_entries, 1):
        print(f"{i:4d}: {entry}")
    print("-" * 80)
    print(f"合計: {len(folder_entries)} エントリ")
    
    return True


def main():
    """メインのCLIループ"""
    global debug_mode, browser
    
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
            # ブラウザが有効な場合はカレントパスを表示、無効な場合は「無効」と表示
            current_path = "無効"
            if browser and browser._entries:
                current_entries = browser.get_current()
                if current_entries:
                    current_path = current_entries[0]
            
            prompt = f"\nブラウザ [{current_path}] > "
            cmd_input = input(prompt).strip()
            
            if not cmd_input:
                continue
                
            cmd = cmd_input.upper()
            
            # コマンド処理
            if cmd == 'Q':
                log_print(INFO, "終了します。")
                break
            elif cmd == '?':
                print_help()
            elif cmd == 'D':
                # Dコマンドでログレベル切り替え
                toggle_log_level()
                continue
            elif cmd == 'A' and browser:  # Pから変更
                # Aコマンドでpagesを1と2の間で切り替え
                current_pages = getattr(browser, '_pages', 1)
                new_pages = 2 if current_pages == 1 else 1
                current_path = browser._entries[browser._current_idx] if browser._entries else ""
                if current_archive_path:
                    set_archive_path(current_archive_path, new_pages, getattr(browser, '_shift', False))
                    # 元の位置にジャンプ
                    if current_path:
                        try:
                            browser.jump(current_path)
                        except:
                            pass
                    log_print(INFO, f"pagesを{new_pages}に変更しました")
                    current_entries = browser.get_current()
                    print("\n現在のカレントエントリ:")
                    print("-" * 80)
                    for i, entry in enumerate(current_entries, 1):
                        print(f"{i}. {entry}")
                    print("-" * 80)
                continue
            elif cmd == 'T' and browser:
                # Tコマンドでshiftをtrue/falseの間で切り替え
                current_shift = getattr(browser, '_shift', False)
                new_shift = not current_shift
                current_path = browser._entries[browser._current_idx] if browser._entries else ""
                if current_archive_path:
                    set_archive_path(current_archive_path, getattr(browser, '_pages', 1), new_shift)
                    # 元の位置にジャンプ
                    if current_path:
                        try:
                            browser.jump(current_path)
                        except:
                            pass
                    log_print(INFO, f"shiftを{new_shift}に変更しました")
                    current_entries = browser.get_current()
                    print("\n現在のカレントエントリ:")
                    print("-" * 80)
                    for i, entry in enumerate(current_entries, 1):
                        print(f"{i}. {entry}")
                    print("-" * 80)
                continue
            elif cmd == 'C':  # カレントエントリ表示コマンド
                if not browser:
                    log_print(ERROR, "エラー: ブラウザが初期化されていません。先に 'S <path>' コマンドを実行してください。")
                    continue
                    
                current_entries = browser.get_current()
                if not current_entries:
                    print("カレントエントリがありません")
                else:
                    print("\n現在のカレントエントリ:")
                    print("-" * 80)
                    for i, entry in enumerate(current_entries, 1):
                        print(f"{i}. {entry}")
                    print("-" * 80)
                continue
            
            # ブラウザナビゲーションコマンド
            if cmd_input == 'lf' and browser:
                list_folder_entries()
                continue
            elif cmd_input == 'n' and browser:
                path = browser.next()
                log_print(INFO, f"次のエントリに移動: {path}")
                current_entries = browser.get_current()
                print("\n現在のカレントエントリ:")
                print("-" * 80)
                for i, entry in enumerate(current_entries, 1):
                    print(f"{i}. {entry}")
                print("-" * 80)
                continue
            elif cmd_input == 'p' and browser:
                path = browser.prev()
                log_print(INFO, f"前のエントリに移動: {path}")
                current_entries = browser.get_current()
                print("\n現在のカレントエントリ:")
                print("-" * 80)
                for i, entry in enumerate(current_entries, 1):
                    print(f"{i}. {entry}")
                print("-" * 80)
                continue
            elif cmd_input == 'nn' and browser:
                path = browser.next_folder()
                log_print(INFO, f"次のフォルダの先頭に移動: {path}")
                current_entries = browser.get_current()
                print("\n現在のカレントエントリ:")
                print("-" * 80)
                for i, entry in enumerate(current_entries, 1):
                    print(f"{i}. {entry}")
                print("-" * 80)
                continue
            elif cmd_input == 'pp' and browser:
                path = browser.prev_folder()
                log_print(INFO, f"前のフォルダの末尾に移動: {path}")
                current_entries = browser.get_current()
                print("\n現在のカレントエントリ:")
                print("-" * 80)
                for i, entry in enumerate(current_entries, 1):
                    print(f"{i}. {entry}")
                print("-" * 80)
                continue
            elif cmd_input == 'gf' and browser:
                path = browser.go_first()
                log_print(INFO, f"リストの先頭に移動: {path}")
                current_entries = browser.get_current()
                print("\n現在のカレントエントリ:")
                print("-" * 80)
                for i, entry in enumerate(current_entries, 1):
                    print(f"{i}. {entry}")
                print("-" * 80)
                continue
            elif cmd_input == 'gl' and browser:
                path = browser.go_last()
                log_print(INFO, f"リストの末尾に移動: {path}")
                current_entries = browser.get_current()
                print("\n現在のカレントエントリ:")
                print("-" * 80)
                for i, entry in enumerate(current_entries, 1):
                    print(f"{i}. {entry}")
                print("-" * 80)
                continue
            elif cmd_input == 'gt' and browser:
                path = browser.go_top()
                log_print(INFO, f"フォルダ内の先頭に移動: {path}")
                current_entries = browser.get_current()
                print("\n現在のカレントエントリ:")
                print("-" * 80)
                for i, entry in enumerate(current_entries, 1):
                    print(f"{i}. {entry}")
                print("-" * 80)
                continue
            elif cmd_input == 'ge' and browser:
                path = browser.go_end()
                log_print(INFO, f"フォルダ内の末尾に移動: {path}")
                current_entries = browser.get_current()
                print("\n現在のカレントエントリ:")
                print("-" * 80)
                for i, entry in enumerate(current_entries, 1):
                    print(f"{i}. {entry}")
                print("-" * 80)
                continue
                
            # 単一文字コマンドとその引数の処理
            cmd = cmd_input[0].lower()  # lコマンドを小文字で処理するために小文字に統一
            args_str = cmd_input[1:].strip() if len(cmd_input) > 1 else ""
            
            # 引数を解析（引用符で囲まれたパスを適切に処理）
            args = parse_command_args(args_str)
            
            if cmd == 's':
                if not args:
                    log_print(ERROR, "エラー: アーカイブパスを指定してください。例: S /path/to/archive.zip")
                    log_print(INFO, "       空白を含むパスは S \"C:/Program Files/file.zip\" のように指定してください")
                else:
                    set_archive_path(args)
            elif cmd == 'j':
                if not browser:
                    log_print(ERROR, "エラー: ブラウザが初期化されていません。先に 'S <path>' コマンドを実行してください。")
                elif not args:
                    log_print(ERROR, "エラー: ジャンプ先のパスを指定してください。例: j /path/to/file.txt")
                else:
                    try:
                        path = browser.jump(args)
                        log_print(INFO, f"パス '{args}' にジャンプしました")
                    except FileNotFoundError as e:
                        log_print(ERROR, f"予期された例外: {e}")
                        log_print(INFO, "指定されたパスにジャンプできませんでした。パスが正しく、アーカイブ内に存在することを確認してください。")
                    except Exception as e:
                        log_print(ERROR, f"予期しない例外が発生しました: {e}")
                        if debug_mode:
                            traceback.print_exc()
            elif cmd == 'l':
                list_matching_entries(args)
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
    parser = argparse.ArgumentParser(description="アーカイブブラウザのテストツール")
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
