"""
アーカイブマネージャーファクトリ

アーカイブマネージャーの生成と取得を行うファクトリモジュール
"""

import os
import tempfile
import shutil
from typing import List, Optional, BinaryIO, Tuple, Dict, Set, Union, Any
from .arc import ArchiveManager, EntryInfo, EntryType, ArchiveHandler
from .handlers import register_standard_handlers  # handlers.py からインポート

# シングルトンインスタンス
_instance: ArchiveManager = None


class ArchiveManager:
    """
    アーカイブマネージャークラス
    
    様々なアーカイブ形式を統一的に扱うためのインターフェース
    """
    
    def __init__(self):
        """初期化"""
        self.handlers: List[ArchiveHandler] = []
        self._handler_cache: Dict[str, ArchiveHandler] = {}
    
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
        if norm_path in self._handler_cache:
            print(f"Handler found in cache: {self._handler_cache[norm_path].__class__.__name__}")
            return self._handler_cache[norm_path]
        
        print(f"Getting handler for path: {norm_path}")
        
        # 各ハンドラでチェック
        for handler in self.handlers.__reversed__():
            # ハンドラが絶対パスを要求し、パスが相対パスの場合は調整
            check_path = norm_path
            if (handler.use_absolute() and hasattr(self, 'current_path') and self.current_path):
                if not os.path.isabs(check_path):
                    abs_path = os.path.join(self.current_path, check_path)
                    print(f"Converting to absolute path for handler: {check_path} -> {abs_path}")
                    check_path = abs_path.replace('\\', '/')
            
            try:
                if handler.can_handle(check_path):
                    print(f"Handler found: {handler.__class__.__name__}")
                    # キャッシュに追加
                    self._handler_cache[norm_path] = handler
                    return handler
                else:
                    print(f"Handler cannot handle: {handler.__class__.__name__}")
            except Exception as e:
                print(f"Handler error ({handler.__class__.__name__}): {e}")
        
        return None
    
    def register_handler(self, handler: ArchiveHandler) -> None:
        """
        ハンドラを登録する
        
        Args:
            handler: 登録するハンドラ
        """
        self.handlers.append(handler)
    
    def clear_cache(self) -> None:
        """キャッシュをクリアする"""
        self._handler_cache.clear()
    
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるエントリのリストを取得する
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        handler = self.get_handler(path)
        if (handler is None):
            return []
        
        # ハンドラが絶対パスを要求する場合は調整
        use_path = path
        if handler.use_absolute() and hasattr(self, 'current_path') and self.current_path:
            if not os.path.isabs(path):
                use_path = os.path.join(self.current_path, path).replace('\\', '/')
                print(f"Using absolute path for list_entries: {path} -> {use_path}")
        
        return handler.list_entries(use_path)
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        handler = self.get_handler(path)
        if handler is None:
            return None
        
        # ハンドラが絶対パスを要求する場合は調整
        use_path = path
        if handler.use_absolute() and hasattr(self, 'current_path') and self.current_path:
            if not os.path.isabs(path):
                use_path = os.path.join(self.current_path, path).replace('\\', '/')
                print(f"Using absolute path for get_entry_info: {path} -> {use_path}")
        
        return handler.get_entry_info(use_path)
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定されたパスのファイルの内容を読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        handler = self.get_handler(path)
        if handler is None:
            return None
        
        # ハンドラが絶対パスを要求する場合は調整
        use_path = path
        if handler.use_absolute() and hasattr(self, 'current_path') and self.current_path:
            if not os.path.isabs(path):
                use_path = os.path.join(self.current_path, path).replace('\\', '/')
                print(f"Using absolute path for read_file: {path} -> {use_path}")
        
        return handler.read_file(use_path)
    
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        handler = self.get_handler(path)
        if handler is None:
            return None
            
        # ハンドラが絶対パスを要求する場合は調整
        use_path = path
        if handler.use_absolute() and hasattr(self, 'current_path') and self.current_path:
            if not os.path.isabs(path):
                use_path = os.path.join(self.current_path, path).replace('\\', '/')
                print(f"Using absolute path for get_stream: {path} -> {use_path}")
        
        return handler.get_stream(use_path)
    
    def is_archive(self, path: str) -> bool:
        """
        指定されたパスがアーカイブファイルかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            アーカイブファイルならTrue、そうでなければFalse
        """
        info = self.get_entry_info(path)
        return info is not None and info.type == EntryType.ARCHIVE
    
    def is_directory(self, path: str) -> bool:
        """
        指定されたパスがディレクトリかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、それ以外の場合はFalse
        """
        handler = self.get_handler(path)
        if handler is None:
            return False
            
        # ハンドラが絶対パスを要求する場合は調整
        use_path = path
        if handler.use_absolute() and hasattr(self, 'current_path') and self.current_path:
            if not os.path.isabs(path):
                use_path = os.path.join(self.current_path, path).replace('\\', '/')
                print(f"Using absolute path for is_directory: {path} -> {use_path}")
        
        return handler.is_directory(use_path)
    
    def get_parent_path(self, path: str) -> str:
        """
        親ディレクトリのパスを取得する
        
        Args:
            path: 対象のパス
            
        Returns:
            親ディレクトリのパス
        """
        handler = self.get_handler(path)
        if handler is None:
            # デフォルト実装（スラッシュで区切られたパスの最後の要素を除去）
            norm_path = path.replace('\\', '/')
            last_slash = norm_path.rfind('/')
            if (last_slash >= 0):
                return norm_path[:last_slash]
            return ""
            
        # ハンドラが絶対パスを要求する場合は調整
        use_path = path
        if handler.use_absolute() and hasattr(self, 'current_path') and self.current_path:
            if not os.path.isabs(path):
                use_path = os.path.join(self.current_path, path).replace('\\', '/')
                print(f"Using absolute path for get_parent_path: {path} -> {use_path}")
        
        return handler.get_parent_path(use_path)
        
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        handler = self.get_handler(archive_path)
        if handler is None:
            return None
            
        # ハンドラが絶対パスを要求する場合は調整
        use_archive_path = archive_path
        if handler.use_absolute() and hasattr(self, 'current_path') and self.current_path:
            if not os.path.isabs(archive_path):
                use_archive_path = os.path.join(self.current_path, archive_path).replace('\\', '/')
                print(f"Using absolute archive path: {archive_path} -> {use_archive_path}")
        
        return handler.read_archive_file(use_archive_path, file_path)


