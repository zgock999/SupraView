"""
デコーダーの基本インターフェース

画像デコーダーが実装すべき基本インターフェース
"""

from typing import List, Optional, Tuple
import numpy as np

from .base import BaseDecoder

class ImageDecoder(BaseDecoder):
    """
    画像デコーダーの基本クラス
    
    すべての画像デコーダーの基底クラス
    """
    
    @property
    def supported_extensions(self) -> List[str]:
        """
        このデコーダーがサポートするファイル拡張子のリスト
        
        Returns:
            List[str]: サポートされている拡張子のリスト（ドット付き）
        """
        return []
    
    def decode(self, data: bytes) -> Optional[np.ndarray]:
        """
        バイトデータから画像をデコード
        
        Args:
            data: デコードする画像のバイトデータ
            
        Returns:
            Optional[np.ndarray]: デコードされた画像のnumpy配列、失敗した場合はNone
        """
        raise NotImplementedError("子クラスでオーバーライドする必要があります")
    
    def get_image_info(self, data: bytes) -> Optional[Tuple[int, int, int]]:
        """
        画像の基本情報を取得する
        
        Args:
            data (bytes): 情報を取得する画像のバイトデータ
            
        Returns:
            Optional[Tuple[int, int, int]]: (幅, 高さ, チャンネル数) の形式の情報、
                                           取得できない場合は None
        """
        pass
    
    def can_decode(self, extension: str) -> bool:
        """
        指定された拡張子をこのデコーダーで処理できるかチェックする
        
        Args:
            extension (str): チェックする拡張子（例: '.jpg'）
            
        Returns:
            bool: サポートしていれば True、そうでなければ False
        """
        return extension.lower() in self.supported_extensions
