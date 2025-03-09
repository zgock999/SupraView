"""
CBZ(コミックブックZIP)アーカイブハンドラ

CBZアーカイブファイルへのアクセスを提供するハンドラ
CBZはZIPファイルの一種で、コンテンツが漫画/コミック画像である
"""

import os
from typing import List, Optional

from .zip_handler import ZipHandler
from .arc import EntryInfo, EntryType


class CbzHandler(ZipHandler):
    """
    CBZ(Comic Book ZIP)アーカイブハンドラ
    
    ZIPハンドラを拡張し、CBZ形式のサポートを追加する
    CBZは基本的にZIPファイルだが、この特殊用途のために区別する
    """
    
    @property
    def supported_extensions(self) -> List[str]:
        """このハンドラがサポートするファイル拡張子のリスト"""
        return ['.cbz']
    
    def can_handle(self, path: str) -> bool:
        """
        このハンドラがパスを処理できるか判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            処理可能な場合はTrue、そうでない場合はFalse
        """
        if not os.path.isfile(path):
            return False
            
        # 拡張子で簡易判定
        _, ext = os.path.splitext(path.lower())
        if ext != '.cbz':
            return False
            
        # CBZファイルはZIPファイルなので、ZIPファイルとして開けるかどうか確認
        return super().can_handle(path.replace('.cbz', '.zip'))
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定したパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するパス
            
        Returns:
            エントリ情報、またはNone（取得できない場合）
        """
        # ZIPハンドラのget_entry_infoを呼び出す
        entry_info = super().get_entry_info(path)
        
        # CBZファイル自体の場合、タイプをARCHIVEに設定
        if entry_info and entry_info.name.lower().endswith('.cbz'):
            entry_info.type = EntryType.ARCHIVE
            
        return entry_info
    
    def _split_path(self, path: str):
        """
        パスをCBZファイルのパスと内部パスに分割する
        
        Args:
            path: 分割するパス
            
        Returns:
            (CBZファイルのパス, 内部パス) のタプル
        """
        # パスの正規化 (バックスラッシュをスラッシュに変換)
        norm_path = path.replace('\\', '/')
        
        # CBZファイル自体かどうか確認
        if os.path.isfile(norm_path) and norm_path.lower().endswith('.cbz'):
            # パス自体がCBZファイル
            return norm_path, ""
            
        # もっと厳密なパス解析を行う
        try:
            # パスを分解してCBZファイル部分を見つける
            parts = norm_path.split('/')
            
            # CBZファイルのパスを見つける
            cbz_path = ""
            internal_path_parts = []
            
            for i in range(len(parts)):
                # パスの部分を結合してテスト
                test_path = '/'.join(parts[:i+1])
                
                # CBZファイルかどうか確認
                if os.path.isfile(test_path) and test_path.lower().endswith('.cbz'):
                    cbz_path = test_path
                    # 残りの部分が内部パス
                    internal_path_parts = parts[i+1:]
                    break
            
            # CBZファイルが見つからなければ無効
            if not cbz_path:
                return "", ""
            
            # 内部パスを結合
            internal_path = '/'.join(internal_path_parts)
            
            return cbz_path, internal_path
        except Exception as e:
            print(f"CBZパス分解エラー: {str(e)}, パス: {path}")
            import traceback
            traceback.print_exc()
            return "", ""
