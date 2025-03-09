"""
アーカイブハンドラの登録モジュール

このモジュールは、アーカイブマネージャーに標準ハンドラを登録する関数を提供します。
"""

from arc.arc import ArchiveManager
from arc.zip_handler import ZipHandler
from arc.fs_handler import FileSystemHandler
from arc.archive_7z_handler import Archive7zHandler
from arc.cbz_handler import CbzHandler
from arc.lzh_handler import LzhHandler
from arc.rar_handler import RarHandler


def register_standard_handlers(manager: ArchiveManager) -> None:
    """
    標準ハンドラをアーカイブマネージャーに登録する
    
    Args:
        manager: ハンドラを登録するArchiveManagerインスタンス
    """
    # ファイルシステムハンドラを登録（常に最初に登録）
    manager.register_handler(FileSystemHandler())
    print("ファイルシステムハンドラを登録しました")

    # 7-Zipハンドラを登録（RAR対応のため）
#    manager.register_handler(Archive7zHandler())
#    print("7-Zipアーカイブハンドラを登録しました")
        
    # RARハンドラを登録
    manager.register_handler(RarHandler())
    print("RARアーカイブハンドラを登録しました")
    
    # ZIPハンドラを登録
    manager.register_handler(ZipHandler())
    print("ZIPハンドラを登録しました")
    
    # LZHハンドラを登録
#    manager.register_handler(LzhHandler())
#    print("LZH/LHAアーカイブハンドラを登録しました")
    
    # CBZハンドラを登録
#    manager.register_handler(CbzHandler())
#    print("CBZ漫画アーカイブハンドラを登録しました")


def create_archive_manager() -> ArchiveManager:
    """
    標準ハンドラを登録したアーカイブマネージャを作成する
    
    Returns:
        設定済みのアーカイブマネージャ
    """
    manager = ArchiveManager()
    register_standard_handlers(manager)
    return manager