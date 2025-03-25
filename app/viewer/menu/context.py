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

# 自然順ソートユーティリティをインポート
from ..utils.sort import get_sorted_keys


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
        
        # ルートフォルダアクション - 空文字列ではなく "/" を渡す
        self.root_action = QAction("/ (ルート)", parent)
        self.root_action.triggered.connect(lambda: self._navigate_to("/"))
        self.folders_menu.addAction(self.root_action)
        
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
        
        # フォルダツリー構造を保持する辞書
        self.folder_tree = {}
    
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
        # フォルダツリーの構築
        self.folder_tree = {}
        
        # エントリキャッシュが空の場合は何もしない
        if not entry_cache:
            self.folders_menu.setEnabled(False)
            return
            
        # メニューを有効化
        self.folders_menu.setEnabled(True)
        
        # ルートフォルダ以外のアクションを全て削除
        actions = self.folders_menu.actions()
        for action in actions[1:]:  # ルートアクションは維持
            self.folders_menu.removeAction(action)
            
        # セパレータを追加
        self.folders_menu.addSeparator()
        
        # エントリキャッシュからすべてのディレクトリパスを抽出
        dir_paths = set()
        
        # キー（パス）のみ使用してフォルダツリーを構築
        for path in entry_cache.keys():
            # 空のパスはルートなのでスキップ
            if not path:
                continue
                
            # このパス自体がフォルダかどうかを確認
            entry_info = entry_cache.get(path)
            is_dir = entry_info and hasattr(entry_info, 'type') and entry_info.type and entry_info.type.is_dir()
            
            # ディレクトリの場合はパスを追加
            if is_dir:
                dir_paths.add(path)
            
            # 親ディレクトリもすべて追加
            parts = path.split('/')
            current_path = ""
            for i in range(len(parts) - 1):
                if parts[i]:
                    if current_path:
                        current_path += f"/{parts[i]}"
                    else:
                        current_path = parts[i]
                    dir_paths.add(current_path)
        
        # ツリー構造を構築
        for path in sorted(dir_paths):
            parts = path.split('/')
            current = self.folder_tree
            
            for part in parts:
                if not part:  # 空のパートはスキップ
                    continue
                    
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        # メニューを再帰的に構築
        self._build_folder_menu(self.folders_menu, self.folder_tree, "")

    def _build_folder_menu(self, parent_menu: QMenu, folder_dict: dict, parent_path: str):
        """
        フォルダメニューを再帰的に構築
        
        Args:
            parent_menu: 親メニュー
            folder_dict: フォルダ構造の辞書
            parent_path: 親フォルダのパス
        """
        # 辞書内のキーを大文字小文字を区別せずにソート - 共通モジュールを使用
        sorted_keys = get_sorted_keys(folder_dict.keys(), ignore_case=True)
        
        # 各フォルダについてメニューアイテムを作成
        for folder_name in sorted_keys:
            # フォルダのフルパスを構築
            if parent_path:
                folder_path = f"{parent_path}/{folder_name}"
            else:
                folder_path = folder_name
            
            # サブフォルダの辞書
            subfolders = folder_dict[folder_name]
            
            if subfolders:  # サブフォルダがある場合
                # サブメニューを作成
                submenu = QMenu(folder_name, parent_menu)
                
                # このフォルダ自体に移動するアクション
                self_action = QAction("このフォルダを開く", parent_menu)
                self_action.triggered.connect(lambda checked=False, path=folder_path: self._navigate_to(path))
                submenu.addAction(self_action)
                
                # 区切り線
                submenu.addSeparator()
                
                # サブフォルダのメニューを再帰的に構築
                self._build_folder_menu(submenu, subfolders, folder_path)
                
                # 親メニューにサブメニューを追加
                parent_menu.addMenu(submenu)
            else:  # サブフォルダがない場合
                # 通常のアクションを作成
                action = QAction(folder_name, parent_menu)
                action.triggered.connect(lambda checked=False, path=folder_path: self._navigate_to(path))
                parent_menu.addAction(action)
    
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
