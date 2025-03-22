"""
エントリキャッシュ管理コンポーネント

アーカイブエントリのキャッシュ管理を行います。
"""

import os
from typing import Dict, List, Optional, Set

from ...arc import EntryInfo, EntryType, EntryStatus

class EntryCacheManager:
    """
    エントリキャッシュ管理クラス
    
    アーカイブ内のエントリをキャッシュし、高速なアクセスを提供します。
    """
    
    def __init__(self, manager):
        """
        エントリキャッシュマネージャーを初期化する
        
        Args:
            manager: 親となるEnhancedArchiveManagerインスタンス
        """
        self._manager = manager
        # すべてのエントリを格納する辞書
        self._all_entries: Dict[str, EntryInfo] = {}
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        # パスの正規化（先頭のスラッシュを削除）        
        if path.startswith('/'):
            path = path[1:]
            self._manager.debug_info(f"先頭のスラッシュを削除しました: {path}")
        
        # パスを正規化して相対パスとして扱う（末尾のスラッシュを削除）
        norm_path = path.replace('\\', '/').lstrip('/').rstrip('/')
        self._manager.debug_info(f"パス '{norm_path}' のエントリを取得")
        
        # キャッシュが初期化されていることを確認
        if not self._all_entries:
            self._manager.debug_info(f"エントリキャッシュが初期化されていません")
            return None
        
        self._manager.debug_info(f"キャッシュからエントリ情報を検索: {norm_path}")
        
        # 正規化したパスでキャッシュを直接検索
        if norm_path in self._all_entries:
            self._manager.debug_info(f"キャッシュでエントリを発見: {norm_path}")
            return self._all_entries[norm_path]
        
        self._manager.debug_info(f"キャッシュにエントリが見つかりませんでした: {norm_path}")
        
        # キャッシュに見つからない場合はNoneを返す
        return None
    
    def get_entry_cache(self) -> Dict[str, EntryInfo]:
        """
        現在のエントリキャッシュを取得する
        
        Returns:
            パスをキーとし、対応するエントリを値とする辞書
        """
        return self._all_entries.copy()
    
    def register_entry(self, key: str, entry: EntryInfo) -> None:
        """
        キーを指定してエントリをキャッシュに登録する
        
        Args:
            key: キャッシュのキー（通常は相対パス）
            entry: 登録するエントリ
        """
        # old_enhanced.pyでは直接self._all_entries[key] = entryを使用していたが、
        # このメソッドを通して同じ処理を行うようにする
        self._all_entries[key] = entry
        self._manager.debug_debug(f"エントリ \"{key}\" をキャッシュに登録: {entry.name} ({entry.type.name})")
    
    def add_entry_to_cache(self, entry: EntryInfo) -> None:
        """
        エントリをキャッシュに追加する
        
        Args:
            entry: 追加するエントリ
        """
        # キャッシュキーとして末尾の/を取り除いた相対パスを使用
        cache_key = entry.rel_path.rstrip('/')
        
        # old_enhanced.pyと同じ条件を使用して、空文字列キーも確実に登録
        if cache_key or cache_key == "":  # 空文字列キー（ルート）も登録可能に
            self.register_entry(cache_key, entry)
        else:
            self._manager.debug_warning(f"キャッシュキーが空のためエントリを登録しません: {entry.name} ({entry.type.name})")
    
    def clear_cache(self) -> None:
        """キャッシュをクリアする"""
        self._all_entries = {}
        self._manager.debug_info("エントリキャッシュをクリアしました")
    
    def get_all_entries(self) -> Dict[str, EntryInfo]:
        """
        すべてのキャッシュされたエントリを取得する
        
        Returns:
            キャッシュされたすべてのエントリ
        """
        return self._all_entries
    
    def set_all_entries(self, entries: Dict[str, EntryInfo]) -> None:
        """
        キャッシュを設定する（すべて置き換え）
        
        Args:
            entries: 新しいエントリキャッシュ
        """
        self._all_entries = entries
    
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるエントリのリストを取得する
        
        Args:
            path: リストを取得するディレクトリのパス（ベースパスからの相対パス）
            
        Returns:
            エントリ情報のリスト
    
        Raises:
            FileNotFoundError: 指定されたパスが見つからない場合
            PermissionError: 指定されたパスにアクセスできない場合
            ValueError: 指定されたパスのフォーマットが不正な場合
            IOError: その他のI/O操作でエラーが発生した場合
        """
        # 元のパス保存（後で判定に使用）
        original_path = path
        
        # パスの正規化（先頭のスラッシュを削除）
        if path.startswith('/'):
            path = path[1:]
            self._manager.debug_info(f"先頭のスラッシュを削除しました: {path}")
        
        # 正規化したパス
        norm_path = path.replace('\\', '/').rstrip('/')
        self._manager.debug_info(f"パス '{norm_path}' のエントリを取得")
        
        # 空のパスはルートを表す
        is_root = not norm_path
        
        # キャッシュが初期化されていることを確認
        if not self._all_entries:
            raise FileNotFoundError(f"エントリキャッシュが初期化されていません。set_current_pathを先に呼び出してください。")
        
        # 結果リスト
        result = []
        
        if is_root:
            # ルートの場合、直接の子エントリのみを返す
            seen_paths = set()  # 重複回避用
            
            for entry_key, entry in self._all_entries.items():
                # EntryInfoオブジェクトの場合のみ処理
                if isinstance(entry, EntryInfo):
                    # 修正：キャッシュのキーを使って子エントリかどうかを判断
                    # 1. キーが空文字でない（ルートエントリ自身を除外）
                    # 2. キーに'/'が含まれていない（直接の子のみ）
                    if entry_key != "" and '/' not in entry_key:
                        if entry.path not in seen_paths:
                            result.append(entry)
                            seen_paths.add(entry.path)
                            self._manager.debug_info(f"  発見 (ルート直下): {entry.name} ({entry.rel_path})")
        else:
            # ファイルエントリかどうかのチェック
            if norm_path in self._all_entries:
                entry = self._all_entries[norm_path]
                if isinstance(entry, EntryInfo) and entry.type == EntryType.FILE:
                    if original_path.endswith('/') or original_path.endswith('\\'):
                        self._manager.debug_error(f"ファイルパスの末尾にスラッシュがあります: {original_path}")
                        raise ValueError(f"ファイルパス '{original_path}' の末尾にスラッシュがあります。")
                    return [entry]
            
            # ディレクトリ/アーカイブの子エントリを検索
            if norm_path in self._all_entries:
                parent_entry = self._all_entries[norm_path]
                if isinstance(parent_entry, EntryInfo) and parent_entry.type in [EntryType.DIRECTORY, EntryType.ARCHIVE]:
                    # 重複回避用のセット
                    seen_paths = set()
                    # パスプレフィックスを構築（明示的に'/'を使用）
                    prefix = f"{norm_path}/"
                    
                    for child_key, child_entry in self._all_entries.items():
                        if isinstance(child_entry, EntryInfo):
                            # このパスの子エントリかどうかを正確に判断
                            # 1. エントリがディレクトリ自体でないこと
                            # 2. エントリキーがプレフィックスで始まること
                            if (child_key != norm_path and child_key.startswith(prefix)):
                                # プレフィックス後の部分を抽出
                                rest_path = child_key[len(prefix):]
                                # 直接の子エントリ（それ以上ネストしていない）のみを対象
                                if '/' not in rest_path:
                                    if child_entry.path not in seen_paths:
                                        result.append(child_entry)
                                        seen_paths.add(child_entry.path)
                                        self._manager.debug_info(f"  発見: {child_entry.name} ({child_entry.rel_path})")
                    return result
            
            # 見つからない場合
            self._manager.debug_error(f"パス '{path}' にエントリが見つかりません")
            raise FileNotFoundError(f"指定されたパス '{path}' にエントリが見つかりません")
        
        return result

    def set_entry_status(self, path: str, status: EntryStatus) -> bool:
        """
        指定されたパスのエントリのステータスを設定する
        
        Args:
            path: ステータスを設定するエントリのパス
            status: 設定する新しいステータス
            
        Returns:
            更新に成功した場合はTrue、エントリが見つからない場合はFalse
        """
        # キャッシュからエントリを取得
        entry = self.get_entry_info(path)
        if entry is None:
            self._manager.debug_warning(f"ステータス更新: エントリが見つかりません: {path}")
            return False
            
        # ステータスを更新
        old_status = entry.status if hasattr(entry, 'status') else 'None'
        entry.status = status
        self._manager.debug_info(f"エントリステータスを更新: {path}, {old_status} -> {status}")
        return True
