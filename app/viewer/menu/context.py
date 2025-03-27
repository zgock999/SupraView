"""
コンテキストメニュー

アプリケーション内で使用するコンテキストメニューの実装
"""

import os
import sys
from typing import Callable, Optional, Dict, List, Any

try:
    from PySide6.QtWidgets import QMenu, QFileDialog, QWidget, QApplication
    from PySide6.QtGui import QAction
    from PySide6.QtCore import Qt
except ImportError:
    print("PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 共通のフォルダメニュービルダーをインポート
from .folder_menu import FolderMenuBuilder


class ViewerContextMenu:
    """ビューアアプリケーション用のコンテキストメニュー"""
    
    def __init__(self, parent: QWidget, open_callback: Callable[[str], None], 
                 navigate_callback: Callable[[str], None] = None):
        """
        コンテキストメニュー初期化
        
        Args:
            parent: 親ウィジェット
            open_callback: パスを開く際に呼び出すコールバック関数
            navigate_callback: フォルダ移動時に呼び出すコールバック関数
        """
        self.parent = parent
        self.open_callback = open_callback
        self.navigate_callback = navigate_callback
        
        # メインコンテキストメニュー
        self.menu = QMenu(parent)
        
        # 「書庫を開く」アクション
        self.open_archive_action = QAction("書庫を開く...", parent)
        self.open_archive_action.triggered.connect(self._on_open_archive)
        self.menu.addAction(self.open_archive_action)
        
        # 「フォルダを開く」アクション
        self.open_folder_action = QAction("フォルダを開く...", parent)
        self.open_folder_action.triggered.connect(self._on_open_folder)
        self.menu.addAction(self.open_folder_action)
        
        # セパレータを追加
        self.menu.addSeparator()
        
        # 「フォルダに移動」サブメニュー
        self.folders_menu = QMenu("フォルダに移動", parent)
        self.folders_menu.setEnabled(False)  # 初期状態では無効
        self.menu.addMenu(self.folders_menu)
        
        # セパレータを追加
        self.menu.addSeparator()
        
        # 設定メニュー
        self.settings_menu = QMenu("設定", parent)
        
        # 超解像設定アクション
        self.sr_settings_action = QAction("超解像設定...", parent)
        self.sr_settings_action.triggered.connect(self._on_show_sr_settings)
        self.settings_menu.addAction(self.sr_settings_action)
        
        # 設定メニューを追加
        self.menu.addMenu(self.settings_menu)
    
    def show(self, position):
        """
        指定された位置にコンテキストメニューを表示
        
        Args:
            position: 表示位置
        """
        self.menu.exec_(position)
    
    def _on_open_archive(self):
        """「書庫を開く」アクション"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent,
            "書庫を開く",
            "",
            "すべてのファイル (*.*)"
        )
        
        if file_path:
            self.open_callback(file_path)
    
    def _on_open_folder(self):
        """「フォルダを開く」アクション"""
        folder_path = QFileDialog.getExistingDirectory(
            self.parent,
            "フォルダを開く",
            "",
            QFileDialog.ShowDirsOnly
        )
        
        if folder_path:
            self.open_callback(folder_path)
    
    def _on_show_sr_settings(self):
        """「超解像設定」アクション"""
        # 親ウィジェットの超解像設定ダイアログ表示メソッドを呼び出す
        if hasattr(self.parent, 'show_sr_settings_dialog'):
            self.parent.show_sr_settings_dialog()
    
    def update_from_cache(self, entry_cache: Dict[str, Any]):
        """
        エントリキャッシュからすべてのフォルダを探索してメニューを更新
        
        Args:
            entry_cache: エントリキャッシュ辞書
        """
        # FolderMenuBuilderを使用してフォルダメニューを構築
        FolderMenuBuilder.build_root_menu(
            parent_menu=self.folders_menu,
            action_callback=self._navigate_to,
            entry_cache=entry_cache
        )
        
        # メニューを有効化
        self.folders_menu.setEnabled(entry_cache is not None and len(entry_cache) > 0)
    
    def _navigate_to(self, path: str):
        """
        指定したパスに移動
        
        Args:
            path: 移動先のパス
        """
        if self.navigate_callback:
            self.navigate_callback(path)


class FileItemContextMenu:
    """ファイルリスト内のアイテム用コンテキストメニュー"""
    
    def __init__(self, parent: QWidget, is_dir: bool,
                 open_callback: Optional[Callable] = None,
                 extract_callback: Optional[Callable] = None):
        """
        ファイルアイテムコンテキストメニュー初期化
        
        Args:
            parent: 親ウィジェット
            is_dir: ディレクトリ（フォルダ/書庫）かどうか
            open_callback: 開く際に呼び出すコールバック
            extract_callback: 抽出時に呼び出すコールバック
        """
        self.parent = parent
        self.is_dir = is_dir
        self.open_callback = open_callback
        self.extract_callback = extract_callback
        
        # メニュー作成
        self.menu = QMenu(parent)
        
        # ディレクトリ用メニューアイテム
        if is_dir:
            self.open_action = QAction("開く", parent)
            self.open_action.triggered.connect(self._on_open)
            self.menu.addAction(self.open_action)
        
        # ファイル用メニューアイテム
        else:
            if extract_callback:
                self.extract_action = QAction("抽出...", parent)
                self.extract_action.triggered.connect(self._on_extract)
                self.menu.addAction(self.extract_action)
    
    def show(self, position):
        """
        指定された位置にコンテキストメニューを表示
        
        Args:
            position: 表示位置
        """
        self.menu.exec_(position)
    
    def _on_open(self):
        """「開く」アクション"""
        if self.open_callback:
            self.open_callback()
    
    def _on_extract(self):
        """「抽出」アクション"""
        if self.extract_callback:
            self.extract_callback()
