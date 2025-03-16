"""
アーカイブマネージャーインターフェース

アーカイブマネージャーの統一されたアクセスインターフェースを提供
"""

import os
from typing import List, Optional, BinaryIO, Dict

from .arc import EntryInfo, EntryType
from .handler.handler import ArchiveHandler

# シングルトンインスタンス
_instance = None

def get_archive_manager():
    """
    アプリケーション全体で共有するアーカイブマネージャーのシングルトンインスタンスを取得する
    
    Returns:
        設定済みのアーカイブマネージャー
    """
    global _instance
    
    if _instance is None:
        _instance = create_archive_manager()
    
    return _instance


def create_archive_manager():
    """
    新しいアーカイブマネージャーのインスタンスを作成する
    
    Returns:
        設定済みの新しいアーカイブマネージャー
    """
    # ここで直接 EnhancedArchiveManager をインポート (循環参照を避けるため遅延インポート)
    from .manager.enhanced import EnhancedArchiveManager
    from .handlers import register_standard_handlers
    
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


# 以下はすべて委譲メソッド - シングルトンインスタンスに処理を委ね、追加の機能を提供
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
            if dir_path:
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
    
    from .manager.enhanced import EnhancedArchiveManager
    # EnhancedArchiveManagerの場合のみキャッシュを取得
    if isinstance(manager, EnhancedArchiveManager):
        return manager.get_entry_cache()
    
    # 通常のArchiveManagerの場合は空の辞書を返す
    return {}
