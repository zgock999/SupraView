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
    
    def __init__(self, manager: EnhancedArchiveManager, path: str = "", exts: List[str] = None, pages: int = 1, shift: bool = False):
        """
        初期化関数
        
        Args:
            manager: 拡張アーカイブマネージャー（必須）
            path: 初期パス（省略可）
            exts: 対象とする拡張子リスト（省略可）
            pages: ページ数（1または2のみ有効、デフォルトは1）
            shift: シフトフラグ（デフォルトはFalse）
        """
        if exts is None:
            exts = []
            
        # pagesの値を検証（1または2のみ有効）
        if pages not in [1, 2]:
            pages = 1  # 不正値の場合はデフォルト値に設定
            
        self._manager = manager
        self._entries = []
        self._current_idx = 0
        self._folder_indices = {}  # フォルダごとの開始インデックスを記録
        self._pages = pages  # ページ数を設定
        self._shift = shift  # シフトフラグを設定
        
        # デバッグ情報追加
        print(f"exts: {exts}")
        cache = manager.get_entry_cache()
        print(f"cache length: {len(cache)}")
        
        # エントリを収集
        self._collect_entries(exts)
        print(f"self._entries length: {len(self._entries)}")

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
        
        # 拡張子リストを正規化: 全て小文字で、ドットありに統一
        normalized_exts = []
        for ext in exts:
            if ext:
                if not ext.startswith('.'):
                    normalized_ext = '.' + ext.lower()
                else:
                    normalized_ext = ext.lower()
                normalized_exts.append(normalized_ext)
        
        print(f"正規化された拡張子リスト: {normalized_exts}")
        
        # エントリキャッシュから条件に合うファイルエントリを抽出（アーカイブは対象外）
        for path, entry in entry_cache.items():
            # ファイルエントリの場合のみ処理
            if entry.type == EntryType.FILE:
                # 拡張子条件を満たすものだけを抽出
                if not normalized_exts:
                    # 拡張子リストが空または指定なしの場合は全ファイルを対象とする
                    self._entries.append(path)
                else:
                    # ファイル拡張子を取得して小文字化
                    _, ext = os.path.splitext(path.lower())
                    # 拡張子リストに含まれるかチェック - 大文字小文字を区別しない比較
                    if ext.lower() in normalized_exts:
                        self._entries.append(path)
        
        print(f"収集されたエントリ数: {len(self._entries)}")
        
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
        次のエントリに移動。pages分先に進む。
        フォルダをまたぐ場合は次のフォルダの先頭に移動する。
        
        Returns:
            移動後のエントリパス
        """
        if not self._entries:
            return ""
            
        current_folder = self._get_current_folder()
        target_idx = self._current_idx
        
        # pages分だけ移動を試みる
        for _ in range(self._pages):
            target_idx = (target_idx + 1) % len(self._entries)
            # フォルダをまたいだかチェック
            if os.path.dirname(self._entries[target_idx]) != current_folder:
                # 新しいフォルダの先頭に移動
                next_folder = os.path.dirname(self._entries[target_idx])
                # self._folder_indicesにフォルダ先頭のインデックスが記録されている場合はそれを使用
                if next_folder in self._folder_indices:
                    target_idx = self._folder_indices[next_folder]
                break
        
        self._current_idx = target_idx
        return self._entries[self._current_idx]
    
    def prev(self) -> str:
        """
        前のエントリに移動。pagesの値とフォルダ境界に応じて挙動が変わる。
        
        - pagesが1の場合：単純に1つ前に移動
        - pagesが2の場合：
          - 同一フォルダ内の移動：2つ前に移動
          - フォルダをまたぐ場合：フォルダの偶数/奇数とshiftフラグに応じて移動
        
        Returns:
            移動後のエントリパス
        """
        if not self._entries:
            return ""
            
        # 現在のフォルダを取得
        current_folder = self._get_current_folder()
        
        if self._pages == 1:
            # pagesが1の場合は単純に1つ前に移動
            self._current_idx = (self._current_idx - 1) % len(self._entries)
            return self._entries[self._current_idx]
        
        # pagesが2の場合の処理 (複雑なフォルダまたぎルール)
        
        # 2つ前と1つ前のインデックスを計算
        one_prev_idx = (self._current_idx - 1) % len(self._entries)
        two_prev_idx = (self._current_idx - 2) % len(self._entries)
        
        # フォルダ情報を取得
        one_prev_folder = os.path.dirname(self._entries[one_prev_idx])
        
        # 2つ前と1つ前が現在のフォルダと同じ場合
        if one_prev_folder == current_folder and os.path.dirname(self._entries[two_prev_idx]) == current_folder:
            # 2つ前に移動
            self._current_idx = two_prev_idx
            return self._entries[self._current_idx]
        
        # 2つ前と1つ前のフォルダが異なる場合
        if os.path.dirname(self._entries[two_prev_idx]) != one_prev_folder:
            # 1つ前に移動
            self._current_idx = one_prev_idx
            return self._entries[self._current_idx]
        
        # 前2つが同一の別フォルダの場合
        # そのフォルダのファイル数をカウント
        folder_start_idx = one_prev_idx
        while folder_start_idx > 0 and os.path.dirname(self._entries[folder_start_idx - 1]) == one_prev_folder:
            folder_start_idx -= 1
            
        folder_end_idx = one_prev_idx
        while (folder_end_idx + 1) < len(self._entries) and os.path.dirname(self._entries[folder_end_idx + 1]) == one_prev_folder:
            folder_end_idx += 1
            
        folder_files_count = folder_end_idx - folder_start_idx + 1
        
        # 偶数かつshiftがfalse、または奇数かつshiftがtrueの場合は2つ前へ
        if (folder_files_count % 2 == 0 and not self._shift) or (folder_files_count % 2 == 1 and self._shift):
            self._current_idx = two_prev_idx
        else:
            # それ以外の場合は1つ前へ
            self._current_idx = one_prev_idx
            
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
        前のフォルダの先頭へ移動
        まず現在のフォルダの先頭へ移動(go_top)してから、
        prevメソッドを使って前に移動
        
        Returns:
            移動後のエントリパス
        """
        # 現在のフォルダの先頭へ移動
        self.go_top()
        
        # prevメソッドを使って前に移動
        return self.prev()
    
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
        まず次のフォルダに移動(next_folder)してから、
        prevメソッドを使って前に移動することで現在のフォルダの末尾へ
        
        Returns:
            移動後のエントリパス
        """
        # まず次のフォルダの先頭へ移動
        self.next_folder()
        
        # prevメソッドで前に移動（現在のフォルダの末尾になる）
        return self.prev()
    
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
        先頭に移動(go_first)してから、
        prevメソッドを使って前に移動することで末尾へ
        
        Returns:
            移動後のエントリパス
        """
        # まず先頭へ移動
        self.go_first()
        
        # prevメソッドで前に移動（循環して末尾になる）
        return self.prev()
    
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
        pagesとshiftの値、およびフォルダ内の位置に応じて1つまたは2つのパスを返す
        
        - pagesが1の場合：現在のパスだけのリストを返す
        - pagesが2の場合：
          - フォルダ先頭かつshiftがtrueの場合：現在のパスだけのリストを返す
          - フォルダ末尾の場合：現在のパスだけのリストを返す
          - それ以外の場合：現在のパスと次のパスのリストを返す
            - ただし、フォルダ内相対位置に応じてカレント位置を調整する場合がある
        
        Returns:
            パスのリスト（1つまたは2つ）
        """
        if not self._entries:
            return []
            
        # pagesが1なら現在のパスだけのリストを返して終了
        if self._pages == 1:
            return [self._entries[self._current_idx]]
        
        # 現在のフォルダとフォルダ内での相対位置を取得
        current_folder = self._get_current_folder()
        
        # フォルダの先頭位置を特定
        folder_start_idx = self._current_idx
        while folder_start_idx > 0 and os.path.dirname(self._entries[folder_start_idx - 1]) == current_folder:
            folder_start_idx -= 1
        
        # フォルダの末尾かどうかを判定
        is_folder_end = False
        if self._current_idx == len(self._entries) - 1:
            # ファイルリストの最後なら必ずフォルダの末尾
            is_folder_end = True
        else:
            # 次のエントリが異なるフォルダならフォルダの末尾
            next_folder = os.path.dirname(self._entries[self._current_idx + 1])
            is_folder_end = (next_folder != current_folder)
        
        # フォルダ内での相対位置（0起点）
        relative_pos = self._current_idx - folder_start_idx
        
        # フォルダ先頭でshiftがtrueなら現在のパスだけのリストを返して終了
        if relative_pos == 0 and self._shift:
            return [self._entries[self._current_idx]]
            
        # フォルダ末尾なら現在のパスだけのリストを返して終了
        if is_folder_end:
            return [self._entries[self._current_idx]]
        
        # 表示調整用の一時的なインデックス
        display_idx = self._current_idx
        
        # shiftがtrueで現在のフォルダ相対位置が0起点で2以上の偶数ならカレント位置を１下げる
        if self._shift and relative_pos >= 2 and relative_pos % 2 == 0:
            display_idx = self._current_idx - 1
        # shiftがfalseで現在のフォルダ相対位置が0起点で１以上の奇数ならカレント位置を１下げる
        elif not self._shift and relative_pos >= 1 and relative_pos % 2 == 1:
            display_idx = self._current_idx - 1
            
        # 次のエントリのインデックス（循環）
        next_idx = (display_idx + 1) % len(self._entries)
        
        # 現在のパスと次のパスのリストを返す
        return [self._entries[display_idx], self._entries[next_idx]]

