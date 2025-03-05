"""
OpenCV を使用した汎用画像デコーダー

OpenCV（cv2）を使用して、様々な一般的な画像フォーマットに対応するデコーダー実装
"""

import cv2
import numpy as np
from io import BytesIO
from typing import List, Optional, Tuple

from .decoder import ImageDecoder


class CV2ImageDecoder(ImageDecoder):
    """
    OpenCV を使用した画像デコーダー
    
    OpenCV がサポートするほとんどの一般的な画像形式に対応している
    """
    
    @property
    def supported_extensions(self) -> List[str]:
        """
        OpenCV がサポートする画像形式の拡張子リスト
        
        Returns:
            List[str]: サポートされている拡張子のリスト
        """
        return [
            '.bmp', '.dib',           # Windows ビットマップ
            '.jpg', '.jpeg', '.jpe',  # JPEG ファイル
            '.jp2',                   # JPEG 2000 ファイル
            '.png',                   # Portable Network Graphics
            '.webp',                  # WebP
            '.pbm', '.pgm', '.ppm',   # Portable image format
            '.pxm', '.pnm',           # Portable image format (拡張)
            '.sr', '.ras',            # Sun rasters
            '.tiff', '.tif',          # TIFF ファイル
            '.exr',                   # OpenEXR 画像ファイル
            '.hdr', '.pic'            # Radiance HDR
        ]
    
    def decode(self, data: bytes) -> Optional[np.ndarray]:
        """
        バイトデータを OpenCV を用いて numpy 配列の画像に変換する
        
        Args:
            data (bytes): デコードする画像のバイトデータ
            
        Returns:
            Optional[np.ndarray]: デコードされた画像の numpy 配列
                                  BGR から RGB に変換して返す
                                  デコードに失敗した場合は None
        """
        try:
            # バイトデータを numpy 配列に変換
            nparr = np.frombuffer(data, np.uint8)
            # OpenCV で画像としてデコード (BGR 形式)
            img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
            
            if img is None:
                return None
                
            # アルファチャンネルの有無を確認
            if len(img.shape) == 2:  # グレースケール
                # グレースケール画像を3チャンネルRGBに変換
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            elif img.shape[2] == 3:  # BGR
                # BGR から RGB に変換
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            elif img.shape[2] == 4:  # BGRA
                # BGRA から RGBA に変換
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                
            return img
        except Exception as e:
            print(f"画像デコードエラー: {e}")
            return None
    
    def get_image_info(self, data: bytes) -> Optional[Tuple[int, int, int]]:
        """
        画像の基本情報を取得する
        
        Args:
            data (bytes): 情報を取得する画像のバイトデータ
            
        Returns:
            Optional[Tuple[int, int, int]]: (幅, 高さ, チャンネル数) の形式の情報
                                           取得できない場合は None
        """
        try:
            # バイトデータを numpy 配列に変換
            nparr = np.frombuffer(data, np.uint8)
            # OpenCV で画像としてデコード
            img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
            
            if img is None:
                return None
                
            # 画像の形状から情報を取得
            if len(img.shape) == 2:  # グレースケール
                height, width = img.shape
                channels = 1
            else:
                height, width, channels = img.shape
                
            return (width, height, channels)
        except Exception as e:
            print(f"画像情報取得エラー: {e}")
            return None
