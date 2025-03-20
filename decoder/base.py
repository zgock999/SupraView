"""
デコーダーの基底クラス

すべての画像デコーダーが継承する基底クラスを定義しています。
"""

import os
import sys
from typing import List, Optional, Any
import numpy as np

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print, DEBUG, INFO, WARNING, ERROR


class BaseDecoder:
    """
    すべてのデコーダーの基底クラス
    """
    
    # サポートする拡張子のリスト（子クラスでオーバーライド）
    supported_extensions: List[str] = []
    
    def __init__(self):
        """デコーダーの初期化"""
        self.debug_mode = False
    
    def decode(self, data: bytes) -> np.ndarray:
        """
        バイトデータを受け取り、numpy配列にデコードする
        
        Args:
            data: デコードするバイトデータ
            
        Returns:
            デコードされた画像のnumpy配列（通常はRGB/RGBAのuint8配列）
            
        Raises:
            DecodingError: デコードに失敗した場合
        """
        raise NotImplementedError("子クラスでオーバーライドする必要があります")
    
    def can_decode(self, data: bytes) -> bool:
        """
        指定されたバイトデータがこのデコーダーでデコード可能かどうかを判定する
        
        Args:
            data: 判定するバイトデータ
            
        Returns:
            デコード可能な場合はTrue、そうでない場合はFalse
        """
        # 基本実装ではサポートしていない
        return False
