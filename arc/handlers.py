"""
標準ハンドラー登録

標準の各種アーカイブハンドラーをアーカイブマネージャーに登録する
"""

from .manager import ArchiveManager
from .handler.handler import ArchiveHandler

# 各ハンドラをインポート
def register_standard_handlers(manager: ArchiveManager) -> None:
    """
    標準のアーカイブハンドラを登録する
    
    Args:
        manager: ハンドラを登録するアーカイブマネージャー
    """
    # ファイルシステムハンドラ
    try:
        from .handler.fs_handler import FileSystemHandler
        print("FileSystemHandler登録中...")
        fs_handler = FileSystemHandler()
        manager.register_handler(fs_handler)
    except Exception as e:
        print(f"FileSystemHandler登録エラー: {e}")
    
    # ZIPハンドラ
    try:
        from .handler.zip_handler import ZipHandler
        print("ZipHandler登録中...")
        zip_handler = ZipHandler()
        manager.register_handler(zip_handler)
    except Exception as e:
        print(f"ZipHandler登録エラー: {e}")
    
    # RARハンドラ
    try:
        from .handler.rar_handler import RarHandler
        print("RarHandler登録中...")
        rar_handler = RarHandler()
        manager.register_handler(rar_handler)
    except Exception as e:
        print(f"RarHandler登録エラー: {e}")


def create_archive_manager() -> ArchiveManager:
    """
    標準ハンドラを登録したアーカイブマネージャを作成する
    
    Returns:
        設定済みのアーカイブマネージャ
    """
    manager = ArchiveManager()
    register_standard_handlers(manager)
    return manager