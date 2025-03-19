"""
エントリファイナライザコンポーネント

ハンドラから返されたエントリの最終処理を担当します。
"""

from typing import List

from ...arc import EntryInfo, EntryType

class EntryFinalizer:
    """
    エントリファイナライザクラス
    
    エントリの最終処理を行い、適切な形式に整形します。
    """
    
    def __init__(self, manager):
        """
        エントリファイナライザを初期化する
        
        Args:
            manager: 親となるEnhancedArchiveManagerインスタンス
        """
        self._manager = manager
    
    def finalize_entry(self, entry: EntryInfo, archive_path: str) -> EntryInfo:
        """
        ハンドラから帰ってきた未完成のエントリを完成させ、追加処理を行う
        
        Args:
            entry: 処理するエントリ
            archive_path: アーカイブ/フォルダの絶対パス
            
        Returns:
            最終処理後のエントリ
        """
        # 基本的なファイナライズ処理を親クラスに委譲
        # superの代わりにself._managerの親クラスの実装を呼び出す
        entry = self._manager.__class__.__bases__[0].finalize_entry(self._manager, entry, archive_path)
        
        # ファイルの場合、アーカイブかどうかを判定
        if entry.type == EntryType.FILE and self._manager._is_archive_by_extension(entry.name):
            entry.type = EntryType.ARCHIVE
        
        return entry

    def finalize_entries(self, entries: List[EntryInfo], archive_path: str) -> List[EntryInfo]:
        """
        ハンドラから帰ってきた未完成のエントリリストを完成させる
        
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
