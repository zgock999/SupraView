"""
ファイルリスト用データモデル

ファイルとフォルダの情報をQtのモデルとして管理するためのクラス
"""

import os
import sys
import re
from typing import List, Dict, Any

try:
    from PySide6.QtCore import Qt, QFileInfo
    from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
    from PySide6.QtWidgets import QFileIconProvider, QStyle, QApplication
except ImportError as e:
    print(f"エラー: 必要なライブラリの読み込みに失敗しました: {e}")
    sys.exit(1)


class FileListModel(QStandardItemModel):
    """ファイルとフォルダを表示するためのモデル"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_provider = QFileIconProvider()
        # カスタムアーカイブアイコン（FileDialogContentsViewを使用）
        self.archive_icon = None
        try:
            # アーカイブ用の特別なアイコンを取得
            self.archive_icon = QApplication.style().standardIcon(QStyle.SP_FileDialogContentsView)
        except:
            # 失敗した場合はデフォルトのフォルダアイコンを使用
            pass
        
        # 親ディレクトリへのナビゲーションアイコン
        self.updir_icon = None
        try:
            self.updir_icon = QApplication.style().standardIcon(QStyle.SP_FileDialogToParent)
        except:
            # 失敗した場合はデフォルトのフォルダアイコンを使用
            pass
        
    def set_items(self, items: List[Dict[str, Any]], in_root: bool = False):
        """
        アイテムのリストをモデルにセットする
        
        Args:
            items: アイテム情報の辞書のリスト。各辞書には少なくとも name, is_dir キーが必要
            in_root: ルートディレクトリにいるかどうか（親ディレクトリ項目の表示制御用）
        """
        self.clear()
        
        # ルートディレクトリではない場合、親ディレクトリへの項目を追加
        if not in_root:
            parent_item = QStandardItem(self.updir_icon or self.icon_provider.icon(QFileIconProvider.Folder), "..")
            parent_item.setData(True, Qt.UserRole + 1)  # フォルダとして扱う
            parent_item.setData(0, Qt.UserRole + 2)     # サイズ（0）
            parent_item.setData("", Qt.UserRole + 3)    # 更新日（空）
            parent_item.setData("..", Qt.UserRole + 4)  # パスを「..」に設定
            parent_item.setData("DIRECTORY", Qt.UserRole + 5)  # エントリタイプ
            parent_item.setData("", Qt.UserRole + 6)   # 自然順ソート用キー（最上位に表示）
            
            parent_item.setToolTip("親ディレクトリに移動")
            self.appendRow(parent_item)
        
        # アイテムをタイプごとに分類
        directories = []
        archives = []
        files = []
        
        # 通常のアイテムを追加
        for item in items:
            name = item.get('name', '')
            is_dir = item.get('is_dir', False)
            size = item.get('size', 0)
            modified = item.get('modified', '')
            path = item.get('path', name)  # パス情報を取得、ない場合は名前を使用
            item_type = item.get('type', '')  # アイテムの種類（DIRECTORY, ARCHIVE, FILEなど）
            
            # アイコン取得
            if is_dir:
                # アーカイブファイルかどうかを判定
                is_archive = item_type == 'ARCHIVE'
                
                if is_archive and self.archive_icon:
                    # アーカイブ用特別アイコン
                    icon = self.archive_icon
                else:
                    # 通常のフォルダアイコン
                    icon = self.icon_provider.icon(QFileIconProvider.Folder)
            else:
                # ファイル拡張子に合わせたアイコンを取得
                file_info = QFileInfo(name)
                icon = self.icon_provider.icon(file_info)
            
            # アイテムを作成
            item_obj = QStandardItem(icon, name)
            item_obj.setData(is_dir, Qt.UserRole + 1)  # フォルダかどうか
            item_obj.setData(size, Qt.UserRole + 2)    # サイズ
            item_obj.setData(modified, Qt.UserRole + 3)  # 更新日
            item_obj.setData(path, Qt.UserRole + 4)    # 完全なパス
            item_obj.setData(item_type, Qt.UserRole + 5)  # エントリタイプ
            
            # 自然順ソート用のキー（アイテム名を数値と文字列に分解）
            sort_key = self._natural_sort_key(name)
            item_obj.setData(sort_key, Qt.UserRole + 6)
            
            # ツールチップにタイプ情報を追加
            type_str = "アーカイブ" if item_type == 'ARCHIVE' else "フォルダ" if is_dir else "ファイル"
            
            item_obj.setToolTip(f"名前: {name}\n"
                             f"種類: {type_str}\n"
                             f"サイズ: {self._format_size(size) if size else '不明'}\n"
                             f"更新日: {modified if modified else '不明'}")
            
            # タイプ別に分類
            if item_type == 'ARCHIVE':
                archives.append(item_obj)
            elif is_dir:
                directories.append(item_obj)
            else:
                files.append(item_obj)
        
        # 各カテゴリごとに自然順ソートして追加
        # カスタム比較関数を使用して型の不一致を処理
        sorted_dirs = sorted(directories, key=lambda x: self._get_natural_sort_key(x.data(Qt.UserRole + 6)))
        sorted_archives = sorted(archives, key=lambda x: self._get_natural_sort_key(x.data(Qt.UserRole + 6)))
        sorted_files = sorted(files, key=lambda x: self._get_natural_sort_key(x.data(Qt.UserRole + 6)))
        
        # アイテムを順番に追加（フォルダ → アーカイブ → ファイル）
        for item_obj in sorted_dirs + sorted_archives + sorted_files:
            self.appendRow(item_obj)
    
    def _format_size(self, size: int) -> str:
        """ファイルサイズを人間が読みやすい形式にフォーマット"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"
    
    def _natural_sort_key(self, text: str) -> List[Any]:
        """
        自然順ソート用のキーを生成（数値部分を数値として扱う）
        
        Args:
            text: ソートする文字列
            
        Returns:
            数値と文字列のリスト（数値は数値型）
        """
        # テキストがNoneまたは数値の場合の対応
        if text is None:
            return [""]
        
        # 文字列に変換して処理（数値など文字列以外の場合に対応）
        text_str = str(text)
        
        # 数値と非数値に分割する正規表現パターン
        pattern = r'(\d+)|(\D+)'
        
        # 結果リスト
        parts = []
        
        # 見つかったすべての部分を処理
        for digit, non_digit in re.findall(pattern, text_str):
            if digit:
                # 数値部分は数値型として追加
                parts.append(int(digit))
            else:
                # 非数値部分は小文字に変換して追加（大文字小文字を区別しないため）
                parts.append(non_digit.lower())
        
        # 空の場合は空文字を入れておく
        if not parts:
            parts.append("")
        
        return parts

    def _get_natural_sort_key(self, sort_key):
        """
        ソートに使用する安全なキーを取得する
        型の不一致によるエラーを防ぐための特別なキーを生成
        
        Args:
            sort_key: アイテムのソートキーデータ
            
        Returns:
            比較可能なソートキー
        """
        # NoneやUndefinedの場合は空リストを返す
        if sort_key is None:
            return []
            
        # すでにリストの場合
        if isinstance(sort_key, list):
            # リスト内の要素を安全に比較できる形式に変換
            result = []
            for item in sort_key:
                if isinstance(item, int):
                    # 整数部分は文字列表現の前に0を詰めて桁数を揃える（最大20桁）
                    result.append(f"{item:020d}")
                elif isinstance(item, str):
                    # 文字列はそのまま（ただし小文字に統一）
                    result.append(item.lower())
                else:
                    # その他の型は文字列に変換
                    result.append(str(item))
            return result
            
        # リストでない場合は単一の値として処理
        if isinstance(sort_key, int):
            return [f"{sort_key:020d}"]
        elif isinstance(sort_key, str):
            return [sort_key.lower()]
        else:
            return [str(sort_key)]
