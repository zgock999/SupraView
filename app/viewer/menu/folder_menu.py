"""
フォルダメニュー

アプリケーション内で共通して使用するフォルダ階層メニューの実装
"""

import os
import sys
import uuid
from typing import Callable, Dict, Any, List, Union, Optional, Set

from PySide6.QtWidgets import QMenu, QFileDialog, QWidget, QApplication, QStyleOptionMenuItem, QStyle
from PySide6.QtGui import QAction, QPainter, QColor, QPen, QBrush
from PySide6.QtCore import Qt, QRect, QPoint

# 自然順ソートユーティリティをインポート
from ..utils.sort import get_sorted_keys


class HighlightableMenu(QMenu):
    """ハイライト機能を持つカスタムメニュークラス"""
    
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.highlighted_items = {}  # {action: color}
        
    def highlight_action(self, action, color):
        """アクションをハイライト"""
        self.highlighted_items[action] = color
        
    def clear_highlights(self):
        """全ハイライトをクリア"""
        self.highlighted_items.clear()
        
    def paintEvent(self, event):
        """メニューの描画をカスタマイズ"""
        painter = QPainter(self)
        
        # 標準のメニュー描画
        super().paintEvent(event)
        
        # ハイライト対象の項目を描画
        for action, color in self.highlighted_items.items():
            if action in self.actions() and action.isVisible():
                # アクションの矩形領域を取得
                rect = self.actionGeometry(action)
                
                # 半透明色でハイライト背景を描画
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setPen(Qt.NoPen)
                
                # ハイライトの色を設定
                if isinstance(color, str):
                    color = QColor(color)
                
                brush = QBrush(QColor(color.red(), color.green(), color.blue(), 120))
                painter.setBrush(brush)
                painter.drawRect(rect)
                
                # 枠線を描画
                painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 200), 1))
                painter.drawRect(rect.adjusted(0, 0, -1, -1))
                
                painter.restore()
        
        painter.end()


