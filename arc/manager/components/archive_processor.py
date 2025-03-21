"""
アーカイブ処理コンポーネント

アーカイブの読み込みと処理を担当します。
"""

import os
import tempfile
from typing import List, Optional, Dict, Tuple

from ...arc import EntryInfo, EntryType, EntryStatus

class ArchiveProcessor:
    """
    アーカイブ処理クラス
    
    アーカイブファイルの処理、内部エントリの抽出と登録を行います。
    """
    
    def __init__(self, manager):
        """
        アーカイブプロセッサーを初期化する
        
        Args:
            manager: 親となるEnhancedArchiveManagerインスタンス
        """
        self._manager = manager
    
    def process_archive_for_all_entries(self, base_path: str, arc_entry: EntryInfo, preload_content: bool = False) -> List[EntryInfo]:
        """
        アーカイブエントリの内容を処理し、すべてのエントリを取得する
        
        Args:
            base_path: 基準となるパス
            arc_entry: 処理するアーカイブエントリ
            preload_content: 使用しません（将来の拡張用）
            
        Returns:
            アーカイブ内のすべてのエントリ
        """
        # 循環参照防止とネスト深度チェック
        if self._manager._current_nest_level >= self._manager.MAX_NEST_DEPTH:
            self._manager.debug_warning(f"最大ネスト階層 ({self._manager.MAX_NEST_DEPTH}) に達しました")
            return []
        
        # 再帰レベルを増加
        self._manager._current_nest_level += 1
        
        try:
            # アーカイブのタイプを確認
            archive_path = arc_entry.path
            self._manager.debug_info(f"アーカイブ処理: {archive_path}")
            
            # アーカイブエントリのタイプをARCHIVEに設定
            if arc_entry.type != EntryType.ARCHIVE:
                self._manager.debug_info(f"エントリタイプをARCHIVEに修正: {arc_entry.path}")
                arc_entry.type = EntryType.ARCHIVE
            
            # 物理ファイルかネストされたアーカイブかで処理を分岐
            if os.path.isfile(archive_path):
                try:
                    entries = self._process_physical_archive(archive_path)
                    # 処理が成功したら、アーカイブエントリをREADYとしてマーク
                    arc_entry.status = EntryStatus.READY
                    return entries
                except (IOError, PermissionError) as e:
                    # エラーが発生した場合、アーカイブエントリをBROKENとしてマーク
                    self._manager.debug_error(f"アーカイブ処理中にエラー発生: {e}")
                    arc_entry.status = EntryStatus.BROKEN
                    return []
            else:
                # ネストされたアーカイブの処理
                try:
                    entries = self._process_nested_archive(base_path, arc_entry)
                    # 処理が成功したら、アーカイブエントリをREADYとしてマーク
                    arc_entry.status = EntryStatus.READY
                    return entries
                except (IOError, PermissionError) as e:
                    # エラーが発生した場合、アーカイブエントリをBROKENとしてマーク
                    self._manager.debug_error(f"ネストされたアーカイブ処理中にエラー発生: {e}")
                    arc_entry.status = EntryStatus.BROKEN
                    return []
        
        except Exception as e:
            self._manager.debug_error(f"アーカイブ処理中にエラーが発生しました: {e}", trace=True)
            # 予期せぬエラーの場合も、アーカイブエントリをBROKENとしてマーク
            if 'arc_entry' in locals():
                arc_entry.status = EntryStatus.BROKEN
            return []
            
        finally:
            # 再帰レベルを減少
            self._manager._current_nest_level -= 1
    
    def _process_physical_archive(self, archive_path: str) -> List[EntryInfo]:
        """
        物理ファイルとして存在するアーカイブを処理する
        
        Args:
            archive_path: 処理するアーカイブファイルのパス
            
        Returns:
            処理結果のエントリリスト
            
        Raises:
            IOError: アーカイブ処理中にエラーが発生した場合
            FileNotFoundError: アーカイブファイルが見つからない場合
            PermissionError: アクセス権限がない場合
        """
        self._manager.debug_info(f"物理アーカイブファイルを処理: {archive_path}")
        
        # ハンドラを取得
        handler = self._manager.get_handler(archive_path)
        if not handler:
            self._manager.debug_warning(f"アーカイブ用のハンドラが見つかりません: {archive_path}")
            raise IOError(f"アーカイブ用のハンドラが見つかりません: {archive_path}")
        
        # アーカイブ内のすべてのエントリを取得
        # ここでハンドラからIOError/FileNotFoundError/PermissionErrorが上位層に伝播します
        entries = handler.list_all_entries(archive_path)
        if not entries:
            self._manager.debug_warning(f"アーカイブ内にエントリがありません: {archive_path}")
            return []
        
        # エントリを修正（パス調整など）
        entries = self._manager.finalize_entries(entries, archive_path)
        
        # アーカイブタイプのエントリをマーク
        marked_entries = self._mark_archive_entries(entries)
        
        # エントリをキャッシュに登録する
        for entry in marked_entries:
            self._manager.debug_debug(f"物理アーカイブから取得したエントリをキャッシュに追加: {entry.name} ({entry.type.name}) rel_path=\"{entry.rel_path}\"")
            self._manager._entry_cache.add_entry_to_cache(entry)
        
        self._manager.debug_info(f"物理アーカイブから {len(marked_entries)} エントリを取得してキャッシュに登録")
        return marked_entries
    
    def _process_nested_archive(self, base_path: str, arc_entry: EntryInfo) -> List[EntryInfo]:
        """
        ネストされたアーカイブエントリを処理する
        
        Args:
            base_path: ベースパス
            arc_entry: 処理するアーカイブエントリ
            
        Returns:
            処理結果のエントリリスト
            
        Raises:
            IOError: アーカイブ処理中にエラーが発生した場合
            FileNotFoundError: アーカイブファイルが見つからない場合
            PermissionError: アクセス権限がない場合
        """
        archive_path = arc_entry.path
        self._manager.debug_info(f"ネストされたアーカイブを処理: {archive_path}")
        
        # 親アーカイブと内部パスを特定
        parent_path, internal_path = self._manager._path_resolver._analyze_path(archive_path)
        if not parent_path:
            self._manager.debug_warning(f"親アーカイブが特定できません: {archive_path}")
            raise FileNotFoundError(f"親アーカイブが特定できません: {archive_path}")
        
        # 絶対パスの確保
        if parent_path and self._manager.current_path and not os.path.isabs(parent_path):
            abs_path = os.path.join(self._manager.current_path, parent_path).replace('\\', '/')
            self._manager.debug_info(f"相対パスを絶対パスに変換: {parent_path} -> {abs_path}")
            parent_path = abs_path
        
        # 親アーカイブのハンドラを取得
        parent_handler = self._manager.get_handler(parent_path)
        if not parent_handler:
            self._manager.debug_warning(f"親アーカイブ用のハンドラが見つかりません: {parent_path}")
            raise IOError(f"親アーカイブ用のハンドラが見つかりません: {parent_path}")
        
        # ネストアーカイブのコンテンツを取得
        self._manager.debug_info(f"親アーカイブから内部アーカイブのコンテンツを取得: {parent_path} -> {internal_path}")
        try:
            nested_archive_content = parent_handler.read_archive_file(parent_path, internal_path)
        except (IOError, FileNotFoundError, PermissionError) as e:
            self._manager.debug_error(f"内部アーカイブのコンテンツを取得できませんでした: {e}")
            arc_entry.status = EntryStatus.BROKEN
            raise IOError(f"内部アーカイブのコンテンツを取得できませんでした: {str(e)}")
        
        if not nested_archive_content:
            self._manager.debug_warning(f"内部アーカイブのコンテンツを取得できませんでした")
            arc_entry.status = EntryStatus.BROKEN
            raise IOError(f"内部アーカイブのコンテンツを取得できませんでした: コンテンツが空です")
        
        # ネストアーカイブ用のハンドラを取得
        handler = self._manager.get_handler(archive_path)
        if not handler:
            self._manager.debug_warning(f"内部アーカイブ用のハンドラが見つかりません: {archive_path}")
            raise IOError(f"内部アーカイブ用のハンドラが見つかりません: {archive_path}")
        
        # バイトデータまたは一時ファイルとしてコンテンツをキャッシュ
        cache_result = self._cache_archive_content(arc_entry, nested_archive_content, handler, archive_path)
        if not cache_result:
            arc_entry.status = EntryStatus.BROKEN
            raise IOError(f"アーカイブコンテンツのキャッシュに失敗しました: {archive_path}")
        
        can_process_bytes, temp_file_path = cache_result
        
        # エントリリストを取得
        entries = self._get_entries_from_cached_content(handler, nested_archive_content, can_process_bytes, temp_file_path)
        if not entries:
            arc_entry.status = EntryStatus.BROKEN
            raise IOError(f"キャッシュされたコンテンツからエントリを取得できませんでした: {archive_path}")
        
        # エントリの処理とキャッシュへの登録
        result_entries = self._process_and_cache_entries(entries, arc_entry, archive_path)
        
        # 処理が成功したら、アーカイブエントリをREADYとしてマーク
        arc_entry.status = EntryStatus.READY
        return result_entries
    
    def _cache_archive_content(self, arc_entry: EntryInfo, content: bytes, handler, archive_path: str) -> Optional[Tuple[bool, Optional[str]]]:
        """
        アーカイブコンテンツをキャッシュする
        
        Args:
            arc_entry: アーカイブエントリ
            content: アーカイブのバイトコンテンツ
            handler: アーカイブハンドラ
            archive_path: アーカイブのパス
            
        Returns:
            (バイト処理可能フラグ, 一時ファイルパス) のタプル。エラー時はNone
        """
        # バイト処理の可否を確認
        can_process_bytes = handler.can_handle_bytes(content, archive_path)
        temp_file_path = None
        
        # エントリにキャッシュフィールドがなければ追加
        if not hasattr(arc_entry, 'cache'):
            self._manager.debug_info(f"エントリにキャッシュフィールドを追加します")
            arc_entry.cache = None
        
        # キャッシュ処理
        if can_process_bytes:
            # バイトデータを直接キャッシュ
            self._manager.debug_info(f"バイトデータをキャッシュします ({len(content)} バイト)")
            arc_entry.cache = content
        else:
            # 一時ファイルとしてキャッシュ
            self._manager.debug_info(f"一時ファイルとしてキャッシュします")
            
            # 拡張子を取得
            _, ext = os.path.splitext(archive_path)
            if not ext:
                ext = '.bin'
            
            try:
                # 一時ファイルを作成
                temp_file_path = handler.save_to_temp_file(content, ext)
                if not temp_file_path:
                    self._manager.debug_error(f"一時ファイルの作成に失敗しました")
                    return None
                
                self._manager.debug_info(f"一時ファイルを作成しました: {temp_file_path}")
                arc_entry.cache = temp_file_path
                self._manager._temp_files.add(temp_file_path)  # 後でクリーンアップするために記録
                
            except Exception as e:
                self._manager.debug_error(f"一時ファイル処理中にエラー: {e}")
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                        self._manager._temp_files.discard(temp_file_path)
                    except Exception as e2:
                        self._manager.debug_error(f"一時ファイル削除中にエラー: {e2}")
                return None
        
        return (can_process_bytes, temp_file_path)
    
    def _get_entries_from_cached_content(self, handler, content: bytes, can_process_bytes: bool, temp_file_path: Optional[str]) -> Optional[List[EntryInfo]]:
        """
        キャッシュされたコンテンツからエントリリストを取得する
        
        Args:
            handler: アーカイブハンドラ
            content: アーカイブのバイトコンテンツ
            can_process_bytes: バイト処理可能フラグ
            temp_file_path: 一時ファイルのパス
            
        Returns:
            エントリのリスト。エラー時はNone
        """
        try:
            if can_process_bytes:
                # バイトデータから直接エントリリストを取得
                entries = handler.list_all_entries_from_bytes(content)
                self._manager.debug_info(f"バイトデータから {len(entries) if entries else 0} エントリを取得")
                return entries
            elif temp_file_path:
                # 一時ファイルからエントリリストを取得
                entries = handler.list_all_entries(temp_file_path)
                self._manager.debug_info(f"一時ファイルから {len(entries) if entries else 0} エントリを取得")
                return entries
        except Exception as e:
            self._manager.debug_error(f"エントリリスト取得中にエラー: {e}")
        
        return None
    
    def _process_and_cache_entries(self, entries: List[EntryInfo], arc_entry: EntryInfo, archive_path: str) -> List[EntryInfo]:
        """
        エントリを処理してキャッシュに登録する
        
        Args:
            entries: 処理するエントリのリスト
            arc_entry: 親アーカイブエントリ
            archive_path: アーカイブパス
            
        Returns:
            処理結果のエントリリスト
        """
        result_entries = []
        
        for entry in entries:
            # パスを構築
            entry_path = f"{archive_path}/{entry.rel_path}" if entry.rel_path else archive_path
            
            # 新しいエントリを作成
            new_entry = self._manager.get_handler(archive_path).create_entry_info(
                name=entry.name,
                path=entry_path,
                rel_path=entry.rel_path,
                type=entry.type,
                size=entry.size,
                modified_time=entry.modified_time,
                created_time=entry.created_time,
                is_hidden=entry.is_hidden,
                name_in_arc=entry.name_in_arc,
                attrs=entry.attrs,
                abs_path=entry_path
            )
            
            # エントリをファイナライズ
            finalized_entry = self._manager.finalize_entry(new_entry, arc_entry.path)
            result_entries.append(finalized_entry)
            
            # デバッグ用：エントリタイプを確認
            self._manager.debug_debug(f"エントリをキャッシュに追加: {finalized_entry.name} ({finalized_entry.type.name}) rel_path=\"{finalized_entry.rel_path}\"")
            
            # エントリをキャッシュに追加
            self._manager._entry_cache.add_entry_to_cache(finalized_entry)
        
        # アーカイブタイプのエントリをマーク
        marked_entries = self._mark_archive_entries(result_entries)
        
        self._manager.debug_info(f"{len(result_entries)} エントリをキャッシュに登録しました")
        
        return marked_entries
    
    def _mark_archive_entries(self, entries: List[EntryInfo]) -> List[EntryInfo]:
        """
        エントリリストのうち、アーカイブ拡張子を持つファイルをARCHIVEタイプとしてマークする
        
        Args:
            entries: 処理するエントリリスト
            
        Returns:
            処理後のエントリリスト
        """
        if not entries:
            return []
        
        for entry in entries:
            if entry.type == EntryType.FILE and self._manager._is_archive_by_extension(entry.name):
                entry.type = EntryType.ARCHIVE
        
        return entries
    
    def list_all_entries(self, path: str, recursive: bool = True) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるすべてのエントリを再帰的に取得する
        
        Args:
            path: リストを取得するディレクトリやアーカイブのパス（ベースパス）
            recursive: 再帰的に探索するかどうか
            
        Returns:
            すべてのエントリ情報のリスト
        """
        from .root_entry_manager import RootEntryManager
        
        # 処理のリセット
        self._manager._processed_paths = set()
        
        # キャッシュをリセット
        old_entries = self._manager._entry_cache.get_all_entries().copy() if "" in self._manager._entry_cache.get_all_entries() else {}
        self._manager._entry_cache.clear_cache()
        
        # パスを正規化
        path = path.replace('\\', '/')
        
        try:
            # ルートエントリを作成
            root_manager = RootEntryManager(self._manager)
            root_entry = root_manager.ensure_root_entry(path)
            
            # バグ修正: ルートエントリがファイルでアーカイブ拡張子を持つ場合、タイプをARCHIVEに修正
            if root_entry and root_entry.type == EntryType.FILE and os.path.isfile(path):
                if self._manager._is_archive_by_extension(root_entry.name):
                    self._manager.debug_info(f"ルートエントリのタイプをARCHIVEに修正: {root_entry.path}")
                    root_entry.type = EntryType.ARCHIVE
            
            # ハンドラを取得
            handler = self._manager.get_handler(path)
            if not handler:
                self._manager.debug_warning(f"パス '{path}' のハンドラが見つかりません")
                if root_entry:
                    root_entry.status = EntryStatus.BROKEN
                return [root_entry] if root_entry else []
            
            # 最初のレベルのエントリを取得
            try:
                raw_entries = handler.list_all_entries(path)
                # ルートエントリをREADYとマーク
                if root_entry:
                    root_entry.status = EntryStatus.READY
            except (IOError, FileNotFoundError, PermissionError) as e:
                self._manager.debug_error(f"エントリ一覧の取得中にエラー: {e}")
                if root_entry:
                    root_entry.status = EntryStatus.BROKEN
                return [root_entry] if root_entry else []
            
            if not raw_entries:
                self._manager.debug_info(f"パス '{path}' にエントリがありません")
                return [root_entry] if root_entry else []
            
            # エントリを処理
            base_entries = []
            for entry in raw_entries:
                finalized_entry = self._manager.finalize_entry(entry, path)
                base_entries.append(finalized_entry)
                self._manager._entry_cache.add_entry_to_cache(finalized_entry)
            
            self._manager.debug_info(f"ベースエントリを {len(base_entries)} 個取得しました")
            
            # 結果リスト（ルートエントリを先頭に）
            all_entries = [root_entry] if root_entry else []
            all_entries.extend(base_entries)
            
            # バグ修正: 結果リスト全体（ルートエントリを含む）に対してアーカイブ識別を実行
            all_entries = self._mark_archive_entries(all_entries)
            
            # 再帰処理の場合はアーカイブも処理
            if recursive:
                self._process_archives_recursively(all_entries, path)
            
            return all_entries
            
        except Exception as e:
            self._manager.debug_error(f"全エントリリスト取得中にエラー: {e}")
            if 'root_entry' in locals() and root_entry:
                root_entry.status = EntryStatus.BROKEN
                return [root_entry]
            return []
    
    def _process_archives_recursively(self, all_entries: List[EntryInfo], base_path: str) -> None:
        """
        アーカイブを再帰的に処理する
        
        Args:
            all_entries: 結果を格納するエントリリスト（参照渡し）
            base_path: ベースパス
        """
        processed_archives = set()  # 処理済みアーカイブの追跡
        archive_queue = []  # 処理するアーカイブのキュー
        
        # 最初のレベルのアーカイブを見つけてキューに追加
        for entry in all_entries:
            if entry.type == EntryType.ARCHIVE and entry.path not in processed_archives:
                archive_queue.append(entry)
        
        self._manager.debug_info(f"{len(archive_queue)} 個のアーカイブをキューに追加しました")
        
        # アーカイブを処理
        while archive_queue:
            arc_entry = archive_queue.pop(0)
            
            # 既に処理済みならスキップ
            if arc_entry.path in processed_archives:
                continue
            
            # 処理済みとしてマーク
            processed_archives.add(arc_entry.path)
            
            # アーカイブの内容を処理
            try:
                nested_entries = self._manager._process_archive_for_all_entries(base_path, arc_entry)
                
                # 結果を追加
                if nested_entries:
                    all_entries.extend(nested_entries)
                    
                    # さらに深いレベルのアーカイブを検索
                    for nested_entry in nested_entries:
                        if nested_entry.type == EntryType.ARCHIVE and nested_entry.path not in processed_archives:
                            archive_queue.append(nested_entry)
            except Exception as e:
                # エラーが発生してもBROKENとマークして処理を継続
                self._manager.debug_error(f"アーカイブ処理中にエラー: {arc_entry.path} - {e}")
                arc_entry.status = EntryStatus.BROKEN
                continue