class EnhancedArchiveManager(ArchiveManager):
    """
    強化されたアーカイブマネージャー
    
    アーカイブ内のアーカイブ（ネスト構造）をサポートするための拡張
    ハンドラに処理を委譲し、アーカイブ形式に依存しないインターフェースを提供
    """
    
    # 最大ネスト階層の深さ制限
    MAX_NEST_DEPTH = 5
    
    def __init__(self):
        """拡張アーカイブマネージャを初期化する"""
        super().__init__()
        # サポートされるアーカイブ拡張子のリスト
        self._archive_extensions = []
        # 現在処理中のアーカイブパスを追跡するセット（循環参照防止）
        self._processing_archives = set()
        # 処理中のネストレベル（再帰制限用）
        self._current_nest_level = 0
        # すべてのエントリを格納するためのクラス変数
        self._all_entries: Dict[str, List[EntryInfo]] = {}
        # 処理済みパスの追跡用セット
        self._processed_paths: Set[str] = set()
        # 現在のベースパス（このパスからの相対パスでエントリを管理）
        self.current_path: str = ""
        # 一時ファイルの追跡（クリーンアップ用）
        self._temp_files: Set[str] = set()
    
    def _update_archive_extensions(self):
        """サポートされているアーカイブ拡張子のリストを更新する"""
        # 各ハンドラからサポートされている拡張子を収集
        self._archive_extensions = []
        for handler in self.handlers:
            self._archive_extensions.extend(handler.supported_extensions)
        # 重複を除去
        self._archive_extensions = list(set(self._archive_extensions))
    
    def _is_archive_by_extension(self, path: str) -> bool:
        """パスがアーカイブの拡張子を持つかどうかを判定する"""
        if not self._archive_extensions:
            self._update_archive_extensions()
            
        _, ext = os.path.splitext(path.lower())
        return ext in self._archive_extensions
    
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるエントリのリストを取得する
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        
        Raises:
            FileNotFoundError: 指定されたパスが見つからない場合
            PermissionError: 指定されたパスにアクセスできない場合
            ValueError: 指定されたパスのフォーマットが不正な場合
            IOError: その他のI/O操作でエラーが発生した場合
        """
        # パスを正規化
        norm_path = path.replace('\\', '/')
        print(f"EnhancedArchiveManager: パス '{norm_path}' のエントリを取得")
        
        # まず、キャッシュされたエントリリストがあるかチェック
        if self._all_entries:
            print(f"EnhancedArchiveManager: キャッシュされた全エントリから検索します ({sum(len(entries) for entries in self._all_entries.values())} エントリ)")
            
            # 1. 完全一致のキャッシュエントリをまず探す
            if norm_path in self._all_entries:
                print(f"EnhancedArchiveManager: パスに対する直接キャッシュを発見: {norm_path}")
                return self._all_entries[norm_path]
            
            # 2. キャッシュからエントリを抽出
            result = []
            seen_paths = set()  # 既に追加したパス
            seen_dirs = set()   # 既に追加したディレクトリ
            
            # すべてのキャッシュされたエントリに対して処理
            for cache_path, entries in self._all_entries.items():
                for entry in entries:
                    entry_path = entry.path
                    
                    # 指定されたパスがエントリの親パスとして一致するかチェック
                    if self._is_parent_dir(norm_path, entry_path):
                        # エントリパスから直接的な子要素を抽出
                        child_path = self._get_child_path(norm_path, entry_path)
                        if child_path:
                            # '/'を含む場合はディレクトリ
                            if '/' in child_path:
                                dir_name = child_path.split('/')[0]
                                dir_path = f"{norm_path}/{dir_name}" if norm_path else dir_name
                                
                                # 既に追加済みのディレクトリはスキップ
                                if dir_path in seen_dirs:
                                    continue
                                    
                                seen_dirs.add(dir_path)
                                
                                # ディレクトリエントリを作成
                                dir_entry = EntryInfo(
                                    name=dir_name,
                                    path=dir_path,
                                    type=EntryType.DIRECTORY,
                                    size=0,
                                    modified_time=None
                                )
                                if dir_path not in seen_paths:
                                    seen_paths.add(dir_path)
                                    result.append(dir_entry)
                            else:
                                # 直下のファイル
                                if entry_path not in seen_paths:
                                    seen_paths.add(entry_path)
                                    result.append(entry)
                    
                    # 指定されたパスとエントリが完全に一致する場合
                    elif entry_path == norm_path:
                        if entry_path not in seen_paths:
                            seen_paths.add(entry_path)
                            result.append(entry)
            
            # 結果を返す
            if result:
                print(f"EnhancedArchiveManager: キャッシュから {len(result)} エントリを取得しました")
                return self._mark_archive_entries(result)
                
            print(f"EnhancedArchiveManager: キャッシュにマッチするエントリがありません。通常の方法で取得します")
        
        # キャッシュに存在しない場合は親クラスのメソッドを使用
        print(f"EnhancedArchiveManager: 親クラスのlist_entriesを使用します")
        try:
            entries = super().list_entries(path)
            
            # 得られた結果をキャッシュに追加
            if entries:
                print(f"EnhancedArchiveManager: 親クラスから取得した {len(entries)} エントリをキャッシュに追加します")
                self._all_entries[norm_path] = entries
                
            return entries
        except Exception as e:
            # エラーを適切な例外に変換
            if isinstance(e, (FileNotFoundError, PermissionError, ValueError)):
                # すでに適切な例外タイプならそのまま再raise
                raise
            else:
                # その他のエラーはI/O操作エラーとして扱う
                error_message = f"エントリリストの取得に失敗しました: {path} - {str(e)}"
                print(f"EnhancedArchiveManager: {error_message}")
                raise IOError(error_message) from e
    
    def _is_parent_dir(self, parent_path: str, child_path: str) -> bool:
        """
        parent_pathがchild_pathの親ディレクトリかどうかを判定
        
        Args:
            parent_path: 親ディレクトリパス
            child_path: 子パス
            
        Returns:
            親子関係であればTrue
        """
        # パスを正規化（末尾のスラッシュを削除）
        parent = parent_path.rstrip('/')
        child = child_path
        
        # 空の親パス（ルート）の場合は常にTrue
        if not parent:
            return True
        
        # 親パスで始まり、その後に'/'が続くか、完全一致する場合
        if child.startswith(parent + '/') or child == parent:
            return True
        
        return False

    def _get_child_path(self, parent_path: str, full_path: str) -> str:
        """
        親パスから見た子パスの相対部分を取得
        
        Args:
            parent_path: 親ディレクトリパス
            full_path: 完全なパス
            
        Returns:
            相対パス部分。親子関係でない場合は空文字
        """
        # パスを正規化
        parent = parent_path.rstrip('/')
        
        # 空の親パス（ルート）の場合はフルパスをそのまま返す
        if not parent:
            return full_path
        
        # 親パスで始まる場合は、その部分を取り除いて返す
        if full_path.startswith(parent + '/'):
            return full_path[len(parent) + 1:]  # '/'も含めて除去
        elif full_path == parent:
            return ''  # 完全一致の場合は空文字
            
        return ''  # 親子関係でない場合

    def _mark_archive_entries(self, entries: List[EntryInfo]) -> List[EntryInfo]:
        """エントリリストの中からファイル拡張子がアーカイブのものをアーカイブタイプとしてマーク"""
        if not entries:
            return []
            
        for entry in entries:
            if entry.type == EntryType.FILE and self._is_archive_by_extension(entry.name):
                entry.type = EntryType.ARCHIVE
        return entries
    
    def _join_paths(self, archive_path: str, internal_path: str) -> str:
        """アーカイブパスと内部パスを結合"""
        if not internal_path:
            return archive_path
        return f"{archive_path}/{internal_path}"
    
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
        
        # パスコンポーネントごとに分解
        parts = norm_path.split('/')
        
        # ドライブレターがある場合の特別処理 (例: Z:/)
        if len(parts) > 0 and ':' in parts[0]:
            # ネットワークドライブのパスはアーカイブパスとして扱わない
            return "", ""
        
        # パスを順に構築し、アーカイブファイルを検出
        test_path = ""
        for i, part in enumerate(parts):
            if i > 0:
                test_path += "/"
            test_path += part
            
            # 現在のパスが物理ファイルとして存在するか確認
            if os.path.isfile(test_path):
                # アーカイブファイルかどうか判定
                handler = super().get_handler(test_path)
                if handler and self._is_archive_by_extension(test_path):
                    # アーカイブファイル発見
                    # 残りのコンポーネントが内部パス
                    internal_path = '/'.join(parts[i+1:])
                    return test_path, internal_path
        
        # 物理ファイルが見つからなかった場合は、親アーカイブを探す
        if self.current_path and os.path.isfile(self.current_path):
            # current_path が設定されていて、それが物理ファイルの場合
            # このパスはcurrent_path内のパスとして扱う
            return self.current_path, path
                
        # アーカイブファイルが見つからなかった
        return "", ""
    
    def _find_handler_for_extension(self, ext: str) -> Optional[ArchiveHandler]:
        """
        拡張子に対応するハンドラを検索
        
        Args:
            ext: 拡張子
            
        Returns:
            対応するハンドラ。見つからない場合はNone
        """
        for handler in self.handlers:
            if ext in handler.supported_extensions:
                return handler
        return None
    
    def _fix_nested_entry_paths(self, entries: List[EntryInfo], base_path: str) -> None:
        """
        ネストされたエントリのパスを修正
        
        Args:
            entries: エントリリスト
            base_path: ベースパス
        """
        for entry in entries:
            entry.path = f"{base_path}/{entry.path}"
    
    def _fix_entry_paths(self, entries: List[EntryInfo], temp_path: str, base_path: str) -> None:
        """
        エントリのパスを修正
        
        Args:
            entries: エントリリスト
            temp_path: 一時ファイルパス
            base_path: ベースパス
        """
        for entry in entries:
            entry.path = entry.path.replace(temp_path, base_path)
    

    def _process_archive_for_all_entries(self, base_path: str, arc_entry: EntryInfo, preload_content: bool = True) -> List[EntryInfo]:
        """
        アーカイブエントリの内容を処理し、すべてのエントリを取得する
        
        Args:
            base_path: 基準となるパス
            arc_entry: 処理するアーカイブエントリ
            preload_content: ファイル内容を事前にキャッシュするかどうか
            
        Returns:
            アーカイブ内のすべてのエントリ
        """
        debug_mode = False
        # 循環参照防止とネスト深度チェック
        if self._current_nest_level >= self.MAX_NEST_DEPTH:
            print(f"EnhancedArchiveManager: 最大ネスト階層 ({self.MAX_NEST_DEPTH}) に達しました")
            return []
        
        # 再帰レベルを増加
        self._current_nest_level += 1
        
        try:
            archive_path = arc_entry.path
            print(f"EnhancedArchiveManager: アーカイブ処理: {archive_path}")

            # 1. 親書庫のタイプと場所を判別
            parent_archive_path = None
            parent_archive_bytes = None
            parent_archive_temp_path = None
            
            # 親書庫がルート書庫かネスト書庫かを判定
            parent_path, internal_path = self._analyze_path(archive_path)
            
            # ルート書庫の場合（1重ネスト）- 親は物理ファイル
            if parent_path and not internal_path:
                # ルート書庫のパスを絶対パス化
                parent_archive_path = parent_path
                if self.current_path and not os.path.isabs(parent_archive_path):
                    parent_archive_path = os.path.join(self.current_path, parent_archive_path).replace('\\', '/')
                
                print(f"EnhancedArchiveManager: 1重ネスト書庫 - 親書庫: {parent_archive_path}")
            
            # ネスト書庫の場合（2重ネスト以上）- 親は他のアーカイブ内のアーカイブ
            elif parent_path and internal_path:
                print(f"EnhancedArchiveManager: 2重以上のネスト書庫 - 親書庫: {parent_path}, 内部パス: {internal_path}")
                
                # 親書庫のエントリを探す
                parent_entry = None
                for entries_list in self._all_entries.values():
                    for entry in entries_list:
                        if entry.path == parent_path:
                            parent_entry = entry
                            break
                    if parent_entry:
                        break
                
                if parent_entry and parent_entry.cache is not None:
                    # 親がキャッシュされている場合
                    if isinstance(parent_entry.cache, bytes):
                        # バイトデータがキャッシュされている場合
                        parent_archive_bytes = parent_entry.cache
                        print(f"EnhancedArchiveManager: 親書庫のバイトデータをキャッシュから取得: {len(parent_archive_bytes)} バイト")
                    elif isinstance(parent_entry.cache, str) and os.path.exists(parent_entry.cache):
                        # 一時ファイルパスがキャッシュされている場合
                        parent_archive_temp_path = parent_entry.cache
                        print(f"EnhancedArchiveManager: 親書庫の一時ファイルパスをキャッシュから取得: {parent_archive_temp_path}")
                else:
                    # 親書庫が見つからないまたはキャッシュされていない場合、親から取得
                    parent_handler = self.get_handler(parent_path)
                    if parent_handler:
                        use_parent_path = parent_path
                        if parent_handler.use_absolute() and self.current_path:
                            if not os.path.isabs(parent_path):
                                use_parent_path = os.path.join(self.current_path, parent_path).replace('\\', '/')
                        
                        # 親書庫からネスト書庫のコンテンツを読み込む
                        print(f"EnhancedArchiveManager: 親書庫からネスト書庫のコンテンツを取得: {use_parent_path} -> {internal_path}")
                        parent_archive_bytes = parent_handler.read_archive_file(use_parent_path, internal_path)
                        
                        if not parent_archive_bytes:
                            print(f"EnhancedArchiveManager: 親書庫からネスト書庫のコンテンツ取得に失敗")
                            return []
                        
                        print(f"EnhancedArchiveManager: 親書庫からネスト書庫のコンテンツを取得成功: {len(parent_archive_bytes)} バイト")
            else:
                # 書庫としての情報が不明な場合
                print(f"EnhancedArchiveManager: 処理対象書庫のパス解析に失敗: {archive_path}")
                return []
            
            # 2. ネスト書庫のハンドラを取得
            handler = self.get_handler(archive_path)
            if not handler:
                print(f"EnhancedArchiveManager: 書庫のハンドラが見つかりません: {archive_path}")
                return []
            
            # 3. ネスト書庫のコンテンツを取得
            nested_archive_content = None  # ネスト書庫の実体(bytes)
            temp_file_path = None          # 一時ファイルパス（必要な場合）
            
            # 親書庫の種類に応じた処理
            if parent_archive_path:
                # ルート書庫からネスト書庫を取得
                print(f"EnhancedArchiveManager: ルート書庫からネスト書庫を取得: {parent_archive_path}")
                
                # 親がルート書庫の場合、read_archive_fileで内容を取得
                parent_handler = self.get_handler(parent_archive_path)
                if parent_handler:
                    # 内部パスは空または相対パス
                    inner_path = internal_path if internal_path else arc_entry.path
                    # 内部パスが絶対パスの場合は相対パスに変換
                    if inner_path.startswith(parent_archive_path + '/'):
                        inner_path = inner_path[len(parent_archive_path) + 1:]
                    
                    nested_archive_content = parent_handler.read_archive_file(parent_archive_path, inner_path)
                    print(f"EnhancedArchiveManager: ルート書庫から取得したネスト書庫: {len(nested_archive_content) if nested_archive_content else 0} バイト")
                else:
                    print(f"EnhancedArchiveManager: ルート書庫のハンドラが見つかりません: {parent_archive_path}")
                    return []
                    
            elif parent_archive_bytes:
                # 親のバイトデータから直接ネスト書庫を処理
                nested_archive_content = parent_archive_bytes
                print(f"EnhancedArchiveManager: 親のキャッシュからネスト書庫を取得: {len(nested_archive_content)} バイト")
                
            elif parent_archive_temp_path:
                # 親の一時ファイルからネスト書庫を読み込み
                print(f"EnhancedArchiveManager: 親の一時ファイルからネスト書庫を取得: {parent_archive_temp_path}")
                try:
                    with open(parent_archive_temp_path, 'rb') as f:
                        nested_archive_content = f.read()
                    print(f"EnhancedArchiveManager: 一時ファイルから読み込み成功: {len(nested_archive_content)} バイト")
                except Exception as e:
                    print(f"EnhancedArchiveManager: 一時ファイルからの読み込みに失敗: {e}")
                    return []
            
            # 4. ネスト書庫のコンテンツが取得できなかった場合
            if not nested_archive_content:
                print(f"EnhancedArchiveManager: ネスト書庫のコンテンツを取得できませんでした: {archive_path}")
                return []
            
            # 5. ネスト書庫のコンテンツの処理方法を決定
            # バイトデータからエントリリストを取得できるか確認
            can_process_bytes = handler.can_handle_bytes(nested_archive_content, archive_path)
            
            # キャッシュ処理 - 重要: ネスト書庫自身のコンテンツをキャッシュする
            # ※ この時点でarc_entryにネスト書庫自体のbytesデータをキャッシュ
            if can_process_bytes:
                # バイトデータを直接処理できる場合、バイトデータをキャッシュ
                print(f"EnhancedArchiveManager: ネスト書庫のバイトデータをキャッシュします ({len(nested_archive_content)} バイト)")
                arc_entry.cache = nested_archive_content
            else:
                # バイトデータを直接処理できない場合は一時ファイルを作成してパスをキャッシュ
                print(f"EnhancedArchiveManager: ネスト書庫の一時ファイルパスをキャッシュします")
                
                # 拡張子を取得
                _, ext = os.path.splitext(archive_path)
                if not ext:
                    ext = '.bin'  # デフォルト拡張子
                
                # 一時ファイルに書き込む
                try:
                    temp_file_path = handler.save_to_temp_file(nested_archive_content, ext)
                    if not temp_file_path:
                        print(f"EnhancedArchiveManager: 一時ファイル作成に失敗しました")
                        return []
                    
                    print(f"EnhancedArchiveManager: 一時ファイルを作成: {temp_file_path}")
                    # 一時ファイルパスをキャッシュ
                    arc_entry.cache = temp_file_path
                    self._temp_files.add(temp_file_path)  # 後でクリーンアップするためにリストに追加
                except Exception as e:
                    print(f"EnhancedArchiveManager: 一時ファイル処理中にエラー: {e}")
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.unlink(temp_file_path)
                            self._temp_files.discard(temp_file_path)
                        except:
                            pass
                    return []
            
            # 6. エントリリストを取得
            entries = None
            
            try:
                # バイトデータから直接エントリリストを取得
                if can_process_bytes:
                    entries = handler.list_all_entries_from_bytes(nested_archive_content)
                    print(f"EnhancedArchiveManager: バイトデータから {len(entries) if entries else 0} エントリを取得")
                # 一時ファイルからエントリリストを取得
                elif temp_file_path:
                    entries = handler.list_all_entries(temp_file_path)
                    print(f"EnhancedArchiveManager: 一時ファイルから {len(entries) if entries else 0} エントリを取得")
            except Exception as e:
                print(f"EnhancedArchiveManager: エントリリスト取得中にエラー: {e}")
                if debug_mode:
                    import traceback
                    traceback.print_exc()
            
            # エラーチェック
            if not entries:
                print(f"EnhancedArchiveManager: エントリが取得できませんでした")
                return []
                
            # 7. エントリリストの処理 - パスの修正のみ行い、個別のコンテンツキャッシュは行わない
            # アーカイブ内のパスを修正（アーカイブパス/エントリパス形式）
            result_entries = []
            for entry in entries:
                # パスを構築
                entry_path = f"{archive_path}/{entry.path}" if entry.path else archive_path
                
                # 新しいエントリを作成（cacheは設定しない）
                new_entry = EntryInfo(
                    name=entry.name,
                    path=entry_path,
                    type=entry.type,
                    size=entry.size,
                    modified_time=entry.modified_time,
                    created_time=entry.created_time,
                    is_hidden=entry.is_hidden,
                    name_in_arc=entry.name_in_arc,
                    attrs=entry.attrs,
                    cache=None  # 個別エントリにはキャッシュを設定しない
                )
                
                # エントリを結果に追加
                result_entries.append(new_entry)
            
            # 8. アーカイブエントリを識別して結果を返す
            marked_entries = self._mark_archive_entries(result_entries)
            
            # 9. キャッシュに保存
            self._all_entries[archive_path] = marked_entries
            
            return marked_entries
        
        except Exception as e:
            print(f"EnhancedArchiveManager: _process_archive_for_all_entries でエラー: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            # 再帰レベルを減少
            self._current_nest_level -= 1

    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定されたパスのファイルの内容を読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        # まずキャッシュ済みの全エントリから検索
        content = self._read_from_cached_entries(path)
        if content is not None:
            return content
        
        # ハンドラを取得
        handler = self.get_handler(path)
        if not handler:
            return None
        
        # ハンドラが絶対パスを使用する場合は、current_pathを基準にした絶対パスを渡す
        use_path = path
        if handler.use_absolute() and self.current_path:
            if not os.path.isabs(path):
                use_path = os.path.join(self.current_path, path).replace('\\', '/')
                print(f"EnhancedArchiveManager: 絶対パスを使用: {path} -> {use_path}")
        
        # キャッシュになければ通常の方法で読み込み
        return handler.read_file(use_path)
    
    def _read_from_cached_entries(self, path: str) -> Optional[bytes]:
        """
        キャッシュされたエントリからファイルを読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容。キャッシュに存在しない場合はNone
        """
        # パスを正規化
        norm_path = path.replace('\\', '/')
        
        # キャッシュされたエントリリストがあるかチェック
        if self._all_entries:
            print(f"EnhancedArchiveManager: キャッシュされた全エントリから検索します ({sum(len(entries) for entries in self._all_entries.values())} エントリ)")
            
            # すべてのキャッシュされたエントリに対して処理
            for cache_path, entries in self._all_entries.items():
                for entry in entries:
                    if entry.path == norm_path:
                        print(f"EnhancedArchiveManager: キャッシュからエントリを取得: {norm_path}")
                        
                        # キャッシュからデータを取得
                        if entry.cache is not None:
                            print(f"EnhancedArchiveManager: キャッシュからコンテンツを取得: {len(entry.cache)} バイト")
                            return entry.cache
                            
                        # キャッシュがない場合はアーカイブから読み込み
                        print(f"EnhancedArchiveManager: キャッシュされたコンテンツがありません。アーカイブから読み込みます")
                        
                        # 親アーカイブを見つけ、ファイルを読み込む
                        parent_archive_path, internal_path = self._analyze_path(entry.path)
                        if parent_archive_path:
                            parent_handler = self.get_handler(parent_archive_path)
                            if parent_handler:
                                # 絶対パスを使用
                                use_parent_path = parent_archive_path
                                if parent_handler.use_absolute() and self.current_path:
                                    if not os.path.isabs(parent_archive_path):
                                        use_parent_path = os.path.join(self.current_path, parent_archive_path).replace('\\', '/')
                                
                                content = parent_handler.read_archive_file(use_parent_path, internal_path)
                                if content:
                                    # 成功したらキャッシュに格納
                                    entry.cache = content
                                    return content
        
        return None

    def set_current_path(self, path: str) -> None:
        """
        現在のベースパスを設定する
        パス設定後は自動的にlist_all_entriesを呼び出して、
        全エントリリストを予め取得しておく
        
        Args:
            path: 設定するベースパス
        """
        # パスを正規化
        normalized_path = path.replace('\\', '/')
        self.current_path = normalized_path
        print(f"EnhancedArchiveManager: 現在のパスを設定: {normalized_path}")
        
        # まず最初にルートエントリをキャッシュに追加
        # これにより、アーカイブルート自体と、そのコンテンツへのアクセスを保証
        self._ensure_root_entry_in_cache(normalized_path)
        
        # その後、すべてのエントリリストを再帰的に取得
        try:
            print("EnhancedArchiveManager: 全エントリリストを取得中...")
            entries = self.list_all_entries(normalized_path, recursive=True)
            print(f"EnhancedArchiveManager: {len(entries)} エントリを取得しました")
        except Exception as e:
            print(f"EnhancedArchiveManager: 全エントリリスト取得中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
    
    def _ensure_root_entry_in_cache(self, path: str) -> None:
        """
        ルートエントリがキャッシュに含まれていることを確認し、
        なければ追加する
        
        Args:
            path: ルートエントリのパス
        """
        # パスがキャッシュに直接含まれているか確認
        if path in self._all_entries:
            print(f"EnhancedArchiveManager: ルートエントリはキャッシュに既に存在します: {path}")
            return
            
        # ルートエントリ情報を取得
        root_info = self.get_entry_info(path)
        if root_info:
            # ルート用のエントリリストを作成（ルートエントリ自身を含む）
            root_entries = [root_info]
            
            # キャッシュに追加
            print(f"EnhancedArchiveManager: ルートエントリをキャッシュに追加: {path}")
            self._all_entries[path] = root_entries
            
            # アーカイブの場合、アーカイブ内のルートディレクトリコンテンツを作成・追加
            if root_info.type == EntryType.ARCHIVE:
                # アーカイブ内のルートコンテンツを取得
                try:
                    # ハンドラを取得
                    handler = self.get_handler(path)
                    if handler:
                        # アーカイブ内のルートディレクトリパスを構築
                        archive_root = f"{path}/"
                        
                        # ハンドラから直接エントリリストを取得
                        direct_children = handler.list_entries(path)
                        if direct_children:
                            print(f"EnhancedArchiveManager: アーカイブのルートディレクトリをキャッシュに追加: {archive_root}")
                            # エントリをマークしてアーカイブを識別
                            direct_children = self._mark_archive_entries(direct_children)
                            self._all_entries[archive_root] = direct_children
                        else:
                            print(f"EnhancedArchiveManager: アーカイブからエントリを取得できませんでした: {path}")
                except Exception as e:
                    print(f"EnhancedArchiveManager: アーカイブのルートディレクトリ作成中にエラー: {e}")
                    import traceback
                    traceback.print_exc()

    def __del__(self):
        """デストラクタ - 一時ファイルのクリーンアップ"""
        for temp_file in self._temp_files:
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass

    def list_all_entries(self, path: str, recursive: bool = True) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるすべてのエントリを再帰的に取得する
        
        アーカイブ内のアーカイブ（ネストされたアーカイブ）も探索し、
        すべてのエントリを統合されたリストとして返します。
        結果はクラス変数に保存され、後で get_all_entries() で取得できます。
        
        Args:
            path: リストを取得するディレクトリやアーカイブのパス
            recursive: 再帰的に探索するかどうか（デフォルトはTrue）
            
        Returns:
            すべてのエントリ情報のリスト
        """
        # 探索済みエントリとプロセス済みパスをリセット
        self._all_entries = {}
        self._processed_paths = set()
        
        # パスを正規化
        path = path.replace('\\', '/')
        
        try:
            # 1. 最初にルートパス自身のエントリ情報を取得
            root_entry_info = self.get_entry_info(path)
            
            # 2. ハンドラを取得（ファイル種別に合わせて適切なハンドラ）
            handler = self.get_handler(path)
            if not handler:
                print(f"EnhancedArchiveManager: パス '{path}' のハンドラが見つかりません")
                # ルートエントリがあれば、それだけを返す
                if root_entry_info:
                    return [root_entry_info]
                return []
            
            print(f"EnhancedArchiveManager: '{handler.__class__.__name__}' を使用して再帰的にエントリを探索します")
            
            # 3. 最初のレベルのエントリリストを取得 (ここがRARハンドラなどを使用する部分)
            # ハンドラが絶対パスを要求する場合は絶対パスを構築
            use_path = path
            if handler.use_absolute() and self.current_path:
                if not os.path.isabs(path):
                    use_path = os.path.join(self.current_path, path).replace('\\', '/')
                    print(f"EnhancedArchiveManager: 絶対パスを使用: {path} -> {use_path}")
            
            # ハンドラの list_entries でルート直下のエントリを取得
            base_entries = handler.list_entries(use_path)
            if not base_entries:
                print(f"EnhancedArchiveManager: エントリが見つかりませんでした: {path}")
                # エントリが取得できなくても、ルートエントリ自体は返す
                if root_entry_info:
                    print(f"EnhancedArchiveManager: ルートエントリのみを返します")
                    return [root_entry_info]
                return []
            
            print(f"EnhancedArchiveManager: ベースレベルで {len(base_entries)} エントリを取得しました")
            
            # 4. エントリをアーカイブとして識別
            base_entries = self._mark_archive_entries(base_entries)
            
            # 5. 結果リストを構築（ルートエントリを先頭に）
            all_entries = []
            
            # ルートエントリが取得できた場合は、リストの最初に追加
            if root_entry_info:
                if root_entry_info.type == EntryType.FILE and self._is_archive_by_extension(root_entry_info.name):
                    root_entry_info.type = EntryType.ARCHIVE
                
                print(f"EnhancedArchiveManager: ルートエントリをリストに追加: {root_entry_info.path}")
                all_entries.append(root_entry_info)
            
            # ベースエントリを結果リストに追加
            all_entries.extend(base_entries)
            
            # 6. キャッシュに保存（これによりlist_entriesから参照可能に）
            self._all_entries[path] = base_entries.copy()
            
            # 7. アーカイブエントリを再帰的に処理
            if recursive:
                processed_archives = set()  # 処理済みアーカイブの追跡
                archive_queue = []  # 処理するアーカイブのキュー
                
                # 最初のレベルでアーカイブを検索
                for entry in base_entries:
                    if entry.type == EntryType.ARCHIVE:
                        archive_queue.append(entry)
                
                print(f"EnhancedArchiveManager: {len(archive_queue)} 個のネスト書庫を検出")
                
                # アーカイブを処理
                while archive_queue:
                    arc_entry = archive_queue.pop(0)
                    
                    # 既に処理済みならスキップ
                    if arc_entry.path in processed_archives:
                        continue
                    
                    # 処理済みとしてマーク
                    processed_archives.add(arc_entry.path)
                    
                    # アーカイブの内容を処理（さらに下のレベルへ）
                    nested_entries = self._process_archive_for_all_entries(path, arc_entry)
                    
                    if nested_entries:
                        # 結果を追加
                        all_entries.extend(nested_entries)
                        
                        # さらにネストされたアーカイブがあれば追加
                        for nested_entry in nested_entries:
                            if nested_entry.type == EntryType.ARCHIVE and nested_entry.path not in processed_archives:
                                archive_queue.append(nested_entry)
            
            return all_entries
                
        except Exception as e:
            print(f"EnhancedArchiveManager.list_all_entries エラー: {e}")
            import traceback
            traceback.print_exc()
            # エラーが発生しても、ルートエントリが取得できていれば返す
            if 'root_entry_info' in locals() and root_entry_info:
                return [root_entry_info]
            return []


