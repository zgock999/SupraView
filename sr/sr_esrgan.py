"""
ESRGAN超解像モデルを使った超解像処理クラス
"""
import os
import cv2
import numpy as np
import time
from typing import Dict, Any, List, Optional

# モジュールのインポートパスを修正
from sr.sr_base import SuperResolutionBase, SRMethod, SRResult

# トーチモデル関連のインポート
try:
    import torch
    from torch.nn import functional as F
    from basicsr.archs.rrdbnet_arch import RRDBNet
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("PyTorchがインストールされていないため、ESRGANモデルは使用できません")


class ESRGANSuperResolution(SuperResolutionBase):
    """
    ESRGANを使用した超解像処理クラス
    """
    
    def __init__(self, sr_method: SRMethod, scale: int = 4):
        """
        初期化
        
        Args:
            sr_method: 使用するESRGANモデルの種類
            scale: 拡大倍率（ESRGANは主に4x）
        """
        super().__init__(scale)
        self._sr_method = sr_method
        self.device = None
        self.model = None
        self._initialized = False
        
        # モデルファイルのURLマッピング
        self._model_urls = {
            # ESRGAN系モデル（標準）
            "ESRGAN_SRx4_DF2KOST_official-ff704c30.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/ESRGAN_SRx4_DF2KOST_official-ff704c30.pth",
            
            # ESRGAN Anime モデル
            "ESRGAN_anime_SRx4_official-eaa2d5d3.pth": "https://huggingface.co/datasets/yolohammer/esrgan-models/resolve/main/ESRGAN_anime_SRx4_official-eaa2d5d3.pth",
            
            # ESRGAN PhotoRealistic モデル
            "ESRGAN_PhotoRealistic_SRx4_official-5b59c6c5.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/ESRGAN_SRx4_DF2KOST_official-ff704c30.pth",
            
            # RealESRGAN モデル
            "RealESRGAN_x2plus.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/RealESRGAN_x2plus.pth",
            "RealESRGAN_x4plus.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        }
    
    @property
    def method(self) -> SRMethod:
        return self._sr_method
    
    def initialize(self, options: Dict[str, Any] = None) -> bool:
        """
        モデルの初期化処理
        
        Args:
            options: 初期化オプション
                - 'device': 使用するデバイス ('cuda', 'cpu')
                
        Returns:
            bool: 初期化成功かどうか
        """
        if not TORCH_AVAILABLE:
            print("PyTorchがインストールされていないため、ESRGANモデルは使用できません")
            return False
            
        try:
            # オプションを処理
            options = options or {}
            
            # デバイスの設定（CUDA利用可能ならGPUを使用）
            if 'device' in options:
                device_str = options['device']
            else:
                device_str = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            self.device = torch.device(device_str)
            
            # モデルファイルの選択
            model_file = self._get_model_filename()
            if not model_file:
                print(f"モデルが見つかりません: {self._sr_method}")
                return False
                
            # モデルファイルが存在するか確認し、なければダウンロード
            model_path = self._get_model_path(model_file)
            if not os.path.exists(model_path) or os.path.getsize(model_path) < 1000000:  # 1MB未満はダウンロード失敗と判断
                model_url = self._model_urls.get(model_file)
                if not model_url:
                    print(f"モデル {model_file} のダウンロードURLが見つかりません")
                    return False
                    
                print(f"モデル {model_file} をダウンロードします...")
                if not self.ensure_model(model_path):
                    print(f"モデルのダウンロードに失敗しました: {model_file}")
                    return False
            
            # モデルアーキテクチャを選択
            num_in_ch = 3  # RGB画像用
            num_out_ch = 3  # RGB出力
            num_feat = 64   # 特徴数
            block_num = 23  # ブロック数
            
            # RealESRGANの場合は設定を変更
            if self._sr_method == SRMethod.REAL_ESRGAN:
                if "plus_anime" in model_file:
                    num_feat = 64
                    block_num = 6
                else:
                    num_feat = 64
                    block_num = 23
            
            # モデルを作成
            model = RRDBNet(
                num_in_ch=num_in_ch,
                num_out_ch=num_out_ch,
                num_feat=num_feat,
                num_block=block_num,
                num_grow_ch=32,
                scale=self.scale
            )
            
            # モデルの重みをロード
            load_path = model_path
            pretrained_dict = torch.load(load_path, map_location=torch.device('cpu'))
            
            # 異なる保存形式に対応
            if 'params_ema' in pretrained_dict:
                model.load_state_dict(pretrained_dict['params_ema'])
            elif 'params' in pretrained_dict:
                model.load_state_dict(pretrained_dict['params'])
            else:
                model.load_state_dict(pretrained_dict)
            
            # デバイスに移動してevalモードに設定
            model.eval()
            model = model.to(self.device)
            
            self.model = model
            self._initialized = True
            
            print(f"ESRGANモデルの初期化に成功しました: {model_file} (device: {self.device})")
            return True
            
        except Exception as e:
            print(f"ESRGANモデルの初期化中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def process(self, image: np.ndarray, options: Dict[str, Any] = None) -> SRResult:
        """
        画像の超解像処理
        
        Args:
            image: 入力画像 (BGR形式)
            options: 処理オプション
                - 'tile': タイル処理のサイズ（大きい画像を分割処理）
                - 'tile_pad': タイル間の重複サイズ
                
        Returns:
            SRResult: 処理結果
        """
        if not self._initialized:
            if not self.initialize(options):
                # 初期化失敗時はOpenCVのリサイズで代替
                h, w = image.shape[:2]
                result = cv2.resize(image, (w * self.scale, h * self.scale), cv2.INTER_CUBIC)
                return SRResult(
                    image=result,
                    processing_time=0.0,
                    method=self._sr_method,
                    scale=self.scale,
                    options=options
                )
        
        try:
            start_time = time.time()
            options = options or {}
            
            # BGR -> RGB変換
            img_rgb = image[..., ::-1]  # BGR -> RGB
            
            # 画像のタイル処理
            tile = options.get('tile', 0)
            tile_pad = options.get('tile_pad', 10)
            
            if tile > 0:
                # タイル処理を行う場合
                result = self._process_by_tile(img_rgb, tile, tile_pad)
            else:
                # 画像全体を一度に処理
                result = self._process_whole_image(img_rgb)
            
            # RGB -> BGR変換
            result = result[..., ::-1]  # RGB -> BGR
            
            # 処理時間を計測
            elapsed_time = time.time() - start_time
            
            return SRResult(
                image=result,
                processing_time=elapsed_time,
                method=self._sr_method,
                scale=self.scale,
                options=options
            )
            
        except Exception as e:
            print(f"ESRGAN処理中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            
            # エラーが発生した場合はOpenCVのリサイズで代替
            h, w = image.shape[:2]
            result = cv2.resize(image, (w * self.scale, h * self.scale), cv2.INTER_CUBIC)
            return SRResult(
                image=result,
                processing_time=0.0,
                method=self._sr_method,
                scale=self.scale,
                options=options
            )
    
    def _process_whole_image(self, img_rgb: np.ndarray) -> np.ndarray:
        """画像全体を一度に処理する"""
        with torch.no_grad():
            # numpy -> torch tensor
            img_tensor = self._preprocess_image(img_rgb)
            
            # 推論実行
            output = self.model(img_tensor)
            
            # torch tensor -> numpy
            output_img = self._postprocess_tensor(output)
            
        return output_img
    
    def _process_by_tile(self, img_rgb: np.ndarray, tile_size: int, tile_pad: int) -> np.ndarray:
        """画像を小さなタイルに分割して処理する"""
        # 入力画像のサイズ
        h, w = img_rgb.shape[:2]
        
        # 出力画像のサイズ
        out_h = h * self.scale
        out_w = w * self.scale
        
        # 出力画像用の配列を作成
        output_img = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        
        # 縦横のタイル数を計算
        tiles_x = (w + tile_size - 1) // tile_size
        tiles_y = (h + tile_size - 1) // tile_size
        
        for i in range(tiles_y):
            for j in range(tiles_x):
                # タイルの開始/終了位置を計算
                x_start = j * tile_size - tile_pad if j > 0 else 0
                y_start = i * tile_size - tile_pad if i > 0 else 0
                x_end = min((j + 1) * tile_size + tile_pad, w)
                y_end = min((i + 1) * tile_size + tile_pad, h)
                
                # 有効なタイル範囲を計算
                x_start_valid = j * tile_size
                y_start_valid = i * tile_size
                x_end_valid = min((j + 1) * tile_size, w)
                y_end_valid = min((i + 1) * tile_size, h)
                
                # タイル画像を切り出し
                tile_img = img_rgb[y_start:y_end, x_start:x_end]
                
                # タイル画像を処理
                tile_result = self._process_whole_image(tile_img)
                
                # 出力画像の対応する位置
                out_x_start = x_start_valid * self.scale
                out_y_start = y_start_valid * self.scale
                out_x_end = x_end_valid * self.scale
                out_y_end = y_end_valid * self.scale
                
                # 有効な出力タイル範囲
                out_x_start_pad = (x_start_valid - x_start) * self.scale
                out_y_start_pad = (y_start_valid - y_start) * self.scale
                out_x_end_pad = out_x_start_pad + (x_end_valid - x_start_valid) * self.scale
                out_y_end_pad = out_y_start_pad + (y_end_valid - y_start_valid) * self.scale
                
                # タイル結果を出力画像にコピー
                output_img[out_y_start:out_y_end, out_x_start:out_x_end] = tile_result[out_y_start_pad:out_y_end_pad, out_x_start_pad:out_x_end_pad]
                
        return output_img
    
    def _preprocess_image(self, img: np.ndarray) -> torch.Tensor:
        """numpy配列をTorchテンソルに変換"""
        # 0-255の整数値を0-1の浮動小数点に変換
        img = img.astype(np.float32) / 255.0
        
        # HWC -> CHW (Torchの形式)
        img = np.transpose(img, (2, 0, 1))
        
        # numpy配列をTorchテンソルに変換
        img = torch.from_numpy(img).unsqueeze(0).to(self.device)  # add batch dimension
        
        return img
    
    def _postprocess_tensor(self, tensor: torch.Tensor) -> np.ndarray:
        """Torchテンソルをnumpy配列に変換"""
        # GPUデータをCPUに移動
        tensor = tensor.to('cpu')
        
        # Torchテンソルをnumpy配列に変換
        output_img = tensor.squeeze().detach().numpy()
        
        # CHW -> HWC
        output_img = np.transpose(output_img, (1, 2, 0))
        
        # 値域を0-1から0-255に変換し、uint8に丸める
        output_img = np.clip(output_img * 255.0, 0, 255).round().astype(np.uint8)
        
        return output_img
    
    def _get_model_filename(self) -> Optional[str]:
        """モデル方式に基づいてモデルファイル名を取得"""
        if self._sr_method == SRMethod.ESRGAN_GENERAL:
            return "ESRGAN_SRx4_DF2KOST_official-ff704c30.pth"
        elif self._sr_method == SRMethod.ESRGAN_ANIME:
            return "ESRGAN_anime_SRx4_official-eaa2d5d3.pth" 
        elif self._sr_method == SRMethod.ESRGAN_PHOTO:
            return "ESRGAN_PhotoRealistic_SRx4_official-5b59c6c5.pth"
        elif self._sr_method == SRMethod.REAL_ESRGAN:
            # 倍率に応じたモデルを選択
            if self.scale == 2:
                return "RealESRGAN_x2plus.pth"
            else:  # デフォルトは4倍
                return "RealESRGAN_x4plus.pth"
        return None
    
    def _get_model_path(self, model_filename: str) -> str:
        """モデルファイルのパスを取得"""
        # モデル保存先ディレクトリ
        model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
        
        # ディレクトリが存在しない場合は作成
        os.makedirs(model_dir, exist_ok=True)
        
        return os.path.join(model_dir, model_filename)
    
    def cleanup(self):
        """リソースの解放処理"""
        if self.model is not None:
            del self.model
            self.model = None
            
        # CUDA使用時はキャッシュを解放
        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        self._initialized = False

    def is_available(self) -> bool:
        """
        ESRGANモデルが利用可能かどうかを返す
        
        Returns:
            モデルがロードされていればTrue
        """
        return self.model is not None


