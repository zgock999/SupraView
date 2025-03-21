"""
超解像処理の基底クラス定義
"""
from enum import Enum
import os
import cv2
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
import time

class SRMethod(Enum):
    """超解像メソッド"""
    # OpenCVベーシック補間系
    OPENCV_NEAREST = "opencv_nearest"
    OPENCV_BILINEAR = "opencv_bilinear"
    OPENCV_CUBIC = "opencv_cubic"
    OPENCV_LANCZOS = "opencv_lanczos"

    # OpenCV DNN系
    OPENCV_EDSR = "opencv_edsr"
    OPENCV_ESPCN = "opencv_espcn"
    OPENCV_FSRCNN = "opencv_fsrcnn"
    OPENCV_LAPSRN = "opencv_lapsrn"

    # SwinIR系
    SWINIR_LIGHTWEIGHT = "swinir_lightweight"
    SWINIR_REAL = "swinir_real"
    SWINIR_LARGE = "swinir_large"  # SWINIR_REAL_LARGEからSWINIR_LARGEに統一
    SWINIR_CLASSICAL = "swinir_classical"
    
    # ESRGANモデル
    ESRGAN_GENERAL = "esrgan_general"  # 追加
    ESRGAN_ANIME = "esrgan_anime"      # 追加
    ESRGAN_PHOTO = "esrgan_photo"      # 追加
    
    # Real-ESRGAN
    REALESRGAN = "realesrgan"

class SRResult:
    """超解像処理結果"""
    def __init__(self, image: np.ndarray, processing_time: float, method: SRMethod,
                 scale: int, options: Optional[Dict[str, Any]] = None):
        """
        超解像処理結果の初期化
        
        Args:
            image: 処理結果画像
            processing_time: 処理にかかった時間（秒）
            method: 使用した超解像メソッド
            scale: スケール倍率
            options: その他のオプション情報
        """
        self.image = image
        self.processing_time = processing_time
        self.method = method
        self.scale = scale
        self.options = options or {}

class SuperResolutionBase:
    """超解像処理の基底クラス"""
    
    def __init__(self, scale: int = 2):
        """
        初期化
        
        Args:
            scale: 拡大倍率
        """
        self.scale = scale
        self._initialized = False
        
    @property
    def method(self) -> SRMethod:
        """使用しているメソッド"""
        return None
        
    def initialize(self, options: Dict[str, Any] = None) -> bool:
        """
        モデルの初期化
        
        Args:
            options: 初期化オプション
            
        Returns:
            bool: 初期化成功か
        """
        self._initialized = True
        return True
    
    def is_initialized(self) -> bool:
        """モデルが初期化されているか"""
        return self._initialized
        
    def process(self, image: np.ndarray, options: Dict[str, Any] = None) -> SRResult:
        """
        画像の超解像処理
        
        Args:
            image: 入力画像
            options: 処理オプション
            
        Returns:
            SRResult: 処理結果
        """
        if not self.is_initialized():
            if not self.initialize():
                raise RuntimeError("モデルの初期化に失敗しました")
        
        start_time = time.time()
        h, w = image.shape[:2]
        result = cv2.resize(image, (w * self.scale, h * self.scale))
        elapsed_time = time.time() - start_time
        
        return SRResult(
            image=result,
            processing_time=elapsed_time,
            method=self.method,
            scale=self.scale,
            options=options
        )
    
    def cleanup(self):
        """リソースの解放処理"""
        self._initialized = False
    
    @classmethod
    def create(cls, method: SRMethod, scale: int = 2, options: Dict[str, Any] = None) -> Optional['SuperResolutionBase']:
        """
        メソッドに応じた超解像処理インスタンスを生成
        
        Args:
            method: 超解像メソッド
            scale: 拡大倍率
            options: 初期化オプション
            
        Returns:
            SuperResolutionBase: 超解像処理インスタンス
        """
        # インポートは関数内で行い、循環参照を防ぐ
        options = options or {}
        
        # OpenCVベーシック補間系（sr_opencv.py）
        if method in [SRMethod.OPENCV_NEAREST, SRMethod.OPENCV_BILINEAR, 
                     SRMethod.OPENCV_CUBIC, SRMethod.OPENCV_LANCZOS]:
            from sr.sr_opencv import OpenCVSuperResolution
            return OpenCVSuperResolution(method=method, scale=scale)
        
        # OpenCV DNN系（sr_contrib.py）
        elif method in [SRMethod.OPENCV_EDSR, SRMethod.OPENCV_ESPCN, 
                       SRMethod.OPENCV_FSRCNN, SRMethod.OPENCV_LAPSRN]:
            try:
                from sr.sr_contrib import OpenCVDnnSuperResolution
                return OpenCVDnnSuperResolution(method=method, scale=scale)
            except ImportError:
                print(f"エラー: OpenCV DNN SuperRes モジュールが利用できません")
                return None
        
        # SwinIR系（sr_swinir.py）
        elif method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                       SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
            from sr.sr_swinir import SwinIRSuperResolution
            return SwinIRSuperResolution(method=method, scale=scale)
        
        # Real-ESRGAN (sr_realesrgan.py)
        elif method == SRMethod.REALESRGAN:
            from sr.sr_realesrgan import RealESRGANSuperResolution
            return RealESRGANSuperResolution(scale=scale)
        
        # その他の未実装メソッド
        else:
            print(f"警告: 未実装のメソッド {method.value} が指定されました")
            return None

    @classmethod
    def get_available_methods(cls) -> List[SRMethod]:
        """
        利用可能な超解像メソッドのリストを取得
        
        Returns:
            List[SRMethod]: 利用可能なメソッドリスト
        """
        methods = [
            SRMethod.OPENCV_NEAREST, 
            SRMethod.OPENCV_BILINEAR,
            SRMethod.OPENCV_CUBIC, 
            SRMethod.OPENCV_LANCZOS
        ]
        
        # OpenCV DNN系（存在確認）
        if hasattr(cv2, 'dnn_superres'):
            methods.extend([
                SRMethod.OPENCV_EDSR,
                SRMethod.OPENCV_ESPCN,
                SRMethod.OPENCV_FSRCNN,
                SRMethod.OPENCV_LAPSRN
            ])
        
        # PyTorchが必要なモデルの確認（SwinIRとReal-ESRGAN）
        try:
            import torch
            methods.extend([
                SRMethod.SWINIR_LIGHTWEIGHT,
                SRMethod.SWINIR_REAL,
                SRMethod.SWINIR_LARGE,  # SWINIR_REAL_LARGEからSWINIR_LARGEに統一
                SRMethod.SWINIR_CLASSICAL,
                SRMethod.REALESRGAN  # Real-ESRGANも追加
            ])
        except ImportError:
            pass
        
        return methods

    @classmethod
    def get_supported_scales(cls, method: SRMethod) -> List[int]:
        """
        指定した超解像メソッドでサポートされるスケール倍率のリストを取得
        
        Args:
            method: 超解像メソッド
            
        Returns:
            List[int]: サポートされるスケール倍率のリスト
        """
        # sr_utilsのget_method_supported_scalesを呼び出す
        from sr.sr_utils import get_method_supported_scales
        return get_method_supported_scales(method)

    def is_available(self) -> bool:
        """
        このSRモデルが利用可能かどうかを返す
        
        Returns:
            利用可能ならTrue
        """
        # 基底クラスではデフォルトでTrueを返す
        return True
