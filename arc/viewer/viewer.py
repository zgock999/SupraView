"""
アーカイブビューア

フォルダとアーカイブ書庫のコンテンツをエクスプローラーの「大アイコン」表示と同様に
表示するためのビューアアプリケーション。
"""

import os
import sys
import argparse
from typing import List, Dict, Any, Optional

# 親パッケージからインポートできるようにパスを調整
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# ロギングユーティリティをインポート
from logutils import setup_logging, log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout,
        QStatusBar, QMessageBox, QMenuBar, QMenu, QToolBar, QFileDialog
    )
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QAction
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 内部モジュールのインポート
from .models.archive_manager_wrapper import ArchiveManagerWrapper
from .widgets.file_list_view import FileListView
from .widgets.path_navigation import PathNavigationBar
from .actions.file_actions import FileActionHandler
from .debug_utils import ViewerDebugMixin


class ViewerWindow(QMainWindow, ViewerDebugMixin):
    """アーカイブビューアのメインウィンドウ"""
    
    def __init__(self, debug_mode=False):
        super().__init__()
        # ViewerDebugMixinの初期化
        self._init_debug_mixin("ViewerWindow")
        
        self.setWindowTitle("SupraView - アーカイブビューア")
        self.setMinimumSize(800, 600)
        
        # モデルの初期化
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
        self._setup_menu()
        
        # イベントハンドラとコールバックの接続
        self._connect_signals()
        
        # ステータスバーの初期メッセージ
        if debug_mode:
            self.statusBar().showMessage("デバッグモードが有効です。フォルダまたはアーカイブファイルをドロップしてください")
        else:
            self.statusBar().showMessage("フォルダまたはアーカイブファイルをドロップしてください")
        
        self.debug_info("アプリケーション初期化完了")
        
        # ドラッグ＆ドロップを有効化
        self.setAcceptDrops(True)
    
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
        
        # ステータスバー
        self.setStatusBar(QStatusBar())
        
        # 中央ウィジェットを設定
        self.setCentralWidget(central_widget)
    
    def _setup_menu(self):
        """メニューの設定"""
        # メニューバーの作成
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        
        # ファイルメニュー
        file_menu = QMenu("ファイル(&F)", self)
        menu_bar.addMenu(file_menu)
        
        # 開くアクション
        open_action = QAction("開く(&O)...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        # 終了アクション
        exit_action = QAction("終了(&X)", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 表示メニュー
        view_menu = QMenu("表示(&V)", self)
        menu_bar.addMenu(view_menu)
        
        # デバッグモードの切り替え
        debug_action = QAction("デバッグモード(&D)", self)
        debug_action.setCheckable(True)
        debug_action.setChecked(self.file_action_handler.debug_mode)
        debug_action.triggered.connect(self._toggle_debug_mode)
        view_menu.addAction(debug_action)
    
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
    
    def _open_file_dialog(self):
        """ファイル選択ダイアログを開く"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "アーカイブを開く",
            "",
            "すべてのファイル (*.*)"
        )
        
        if path:
            self._handle_open_path(path)
    
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
            self.debug_info(f"パスの読み込み成功: {path}")
        else:
            self.debug_error(f"パスの読み込み失敗: {path}")
    
    def _handle_path_navigation(self, path: str):
        """
        パスナビゲーションからのパス変更ハンドラ
        
        Args:
            path: 履歴から復元された相対パス
        """
        self.debug_info(f"パスナビゲーション: 相対パス '{path}'")
        # 履歴からの相対パス（空文字はルート）をナビゲーション
        self.file_action_handler.navigate_to(path)
    
    def _handle_item_activated(self, name: str, is_dir: bool):
        """アイテムアクティベートハンドラ"""
        self.file_action_handler.handle_item_activated(name, is_dir)
    
    def _handle_directory_loaded(self, items: List[Dict[str, Any]]):
        """ディレクトリ読み込み完了時のハンドラ"""
        # ルートディレクトリかどうかを判定
        in_root = self.archive_manager.current_directory == ""
        self.file_view.file_model.set_items(items, in_root=in_root)
    
    def _handle_path_changed(self, display_path: str, rel_path: str = ""):
        """
        パス変更時のハンドラ
        
        Args:
            display_path: 表示用の完全なパス（互換性のために残す）
            rel_path: 内部参照用の相対パス
        """
        # 表示用と内部相対パスを両方設定（表示には相対パスを使用）
        self.path_nav.set_path(display_path, rel_path)
    
    def _handle_status_message(self, message: str):
        """ステータスメッセージ更新ハンドラ"""
        self.statusBar().showMessage(message)
    
    def _handle_loading_start(self):
        """読み込み開始時の処理"""
        # カーソルを砂時計（待機中）に変更
        QApplication.setOverrideCursor(Qt.WaitCursor)
    
    def _handle_loading_end(self):
        """読み込み完了時の処理"""
        # カーソルを元に戻す
        QApplication.restoreOverrideCursor()


def main():
    """アプリケーションのエントリポイント"""
    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(description="SupraView - アーカイブビューア")
    parser.add_argument("path", nargs="?", help="開くファイルまたはディレクトリのパス")
    parser.add_argument("--debug", action="store_true", help="デバッグモードで起動")
    args = parser.parse_args()
    
    # デバッグモードが指定されていれば、ログレベルを調整
    log_level = DEBUG if args.debug else ERROR  # INFOからDEBUGに変更
    setup_logging(log_level)
    
    if args.debug:
        log_print(INFO, "デバッグモードが有効化されました")
    
    app = QApplication(sys.argv)
    
    # スタイルシートを適用（オプション）
    app.setStyle("Fusion")
    
    # デバッグモード設定をウィンドウに渡す
    window = ViewerWindow(debug_mode=args.debug)
    window.show()
    
    # コマンドライン引数でパスが指定されていれば開く
    if args.path:
        window.file_action_handler.open_path(args.path)
    
    log_print(INFO, "アプリケーション実行開始")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
