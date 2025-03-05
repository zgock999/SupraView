"""
画像デコーダーの基底クラス

バイトデータを numpy 配列の画像データに変換するための抽象基底クラス
各具体的なデコーダークラスはこのクラスを継承して実装する
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import List, Optional, Tuple


class ImageDecoder(ABC):
    """
    画像デコーダーの基底クラス
    
    バイトデータから画像の numpy 配列を生成する機能を提供する
    サポートする拡張子のリストを返すプロパティを持つ
    """
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """
        このデコーダーがサポートするファイル拡張子のリスト
        
        Returns:
            List[str]: サポートする拡張子のリスト（例: ['.jpg', '.jpeg']）
        """
        pass
    
    @abstractmethod
    def decode(self, data: bytes) -> Optional[np.ndarray]:
        """
        バイトデータを numpy 配列の画像に変換する
        
        Args:
            data (bytes): デコードする画像のバイトデータ
            
        Returns:
            Optional[np.ndarray]: デコードされた画像の numpy 配列、失敗した場合は None
                                  形状は (height, width, channels) の順
        """
        pass
    
    @abstractmethod
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
