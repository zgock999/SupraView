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
    def create_browser(manager: EnhancedArchiveManager, path: str = "", exts: List[str] = None) -> ArchiveBrowser:
        """
        ArchiveBrowserを作成する
        
        Args:
            manager: 拡張アーカイブマネージャー（必須）
            path: 初期パス（省略可）
            exts: 対象とする拡張子リスト（省略可）
            
        Returns:
            ArchiveBrowserインスタンス
        """
        return ArchiveBrowser(manager, path, exts)

def get_browser(manager: EnhancedArchiveManager, path: str = "", exts: List[str] = None) -> ArchiveBrowser:
    """
    ArchiveFactoryを使用してArchiveBrowserを返す
    
    Args:
        manager: 拡張アーカイブマネージャー（必須）
        path: 初期パス（省略可）
        exts: 対象とする拡張子リスト（省略可）
        
    Returns:
        ArchiveBrowserインスタンス
    """
    return ArchiveFactory.create_browser(manager, path, exts)
