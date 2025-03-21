"""
OpenCV基本機能を使った超解像処理クラス
"""
import cv2
import numpy as np
import time
from typing import Dict, Any, List

# モジュールのインポートパスを修正
from sr.sr_base import SuperResolutionBase, SRMethod, SRResult


class OpenCVSuperResolution(SuperResolutionBase):
    """
    OpenCVの基本リサイズ機能を使った超解像処理クラス
    高速だが品質は低め
    """
    
    def __init__(self, method: SRMethod, scale: int = 4):
        """
        初期化
        
        Args:
            sr_method: 超解像手法（OpenCV系のいずれか）
            scale: 拡大倍率
        """
        super().__init__(scale)
        self._sr_method = method
        self._interpolation_method = None
        self._initialized = False
    
    @property
    def method(self) -> SRMethod:
        return self._sr_method
    
    def initialize(self, options: Dict[str, Any] = None) -> bool:
        """
        初期化処理
        
        Args:
            options: 初期化オプション (未使用)
            
        Returns:
            bool: 初期化成功かどうか
        """
        # 補間方法を決定
        if self._sr_method == SRMethod.OPENCV_CUBIC:
            self._interpolation_method = cv2.INTER_CUBIC
        elif self._sr_method == SRMethod.OPENCV_LANCZOS:
            self._interpolation_method = cv2.INTER_LANCZOS4
        elif self._sr_method == SRMethod.OPENCV_NEAREST:
            self._interpolation_method = cv2.INTER_NEAREST
        elif self._sr_method == SRMethod.OPENCV_LINEAR:
            self._interpolation_method = cv2.INTER_LINEAR
        elif self._sr_method == SRMethod.OPENCV_AREA:
            self._interpolation_method = cv2.INTER_AREA
        else:
            # サポート外の方法
            return False
            
        self._initialized = True
        return True
    
    def process(self, image: np.ndarray, options: Dict[str, Any] = None) -> SRResult:
        """
        画像の超解像処理
        
        Args:
            image: 入力画像 (BGR形式)
            options: 処理オプション (未使用)
            
        Returns:
            SRResult: 処理結果
        """
        if not self._initialized:
            self.initialize()
            
        start_time = time.time()
        
        # 画像の高さと幅を取得
        h, w = image.shape[:2]
        
        # 拡大後のサイズを計算
        new_h = int(h * self.scale)
        new_w = int(w * self.scale)
        
        # リサイズ処理
        resized = cv2.resize(image, (new_w, new_h), interpolation=self._interpolation_method)
        
        # 処理時間を計測
        elapsed_time = time.time() - start_time
        
        return SRResult(
            image=resized,
            processing_time=elapsed_time,
            method=self._sr_method,
            scale=self.scale,
            options=options
        )
    
    def cleanup(self):
        """リソースの解放処理 - OpenCVは解放不要"""
        pass

    def is_available(self) -> bool:
        """
        OpenCV補間処理は常に利用可能
        
        Returns:
            常にTrue
        """
        return True

