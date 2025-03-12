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
        self.current_path: str = ""
    
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
            handler = self._handler_cache[norm_path]
            # ハンドラのcurrent_pathを更新
            if self.current_path:
                handler.set_current_path(self.current_path)
            print(f"Handler found in cache: {handler.__class__.__name__}")
            return handler
        
        print(f"Getting handler for path: {norm_path}")
        
        # 各ハンドラでチェック
        for handler in self.handlers.__reversed__():
            # ハンドラにcurrent_pathを設定
            if self.current_path:
                handler.set_current_path(self.current_path)
            print(f"checking: {handler.__class__.__name__}")
            
            try:
                if handler.can_handle(norm_path):
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
        # 現在のcurrent_pathを設定
        if self.current_path:
            handler.set_current_path(self.current_path)
    
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
        
        return handler.list_entries(path)
    
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
        
        return handler.get_entry_info(path)
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定されたパスのファイルの内容を読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        # 抽象メソッド - サブクラスで実装する必要がある
        raise NotImplementedError("サブクラスで実装する必要があります")
    
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
        
        return handler.get_stream(path)
    
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
        
        return handler.is_directory(path)
    
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
        
        return handler.get_parent_path(path)
        
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
        
        return handler.read_archive_file(archive_path, file_path)

    def set_current_path(self, path: str) -> None:
        """
        現在のベースパスを設定する
        
        Args:
            path: 設定するベースパス
        """
        # パスを正規化
        self.current_path = path.replace('\\', '/')
        
        # 全ハンドラーにcurrent_pathを設定
        for handler in self.handlers:
            handler.set_current_path(self.current_path)


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
        
        # FileSystemHandlerにアーカイブ拡張子を設定
        for handler in self.handlers:
            if handler.__class__.__name__ == 'FileSystemHandler':
                if hasattr(handler, 'set_archive_extensions'):
                    handler.set_archive_extensions(self._archive_extensions)
                    break
    
    def _is_archive_by_extension(self, path: str) -> bool:
        """パスがアーカイブの拡張子を持つかどうかを判定する"""
        if not self._archive_extensions:
            self._update_archive_extensions()
            
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
        if norm_path in self._handler_cache:
            handler = self._handler_cache[norm_path]
            # ハンドラのcurrent_pathを更新
            if self.current_path:
                handler.set_current_path(self.current_path)
            print(f"Handler found in cache: {handler.__class__.__name__}")
            return handler
        
        print(f"Getting handler for path: {norm_path}")
        
        # アーカイブのアクセスパターンを検出（末尾がスラッシュで終わるアーカイブパス）
        if norm_path.endswith('/'):
            # アーカイブ内部アクセス - アーカイブ名を抽出
            base_path = norm_path.rstrip('/')
            
            # アーカイブファイルが存在するか確認
            if os.path.isfile(base_path):
                # ファイル拡張子を確認
                _, ext = os.path.splitext(base_path.lower())
                
                # アーカイブハンドラを探す
                for handler in self.handlers.__reversed__():
                    # ハンドラにcurrent_pathを設定
                    if self.current_path:
                        handler.set_current_path(self.current_path)
                    
                    if ext in handler.supported_extensions and handler.can_handle(base_path):
                        # キャッシュに追加
                        self._handler_cache[norm_path] = handler
                        print(f"Archive directory handler found: {handler.__class__.__name__}")
                        return handler
        
        # 通常のパス処理も逆順にハンドラを検索する
        for handler in self.handlers.__reversed__():
            # ハンドラにcurrent_pathを設定
            if self.current_path:
                handler.set_current_path(self.current_path)
            print(f"checking: {handler.__class__.__name__}")
            
            try:
                if handler.can_handle(norm_path):
                    # このハンドラで処理可能
                    self._handler_cache[norm_path] = handler
                    print(f"Handler matched: {handler.__class__.__name__}")
                    return handler
            except Exception as e:
                print(f"Handler error ({handler.__class__.__name__}): {e}")
        
        # 該当するハンドラが見つからない
        print(f"No handler found for: {norm_path}")
        return None
    
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
        # パスの正規化（先頭のスラッシュを削除）
        if path.startswith('/'):
            path = path[1:]
            print(f"EnhancedArchiveManager: 先頭のスラッシュを削除しました: {path}")
        
        # パスを正規化
        norm_path = path.replace('\\', '/')
        print(f"EnhancedArchiveManager: パス '{norm_path}' のエントリを取得")
        
        # 空のパスはルート階層を表す
        is_root = not norm_path
        
        # キャッシュされたエントリリストを検索
        if self._all_entries:
            print(f"EnhancedArchiveManager: キャッシュされた全エントリから検索します ({sum(len(entries) for entries in self._all_entries.values())} エントリ)")
            
            # 末尾のスラッシュを正規化したパス
            norm_path_without_slash = norm_path.rstrip('/')
                       
            # 1. 直接対象のファイルを全キャッシュから検索する
            # ファイル自体を取得しようとしている場合（ディレクトリの中身ではなく）
            found_entry = None
            for cache_entries in self._all_entries.values():
                for entry in cache_entries:
                    # パスの完全一致を確認
                    if entry.rel_path.rstrip('/') == norm_path_without_slash:
                        print(f"EnhancedArchiveManager: 完全一致するファイルエントリを発見: {entry.path}")
                        if entry.type == EntryType.FILE:
                            if norm_path.endswith('/'):
                                print(f"EnhancedArchiveManager: 指定されたパスはファイルだが末尾にスラッシュがついています: {norm_path}")
                                raise ValueError(f"指定されたパス '{path}' はファイルですが、末尾にスラッシュがついています")
                        found_entry = entry
                        break
                if found_entry:
                    break
            
            # ファイルエントリが見つかった場合は、そのファイルを含むリストを返す
            if found_entry and found_entry.type == EntryType.FILE:
                print(f"EnhancedArchiveManager: ファイルエントリを返します: {found_entry.path}")
                return [found_entry]
            
            # 2. キャッシュエントリの検索
            # 通常のディレクトリとしての検索
            if norm_path in self._all_entries:
                print(f"EnhancedArchiveManager: 完全一致するキャッシュエントリを発見: {norm_path}")
                return self._all_entries[norm_path]
            elif norm_path_without_slash in self._all_entries:
                print(f"EnhancedArchiveManager: スラッシュなしで一致するキャッシュエントリを発見: {norm_path_without_slash}")
                return self._all_entries[norm_path_without_slash]
            elif is_root and self.current_path and self.current_path in self._all_entries:
                print(f"EnhancedArchiveManager: ルート要求に対してcurrent_path直下のエントリを返します: {self.current_path}")
                
                # アーカイブのルート（または任意のルート）の場合
                # rel_pathを使って直接の子エントリのみをフィルタリング
                result = []
                seen_paths = set()  # 重複回避用
                
                # すべてのキャッシュされたエントリから直接の子エントリを検索
                for entries_list in self._all_entries.values():
                    for entry in entries_list:
                        rel_path = entry.rel_path.rstrip('/')
                        
                        # ルートディレクトリの直接の子エントリかチェック
                        # (直接の子は、スラッシュを含まないか、最初のスラッシュ以降にスラッシュがない)
                        if rel_path and '/' not in rel_path:
                            # 直接の子エントリの場合
                            if entry.path not in seen_paths:
                                result.append(entry)
                                seen_paths.add(entry.path)
                                print(f"  発見: {entry.name} ({entry.path})")
                
                if result:
                    print(f"EnhancedArchiveManager: ルートから {len(result)} 直接の子エントリを取得しました")
                    return result
                
                # 直接の子がない場合（通常ありえない）、元の処理を実行
                print(f"EnhancedArchiveManager: 直接の子エントリが見つからないため、すべてのエントリを返します")
                return self._all_entries[self.current_path]
            
            # 3. キャッシュから直接の子エントリを抽出
            result = []
            seen_paths = set()  # 重複回避用
            
            # 検索パスの準備（末尾のスラッシュ有無両方の形式）
            search_path = norm_path
            search_path_with_slash = norm_path if norm_path.endswith('/') else norm_path + '/'
            search_path_without_slash = norm_path_without_slash
            
            print(f"EnhancedArchiveManager: 検索パス {search_path} の直接の子エントリを検索")
            
            # すべてのキャッシュされたエントリから直接の子エントリを検索
            for cache_path, entries in self._all_entries.items():
                for entry in entries:
                    # エントリの相対パスを取得して判定
                    entry_path = entry.path.rstrip('/')
                    entry_rel_path = entry.rel_path.rstrip('/') if entry.rel_path else entry_path
                    
                    # 検索パス自体と同じエントリは除外
                    if entry_path == norm_path_without_slash or entry_rel_path == norm_path_without_slash:
                        continue
                    
                    is_direct_child = False
                    
                    if is_root:
                        # ルート検索時は最上位レベルのエントリを返す
                        # rel_pathが空またはスラッシュを含まない場合は直接の子
                        is_direct_child = not entry_rel_path or '/' not in entry_rel_path
                        
                        # ルートがアーカイブファイルの場合の特別処理
                        if self.current_path and os.path.isfile(self.current_path) and self._is_archive_by_extension(self.current_path):
                            # アーカイブのルートディレクトリ内のトップレベルエントリのみを対象とする
                            archive_root_prefix = f"{self.current_path}/"
                            
                            # アーカイブルート内のエントリかチェック
                            if entry_path.startswith(archive_root_prefix):
                                # アーカイブルートからの相対パスを抽出
                                rel_to_archive_root = entry_path[len(archive_root_prefix):]
                                # トップレベルのエントリのみを対象とする
                                is_direct_child = '/' not in rel_to_archive_root
                            else:
                                # アーカイブルート外のエントリは対象外
                                is_direct_child = False
                    else:
                        # それ以外の場合は検索パスの直接の子か確認
                        # 両方のパターン（スラッシュあり/なし）をチェック
                        if entry_rel_path.startswith(search_path_with_slash):
                            # search_path_with_slash で始まり、それ以降にスラッシュがない
                            remaining = entry_rel_path[len(search_path_with_slash):]
                            is_direct_child = '/' not in remaining
                        elif entry_rel_path.startswith(search_path_without_slash + '/'):
                            # search_path_without_slash/ で始まり、それ以降にスラッシュがない
                            remaining = entry_rel_path[len(search_path_without_slash) + 1:]
                            is_direct_child = '/' not in remaining
                    
                    # 直接の子エントリかつ未追加の場合は結果に追加
                    if is_direct_child and entry.path not in seen_paths:
                        result.append(entry)
                        seen_paths.add(entry.path)
                        print(f"  発見: {entry.name} ({entry.path})")
            
            # 結果を返す
            if result:
                print(f"EnhancedArchiveManager: キャッシュから {len(result)} エントリを取得しました")
                return result
            
            # キャッシュに存在しない場合、このパスは無効である可能性が高い
            print(f"EnhancedArchiveManager: キャッシュにマッチするエントリがありません。パス '{path}' は無効かアクセス不能です。")
            raise FileNotFoundError(f"指定されたパス '{path}' にエントリが見つかりません")
            
        # キャッシュが空（初回アクセスなど）の場合は例外
        raise FileNotFoundError(f"エントリキャッシュが初期化されていません。set_current_pathを先に呼び出してください。")
    
    def _is_direct_child(self, parent_path: str, child_path: str) -> bool:
        """
        child_pathがparent_pathの直下の子かどうか判定
        
        Args:
            parent_path: 親ディレクトリパス
            child_path: 子エントリパス
            
        Returns:
            直下の子エントリならTrue、そうでなければFalse
        """
        # パスを正規化
        parent = parent_path.rstrip('/')
        child = child_path.rstrip('/')
        
        # 空の親パス（ルート）の場合は特別処理
        if not parent:
            # ルートの直下の子かどうかを判定（スラッシュが1つだけ）
            return child.count('/') == 0
        
        # 親パスで始まるか確認
        if not child.startswith(parent):
            return False
            
        # 親の後に'/'があるか確認（親と子が同一の場合を除外）
        if len(child) <= len(parent):
            return False
            
        if child[len(parent)] != '/':
            return False
            
        # 親の後の部分でスラッシュが1つだけかを確認
        remaining = child[len(parent) + 1:]
        return '/' not in remaining

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
        
        パスを末尾からファイル自体を除き、段階的に削りながらハンドラを検索し、
        can_archive()がTrueのハンドラが処理できるパスをアーカイブパス、
        元のパスのそれ以降の部分を内部パスとして返す
        
        Args:
            path: 分割するパス
            
        Returns:
            (アーカイブファイルのパス, 内部パス) のタプル
        """
        # 正規化したパス
        norm_path = path.replace('\\', '/')
        print(f"EnhancedArchiveManager: パスを解析: {norm_path}")
        
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
            if not os.path.isabs(test_path) and self.current_path:
                abs_test_path = os.path.join(self.current_path, test_path).replace('\\', '/')
            
            # ハンドラを取得
            handler = self.get_handler(abs_test_path)
            
            # ハンドラがcan_archive()を実装し、かつTrueを返すかチェック
            if handler and handler.can_archive():
                # アーカイブハンドラが見つかった場合
                print(f"EnhancedArchiveManager: アーカイブパス特定: {abs_test_path}, 内部パス: {remaining}")
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
        if self.current_path and os.path.isfile(self.current_path) and self._is_archive_by_extension(self.current_path):
            # ルートがアーカイブファイルの場合、current_pathをアーカイブパスとして、
            # 元のパス全体を内部パスとして返す
            print(f"EnhancedArchiveManager: ルートアーカイブを使用: {self.current_path}, 内部パス: {norm_path}")
            return self.current_path, norm_path
        
        # ルートもアーカイブでない場合は空のアーカイブパスと残りの全部を返す
        print(f"EnhancedArchiveManager: アーカイブパスが特定できませんでした: {norm_path}")
        return "", remaining
    
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
        debug_mode = True  # デバッグモードを有効化
        # 循環参照防止とネスト深度チェック
        if self._current_nest_level >= self.MAX_NEST_DEPTH:
            print(f"EnhancedArchiveManager: 最大ネスト階層 ({self.MAX_NEST_DEPTH}) に達しました")
            return []
        
        # 再帰レベルを増加
        self._current_nest_level += 1
        
        try:
            archive_path = arc_entry.path
            print(f"EnhancedArchiveManager: アーカイブ処理: {archive_path}")
            print(f"EnhancedArchiveManager: アーカイブエントリ ({arc_entry.path} )")

            # 書庫エントリの種別を確実にARCHIVEに設定
            # これが重要です - 物理ファイルであれ何であれ、この時点で処理されるエントリは書庫なので
            if arc_entry.type != EntryType.ARCHIVE:
                print(f"EnhancedArchiveManager: エントリタイプをARCHIVEに修正: {arc_entry.path}")
                arc_entry.type = EntryType.ARCHIVE

            # 処理対象が物理ファイルであれば、適切な処理を行う
            if os.path.isfile(archive_path):
                print(f"EnhancedArchiveManager: 物理ファイルを処理: {archive_path}")
                handler = self.get_handler(archive_path)
                if handler:
                    try:
                        # アーカイブ内のすべてのエントリ情報を取得するには list_all_entries を使用
                        entries = handler.list_all_entries(archive_path)
                        if entries:
                            # 結果を返す前にEntryTypeをマーク
                            marked_entries = self._mark_archive_entries(entries)
                            print(f"EnhancedArchiveManager: 物理アーカイブから {len(marked_entries)} エントリを取得")
                            return marked_entries
                        else:
                            print(f"EnhancedArchiveManager: ハンドラはエントリを返しませんでした: {handler.__class__.__name__}")
                    except Exception as e:
                        print(f"EnhancedArchiveManager: ハンドラの呼び出しでエラー: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"EnhancedArchiveManager: ファイルを処理するハンドラが見つかりません: {archive_path}")
                
                # エラーまたは結果が空の場合は空リストを返す
                return []

            # 1. 親書庫のタイプと場所を判別
            parent_archive_path = None
            parent_archive_bytes = None
            parent_archive_temp_path = None
            
            # パスを詳細に分析して親書庫と内部パスを特定
            parent_path, internal_path = self._analyze_path(archive_path)
            
            # パスを詳細に分析して親書庫と内部パスを特定
            if parent_path:
                parent_archive_path = parent_path
                print(f"EnhancedArchiveManager: 親書庫を検出: {parent_archive_path}, 内部パス: {internal_path}")
            else:
                print(f"EnhancedArchiveManager: 親書庫が見つかりません: {archive_path}")
                return []
            
            # 絶対パスの確保
            if parent_archive_path and self.current_path and not os.path.isabs(parent_archive_path):
                abs_path = os.path.join(self.current_path, parent_archive_path).replace('\\', '/')
                print(f"EnhancedArchiveManager: 相対パスを絶対パスに変換: {parent_archive_path} -> {abs_path}")
                parent_archive_path = abs_path
            
            # 2. 親書庫のハンドラを取得
            parent_handler = self.get_handler(parent_archive_path)
            if not parent_handler:
                print(f"EnhancedArchiveManager: 親書庫のハンドラが見つかりません: {parent_archive_path}")
                return []
            
            # 3. ネスト書庫のコンテンツを取得
            print(f"EnhancedArchiveManager: 親書庫からネスト書庫のコンテンツを取得: {parent_archive_path} -> {internal_path}")
            nested_archive_content = parent_handler.read_archive_file(parent_archive_path, internal_path)
            
            if not nested_archive_content:
                print(f"EnhancedArchiveManager: 親書庫からネスト書庫のコンテンツ取得に失敗")
                return []
            
            print(f"EnhancedArchiveManager: 親書庫からネスト書庫のコンテンツを取得成功: {len(nested_archive_content)} バイト")

            # 4. ネスト書庫のハンドラを取得
            handler = self.get_handler(archive_path)
            if not handler:
                print(f"EnhancedArchiveManager: 書庫のハンドラが見つかりません: {archive_path}")
                return []
            
            # 5. ネスト書庫のコンテンツの処理方法を決定
            # バイトデータからエントリリストを取得できるか確認
            can_process_bytes = handler.can_handle_bytes(nested_archive_content, archive_path)

            # 現在のエントリにcacheプロパティがあるか確認
            if not hasattr(arc_entry, 'cache'):
                print(f"EnhancedArchiveManager: エントリにcacheプロパティがありません。作成します。")
                arc_entry.cache = None

            # キャッシュ処理 - 重要: ネスト書庫自身のコンテンツをキャッシュする
            if can_process_bytes:
                # バイトデータを直接処理できる場合、バイトデータをキャッシュ
                print(f"EnhancedArchiveManager: ネスト書庫のバイトデータをキャッシュします ({len(nested_archive_content)} バイト)")
                arc_entry.cache = nested_archive_content
                print(f"EnhancedArchiveManager: ネスト書庫のバイトデータをキャッシュしました ({arc_entry.path} )")
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
                
            # 7. エントリリストの処理 - パスの修正のみを行う（プリロードは行わない）
            result_entries = []
            
            for entry in entries:
                # パスを構築
                entry_path = f"{archive_path}/{entry.path}" if entry.path else archive_path
                
                # 新しいエントリを作成
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
                    cache=None  # キャッシュは設定しない
                )
                
                # エントリを結果に追加
                result_entries.append(new_entry)
            
            # 8. アーカイブエントリを識別して結果を返す
            marked_entries = self._mark_archive_entries(result_entries)
            
            # 9. キャッシュに保存
            self._all_entries[archive_path] = marked_entries
            
            # キャッシュ状態のデバッグ情報
            if debug_mode:
                print(f"EnhancedArchiveManager: キャッシュ状況:")
                print(f"  書庫キャッシュ: arc_entry.cache {'あり' if arc_entry.cache is not None else 'なし'}")
                print(f"  キャッシュされたエントリパス例: {[e.path for e in marked_entries[:3]]}")
            
            return marked_entries
        
        except Exception as e:
            print(f"EnhancedArchiveManager: _process_archive_for_all_entries でエラー: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            # 再帰レベルを減少
            self._current_nest_level -= 1

    def _get_handler_type(self, path: str) -> Optional[str]:
        """
        指定されたパスを処理できるハンドラの型名を取得する
        
        Args:
            path: 処理対象のパス
            
        Returns:
            ハンドラの型名。対応するものがなければNone
        """
        handler = self.get_handler(path)
        if handler:
            return handler.__class__.__name__
        return None

    def _find_archive_handler(self, path: str) -> Optional[ArchiveHandler]:
        """
        指定されたアーカイブに対応する専用のハンドラを探す
        
        Args:
            path: アーカイブファイルのパス
            
        Returns:
            アーカイブ対応のハンドラ。見つからなければNone
        """
        # ファイル拡張子を取得
        _, ext = os.path.splitext(path.lower())
        
        # 拡張子に対応するハンドラを探す
        for handler in self.handlers:
            if ext in handler.supported_extensions and handler.__class__.__name__ != 'FileSystemHandler':
                handler.set_current_path(self.current_path)
                return handler
        
        return None

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
            print(f"EnhancedArchiveManager: 先頭のスラッシュを削除しました: {path}")
        
        # パスからアーカイブと内部パス、キャッシュされたバイトデータを導き出す
        print(f"EnhancedArchiveManager: アーカイブパス解析: {path}")
        result = self._resolve_file_source(path)
        archive_path, internal_path, cached_bytes = result
        print(f"EnhancedArchiveManager: ファイル読み込み: {path} -> {archive_path} -> {internal_path}")         
        # アーカイブパスと内部パスがある場合
        if archive_path and internal_path:
            print(f"EnhancedArchiveManager: アーカイブ内のファイルを読み込み: {archive_path} -> {internal_path}")
            handler = self.get_handler(archive_path)
            if (handler):
                # キャッシュされたバイトデータがある場合は、read_file_from_bytesを使用
                if cached_bytes is not None:
                    print(f"EnhancedArchiveManager: キャッシュされた書庫データから内部ファイルを抽出: {internal_path}")
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
        # (内部パスがない場合やハンドラがread_file_from_bytesをサポートしていない場合)
        if cached_bytes is not None:
            print(f"EnhancedArchiveManager: キャッシュからファイルを読み込み: {path}")
            return cached_bytes
        
        # 該当するファイルが見つからない場合はエラー
        raise FileNotFoundError(f"指定されたファイルは存在しません: {path}")

    def _resolve_file_source(self, path: str) -> Tuple[str, str, Optional[bytes]]:
        """
        パスからアーカイブパス、内部パス、キャッシュされたバイトデータを導き出す
        
        Args:
            path: 処理対象のパス
            
        Returns:
            (アーカイブパス, 内部パス, キャッシュされたバイト) のタプル
            - アーカイブが見つからない場合は ("", "", None)
            - バイトデータが直接キャッシュされている場合は (仮想パス, internal_path, bytes)
            - 一時ファイルでキャッシュされている場合は (cache_path, internal_path, None)
            - 通常のアーカイブ内ファイルの場合は (archive_path, internal_path, None)
        """
        # パスを正規化
        norm_path = path.replace('\\', '/')
        print(f"EnhancedArchiveManager: ファイルソース解決: {norm_path}")
        
        # 1. まずエントリキャッシュから完全一致するエントリを検索
        entry_found = False
        entry_info = None
        for cache_path, entries in self._all_entries.items():
            for entry in entries:
                if entry.rel_path.rstrip('/') == norm_path.rstrip('/'):
                    print(f"EnhancedArchiveManager: キャッシュされたエントリを発見: {entry.path}")
                    entry_found = True
                    entry_info = entry
                    break
            if entry_found:
                break
        
        # エントリが見つからない場合は早期リターン
        if not entry_found:
            print(f"EnhancedArchiveManager: 指定されたパス {norm_path} に対応するエントリが見つかりません")
            return "", "", None
        
        # 2. パスコンポーネントを解析してアーカイブを特定
        archive_path = ""
        internal_path = entry_info.name_in_arc  # name_in_arcは必ず存在する前提
        print(f"EnhancedArchiveManager: name_in_arcを内部パスとして使用: {internal_path}")
        
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
            # アーカイブかどうか確認
            is_archive = False
            test_entry_info = self.get_entry_info(test_path)
            if test_entry_info and test_entry_info.type == EntryType.ARCHIVE:
                is_archive = True
            elif os.path.isfile(test_path):
                _, ext = os.path.splitext(test_path.lower())
                if ext in self._archive_extensions:
                    is_archive = True
            
            if is_archive:
                archive_path = test_path
                print(f"EnhancedArchiveManager: アーカイブ {archive_path} を特定")
                
                # アーカイブエントリがキャッシュを持っているか確認
                if test_entry_info and hasattr(test_entry_info, 'cache') and test_entry_info.cache is not None:
                    cache = test_entry_info.cache
                    if isinstance(cache, bytes):
                        print(f"EnhancedArchiveManager: アーカイブエントリからキャッシュされたバイトデータを返します: {len(cache)} バイト")
                        return test_entry_info.path, internal_path, cache
                    elif isinstance(cache, str) and os.path.exists(cache):
                        print(f"EnhancedArchiveManager: アーカイブエントリからキャッシュされた一時ファイルを返します: {cache}")
                        return cache, internal_path, None
                
                break
            
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
        
        # アーカイブパスが特定できた場合
        if archive_path:
            # 相対パスを絶対パスに変換
            if not os.path.isabs(archive_path) and self.current_path:
                archive_path = os.path.join(self.current_path, archive_path).replace('\\', '/')
                print(f"EnhancedArchiveManager: アーカイブパスを絶対パスに変換: {archive_path}")
            
            return archive_path, internal_path, None
        
        # ここに到達する場合、アーカイブパス候補がなかった
        # 最終手段として、ルートがアーカイブファイルかどうかをチェック
        if self.current_path and os.path.isfile(self.current_path) and self._is_archive_by_extension(self.current_path):
            print(f"EnhancedArchiveManager: ルートアーカイブを使用: {self.current_path}")
            archive_path = self.current_path
            
            # キャッシュされたアーカイブエントリを探す
            arc_entry = self._find_archive_entry_in_cache(archive_path)
            if arc_entry and hasattr(arc_entry, 'cache') and arc_entry.cache is not None:
                cache = arc_entry.cache
                if isinstance(cache, bytes):
                    print(f"EnhancedArchiveManager: アーカイブのバイトデータキャッシュを返します")
                    return arc_entry.path, internal_path, cache
                elif isinstance(cache, str) and os.path.exists(cache):
                    print(f"EnhancedArchiveManager: アーカイブの一時ファイルパスを返します: {cache}")
                    return cache, internal_path, None
            
            print(f"EnhancedArchiveManager: アーカイブ内ファイルアクセス: {archive_path} -> {internal_path}")
            return archive_path, internal_path, None
        
        print(f"EnhancedArchiveManager: アーカイブパスの特定に失敗しました")
        return "", "", None

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
                        if hasattr(entry, 'cache') and entry.cache is not None:
                            # キャッシュの種類をチェック
                            if isinstance(entry.cache, bytes):
                                print(f"EnhancedArchiveManager: キャッシュからバイトデータコンテンツを取得: {len(entry.cache)} バイト")
                                return entry.cache
                            elif isinstance(entry.cache, str) and os.path.exists(entry.cache):
                                # 一時ファイルパスの場合、ファイルから読み込む
                                try:
                                    with open(entry.cache, 'rb') as f:
                                        content = f.read()
                                        print(f"EnhancedArchiveManager: キャッシュの一時ファイルからコンテンツを取得: {len(content)} バイト")
                                        # バイトデータでキャッシュを更新（次回の高速化のため）
                                        entry.cache = content
                                        return content
                                except Exception as e:
                                    print(f"EnhancedArchiveManager: 一時ファイルからの読み込みエラー: {e}")
                                    # 読み込み失敗時はキャッシュをクリア
                                    entry.cache = None
                        
                        # キャッシュがない場合はアーカイブから読み込み
                        print(f"EnhancedArchiveManager: キャッシュされたコンテンツがありません。アーカイブから読み込みます")
                        
                        # 親アーカイブを特定
                        # パスの先頭から順にアーカイブを探す方式に変更
                        parent_archive_path = self._find_parent_archive(norm_path)
                        if parent_archive_path:
                            # アーカイブ内の相対パスを計算
                            if parent_archive_path == norm_path:
                                # 自分自身がアーカイブの場合
                                internal_path = ""
                            else:
                                # 相対パスを計算
                                if norm_path.startswith(parent_archive_path + '/'):
                                    internal_path = norm_path[len(parent_archive_path) + 1:]
                                else:
                                    # パス解析に失敗した場合
                                    print(f"EnhancedArchiveManager: 親アーカイブパスの解析に失敗: {parent_archive_path} -> {norm_path}")
                                    return None
                                    
                            print(f"EnhancedArchiveManager: 親アーカイブを特定: {parent_archive_path}, 内部パス: {internal_path}")
                            
                            # 親アーカイブエントリをキャッシュから探す
                            parent_entry = self._find_archive_entry_in_cache(parent_archive_path)
                            
                            if parent_entry:
                                print(f"EnhancedArchiveManager: 親アーカイブをキャッシュから発見: {parent_archive_path}")
                                
                                # 親アーカイブがキャッシュされている場合
                                if hasattr(parent_entry, 'cache') and parent_entry.cache is not None:
                                    # バイトデータとしてキャッシュされている場合
                                    if isinstance(parent_entry.cache, bytes):
                                        print(f"EnhancedArchiveManager: 親アーカイブのバイトデータキャッシュから読み込み: {len(parent_entry.cache)} バイト -> {internal_path}")
                                        handler = self.get_handler(parent_archive_path)
                                        if handler and handler.can_handle_bytes(parent_entry.cache):
                                            content = handler.read_file_from_bytes(parent_entry.cache, internal_path)
                                            if content:
                                                # 成功したらエントリにもキャッシュ
                                                print(f"EnhancedArchiveManager: 親アーカイブのキャッシュから読み込みに成功: {len(content)} バイト")
                                                entry.cache = content
                                                return content
                                    # 一時ファイルとしてキャッシュされている場合
                                    elif isinstance(parent_entry.cache, str) and os.path.exists(parent_entry.cache):
                                        print(f"EnhancedArchiveManager: 親アーカイブの一時ファイルから読み込み: {parent_entry.cache} -> {internal_path}")
                                        handler = self.get_handler(parent_entry.cache)
                                        if handler:
                                            content = handler.read_archive_file(parent_entry.cache, internal_path)
                                            if content:
                                                # 成功したらエントリにもキャッシュ
                                                print(f"EnhancedArchiveManager: 親アーカイブの一時ファイルから読み込みに成功: {len(content)} バイト")
                                                entry.cache = content
                                                return content
                            
                            # 親アーカイブからの直接読み込み（キャッシュになければ）
                            parent_handler = self.get_handler(parent_archive_path)
                            if parent_handler:
                                # 絶対パスを使用
                                use_parent_path = parent_archive_path
                                if parent_handler.use_absolute() and self.current_path:
                                    if not os.path.isabs(parent_archive_path):
                                        use_parent_path = os.path.join(self.current_path, parent_archive_path).replace('\\', '/')
                                
                                print(f"EnhancedArchiveManager: 親アーカイブから直接読み込み: {use_parent_path} -> {internal_path}")
                                content = parent_handler.read_archive_file(use_parent_path, internal_path)
                                
                                if content:
                                    # 成功したらキャッシュに格納
                                    print(f"EnhancedArchiveManager: コンテンツを読み込み成功: {len(content)} バイト、キャッシュに保存")
                                    entry.cache = content
                                    return content
                                else:
                                    print(f"EnhancedArchiveManager: 親アーカイブからの読み込みに失敗")
                            else:
                                print(f"EnhancedArchiveManager: 親アーカイブのハンドラが見つかりません: {parent_archive_path}")
                        else:
                            print(f"EnhancedArchiveManager: 親アーカイブが特定できません: {norm_path}")
            
            print(f"EnhancedArchiveManager: パス {norm_path} に一致するエントリがキャッシュにありませんでした")
        
        return None

    def _find_parent_archive(self, path: str) -> str:
        """
        指定されたパスの親アーカイブのパスを特定する
        
        パスを先頭から順に解析し、アーカイブファイルを見つける
        
        Args:
            path: 解析するパス
            
        Returns:
            親アーカイブのパス。見つからない場合は空文字列
        """
        # パスを正規化
        norm_path = path.replace('\\', '/')
        
        # パスをコンポーネントに分解
        parts = norm_path.split('/')
        
        # パスを先頭から順に再構築していき、最後のアーカイブファイルを特定
        current_path = ""
        last_archive_path = ""
        
        for i, part in enumerate(parts):
            # パスを構築
            if i > 0:
                current_path += "/"
            current_path += part
            
            # 物理ファイルの場合はアーカイブかどうか確認
            if os.path.isfile(current_path):
                _, ext = os.path.splitext(current_path.lower())
                if ext in self._archive_extensions:
                    last_archive_path = current_path
            
            # キャッシュから拡張子がアーカイブと一致するエントリを探す
            for entries_list in self._all_entries.values():
                for entry in entries_list:
                    if entry.path == current_path and entry.type == EntryType.ARCHIVE:
                        last_archive_path = current_path
                        break
        
        # 見つかった最後のアーカイブパスを返す
        return last_archive_path

    def _find_archive_entry_in_cache(self, archive_path: str) -> Optional[EntryInfo]:
        """
        キャッシュからアーカイブエントリを探す
        
        Args:
            archive_path: 探すアーカイブのパス
            
        Returns:
            見つかったアーカイブエントリ。見つからなければNone
        """
        # キャッシュからエントリを探す
        for entries_list in self._all_entries.values():
            for entry in entries_list:
                if entry.path == archive_path and entry.type == EntryType.ARCHIVE:
                    return entry
        
        return None
        
    def get_entry_cache(self) -> Dict[str, List[EntryInfo]]:
        """
        現在のエントリキャッシュを取得する
        
        Returns:
            パスをキーとし、対応するエントリのリストを値とする辞書
        """
        return self._all_entries.copy()

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
        
        # 物理ファイルかフォルダかを判定
        if os.path.exists(path):
            # 物理パスの場合は絶対パスに変換
            abs_path = os.path.abspath(path)
            normalized_path = abs_path.replace('\\', '/')
            print(f"EnhancedArchiveManager: 物理パスを絶対パスに変換: {path} -> {normalized_path}")
            
            # フォルダの場合、末尾にスラッシュがあることを確認
            if os.path.isdir(path) and not normalized_path.endswith('/'):
                normalized_path += '/'
                print(f"EnhancedArchiveManager: フォルダパスの末尾にスラッシュを追加: {normalized_path}")
        
        # まず基底クラスのset_current_pathを呼び出して全ハンドラーに通知
        super().set_current_path(normalized_path)
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
        
        # カレントパスが物理フォルダかアーカイブファイルかを判断して処理を分ける
        if os.path.isdir(path):
            # 物理フォルダの場合の処理
            print(f"EnhancedArchiveManager: 物理フォルダのルートエントリを作成: {path}")
            
            # フォルダのEntryInfoを作成
            # ディレクトリ名を正しく取得 (パスの末尾スラッシュを考慮)
            folder_name = os.path.basename(path.rstrip('/'))
            if not folder_name and path:
                # ルートディレクトリの場合（例：C:/ や Z:/）
                # ドライブレターや完全パスをそのまま名前として使用
                if ':' in path:
                    # Windowsのドライブレターの場合
                    drive_parts = path.split(':')
                    if len(drive_parts) > 0:
                        folder_name = drive_parts[0] + ":"
                else:
                    folder_name = path
            
            print(f"EnhancedArchiveManager: フォルダ名: '{folder_name}'")
            
            # フォルダのEntryInfoを作成
            root_info = EntryInfo(
                name=folder_name,
                path=path,
                type=EntryType.DIRECTORY,
                size=0,
                modified_time=None
            )
            
            # フォルダのエントリリストをキャッシュに追加
            self._all_entries[path] = [root_info]
            
            # 物理フォルダの内容をキャッシュに追加
            try:
                # フォルダの内容を取得
                folder_contents = []
                
                for item in os.listdir(path):
                    item_path = os.path.join(path, item).replace('\\', '/')
                    
                    if os.path.isdir(item_path):
                        # フォルダ
                        if not item_path.endswith('/'):
                            item_path += '/'
                            
                        entry = EntryInfo(
                            name=item,
                            path=item_path,
                            type=EntryType.DIRECTORY,
                            size=0,
                            modified_time=None
                        )
                        folder_contents.append(entry)
                    else:
                        # ファイル
                        try:
                            size = os.path.getsize(item_path)
                            mtime = os.path.getmtime(item_path)
                            import datetime
                            modified_time = datetime.datetime.fromtimestamp(mtime)
                            
                            # アーカイブかどうか判定
                            file_type = EntryType.FILE
                            _, ext = os.path.splitext(item_path.lower())
                            if ext in self._archive_extensions:
                                file_type = EntryType.ARCHIVE
                                
                            entry = EntryInfo(
                                name=item,
                                path=item_path,
                                type=file_type,
                                size=size,
                                modified_time=modified_time
                            )
                            folder_contents.append(entry)
                        except Exception as e:
                            print(f"EnhancedArchiveManager: ファイル情報取得エラー: {item_path} - {e}")
                
                # フォルダのコンテンツをキャッシュに追加
                print(f"EnhancedArchiveManager: フォルダ内容をキャッシュに追加: {path} ({len(folder_contents)} アイテム)")
                
                # 物理フォルダの場合は、そのパスと空パスの両方にコンテンツをキャッシュ
                self._all_entries[path] = folder_contents
                # 空パスにもキャッシュして、list_entriesで空のパスが渡された時に正しく動作するようにする
                self._all_entries[''] = folder_contents
                print(f"EnhancedArchiveManager: 空パスにもフォルダ内容をキャッシュしました")
                
            except Exception as e:
                print(f"EnhancedArchiveManager: フォルダ内容の取得エラー: {path} - {e}")
            
        elif os.path.isfile(path):
            # アーカイブファイルの場合の処理
            print(f"EnhancedArchiveManager: アーカイブファイルのルートエントリを作成: {path}")
            
            # ルートエントリ情報を取得
            root_info = self.get_entry_info(path)
            if root_info:
                # ファイルタイプがアーカイブかどうか確認して修正
                if root_info.type == EntryType.FILE and self._is_archive_by_extension(root_info.name):
                    root_info.type = EntryType.ARCHIVE
                    
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
                                # アーカイブファイルの場合も空パスにキャッシュ
                                self._all_entries[''] = direct_children
                                print(f"EnhancedArchiveManager: 空パスにもアーカイブ内容をキャッシュしました")
                            else:
                                print(f"EnhancedArchiveManager: アーカイブからエントリを取得できませんでした: {path}")
                    except Exception as e:
                        print(f"EnhancedArchiveManager: アーカイブのルートディレクトリ作成中にエラー: {e}")
                        import traceback
                        traceback.print_exc()
        else:
            # 物理ファイルとして存在しないパスの場合
            print(f"EnhancedArchiveManager: パス '{path}' は物理ファイルとして存在しません")
    
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
            root_entry_info = self.get_raw_entry_info(path)
            
            # 2. ハンドラを取得（ファイル種別に合わせて適切なハンドラ）
            handler = self.get_handler(path)
            if not handler:
                print(f"EnhancedArchiveManager: パス '{path}' のハンドラが見つかりません")
                # ルートエントリがあれば、それだけを返す
                if root_entry_info:
                    return [root_entry_info]
                return []
            
            print(f"EnhancedArchiveManager: '{handler.__class__.__name__}' を使用して再帰的にエントリを探索します")
            
            # 3. 最初のレベルのエントリリストを取得
            base_entries = handler.list_all_entries(path)
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
                        
                        # ネスト書庫のパスに対応するキャッシュエントリを登録
                        # ネスト書庫自身のパスを使って登録することが重要（エントリのパスと対応させる）
                        print(f"EnhancedArchiveManager: ネスト書庫エントリをキャッシュに登録: {arc_entry.path} ({len(nested_entries)} エントリ)")
                        self._all_entries[arc_entry.path] = nested_entries.copy()
                        
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

    def get_raw_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報をハンドラ経由で取得する
        原則としてエントリキャッシュ初期化時だけ使用される
        初期化後はキャッシュからのみエントリを取得する
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        handler = self.get_handler(path)
        if handler is None:
            return None
        
        return handler.get_entry_info(path)

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
        # パスの正規化（先頭のスラッシュを削除）
        if path.startswith('/'):
            path = path[1:]
            print(f"EnhancedArchiveManager: 先頭のスラッシュを削除しました: {path}")
        
        # パスを正規化
        norm_path = path.replace('\\', '/')
        
        # キャッシュされたエントリリストから検索
        if self._all_entries:
            print(f"EnhancedArchiveManager: キャッシュからエントリ情報を検索: {norm_path}")
            
            # すべてのエントリリストを検索
            for cache_path, entries in self._all_entries.items():
                for entry in entries:
                    # パスの比較（末尾のスラッシュを無視）
                    if entry.rel_path.rstrip('/') == norm_path.rstrip('/'):
                        print(f"EnhancedArchiveManager: キャッシュでエントリを発見: {entry.path}")
                        return entry
            
            print(f"EnhancedArchiveManager: キャッシュにエントリが見つかりませんでした: {norm_path}")
        else:
            print(f"EnhancedArchiveManager: エントリキャッシュが初期化されていません")
        
        # キャッシュに見つからない場合はNoneを返す（フォールバックは行わない）
        return None


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
    # パスの正規化（先頭のスラッシュを削除）
    if path.startswith('/'):
        path = path[1:]
        print(f"ArchiveManager: 先頭のスラッシュを削除しました: {path}")
    
    return get_archive_manager().list_entries(path)


def get_entry_info(path: str) -> Optional[EntryInfo]:
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
        print(f"ArchiveManager: 先頭のスラッシュを削除しました: {path}")
    
    return get_archive_manager().get_entry_info(path)


def read_file(path: str) -> Optional[bytes]:
    """
    指定されたパスのファイルの内容を読み込む
    
    Args:
        path: 読み込むファイルのパス
            
    Returns:
        ファイルの内容。読み込みに失敗した場合はNone
    """
    # パスの正規化（先頭のスラッシュを削除）
    if path.startswith('/'):
        path = path[1:]
        print(f"ArchiveManager: 先頭のスラッシュを削除しました: {path}")
    
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
    # パスの正規化（先頭のスラッシュを削除）
    if path.startswith('/'):
        path = path[1:]
        print(f"ArchiveManager: 先頭のスラッシュを削除しました: {path}")
    
    return get_archive_manager().get_stream(path)


def is_archive(path: str) -> bool:
    """
    指定されたパスがアーカイブファイルかどうかを判定する
    
    Args:
        path: 判定するパス
            
    Returns:
        アーカイブファイルならTrue、そうでなければFalse
    """
    # パスの正規化（先頭のスラッシュを削除）
    if path.startswith('/'):
        path = path[1:]
        print(f"ArchiveManager: 先頭のスラッシュを削除しました: {path}")
    
    return get_archive_manager().is_archive(path)


def is_directory(path: str) -> bool:
    """
    指定されたパスがディレクトリかどうかを判定する
    
    Args:
        path: 判定するパス
            
    Returns:
        ディレクトリの場合はTrue、それ以外の場合はFalse
    """
    # パスの正規化（先頭のスラッシュを削除）
    if path.startswith('/'):
        path = path[1:]
        print(f"ArchiveManager: 先頭のスラッシュを削除しました: {path}")
    
    return get_archive_manager().is_directory(path)


def get_parent_path(path: str) -> str:
    """
    親ディレクトリのパスを取得する
    
    Args:
        path: 対象のパス
            
    Returns:
        親ディレクトリのパス
    """
    # パスの正規化（先頭のスラッシュを削除）
    if path.startswith('/'):
        path = path[1:]
        print(f"ArchiveManager: 先頭のスラッシュを削除しました: {path}")
    
    return get_archive_manager().get_parent_path(path)


def get_entry_cache() -> Dict[str, List[EntryInfo]]:
    """
    現在のアーカイブマネージャーが保持しているエントリキャッシュを取得する
    
    Returns:
        パスをキーとして、それに対応するEntryInfoのリストを値とする辞書
    """
    manager = get_archive_manager()
    
    # EnhancedArchiveManagerの場合のみキャッシュを取得
    if isinstance(manager, EnhancedArchiveManager):
        return manager.get_entry_cache()
    
    # 通常のArchiveManagerの場合は空の辞書を返す
    return {}
