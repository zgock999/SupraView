"""
ArchiveBrowserクラス - 書庫内ファイルエントリのブラウジング機能
"""

import os
from typing import List, Optional, Dict
import re
from arc.manager.enhanced import EnhancedArchiveManager
from arc.arc import EntryInfo, EntryType

class ArchiveBrowser:
    """
    ブラウジングモジュール
    フォルダ/書庫内のディレクトリを横断してファイルエントリを返す
    """
    
    def __init__(self, manager: EnhancedArchiveManager, path: str = "", exts: List[str] = None):
        """
        初期化関数
        
        Args:
            manager: 拡張アーカイブマネージャー（必須）
            path: 初期パス（省略可）
            exts: 対象とする拡張子リスト（省略可）
        """
        if exts is None:
            exts = []
            
        self._manager = manager
        self._entries = []
        self._current_idx = 0
        self._folder_indices = {}  # フォルダごとの開始インデックスを記録
        
        # エントリを収集
        self._collect_entries(exts)
        
        # 初期位置を設定
        if path and self._entries:
            try:
                self.jump(path)
            except FileNotFoundError:
                # jumpメソッドが前方一致をサポートするようになったため、フォールバック処理は不要
                pass
        elif self._entries:  # パスが指定されていない場合はgo_firstを呼び出す
            self.go_first()
        
    def _collect_entries(self, exts: List[str]):
        """
        マネージャーからエントリを収集
        EnhancedArchiveManagerのエントリキャッシュを活用
        
        Args:
            exts: 対象とする拡張子リスト
        """
        # エントリキャッシュから直接取得
        entry_cache = self._manager.get_entry_cache()
        
        # エントリキャッシュから条件に合うファイルエントリを抽出（アーカイブは対象外）
        for path, entry in entry_cache.items():
            # ファイルエントリの場合のみ処理
            if entry.type == EntryType.FILE:
                # 拡張子条件を満たすものだけを抽出
                if not exts or os.path.splitext(path)[1].lower()[1:] in exts:
                    self._entries.append(path)
        
        # 自然順ソート (数字を考慮したソート)
        self._entries = self._natural_sort(self._entries)
        
        # フォルダごとのインデックスを記録
        current_folder = None
        for i, entry in enumerate(self._entries):
            folder = os.path.dirname(entry)
            if folder != current_folder:
                current_folder = folder
                self._folder_indices[folder] = i
    
    def _natural_sort(self, entries: List[str]) -> List[str]:
        """
        自然順ソート (2020/2/8が2020/10/10より前に来るようにする)
        
        Args:
            entries: ソート対象のエントリリスト
            
        Returns:
            ソート済みエントリリスト
        """
        def convert(text):
            return int(text) if text.isdigit() else text.lower()
            
        def alphanum_key(key):
            return [convert(c) for c in re.split('([0-9]+)', key)]
            
        return sorted(entries, key=alphanum_key)
    
    def _get_current_folder(self) -> str:
        """
        現在のフォルダを取得
        
        Returns:
            現在のフォルダパス
        """
        return os.path.dirname(self._entries[self._current_idx])
    
    def next(self) -> str:
        """
        次のエントリに移動。末尾だったら先頭へ
        
        Returns:
            移動後のエントリパス
        """
        self._current_idx = (self._current_idx + 1) % len(self._entries)
        return self._entries[self._current_idx]
    
    def prev(self) -> str:
        """
        前のエントリに移動。先頭だったら末尾へ
        
        Returns:
            移動後のエントリパス
        """
        self._current_idx = (self._current_idx - 1) % len(self._entries)
        return self._entries[self._current_idx]
    
    def next_folder(self) -> str:
        """
        次のフォルダの先頭へ移動
        
        Returns:
            移動後のエントリパス
        """
        current_folder = self._get_current_folder()
        for i in range(self._current_idx + 1, len(self._entries)):
            folder = os.path.dirname(self._entries[i])
            if folder != current_folder:
                self._current_idx = i
                return self._entries[self._current_idx]
                
        # 最後まで行ったら先頭フォルダの先頭へ
        self._current_idx = 0
        return self._entries[self._current_idx]
    
    def prev_folder(self) -> str:
        """
        前のフォルダの末尾へ移動
        
        Returns:
            移動後のエントリパス
        """
        current_folder = self._get_current_folder()
        prev_folder_end = -1
        
        # 前のフォルダの最後のエントリを探す
        for i in range(self._current_idx - 1, -1, -1):
            folder = os.path.dirname(self._entries[i])
            if folder != current_folder:
                next_folder = folder
                while i >= 0 and os.path.dirname(self._entries[i]) == next_folder:
                    prev_folder_end = i
                    i -= 1
                break
        
        # 見つからなかったら最後のフォルダの末尾へ
        if prev_folder_end == -1:
            last_folder = os.path.dirname(self._entries[-1])
            for i in range(len(self._entries) - 1, -1, -1):
                if os.path.dirname(self._entries[i]) == last_folder:
                    prev_folder_end = i
                    break
                    
        self._current_idx = prev_folder_end
        return self._entries[self._current_idx]
    
    def go_top(self) -> str:
        """
        フォルダ内の先頭へ移動
        
        Returns:
            移動後のエントリパス
        """
        current_folder = self._get_current_folder()
        for i in range(len(self._entries)):
            if os.path.dirname(self._entries[i]) == current_folder:
                self._current_idx = i
                return self._entries[self._current_idx]
                
        return self._entries[self._current_idx]
    
    def go_end(self) -> str:
        """
        フォルダ内の末尾へ移動
        
        Returns:
            移動後のエントリパス
        """
        current_folder = self._get_current_folder()
        for i in range(len(self._entries) - 1, -1, -1):
            if os.path.dirname(self._entries[i]) == current_folder:
                self._current_idx = i
                return self._entries[self._current_idx]
                
        return self._entries[self._current_idx]
    
    def go_first(self) -> str:
        """
        リストの先頭へ移動
        
        Returns:
            移動後のエントリパス
        """
        self._current_idx = 0
        return self._entries[self._current_idx]
    
    def go_last(self) -> str:
        """
        リストの末尾へ移動
        
        Returns:
            移動後のエントリパス
        """
        self._current_idx = len(self._entries) - 1
        return self._entries[self._current_idx]
    
    def jump(self, path: str) -> str:
        """
        与えられたパスに移動。無効なパスは例外
        
        Args:
            path: 移動先のパス
            
        Returns:
            移動後のエントリパス
            
        Raises:
            FileNotFoundError: 指定されたパスが見つからない場合
        """
        if not self._entries:
            raise FileNotFoundError(f"パス '{path}' が見つかりません")
        
        # パスから末尾の/を削除
        clean_path = path.rstrip('/')
        
        # 1. 完全一致を検索
        for i, entry in enumerate(self._entries):
            if entry == path or entry == clean_path:
                self._current_idx = i
                return self._entries[self._current_idx]
        
        # 2. 前方一致を検索 - フォルダパスの場合のみ
        # clean_path + '/' のような形で厳密にフォルダパスの前方一致を確認
        prefix = clean_path + '/'
        
        for i, entry in enumerate(self._entries):
            if entry.startswith(prefix):
                # 前方一致が見つかった場合は、続く文字が/かどうかを確認する必要はない
                # (prefix自体が/で終わっているため)
                self._current_idx = i
                return self._entries[self._current_idx]
        
        # clean_pathで始まるがprefixで始まらないエントリが存在するか確認
        # これは不完全な一致を意味する (例: "folder/fil"が"folder/file1"と不完全一致)
        for entry in self._entries:
            if entry.startswith(clean_path) and not entry.startswith(prefix) and not entry == clean_path:
                # 不完全一致がある場合は、パスが不完全と判断
                raise FileNotFoundError(f"パス '{path}' は不完全です。フォルダパスには末尾に/を付けてください")
        
        # 見つからなかった場合
        raise FileNotFoundError(f"パス '{path}' が見つかりません")
    
    def get_current(self) -> List[str]:
        """
        現在のカレント位置を返す
        
        Returns:
            現在のパスをリストとして返す（将来の拡張のため）
        """
        return [self._entries[self._current_idx]]
