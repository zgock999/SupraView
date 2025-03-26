#!/usr/bin/env python3
"""
SupraViewのメインビューア実行モジュール

このモジュールはデバッグ実行用のエントリーポイントを提供します。
"""

import os
import sys
import argparse
from typing import List, Dict, Any, Optional
import traceback
from pathlib import Path

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ロギングユーティリティをインポート
from logutils import setup_logging, log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL
from arc.manager.enhanced import EnhancedArchiveManager
from arc.handler.fs_handler import FileSystemHandler
from arc.handler.zip_handler import ZipHandler
from arc.handler.rar_handler import RarHandler
from arc.interface import get_archive_manager
from arc.arc import EntryInfo, EntryType
from arc.path_utils import normalize_path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout,
        QStatusBar, QMessageBox, QProgressDialog
    )
    from PySide6.QtCore import Qt, QSize, QCoreApplication, QThread, Signal
    from PySide6.QtGui import QDragEnterEvent, QDropEvent
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 内部モジュールのインポート
from .models.archive_manager_wrapper import ArchiveManagerWrapper
from .widgets.file_list_view import FileListView
from .widgets.path_navigation import PathNavigationBar
from .actions.file_actions import FileActionHandler
from .debug_utils import ViewerDebugMixin
from .menu.context import ViewerContextMenu

# 超解像処理モジュールのインポート
from sr.sr_base import SuperResolutionBase, SRMethod, SRResult
from sr.sr_utils import is_cuda_available, get_gpu_info, get_sr_method_from_string
from app.viewer.superres.sr_enhanced import EnhancedSRManager

# 追加のインポート
from PySide6.QtCore import QTimer
from .widgets.sr_settings_dialog import SuperResolutionSettingsDialog


