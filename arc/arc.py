"""
アーカイブおよびファイルシステム透過アクセスモジュール

物理フォルダとアーカイブファイル（ZIP, RAR, LHA等）を透過的に扱うためのクラス群
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, BinaryIO, Tuple


class EntryType(Enum):
    """エントリのタイプを表す列挙型"""
    FILE = 1       # 通常ファイル
    DIRECTORY = 2  # ディレクトリ
    ARCHIVE = 3    # アーカイブファイル（ZIPなど）
    SYMLINK = 4    # シンボリックリンク
    UNKNOWN = 99   # 不明な型


@dataclass
class EntryInfo:
    """
    ファイルシステム内のエントリ（ファイルやディレクトリ）の情報
    
    物理ファイルとアーカイブ内のファイルの両方を表現できる
    """
    name: str                  # エントリの名前（ファイル名またはディレクトリ名）
    path: str                  # エントリへのパス（仮想パスシステムでの絶対パス）
    type: EntryType            # エントリのタイプ
    size: int = 0              # ファイルサイズ（バイト）
    created_time: Optional[datetime] = None  # 作成日時
    modified_time: Optional[datetime] = None  # 更新日時
    is_hidden: bool = False    # 隠しファイルかどうか
    name_in_arc: Optional[str] = None  # アーカイブ内の元のファイル名（エンコード変換前）
    attrs: Dict = None         # 追加属性（拡張用）
    cache: Optional[Union[bytes, str]] = None  # コンテンツキャッシュ（バイトまたは一時ファイルパス）
    rel_path: Optional[str] = None  # エントリへの相対パス（カレントパスからの相対）

    def __post_init__(self):
        """オブジェクト初期化後の処理"""
        if self.attrs is None:
            self.attrs = {}
        # 相対パスが指定されていない場合は、絶対パスをそのまま設定
        if self.rel_path is None:
            self.rel_path = self.path
    
    @property
    def extension(self) -> str:
        """ファイル拡張子を取得（小文字）"""
        if self.type == EntryType.FILE or self.type == EntryType.ARCHIVE:
            _, ext = os.path.splitext(self.name)
            return ext.lower()
        return ""
    
    @property
    def is_archive(self) -> bool:
        """アーカイブファイルかどうかを判定"""
        return self.type == EntryType.ARCHIVE


class ArchiveHandler(ABC):
    """
    アーカイブファイルまたはディレクトリを扱うための抽象基底クラス
    
    このクラスは、ファイルシステムとアーカイブファイルを透過的に扱うためのインターフェースを定義する
    """
    def __init__(self):
        # 現在のベースパス（相対パスの基準となるパス）
        self.current_path: str = ""
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """このハンドラがサポートするファイル拡張子のリスト"""
        pass
    

    def use_absolute(self) -> bool:
        """
        絶対パスを使用するかどうかを返す
        
        Returns:
            絶対パスを使用する場合はTrue、相対パスを使用する場合はFalse
        """
        return False
    
    @abstractmethod
    def can_handle(self, path: str) -> bool:
        """
        指定されたパスをこのハンドラで処理できるかどうかを判定する
        
        Args:
            path: 判定対象のパス
            
        Returns:
            処理可能な場合はTrue、そうでなければFalse
        """
        pass
    
    def can_handle_bytes(self, data: bytes = None, path: str = None) -> bool:
        """
        バイトデータまたはパス指定でバイトデータ解凍が可能かどうかを判定する
        
        Args:
            data: 判定するバイトデータ（省略可能）
            path: 判定するファイルのパス（省略可能、拡張子での判定に使用）
            
        Returns:
            バイトデータから解凍可能な場合はTrue、そうでなければFalse
        """
        # デフォルトではバイトからの解凍をサポートしない
        return False
    
    @abstractmethod
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるエントリ（ファイル・ディレクトリ）のリストを返す
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            エントリ情報のリスト
        """
        pass
    
    def list_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のアーカイブデータからエントリのリストを返す
        
        Args:
            archive_data: アーカイブデータのバイト配列
            path: アーカイブ内のパス（デフォルトはルートディレクトリ）
            
        Returns:
            エントリ情報のリスト。サポートしていない場合は空リスト
        """
        # can_handle_bytesがFalseの場合は空のリストを返す
        if not self.can_handle_bytes(archive_data, path):
            print(f"{self.__class__.__name__}: バイトデータからのリスト取得はサポートしていません")
            return []
        # デフォルト実装は空のリストを返す（サブクラスでオーバーライドする）
        print(f"{self.__class__.__name__}: list_entries_from_bytes の実装が必要です")
        return []
        
    @abstractmethod
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        pass
    
    # read_fileを削除 - read_archive_fileを主要APIとして使用する
    
    def read_file_from_bytes(self, archive_data: bytes, file_path: str) -> Optional[bytes]:
        """
        メモリ上のアーカイブデータから特定のファイルを読み込む
        
        Args:
            archive_data: アーカイブデータのバイト配列
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容（バイト配列）。サポートしていないか読み込みに失敗した場合はNone
        """
        # can_handle_bytesがFalseの場合はNoneを返す
        if not self.can_handle_bytes(archive_data, file_path):
            print(f"{self.__class__.__name__}: バイトデータからのファイル読み込みはサポートしていません")
            return None
        # デフォルト実装はNoneを返す（サブクラスでオーバーライドする）
        print(f"{self.__class__.__name__}: read_file_from_bytes の実装が必要です")
        return None
        
    @abstractmethod
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        pass
    
    @abstractmethod
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む
        パスはハンドラによって相対パスまたは絶対パスとして扱われる
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容（バイト配列）。読み込みに失敗した場合はNone
        """
        pass
    
    @abstractmethod
    def is_directory(self, path: str) -> bool:
        """
        指定したパスがディレクトリかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、そうでない場合はFalse
        """
        pass
    
    @abstractmethod
    def get_parent_path(self, path: str) -> str:
        """
        指定したパスの親ディレクトリのパスを取得する
        
        Args:
            path: 親ディレクトリを取得するパス
            
        Returns:
            親ディレクトリのパス。親がない場合は空文字列
        """
        pass
    
    @abstractmethod
    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定したパスのアーカイブ内のすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        このメソッドはアーカイブ内のすべてのファイルとディレクトリを再帰的にリストアップし、
        階層構造を無視してフラットなリストとして返します。
        特にアーカイブ内の特定のファイルを検索する際に有用です。
        
        Args:
            path: アーカイブファイルのパス
            
        Returns:
            アーカイブ内のすべてのエントリのリスト
        """
        pass
    
    @abstractmethod
    def list_all_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のアーカイブデータからすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        このメソッドはアーカイブ内のすべてのファイルとディレクトリを再帰的にリストアップし、
        階層構造を無視してフラットなリストとして返します。特に検索機能で有用です。
        
        Args:
            archive_data: アーカイブデータのバイト配列
            path: ベースパス（結果のEntryInfoに反映される）
            
        Returns:
            アーカイブ内のすべてのエントリのリスト。サポートしていない場合は空リスト
        """
        pass
    
    # 以下は共通実装を提供（サブクラスで必要に応じてオーバーライド可能）
    def _split_path(self, path: str) -> Tuple[str, str]:
        """
        パスをアーカイブファイルのパスと内部パスに分割する
        
        Args:
            path: 分割するパス
            
        Returns:
            (アーカイブファイルのパス, 内部パス) のタプル
        """
        # 基本実装は空のパスを返す（通常ハンドラ実装でオーバーライドする必要あり）
        return "", ""
    
    def _join_paths(self, archive_path: str, internal_path: str) -> str:
        """
        アーカイブファイルのパスと内部パスを結合する
        
        Args:
            archive_path: アーカイブファイルのパス
            internal_path: 内部パス
            
        Returns:
            結合されたパス
        """
        # 内部パスが空なら、アーカイブファイルのパスをそのまま返す
        if not internal_path:
            return archive_path
            
        # アーカイブファイルのパスと内部パスを結合
        return f"{archive_path}/{internal_path}"
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """
        パスを正規化する
        
        Args:
            path: 正規化するパス
            
        Returns:
            正規化されたパス
        """
        # パスの区切り文字を統一
        normalized = path.replace('\\', '/')
        
        # 連続するスラッシュを1つに
        while '//' in normalized:
            normalized = normalized.replace('//', '/')
        
        # 末尾のスラッシュを除去
        if normalized.endswith('/') and len(normalized) > 1:
            normalized = normalized[:-1]
            
        return normalized
    
    def save_to_temp_file(self, content: bytes, extension: str) -> Optional[str]:
        """ 
        バイナリコンテンツを一時ファイルに保存する
        
        Args:
            content: 保存するコンテンツ
            extension: ファイルの拡張子 (.zip, .rar 等)
            
        Returns:
            一時ファイルのパス、または失敗時にNone
        """
        try:
            import tempfile
            import hashlib
            import os
            
            # 拡張子が与えられているか確認
            if not extension.startswith('.'):
                extension = '.' + extension
            
            # 一時ファイルを保存するディレクトリ
            temp_dir = os.path.join(tempfile.gettempdir(), "supraview_temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            # コンテンツのハッシュを計算して一意のファイル名を作る
            content_hash = hashlib.md5(content[:1024] if len(content) > 1024 else content).hexdigest()
            file_name = f"supraview_{content_hash}{extension}"
            temp_path = os.path.join(temp_dir, file_name)
            
            # ファイルに書き込む（バイナリモード）
            with open(temp_path, 'wb') as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())  # 確実にディスクに書き込む
            
            print(f"ArchiveHandler: コンテンツを一時ファイルに保存: {temp_path} ({len(content)} バイト)")
            
            # ファイル読み取り確認
            with open(temp_path, 'rb') as check_file:
                check_size = len(check_file.read())
                print(f"ArchiveHandler: 一時ファイル読み取り確認: {check_size} バイト")
                if check_size != len(content):
                    print(f"ArchiveHandler: 警告: 書き込みサイズと読み取りサイズが一致しません")
            
            return temp_path
        
        except Exception as e:
            print(f"ArchiveHandler: 一時ファイル作成エラー: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def cleanup_temp_file(self, temp_file_path: str) -> None:
        """
        一時ファイルを削除する
        
        Args:
            temp_file_path: 削除する一時ファイルのパス
        """
        try:
            import os
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                print(f"ArchiveHandler: 一時ファイルを削除: {temp_file_path}")
        except Exception as e:
            print(f"ArchiveHandler: 一時ファイル削除エラー: {e}")
    
    def needs_encoding_conversion(self) -> bool:
        """
        このハンドラが文字コード変換を必要とするかどうかを返す
        
        日本語ファイル名を含むアーカイブなど、ファイル名のエンコーディング変換が
        必要なアーカイブ形式の場合はTrueを返す
        
        Returns:
            文字コード変換が必要な場合はTrue、そうでなければFalse
        """
        return False
    
    def set_current_path(self, path: str) -> None:
        """
        現在のベースパスを設定する
        相対パスを解決する際に使用される
        
        Args:
            path: ベースパスとするディレクトリまたはファイルのパス
        """
        self.current_path = path
    
    def to_relative_path(self, abs_path: str) -> str:
        """
        絶対パスを現在のベースパスからの相対パスに変換する
        
        Args:
            abs_path: 変換する絶対パス
            
        Returns:
            相対パス（カレントパスからの相対）
        """
        if not abs_path:
            return ""
        
        # パスを正規化
        norm_path = self.normalize_path(abs_path)
        
        # カレントパスが設定されていない場合はそのまま返す
        if not self.current_path:
            return norm_path
        
        # カレントパスを正規化
        norm_current = self.normalize_path(self.current_path)
        
        # カレントパスでの接頭辞チェック
        if norm_path.startswith(norm_current):
            # カレントパスを除去（先頭のスラッシュも含む）
            rel_path = norm_path[len(norm_current):]
            # スラッシュで始まる場合は削除
            if rel_path.startswith('/'):
                rel_path = rel_path[1:]
            return rel_path
        
        # カレントパスの接頭辞がなければそのまま返す
        return norm_path
    
    def create_entry_info(self, name: str, abs_path: str, type: EntryType, **kwargs) -> EntryInfo:
        """
        相対パスを自動計算したEntryInfoオブジェクトを作成する
        
        Args:
            name: エントリの名前
            abs_path: エントリへの絶対パス
            type: エントリのタイプ
            **kwargs: その他のEntryInfo引数
            
        Returns:
            相対パスが設定されたEntryInfoオブジェクト
        """
        # 相対パスを計算
        rel_path = self.to_relative_path(abs_path)
        
        # EntryInfoオブジェクトを作成して返す
        return EntryInfo(
            name=name,
            path=abs_path,
            type=type,
            rel_path=rel_path,
            **kwargs
        )
    
    def can_archive(self) -> bool:
        """
        このハンドラがアーカイバとして機能するかどうかを返す
        
        アーカイバとして機能するハンドラは圧縮アーカイブファイルを直接扱える。
        FileSystemHandlerなどのアーカイブでないハンドラはFalseを返す。
        
        Returns:
            アーカイバとして機能する場合はTrue、そうでなければFalse
        """
        return True  # デフォルトではアーカイバとして機能する


class ArchiveManager:
    """
    複数のアーカイブハンドラを管理し、適切なハンドラを選択するクラス
    
    このクラスは、パスに応じて適切なハンドラを選択し、操作を委譲する
    """
    
    def __init__(self):
        """利用可能なアーカイブハンドラを初期化する"""
        self.handlers: List[ArchiveHandler] = []
        self.path_handler_cache: Dict[str, ArchiveHandler] = {}
    
    def register_handler(self, handler: ArchiveHandler) -> None:
        """
        新しいアーカイブハンドラを登録する
        
        Args:
            handler: 登録するハンドラ
        """
        self.handlers.append(handler)
    
    def clear_cache(self) -> None:
        """パスとハンドラのマッピングキャッシュをクリアする"""
        self.path_handler_cache.clear()
    
    def get_handler(self, path: str) -> Optional[ArchiveHandler]:
        """
        指定されたパスを処理できるハンドラを取得する
        
        Args:
            path: 処理対象のパス
            
        Returns:
            対応するハンドラ。対応するものがなければNone
        """
        # 正規化したパスを使用
        norm_path = ArchiveHandler.normalize_path(path)
        print(f"Getting handler for path: {norm_path}")
        
        # キャッシュを確認
        if norm_path in self.path_handler_cache:
            print(f"Handler found in cache: {self.path_handler_cache[norm_path].__class__.__name__}")   
            return self.path_handler_cache[norm_path]
        
        # パスを処理できるハンドラを探す
        for handler in self.handlers.__reversed__():
            if handler.can_handle(norm_path):
                # キャッシュに格納して返す
                self.path_handler_cache[norm_path] = handler
                print(f"Handler found: {handler.__class__.__name__}")
                return handler
            else:
                print(f"Handler cannot handle: {handler.__class__.__name__}")
        
        return None
    
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるエントリのリストを取得する
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        handler = self.get_handler(path)
        if (handler is not None):
            print(f"Getting entries by {handler.__class__.__name__}: {path}")
            return handler.list_entries(path)
        else:
            print(f"Handler not found for path: {path}")
        return []
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        handler = self.get_handler(path)
        if handler is not None:
            return handler.get_entry_info(path)
        return None
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定されたパスのファイルの内容を読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        handler = self.get_handler(path)
        if handler is not None:
            print(f"Reading file by {handler.__class__.__name__}: {path}")
            # アーカイブ内のファイルパスを判定
            parent_path = self.get_parent_path(path)
            entry_info = self.get_entry_info(parent_path)
            
            if entry_info and entry_info.is_archive:
                # アーカイブの中のファイルの場合
                print(f"Reading file inside archive: {path} (parent: {parent_path})")
                # アーカイブ内のファイルパスを取得
                relative_path = path[len(parent_path)+1:] if path.startswith(parent_path) else path
                return handler.read_archive_file(parent_path, relative_path)
            else:
                # 通常のファイル
                return handler.read_archive_file(path, "")
        return None
    
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        handler = self.get_handler(path)
        if handler is not None:
            return handler.get_stream(path)
        return None
    
    def is_archive(self, path: str) -> bool:
        """
        指定されたパスがアーカイブファイルかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            アーカイブファイルならTrue、そうでなければFalse
        """
        info = self.get_entry_info(path)
        return info is not None and info.is_archive
    
    def get_parent_path(self, path: str) -> str:
        """
        親ディレクトリのパスを取得する
        
        Args:
            path: 対象のパス
            
        Returns:
            親ディレクトリのパス
        """
        norm_path = ArchiveHandler.normalize_path(path)
        if not norm_path or norm_path == '/':
            return ''
        
        # 末尾のスラッシュを除去
        if norm_path.endswith('/'):
            norm_path = norm_path[:-1]
        
        # 最後のスラッシュの位置を取得
        last_slash = norm_path.rfind('/')
        if (last_slash > 0):
            return norm_path[:last_slash]
        elif (last_slash == 0):  # ルートディレクトリの直下
            return '/'
        else:
            return ''
    
    def is_directory(self, path: str) -> bool:
        """
        指定されたパスがディレクトリかどうかを判定する
        
        物理ファイルシステム上のディレクトリ、またはアーカイブ内のディレクトリの場合にTrueを返す
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、それ以外の場合はFalse
        """
        # 物理ファイルシステムのディレクトリかチェック
        if os.path.isdir(path):
            return True
        
        # アーカイブ内のパスの場合、エントリ情報を取得して判定
        entry_info = self.get_entry_info(path)
        if entry_info:
            return entry_info.type == EntryType.DIRECTORY or entry_info.type == EntryType.ARCHIVE
        
        # 存在しないパスの場合はFalseを返す
        return False
    
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        # アーカイブファイルを処理するハンドラを取得
        handler = self.get_handler(archive_path)
        if handler is None:
            print(f"ArchiveManager: アーカイブ {archive_path} に対応するハンドラが見つかりません")
            return None
        
        print(f"ArchiveManager: {handler.__class__.__name__} でアーカイブファイル読み込み: {archive_path}/{file_path}")
        
        # アーカイブ内のファイルを読み込む
        return handler.read_archive_file(archive_path, file_path)
    
    def _get_all_archive_extensions(self) -> List[str]:
        """すべてのハンドラがサポートするアーカイブ拡張子のリストを取得"""
        extensions = []
        for handler in self.handlers:
            extensions.extend(handler.supported_extensions)
        return list(set(extensions))  # 重複を削除