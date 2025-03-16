"""
アーカイブマネージャー

複数のアーカイブハンドラを管理し、適切なハンドラに処理を委譲するマネージャー
"""
import os
from typing import List, Optional, BinaryIO, Dict, Any

from ..arc import EntryInfo, EntryType
from ..handler.handler import ArchiveHandler
# loggingモジュールからlogutilsへの参照変更
from logutils import log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL


class ArchiveManager:
    """
    アーカイブマネージャー
    
    複数のアーカイブハンドラを管理し、パスに適したハンドラを選択して処理を委譲する
    """
    
    def __init__(self):
        """アーカイブマネージャーを初期化する"""
        # ハンドラーリスト
        self.handlers: List[ArchiveHandler] = []
        # 現在のディレクトリパス
        self.current_path: str = ""
        # ハンドラーキャッシュ
        self._handler_cache: Dict[str, ArchiveHandler] = {}
    
    def debug_print(self, message: Any, *args, level: int = INFO, trace: bool = False, **kwargs):
        """
        デバッグ出力のラッパーメソッド
        
        Args:
            message: 出力するメッセージ
            *args: メッセージのフォーマット用引数
            level: ログレベル（デフォルトはINFO）
            trace: Trueならスタックトレース情報も出力する（デフォルトはFalse）
            **kwargs: 追加のキーワード引数
        """
        # クラス名をログの名前空間として使用
        name = f"arc.manager.{self.__class__.__name__}"
        
        if trace:
            log_trace(None, level, message, *args, name=name, **kwargs)
        else:
            log_print(level, message, *args, name=name, **kwargs)
    
    def debug_debug(self, message: Any, *args, trace: bool = False, **kwargs):
        """DEBUGレベルのログ出力"""
        self.debug_print(message, *args, level=DEBUG, trace=trace, **kwargs)
    
    def debug_info(self, message: Any, *args, trace: bool = False, **kwargs):
        """INFOレベルのログ出力"""
        self.debug_print(message, *args, level=INFO, trace=trace, **kwargs)
    
    def debug_warning(self, message: Any, *args, trace: bool = False, **kwargs):
        """WARNINGレベルのログ出力"""
        self.debug_print(message, *args, level=WARNING, trace=trace, **kwargs)
    
    def debug_error(self, message: Any, *args, trace: bool = False, **kwargs):
        """ERRORレベルのログ出力"""
        self.debug_print(message, *args, level=ERROR, trace=trace, **kwargs)
        
    def debug_critical(self, message: Any, *args, trace: bool = False, **kwargs):
        """CRITICALレベルのログ出力"""
        self.debug_print(message, *args, level=CRITICAL, trace=trace, **kwargs)
    
    def register_handler(self, handler: ArchiveHandler) -> None:
        """
        アーカイブハンドラーを登録する
        
        Args:
            handler: 登録するハンドラーのインスタンス
        """
        self.handlers.append(handler)
        
    def set_current_path(self, path: str) -> None:
        """
        現在のベースパスを設定する
        
        Args:
            path: 設定するベースパス
        """
        self.current_path = path
        # 現在のパスをすべてのハンドラに伝達
        for handler in self.handlers:
            handler.set_current_path(path)
        
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
            return self._handler_cache[norm_path]
        
        # 各ハンドラがパスを処理できるか確認
        for handler in self.handlers:
            if handler.can_handle(norm_path):
                # このハンドラで処理可能
                self._handler_cache[norm_path] = handler
                return handler
        
        # 該当するハンドラが見つからない
        return None
        
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるエントリのリストを取得する
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        # 適切なハンドラを取得
        handler = self.get_handler(path)
        if handler is None:
            return []
        
        # ハンドラにリスト取得を委譲
        return handler.list_entries(path)
    
    def finalize_entry(self, entry: EntryInfo, archive_path: str) -> EntryInfo:
        """
        ハンドラから帰ってきた未完成のエントリを完成させる
        - 書庫内パスに書庫の絶対パスを連結してabs_pathを設定
        - abs_pathからcurrent_pathを引いてrel_pathをルートからの相対パスに設定
        - ファイルの場合、ハンドラが書庫として処理できる拡張子ならtypeをARCHIVEに変更
        
        Args:
            entry: 処理するエントリ
            archive_path: アーカイブ/フォルダの絶対パス
            
        Returns:
            最終処理後のエントリ
        """
        # ファイルの場合、アーカイブかどうかを判定
        if entry.type == EntryType.FILE and self._is_archive_by_extension(entry.name):
            entry.type = EntryType.ARCHIVE
        
        # パスを絶対パスに変換
        abs_path = os.path.join(archive_path, entry.rel_path).replace('\\', '/')
        entry.path = abs_path
        entry.abs_path = abs_path
        
        # ルートからの相対パスを設定
        rel_path = abs_path.replace(self.current_path, '', 1).lstrip('/')
        entry.rel_path = rel_path
        self.debug_debug(f"ArchiveManager: Finalized: rel_path={entry.rel_path}")
        return entry

    def finalize_entries(self, entries: List[EntryInfo], archive_path:str) -> List[EntryInfo]:
        """
        ハンドラから帰ってきた未完成のエントリリストを完成させる
        - 書庫内パスに書庫の絶対パスを連結してabs_pathを設定
        - abs_pathからcurrent_pathを引いてrel_pathをルートからの相対パスに設定
        - ファイルの場合、ハンドラが書庫として処理できる拡張子ならtypeをARCHIVEに変更
        
        Args:
            entries: 処理するエントリリスト
            archive_path: アーカイブ/フォルダの絶対パス
            
        Returns:
            最終処理後のエントリリスト
        """
        finalized_entries = []
        for entry in entries:
            finalized_entries.append(self.finalize_entry(entry, archive_path))
        return finalized_entries
        
    # finalyzeという古いスペルミスのメソッドを互換性のために残す
    def finalyze_entries(self, entries: List[EntryInfo], archive_path:str) -> List[EntryInfo]:
        """
        ハンドラから帰ってきた未完成のエントリリストを完成させる（互換性のため）
        
        Args:
            entries: 処理するエントリリスト
            archive_path: アーカイブ/フォルダの絶対パス
            
        Returns:
            最終処理後のエントリリスト
        """
        # 正しいスペルのメソッドに転送
        return self.finalize_entries(entries, archive_path)

    def _is_archive_by_extension(self, path: str) -> bool:
        """
        パスがアーカイブの拡張子を持つかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            アーカイブの拡張子を持つ場合はTrue
        """
        # このメソッドはサブクラスでオーバーライドされることを想定
        return False
    
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
        # パスを正規化
        path = path.replace('\\', '/')
        # パスを絶対パスに変換して正規化
        if not os.path.isabs(path) and self.current_path:
            path = os.path.join(self.current_path, path).replace('\\', '/')
        archive_path, internal_path = self._analyze_path(path)
        handler = self.get_handler(archive_path)
        if handler is None:
            return None
        # name_in_arcを知るため、まずlist_all_entriesを呼び出す
        entries = handler.list_all_entries(path)
        if entries is None:
            return None
        # rel_pathが一致するエントリを探す
        for entry in entries:
            # rel_pathとinternal_pathを比較する際に末尾のスラッシュを考慮する
            if entry.rel_path.rstrip('/') == internal_path.rstrip('/'):
                entry = self.finalize_entry(entry, archive_path)
                return entry
        return None

    def _analyze_path(self, path: str) -> tuple[str, str]:
        """
        パスを解析し、アーカイブパスと内部パスに分割する
        
        Args:
            path: 分割するパス
            
        Returns:
            (アーカイブパス, 内部パス) のタプル
        """
        # このメソッドはサブクラスでオーバーライドされることを想定
        return path, ""
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        デフォルトではget_raw_entry_infoを呼び出す
        サブクラスでキャッシュを使用する場合はオーバーライドする
        
        Args:
            path: 情報を取得するエントリのパス(ベースパスからの相対パス)
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        return self.get_raw_entry_info(path)
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定されたパスのファイルの内容を読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        # 適切なハンドラを取得
        handler = self.get_handler(path)
        if handler is None:
            return None
        
        # ハンドラにファイル読み込みを委譲
        return handler.read_file(path)
    
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        # 適切なハンドラを取得
        handler = self.get_handler(path)
        if handler is None:
            return None
        
        # ハンドラにストリーム取得を委譲
        return handler.get_stream(path)
    
    def is_archive(self, path: str) -> bool:
        """
        指定されたパスがアーカイブファイルかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            アーカイブファイルならTrue、そうでなければFalse
        """
        # 適切なハンドラを取得
        handler = self.get_handler(path)
        if handler is None:
            return False
        
        # ハンドラがアーカイブをサポートしているか確認
        return handler.can_archive()
    
    def is_directory(self, path: str) -> bool:
        """
        指定されたパスがディレクトリかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、それ以外の場合はFalse
        """
        # 適切なハンドラを取得
        handler = self.get_handler(path)
        if handler is None:
            return False
        
        # ハンドラにディレクトリ判定を委譲
        return handler.is_directory(path)
    
    def get_parent_path(self, path: str) -> str:
        """
        親ディレクトリのパスを取得する
        
        Args:
            path: 対象のパス
            
        Returns:
            親ディレクトリのパス
        """
        # 適切なハンドラを取得
        handler = self.get_handler(path)
        if handler is None:
            # ハンドラが見つからない場合の標準処理
            import os
            parent = os.path.dirname(path)
            return parent.replace('\\', '/')
        
        # ハンドラに親パス取得を委譲
        return handler.get_parent_path(path)
