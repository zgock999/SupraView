"""
SwinIR超解像処理カプセル化モジュール
SwinIRモデルを使いやすくラップしたモジュール
"""
import os
import sys
import torch
import numpy as np
import cv2
import time
import requests
import json
from pathlib import Path
from tqdm import tqdm
from enum import Enum
from typing import Dict, Any, List, Optional, Union, Tuple

# SuperResolutionBaseクラスとSRMethodをインポート
from sr.sr_base import SuperResolutionBase, SRMethod, SRResult

# swinir.swinir_modelモジュールをインポート
from sr.swinir.swinir_model import SwinIR, SwinIRModelType, make_model

# SwinIRモデルのダウンロードURL
SWINIR_MODEL_URLS = {
    # Real-SR モデル (標準
    'real_sr_x2': "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x2_GAN-with-dict-keys-params-and-params_ema.pth",
    'real_sr_x3': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-M_x3_GAN.pth',
    'real_sr_x4': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN-with-dict-keys-params-and-params_ema.pth',
    # Real-SR モデル (大規模)
    'real_sr_large_x2': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x2_GAN.pth',
    'real_sr_large_x4': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_GAN.pth',
    
    # Classical-SR モデル
    'classical_sr_x2': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DF2K_s64w8_SwinIR-M_x2.pth',
    'classical_sr_x3': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DF2K_s64w8_SwinIR-M_x3.pth',
    'classical_sr_x4': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DF2K_s64w8_SwinIR-M_x4.pth',
    
    # Lightweight-SR モデル
    'lightweight_sr_x2': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth',
    'lightweight_sr_x3': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x3.pth',
    'lightweight_sr_x4': 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth',
}

# 設定定義
SWINIR_DEFAULT_SETTINGS = {
    # 共通設定
    'common': {
        'tile_size': {
            'type': 'int',
            'default': 0,
            'min': 0,
            'max': 2048,
            'step': 64,
            'label': 'タイルサイズ (0=無効)',
            'help': 'メモリ使用量を削減するためのタイル処理サイズです。大きな画像の場合は512程度の値を設定してください。'
        },
        'tile_overlap': {
            'type': 'int',
            'default': 32,
            'min': 0,
            'max': 128,
            'step': 8,
            'label': 'タイル重複サイズ',
            'help': 'タイル間のつなぎ目を自然にするための重複ピクセル数です。'
        },
        'auto_download': {
            'type': 'bool',
            'default': True,
            'label': 'モデルを自動ダウンロード',
            'help': 'モデルファイルが見つからない場合に自動ダウンロードします。'
        },
        'device': {
            'type': 'enum',
            'default': 'auto',
            'options': ['auto', 'cuda', 'cpu'],
            'label': '実行デバイス',
            'help': '使用するデバイスです。autoではGPUを優先使用します。'
        }
        # 半精度オプションを削除
    },
    
    # モデル固有設定
    SRMethod.SWINIR_LIGHTWEIGHT: {
        'model_path': {
            'type': 'file',
            'default': '',
            'label': 'カスタムモデルパス',
            'help': '独自のモデルファイルを使用する場合に指定します。空欄の場合はデフォルトモデルを使用します。',
            'filter': '重みファイル (*.pth *.pt)'
        },
        # 軽量モデル特有の設定をここに追加
    },
    
    SRMethod.SWINIR_REAL: {
        'model_path': {
            'type': 'file',
            'default': '',
            'label': 'カスタムモデルパス',
            'help': '独自のモデルファイルを使用する場合に指定します。空欄の場合はデフォルトモデルを使用します。',
            'filter': '重みファイル (*.pth *.pt)'
        },
        # 実写画像超解像特有の設定をここに追加
    },
    
    SRMethod.SWINIR_LARGE: {
        'model_path': {
            'type': 'file',
            'default': '',
            'label': 'カスタムモデルパス',
            'help': '独自のモデルファイルを使用する場合に指定します。空欄の場合はデフォルトモデルを使用します。',
            'filter': '重みファイル (*.pth *.pt)'
        },
        # 大規模モデル特有の設定をここに追加
    },
    
    SRMethod.SWINIR_CLASSICAL: {
        'model_path': {
            'type': 'file',
            'default': '',
            'label': 'カスタムモデルパス',
            'help': '独自のモデルファイルを使用する場合に指定します。空欄の場合はデフォルトモデルを使用します。',
            'filter': '重みファイル (*.pth *.pt)'
        },
        # 古典的超解像特有の設定をここに追加
    }
}

