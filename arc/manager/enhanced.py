"""
拡張アーカイブマネージャー

アーカイブ内のネスト構造をサポートする拡張アーカイブマネージャー
"""

import os
import tempfile
import shutil
from typing import List, Optional, BinaryIO, Tuple, Dict, Set, Any

from .manager import ArchiveManager
from ..arc import EntryInfo, EntryType
from ..handler.handler import ArchiveHandler

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
        # すべてのエントリを格納するためのクラス変数（リストから単一エントリに変更）
        self._all_entries: Dict[str, EntryInfo] = {}
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
        
        # パスを正規化して相対パスとして扱う（末尾のスラッシュを削除）
        norm_path = path.replace('\\', '/').lstrip('/').rstrip('/')
        
        # キャッシュされたエントリリストから検索
        if self._all_entries:
            print(f"EnhancedArchiveManager: キャッシュからエントリ情報を検索: {norm_path}")
            
            # 正規化したパスでキャッシュを直接検索
            if norm_path in self._all_entries:
                print(f"EnhancedArchiveManager: キャッシュでエントリを発見: {norm_path}")
                return self._all_entries[norm_path]
            
            print(f"EnhancedArchiveManager: キャッシュにエントリが見つかりませんでした: {norm_path}")
        else:
            print(f"EnhancedArchiveManager: エントリキャッシュが初期化されていません")
        
        # キャッシュに見つからない場合はNoneを返す（フォールバックは行わない）
        return None

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
            print(f"EnhancedArchiveManager: 先頭のスラッシュを削除しました: {path}")
        
        # パスを正規化して末尾のスラッシュを削除（キャッシュのキーは末尾スラッシュなし）
        norm_path = path.replace('\\', '/').rstrip('/')
        print(f"EnhancedArchiveManager: パス '{norm_path}' のエントリを取得")
        
        # 空のパスはベースパス自体（ルート階層）を表す
        is_root = not norm_path
        
        # キャッシュが初期化されていることを確認
        if not self._all_entries:
            raise FileNotFoundError(f"エントリキャッシュが初期化されていません。set_current_pathを先に呼び出してください。")
        
        print(f"EnhancedArchiveManager: キャッシュされた全エントリから検索します ({len(self._all_entries)} エントリキー)")
        
        # ルートディレクトリ(空パス)の場合
        if is_root:
            # キャッシュから直接の子エントリを探す
            result = []
            seen_paths = set()  # 重複回避用

            # すべてのエントリを検索して、直接の子エントリのみを対象にする
            for entry_key, entry in self._all_entries.items():
                # EntryInfoオブジェクトの場合のみ
                if isinstance(entry, EntryInfo):
                    # 修正：キャッシュのキーを使って子エントリかどうかを判断
                    # 1. キーが空文字でない（ルートエントリ自身を除外）
                    # 2. キーに'/'が含まれていない（直接の子のみ）
                    if entry_key != "" and '/' not in entry_key:
                        if entry.path not in seen_paths:
                            result.append(entry)
                            seen_paths.add(entry.path)
                            print(f"  発見 (ルート直下): {entry.name} ({entry.rel_path})")

            # 結果を返す（空の場合でも空リストを返す）
            print(f"EnhancedArchiveManager: キャッシュから {len(result)} エントリを取得しました")
            return result
        
        # 非ルートパスの場合、相対パスとしてキャッシュをチェック
        
        # 1. まずパスがファイルを指しているかチェック
        if norm_path in self._all_entries:
            entry = self._all_entries[norm_path]
            if isinstance(entry, EntryInfo) and entry.type == EntryType.FILE:
                # 問題点3の修正: ファイルエントリなのに末尾がスラッシュの場合は例外を投げる
                if original_path.endswith('/') or original_path.endswith('\\'):
                    print(f"EnhancedArchiveManager: ファイルパスの末尾にスラッシュがあります: {original_path}")
                    raise ValueError(f"ファイルパス '{original_path}' の末尾にスラッシュがあります。ファイルパスにスラッシュは使用できません。")
                
                print(f"EnhancedArchiveManager: ファイルエントリを返します: {entry.path}")
                return [entry]
        
        # 2. ディレクトリ/アーカイブエントリ自体をチェック
        if norm_path in self._all_entries:
            found_entry = self._all_entries[norm_path]
            
            if found_entry and isinstance(found_entry, EntryInfo) and found_entry.type in [EntryType.DIRECTORY, EntryType.ARCHIVE]:
                # 対応するディレクトリ/アーカイブを発見 - 子エントリを検索
                result = []
                seen_paths = set()  # 重複回避用
                
                # パスプレフィックスを構築（明示的に'/'を使用）
                prefix = f"{norm_path}/"
                
                # すべてのエントリを対象に、このディレクトリの直接の子エントリを検索
                for entry_key, child_entry in self._all_entries.items():
                    if isinstance(child_entry, EntryInfo):
                        # このパスの子エントリかどうかを正確に判断
                        # 1. エントリがディレクトリ自体でないこと
                        # 2. エントリキーがプレフィックスで始まること
                        if (entry_key != norm_path and entry_key.startswith(prefix)):
                            # プレフィックス後の部分を抽出
                            rest_path = entry_key[len(prefix):]
                            # 直接の子エントリ（それ以上ネストしていない）のみを対象
                            if '/' not in rest_path:
                                if child_entry.path not in seen_paths:
                                    result.append(child_entry)
                                    seen_paths.add(child_entry.path)
                                    print(f"  発見: {child_entry.name} ({child_entry.rel_path})")
                
                # 結果を返す（空でも空リストを返す）
                print(f"EnhancedArchiveManager: キャッシュから {len(result)} エントリを取得しました")
                return result
        
        # 指定されたパスが見つからない場合
        print(f"EnhancedArchiveManager: キャッシュにマッチするエントリがありません。パス '{path}' は無効かアクセス不能です。")
        raise FileNotFoundError(f"指定されたパス '{path}' にエントリが見つかりません")

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
        
        # 物理フォルダの場合は、すぐにそのパスをアーカイブパスとして返す
        if os.path.isdir(norm_path):
            print(f"EnhancedArchiveManager: 物理フォルダを検出: {norm_path}")
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
        
    def finalize_entry(self, entry: EntryInfo, archive_path: str) -> EntryInfo:
        """
        ハンドラから帰ってきた未完成のエントリを完成させ、追加処理を行う
        - スーパークラスのfinalize_entriesを呼び出して基本的な処理を行う
        - アーカイブタイプの判定を行う
        
        Args:
            entry: 処理するエントリ
            archive_path: アーカイブ/フォルダの絶対パス
            
        Returns:
            最終処理後のエントリ
        """
        # 基本的なファイナライズ処理を親クラスに委譲
        entry = super().finalize_entry(entry, archive_path)
        # ファイルの場合、アーカイブかどうかを判定
        if entry.type == EntryType.FILE and self._is_archive_by_extension(entry.name):
            entry.type = EntryType.ARCHIVE
        
        return entry

    def finalize_entries(self, entries: List[EntryInfo], archive_path: str) -> List[EntryInfo]:
        """
        ハンドラから帰ってきた未完成のエントリリストを完成させ、追加処理を行う
        - スーパークラスのfinalize_entriesを呼び出して基本的な処理を行う
        - アーカイブタイプの判定を行う
        
        Args:
            entries: 処理するエントリリスト
            archive_path: アーカイブ/フォルダの絶対パス
            
        Returns:
            最終処理後のエントリリスト
        """
        finalized_entries = []
        for entry in entries:
            entry = self.finalize_entry(entry, archive_path)
            finalized_entries.append(entry)
        
        return finalized_entries

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
                            # ネストされたエントリのパスを修正
                            entries = super().finalyze_entries(entries, archive_path)
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
                
            # 7. エントリリストの処理 - パスの修正とファイナライズを同時に行う
            result_entries = []
            
            for entry in entries:
                # パスを構築
                entry_path = f"{archive_path}/{entry.rel_path}" if entry.path else archive_path
                
                # 問題点2の修正: abs_pathを明示的に設定
                new_entry = handler.create_entry_info(
                    name=entry.name,
                    abs_path=entry_path,  # abs_pathにentry_pathを設定
                    rel_path=entry.rel_path,
                    type=entry.type,
                    size=entry.size,
                    modified_time=entry.modified_time,
                    created_time=entry.created_time,
                    is_hidden=entry.is_hidden,
                    name_in_arc=entry.name_in_arc,
                    attrs=entry.attrs,
                    path=entry_path  # pathにもentry_pathを設定
                )
                
                # 作成したエントリを即座にファイナライズ
                finalized_entry = self.finalize_entry(new_entry, arc_entry.path)
                
                # エントリを結果に追加
                result_entries.append(finalized_entry)
            
            # 8. アーカイブエントリを識別
            marked_entries = self._mark_archive_entries(result_entries)
            
            # 9. キャッシュに保存 - 各エントリを個別に登録
            print(f"EnhancedArchiveManager: {len(result_entries)} エントリをキャッシュに登録")
            
            # 各エントリを個別にキャッシュに追加（相対パスのみを使用）
            for entry in result_entries:
                # キャッシュ登録用のキー（相対パス）を取得し、末尾の/を取り除く
                entry_key = entry.rel_path.rstrip('/')
                # 空文字でない相対パスのみ登録（ルートエントリは登録しない）
                if entry_key or entry_key == "":  # 空文字列キー（ルート）も登録可能に
                    self._all_entries[entry_key] = entry
                    print(f"EnhancedArchiveManager: エントリ {entry_key} をキャッシュに登録")
            
            # キャッシュ状態のデバッグ情報
            if debug_mode:
                print(f"EnhancedArchiveManager: キャッシュ状況:")
                print(f"  書庫キャッシュ: arc_entry.cache {'あり' if arc_entry.cache is not None else 'なし'}")
                print(f"  キャッシュされたエントリパス例: {[e.path for e in marked_entries[:3]]}")
            
            return result_entries
        
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
            - アーカイブが見つからない場合は (current_path, "", None)
            - バイトデータが直接キャッシュされている場合は (仮想パス, internal_path, bytes)
            - 一時ファイルでキャッシュされている場合は (cache_path, internal_path, None)
            - 通常のアーカイブ内ファイルの場合は (archive_path, internal_path, None)
        """
        # パスを正規化（先頭のスラッシュを削除、末尾のスラッシュも削除）
        norm_path = path.replace('\\', '/').lstrip('/').rstrip('/')
        print(f"EnhancedArchiveManager: ファイルソース解決: {norm_path}")
        
        # 1. まずエントリキャッシュから完全一致するエントリを検索
        entry_info = self.get_entry_info(norm_path)
        
        # エントリが見つからない場合は早期リターン
        if not entry_info:
            print(f"EnhancedArchiveManager: 指定されたパス {norm_path} に対応するエントリが見つかりません")
            return "", "", None
        
        # 2. パスコンポーネントを解析してアーカイブを特定
        archive_path = ""
        internal_path = entry_info.name_in_arc  # name_in_arcは必ず存在する前提
        print(f"EnhancedArchiveManager: name_in_arcを内部パスとして使用: {internal_path}")
        
        # パスをコンポーネントに分解して親となるアーカイブを特定
        parent_archive_path = self._find_parent_archive(norm_path)
        
        if parent_archive_path:
            archive_path = parent_archive_path
            
            # 親アーカイブエントリをキャッシュから探す
            parent_entry = self._find_archive_entry_in_cache(parent_archive_path)
            
            if parent_entry and hasattr(parent_entry, 'cache') and parent_entry.cache is not None:
                cache = parent_entry.cache
                if isinstance(cache, bytes):
                    print(f"EnhancedArchiveManager: アーカイブエントリからキャッシュされたバイトデータを返します: {len(cache)} バイト")
                    return parent_entry.path, internal_path, cache
                elif isinstance(cache, str) and os.path.exists(cache):
                    print(f"EnhancedArchiveManager: アーカイブエントリからキャッシュされた一時ファイルを返します: {cache}")
                    return cache, internal_path, None
        
        # アーカイブパスが特定できた場合
        if archive_path:
            # 相対パスを絶対パスに変換
            if not os.path.isabs(archive_path) and self.current_path:
                archive_path = os.path.join(self.current_path, archive_path).replace('\\', '/')
                print(f"EnhancedArchiveManager: アーカイブパスを絶対パスに変換: {archive_path}")
            
            return archive_path, internal_path, None
        
        # 親アーカイブが見つからない場合は、current_pathとname_in_arcを返す
        # これにより、ルートエントリなどの処理が正しく行われる
        print(f"EnhancedArchiveManager: 親アーカイブが見つからないため、ルートパスを使用します")
        return self.current_path, entry_info.name_in_arc, None

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
            if norm_current_path in self._all_entries:
                entry = self._all_entries[norm_current_path]
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
        if norm_path in self._all_entries:
            entry = self._all_entries[norm_path]
            if entry.type == EntryType.ARCHIVE:
                return entry
        
        return None
        
    def get_entry_cache(self) -> Dict[str, EntryInfo]:
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
        
        # デバッグ: list_all_entries 呼び出し前のルートエントリ状態
        if "" in self._all_entries:
            root_entry = self._all_entries[""]
            print(f"DEBUG: [set_current_path] list_all_entries 呼び出し前のルートエントリ: rel_path=\"{root_entry.rel_path}\"")
        else:
            print(f"DEBUG: [set_current_path] list_all_entries 呼び出し前: ルートエントリがまだ存在しません")
        
        # ルートエントリ作成は list_all_entries に委譲
        
        # その後、すべてのエントリリストを再帰的に取得
        try:
            print("EnhancedArchiveManager: 全エントリリストを取得中...")
            entries = self.list_all_entries(normalized_path, recursive=True)
            
            # デバッグ: list_all_entries 呼び出し後のルートエントリ状態
            if "" in self._all_entries:
                root_entry = self._all_entries[""]
                print(f"DEBUG: [set_current_path] list_all_entries 呼び出し後のルートエントリ: rel_path=\"{root_entry.rel_path}\"")
            else:
                print(f"DEBUG: [set_current_path] list_all_entries 呼び出し後: ルートエントリが存在しません！")
                
            print(f"EnhancedArchiveManager: {len(entries)} エントリを取得しました")
            return entries
        except Exception as e:
            print(f"EnhancedArchiveManager: 全エントリリスト取得中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()

    def _ensure_root_entry_in_cache(self, path: str) -> None:
        """
        ルートエントリがキャッシュに含まれていることを確認し、
        なければ追加する。
        
        ここでの「ルート」とはベースパス（set_current_pathで設定されたパス）を指す。
        
        Args:
            path: ルートエントリのパス（ベースパス）
            
        Raises:
            FileNotFoundError: 指定されたパスが見つからない場合
        """
        # 物理ファイルとして存在しないパスの場合は例外を投げる
        if not os.path.exists(path):
            print(f"EnhancedArchiveManager: パス '{path}' は物理ファイルとして存在しません")
            raise FileNotFoundError(f"指定されたパス '{path}' が見つかりません")
        
        # パスを正規化
        normalized_path = path.replace('\\', '/')
        
        # キャッシュが既に初期化されているかチェック
        if "" in self._all_entries:
            print(f"EnhancedArchiveManager: ルートエントリはキャッシュに既に存在します")
            return
        
        # カレントパスが物理フォルダかアーカイブファイルかを判断して処理を分ける
        if os.path.isdir(path):
            # 物理フォルダの場合の処理
            print(f"EnhancedArchiveManager: 物理フォルダのルートエントリを作成: {path}")
            
            # パスから末尾のスラッシュを除去
            path_without_slash = path.rstrip('/')
            
            # フォルダ名の取得処理を改善
            folder_name = os.path.basename(path_without_slash)
            
            # フォルダ名が空の場合（ルートディレクトリなど）の特殊処理
            if not folder_name:
                if ':' in path_without_slash:
                    # Windowsのドライブルート (C:\ など)
                    drive = path_without_slash.split(':')[0]
                    folder_name = f"{drive}:"
                # 問題点1の修正: '//'判定を'/'判定より先に行う
                elif path.startswith('//') or path.startswith('\\\\'):
                    # ネットワークパス
                    parts = path_without_slash.replace('\\', '/').strip('/').split('/')
                    folder_name = parts[0] if parts else "Network"
                elif path.startswith('/'):
                    # UNIXのルートディレクトリ
                    folder_name = "/"
                else:
                    # その他の特殊ケース
                    folder_name = path_without_slash or "Root"
            
            print(f"EnhancedArchiveManager: フォルダ名: '{folder_name}'")
            
            # EntryInfoオブジェクトを生成
            root_info = EntryInfo(
                name=folder_name,
                path=path,
                rel_path="",  # 初期値として空文字列を設定
                type=EntryType.DIRECTORY,
                size=0,
                modified_time=None,
                abs_path=path  # 絶対パスを明示的に設定
            )
            
            # コンストラクタで上書きされる可能性がある重要な属性を明示的に上書き
            root_info.rel_path = ""  # 確実に空文字列を設定
            root_info.abs_path = path  # 絶対パスを明示的に設定
            
            # キャッシュキーとして使用するための確実に空文字列である変数
            cache_key = ""
            
            # ルートエントリをキャッシュに追加（空文字列をキーとする）
            self._all_entries[cache_key] = root_info
            
            # デバッグログの改善（引用符で囲んで空文字列を視覚化）
            print(f"EnhancedArchiveManager: ルートエントリをキャッシュに追加: キー=\"{cache_key}\" -> パス=\"{root_info.path}\", rel_path=\"{root_info.rel_path}\"")
            
            # 物理フォルダの内容をキャッシュに追加
            try:
                # フォルダの内容を取得
                folder_contents = []
                
                for item in os.listdir(path):
                    item_path = os.path.join(path, item).replace('\\', '/')
                    rel_path = item  # ルートからの相対パス
                    
                    if os.path.isdir(item_path):
                        # フォルダ
                        # 問題点2の修正: EntryInfoにabs_pathを設定
                        entry = EntryInfo(
                            name=item,
                            path=item_path,
                            rel_path=rel_path,  # ルートからの相対パス
                            type=EntryType.DIRECTORY,
                            size=0,
                            modified_time=None,
                            abs_path=item_path  # abs_pathにpathを設定
                        )
                        folder_contents.append(entry)
                        
                        # キャッシュキーとして末尾の/を取り除いた相対パスを使用
                        cache_key = rel_path.rstrip('/')
                        self._all_entries[cache_key] = entry
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
                            
                            # 問題点2の修正: EntryInfoにabs_pathを設定
                            entry = EntryInfo(
                                name=item,
                                path=item_path,
                                rel_path=rel_path,  # ルートからの相対パス
                                type=file_type,
                                size=size,
                                modified_time=modified_time,
                                abs_path=item_path  # abs_pathにpathを設定
                            )
                            folder_contents.append(entry)
                            
                            # キャッシュキーとして末尾の/を取り除いた相対パスを使用
                            cache_key = rel_path.rstrip('/')
                            self._all_entries[cache_key] = entry
                        except Exception as e:
                            print(f"EnhancedArchiveManager: ファイル情報取得エラー: {item_path} - {e}")
                    
                print(f"EnhancedArchiveManager: フォルダ内容を処理: {path} ({len(folder_contents)} アイテム)")
                    
            except Exception as e:
                print(f"EnhancedArchiveManager: フォルダ内容の取得エラー: {path} - {e}")
        
        elif os.path.isfile(path):
            # アーカイブファイルの場合の処理
            print(f"EnhancedArchiveManager: アーカイブファイルのルートエントリを作成: {path}")
            
            # ファイル情報を取得
            try:
                size = os.path.getsize(path)
                mtime = os.path.getmtime(path)
                import datetime
                modified_time = datetime.datetime.fromtimestamp(mtime)
                
                # EntryInfoオブジェクトを生成
                root_info = EntryInfo(
                    name=os.path.basename(path),
                    path=path,
                    rel_path="",  # 初期値として空文字列を設定
                    type=EntryType.ARCHIVE,
                    size=size,
                    modified_time=modified_time,
                    abs_path=path  # 絶対パスを明示的に設定
                )
                
                # コンストラクタで上書きされる可能性がある重要な属性を明示的に上書き
                root_info.rel_path = ""  # 確実に空文字列を設定
                root_info.abs_path = path  # 絶対パスを明示的に設定
                
                # 属性が正しく設定されたか確認
                if root_info.rel_path != "":
                    print(f"警告: ルートエントリのrel_pathが上書きされています: \"{root_info.rel_path}\"")
                    root_info.rel_path = ""  # 強制的に修正
                
                # キャッシュキーとして使用するための確実に空文字列である変数
                cache_key = ""
                
                # ルートエントリをキャッシュに追加
                self._all_entries[cache_key] = root_info
                
                # デバッグログの改善（引用符で囲んで空文字列を視覚化）
                print(f"EnhancedArchiveManager: ルートエントリをキャッシュに追加: キー=\"{cache_key}\" -> パス=\"{root_info.path}\", rel_path=\"{root_info.rel_path}\"")
                
                # アーカイブの場合、アーカイブ内のエントリを取得・登録
                try:
                    # ハンドラを取得
                    handler = self.get_handler(path)
                    if handler:
                        # ハンドラから直接エントリリストを取得
                        # 修正: list_entriesではなくlist_all_entriesを使用
                        direct_children = handler.list_all_entries(path)
                        if direct_children:
                            print(f"EnhancedArchiveManager: アーカイブから {len(direct_children)} エントリを取得")
                            
                            # エントリをファイナライズしてアーカイブを識別
                            for entry in direct_children:
                                finalized_entry = self.finalize_entry(entry, path)
                                
                                # 相対パスのみでキャッシュに登録
                                rel_path = entry.rel_path
                                if rel_path:  # 空文字でない場合のみ登録
                                    # キャッシュキーとして末尾の/を取り除いた相対パスを使用
                                    cache_key = rel_path.rstrip('/')
                                    self._all_entries[cache_key] = finalized_entry
                        else:
                            print(f"EnhancedArchiveManager: アーカイブは空です: {path}")
                except Exception as e:
                    print(f"EnhancedArchiveManager: アーカイブのエントリ取得中にエラー: {e}")
                    import traceback
                    traceback.print_exc()
                
            except Exception as e:
                print(f"EnhancedArchiveManager: ファイル情報取得エラー: {path} - {e}")

    def list_all_entries(self, path: str, recursive: bool = True) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるすべてのエントリを再帰的に取得する
        
        アーカイブ内のアーカイブ（ネストされたアーカイブ）も探索し、
        すべてのエントリを統合されたリストとして返します。
        結果はクラス変数に保存され、後で get_all_entries() で取得できます。
        
        Args:
            path: リストを取得するディレクトリやアーカイブのパス（ベースパス）
            recursive: 再帰的に探索するかどうか（デフォルトはTrue）
            
        Returns:
            すべてのエントリ情報のリスト
        """
        # 探索済みエントリとプロセス済みパスをリセット
        old_entries = self._all_entries.copy() if "" in self._all_entries else {}
        self._all_entries = {}
        self._processed_paths = set()
        
        # パスを正規化
        path = path.replace('\\', '/')
        
        try:
            # キャッシュをクリアした後、最初にルートエントリをキャッシュに追加
            print(f"DEBUG: [list_all_entries] _ensure_root_entry_in_cache 呼び出し前")
            self._ensure_root_entry_in_cache(path)
            
            # デバッグ: ルートエントリ作成直後の状態
            if "" in self._all_entries:
                root_entry = self._all_entries[""]
                print(f"DEBUG: [list_all_entries] ルートエントリ作成直後: rel_path=\"{root_entry.rel_path}\"")
            else:
                print(f"DEBUG: [list_all_entries] ルートエントリ作成失敗！")
            
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
            raw_base_entries = handler.list_all_entries(path)
            if not raw_base_entries:
                print(f"EnhancedArchiveManager: エントリが見つかりませんでした: {path}")
                # エントリが取得できなくても、ルートエントリ自体は返す
                if root_entry_info:
                    print(f"EnhancedArchiveManager: ルートエントリのみを返します")
                    return [root_entry_info]
                return []
            
            # ハンドラが返したエントリを一つずつファイナライズ処理する
            base_entries = []
            for entry in raw_base_entries:
                finalized_entry = self.finalize_entry(entry, path)
                base_entries.append(finalized_entry)
            
            print(f"EnhancedArchiveManager: ベースレベルで {len(base_entries)} エントリを取得しました")
            
            # 5. 結果リストを構築（ルートエントリを先頭に）
            all_entries = []
            
            # ルートエントリが取得できた場合は、リストの最初に追加
            if root_entry_info:
                # ファイナライズでアーカイブ判定が行われるため、ここではfinalize_entryを適用
                root_entry_info = self.finalize_entry(root_entry_info, path)
                print(f"EnhancedArchiveManager: ルートエントリをリストに追加: {root_entry_info.path}")
                all_entries.append(root_entry_info)
            
            # ベースエントリを結果リストに追加
            all_entries.extend(base_entries)
            
            # 6. キャッシュに保存 - 各エントリを個別に登録
            for entry in base_entries:
                # 相対パスをキャッシュのキーとして使用し、末尾の/を取り除く
                entry_key = entry.rel_path.rstrip('/')
                # 空でない相対パスのみ登録
                if entry_key or entry_key == "":  # 空文字列キー（ルート）も登録可能に
                    self._all_entries[entry_key] = entry
                    print(f"EnhancedArchiveManager: ベースエントリ {entry_key} をキャッシュに登録")
            
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
                    
                    # 結果を追加
                    if nested_entries:
                        all_entries.extend(nested_entries)
                        
                        # ネスト書庫内の各エントリを個別に登録
                        for nested_entry in nested_entries:
                            # エントリキー（相対パス）を正規化
                            entry_key = nested_entry.rel_path
                            # キーの正規化（先頭のスラッシュを削除、末尾のスラッシュを削除）
                            if entry_key.startswith('/'):
                                entry_key = entry_key[1:]
                            entry_key = entry_key.rstrip('/')
                            
                            # 空でない相対パスのみ登録
                            if entry_key or entry_key == "":  # 空文字列キー（ルート）も登録可能に
                                self._all_entries[entry_key] = nested_entry
                                
                                # ネストされたアーカイブも処理するためにキューに追加
                                if nested_entry.type == EntryType.ARCHIVE and nested_entry.path not in processed_archives:
                                    archive_queue.append(nested_entry)
            
            # メソッドの最後で再度ルートエントリの状態を確認
            if "" in self._all_entries:
                root_entry = self._all_entries[""]
                print(f"DEBUG: [list_all_entries] メソッド終了時のルートエントリ: rel_path=\"{root_entry.rel_path}\"")
            else:
                print(f"DEBUG: [list_all_entries] メソッド終了時: ルートエントリが存在しません！")
            
            return all_entries
                
        except Exception as e:
            print(f"EnhancedArchiveManager.list_all_entries エラー: {e}")
            import traceback
            traceback.print_exc()
            # エラーが発生しても、ルートエントリが取得できていれば返す
            if 'root_entry_info' in locals() and root_entry_info:
                return [root_entry_info]
            return []