class FolderMenuBuilder:
    """複数のビューで共有できるフォルダ階層メニューのビルダークラス"""
    
    # クリアする必要のあるメニューを追跡するグローバル辞書
    _highlight_menus = set()
    
    @staticmethod
    def build_root_menu(parent_menu: QMenu, 
                        action_callback: Callable[[str], None],
                        entry_cache: Optional[Dict[str, Any]] = None) -> QMenu:
        """
        ルートメニューを構築する
        
        Args:
            parent_menu: 親となるメニューオブジェクト
            action_callback: メニューアイテム選択時に呼び出されるコールバック関数
            entry_cache: エントリキャッシュ辞書（省略可能）
            
        Returns:
            QMenu: 構築されたメニューオブジェクト（親メニューまたは新しいHighlightableMenu）
        """
        # 親メニューを追跡対象に追加
        FolderMenuBuilder._highlight_menus.add(parent_menu)
        
        # 既存のメニューがHighlightableMenuでない場合は作り直す
        if not isinstance(parent_menu, HighlightableMenu):
            # 元のメニューのプロパティを保持
            title = parent_menu.title()
            parent = parent_menu.parent()
            
            # 新しいHighlightableMenuを作成
            new_menu = HighlightableMenu(title, parent)
        else:
            new_menu = parent_menu
        
        # 以降は新しいメニューで処理を続ける
        
        # 親メニューの全アクションをクリア
        new_menu.clear()
        
        # メニューのハイライトをクリア
        if isinstance(new_menu, HighlightableMenu):
            new_menu.clear_highlights()
        
        # ルートフォルダアクション
        root_action = QAction("/ (ルート)", new_menu)
        root_action.triggered.connect(lambda: action_callback(""))
        new_menu.addAction(root_action)
        
        # エントリキャッシュが提供されていない場合はルートアクションのみ追加して終了
        if not entry_cache:
            new_menu.setEnabled(False)
            return new_menu
            
        # メニューを有効化
        new_menu.setEnabled(True)
        
        # セパレータを追加
        new_menu.addSeparator()
        
        # フォルダツリーを構築
        folder_tree = FolderMenuBuilder._build_folder_tree(entry_cache)
        
        # フォルダツリーが空でなければ、メニューを再帰的に構築
        if folder_tree:
            FolderMenuBuilder._build_folder_menu(new_menu, folder_tree, "", action_callback)
        
        return new_menu
    
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
                # サブメニューを作成 (HighlightableMenuを使用)
                submenu = HighlightableMenu(folder_name, parent_menu)
                FolderMenuBuilder._highlight_menus.add(submenu)
                
                # このフォルダ自体に移動するアクション
                self_action = QAction("このフォルダを開く", submenu)
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
            parent_action.setObjectName(f"menuaction_{uuid.uuid4().hex}")
            parent_menu.addAction(parent_action)
                
        # 現在のディレクトリ
        dir_name = current_path.split("/")[-1] if "/" in current_path else current_path
        current_dir_action = QAction(f"現在のディレクトリ ({dir_name})", parent_menu)
        current_dir_action.triggered.connect(lambda: action_callback(current_path))
        current_dir_action.setEnabled(False)  # 現在のディレクトリは選択できないように
        current_dir_action.setObjectName(f"menuaction_{uuid.uuid4().hex}")
        parent_menu.addAction(current_dir_action)
        
        # ルートディレクトリへのアクションを追加
        parent_menu.addSeparator()
        root_action = QAction("ルートディレクトリ", parent_menu)
        root_action.triggered.connect(lambda: action_callback(""))
        root_action.setObjectName(f"menuaction_{uuid.uuid4().hex}")
        parent_menu.addAction(root_action)
    
    @staticmethod
    def _reset_menu_highlights_recursive(menu: QMenu) -> None:
        """
        指定されたメニューとそのすべてのサブメニューのハイライトを再帰的にリセットする
        
        Args:
            menu: リセット対象のメニュー
        """
        # このメニューがHighlightableMenuであればハイライトをクリア
        if isinstance(menu, HighlightableMenu):
            menu.clear_highlights()
            
        # メニュー内のすべてのアクションのフォント設定をリセットし、サブメニューも再帰処理
        for action in menu.actions():
            # セパレータはスキップ
            if action.isSeparator():
                continue
                
            # フォントの太字設定をリセット
            font = action.font()
            font.setBold(False)
            action.setFont(font)
            
            # サブメニューがあれば再帰的に処理
            if action.menu():
                submenu = action.menu()
                FolderMenuBuilder._reset_menu_highlights_recursive(submenu)

    @staticmethod
    def _reset_all_menu_highlights() -> None:
        """すべてのメニューのハイライトをリセット"""
        # 追跡中のすべてのメニューを再帰的に処理
        for menu in list(FolderMenuBuilder._highlight_menus):
            if menu:
                FolderMenuBuilder._reset_menu_highlights_recursive(menu)
    
    @staticmethod
    def highlight_menu(menu: QMenu, path: str) -> bool:
        """
        指定されたパスに対応するメニュー項目を強調表示する
        
        Args:
            menu: ルートメニューオブジェクト（build_root_menu()で構築したもの）
            path: 強調表示するパス（例: 'aaa/bbb/ccc'）
            
        Returns:
            bool: 該当する項目が見つかり、強調表示されたかどうか
        """
        # すべてのメニューのハイライトをリセット（必ず実行）
        FolderMenuBuilder._reset_all_menu_highlights()
        
        # 空のパスは処理しない
        if not path:
            return False
        
        # メニューがHighlightableMenuでない場合は警告を表示
        if not isinstance(menu, HighlightableMenu):
            print("警告: メニューがHighlightableMenuではありません。ハイライト機能は動作しません。")
            return False
        
        # パスを要素に分割
        path_parts = [part for part in path.split('/') if part]
        if not path_parts:
            return False
            
        return FolderMenuBuilder._recursive_hilight_menu(menu, path_parts, 0, path)
    
    @staticmethod
    def _recursive_hilight_menu(menu: QMenu, path_parts: List[str], level: int, full_path: str) -> bool:
        """
        メニューを再帰的にトラバースして指定されたパスに対応する項目を強調表示する
        
        Args:
            menu: 現在のメニューオブジェクト
            path_parts: パスの各部分のリスト
            level: 現在の深さレベル
            full_path: 完全なパス（デバッグ用）
            
        Returns:
            bool: 該当する項目が見つかり、強調表示されたかどうか
        """
        if level >= len(path_parts):
            return False
            
        current_part = path_parts[level]
        last_level = level == len(path_parts) - 1
        
        # このレベルのすべてのアクションをチェック
        for action in menu.actions():
            # セパレータはスキップ
            if action.isSeparator():
                continue
                
            # アクションがメニューを持っている場合（サブメニュー）
            if action.menu():
                # テキストがマッチするか確認（「このフォルダを開く」などの特殊アクションを除く）
                submenu = action.menu()
                if action.text() == current_part:
                    # メニューがHighlightableMenuの場合、ハイライト
                    if isinstance(menu, HighlightableMenu):
                        menu.highlight_action(action, "#8096F3")  # 青のハイライト
                    
                    # フォント設定を太字に変更
                    font = action.font()
                    font.setBold(True)
                    action.setFont(font)
                    
                    # 最終レベルなら、「このフォルダを開く」アクションを探して強調表示
                    if last_level and isinstance(submenu, HighlightableMenu):
                        for sub_action in submenu.actions():
                            if sub_action.text() == "このフォルダを開く":
                                # ハイライト
                                submenu.highlight_action(sub_action, "#4CAF50")  # 緑のハイライト
                                
                                # フォントを太字に設定して強調表示
                                font = sub_action.font()
                                font.setBold(True)
                                sub_action.setFont(font)
                                return True
                    # 最終レベルでなければ、次のレベルを再帰的に処理
                    else:
                        if FolderMenuBuilder._recursive_hilight_menu(submenu, path_parts, level + 1, full_path):
                            return True
                
            # 通常のアクション（サブメニューなし）
            elif action.text() == current_part and last_level:
                # メニューがHighlightableMenuの場合、ハイライト
                if isinstance(menu, HighlightableMenu):
                    menu.highlight_action(action, "#4CAF50")  # 緑のハイライト
                
                # フォントを太字に設定して強調表示
                font = action.font()
                font.setBold(True)
                action.setFont(font)
                return True
                
        return False

    @staticmethod
    def reset_path_highlights(menu: QMenu, path: str) -> bool:
        """
        特定のパスに対応するメニュー項目のハイライトのみをリセットする
        （再帰的な全メニューのリセットよりも効率的）
        
        Args:
            menu: ルートメニューオブジェクト
            path: リセット対象のパス
            
        Returns:
            bool: リセットが成功したかどうか
        """
        # 空のパスは処理しない
        if not path:
            return False
        
        # メニューがHighlightableMenuでない場合は何もしない
        if not isinstance(menu, HighlightableMenu):
            return False
        
        # パスを要素に分割
        path_parts = [part for part in path.split('/') if part]
        if not path_parts:
            return False
        
        # パスに対応するメニュー項目のハイライトをリセット
        return FolderMenuBuilder._reset_path_highlights_recursive(menu, path_parts, 0)
    
    @staticmethod
    def _reset_path_highlights_recursive(menu: QMenu, path_parts: List[str], level: int) -> bool:
        """
        特定のパスに対応するメニュー項目のハイライトを再帰的にリセットする
        
        Args:
            menu: 現在のメニューオブジェクト
            path_parts: パスの各部分のリスト
            level: 現在の深さレベル
            
        Returns:
            bool: ハイライトのリセットに成功したかどうか
        """
        if level >= len(path_parts):
            return False
        
        current_part = path_parts[level]
        last_level = level == len(path_parts) - 1
        
        # このレベルのすべてのアクションをチェック
        for action in menu.actions():
            # セパレータはスキップ
            if action.isSeparator():
                continue
            
            # アクションがメニューを持っている場合（サブメニュー）
            if action.menu():
                submenu = action.menu()
                if action.text() == current_part:
                    # このアクションのハイライトとフォントをリセット
                    if isinstance(menu, HighlightableMenu) and action in menu.highlighted_items:
                        del menu.highlighted_items[action]
                    
                    # フォント設定を元に戻す
                    font = action.font()
                    font.setBold(False)
                    action.setFont(font)
                    
                    # 最終レベルの場合、「このフォルダを開く」アクションもリセット
                    if last_level and isinstance(submenu, HighlightableMenu):
                        for sub_action in submenu.actions():
                            if sub_action.text() == "このフォルダを開く":
                                if sub_action in submenu.highlighted_items:
                                    del submenu.highlighted_items[sub_action]
                                
                                # フォント設定を元に戻す
                                sub_font = sub_action.font()
                                sub_font.setBold(False)
                                sub_action.setFont(sub_font)
                                return True
                    
                    # 最終レベルでなければ、次のレベルを再帰的に処理
                    else:
                        if FolderMenuBuilder._reset_path_highlights_recursive(submenu, path_parts, level + 1):
                            return True
            
            # 通常のアクション（サブメニューなし）
            elif action.text() == current_part and last_level:
                # このアクションのハイライトとフォントをリセット
                if isinstance(menu, HighlightableMenu) and action in menu.highlighted_items:
                    del menu.highlighted_items[action]
                
                # フォント設定を元に戻す
                font = action.font()
                font.setBold(False)
                action.setFont(font)
                return True
        
        return False
