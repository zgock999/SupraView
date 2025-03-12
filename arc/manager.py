"""
アーカイブマネージャーファクトリ

アーカイブマネージャーの生成と取得を行うファクトリモジュール
"""

import os
from typing import List, Optional, BinaryIO, Dict

from .arc import EntryInfo, EntryType
from .handler.handler import ArchiveHandler

# シングルトンインスタンス
_instance: 'ArchiveManager' = None


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


# インターフェース関数はinterface.pyに移動したため、ここではスタブのみを残す
def get_archive_manager():
    """アーカイブマネージャーのインスタンスを取得する (スタブ)"""
    from .interface import get_archive_manager as get_manager
    return get_manager()


def create_archive_manager():
    """新しいアーカイブマネージャーを作成する (スタブ)"""
    from .interface import create_archive_manager as create_manager
    return create_manager()


def reset_manager():
    """アーカイブマネージャーをリセットする (スタブ)"""
    from .interface import reset_manager as reset
    return reset()
