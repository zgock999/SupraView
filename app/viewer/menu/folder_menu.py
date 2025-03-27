"""
フォルダメニュー

アプリケーション内で共通して使用するフォルダ階層メニューの実装
"""

import os
import sys
from typing import Callable, Dict, Any, List, Union, Optional

from PySide6.QtWidgets import QMenu, QFileDialog, QWidget, QApplication
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

# 自然順ソートユーティリティをインポート
from ..utils.sort import get_sorted_keys


class FolderMenuBuilder:
    """複数のビューで共有できるフォルダ階層メニューのビルダークラス"""
    
    @staticmethod
    def build_root_menu(parent_menu: QMenu, 
                        action_callback: Callable[[str], None],
                        entry_cache: Optional[Dict[str, Any]] = None) -> None:
        """
        ルートメニューを構築する
        
        Args:
            parent_menu: 親となるメニューオブジェクト
            action_callback: メニューアイテム選択時に呼び出されるコールバック関数
            entry_cache: エントリキャッシュ辞書（省略可能）
        """
        # 親メニューの全アクションをクリア
        parent_menu.clear()
        
        # ルートフォルダアクション
        root_action = QAction("/ (ルート)", parent_menu)
        root_action.triggered.connect(lambda: action_callback(""))
        parent_menu.addAction(root_action)
        
        # エントリキャッシュが提供されていない場合はルートアクションのみ追加して終了
        if not entry_cache:
            parent_menu.setEnabled(False)
            return
            
        # メニューを有効化
        parent_menu.setEnabled(True)
        
        # セパレータを追加
        parent_menu.addSeparator()
        
        # フォルダツリーを構築
        folder_tree = FolderMenuBuilder._build_folder_tree(entry_cache)
        
        # フォルダツリーが空でなければ、メニューを再帰的に構築
        if folder_tree:
            FolderMenuBuilder._build_folder_menu(parent_menu, folder_tree, "", action_callback)
    
    @staticmethod
    def _build_folder_tree(entry_cache: Dict[str, Any]) -> Dict[str, Any]:
        """
        エントリキャッシュからフォルダツリー構造を構築
        
        Args:
            entry_cache: エントリキャッシュ辞書
            
        Returns:
            フォルダ構造の辞書
        """
        folder_tree = {}
        
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
            current = folder_tree
            
            for part in parts:
                if not part:  # 空のパートはスキップ
                    continue
                    
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        return folder_tree
    
    @staticmethod
    def _build_folder_menu(parent_menu: QMenu, folder_dict: dict, parent_path: str, 
                          action_callback: Callable[[str], None]) -> None:
        """
        フォルダメニューを再帰的に構築
        
        Args:
            parent_menu: 親メニュー
            folder_dict: フォルダ構造の辞書
            parent_path: 親フォルダのパス
            action_callback: メニューアイテム選択時に呼び出されるコールバック関数
        """
        # 辞書内のキーを大文字小文字を区別せずにソート
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
                self_action.triggered.connect(lambda checked=False, path=folder_path: action_callback(path))
                submenu.addAction(self_action)
                
                # 区切り線
                submenu.addSeparator()
                
                # サブフォルダのメニューを再帰的に構築
                FolderMenuBuilder._build_folder_menu(submenu, subfolders, folder_path, action_callback)
                
                # 親メニューにサブメニューを追加
                parent_menu.addMenu(submenu)
            else:  # サブフォルダがない場合
                # 通常のアクションを作成
                action = QAction(folder_name, parent_menu)
                action.triggered.connect(lambda checked=False, path=folder_path: action_callback(path))
                parent_menu.addAction(action)
    
    @staticmethod
    def add_path_navigation_menu(parent_menu: QMenu, current_path: str, action_callback: Callable[[str], None]) -> None:
        """
        現在のパスに基づくナビゲーションメニューを追加
        
        Args:
            parent_menu: 親となるメニューオブジェクト
            current_path: 現在のパス
            action_callback: メニューアイテム選択時に呼び出されるコールバック関数
        """
        # 現在のディレクトリが設定されていない場合は何もしない
        if not current_path:
            return
        
        # メニューをクリア
        parent_menu.clear()
        
        # 親ディレクトリを追加（現在のパスから抽出）
        parent_path = ""
        if "/" in current_path:
            parent_path = current_path.rsplit("/", 1)[0]
        
        # 親ディレクトリのアクションを追加（存在する場合）
        if parent_path:
            parent_name = parent_path.split("/")[-1] if "/" in parent_path else parent_path
            parent_action = QAction(f"上の階層 ({parent_name})", parent_menu)
            parent_action.triggered.connect(lambda: action_callback(parent_path))
            parent_menu.addAction(parent_action)
                
        # 現在のディレクトリ
        dir_name = current_path.split("/")[-1] if "/" in current_path else current_path
        current_dir_action = QAction(f"現在のディレクトリ ({dir_name})", parent_menu)
        current_dir_action.triggered.connect(lambda: action_callback(current_path))
        current_dir_action.setEnabled(False)  # 現在のディレクトリは選択できないように
        parent_menu.addAction(current_dir_action)
        
        # ルートディレクトリへのアクションを追加
        parent_menu.addSeparator()
        root_action = QAction("ルートディレクトリ", parent_menu)
        root_action.triggered.connect(lambda: action_callback(""))
        parent_menu.addAction(root_action)
