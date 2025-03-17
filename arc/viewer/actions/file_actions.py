"""
ファイル関連アクション

ファイルやフォルダに関する操作を処理するアクションハンドラ
"""

import os
import sys
import traceback
from typing import Optional, Callable, Dict, Any, List

# 親パッケージからインポートできるようにパスを調整
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# ロギングユーティリティをインポート
from logutils import log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL
from arc.path_utils import normalize_path
from arc.arc import EntryType

try:
    from PySide6.QtWidgets import QMessageBox, QWidget, QApplication
    from PySide6.QtCore import Qt
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

from ..models.archive_manager_wrapper import ArchiveManagerWrapper
from ..debug_utils import ViewerDebugMixin


class FileActionHandler(ViewerDebugMixin):
    """ファイル関連のアクション処理を行うハンドラ"""
    
    def __init__(self, archive_manager: ArchiveManagerWrapper, parent_widget: QWidget = None):
        """
        初期化
        
        Args:
            archive_manager: アーカイブマネージャーラッパー
            parent_widget: メッセージボックス等の親ウィジェット
        """
        # ViewerDebugMixinの初期化
        self._init_debug_mixin("FileActionHandler")
        
        self.archive_manager = archive_manager
        self.parent_widget = parent_widget
        
        # コールバック
        self.on_directory_loaded = None  # ディレクトリ読み込み時のコールバック
        self.on_path_changed = None  # パス変更時のコールバック
        self.on_status_message = None  # ステータスメッセージ更新時のコールバック
        self.on_loading_start = None  # 読み込み開始時のコールバック
        self.on_loading_end = None  # 読み込み完了時のコールバック
        
        # 最後に表示したステータスメッセージを保存
        self._last_status_message = ""
        
        self.debug_info("FileActionHandlerを初期化しました")
    
    @property
    def debug_mode(self) -> bool:
        """デバッグモードの取得"""
        return self.archive_manager.debug_mode
    
    @debug_mode.setter
    def debug_mode(self, value: bool):
        """デバッグモードの設定（アーカイブマネージャーと同期）"""
        self.archive_manager.debug_mode = value
        self.debug_info(f"デバッグモードを {value} に設定しました")
    
    def open_path(self, path: str) -> bool:
        """
        指定されたパスを開く（ドロップ時または外部からの絶対パス指定のみ）
        
        Args:
            path: 開くパス（フォルダまたはアーカイブファイル）
            
        Returns:
            bool: 成功したかどうか
        """
        try:
            self.debug_info(f"パスを開きます: {path}")
            
            # 読み込み開始を通知（カーソルを砂時計に変更など）
            self._notify_loading_start()
            
            # ステータスメッセージを更新（読み込み中）
            loading_message = f"'{os.path.basename(path)}' を読み込んでいます..."
            self._update_status(loading_message)
            
            # 重要: UIの更新を待つために、イベントループを一度処理する
            QApplication.processEvents()
            
            # パスが存在するか確認（os.pathを使うのはドロップ時の最初の絶対パス確認のみ）
            if not os.path.exists(path):
                self._show_error("パスエラー", f"指定されたパスが存在しません: {path}")
                self.debug_error(f"パスが存在しません: {path}")
                self._notify_loading_end()  # 処理完了通知
                return False
            
            # バックエンドでパスを開く
            success = self.archive_manager.open(path)
            if not success:
                self._show_error("オープンエラー", f"パスを開けませんでした: {path}")
                self.debug_error(f"パスを開けませんでした: {path}")
                self._notify_loading_end()  # 処理完了通知
                return False
            
            # 現在のディレクトリの内容を読み込む
            self._load_current_directory()
            
            # パス変更を通知
            if self.on_path_changed:
                # ベースパスをUI表示用に通知、相対パスは空
                self.on_path_changed(path, "")
            
            # アーカイブ情報を表示
            self._show_archive_info()
            
            self.debug_info(f"パスが正常に開かれました: {path}")
            
            # 処理完了通知
            self._notify_loading_end()
            return True
            
        except Exception as e:
            self._show_error("エラー", f"パスを開く際にエラーが発生しました:\n{str(e)}")
            self.debug_error(f"パスを開く際に例外が発生しました: {str(e)}", trace=True)
            self._notify_loading_end()  # 処理完了通知
            return False
    
    def navigate_to(self, path: str) -> bool:
        """
        指定したパスに移動
        
        Args:
            path: 移動先のパス
                - 最初のドロップ/オープン時のみ絶対パスが許可される
                - 内部ナビゲーションはすべて相対パスで処理
            
        Returns:
            bool: 成功したかどうか
        """
        # 最初のみ許可される絶対パス（ドロップ/オープン時）
        if not self.archive_manager.current_path and os.path.exists(path):
            return self.open_path(path)
            
        # アーカイブが開かれていない場合
        if not self.archive_manager.current_path:
            self._show_error("ナビゲーションエラー", "先にアーカイブやフォルダを開いてください")
            return False

        # パス文字列からベースパスの部分を除去して内部パスを抽出
        internal_path = self._extract_internal_path(path)
        if internal_path is None:
            self._show_error("ナビゲーションエラー", f"無効なパス形式です: {path}")
            self.debug_error(f"無効なパス形式: {path}")
            return False
        
        # 内部パスに対して処理
        if ':/' in internal_path:
            # コロンが含まれる場合は絶対パスの一部と判断し、エラー
            self.debug_error(f"不正なパス形式（コロンを含む）: {internal_path}")
            self._show_error("ナビゲーションエラー", f"無効なパス形式です: {internal_path}")
            return False
        
        # 相対パスとして処理
        return self._navigate_internal(internal_path)
    
    def _extract_internal_path(self, path: str) -> Optional[str]:
        """
        表示用パスから内部相対パスを抽出する
        
        Args:
            path: 表示用パス
            
        Returns:
            Optional[str]: 内部相対パス、抽出できない場合はNone
        """
        # 相対パスの場合はそのまま返す
        if not path.startswith('/') and not ':/' in path:
            return path
            
        # ベースパスを取得
        base_path = self.archive_manager.current_path
        
        # アーカイブ内パス形式 "basepath:/internalpath" を処理
        if ':/' in path:
            parts = path.split(':', 1)
            if len(parts) == 2 and parts[1].startswith('/'):
                # 先頭の / を除去
                return parts[1][1:] if len(parts[1]) > 1 else ""
        
        # 物理フォルダのパスを処理
        if path.startswith(base_path):
            if path == base_path:
                # ベースパスと同じなら空文字（ルート）を返す
                return ""
            
            # ベースパスより長いかを確認
            if len(path) > len(base_path):
                # ベースパスの後に / または \ がある場合は1文字多く除去
                sep_pos = len(base_path)
                if path[sep_pos] in ['/', '\\']:
                    sep_pos += 1
                # ベースパスを除去して相対パスを返す
                return path[sep_pos:]
        
        # マッチしない場合はNoneを返す
        return None
    
    def _navigate_internal(self, path: str) -> bool:
        """
        アーカイブ/フォルダ内の内部パス移動処理
        
        Args:
            path: 内部パス（相対パスのみサポート）
            
        Returns:
            bool: 成功したかどうか
        """
        try:
            # パスを正規化
            path = normalize_path(path)
            self.debug_info(f"内部パスに移動: '{path}'")
            
            # ステータスメッセージを更新（読み込み中）
            loading_message = f"'{path}' に移動しています..."
            self._update_status(loading_message)
            
            # UIの更新を待つために、イベントループを一度処理する
            QApplication.processEvents()
            
            # ディレクトリ変更（必ず相対パスとして扱う）
            success = self.archive_manager.change_directory(path)
            if not success:
                self._show_error("ナビゲーションエラー", f"指定されたパスに移動できませんでした: {path}")
                return False
            
            # 現在のディレクトリの内容を読み込む
            self._load_current_directory()
            
            # パス変更を通知（相対パスのみ）
            if self.on_path_changed:
                # 現在の相対パスを通知（表示用と内部パスは同じ）
                rel_path = self.archive_manager.current_directory
                display_path = self.archive_manager.get_full_path()  # 以前のコードとの互換性のため残す
                self.on_path_changed(display_path, rel_path)
            
            return True
                
        except Exception as e:
            self._show_error("ナビゲーションエラー", f"指定されたパスに移動できませんでした:\n{str(e)}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            return False
    
    def handle_item_activated(self, name: str, is_dir: bool) -> bool:
        """
        アイテムがアクティブになった（ダブルクリックまたはシングルクリック）ときの処理
        
        Args:
            name: アイテム名（カレントディレクトリからの相対名）
            is_dir: ディレクトリかどうか
            
        Returns:
            bool: 処理に成功したかどうか
        """
        if is_dir:
            # ディレクトリの場合は移動
            try:
                # ステータスメッセージを更新（読み込み中）
                loading_message = f"'{name}' に移動しています..."
                self._update_status(loading_message)
                
                # UIの更新を待つためにイベントループを処理
                QApplication.processEvents()
                
                if name == "..":
                    self.debug_info("親ディレクトリに移動")
                    success = self.archive_manager.change_directory("..")
                else:
                    self.debug_info(f"ディレクトリに移動: '{name}'")
                    success = self.archive_manager.change_directory(name)
                    
                if not success:
                    self._show_error("ディレクトリエラー", f"ディレクトリに移動できませんでした: {name}")
                    return False
                
                # 現在のディレクトリの内容を読み込む
                self._load_current_directory()
                
                # パス変更を通知
                if self.on_path_changed:
                    rel_path = self.archive_manager.current_directory
                    display_path = self.archive_manager.get_full_path()
                    self.on_path_changed(display_path, rel_path)
                
                return True
                
            except Exception as e:
                self._show_error("ディレクトリエラー", f"ディレクトリに移動できませんでした:\n{str(e)}")
                if self.debug_mode:
                    traceback.print_exc()
                return False
        else:
            # ファイルの場合のアクション
            if self.on_status_message:
                self.on_status_message(f"ファイル '{name}' を選択しました")
            # TODO: ファイルプレビューの実装
            return True
    
    def _load_current_directory(self) -> bool:
        """
        現在のディレクトリの内容をロード
        
        Returns:
            bool: 成功したかどうか
        """
        try:
            # アーカイブマネージャーから現在のディレクトリの内容を取得
            items = self.archive_manager.list_items()
            
            # 結果をコールバックで通知
            if self.on_directory_loaded:
                self.on_directory_loaded(items)
            
            # ステータスメッセージ更新
            if self.on_status_message:
                dir_count = sum(1 for item in items if item.get('is_dir', False))
                file_count = len(items) - dir_count
                self.on_status_message(f"{len(items)} アイテム ({dir_count} フォルダ, {file_count} ファイル)")
            
            return True
            
        except Exception as e:
            self._show_error("読み込みエラー", f"ディレクトリの内容を読み込めませんでした:\n{str(e)}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            if self.on_directory_loaded:
                self.on_directory_loaded([])
            return False
    
    def _show_archive_info(self) -> None:
        """
        アーカイブの情報をステータスバーに表示
        """
        try:
            # アーカイブ情報を取得
            archive_info = self.archive_manager.get_archive_info()
            path = archive_info.get('path', '')
            
            # 基本情報を表示
            if path:
                # ファイルの判定はマネージャから取得した情報で行う（os.path.isfile使用しない）
                entry_type = archive_info.get('type', '')
                
                if entry_type == EntryType.ARCHIVE.name or entry_type == EntryType.FILE.name:
                    size_str = f"{archive_info.get('size', 0):,} バイト"
                    entries_str = f"{archive_info.get('entries', 0)} エントリ"
                    status_message = f"アーカイブを開きました: {os.path.basename(path)} ({size_str}, {entries_str})"
                else:
                    status_message = f"フォルダを開きました: {os.path.basename(path)}"
                    
                # 最後のステータスメッセージを保存してから表示
                self._last_status_message = status_message
                self._update_status(status_message)
                
        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
    
    def _show_error(self, title: str, message: str) -> None:
        """エラーメッセージを表示"""
        self.debug_error(f"{title}: {message}")
        if self.parent_widget:
            QMessageBox.warning(self.parent_widget, title, message)
        else:
            log_print(ERROR, f"{title}: {message}")
    
    def _notify_loading_start(self):
        """読み込み開始を通知（カーソルを砂時計に変更など）"""
        if hasattr(self, 'on_loading_start') and callable(self.on_loading_start):
            self.on_loading_start()
    
    def _notify_loading_end(self):
        """読み込み完了を通知（カーソルを通常に戻すなど）"""
        # カーソルを元に戻す
        if hasattr(self, 'on_loading_end') and callable(self.on_loading_end):
            self.on_loading_end()
            
        # 保存されている最後のステータスメッセージを表示
        # これにより、読み込み中のメッセージが残ることを防ぐ
        if hasattr(self, '_last_status_message') and self._last_status_message:
            self._update_status(self._last_status_message)
    
    def _update_status(self, message: str) -> None:
        """
        ステータスメッセージを更新する（ヘルパーメソッド）
        
        Args:
            message: 表示するメッセージ
        """
        if self.on_status_message:
            self.on_status_message(message)
