"""
Real-ESRGANを使用した超解像処理の実装
Real-ESRGANは特有の前処理、後処理が必要なため専用クラスを用意
"""
import os
import cv2
import numpy as np
import torch
import time
import hashlib  # hashlib モジュールを import
import shutil
import urllib.request
from typing import Dict, Any, Optional, Union, Tuple, List
from sr.sr_base import SuperResolutionBase, SRMethod, SRResult
from tqdm import tqdm


class RealESRGANSuperResolution(SuperResolutionBase):
    """Real-ESRGANによる超解像処理クラス"""
    
    def __init__(self, scale: int = 4):
        """
        Args:
            scale: 拡大倍率（2または4）
        """
        # サポートするスケーリング係数を確認
        supported_scales = self.get_supported_scales(SRMethod.REALESRGAN)
        if scale not in supported_scales:
            raise ValueError(f"Real-ESRGANでは拡大倍率 {scale} はサポートされていません。対応倍率: {supported_scales}")
        
        super().__init__(scale)
        self._method = SRMethod.REALESRGAN
        self._model = None
        self._face_enhancer = None  # 顔強調モデル
        self._device = None
        self._last_options_hash = None  # 前回のオプションハッシュ
        
        # モデルURLの初期化
        self._init_model_urls()
    
    @classmethod
    def get_supported_scales(cls, method: SRMethod) -> List[int]:
        """Real-ESRGANがサポートする拡大倍率を返す"""
        return [2, 4]
    
    def _init_model_urls(self):
        """モデルのダウンロードURL辞書を初期化"""
        self._model_urls = {
            # 標準 Real-ESRGAN
            "RealESRGAN_x4plus.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            # アニメ向け Real-ESRGAN
            "RealESRGAN_x4plus_anime_6B.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
            # 顔修復用 GFPGAN
            "GFPGANv1.3.pth":
                "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth",
               
            # 動画向け Real-ESRGAN
            "realesr-animevideov3.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",

            "realesr-general-x4v3.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        }
    
    @property
    def method(self) -> SRMethod:
        return self._method
    
    def initialize(self, options: Dict[str, Any] = None) -> bool:
        """
        Real-ESRGANモデルを初期化
        
        Args:
            options: 初期化オプション
              - use_cuda: GPUを使用するか (bool、デフォルトはTrue)
              - model_path: カスタムモデルパス (文字列、指定しない場合はデフォルトのパスを使用)
              - half_precision: 半精度（FP16）を使用するか (bool、デフォルトはFalse)
              - auto_download: モデルが見つからない場合に自動ダウンロードするか (bool、デフォルトはTrue)
              - variant: Real-ESRGANのバリアント ('standard', 'anime', 'video', 'denoise' など)
              - face_enhance: 顔強調を使用するか (bool、デフォルトはFalse)
              - denoise_strength: デノイズ強度（0.0～1.0、デフォルトは0.5）
              
        Returns:
            bool: 初期化成功か
        """
        try:
            # オプションの更新
            options = options or {}
            print(f"RealESRGAN初期化オプション: {options}")
            
            # ハッシュ計算前に重要な値を出力して確認
            if 'denoise_strength' in options:
                print(f"初期化オプションのデノイズ強度: {options['denoise_strength']}")
            
            # デノイズ強度の設定があれば反映（UXの向上）
            if 'denoise_strength' in options and options.get('variant', '') == 'denoise':
                # デノイズ強度を0.0〜1.0の範囲に制限
                denoise_strength = max(0.0, min(1.0, float(options['denoise_strength'])))
                # DNIウェイトを計算（デノイズ強度が高いほど、wdnモデルの比率が高くなる）
                options['dni_weight'] = [denoise_strength, 1.0 - denoise_strength]
                print(f"デノイズ強度を設定: {denoise_strength} (DNIウェイト: {options['dni_weight']})")
            
            # デバイスの設定
            use_cuda = options.get('use_cuda', True)
            old_device = self._device
            new_device = torch.device('cuda' if use_cuda and torch.cuda.is_available() else 'cpu')
            
            # デバイスが変更された場合は強制的に再初期化
            if old_device != new_device and (self._model is not None or self._face_enhancer is not None):
                print(f"デバイスが変更されたため ({old_device} → {new_device})、モデルを再初期化します。")
                self._model = None
                self._face_enhancer = None
                self._initialized = False
                if old_device is not None and old_device.type == 'cuda':
                    # 古いGPUメモリをクリア
                    torch.cuda.empty_cache()
                
            # 既に初期化済みかどうかをチェック
            options_hash = self._calculate_options_hash(options)
            # ハッシュ値をデバッグ出力
            print(f"新しいハッシュ値: {options_hash}")
            print(f"前回のハッシュ値: {self._last_options_hash if hasattr(self, '_last_options_hash') else 'None'}")
            
            if self._initialized and self._model is not None:
                # モデルが既に存在し、初期化済みの場合は、オプションをチェックして再利用可能か確認
                if options_hash == self._last_options_hash:
                    print(f"Real-ESRGANモデルはすでに初期化済みです。再利用します。")
                    # 明示的に初期化成功を返す
                    return True
                else:
                    print(f"Real-ESRGANモデルの設定が変更されたため再初期化します。")
                    # 変更点の詳細を表示（デバッグ用）
                    if 'variant' in options:
                        print(f"- バリアント: {options.get('variant')}")
                    if 'denoise_strength' in options:
                        print(f"- デノイズ強度: {options.get('denoise_strength')}")
                    if 'face_enhance' in options:
                        print(f"- 顔強調: {options.get('face_enhance')}")
                    if 'dni_weight' in options:
                        print(f"- DNIウェイト: {options.get('dni_weight')}")
                    
                    # 古いモデルをクリア
                    self._model = None
                    self._face_enhancer = None
                    self._initialized = False
                    if self._device is not None and self._device.type == 'cuda':
                        torch.cuda.empty_cache()
            
            self._last_options_hash = options_hash
            self._device = new_device
            
            # 半精度の設定
            half_precision = options.get('half_precision', False)
            
            # バリアント設定（standard, anime, video, denoise）
            variant = options.get('variant', 'denoise')
            print(f"選択されたバリアント: {variant}")
            
            # モデルパスとパラメータを取得
            model_info = self._get_model_info(variant)
            
            # デノイズ強度が指定されている場合、DNIウェイトを上書き
            if 'dni_weight' in options and variant == 'denoise':
                model_info['dni_weight'] = options['dni_weight']
                
            model_path = options.get('model_path', model_info['model_path'])
            
            # モデルパスの存在確認と自動ダウンロード
            auto_download = options.get('auto_download', True)
            if not os.path.exists(model_path):
                if auto_download:
                    if not self.ensure_model(model_path):
                        raise FileNotFoundError(f"モデルが見つからず、ダウンロードにも失敗しました: {model_path}")
                else:
                    raise FileNotFoundError(f"モデルが見つかりません: {model_path}")
            
            # WDNモデルが必要な場合は、そのファイルの存在も確認
            # デノイズモードでDNIウェイトが指定されている場合のみ必要
            if variant == 'denoise' and 'model_path_wdn' in model_info and 'dni_weight' in model_info:
                wdn_path = model_info['model_path_wdn']
                if not os.path.exists(wdn_path):
                    if auto_download:
                        print(f"デノイズウェイトモデル {os.path.basename(wdn_path)} をダウンロードしています...")
                        if not self.ensure_model(wdn_path):
                            print(f"警告: WDNモデルのダウンロードに失敗しました: {wdn_path}")
                            # WDNモデルがなければ、単一モデルモードで実行（DNIウェイトを使用しない）
                            if 'dni_weight' in model_info:
                                print("DNIウェイトを無効化し、単一モデルモードで実行します")
                                del model_info['dni_weight']
                                # デノイズ強度の警告（単一モデルではデノイズ強度は調整できない）
                                if 'denoise_strength' in options:
                                    print(f"警告: デノイズウェイトモデルが利用できないため、デノイズ強度 {options.get('denoise_strength')} は無視されます")
                    else:
                        print(f"WDNモデルが見つからず、auto_downloadは無効です。DNIウェイトを無効化します: {wdn_path}")
                        # WDNモデルがなければ、単一モデルモードで実行
                        if 'dni_weight' in model_info:
                            del model_info['dni_weight']
            
            # 顔強調オプション
            face_enhance = options.get('face_enhance', False)
            
            # モデルの初期化
            self._initialize_realesrgan(model_path, model_info, half_precision)
            
            # 顔強調モデルの初期化（オプション）
            if face_enhance:
                self._initialize_face_enhancer(half_precision)
            
            # 初期化成功のフラグを設定
            self._initialized = True
            print(f"Real-ESRGANモデルの初期化に成功しました")
            
            # モデル情報の詳細をログ出力（デバッグ用）
            print(f"- バリアント: {variant}")
            print(f"- 半精度モード: {half_precision}")
            print(f"- 顔強調: {face_enhance}")
            if 'dni_weight' in model_info:
                print(f"- DNIウェイト: {model_info['dni_weight']}")
                
            return True
            
        except Exception as e:
            print(f"Real-ESRGANの初期化に失敗しました: {e}")
            import traceback
            traceback.print_exc()
            self._initialized = False
            self._model = None
            self._face_enhancer = None
            return False
    
    def _initialize_realesrgan(self, model_path: str, model_info: Dict[str, Any], half_precision: bool) -> None:
        """
        Real-ESRGANモデルの初期化処理
        
        Args:
            model_path: モデルのファイルパス
            model_info: モデル情報
            half_precision: 半精度計算を使用するか
        """
        try:
            # 必要なモジュールのインポート
            try:
                from basicsr.archs.rrdbnet_arch import RRDBNet
            except ImportError:
                raise ImportError("basicsr パッケージがインストールされていません。")
                
            try:
                from realesrgan import RealESRGANer
            except ImportError:
                raise ImportError("realesrgan パッケージがインストールされていません。")
            
            # モデルタイプに基づいてアーキテクチャを選択
            if model_info.get('arch') == 'RRDBNet':
                model = RRDBNet(
                    num_in_ch=3,
                    num_out_ch=3,
                    num_feat=model_info.get('num_feat', 64),
                    num_block=model_info.get('num_block', 23),
                    num_grow_ch=model_info.get('num_grow_ch', 32),
                    scale=self.scale
                )
                netscale = self.scale
            else:
                from realesrgan.archs.srvgg_arch import SRVGGNetCompact
                model = SRVGGNetCompact(
                    num_in_ch=3,
                    num_out_ch=3,
                    num_feat=model_info.get('num_feat', 64),
                    num_conv=model_info.get('num_conv', 16),
                    upscale=self.scale,
                    act_type=model_info.get('act_type', 'prelu')
                )
                netscale = self.scale
            
            # DNIウェイト用の2つ目のモデルパスを準備
            model_path_2 = None
            if 'dni_weight' in model_info and 'model_path_wdn' in model_info:
                model_path_2 = model_info['model_path_wdn']
                dni_weight = model_info['dni_weight']
                print(f"DNIウェイトを使用: {dni_weight}, WDNモデル: {os.path.basename(model_path_2)}")
            else:
                dni_weight = None
                
            # タイルサイズとパディング
            tile = model_info.get('tile', 0)
            tile_pad = model_info.get('tile_pad', 10)
            pre_pad = model_info.get('pre_pad', 0)
            
            # RealESRGANerの初期化
            if model_path_2 and os.path.exists(model_path_2) and dni_weight:
                # 2つのモデルを混合する場合
                self._model = RealESRGANer(
                    scale=netscale,
                    model_path=[model_path, model_path_2],
                    dni_weight=dni_weight,
                    model=model,
                    tile=tile,
                    tile_pad=tile_pad,
                    pre_pad=pre_pad,
                    half=half_precision,
                    gpu_id=0 if self._device.type == 'cuda' else None
                )
            else:
                # 単一モデルの場合
                self._model = RealESRGANer(
                    scale=netscale,
                    model_path=model_path,
                    model=model,
                    tile=tile,
                    tile_pad=tile_pad,
                    pre_pad=pre_pad,
                    half=half_precision,
                    gpu_id=0 if self._device.type == 'cuda' else None
                )
            
            # 半精度モードの場合、追加でモデル内部のテンソル一貫性を確保
            if half_precision and self._device.type == 'cuda':
                self._ensure_half_precision_consistency()
        
        except Exception as e:
            raise RuntimeError(f"Real-ESRGANモデルの初期化中にエラーが発生しました: {e}")
    
    def _ensure_half_precision_consistency(self):
        """Real-ESRGANのモデル内部テンソルの型一貫性を確保"""
        try:
            # RealESRGANerモデルの場合、内部モデルにアクセス
            if hasattr(self._model, 'model') and self._model.model is not None:
                base_model = self._model.model
                
                # モデルの精度を検出
                model_dtype = next(base_model.parameters()).dtype
                is_half = (model_dtype == torch.float16)
                
                if is_half:
                    # 内部モデルのすべてのテンソルを確認
                    for module in base_model.modules():
                        # 畳み込み層のパラメータをチェック
                        if isinstance(module, (torch.nn.Conv2d, torch.nn.Linear)):
                            if hasattr(module, 'weight') and module.weight is not None:
                                if module.weight.dtype != torch.float16:
                                    module.weight.data = module.weight.data.half()
                            if hasattr(module, 'bias') and module.bias is not None:
                                if module.bias.dtype != torch.float16:
                                    module.bias.data = module.bias.data.half()
                        
                        # バッチ正規化層のパラメータをチェック
                        elif isinstance(module, (torch.nn.BatchNorm2d)):
                            if hasattr(module, 'running_mean') and module.running_mean is not None:
                                if module.running_mean.dtype != torch.float16:
                                    module.running_mean = module.running_mean.half()
                            if hasattr(module, 'running_var') and module.running_var is not None:
                                if module.running_var.dtype != torch.float16:
                                    module.running_var = module.running_var.half()
        
        except Exception as e:
            print(f"半精度テンソルの一貫性確保中にエラーが発生: {e}")
    
    def _initialize_face_enhancer(self, half_precision: bool) -> None:
        """
        顔強調モデル（GFPGAN）の初期化処理
        
        Args:
            half_precision: 半精度計算を使用するか
        """
        try:
            from gfpgan import GFPGANer
            
            # モデルディレクトリを取得
            model_dir = self._get_model_dir()
            
            # 顔強調モデルのパス
            model_path = os.path.join(model_dir, 'GFPGANv1.3.pth')
            
            # モデルファイルの存在確認とダウンロード
            if not os.path.exists(model_path):
                if not self.ensure_model(model_path):
                    raise FileNotFoundError(f"GFPGANモデルが見つからず、ダウンロードにも失敗しました: {model_path}")
            
            # モデルの初期化
            self._face_enhancer = GFPGANer(
                model_path=model_path,
                upscale=self.scale,
                arch='clean',
                channel_multiplier=2,
                bg_upsampler=self._model
            )
            
        except ImportError as e:
            self._face_enhancer = None
            print(f"顔強調モデル初期化をスキップします。GFPGAN依存関係がありません: {e}")
        except Exception as e:
            self._face_enhancer = None
            print(f"顔強調モデルの初期化に失敗しました: {e}")
    
    def _get_model_info(self, variant: str = 'standard') -> Dict[str, Any]:
        """
        指定されたバリアントに基づくReal-ESRGANモデル情報を取得
        
        Args:
            variant: モデルのバリアント ('standard', 'anime', 'video', 'denoise' など)
            
        Returns:
            Dict[str, Any]: モデル情報
        """
        # モデルディレクトリを取得（相対パスではなく絶対パスを使用）
        model_dir = self._get_model_dir()
        
        if variant == 'anime':
            return {
                'model_path': os.path.join(model_dir, 'RealESRGAN_x4plus_anime_6B.pth'),
                'num_feat': 64,
                'num_block': 6,  # アニメ向けは少ないブロック数
                'num_grow_ch': 32,
                'scale': self.scale,
                'arch': 'RRDBNet',
                'tile': 400,  # タイルサイズ
                'tile_pad': 10,
                'pre_pad': 0
            }
        elif variant == 'video':
            return {
                'model_path': os.path.join(model_dir, 'realesr-animevideov3.pth'),
                'num_feat': 64,
                'num_conv': 16,
                'scale': self.scale,
                'arch': 'SRVGGNetCompact',
                'tile': 100,  # ビデオ処理用に小さいタイル
                'tile_pad': 10,
                'pre_pad': 0
            }
        elif variant == 'denoise':  # デノイズモデルを明示的に設定
            # 特にノイズ除去に最適化されたバージョン
            return {
                'model_path': os.path.join(model_dir, 'realesr-general-x4v3.pth'),
                'model_path_wdn': os.path.join(model_dir, 'realesr-general-wdn-x4v3.pth'),
                'num_feat': 64,
                'num_block': 23,
                'num_conv': 32,
                'act_type': 'prelu',
                'scale': self.scale,
                'arch': 'SRVGGNetCompact',
                'tile': 200,
                'tile_pad': 10,
                'pre_pad': 0,
                'dni_weight': [0.5, 0.5]  # デノイズ強度と復元強度のバランス
            }
        else:  # 'standard' などのデフォルトモデル
            return {
                'model_path': os.path.join(model_dir, 'RealESRGAN_x4plus.pth'),
                'num_feat': 64,
                'num_block': 23,
                'num_grow_ch': 32,
                'scale': self.scale,
                'arch': 'RRDBNet',
                'tile': 0,  # タイル処理なし
                'tile_pad': 10,
                'pre_pad': 0
            }
    
    def _get_model_dir(self) -> str:
        """モデルディレクトリのパスを取得"""
        # アプリケーションの基準ディレクトリ
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # モデルディレクトリを作成
        model_dir = os.path.join(base_dir, 'models', 'torch_models')
        os.makedirs(model_dir, exist_ok=True)
        
        return model_dir
    
    def _download_model_impl(self, model_path: str) -> bool:
        """RealESRGANモデルのダウンロード実装"""
        model_name = os.path.basename(model_path)
        
        # まず標準のGitHubリリースURLを確認
        if model_name in self._model_urls:
            url = self._model_urls[model_name]
            print(f"標準URLからダウンロードを試みます: {url}")
            result = self.download_model(model_path, url)
            if result:
                return True
        
        # GitHubが失敗したら、代替URLからダウンロードを試みる
        backup_urls = {
            # denoise関連のモデル
            "realesr-general-x4v3.pth": 
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
            "realesr-general-wdn-x4v3.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth",
            
            # 標準モデル
            "RealESRGAN_x2plus.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
            "RealESRGAN_x4plus.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            
            # アニメ関連のモデル
            "RealESRGAN_x4plus_anime_6B.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
            "realesr-animevideov3.pth":
                "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
                
            # GFPGAN (顔強調用)
            "GFPGANv1.3.pth":
                "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth"
        }
        
        if model_name in backup_urls:
            url = backup_urls[model_name]
            print(f"代替URLからダウンロードを試みます: {url}")
            return self.download_model(model_path, url)
        
        print(f"モデル {model_name} のURLが見つかりませんでした。")
        return False
    
    def process(self, image: np.ndarray, options: Dict[str, Any] = None) -> SRResult:
        """
        Real-ESRGANによる超解像処理
        
        Args:
            image: 入力画像 (BGR形式)
            options: 処理オプション
              - face_enhance: 顔強調を使用するか (bool、デフォルトはFalse)
              - outscale: 出力スケール倍率（デフォルトは設定されたscale値）
              - tile_size: タイルサイズ
              - tile_pad: タイルパディングサイズ
              - pre_pad: 事前パディングサイズ
              - half_precision: 半精度計算を使用するか
              
        Returns:
            SRResult: 処理結果
        """
        if not self.is_initialized():
            if not self.initialize():
                print("モデルの初期化に失敗したため、通常のリサイズを使用します")
                return super().process(image, options)
        
        # オプション取得
        options = options or {}
        
        # 処理オプションに変更がある場合、ハッシュ値を更新
        process_options_hash = self._calculate_process_options_hash(options)
        if hasattr(self, '_last_process_options_hash') and process_options_hash != self._last_process_options_hash:
            print(f"処理オプションが変更されました: {self._method.value}")
        self._last_process_options_hash = process_options_hash
        
        face_enhance = options.get('face_enhance', False)
        outscale = options.get('outscale', self.scale)
        
        # 開始時間を記録
        start_time = time.time()
        
        try:
            # RGBA対応
            img_mode = None
            if len(image.shape) == 3 and image.shape[2] == 4:
                img_mode = 'RGBA'
            
            # 処理実行
            if face_enhance and self._face_enhancer is not None:
                # 顔強調処理
                _, _, output = self._face_enhancer.enhance(
                    image, 
                    has_aligned=False, 
                    only_center_face=False, 
                    paste_back=True
                )
            else:
                # 通常の処理
                output, _ = self._model.enhance(image, outscale=outscale)
            
            # 処理時間を計算
            processing_time = time.time() - start_time
            
            return SRResult(
                image=output,
                processing_time=processing_time,
                method=self._method,
                scale=outscale,  # 実際に適用されたスケールを記録
                options=options
            )
            
        except Exception as e:
            # エラー時は元の画像をリサイズして返す
            print(f"Real-ESRGANでの処理中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            
            h, w = image.shape[:2]
            fallback_image = cv2.resize(image, (w * self.scale, h * self.scale), interpolation=cv2.INTER_CUBIC)
            
            processing_time = time.time() - start_time
            
            return SRResult(
                image=fallback_image,
                processing_time=processing_time,
                method=self._method,
                scale=self.scale,
                options=options
            )
    
    def cleanup(self):
        """リソースの解放処理"""
        if hasattr(self, '_model') and self._model is not None:
            self._model = None
        
        if hasattr(self, '_face_enhancer') and self._face_enhancer is not None:
            self._face_enhancer = None
        
        # ハッシュ値をクリア
        self._last_options_hash = None
        if hasattr(self, '_last_process_options_hash'):
            self._last_process_options_hash = None
            
        # GPUメモリのクリア
        if hasattr(self, '_device') and self._device is not None and self._device.type == 'cuda':
            torch.cuda.empty_cache()
        
        self._initialized = False
    
    def _calculate_options_hash(self, options: Dict[str, Any]) -> str:
        """オプションのハッシュ値を計算"""
        if options is None:
            return "default"
        
        # 重要なオプションキーだけを抽出
        important_keys = [
            'use_cuda', 'half_precision', 'model_path', 'variant', 'face_enhance',
            'denoise_strength', 'dni_weight'  # デノイズ強度とDNIウェイトを追加
        ]
        
        # 辞書を作成
        option_dict = {}
        for k in important_keys:
            if k in options:
                # 浮動小数点数は丸めて比較（わずかな差を無視）
                if isinstance(options[k], float):
                    option_dict[k] = round(options[k], 3)
                else:
                    option_dict[k] = options[k]
        
        options_str = str(option_dict)
        
        # デバイスIDも含める（GPUが複数ある場合に対応）
        if torch.cuda.is_available():
            device_info = f"cuda:{torch.cuda.current_device()}" if options.get('use_cuda', True) else "cpu"
        else:
            device_info = "cpu"
        options_str += f"_device:{device_info}"
        
        # デバッグ出力
        print(f"オプションハッシュ文字列: {options_str}")
        
        import hashlib
        return hashlib.md5(options_str.encode()).hexdigest()

    def _calculate_process_options_hash(self, options: Dict[str, Any]) -> str:
        """処理オプションのハッシュ値を計算"""
        if options is None:
            return "default_process"
        
        # 処理に影響するオプションキーだけを抽出
        process_keys = ['face_enhance', 'outscale', 'tile_size', 'tile_pad', 'pre_pad', 'half_precision']
        options_str = str({k: options.get(k) for k in process_keys if k in options})
        
        # シンプルなハッシュ値を生成
        return hashlib.md5(options_str.encode()).hexdigest()

    def ensure_model(self, model_path: str) -> bool:
        """
        モデルファイルの存在を確認し、なければダウンロードを試みる
        
        Args:
            model_path: モデルのファイルパス
            
        Returns:
            bool: モデルファイルが存在するか、ダウンロードに成功したか
        """
        if os.path.exists(model_path):
            return True
        
        # モデルディレクトリを作成
        os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)
        
        # モデル名からURLを取得してダウンロード
        return self._download_model_impl(model_path)

    def download_model(self, model_path: str, url: str) -> bool:
        """
        指定したURLからモデルをダウンロード
        
        Args:
            model_path: 保存先のファイルパス
            url: ダウンロード元のURL
            
        Returns:
            bool: ダウンロードに成功したか
        """
        temp_file = None
        try:
            print(f"モデルをダウンロードします: {os.path.basename(model_path)}")
            print(f"URL: {url}")
            
            # ダウンロード先ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)
            
            # 一時ファイルにダウンロード
            temp_file = model_path + ".downloading"
            
            # ユーザーエージェントを指定（一部サーバーでは必要）
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # URLリクエストにヘッダーを追加
            request = urllib.request.Request(url, headers=headers)
            
            # プログレスバー付きでダウンロード
            with tqdm(unit='B', unit_scale=True, unit_divisor=1024, miniters=1, desc=os.path.basename(model_path)) as t:
                def report_hook(block_num, block_size, total_size):
                    if total_size > 0:
                        t.total = total_size
                    read_size = block_num * block_size
                    t.update(block_size if read_size <= t.total else t.total - (read_size - block_size))
                
                # リクエストを使用してダウンロード
                urllib.request.urlretrieve(url, temp_file, reporthook=report_hook)
            
            # ダウンロードが完了したらファイル名を変更
            shutil.move(temp_file, model_path)
            print(f"ダウンロード完了: {model_path}")
            
            return True
            
        except Exception as e:
            print(f"モデルのダウンロードに失敗しました: {e}")
            # 一時ファイルが残っていれば削除
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    def is_available(self) -> bool:
        """
        Real-ESRGANモデルが利用可能かどうかを返す
        
        Returns:
            モデルがロードされていればTrue
        """
        return self.model is not None