def get_archive_manager() -> ArchiveManager:
    """
    アプリケーション全体で共有するアーカイブマネージャーのシングルトンインスタンスを取得する
    
    Returns:
        設定済みのアーカイブマネージャー
    """
    global _instance
    
    if (_instance is None):
        _instance = create_archive_manager()
    
    return _instance


def create_archive_manager() -> ArchiveManager:
    """
    新しいアーカイブマネージャーのインスタンスを作成する
    
    Returns:
        設定済みの新しいアーカイブマネージャー
    """
    # 強化版のマネージャーを使用
    manager = EnhancedArchiveManager()
    try:
        register_standard_handlers(manager)
    except Exception as e:
        print(f"ハンドラの登録中にエラーが発生しました: {e}")
    return manager


def reset_manager() -> None:
    """
    シングルトンのアーカイブマネージャーをリセットする（主にテスト用）
    """
    global _instance
    _instance = None


# 以下はアプリケーション層向けの統一インターフェース
# アプリ層はArcManagerクラスを直接使わず、以下の関数を通して操作する

def list_entries(path: str) -> List[EntryInfo]:
    """
    指定されたパスの配下にあるエントリのリストを取得する
    
    Args:
        path: リストを取得するディレクトリのパス
            
    Returns:
        エントリ情報のリスト。失敗した場合は空リスト
    """
    return get_archive_manager().list_entries(path)


