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
from decoder.interface import get_supported_image_extensions


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
        
        # デコーダーでサポートされている画像拡張子のリストを取得
        self.supported_image_extensions = get_supported_image_extensions()
        
        # デバッグ情報を追加
        self.debug_info(f"サポートされている画像拡張子: {self.supported_image_extensions}")
        
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
        if not self.archive_manager.current_path:
            return self.open_path(path)
        
        # 内部パスに対して処理
        if ':/' in path:
            # アーカイブ内のパス表記からの相対パス抽出
            parts = path.split(':', 1)
            if len(parts) == 2 and parts[1].startswith('/'):
                # 先頭の / を除去して相対パス化
                rel_path = parts[1][1:] if len(parts[1]) > 1 else ""
                return self._navigate_internal(rel_path)
        elif path.startswith('/'):
            # 絶対パス形式なら先頭の / を除去
            rel_path = path[1:] if len(path) > 1 else ""
            return self._navigate_internal(rel_path)
        
        # 相対パスはそのまま処理
        return self._navigate_internal(path)
    
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
            
            # ディレクトリ変更（直接ラッパーに委任）
            success = self.archive_manager.change_directory(path)
            if not success:
                self._show_error("ナビゲーションエラー", f"指定されたパスに移動できませんでした: {path}")
                return False
            
            # 現在のディレクトリの内容を読み込む
            self._load_current_directory()
            
            # パス変更を通知（相対パスのみ）
            if self.on_path_changed:
                # 現在の相対パスを通知
                rel_path = self.archive_manager.current_directory
                display_path = self.archive_manager.get_full_path()
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
                    # change_directoryからnavigate_to_itemに変更
                    success = self.archive_manager.navigate_to_item(name)
                    
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
            try:
                # ステータスメッセージを更新
                self.on_status_message(f"ファイル '{name}' を読み込んでいます...")
                
                # UIの更新を待つためにイベントループを処理
                QApplication.processEvents()
                
                # ファイル名の拡張子を取得
                _, ext = os.path.splitext(name.lower())
                
                # デバッグ出力を追加
                self.debug_info(f"ファイル拡張子: '{ext}', サポートされている拡張子: {self.supported_image_extensions}")
                self.debug_info(f"拡張子判定結果: {ext in self.supported_image_extensions}")
                
                # 画像ファイルの場合はプレビューウィンドウを表示
                if ext in self.supported_image_extensions:
                    self.debug_info(f"画像ファイルを開きます: {name}")
                    return self._open_image_preview(name)
                else:
                    # その他のファイルはhexdumpビューアを表示
                    self.debug_info(f"バイナリファイルを開きます: {name}")
                    return self._open_hexdump_viewer(name)
                
            except Exception as e:
                self._show_error("ファイルエラー", f"ファイルの処理中にエラーが発生しました:\n{str(e)}")
                if self.debug_mode:
                    import traceback
                    traceback.print_exc()
                return False
    
    def _open_image_preview(self, path: str) -> bool:
        """
        画像プレビューウィンドウを開く
        
        Args:
            path: プレビューする画像ファイルのパス（カレントディレクトリからの相対パス）
            
        Returns:
            成功したかどうか
        """
        from app.viewer.widgets.preview import ImagePreviewWindow
        
        try:
            # ファイルデータを読み込む
            self.debug_info(f"画像ファイルを読み込みます: {path}")
            
            # プレビューウィンドウを作成
            preview_window = ImagePreviewWindow(parent=self.parent_widget, archive_manager=self.archive_manager)
            preview_window.setWindowTitle(f"画像プレビュー - {os.path.basename(path)}")
            
            # 画像データを読み込み - extract_file から extract_item に変更
            success = preview_window.load_image_from_path(path)
            
            if success:
                # ウィンドウを表示
                preview_window.show()
                self._update_status(f"画像をプレビュー中: {os.path.basename(path)}")
                return True
            else:
                self._update_status(f"画像の読み込みに失敗しました: {path}")
                return False
                
        except Exception as e:
            self._show_error("画像プレビュー表示中にエラーが発生しました", str(e))
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            return False
    
    def _open_hexdump_viewer(self, path: str) -> bool:
        """
        hexdumpビューアを開く
        
        Args:
            path: 表示するファイルのパス（カレントディレクトリからの相対パス）
            
        Returns:
            成功したかどうか
        """
        try:
            # ファイルの内容を読み込む - extract_file から extract_item に変更
            file_data = self.archive_manager.extract_item(path)
            if file_data is None:
                self._show_error("ファイル読み込みエラー", f"ファイル '{path}' を読み込めませんでした")
                return False
            
            # HexDumpViewをインポート（ここでインポートして循環参照を防ぐ）
            from ..widgets.hexdump import HexDumpView
            
            # 16進数ダンプビューウィンドウを作成
            hex_view = HexDumpView(
                parent=self.parent_widget,
                title=f"16進数ダンプ: {os.path.basename(path)}",
                bytes_data=file_data
            )
            
            # ウィンドウを表示
            hex_view.show()
            
            # ステータスメッセージを更新
            self._update_status(f"ファイル '{path}' を読み込みました ({len(file_data):,} バイト)")
            return True
            
        except Exception as e:
            self._show_error("ファイルエラー", f"ファイルの処理中にエラーが発生しました:\n{str(e)}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            return False
    
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
