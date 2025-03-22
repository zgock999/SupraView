"""
ArchiveFactoryクラス - ArchiveBrowserの生成を行うファクトリクラス
"""

from typing import List
from arc.manager.enhanced import EnhancedArchiveManager
from .browser import ArchiveBrowser

class ArchiveFactory:
    """
    ArchiveBrowserのファクトリクラス
    """
    
    @staticmethod
    def create_browser(manager: EnhancedArchiveManager, path: str = "", exts: List[str] = None, pages: int = 1, shift: bool = False) -> ArchiveBrowser:
        """
        ArchiveBrowserを作成する
        
        Args:
            manager: 拡張アーカイブマネージャー（必須）
            path: 初期パス（省略可）
            exts: 対象とする拡張子リスト（省略可）
            pages: ページ数（1または2のみ有効、デフォルトは1）
            shift: シフトフラグ（デフォルトはFalse）
            
        Returns:
            ArchiveBrowserインスタンス
        """
        return ArchiveBrowser(manager, path, exts, pages, shift)

def get_browser(manager: EnhancedArchiveManager, path: str = "", exts: List[str] = None, pages: int = 1, shift: bool = False) -> ArchiveBrowser:
    """
    ArchiveFactoryを使用してArchiveBrowserを返す
    
    Args:
        manager: 拡張アーカイブマネージャー（必須）
        path: 初期パス（省略可）
        exts: 対象とする拡張子リスト（省略可）
        pages: ページ数（1または2のみ有効、デフォルトは1）
        shift: シフトフラグ（デフォルトはFalse）
        
    Returns:
        ArchiveBrowserインスタンス
    """
    return ArchiveFactory.create_browser(manager, path, exts, pages, shift)