def get_entry_info(path: str) -> Optional[EntryInfo]:
    """
    指定されたパスのエントリ情報を取得する
    
    Args:
        path: 情報を取得するエントリのパス
            
    Returns:
        エントリ情報。存在しない場合はNone
    """
    return get_archive_manager().get_entry_info(path)


def read_file(path: str) -> Optional[bytes]:
    """
    指定されたパスのファイルの内容を読み込む
    
    Args:
        path: 読み込むファイルのパス
            
    Returns:
        ファイルの内容。読み込みに失敗した場合はNone
    """
    return get_archive_manager().read_file(path)


def read_archive_file(archive_path: str, file_path: str) -> Optional[bytes]:
    """
    アーカイブファイル内のファイルの内容を読み込む
    
    Args:
        archive_path: アーカイブファイルのパス
        file_path: アーカイブ内のファイルパス
            
    Returns:
        ファイルの内容。読み込みに失敗した場合はNone
    """
    # アーカイブファイルを処理するハンドラを取得
    handler = get_archive_manager().get_handler(archive_path)
    if handler is None:
        print(f"ArchiveManager: アーカイブ {archive_path} に対応するハンドラが見つかりません")
        return None
        
    # アーカイブ内のファイルを読み込む前に、EntryInfoを取得してname_in_arcをチェック
    full_path = f"{archive_path}/{file_path}"
    entry_info = get_archive_manager().get_entry_info(full_path)
    
    # name_in_arcが設定されている場合
    if entry_info and entry_info.name_in_arc:
        # name_in_arcが完全パスか、単なるファイル名かを判断
        if '/' in entry_info.name_in_arc:
            # name_in_arcが完全パス - そのまま使用
            corrected_path = entry_info.name_in_arc
        else:
            # name_in_arcがファイル名のみ - ディレクトリ部分を追加
            dir_path = os.path.dirname(file_path)
            if (dir_path):
                dir_path += '/'
            corrected_path = dir_path + entry_info.name_in_arc
            
        # パスが異なる場合のみログを出力
        if corrected_path != file_path:
            print(f"ArchiveManager: name_in_arcを使用: {file_path} -> {corrected_path}")
            file_path = corrected_path
    
    # 通常のファイル読み込み
    print(f"ArchiveManager: {handler.__class__.__name__} でアーカイブファイル読み込み: {archive_path}/{file_path}")
    return handler.read_archive_file(archive_path, file_path)


def get_stream(path: str) -> Optional[BinaryIO]:
    """
    指定されたパスのファイルのストリームを取得する
    
    Args:
        path: ストリームを取得するファイルのパス
            
    Returns:
        ファイルストリーム。取得できない場合はNone
    """
    return get_archive_manager().get_stream(path)


def is_archive(path: str) -> bool:
    """
    指定されたパスがアーカイブファイルかどうかを判定する
    
    Args:
        path: 判定するパス
            
    Returns:
        アーカイブファイルならTrue、そうでなければFalse
    """
    return get_archive_manager().is_archive(path)


def is_directory(path: str) -> bool:
    """
    指定されたパスがディレクトリかどうかを判定する
    
    Args:
        path: 判定するパス
            
    Returns:
        ディレクトリの場合はTrue、それ以外の場合はFalse
    """
    return get_archive_manager().is_directory(path)


def get_parent_path(path: str) -> str:
    """
    親ディレクトリのパスを取得する
    
    Args:
        path: 対象のパス
            
    Returns:
        親ディレクトリのパス
    """
    return get_archive_manager().get_parent_path(path)
