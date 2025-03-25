"""
超解像処理を管理するクラス
app.viewerから超解像処理モジュールsrを使うためのインターフェース
"""
import os
import time
import cv2
import numpy as np
from typing import Dict, Any, Optional, List, Union, Tuple

# sr関連のインポート
from sr.sr_base import SuperResolutionBase, SRMethod, SRResult
from sr.sr_utils import is_cuda_available, get_gpu_info, get_sr_method_from_string

class SuperResolutionManager:
    """
    超解像処理を管理するクラス
    app.viewerのためのsr管理インターフェース
    """
    
    def __init__(self):
        """初期化"""
        self._model = None
        self._method = None
        self._scale = 2  # デフォルトは2倍
        self._initialized = False
        self._options = {}
        
    def initialize(self, method: SRMethod, scale: int = 2, options: Dict[str, Any] = None) -> bool:
        """
        超解像モデルを初期化する
        
        Args:
            method: 使用する超解像メソッド
            scale: 拡大倍率
            options: 初期化オプション
            
        Returns:
            bool: 初期化に成功したかどうか
        """
        try:
            # 既存のモデルがあればクリーンアップ
            if self._model is not None:
                self._model.cleanup()
                self._model = None
                
            self._method = method
            self._scale = scale
            self._options = options or {}
            self._initialized = False
            
            # モデルを作成
            self._model = SuperResolutionBase.create(method, scale, self._options)
            
            # モデルの初期化
            if self._model is not None:
                if self._model.initialize(self._options):
                    self._initialized = True
                    print(f"超解像モデル初期化成功: {method.name}, 倍率: {scale}")
                    return True
                else:
                    print(f"超解像モデル初期化失敗: {method.name}")
            else:
                print(f"超解像モデル作成失敗: {method.name}")
            
            return False
            
        except Exception as e:
            print(f"超解像モデル初期化エラー: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def process(self, image: np.ndarray, options: Dict[str, Any] = None) -> Optional[SRResult]:
        """
        画像の超解像処理を実行
        
        Args:
            image: 入力画像 (BGR形式)
            options: 処理オプション
            
        Returns:
            Optional[SRResult]: 処理結果、または失敗時はNone
        """
        if not self._initialized or self._model is None:
            print("モデルが初期化されていません")
            return None
            
        try:
            # オプションを結合
            process_options = self._options.copy()
            if options:
                process_options.update(options)
                
            # 処理を実行
            result = self._model.process(image, process_options)
            return result
            
        except Exception as e:
            print(f"超解像処理エラー: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def cleanup(self):
        """リソースを解放"""
        if self._model is not None:
            self._model.cleanup()
            self._model = None
        self._initialized = False
        
    @property
    def is_initialized(self) -> bool:
        """初期化済みかどうか"""
        return self._initialized and self._model is not None
    
    @property
    def method(self) -> Optional[SRMethod]:
        """現在のメソッド"""
        return self._method
        
    @property
    def scale(self) -> int:
        """現在の拡大倍率"""
        return self._scale
    
    @staticmethod
    def get_available_methods() -> List[SRMethod]:
        """
        利用可能な超解像メソッドのリストを取得
        
        Returns:
            List[SRMethod]: 利用可能なメソッドのリスト
        """
        return SuperResolutionBase.get_available_methods()
    
    @staticmethod
    def get_supported_scales(method: SRMethod) -> List[int]:
        """
        指定したメソッドでサポートされる拡大倍率を取得
        
        Args:
            method: 超解像メソッド
            
        Returns:
            List[int]: サポートされる拡大倍率のリスト
        """
        return SuperResolutionBase.get_supported_scales(method)
    
    @staticmethod
    def get_method_from_string(method_str: str) -> Optional[SRMethod]:
        """
        文字列からSRMethodを取得
        
        Args:
            method_str: メソッド名の文字列
            
        Returns:
            Optional[SRMethod]: 対応するSRMethod、または存在しない場合はNone
        """
        return get_sr_method_from_string(method_str)
    
    @staticmethod
    def is_cuda_available() -> bool:
        """CUDAが利用可能かどうかを確認"""
        return is_cuda_available()
    
    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        """GPU情報を取得"""
        return get_gpu_info()
