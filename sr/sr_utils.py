"""
超解像処理のユーティリティ関数
"""

import os
import sys
import importlib
import platform
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
from sr.sr_base import SRMethod


def is_cuda_available() -> bool:
    """CUDAが利用可能かどうかを返す"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False

def get_gpu_info() -> Dict[str, Any]:
    """GPUの情報を取得する"""
    result = {
        "available": False,
        "name": None,
        "memory_total": 0,
        "cuda_version": None,
        "device_count": 0
    }
    
    try:
        import torch
        if torch.cuda.is_available():
            result["available"] = True
            result["device_count"] = torch.cuda.device_count()
            result["cuda_version"] = torch.version.cuda
            
            if result["device_count"] > 0:
                result["name"] = torch.cuda.get_device_name(0)
                result["memory_total"] = torch.cuda.get_device_properties(0).total_memory
                
        return result
    except ImportError:
        return result

def get_available_memory() -> Dict[str, int]:
    """利用可能なGPUメモリ情報を取得する"""
    result = {"total": 0, "free": 0, "used": 0}
    
    try:
        import torch
        if torch.cuda.is_available():
            # 現在のデバイス
            device = torch.cuda.current_device()
            
            # GPUの総メモリ量を取得
            result["total"] = torch.cuda.get_device_properties(device).total_memory
            
            # 予約されているメモリ（キャッシュメモリ）とアクティブなメモリ
            result["used"] = torch.cuda.memory_allocated(device) + torch.cuda.memory_reserved(device)
            
            # 空きメモリ
            result["free"] = result["total"] - result["used"]
            
        return result
    except ImportError:
        return result

def get_cuda_devices() -> List[str]:
    """CUDA対応デバイスのリストを取得"""
    devices = []
    try:
        import torch
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i)
                properties = torch.cuda.get_device_properties(i)
                total_memory_gb = properties.total_memory / (1024 ** 3)
                devices.append(f"{name} ({total_memory_gb:.1f} GB)")
        return devices
    except ImportError:
        return devices

def disable_realesrgan_if_needed():
    """
    Python 3.10 で typing.Self の互換性問題が発生する場合、
    環境変数を設定して RealESRGAN を無効化します
    """
    # Python 3.10 以下での特別な互換性処理
    if sys.version_info.major == 3 and sys.version_info.minor <= 10:
        # すでに環境変数が設定されていれば何もしない
        if os.environ.get("DISABLE_REALESRGAN"):
            return
        
        # basicsr モジュールが問題なくインポートできるかテスト
        try:
            spec = importlib.util.find_spec("basicsr")
            if spec is None:
                # basicsr がインストールされていなければスキップ
                return
                
            # typing.Self 問題をチェック
            try:
                import torch._dynamo.variables.lazy
                # インポートに成功したら問題なし
            except (ImportError, TypeError) as e:
                # typing.Self エラーが発生した場合
                if "typing.Self" in str(e):
                    print("Python 3.10 で typing.Self の互換性問題を検出しました")
                    print("RealESRGAN を無効化します")
                    os.environ["DISABLE_REALESRGAN"] = "1"
        except Exception:
            # 安全のため例外をキャッチして通常の処理を続行
            pass

def is_safe_to_import_realesrgan():
    """
    RealESRGAN をインポートしても安全かどうか確認します
    """
    # 明示的に無効化されていればFalse
    if os.environ.get("DISABLE_REALESRGAN") == "1":
        return False
    
    # Python 3.10 以下では特別な確認
    if sys.version_info.major == 3 and sys.version_info.minor <= 10:
        try:
            # 実際にインポートを試みずにチェック
            import torch
            
            # typing.Self 問題をチェック
            try:
                import torch._dynamo.variables.lazy
                return True
            except (ImportError, TypeError) as e:
                if "typing.Self" in str(e):
                    return False
        except ImportError:
            return False
    
    # その他の場合は安全と判断
    return True

# 起動時に自動的に互換性チェックを実行
disable_realesrgan_if_needed()

def download_with_progress(url: str, save_path: str, description: Optional[str] = None) -> bool:
    """プログレスバー付きでファイルダウンロード"""
    try:
        try:
            from tqdm import tqdm
            has_tqdm = True
        except ImportError:
            has_tqdm = False
            
        import requests
        
        # リクエストを送信
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        # ファイル保存先のディレクトリを作成
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # ダウンロード・プログレス
        if has_tqdm:
            desc = description or os.path.basename(save_path)
            with open(save_path, 'wb') as f, tqdm(
                desc=desc,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in response.iter_content(chunk_size=1024):
                    size = f.write(data)
                    bar.update(size)
        else:
            # tqdmが無い場合はシンプルなプログレス
            print(f"Downloading {description or save_path}...")
            with open(save_path, 'wb') as f:
                for i, data in enumerate(response.iter_content(chunk_size=1024*1024)):
                    f.write(data)
                    if i % 10 == 0:
                        print(".", end="", flush=True)
            print("Done!")
        
        # チェック
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return True
            
        return False
    except Exception as e:
        print(f"ダウンロード中にエラーが発生: {e}")
        return False

def download_models(model_dir: str = None) -> bool:
    """必要なモデルファイルをダウンロード"""
    # モデルディレクトリの設定
    if model_dir is None:
        model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    
    # ディレクトリが存在しない場合は作成
    if not os.path.exists(model_dir):
        os.makedirs(model_dir, exist_ok=True)
    
    # download_models.py スクリプトを実行
    try:
        download_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "download_models.py")
        if os.path.exists(download_script):
            print("モデルダウンロードスクリプトを実行します...")
            
            # システムに応じた実行方法
            if sys.platform.startswith('win'):
                os.system(f'python "{download_script}" --all')
            else:
                os.system(f'python3 "{download_script}" --all')
                
            return True
        else:
            print(f"警告: モデルダウンロードスクリプトが見つかりません: {download_script}")
    except Exception as e:
        print(f"モデルのダウンロード中にエラーが発生しました: {e}")
    
    return False

def convert_bgr_to_rgb(image):
    """BGR形式の画像をRGB形式に変換"""
    import cv2
    import numpy as np
    
    if image is None:
        return None
        
    if len(image.shape) == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        return image

def convert_rgb_to_bgr(image):
    """RGB形式の画像をBGR形式に変換"""
    import cv2
    import numpy as np
    
    if image is None:
        return None
        
    if len(image.shape) == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    else:
        return image

def get_sr_method_from_string(method_str: str) -> Optional[SRMethod]:
    """
    文字列から対応するSRMethodオブジェクトを返す
    
    Args:
        method_str: メソッド名を表す文字列
    
    Returns:
        SRMethod: 対応するSRMethodオブジェクト、見つからない場合はNone
    """
    # 文字列からSRMethodを取得するために小文字化
    method_str = method_str.lower()
    
    # valueからSRMethodを探す
    for method in SRMethod:
        if method.value == method_str or method.name.lower() == method_str:
            return method
            
    # 部分一致の場合
    for method in SRMethod:
        if method_str in method.value.lower() or method_str in method.name.lower():
            return method
    
    # コンボボックスの表示文字列からの変換（特殊ケース）
    method_map = {
        "opencv bicubic": SRMethod.OPENCV_CUBIC,
        "opencv lanczos4": SRMethod.OPENCV_LANCZOS,
        "opencv espcn": SRMethod.OPENCV_ESPCN,
        "opencv fsrcnn": SRMethod.OPENCV_FSRCNN,
        "opencv edsr": SRMethod.OPENCV_EDSR,
        "opencv lapsrn": SRMethod.OPENCV_LAPSRN,
        "swinir 軽量モデル": SRMethod.SWINIR_LIGHTWEIGHT,
        "swinir 標準モデル": SRMethod.SWINIR_CLASSICAL,
        "swinir 実写向け": SRMethod.SWINIR_REAL,
        "swinir 高品質モデル": SRMethod.SWINIR_LARGE,
        "real-esrgan": SRMethod.REALESRGAN,
    }
    
    return method_map.get(method_str.lower())

def get_method_supported_scales(method: SRMethod) -> List[int]:
    """
    指定した超解像メソッドがサポートするスケール倍率のリストを取得
    
    Args:
        method: 超解像メソッド
        
    Returns:
        List[int]: サポートされるスケール倍率のリスト
    """
    # OpenCV の基本補間
    if method in [SRMethod.OPENCV_NEAREST, SRMethod.OPENCV_BILINEAR, 
                 SRMethod.OPENCV_CUBIC, SRMethod.OPENCV_LANCZOS]:
        return [2, 3, 4, 8, 16]  # 任意の倍率が可能
        
    # OpenCV DNN系
    elif method == SRMethod.OPENCV_EDSR:
        return [2, 3, 4]
    elif method == SRMethod.OPENCV_ESPCN:
        return [2, 3, 4]
    elif method == SRMethod.OPENCV_FSRCNN:
        return [2, 3, 4]
    elif method == SRMethod.OPENCV_LAPSRN:
        return [2, 4, 8]
    
    # SwinIR系
    elif method == SRMethod.SWINIR_LIGHTWEIGHT:
        return [2, 3, 4]
    elif method == SRMethod.SWINIR_REAL:
        return [4]
    elif method == SRMethod.SWINIR_CLASSICAL:
        return [2, 3, 4]
    elif method == SRMethod.SWINIR_LARGE:
        return [4]  # x3スケールモデルが公開されていない
    
    # Real-ESRGAN系
    elif method == SRMethod.REALESRGAN:
        return [2, 4]
        
    # デフォルト：一般的な倍率
    return [2, 3, 4]

def supports_half_precision(method: SRMethod) -> bool:
    """
    指定した超解像メソッドが半精度計算（FP16）をサポートしているか判定
    
    Args:
        method: 超解像メソッド
        
    Returns:
        bool: 半精度計算をサポートしているか
    """
    # OpenCV系はすべて半精度非サポート
    if method in [
        SRMethod.OPENCV_NEAREST, SRMethod.OPENCV_BILINEAR, 
        SRMethod.OPENCV_CUBIC, SRMethod.OPENCV_LANCZOS,
        SRMethod.OPENCV_EDSR, SRMethod.OPENCV_ESPCN, 
        SRMethod.OPENCV_FSRCNN, SRMethod.OPENCV_LAPSRN
    ]:
        return False
    
    # SwinIR系は現在の実装では半精度非サポート
    elif method in [
        SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL,
        SRMethod.SWINIR_CLASSICAL, SRMethod.SWINIR_LARGE
    ]:
        return False
    
    # Real-ESRGANは半精度サポート
    elif method == SRMethod.REALESRGAN:
        return True
    
    # デフォルト：サポートなし
    return False

def get_method_info(method: SRMethod) -> Dict[str, Any]:
    """
    指定した超解像メソッドの詳細情報を取得
    
    Args:
        method: 超解像メソッド
        
    Returns:
        Dict[str, Any]: メソッドの詳細情報
    """
    # 基本となる情報辞書
    info = {
        'scales': get_method_supported_scales(method),
        'fp16_support': supports_half_precision(method),
        'name': method.value,
        'description': '',
        'performance': '中',  # 低, 中, 高, 最高
        'memory': '中',      # 低, 中, 高
        'speed': '中',       # 低, 中, 高
        'details': ''
    }
    
    # メソッド別の詳細情報を設定
    if method == SRMethod.OPENCV_NEAREST:
        info.update({
            'name': 'OpenCV 最近傍補間',
            'description': '最も単純な拡大方式です。画素値の繰り返しにより拡大します。',
            'performance': '低',
            'memory': '低',
            'speed': '高',
            'details': '最近傍補間は最も計算コストが低いですが、画質も最も低くなります。ピクセル化した見た目になります。'
        })
    elif method == SRMethod.OPENCV_BILINEAR:
        info.update({
            'name': 'OpenCV バイリニア補間',
            'description': '線形補間を使用した滑らかな拡大方式です。',
            'performance': '低',
            'memory': '低',
            'speed': '高',
            'details': 'バイリニア補間は計算効率が良く、それなりに自然な結果が得られますが、細部が失われます。'
        })
    elif method == SRMethod.OPENCV_CUBIC:
        info.update({
            'name': 'OpenCV バイキュービック補間',
            'description': '3次補間を使用した高品質な拡大方式です。',
            'performance': '中',
            'memory': '低',
            'speed': '中',
            'details': 'バイキュービック補間はバイリニアよりも高品質で、エッジがより鮮明になりますが、わずかにオーバーシュートが発生することがあります。'
        })
    elif method == SRMethod.OPENCV_LANCZOS:
        info.update({
            'name': 'OpenCV Lanczos補間',
            'description': 'Lanczosフィルタを使った高品質な補間方式です。',
            'performance': '中',
            'memory': '低',
            'speed': '中',
            'details': 'Lanczos補間は一般的に最も品質の高い従来の補間方法とされ、エッジの鮮明さと良好なディテールのバランスが特徴です。'
        })
    elif method == SRMethod.OPENCV_EDSR:
        info.update({
            'name': 'OpenCV EDSR',
            'description': '深層学習ベースのEnhanced Deep SR (EDSR)モデルです。',
            'performance': '中',
            'memory': '中',
            'speed': '中',
            'details': 'EDSRは残差ブロックを利用した畳み込みニューラルネットワークで、NTIRE 2017超解像コンテストの優勝モデルです。'
        })
    elif method == SRMethod.OPENCV_ESPCN:
        info.update({
            'name': 'OpenCV ESPCN',
            'description': '効率的なサブピクセル畳み込みネットワークです。',
            'performance': '中',
            'memory': '低',
            'speed': '高',
            'details': 'ESPCNは低解像度画像に直接畳み込みを適用し、最後にピクセルシャッフル層で高解像度に変換するため効率的です。'
        })
    elif method == SRMethod.OPENCV_FSRCNN:
        info.update({
            'name': 'OpenCV FSRCNN',
            'description': '高速なSuper-ResolutionCNNです。',
            'performance': '中',
            'memory': '低',
            'speed': '高',
            'details': 'FSRCNNはESPCNの改良版で、入力画像のサイズを最初に縮小せず、より少ないパラメータと計算時間で動作します。'
        })
    elif method == SRMethod.OPENCV_LAPSRN:
        info.update({
            'name': 'OpenCV LapSRN',
            'description': 'ラプラシアンピラミッド超解像ネットワークです。',
            'performance': '中',
            'memory': '中',
            'speed': '中',
            'details': 'LapSRNは段階的に解像度を上げ、各段階で細部を追加していくピラミッド構造を持つネットワークです。'
        })
    elif method == SRMethod.SWINIR_LIGHTWEIGHT:
        info.update({
            'name': 'SwinIR 軽量版',
            'description': 'メモリ効率を重視した軽量なSwinIRモデルです。',
            'performance': '低',
            'memory': '低',
            'speed': '高',
            'details': 'DIV2Kデータセットで学習された軽量SwinIRモデル。サイズが小さく処理速度が速いのが特徴です。'
        })
    elif method == SRMethod.SWINIR_CLASSICAL:
        info.update({
            'name': 'SwinIR 古典的超解像',
            'description': '古典的な超解像処理向けに最適化されたSwinIRモデルです。',
            'performance': '中',
            'memory': '中', 
            'speed': '中',
            'details': 'DF2Kデータセットで学習された古典的超解像モデル。バランスの良い品質と速度を提供します。'
        })
    elif method == SRMethod.SWINIR_REAL:
        info.update({
            'name': 'SwinIR 実写画像',
            'description': '実写画像の詳細を復元するSwinIRモデルです。',
            'performance': '高',
            'memory': '中',
            'speed': '中',
            'details': '実世界の画像向けにBSRGANデータセットで訓練されたモデル。詳細な復元能力が高いのが特徴です。'
        })
    elif method == SRMethod.SWINIR_LARGE:
        info.update({
            'name': 'SwinIR 実写画像（大）',
            'description': '高精細な実写画像超解像処理用の大規模SwinIRモデルです。',
            'performance': '最高',
            'memory': '高',
            'speed': '低',
            'details': 'より多くのトランスフォーマーレイヤーと大きなモデルサイズで、最高品質の復元を目指します。'
        })
    elif method == SRMethod.REALESRGAN:
        info.update({
            'name': 'Real-ESRGAN',
            'description': 'リアルな写真やアニメの復元に特化したモデルです。',
            'performance': '高',
            'memory': '中',
            'speed': '中',
            'details': '実写画像のノイズやぼけを修正しながら超解像する優れたモデルで、顔強調機能もサポートしています。'
        })
    
    return info

def get_all_method_infos() -> Dict[SRMethod, Dict[str, Any]]:
    """
    すべての超解像メソッドの詳細情報を取得
    
    Returns:
        Dict[SRMethod, Dict[str, Any]]: すべてのメソッドの詳細情報
    """
    from sr.sr_base import SuperResolutionBase
    available_methods = SuperResolutionBase.get_available_methods()
    
    return {method: get_method_info(method) for method in available_methods}