class SwinIRSuperResolution(SuperResolutionBase):
    """SwinIRモデルを使った超解像処理クラス"""
    
    def __init__(self, method=SRMethod.SWINIR_REAL, scale=4, options=None):
        """
        SwinIR処理モジュールの初期化
        
        Args:
            method: 使用するメソッド (SRMethod.SWINIR_XXX)
            scale: 拡大倍率 (2, 3, 4のいずれか)
            options: その他のオプション
        """
        super().__init__(scale)
        self._method = method  # privateフィールドにする
        self.options = self._merge_default_options(options or {})
        
        # デバイス設定
        self.device = self._get_device()
        
        # オプションからタイル設定を取得
        self.tile_size = self.options.get('tile_size', 512)
        if self.tile_size in [0, 'null', 'none', 'None', None]:
            self.tile_size = None
        
        self.tile_overlap = self.options.get('tile_overlap', 32)
        
        # モデル初期化
        self.model = None
        self.model_type = self._get_model_type_from_method(method)
        
        # 自動初期化が有効な場合は初期化
        if self.options.get('auto_initialize', True):
            self.initialize()
    
    def _merge_default_options(self, user_options):
        """
        ユーザーオプションとデフォルト設定をマージする
        
        Args:
            user_options: ユーザー指定オプション
            
        Returns:
            Dict: マージされたオプション
        """
        # 共通設定からデフォルト値を取得
        result = {}
        for key, setting in SWINIR_DEFAULT_SETTINGS['common'].items():
            result[key] = setting['default']
        
        # メソッド固有の設定からデフォルト値を取得
        if self._method in SWINIR_DEFAULT_SETTINGS:
            for key, setting in SWINIR_DEFAULT_SETTINGS[self._method].items():
                result[key] = setting['default']
        
        # ユーザー設定で上書き
        for key, value in user_options.items():
            result[key] = value
        
        return result
    
    @property
    def method(self):
        """メソッドのプロパティ (オーバーライド)"""
        return self._method
    
    def _get_device(self):
        """使用するデバイスを取得"""
        # オプションからデバイス設定を取得、なければ自動検出
        device_name = self.options.get('device', 'auto')
        if device_name == 'cuda' and torch.cuda.is_available():
            return torch.device('cuda')
        elif device_name == 'cpu':
            return torch.device('cpu')
        else:
            # 自動検出 (CUDA優先)
            return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    def _get_model_type_from_method(self, method):
        """SRMethodからSwinIRModelTypeへの変換"""
        method_to_model = {
            SRMethod.SWINIR_LIGHTWEIGHT: SwinIRModelType.LIGHTWEIGHT_SR,
            SRMethod.SWINIR_REAL: SwinIRModelType.REAL_SR,
            SRMethod.SWINIR_LARGE: SwinIRModelType.REAL_SR_LARGE,
            SRMethod.SWINIR_CLASSICAL: SwinIRModelType.CLASSICAL_SR
        }
        return method_to_model.get(method, SwinIRModelType.REAL_SR)
    
    def initialize(self, options=None):
        """
        モデルを初期化
        
        Args:
            options: 初期化オプション (Noneの場合は既存のオプションを使用)
        
        Returns:
            bool: 初期化成功したかどうか
        """
        if options is not None:
            self.options.update(options)
        
        try:
            # モデルタイプに応じたモデル作成
            self.model = make_model(self.model_type, self.scale)
            
            # モデルパス取得
            model_path = self._get_model_path()
            
            # モデルが存在しない場合はダウンロード
            if not os.path.exists(model_path):
                if self.options.get('auto_download', True):
                    if not self._download_model(model_path):
                        raise FileNotFoundError(f"モデルファイル {model_path} が見つからず、ダウンロードにも失敗しました")
                else:
                    raise FileNotFoundError(f"モデルファイル {model_path} が見つかりません（自動ダウンロードは無効になっています）")
            
            # 重み読み込み
            pretrained = torch.load(model_path, map_location=self.device)
            
            # パラメータキーを探す
            if 'params_ema' in pretrained:
                self.model.load_state_dict(pretrained['params_ema'], strict=True)
            elif 'params' in pretrained:
                self.model.load_state_dict(pretrained['params'], strict=True)
            else:
                self.model.load_state_dict(pretrained, strict=True)
            
            # モデルをデバイスに転送し、評価モードに設定
            self.model = self.model.to(self.device)
            self.model.eval()
            
            # 初期化完了
            self._initialized = True
            print(f"SwinIRモデルを初期化: スケール={self.scale}, タイプ={self.model_type.name}, デバイス={self.device}")
            return True
            
        except Exception as e:
            print(f"SwinIRモデル初期化エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            self._initialized = False
            return False
    
    def _get_model_path(self):
        """使用するモデルのパスを取得"""
        # カスタムモデルパスがオプションに指定されている場合はそれを使用
        if 'model_path' in self.options and self.options['model_path']:
            custom_path = self.options['model_path']
            if os.path.exists(custom_path):
                return custom_path
            else:
                print(f"警告: 指定されたカスタムモデルパス '{custom_path}' が存在しません。デフォルトパスを使用します。")
        
        # モデルディレクトリ確認と作成
        model_dir = Path('./torch_models')
        model_dir.mkdir(exist_ok=True)
        
        # モデルタイプに応じたデフォルトパスを取得
        if self.model_type == SwinIRModelType.REAL_SR_LARGE:
            model_file = f'003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x{self.scale}_GAN.pth'
        elif self.model_type == SwinIRModelType.REAL_SR:
            model_file = f'003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x{self.scale}_GAN.pth'
            if self.scale == 4:
                model_file = "003_realSR_BSRGAN_DFO_s64w8_SwinIR-L_x4_GAN-with-dict-keys-params-and-params_ema.pth"
            else:
                model_file = "003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x2_GAN-with-dict-keys-params-and-params_ema.pth"
        elif self.model_type == SwinIRModelType.CLASSICAL_SR:
            model_file = f'001_classicalSR_DF2K_s64w8_SwinIR-M_x{self.scale}.pth'
        elif self.model_type == SwinIRModelType.LIGHTWEIGHT_SR:
            model_file = f'002_lightweightSR_DIV2K_s64w8_SwinIR-S_x{self.scale}.pth'
        else:
            model_file = f'003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-M_x{self.scale}_GAN.pth'
        
        # 絶対パスを構築
        full_path = os.path.abspath(os.path.join(model_dir, model_file))
        print(f"モデルパス: {full_path}")
        return full_path
    
    def _download_model(self, model_path):
        """モデルを自動ダウンロード
        
        Args:
            model_path: モデルの保存先パス
            
        Returns:
            bool: ダウンロード成功したかどうか
        """
        if not model_path:
            print("エラー: モデルパスが空です")
            return False
        
        # URLマップからURL取得
        url_key = self._get_url_key()
        if url_key not in SWINIR_MODEL_URLS:
            print(f"エラー: モデル {url_key} のダウンロードURLが定義されていません")
            return False
        
        url = SWINIR_MODEL_URLS[url_key]
        
        # ディレクトリの確認と作成
        model_dir = os.path.dirname(model_path)
        if not os.path.exists(model_dir):
            try:
                os.makedirs(model_dir, exist_ok=True)
            except Exception as e:
                print(f"モデルディレクトリ作成エラー: {e}")
                return False
        
        print(f"SwinIRモデル '{url_key}' をダウンロードしています...")
        print(f"URL: {url}")
        print(f"保存先: {model_path}")
        
        try:
            # リクエストを作成
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # ファイルサイズを取得
            total_size_in_bytes = int(response.headers.get('content-length', 0))
            block_size = 8192  # 8KB単位でダウンロード
            
            # 進捗バーを使ってダウンロード
            with open(model_path, 'wb') as file, tqdm(
                desc=f"モデルダウンロード中",
                total=total_size_in_bytes,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
            ) as progress_bar:
                for data in response.iter_content(block_size):
                    progress_bar.update(len(data))
                    file.write(data)
            
            print(f"モデルのダウンロードが完了しました: {model_path}")
            return True
            
        except Exception as e:
            print(f"モデルのダウンロード中にエラーが発生しました: {e}")
            # ダウンロードが失敗した場合は不完全なファイルを削除
            if os.path.exists(model_path):
                try:
                    os.remove(model_path)
                except:
                    pass
            return False
    
    def _get_url_key(self):
        """モデルURLの取得用キーを生成"""
        if self.model_type == SwinIRModelType.REAL_SR_LARGE:
            return f"real_sr_large_x{self.scale}"
        elif self.model_type == SwinIRModelType.REAL_SR:
            return f"real_sr_x{self.scale}"
        elif self.model_type == SwinIRModelType.CLASSICAL_SR:
            return f"classical_sr_x{self.scale}"
        elif self.model_type == SwinIRModelType.LIGHTWEIGHT_SR:
            return f"lightweight_sr_x{self.scale}"
        else:
            return f"real_sr_x{self.scale}"
    
    def process(self, image, options=None):
        """
        画像処理を実行
        
        Args:
            image: 入力画像 (numpy.ndarray, BGR形式)
            options: 処理オプション
            
        Returns:
            SRResult: 処理結果
        """
        if image is None or not isinstance(image, np.ndarray):
            print("入力画像が無効です")
            return None
            
        # オプションを更新
        if options:
            self.options.update(options)
            
        # 未初期化の場合は初期化
        if not self._initialized:
            if not self.initialize():
                print("モデルの初期化に失敗しました")
                return None
                
        start_time = time.time()
        
        try:
            # 画像前処理
            img_lq = self._preprocess_image(image)
            img_lq = img_lq.to(self.device)
            
            # パディング
            _, _, h_old, w_old = img_lq.size()
            window_size = 8  # SwinIRのウィンドウサイズ
            
            h_pad = (window_size - h_old % window_size) % window_size
            w_pad = (window_size - w_old % window_size) % window_size
            
            if h_pad > 0 or w_pad > 0:
                img_lq = torch.nn.functional.pad(img_lq, (0, w_pad, 0, h_pad), 'reflect')
                
            # 推論実行
            with torch.no_grad():
                if self.tile_size is None:
                    # タイルなしの場合
                    output = self.model(img_lq)
                else:
                    # タイル処理実行
                    output = self._process_tile(img_lq, window_size)
                
                # 元のサイズにクロップ
                output = output[..., :h_old * self.scale, :w_old * self.scale]
                
            # 後処理
            result_img = self._postprocess_image(output)
            
            # 処理時間計測
            elapsed_time = time.time() - start_time
            
            # 結果作成
            return SRResult(
                image=result_img,
                processing_time=elapsed_time,
                method=self.method,
                scale=self.scale,
                options=self.options.copy()
            )
            
        except Exception as e:
            print(f"SwinIR処理エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _preprocess_image(self, img):
        """画像前処理 (BGR -> RGB, torch tensor)"""
        img = img.astype(np.float32) / 255.0
        img = img[:, :, [2, 1, 0]]  # BGR -> RGB
        img = np.transpose(img, (2, 0, 1))  # HWC -> CHW
        img = torch.from_numpy(img).float().unsqueeze(0)  # CHW -> NCHW
        return img
    
    def _postprocess_image(self, output):
        """モデル出力後処理 (torch tensor -> BGR)"""
        output = output.data.squeeze().float().cpu().clamp_(0, 1).numpy()
        if output.ndim == 3:
            output = np.transpose(output, (1, 2, 0))  # CHW -> HWC
            output = output[:, :, [2, 1, 0]]  # RGB -> BGR
        output = (output * 255.0).round().astype(np.uint8)
        return output
    
    def _process_tile(self, img, window_size):
        """タイル処理実行"""
        # 画像サイズ取得
        b, c, h, w = img.size()
        
        # タイルサイズ調整
        tile = min(self.tile_size, h, w)
        
        # タイルサイズがwindow_sizeの倍数になるよう調整
        if tile % window_size != 0:
            tile = (tile // window_size) * window_size
        
        # オーバーラップを考慮したストライド計算
        stride = tile - self.tile_overlap
        
        # タイル位置計算
        h_idx_list = list(range(0, h - tile, stride)) + [max(0, h - tile)]
        w_idx_list = list(range(0, w - tile, stride)) + [max(0, w - tile)]
        h_idx_list = sorted(list(set(h_idx_list)))
        w_idx_list = sorted(list(set(w_idx_list)))
        
        # タイル総数
        total_tiles = len(h_idx_list) * len(w_idx_list)
        if total_tiles > 1:
            print(f"タイル処理: {total_tiles}個のタイル ({h}x{w}画像、タイルサイズ={tile})")
        
        # 出力テンソルと重みテンソル
        output = torch.zeros(b, c, h*self.scale, w*self.scale, device=self.device)
        weight = torch.zeros_like(output)
        
        # 各タイルを処理
        for h_idx in h_idx_list:
            for w_idx in w_idx_list:
                # タイル範囲計算
                h_end = min(h_idx + tile, h)
                w_end = min(w_idx + tile, w)
                
                # 端のタイル調整
                h_idx_final = max(0, h_end - tile)
                w_idx_final = max(0, w_end - tile)
                
                # タイル抽出
                in_patch = img[..., h_idx_final:h_end, w_idx_final:w_end]
                
                # タイル処理
                out_patch = self.model(in_patch)
                
                # 出力位置計算
                h_out_start = h_idx_final * self.scale
                w_out_start = w_idx_final * self.scale
                h_out_end = h_end * self.scale
                w_out_end = w_end * self.scale
                
                # 出力と重み蓄積
                output[..., h_out_start:h_out_end, w_out_start:w_out_end].add_(out_patch)
                weight[..., h_out_start:h_out_end, w_out_start:w_out_end].add_(torch.ones_like(out_patch))
        
        # 重み付き平均計算
        output = output.div_(weight)
        return output
    
    def cleanup(self):
        """リソース解放"""
        if self.model is not None:
            del self.model
            self.model = None
            
        # GPUメモリを明示的に解放
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        self._initialized = False
        print("SwinIRモデルをアンロードしました")
        
    def get_model_name(self):
        """モデル名を取得"""
        model_names = {
            SRMethod.SWINIR_LIGHTWEIGHT: "SwinIR Lightweight",
            SRMethod.SWINIR_REAL: "SwinIR Real-SR",
            SRMethod.SWINIR_LARGE: "SwinIR Real-SR Large",
            SRMethod.SWINIR_CLASSICAL: "SwinIR Classical"
        }
        return model_names.get(self.method, "SwinIR")
    
    @staticmethod
    def get_settings_schema(method=None):
        """
        指定されたメソッドの設定スキーマを取得する
        メソッドが指定されていない場合は共通設定のスキーマを取得する
        
        Args:
            method: SRMethod列挙型の値
            
        Returns:
            Dict: 設定スキーマ
        """
        # 共通設定を返す
        if method is None:
            return SWINIR_DEFAULT_SETTINGS['common']
        
        # 指定されたメソッドの設定に共通設定を追加して返す
        if method in SWINIR_DEFAULT_SETTINGS:
            settings = SWINIR_DEFAULT_SETTINGS['common'].copy()
            settings.update(SWINIR_DEFAULT_SETTINGS[method])
            return settings
        
        # 該当する設定がなければ共通設定のみ返す
        return SWINIR_DEFAULT_SETTINGS['common']

    @staticmethod
    def get_method_info(method=None):
        """
        モデルとメソッドの情報を取得する
        
        Args:
            method: SRMethod列挙型の値（指定しない場合は全メソッド）
            
        Returns:
            Dict: メソッド情報
        """
        # sr_utils.get_method_infoを使用するようにリダイレクト
        from sr.sr_utils import get_method_info
        
        if method is not None:
            return get_method_info(method)
            
        # 全メソッド情報の場合
        from sr.sr_utils import get_all_method_infos
        return {m: info for m, info in get_all_method_infos().items() 
                if m in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL,
                         SRMethod.SWINIR_CLASSICAL, SRMethod.SWINIR_LARGE]}
        
    @staticmethod
    def get_default_options(method=None):
        """
        デフォルトオプションを取得する
        
        Args:
            method: SRMethod列挙型の値（指定しない場合は共通オプション）
        
        Returns:
            Dict: デフォルトオプション
        """
        defaults = {}
        
        # 共通設定からデフォルト値を取得
        for key, setting in SWINIR_DEFAULT_SETTINGS['common'].items():
            defaults[key] = setting['default']
        
        # メソッド固有設定があれば追加
        if method is not None and method in SWINIR_DEFAULT_SETTINGS:
            for key, setting in SWINIR_DEFAULT_SETTINGS[method].items():
                defaults[key] = setting['default']
                
        return defaults
    def is_available(self) -> bool:
        """
        このSRモデルが利用可能かどうかを返す
        
        Returns:
            利用可能ならTrue
        """
        # 必要なライブラリがインストールされているかチェック
        try:
            import torch
            # 初期化されているかチェック
            return hasattr(self, '_initialized') and self._initialized
        except ImportError:
            return False
# sr.sr_baseのcreateメソッドから使用するためのファクトリ関数
def create_swinir(method=SRMethod.SWINIR_REAL, scale=4, options=None):
    """SwinIR超解像モデルを作成"""
    return SwinIRSuperResolution(method, scale, options)