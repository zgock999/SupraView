"""
SupraView アーカイブ処理モジュール

様々なアーカイブフォーマットに対応する統一インターフェースを提供
"""

# 基本型のみをインポート (循環参照を避けるため)
from .arc import EntryType, EntryInfo

# インターフェース関数をインポート
from .interface import get_archive_manager, create_archive_manager, reset_manager

__all__ = [
    'EntryInfo', 'EntryType',
    'get_archive_manager', 'create_archive_manager', 'reset_manager'
]
