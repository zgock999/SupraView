"""
スリム版 拡張アーカイブマネージャー

肥大化したEnhancedArchiveManagerの機能を複数のモジュールに分割し、
インターフェースを維持したスリム版を提供します。
"""

import os
from typing import List, Optional, Dict, Set, Any

from .manager import ArchiveManager
from ..arc import EntryInfo, EntryType
from ..handler.handler import ArchiveHandler

# 分割した機能をインポート
from .components.entry_cache import EntryCacheManager
from .components.path_resolver import PathResolver
from .components.archive_processor import ArchiveProcessor
from .components.entry_finalizer import EntryFinalizer
from .components.root_entry_manager import RootEntryManager

class EnhancedArchiveManager(ArchiveManager):
    """
    強化されたアーカイブマネージャー
    
    アーカイブ内のアーカイブ（ネスト構造）をサポートするための拡張
    ハンドラに処理を委譲し、アーカイブ形式に依存しないインターフェースを提供
    
    機能を複数のコンポーネントに分割して内部実装を簡素化
    """

    # 最大ネスト階層の深さ制限
    MAX_NEST_DEPTH = 5
    
    def __init__(self):
        """拡張アーカイブマネージャを初期化する"""
        super().__init__()
        
        # 分割した機能コンポーネントを初期化
        self._entry_cache = EntryCacheManager(self)
        self._path_resolver = PathResolver(self)
        self._archive_processor = ArchiveProcessor(self)
        self._entry_finalizer = EntryFinalizer(self)
        self._root_manager = RootEntryManager(self)
        
        # サポートされるアーカイブ拡張子のリスト
        self._archive_extensions = []
        # 現在処理中のアーカイブパスを追跡するセット（循環参照防止）
        self._processing_archives = set()
        # 処理中のネストレベル（再帰制限用）
        self._current_nest_level = 0
        # 処理済みパスの追跡用セット
        self._processed_paths: Set[str] = set()
        # 一時ファイルの追跡（クリーンアップ用）
        self._temp_files: Set[str] = set()
    
    def _update_archive_extensions(self):
        """サポートされているアーカイブ拡張子のリストを更新する"""
        return self._path_resolver.update_archive_extensions()
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        EnhancedArchiveManagerは前提としてすべてのエントリがキャッシュに存在するため、
        キャッシュからのみエントリを検索する。キャッシュにないエントリは存在しないとみなす。
        
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        return self._entry_cache.get_entry_info(path)

    def _is_archive_by_extension(self, path: str) -> bool:
        """パスがアーカイブの拡張子を持つかどうかを判定する"""
        return self._path_resolver.is_archive_by_extension(path)
    
    def get_handler(self, path: str) -> Optional[ArchiveHandler]:
        """
        指定されたパスを処理できるハンドラを取得する
        
        Args:
            path: 処理するファイルのパス
            
        Returns:
            ハンドラのインスタンス。処理できるハンドラがない場合はNone
        """
        return self._path_resolver.get_handler(path)
    
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
        return self._entry_cache.list_entries(path)
    
    def finalize_entry(self, entry: EntryInfo, archive_path: str) -> EntryInfo:
        """
        ハンドラから帰ってきた未完成のエントリを完成させ、追加処理を行う
        
        Args:
            entry: 処理するエントリ
            archive_path: アーカイブ/フォルダの絶対パス
            
        Returns:
            最終処理後のエントリ
        """
        return self._entry_finalizer.finalize_entry(entry, archive_path)

    def finalize_entries(self, entries: List[EntryInfo], archive_path: str) -> List[EntryInfo]:
        """
        ハンドラから帰ってきた未完成のエントリリストを完成させる
        
        Args:
            entries: 処理するエントリリスト
            archive_path: アーカイブ/フォルダの絶対パス
            
        Returns:
            最終処理後のエントリリスト
        """
        return self._entry_finalizer.finalize_entries(entries, archive_path)

    def _process_archive_for_all_entries(self, base_path: str, arc_entry: EntryInfo, preload_content: bool = False) -> List[EntryInfo]:
        """
        アーカイブエントリの内容を処理し、すべてのエントリを取得する
        
        Args:
            base_path: 基準となるパス
            arc_entry: 処理するアーカイブエントリ
            preload_content: 使用しません（将来の拡張用）
            
        Returns:
            アーカイブ内のすべてのエントリ
        """
        return self._archive_processor.process_archive_for_all_entries(base_path, arc_entry, preload_content)
        
    def get_entry_cache(self) -> Dict[str, EntryInfo]:
        """
        現在のエントリキャッシュを取得する
        
        Returns:
            パスをキーとし、対応するエントリのリストを値とする辞書
        """
        return self._entry_cache.get_entry_cache()

    def set_current_path(self, path: str) -> None:
        """
        現在のベースパスを設定する
        パス設定後は自動的にlist_all_entriesを呼び出して、
        全エントリリストを予め取得しておく
        
        Args:
            path: 設定するベースパス
        """
        # まず基底クラスのset_current_pathを呼び出して全ハンドラーに通知
        super().set_current_path(path)
        self.debug_info(f"現在のパスを設定: {path}")
        
        # その後、すべてのエントリリストを再帰的に取得
        try:
            self.debug_info("全エントリリストを取得中...")
            entries = self.list_all_entries(path, recursive=True)
            self.debug_info(f"{len(entries)} エントリを取得しました")
            return entries
        except Exception as e:
            self.debug_error(f"全エントリリスト取得中にエラーが発生しました: {e}", trace=True)

    def list_all_entries(self, path: str, recursive: bool = True) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるすべてのエントリを再帰的に取得する
        
        Args:
            path: リストを取得するディレクトリやアーカイブのパス（ベースパス）
            recursive: 再帰的に探索するかどうか（デフォルトはTrue）
            
        Returns:
            すべてのエントリ情報のリスト
        """
        return self._archive_processor.list_all_entries(path, recursive)

    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定されたパスのファイルの内容を読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
            
        Raises:
            FileNotFoundError: 指定されたパスが存在しない場合
        """
        # パスの正規化（先頭のスラッシュを削除）
        if path.startswith('/'):
            path = path[1:]
            self.debug_info(f"先頭のスラッシュを削除しました: {path}")
        
        # パスからアーカイブと内部パス、キャッシュされたバイトデータを導き出す
        self.debug_info(f"アーカイブパス解析: {path}")
        result = self._path_resolver.resolve_file_source(path)
        archive_path, internal_path, cached_bytes = result
        self.debug_info(f"ファイル読み込み: {path} -> {archive_path} -> {internal_path}")
        
        # アーカイブパスと内部パスがある場合
        if archive_path and internal_path:
            self.debug_info(f"アーカイブ内のファイルを読み込み: {archive_path} -> {internal_path}")
            handler = self.get_handler(archive_path)
            if (handler):
                # キャッシュされたバイトデータがある場合は、read_file_from_bytesを使用
                if cached_bytes is not None:
                    self.debug_info(f"キャッシュされた書庫データから内部ファイルを抽出: {internal_path}")
                    content = handler.read_file_from_bytes(cached_bytes, internal_path)
                    if content is None:
                        raise FileNotFoundError(f"指定されたファイルはアーカイブ内に存在しません: {path}")
                    return content
                else:
                    # 通常のファイル読み込み
                    content = handler.read_archive_file(archive_path, internal_path)
                    if content is None:
                        raise FileNotFoundError(f"指定されたファイルはアーカイブ内に存在しません: {path}")
                    return content
        
        # キャッシュされたバイトデータがある場合は、そのまま返す
        if cached_bytes is not None:
            self.debug_info(f"キャッシュからファイルを読み込み: {path}")
            return cached_bytes
        
        # 該当するファイルが見つからない場合はエラー
        raise FileNotFoundError(f"指定されたファイルは存在しません: {path}")
