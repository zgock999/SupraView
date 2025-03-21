"""
OpenCV DNN SuperResolution実装
"""
import os
import cv2
import numpy as np
import time
from typing import Dict, Any, Optional
import traceback

from sr.sr_base import SuperResolutionBase, SRMethod, SRResult

class OpenCVDnnSuperResolution(SuperResolutionBase):
    """OpenCV DNN SuperResolutionを使用した超解像処理"""
    
    def __init__(self, method: SRMethod = SRMethod.OPENCV_EDSR, scale: int = 2):
        """
        初期化
        
        Args:
            method: 使用するSR手法 (OPENCV_EDSR, OPENCV_ESPCN, OPENCV_FSRCNN, OPENCV_LAPSRN)
            scale: 拡大倍率 (通常は2, 3, 4から選択)
        """
        # OpenCV DNN SuperResモジュールの存在確認
        if not hasattr(cv2, 'dnn_superres'):
            raise ImportError(
                "OpenCV DNN SuperResモジュールが見つかりません。"
                "opencv-contribをインストールしてください: pip install opencv-contrib-python"
            )
        
        super().__init__(scale)
        self._method = method
        self._sr = None
        self._initialized = False
        
        # サポートされるスケールのバリデーション
        supported_scales = self.get_supported_scales(method)
        if scale not in supported_scales:
            print(f"警告: {method.value} では拡大率 {scale} がサポートされていません。")
            print(f"サポートされている拡大率: {supported_scales}")
            # サポートされるスケールのうち最も近いものを選択
            if supported_scales:
                closest_scale = min(supported_scales, key=lambda x: abs(x - scale))
                print(f"拡大率を {closest_scale} に調整します。")
                self.scale = closest_scale
    
    @property
    def method(self) -> SRMethod:
        return self._method
    
    def _get_model_name_for_cv2(self) -> str:
        """OpenCV DNN SuperResの内部名を取得"""
        method_map = {
            SRMethod.OPENCV_EDSR: "edsr",
            SRMethod.OPENCV_ESPCN: "espcn",
            SRMethod.OPENCV_FSRCNN: "fsrcnn",
            SRMethod.OPENCV_LAPSRN: "lapsrn"
        }
        return method_map.get(self._method, "edsr")
    
    def _get_model_path(self) -> str:
        """モデルファイルのパスを取得"""
        # モデル命名規則: <model_name>_x<scale>.pb
        model_name = self._get_model_name_for_cv2().upper()
        model_filename = f"{model_name}_x{self.scale}.pb"
        
        # まず現在のディレクトリの下の'models'を探す
        current_dir_model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", model_filename)
        if os.path.exists(current_dir_model_path):
            return current_dir_model_path
            
        # システムのどこかにある可能性のあるパス
        search_paths = [
            os.path.join(os.path.expanduser("~"), "models", model_filename),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", model_filename),
            os.path.join("models", model_filename),
            model_filename
        ]
        
        # 最初に見つかったパスを返す
        for path in search_paths:
            if os.path.exists(path):
                return path
                
        # 見つからなければデフォルトパスを返す (initialize内でエラーにする)
        return current_dir_model_path
        
    def initialize(self, options: Dict[str, Any] = None) -> bool:
        """
        モデルの初期化
        
        Args:
            options: 初期化オプション
                model_path: カスタムモデルパス
                
        Returns:
            bool: 初期化成功か
        """
        try:
            options = options or {}
            model_path = options.get('model_path', self._get_model_path())
            
            if not os.path.exists(model_path):
                print(f"エラー: モデルファイルが見つかりません: {model_path}")
                return False
            
            # DNN SuperRes実装の作成
            self._sr = cv2.dnn_superres.DnnSuperResImpl_create()
            
            # モデルの読み込み
            model_name = self._get_model_name_for_cv2()
            print(f"モデルを読み込み中: {model_path}")
            self._sr.readModel(model_path)
            self._sr.setModel(model_name, self.scale)
            
            self._initialized = True
            print(f"モデル {model_name}_x{self.scale} の初期化に成功しました")
            return True
            
        except Exception as e:
            print(f"モデルの初期化に失敗しました: {str(e)}")
            traceback.print_exc()
            self._initialized = False
            return False
    
    def process(self, image: np.ndarray, options: Dict[str, Any] = None) -> SRResult:
        """
        画像の超解像処理
        
        Args:
            image: 入力画像
            options: 処理オプション (現在は使用していません)
            
        Returns:
            SRResult: 処理結果
        """
        if not self.is_initialized():
            if not self.initialize():
                print("モデルの初期化に失敗したため、通常のリサイズを使用します")
                return super().process(image, options)
        
        try:
            start_time = time.time()
            
            # 超解像処理の実行
            result = self._sr.upsample(image)
            
            processing_time = time.time() - start_time
            
            return SRResult(
                image=result,
                processing_time=processing_time,
                method=self.method,
                scale=self.scale,
                options=options
            )
        except Exception as e:
            print(f"超解像処理中にエラーが発生しました: {str(e)}")
            traceback.print_exc()
            
            # エラー時は通常のリサイズで代替
            return super().process(image, options)
    
    def cleanup(self):
        """リソースの解放処理"""
        self._sr = None
        self._initialized = False
    
    def is_available(self) -> bool:
        """
        OpenCV DNN SRモデルが利用可能かどうかを返す
        
        Returns:
            モデルがロードされていればTrue
        """
        return hasattr(self, 'sr') and self.sr is not None
    
    @staticmethod
    def get_supported_scales(method: SRMethod) -> list:
        """
        メソッドがサポートする拡大倍率のリストを取得
        
        Args:
            method: 超解像メソッド
            
        Returns:
            list: サポートされる拡大倍率のリスト
        """
        if method == SRMethod.OPENCV_EDSR:
            return [2, 3, 4]
        elif method == SRMethod.OPENCV_ESPCN:
            return [2, 3, 4]
        elif method == SRMethod.OPENCV_FSRCNN:
            return [2, 3, 4]
        elif method == SRMethod.OPENCV_LAPSRN:
            return [2, 4, 8]
        else:
            return []
    
    @classmethod
    def check_model_files_exist(cls) -> Dict[str, bool]:
        """
        すべてのモデルファイルの存在確認
        
        Returns:
            Dict[str, bool]: モデル名とファイルの存在状態を示す辞書
        """
        result = {}
        models = [
            ("EDSR_x2.pb", SRMethod.OPENCV_EDSR, 2),
            ("EDSR_x3.pb", SRMethod.OPENCV_EDSR, 3),
            ("EDSR_x4.pb", SRMethod.OPENCV_EDSR, 4),
            ("ESPCN_x2.pb", SRMethod.OPENCV_ESPCN, 2),
            ("ESPCN_x3.pb", SRMethod.OPENCV_ESPCN, 3),
            ("ESPCN_x4.pb", SRMethod.OPENCV_ESPCN, 4),
            ("FSRCNN_x2.pb", SRMethod.OPENCV_FSRCNN, 2),
            ("FSRCNN_x3.pb", SRMethod.OPENCV_FSRCNN, 3),
            ("FSRCNN_x4.pb", SRMethod.OPENCV_FSRCNN, 4),
            ("LapSRN_x2.pb", SRMethod.OPENCV_LAPSRN, 2),
            ("LapSRN_x4.pb", SRMethod.OPENCV_LAPSRN, 4),
            ("LapSRN_x8.pb", SRMethod.OPENCV_LAPSRN, 8)
        ]
        
        for model_file, method, scale in models:
            # モデルインスタンスを仮作成してパスを取得
            temp_instance = cls(method=method, scale=scale)
            model_path = temp_instance._get_model_path()
            exists = os.path.exists(model_path)
            result[model_file] = exists
            
        return result
