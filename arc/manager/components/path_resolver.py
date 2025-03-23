"""
パス解決コンポーネント

パスの解析と適切なハンドラの解決を担当します。
"""

import os
from typing import Optional, Tuple, List, Any

from ...arc import EntryInfo, EntryType
from ...handler.handler import ArchiveHandler

class PathResolver:
    """
    パス解決クラス
    
    パスの解析、アーカイブパスの特定、ハンドラの解決を行います。
    """
    
    def __init__(self, manager):
        """
        パス解決マネージャーを初期化する
        
        Args:
            manager: 親となるEnhancedArchiveManagerインスタンス
        """
        self._manager = manager
        # サポートされるアーカイブ拡張子のリスト
        self._archive_extensions = []
    
    def update_archive_extensions(self) -> List[str]:
        """
        サポートされているアーカイブ拡張子のリストを更新する
        
        Returns:
            更新されたアーカイブ拡張子のリスト
        """
        # 各ハンドラからサポートされている拡張子を収集
        self._archive_extensions = []
        for handler in self._manager.handlers:
            self._archive_extensions.extend(handler.supported_extensions)
        # 重複を除去
        self._archive_extensions = list(set(self._archive_extensions))
        
        # FileSystemHandlerにアーカイブ拡張子を設定
        for handler in self._manager.handlers:
            if handler.__class__.__name__ == 'FileSystemHandler':
                if hasattr(handler, 'set_archive_extensions'):
                    handler.set_archive_extensions(self._archive_extensions)
                    break
        
        return self._archive_extensions
    
    def is_archive_by_extension(self, path: str) -> bool:
        """
        パスがアーカイブの拡張子を持つかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            アーカイブの拡張子を持つ場合はTrue、そうでなければFalse
        """
        if not self._archive_extensions:
            self.update_archive_extensions()
            
        _, ext = os.path.splitext(path.lower())
        return ext in self._archive_extensions
    
    def get_handler(self, path: str) -> Optional[ArchiveHandler]:
        """
        指定されたパスを処理できるハンドラを取得する
        
        Args:
            path: 処理するファイルのパス
            
        Returns:
            ハンドラのインスタンス。処理できるハンドラがない場合はNone
        """
        # パスを正規化
        norm_path = path.replace('\\', '/')
        
        # キャッシュをチェック
        if norm_path in self._manager._handler_cache:
            handler = self._manager._handler_cache[norm_path]
            # ハンドラのcurrent_pathを更新
            if self._manager.current_path:
                handler.set_current_path(self._manager.current_path)
            self._manager.debug_info(f"Handler found in cache: {handler.__class__.__name__}")
            return handler
        
        self._manager.debug_info(f"Getting handler for path: {norm_path}")
        
        # アーカイブのアクセスパターンを検出（末尾がスラッシュで終わるアーカイブパス）
        if norm_path.endswith('/'):
            # アーカイブ内部アクセス - アーカイブ名を抽出
            base_path = norm_path.rstrip('/')
            
            # アーカイブファイルが存在するか確認
            if os.path.isfile(base_path):
                # ファイル拡張子を確認
                _, ext = os.path.splitext(base_path.lower())
                
                # アーカイブハンドラを探す
                for handler in self._manager.handlers.__reversed__():
                    # ハンドラにcurrent_pathを設定
                    if self._manager.current_path:
                        handler.set_current_path(self._manager.current_path)
                    
                    if ext in handler.supported_extensions and handler.can_handle(base_path):
                        # キャッシュに追加
                        self._manager._handler_cache[norm_path] = handler
                        self._manager.debug_info(f"Archive directory handler found: {handler.__class__.__name__}")
                        return handler
        
        # 通常のパス処理も逆順にハンドラを検索する
        for handler in self._manager.handlers.__reversed__():
            # ハンドラにcurrent_pathを設定
            if self._manager.current_path:
                handler.set_current_path(self._manager.current_path)
            self._manager.debug_debug(f"checking: {handler.__class__.__name__}")
            
            try:
                if handler.can_handle(norm_path):
                    # このハンドラで処理可能
                    self._manager._handler_cache[norm_path] = handler
                    self._manager.debug_info(f"Handler matched: {handler.__class__.__name__}")
                    return handler
            except Exception as e:
                self._manager.debug_error(f"Handler error ({handler.__class__.__name__}): {e}", trace=True)
        
        # 該当するハンドラが見つからない
        self._manager.debug_warning(f"No handler found for: {norm_path}")
        return None
    
    def resolve_file_source(self, path: str) -> Tuple[str, str, Optional[bytes]]:
        """
        パスからアーカイブパス、内部パス、キャッシュされたバイトデータを導き出す
        
        Args:
            path: 処理対象のパス
            
        Returns:
            (アーカイブパス, 内部パス, キャッシュされたバイト) のタプル
            - アーカイブが見つからない場合は (current_path, "", None)
            - バイトデータが直接キャッシュされている場合は (仮想パス, internal_path, bytes)
            - 一時ファイルでキャッシュされている場合は (cache_path, internal_path, None)
            - 通常のアーカイブ内ファイルの場合は (archive_path, internal_path, None)
        """
        # パスを正規化（先頭のスラッシュを削除、末尾のスラッシュも削除）
        norm_path = path.replace('\\', '/').lstrip('/').rstrip('/')
        self._manager.debug_info(f"ファイルソース解決: {norm_path}")
        
        # 1. まずエントリキャッシュから完全一致するエントリを検索
        entry_info = self._manager.get_entry_info(norm_path)
        
        # エントリが見つからない場合は早期リターン
        if not entry_info:
            self._manager.debug_warning(f"指定されたパス {norm_path} に対応するエントリが見つかりません")
            return "", "", None
        
        # 2. パスコンポーネントを解析してアーカイブを特定
        archive_path = ""
        internal_path = entry_info.name_in_arc  # name_in_arcは必ず存在する前提
        self._manager.debug_info(f"name_in_arcを内部パスとして使用: {internal_path}")
        
        # パスをコンポーネントに分解して親となるアーカイブを特定
        parent_archive_path = self._find_parent_archive(norm_path)
        
        if parent_archive_path:
            archive_path = parent_archive_path
            
            # 親アーカイブエントリをキャッシュから探す
            parent_entry = self._find_archive_entry_in_cache(parent_archive_path)
            
            if parent_entry and hasattr(parent_entry, 'cache') and parent_entry.cache is not None:
                cache = parent_entry.cache
                if isinstance(cache, bytes):
                    self._manager.debug_info(f"アーカイブエントリからキャッシュされたバイトデータを返します: {len(cache)} バイト")
                    return parent_entry.path, internal_path, cache
                elif isinstance(cache, str) and os.path.exists(cache):
                    self._manager.debug_info(f"アーカイブエントリからキャッシュされた一時ファイルを返します: {cache}")
                    return cache, internal_path, None
        
        # アーカイブパスが特定できた場合
        if archive_path:
            # 相対パスを絶対パスに変換
            if not os.path.isabs(archive_path) and self._manager.current_path:
                archive_path = os.path.join(self._manager.current_path, archive_path).replace('\\', '/')
                self._manager.debug_info(f"アーカイブパスを絶対パスに変換: {archive_path}")
            
            return archive_path, internal_path, None
        
        # 親アーカイブが見つからない場合は、current_pathとname_in_arcを返す
        # これにより、ルートエントリなどの処理が正しく行われる
        self._manager.debug_info(f"親アーカイブが見つからないため、ルートパスを使用します")
        return self._manager.current_path, entry_info.name_in_arc, None

    def _find_parent_archive(self, path: str) -> str:
        """
        指定されたパスの親アーカイブのパスを特定する
        
        パスを末尾から順にさかのぼり、ARCHIVE属性を持つエントリを親アーカイブとして特定する
        
        Args:
            path: 解析するパス
            
        Returns:
            親アーカイブのパス。見つからない場合は空文字列
        """
        # パスを正規化
        norm_path = path.replace('\\', '/')
        
        # パスをコンポーネントに分解
        parts = norm_path.split('/')
        
        # 自分自身はスキップ（親アーカイブを探すため）
        if len(parts) <= 1:
            return ""  # 親がない場合は空文字列を返す
        
        # パスを末尾から順にさかのぼる
        current_path = norm_path
        
        # 自分自身をスキップ（親アーカイブを探すため）
        if '/' in current_path:
            current_path = current_path.rsplit('/', 1)[0]
        else:
            # パスにスラッシュがなければ親はない
            return ""
        
        # パスを順にさかのぼりながら親アーカイブを探す
        while current_path:
            # キャッシュでこのパスのエントリを検索
            norm_current_path = current_path.rstrip('/')
            cached_entries = self._manager._entry_cache.get_all_entries()
            if norm_current_path in cached_entries:
                entry = cached_entries[norm_current_path]
                if entry.type == EntryType.ARCHIVE:
                    return current_path
            
            # 物理ファイルの場合はアーカイブかどうか確認
            if os.path.isfile(current_path):
                _, ext = os.path.splitext(current_path.lower())
                if ext in self._archive_extensions:
                    return current_path
            
            # さらに親をさかのぼる
            if '/' in current_path:
                current_path = current_path.rsplit('/', 1)[0]
            else:
                break
        
        # 見つからない場合は空文字列
        return ""

    def _find_archive_entry_in_cache(self, archive_path: str) -> Optional[EntryInfo]:
        """
        キャッシュからアーカイブエントリを探す
        
        Args:
            archive_path: 探すアーカイブのパス
            
        Returns:
            見つかったアーカイブエントリ。見つからなければNone
        """
        # アーカイブパスを正規化（先頭と末尾のスラッシュを削除）
        norm_path = archive_path.replace('\\', '/').lstrip('/').rstrip('/')
        
        # 正規化したパスでキャッシュを直接検索
        cached_entries = self._manager._entry_cache.get_all_entries()
        if norm_path in cached_entries:
            entry = cached_entries[norm_path]
            if entry.type == EntryType.ARCHIVE:
                return entry
        
        return None
    
    def _analyze_path(self, path: str) -> Tuple[str, str]:
        """
        パスを解析し、アーカイブパスと内部パスに分割する
        
        Args:
            path: 分割するパス
            
        Returns:
            (アーカイブファイルのパス, 内部パス) のタプル
        """
        # 正規化したパス
        norm_path = path.replace('\\', '/')
        self._manager.debug_info(f"パスを解析: {norm_path}")
        
        # 物理フォルダまたはファイルの場合は、すぐにそのパスをアーカイブパスとして返す
        if os.path.isdir(norm_path) or os.path.isfile(norm_path):
            self._manager.debug_info(f"物理パスを検出: {norm_path}")
            return norm_path, ""
        
        # パスをコンポーネントに分解
        parts = norm_path.split('/')
        
        # ファイル自体を除いたパスから始める
        if len(parts) > 1:
            # 最後の要素を除いたパス
            test_path = '/'.join(parts[:-1])
            # 最後の要素（内部パスの先頭部分）
            remaining = parts[-1]
        else:
            # パスが単一要素の場合
            test_path = ""  # 空文字から始める
            remaining = norm_path  # 全体が内部パスになる可能性
        
        # パスを段階的に削りながらアーカイブを検索
        while test_path:
            # 絶対パスに変換
            abs_test_path = test_path
            if not os.path.isabs(test_path) and self._manager.current_path:
                abs_test_path = os.path.join(self._manager.current_path, test_path).replace('\\', '/')
            
            # ハンドラを取得
            handler = self._manager.get_handler(abs_test_path)
            
            # ハンドラがcan_archive()を実装し、かつTrueを返すかチェック
            if handler and hasattr(handler, 'can_archive') and handler.can_archive():
                # アーカイブハンドラが見つかった場合
                abs_test_path = abs_test_path.rstrip('/')
                self._manager.debug_info(f"アーカイブパス特定: {abs_test_path}, 内部パス: {remaining}")
                return abs_test_path, remaining
            
            # パスをさらに削る（次の階層へ）
            if '/' in test_path:
                last_slash = test_path.rindex('/')
                # 残りのパスを内部パスとして蓄積
                next_part = test_path[last_slash+1:]
                remaining = next_part + '/' + remaining if next_part else remaining
                # テストパスを短くする
                test_path = test_path[:last_slash]
            else:
                # 最後の要素
                if test_path:
                    remaining = test_path + '/' + remaining
                test_path = ""  # これ以上削れない
        
        # ここに到達する場合、アーカイブパス候補がなかった
        # 最終手段として、ルートがアーカイブファイルかどうかをチェック
        if self._manager.current_path and os.path.isfile(self._manager.current_path) and self.is_archive_by_extension(self._manager.current_path):
            # ルートがアーカイブファイルの場合、current_pathをアーカイブパスとして、
            # 元のパス全体を内部パスとして返す
            self._manager.debug_info(f"ルートアーカイブを使用: {self._manager.current_path}, 内部パス: {norm_path}")
            return self._manager.current_path, norm_path
        
        # ルートもアーカイブでない場合は空のアーカイブパスと残りの全部を返す
        self._manager.debug_warning(f"アーカイブパスが特定できませんでした: {norm_path}")
        return "", remaining