class ViewerWindow(QMainWindow, ViewerDebugMixin):
    """アーカイブビューアのメインウィンドウ"""
    
    def __init__(self, debug_mode=False, sr_manager=None):
        super().__init__()
        # ViewerDebugMixinの初期化
        self._init_debug_mixin("ViewerWindow")
        
        self.setWindowTitle("SupraView - アーカイブビューア")
        self.setMinimumSize(800, 600)
        
        # デバッグモードフラグ設定（クラス属性として追加）
        self.debug_mode = debug_mode
        
        # 超解像マネージャをインスタンス変数として保存
        self.sr_manager = sr_manager
        
        # デバッグ情報を追加 - デコーダーのサポート拡張子を確認
        try:
            from decoder.interface import get_supported_image_extensions
            extensions = get_supported_image_extensions()
            self.debug_info(f"デコーダーがサポートする拡張子: {extensions}")
        except Exception as e:
            self.debug_error(f"デコーダー拡張子情報の取得に失敗: {e}")
        
        # アーカイブマネージャの初期化
        self.archive_manager = ArchiveManagerWrapper()
        
        # アクションハンドラの初期化
        self.file_action_handler = FileActionHandler(self.archive_manager, self)
        
        # 初期デバッグモードを設定
        if debug_mode:
            self.file_action_handler.debug_mode = True
            self.archive_manager.debug_mode = True
            setup_logging(DEBUG)  # INFOからDEBUGに変更
            self.debug_info("デバッグモードで起動しました")
        
        # UI初期化
        self._setup_ui()
        
        # イベントハンドラとコールバックの接続
        self._connect_signals()
        
        # コンテキストメニューの初期化（ナビゲーションコールバックを追加）
        self.context_menu = ViewerContextMenu(
            self, 
            self._handle_open_path,
            self._handle_navigate_to_folder
        )
        
        # ステータスバーの初期メッセージ
        if debug_mode:
            self.statusBar().showMessage("デバッグモードが有効です。フォルダまたはアーカイブファイルをドロップしてください")
        else:
            self.statusBar().showMessage("フォルダまたはアーカイブファイルをドロップしてください")
        
        self.debug_info("アプリケーション初期化完了")
        
        # ドラッグ＆ドロップを有効化
        self.setAcceptDrops(True)
        
        # 超解像処理関連のシグナル接続
        if self.sr_manager:
            self.connect_sr_signals()
    
    def connect_sr_signals(self):
        """
        超解像処理のコールバックを設定
        
        Note: シグナル接続からコールバックに変更
        """
        if self.sr_manager:
            # コールバック設定
            self.sr_manager.set_callbacks(
                progress_callback=self.update_sr_progress,
                completion_callback=self.on_sr_initialization_completed,
                settings_callback=self.on_sr_settings_changed
            )

    def update_sr_progress(self, message: str):
        """超解像処理の進捗メッセージを更新"""
        self.statusBar().showMessage(message)

    def on_sr_initialization_completed(self, success: bool):
        """超解像処理の初期化完了時の処理"""
        if success:
            method_name = self.sr_manager.get_method_display_name(self.sr_manager.method)
            self.statusBar().showMessage(f"{method_name} (x{self.sr_manager.scale}) モデルの初期化が完了しました")
            self.debug_info(f"超解像モデル初期化完了: {method_name}")
        else:
            self.statusBar().showMessage("超解像モデルの初期化に失敗しました")
            self.debug_error("超解像モデル初期化失敗")

    def on_sr_settings_changed(self, settings: Dict[str, Any]):
        """超解像設定変更時の処理"""
        method_name = self.sr_manager.get_method_display_name(self.sr_manager.method)
        self.statusBar().showMessage(f"超解像設定を更新しました: {method_name} (x{self.sr_manager.scale})")
        self.debug_info(f"超解像設定が更新されました: {method_name}")
    
    def show_sr_settings_dialog(self):
        """超解像設定ダイアログを表示"""
        # モデル初期化中は設定ダイアログを開かない
        if not self.sr_manager or self.sr_manager.is_initializing:
            QMessageBox.information(
                self,
                "初期化中",
                "モデルの初期化中です。しばらくお待ちください。"
            )
            return
        
        # 現在の設定を保存（キャンセル時のために）
        original_method = self.sr_manager.method
        original_scale = self.sr_manager.scale
        original_options = self.sr_manager.options.copy() if hasattr(self.sr_manager, 'options') and self.sr_manager.options else {}
        
        dialog = SuperResolutionSettingsDialog(
            self,
            options=original_options,
            current_method=original_method,
            current_scale=original_scale
        )
        
        if dialog.exec():
            # 設定を取得
            settings = dialog.get_settings()
            
            # 再初期化が必要かチェック
            need_reinit = self._check_need_reinit(settings)
                
            # 再初期化が必要ならダイアログ表示
            if need_reinit:
                progress_dialog = self._prepare_reinit_dialog()
                progress_dialog.show()
                
                # イベントループを実行して確実に表示されるようにする
                QCoreApplication.processEvents()
                    
            # 設定更新と結果処理のコールバック
            def on_settings_updated(success, message):
                # 設定更新結果を通知
                self.update_sr_progress(message)
                
                if success:
                    # 成功時のメッセージ
                    method_name = self.sr_manager.get_method_display_name(self.sr_manager.method)
                    self.statusBar().showMessage(f"超解像設定を更新しました: {method_name} (x{self.sr_manager.scale})")
                    self.debug_info(f"超解像設定が更新されました: {method_name}")
                else:
                    # 失敗時のメッセージ
                    self.statusBar().showMessage("設定更新に失敗しました")
                    self.debug_error("超解像設定の更新に失敗しました")
                    
                    # エラーメッセージを表示
                    QMessageBox.warning(
                        self,
                        "設定更新エラー",
                        "超解像設定の更新中にエラーが発生しました。\n元の設定に戻します。"
                    )
            
            # 設定を更新（コールバックで結果を処理）
            self.sr_manager.update_settings_with_callback(settings, on_settings_updated)
    
    def _check_need_reinit(self, settings):
        """再初期化が必要かどうか判定"""
        try:
            # 現在の設定を取得
            current_method = self.sr_manager.method
            current_scale = self.sr_manager.scale
            
            # 新しい設定を取得
            new_method = settings.get('method', current_method)
            new_scale = settings.get('scale', current_scale)
            
            # メソッドまたはスケールが変わる場合は再初期化が必要
            return new_method != current_method or new_scale != current_scale
        except:
            # エラー発生時は安全側に倒して再初期化必要と判断
            return True
    
    def _prepare_reinit_dialog(self):
        """再初期化ダイアログを準備して返す"""
        # 進捗ダイアログを作成
        progress = QProgressDialog(
            "超解像モデルを再初期化しています...",
            "バックグラウンド実行",  # キャンセルボタンのテキスト
            0, 0,  # 進捗範囲（不定）
            self
        )
        progress.setWindowTitle("モデル再初期化中")
        # ウィンドウモーダルに設定
        progress.setWindowModality(Qt.WindowModal)
        # 最小表示時間を設定
        progress.setMinimumDuration(0)
        
        # バックグラウンド実行ボタンの処理
        progress.canceled.connect(progress.close)
        
        # 進捗更新用コールバック
        def update_progress(message):
            if progress.isVisible():
                progress.setLabelText(message)
                # イベントループを実行して表示更新を保証
                QCoreApplication.processEvents()
        
        # 完了時コールバック
        def on_completed(success):
            if progress.isVisible():
                # 完了時にダイアログを閉じる
                progress.close()
                
                if not success:
                    # 失敗時のメッセージ表示
                    QMessageBox.warning(
                        self,
                        "再初期化エラー",
                        "モデルの再初期化に失敗しました。\n設定は元に戻されます。"
                    )
        
        # コールバックの登録
        self.sr_manager.set_callbacks(
            progress_callback=update_progress,
            completion_callback=on_completed
        )
        
        return progress
    
    def _setup_ui(self):
        """UIの初期化"""
        # 中央ウィジェット
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # パスナビゲーションバー
        self.path_nav = PathNavigationBar()
        main_layout.addWidget(self.path_nav)
        
        # ファイルリストビュー
        self.file_view = FileListView()
        main_layout.addWidget(self.file_view)
        
        # ファイルリストビューにアーカイブマネージャを設定
        self.file_view.set_archive_manager(self.archive_manager)
        
        # ステータスバー
        self.setStatusBar(QStatusBar())
        
        # 中央ウィジェットを設定
        self.setCentralWidget(central_widget)
    
    def _connect_signals(self):
        """シグナルとスロットの接続"""
        # パスナビゲーションバーのパス変更シグナル
        self.path_nav.path_changed.connect(self._handle_path_navigation)
        
        # ファイルビューのアイテムアクティベートシグナル
        self.file_view.item_activated.connect(self._handle_item_activated)
        
        # アクションハンドラにコールバック設定
        self.file_action_handler.on_directory_loaded = self._handle_directory_loaded
        self.file_action_handler.on_path_changed = self._handle_path_changed
        self.file_action_handler.on_status_message = self._handle_status_message
        
        # 読み込み状態通知用コールバックを追加
        self.file_action_handler.on_loading_start = self._handle_loading_start
        self.file_action_handler.on_loading_end = self._handle_loading_end
        
        # サムネイル生成スレッドのキャンセル用コールバックを設定（重要）
        self.file_action_handler.cancel_thumbnails_callback = self._cancel_thumbnails
    
    def _cancel_thumbnails(self):
        """サムネイル生成スレッドをキャンセルする"""
        self.debug_info("サムネイル生成スレッドをキャンセルします")
        # FileListViewのサムネイル生成タスクをキャンセル
        if hasattr(self, 'file_view') and hasattr(self.file_view, 'handle_folder_changed'):
            self.file_view.handle_folder_changed()
            # サムネイルの完全停止を少し待機
            QCoreApplication.processEvents()
    
    def contextMenuEvent(self, event):
        """コンテキストメニューイベント処理"""
        # メインウィンドウの空白部分でコンテキストメニューを表示
        self.context_menu.show(event.globalPos())
    
    def _open_file_dialog(self):
        """ファイル選択ダイアログを開く"""
        # 書庫を開くダイアログを使用する
        self.context_menu._on_open_archive()
    
    def _toggle_debug_mode(self, checked: bool):
        """デバッグモードの切り替え"""
        self.file_action_handler.debug_mode = checked
        if checked:
            # デバッグモード有効時はDEBUGレベルに設定（INFOからDEBUGに変更）
            setup_logging(DEBUG)
            self.statusBar().showMessage("デバッグモードを有効化しました")
            self.debug_info("デバッグモードを有効化しました")
        else:
            # デバッグモード無効時はERRORレベルに設定
            setup_logging(ERROR)
            self.statusBar().showMessage("デバッグモードを無効化しました")
            self.debug_info("デバッグモードを無効化しました")
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """ドラッグエンターイベント処理"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """ドロップイベント処理"""
        urls = event.mimeData().urls()
        if urls:
            # 最初のURLだけを処理
            path = urls[0].toLocalFile()
            self._handle_open_path(path)
    
    def _handle_open_path(self, path: str):
        """パスを開く処理のハンドラ"""
        self.debug_info(f"パスを開きます: {path}")
        success = self.file_action_handler.open_path(path)
        if success:
            # ウィンドウタイトルを更新
            self.setWindowTitle(f"SupraView - {os.path.basename(path)}")
            
            # アーカイブオープン成功後にキャッシュからすべてのフォルダを取得してメニューを更新
            entry_cache = self.archive_manager.get_entry_cache()
            self.context_menu.update_from_cache(entry_cache)
            
            self.debug_info(f"パスの読み込み成功: {path}")
        else:
            self.debug_error(f"パスの読み込み失敗: {path}")
    
    def _handle_path_navigation(self, path: str):
        """
        パスナビゲーションからのパス変更ハンドラ
        
        Args:
            path: ナビゲーションバーから指定されたパス
        """
        self.debug_info(f"パスナビゲーション: パス '{path}'")
        self.file_action_handler.navigate_to(path)
    
    def _handle_navigate_to_folder(self, path: str):
        """
        フォルダメニューからのナビゲーションハンドラ
        
        Args:
            path: 移動先のフォルダパス
        """
        self.debug_info(f"フォルダメニューからのナビゲーション: '{path}'")
        # ファイルアクションハンドラを通じてナビゲーション
        self.file_action_handler.navigate_to(path)
    
    def _handle_item_activated(self, entry: EntryInfo):
        """
        ファイルビューのアイテムアクティベートハンドラ
        
        Args:
            entry (EntryInfo): アクティベートされたエントリ情報
        """
        self.debug_info(f"アイテムがアクティベートされました: {entry.path}")
        
        # EntryInfoオブジェクトをそのままFileActionHandlerに渡す
        self.file_action_handler.handle_entry_activated(entry)
    
    def _handle_directory_loaded(self, items: List[Dict[str, Any]]):
        """
        ディレクトリ読み込み完了ハンドラ
        
        Args:
            items: ディレクトリ内のアイテムリスト
        """
        self.debug_info(f"ディレクトリが読み込まれました: {len(items)}アイテム")
        # FileListViewにアイテムリストを設定
        self.file_view.set_items(items)
        
        # 表示用とナビゲーション用のパスを取得
        display_path = self.archive_manager.get_full_path()
        rel_path = self.archive_manager.current_directory
        
        # パスナビゲーションバーに設定
        self.path_nav.set_path(display_path, rel_path)
    
    def _handle_path_changed(self, display_path: str, rel_path: str):
        """
        パス変更ハンドラ
        
        Args:
            display_path: 表示用のパス
            rel_path: 内部参照用の相対パス
        """
        self.debug_info(f"パスが変更されました: 表示={display_path}, 相対={rel_path}")
        self.path_nav.set_path(display_path, rel_path)
    
    def _handle_status_message(self, message: str):
        """
        ステータスメッセージハンドラ
        
        Args:
            message (str): ステータスメッセージ
        """
        self.statusBar().showMessage(message)
    
    def _handle_loading_start(self):
        """読み込み開始ハンドラ"""
        # カーソルを砂時計（待機中）に変更
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage("読み込み中...")
    
    def _handle_loading_end(self):
        """読み込み終了ハンドラ"""
        # カーソルを元に戻す
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()


def main():
    """メイン関数"""
    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(description="SupraView - アーカイブビューア")
    parser.add_argument("path", nargs="?", help="開くファイルまたはディレクトリのパス")
    parser.add_argument("--debug", action="store_true", help="デバッグモードで起動")
    
    # ここでメソッド名を修正: parseArgs() -> parse_args()
    args = parser.parse_args()
    
    # デバッグモードが指定されていれば、ログレベルを調整
    log_level = DEBUG if args.debug else ERROR  # INFOからDEBUGに変更
    setup_logging(log_level)
    
    if args.debug:
        log_print(INFO, "デバッグモードが有効化されました")
    
    # アプリケーションの初期化
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # スタイルシートを適用
    
    # 超解像マネージャを作成して初期化
    sr_manager = initialize_sr_manager()
    
    # 初期化が失敗した場合はアプリケーション終了
    if not sr_manager:
        sys.exit(1)
    
    # 初期化済みの超解像マネージャを渡してビューアウィンドウを作成
    window = ViewerWindow(debug_mode=args.debug, sr_manager=sr_manager)
    window.show()
    
    # コマンドライン引数でパスが指定されていれば開く
    if args.path:
        window.file_action_handler.open_path(args.path)
    
    log_print(INFO, "アプリケーション実行開始")
    sys.exit(app.exec())


def initialize_sr_manager():
    """超解像マネージャの初期化"""
    # 進捗ダイアログを作成
    progress = QProgressDialog(
        "超解像モデルを初期化しています...",
        "キャンセル",  # キャンセルボタンのテキスト
        0, 0,  # 進捗範囲（不定）
        None
    )
    progress.setWindowTitle("超解像モデル初期化中")
    progress.setWindowModality(Qt.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.canceled.connect(QApplication.quit)  # キャンセル時はアプリケーション終了
    progress.show()
    
    # 拡張したSuperResolutionManagerの生成
    sr_manager = EnhancedSRManager()
    
    # 進捗表示用コールバック
    def update_progress(message):
        if progress.isVisible():
            progress.setLabelText(message)
            # イベントループを実行して表示を更新
            QCoreApplication.processEvents()
    
    # 初期化完了時の処理
    def on_init_completed(success):
        # 進捗ダイアログを閉じる
        progress.close()
        
        if not success:
            # 初期化失敗時のエラーメッセージ
            QMessageBox.critical(
                None,
                "初期化エラー",
                "超解像モデルの初期化に失敗しました。\n"
                "アプリケーションを終了します。"
            )
            QApplication.quit()
    
    # コールバックを設定
    sr_manager.set_callbacks(
        progress_callback=update_progress,
        completion_callback=on_init_completed
    )
    
    # 初期化パラメータの設定（デフォルト値）
    method = SRMethod.REALESRGAN
    scale = 4
    options = {
        'tile': 512,
        'tile_pad': 32,
        'variant': 'denoise',
        'denoise_strength': 0.5,
        'auto_download': True,
        'face_enhance': False
    }
    
    # 初期化を実行
    update_progress(f"モデル {method.name} (x{scale}) の初期化中...")
    success = sr_manager.initialize(method, scale, options)
    
    # 初期化結果を返す
    if success:
        progress.close()
        return sr_manager
    else:
        on_init_completed(False)
        return None


if __name__ == "__main__":
    main()