"""
一時ファイル管理コンポーネント

アーカイブ処理で使用される一時ファイルを管理します。
"""

import os
import tempfile
import atexit
from typing import Set, Optional

class TempFileManager:
    """
    一時ファイル管理クラス
    
    アーカイブ処理で生成される一時ファイルの作成、追跡、クリーンアップを行います。
    """
    
    def __init__(self, manager):
        """
        一時ファイル管理マネージャーを初期化する
        
        Args:
            manager: 親となるEnhancedArchiveManagerインスタンス
        """
        self._manager = manager
        # 一時ファイルパスの集合
        self._temp_files: Set[str] = set()
        
        # プログラム終了時にクリーンアップを実行するよう登録
        atexit.register(self.cleanup_all)
    
    def create_temp_file(self, content: bytes, extension: str = '.bin') -> Optional[str]:
        """
        一時ファイルを作成し、そのパスを追跡する
        
        Args:
            content: 一時ファイルに書き込む内容
            extension: ファイル拡張子（デフォルト: .bin）
            
        Returns:
            作成された一時ファイルのパス。失敗した場合はNone
        """
        try:
            # 拡張子の正規化（.から始まることを確認）
            if not extension.startswith('.'):
                extension = '.' + extension
            
            # tempfileを使用して一時ファイルを作成
            fd, temp_path = tempfile.mkstemp(suffix=extension)
            
            # ファイルを書き込みモードで開き、コンテンツを書き込む
            with os.fdopen(fd, 'wb') as f:
                f.write(content)
            
            # 一時ファイルのパスを追跡リストに追加
            self._temp_files.add(temp_path)
            self._manager.debug_info(f"一時ファイルを作成しました: {temp_path}")
            
            return temp_path
            
        except Exception as e:
            self._manager.debug_error(f"一時ファイル作成中にエラー: {e}", trace=True)
            return None
    
    def register_temp_file(self, file_path: str) -> bool:
        """
        既存の一時ファイルを追跡リストに追加する
        
        Args:
            file_path: 一時ファイルのパス
            
        Returns:
            成功した場合はTrue、失敗した場合はFalse
        """
        if not file_path or not os.path.exists(file_path):
            self._manager.debug_warning(f"登録できない一時ファイル: {file_path}")
            return False
            
        self._temp_files.add(file_path)
        self._manager.debug_info(f"一時ファイルを登録しました: {file_path}")
        return True
    
    def remove_temp_file(self, file_path: str) -> bool:
        """
        一時ファイルを削除し、追跡リストから削除する
        
        Args:
            file_path: 削除する一時ファイルのパス
            
        Returns:
            成功した場合はTrue、失敗した場合はFalse
        """
        if not file_path or file_path not in self._temp_files:
            return False
            
        try:
            # ファイルが存在するか確認
            if os.path.exists(file_path):
                # ファイルを削除
                os.unlink(file_path)
                self._manager.debug_info(f"一時ファイルを削除しました: {file_path}")
            
            # 追跡リストから削除
            self._temp_files.discard(file_path)
            return True
            
        except Exception as e:
            self._manager.debug_error(f"一時ファイル削除中にエラー: {e}", trace=True)
            return False
    
    def get_temp_files(self) -> Set[str]:
        """
        追跡中の一時ファイルのパスセットを取得する
        
        Returns:
            一時ファイルパスのセット
        """
        return self._temp_files.copy()
    
    def cleanup_all(self) -> None:
        """
        すべての一時ファイルを削除する
        
        主にプログラム終了時の処理として使用されます。
        """
        # 削除対象のパスをコピー（反復処理中にセットを変更するため）
        files_to_remove = self._temp_files.copy()
        
        for file_path in files_to_remove:
            self.remove_temp_file(file_path)
        
        self._manager.debug_info(f"一時ファイルのクリーンアップが完了しました")
