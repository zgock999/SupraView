"""
超解像処理のマネージャークラス
各種の超解像モデルを統合管理する
"""
import os
import time
import numpy as np
from typing import Dict, Any, Optional, List, Union

from sr.sr_base import SuperResolutionBase, SRMethod, SRResult
from app.constants import EsdrModel, EsdrScale
from sr.sr_utils import get_sr_method_from_string
class SRManager:
    """超解像処理を統合管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self._model = None
        self._sr_enabled = False
        self._model_type = EsdrModel.AUTO
        self._scale = None  # Noneの場合は自動スケール
        self._initialized = False
        self._last_options = {}
        self._debug_mode = False
        
        # 初期状態はモデルを作成するが初期化はしない
        self._create_model()
    
    def set_debug(self, debug_mode: bool):
        """デバッグモードを設定"""
        self._debug_mode = debug_mode
    
    def toggle_sr(self, enabled: bool):
        """超解像処理の有効/無効を切り替え"""
        if self._sr_enabled != enabled:
            self._sr_enabled = enabled
            if self._debug_mode:
                print(f"超解像処理を{'有効' if enabled else '無効'}にしました")
                
            if enabled and self._model and not self._initialized:
                # 有効化された場合は初期化を試みる
                self._initialize_model()
                
    def set_model(self, model_type: EsdrModel):
        """使用する超解像モデルを設定"""
        if self._model_type != model_type:
            self._model_type = model_type
            if self._debug_mode:
                print(f"超解像モデルを設定: {model_type}")
                
            # モデルタイプが変更された場合は再作成する
            self._create_model()
            
    def set_scale(self, scale: Optional[int]):
        """スケール値を設定"""
        if self._scale != scale:
            self._scale = scale
            if self._debug_mode:
                print(f"超解像スケールを設定: {scale or 'AUTO'}")

    def set_options(self, options: Dict[str, Any]):
        """オプションを設定"""
        if self._model is not None:
            self._model.options = options

    def _create_model(self, method: Optional[str] = None, options: Optional[Dict[str, Any]] = None, scale: Optional[int] = None):
        """
        モデルを作成する
        constants.pyのSR_METHOD_SETTINGSからデフォルト設定を取得して
        モデルインスタンスを直接作成する
        """
        # 既存のモデルがあればクリーンアップ
        if self._model is not None:
            self._model.cleanup()
            self._model = None
            
        # 初期化状態をリセット
        self._initialized = False
        
        try:
            if method is not None:
                print("ユーザー指定の超解像メソッドを使用します")
                selected_method = get_sr_method_from_string(method)
                selected_scale = scale or 2
                selected_options = options or {}
            else:
                # constants.pyからデフォルト設定を取得
                from app.constants import SR_METHOD_SETTINGS
                
                # 利用可能なメソッドのリストを取得
                available_methods = set(SuperResolutionBase.get_available_methods())
                
                # デフォルト設定を探す
                selected_method = None
                selected_options = {}
                selected_scale = self._scale or 2  # デフォルトは2倍
                
                # まずデフォルト設定を探す（デフォルトフラグがTrueのもの）
                for item in SR_METHOD_SETTINGS:
                    # 5要素タプル（名前、メソッド、オプション、スケール、デフォルトフラグ）として処理
                    if len(item) >= 5 and item[4] and get_sr_method_from_string(item[1]) in available_methods:
                        selected_method = get_sr_method_from_string(item[1])
                        selected_options = item[2].copy()
                        selected_scale = item[3] or selected_scale  # スケール値（指定がなければデフォルト値を維持）
                        if self._debug_mode:
                            print(f"デフォルト超解像メソッドを選択: {selected_method.name}, スケール: {selected_scale}")
                        break
                
                # デフォルト設定が見つからない場合は最初の利用可能なメソッドを使用
                if selected_method is None:
                    for item in SR_METHOD_SETTINGS:
                        if get_sr_method_from_string(item[1]) in available_methods:
                            selected_method = get_sr_method_from_string(item[1])
                            selected_options = item[2].copy()
                            # 5要素タプルの場合はスケール値も取得
                            if len(item) >= 4:
                                selected_scale = item[3] or selected_scale
                            if self._debug_mode:
                                print(f"利用可能な最初の超解像メソッドを選択: {selected_method.name}, スケール: {selected_scale}")
                            break
                
            # 選択されたメソッドがまだない場合（何も利用できない）
            if selected_method is None:
                if self._debug_mode:
                    print("利用可能な超解像メソッドが見つかりません。モデル作成をスキップします。")
                return
            
            # 選択されたメソッドとオプションを出力
            if self._debug_mode:
                print(f"選択された超解像メソッド: {selected_method.name}, オプション: {selected_options}, スケール: {selected_scale}")
            
            # スケール値を設定（ユーザー指定のスケールを優先）
            final_scale = self._scale or selected_scale
            
            # 選択されたメソッドに合わせてSuperResolutionBaseのサブクラスを作成
            self._model = SuperResolutionBase.create(selected_method, final_scale, selected_options)
            
            if self._model is not None:
                if self._debug_mode:
                    print(f"モデル作成成功: {type(self._model).__name__}")
                # モデルのオプション辞書を初期化
                if not hasattr(self._model, 'options'):
                    self._model.options = {}
                # 選択されたオプションを設定
                self._model.options.update(selected_options)
                self._model.initialize(self._model.options)
            else:
                print(f"モデル '{selected_method.name}' の作成に失敗しました")
                
        except Exception as e:
            print(f"モデル作成中にエラー: {e}")
            if self._debug_mode:
                import traceback
                traceback.print_exc()
            self._model = None
            self._initialized = False
    
    def _initialize_model(self):
        """モデルの初期化"""
        if self._model is None:
            if self._debug_mode:
                print("モデルがNoneのため初期化できません")
            return False
            
        try:
            # 初期化オプションを設定
            options = {
                'use_cuda': True,  # GPUを使用
                'half_precision': False,  # 半精度計算を使用するか
                'auto_download': True,  # モデルを自動ダウンロード
            }
            
            # スケール値を設定
            if self._scale is not None:
                options['scale'] = self._scale
                
            # モデルを初期化
            success = self._model.initialize(options)
            
            if success:
                self._initialized = True
                self._last_options = options
                if self._debug_mode:
                    print(f"モデル初期化に成功しました: {type(self._model).__name__}")
            else:
                print(f"モデル初期化に失敗しました: {type(self._model).__name__}")
                
            return success
            
        except Exception as e:
            print(f"モデル初期化中にエラー: {e}")
            if self._debug_mode:
                import traceback
                traceback.print_exc()
            self._initialized = False
            return False
    
    def process_image(self, image: np.ndarray, options: Dict[str, Any] = None) -> Optional[np.ndarray]:
        """
        画像の超解像処理を実行
        
        Args:
            image: 入力画像 (BGR形式)
            options: 処理オプション
            
        Returns:
            Optional[np.ndarray]: 処理された画像またはNone（処理失敗時）
        """
        if not self._sr_enabled:
            # 超解像処理が無効の場合はNoneを返す
            return None
            
        if self._model is None:
            # モデルがない場合は再作成を試みる
            self._create_model()
            if self._model is None:
                # 再作成に失敗した場合
                print("モデル作成に失敗したため処理できません")
                return None
        
        # モデルが初期化されていない場合は初期化
        if not self._initialized or not self._model.is_initialized():
            success = self._initialize_model()
            if not success:
                print("モデル初期化に失敗したため処理できません")
                return None
        
        # オプションを設定
        process_options = options or {}
        
        # スケールが設定されていればオプションに追加
        if self._scale is not None:
            process_options['outscale'] = self._scale
        
        try:
            # 処理実行
            start_time = time.time()
            result = self._model.process(image, process_options)
            processing_time = time.time() - start_time
            
            if self._debug_mode:
                print(f"超解像処理完了: {processing_time:.2f}秒")
            
            if result and hasattr(result, 'image'):
                return result.image
            return None
            
        except Exception as e:
            print(f"超解像処理中にエラーが発生しました: {e}")
            if self._debug_mode:
                import traceback
                traceback.print_exc()
            return None
    
    def cleanup(self):
        """リソースを解放"""
        if self._model is not None:
            self._model.cleanup()
            self._model = None
        self._initialized = False
