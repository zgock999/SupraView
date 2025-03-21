"""
超解像モデルのダウンロードユーティリティ

以下のモデルをダウンロードします：
- OpenCV DNN SuperRes モデル
- Real-ESRGAN モデル
- SwinIR モデル
"""
import os
import sys
import argparse
import platform
import time
from pathlib import Path
import urllib.request
import hashlib
from typing import Dict, List, Tuple, Optional

# プログレスバーの表示をサポート
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# モデルの定義
MODEL_URLS = {
    # OpenCV DNN Super Resolution モデル
    "EDSR_x2.pb": "https://github.com/fannymonori/TF-EDSR/raw/master/export/EDSR_x2.pb",
    "EDSR_x3.pb": "https://github.com/fannymonori/TF-EDSR/raw/master/export/EDSR_x3.pb",
    "EDSR_x4.pb": "https://github.com/fannymonori/TF-EDSR/raw/master/export/EDSR_x4.pb",
    "ESPCN_x2.pb": "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x2.pb",
    "ESPCN_x3.pb": "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x3.pb",
    "ESPCN_x4.pb": "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x4.pb",
    "FSRCNN_x2.pb": "https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x2.pb",
    "FSRCNN_x3.pb": "https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x3.pb",
    "FSRCNN_x4.pb": "https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x4.pb",
    "LapSRN_x2.pb": "https://github.com/fannymonori/TF-LapSRN/raw/master/export/LapSRN_x2.pb",
    "LapSRN_x4.pb": "https://github.com/fannymonori/TF-LapSRN/raw/master/export/LapSRN_x4.pb",
    "LapSRN_x8.pb": "https://github.com/fannymonori/TF-LapSRN/raw/master/export/LapSRN_x8.pb",

    # Real-ESRGAN モデル
    "RealESRGAN_x4plus.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
    "RealESRGAN_x4plus_anime_6B.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
    "RealESRGAN_x2plus.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    "realesr-animevideov3.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
    "realesr-general-x4v3.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",

    # SwinIR モデル
    "001_classicalSR_DIV2K_s48w8_SwinIR-M_x2.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DIV2K_s48w8_SwinIR-M_x2.pth",
    "001_classicalSR_DIV2K_s48w8_SwinIR-M_x3.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DIV2K_s48w8_SwinIR-M_x3.pth",
    "001_classicalSR_DIV2K_s48w8_SwinIR-M_x4.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DIV2K_s48w8_SwinIR-M_x4.pth",
    "001_classicalSR_DIV2K_s48w8_SwinIR-M_x8.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DIV2K_s48w8_SwinIR-M_x8.pth",
    "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth",
    "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x3.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x3.pth",
    "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth",
    "003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth",
    "003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_GAN.pth": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_GAN.pth",
}

# モデルカテゴリの定義
MODEL_CATEGORIES = {
    "opencv": [
        "EDSR_x2.pb", "EDSR_x3.pb", "EDSR_x4.pb",
        "ESPCN_x2.pb", "ESPCN_x3.pb", "ESPCN_x4.pb",
        "FSRCNN_x2.pb", "FSRCNN_x3.pb", "FSRCNN_x4.pb",
        "LapSRN_x2.pb", "LapSRN_x4.pb", "LapSRN_x8.pb",
    ],
    "realesrgan": [
        "RealESRGAN_x4plus.pth", "RealESRGAN_x4plus_anime_6B.pth", 
        "RealESRGAN_x2plus.pth", "realesr-animevideov3.pth", 
        "realesr-general-x4v3.pth",
    ],
    "swinir": [
        "001_classicalSR_DIV2K_s48w8_SwinIR-M_x2.pth",
        "001_classicalSR_DIV2K_s48w8_SwinIR-M_x3.pth",
        "001_classicalSR_DIV2K_s48w8_SwinIR-M_x4.pth",
        "001_classicalSR_DIV2K_s48w8_SwinIR-M_x8.pth",
        "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth",
        "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x3.pth",
        "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth",
        "003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth",
        "003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_GAN.pth",
    ]
}

# モデルのハッシュ（MD5）- 一部のみ定義
MODEL_HASHES = {
    "EDSR_x4.pb": "5c710c6a5a3dfe63fde0f12bfed865f0",
    "RealESRGAN_x4plus.pth": "4fa03b6255fcc7ec291b4b2f48270fa6",
    "001_classicalSR_DIV2K_s48w8_SwinIR-M_x4.pth": "7c1dea1cd3545102140c1b44e000286d",
}

def download_file(url: str, output_path: str, desc: Optional[str] = None) -> bool:
    """
    ファイルをダウンロードする関数
    
    Args:
        url: ダウンロードURL
        output_path: 保存先パス
        desc: 表示名 (tqdmのバーに表示)
    
    Returns:
        bool: ダウンロード成功かどうか
    """
    desc = desc or os.path.basename(output_path)
    
    # 出力ディレクトリの作成
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        # URLのセットアップ
        with urllib.request.urlopen(url) as response:
            total_size = int(response.info().get('Content-Length', 0))
            
            # tqdmがインストールされている場合はプログレスバーを表示
            if TQDM_AVAILABLE:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=desc) as pbar:
                    with open(output_path, 'wb') as out_file:
                        chunk_size = 8192
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            out_file.write(chunk)
                            pbar.update(len(chunk))
            else:
                # tqdmがない場合のシンプルなプログレス表示
                print(f"ダウンロード中: {desc}")
                with open(output_path, 'wb') as out_file:
                    chunk_size = 8192
                    downloaded_size = 0
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = downloaded_size / total_size * 100
                            sys.stdout.write(f"\r{'▓' * int(progress // 2)}{'░' * (50 - int(progress // 2))} {progress:.1f}% [{downloaded_size}/{total_size} bytes]")
                            sys.stdout.flush()
                print("\r完了" + " " * 70)
        
        # サイズチェック
        file_size = os.path.getsize(output_path)
        if total_size > 0 and file_size != total_size:
            print(f"警告: ダウンロードしたファイルのサイズが予期しない値です ({file_size} != {total_size} bytes)")
            if file_size < 10000:  # 非常に小さいファイルは不正の可能性
                return False
        
        # ハッシュチェック（ハッシュが定義されている場合）
        filename = os.path.basename(output_path)
        if filename in MODEL_HASHES:
            file_hash = compute_md5(output_path)
            if file_hash != MODEL_HASHES[filename]:
                print(f"警告: ハッシュ値が一致しません: {file_hash} != {MODEL_HASHES[filename]}")
                return False
        
        return True
    
    except Exception as e:
        print(f"ダウンロード中にエラーが発生しました: {e}")
        if os.path.exists(output_path):  # 部分的にダウンロードされたファイルを削除
            os.remove(output_path)
        return False

def compute_md5(file_path: str) -> str:
    """ファイルのMD5ハッシュを計算する"""
    with open(file_path, 'rb') as f:
        file_hash = hashlib.md5()
        chunk = f.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(8192)
    return file_hash.hexdigest()

def download_model_category(category: str, base_dir: Optional[str] = None) -> bool:
    """
    特定のカテゴリのモデルをすべてダウンロードする
    
    Args:
        category: カテゴリ名 ('opencv', 'realesrgan', 'swinir')
        base_dir: モデルを保存するベースディレクトリ
    
    Returns:
        bool: すべてのダウンロードが成功したかどうか
    """
    if category not in MODEL_CATEGORIES:
        print(f"エラー: カテゴリ '{category}' は存在しません")
        return False
    
    # 保存先ディレクトリの設定
    if base_dir is None:
        base_dir = os.path.join('.', 'models')
    
    # カテゴリごとにディレクトリを分ける
    model_dir = os.path.join(base_dir, category)
    os.makedirs(model_dir, exist_ok=True)
    
    # カテゴリ内のモデルをダウンロード
    models = MODEL_CATEGORIES[category]
    success_count = 0
    
    print(f"{category}モデルのダウンロードを開始します（{len(models)}個）...")
    
    for model_name in models:
        if model_name not in MODEL_URLS:
            print(f"警告: モデル '{model_name}' のURLが登録されていません")
            continue
        
        url = MODEL_URLS[model_name]
        output_path = os.path.join(model_dir, model_name)
        
        # ファイルが既に存在するか確認
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            # ハッシュチェック（ハッシュが定義されている場合）
            if model_name in MODEL_HASHES:
                file_hash = compute_md5(output_path)
                if file_hash == MODEL_HASHES[model_name]:
                    print(f"'{model_name}' は既に存在し、ハッシュも一致しています - スキップします")
                    success_count += 1
                    continue
                else:
                    print(f"'{model_name}' は既に存在しますが、ハッシュが一致しません - 再ダウンロードします")
            else:
                # ファイルサイズが一定以上あれば成功とみなす
                if file_size > 1000000:  # 1MB以上のファイルは成功とみなす
                    print(f"'{model_name}' は既に存在します - スキップします")
                    success_count += 1
                    continue
        
        # 実際のダウンロード実行
        print(f"ダウンロード中: {model_name}")
        if download_file(url, output_path, desc=model_name):
            print(f"'{model_name}' のダウンロードが完了しました")
            success_count += 1
        else:
            print(f"'{model_name}' のダウンロードに失敗しました")
    
    # 結果表示
    print(f"{category}モデル: {success_count}/{len(models)}個のダウンロードが成功しました")
    return success_count == len(models)

def download_all_models(base_dir: Optional[str] = None) -> bool:
    """すべてのモデルをダウンロードする"""
    print("すべてのモデルのダウンロードを開始します...")
    
    success = True
    for category in MODEL_CATEGORIES.keys():
        print(f"\n----- {category} モデル -----")
        if not download_model_category(category, base_dir):
            success = False
    
    return success

def download_recommended_models(base_dir: Optional[str] = None) -> bool:
    """推奨モデルのみをダウンロードする"""
    print("推奨モデルのダウンロードを開始します...")
    
    # 推奨モデルの定義
    recommended_models = {
        "opencv": ["ESPCN_x4.pb", "EDSR_x4.pb", "FSRCNN_x4.pb"],
        "realesrgan": ["RealESRGAN_x4plus.pth", "RealESRGAN_x4plus_anime_6B.pth"],
        "swinir": ["001_classicalSR_DIV2K_s48w8_SwinIR-M_x4.pth", "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth"]
    }
    
    success = True
    for category, models in recommended_models.items():
        print(f"\n----- {category} 推奨モデル -----")
        
        # 保存先ディレクトリの設定
        if base_dir is None:
            model_dir = os.path.join('.', 'models', category)
        else:
            model_dir = os.path.join(base_dir, category)
            
        os.makedirs(model_dir, exist_ok=True)
        
        success_count = 0
        for model_name in models:
            if model_name not in MODEL_URLS:
                print(f"警告: モデル '{model_name}' のURLが登録されていません")
                continue
                
            url = MODEL_URLS[model_name]
            output_path = os.path.join(model_dir, model_name)
            
            # ファイルが既に存在するか確認
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000000:
                print(f"'{model_name}' は既に存在します - スキップします")
                success_count += 1
                continue
            
            # 実際のダウンロード実行
            print(f"ダウンロード中: {model_name}")
            if download_file(url, output_path, desc=model_name):
                print(f"'{model_name}' のダウンロードが完了しました")
                success_count += 1
            else:
                print(f"'{model_name}' のダウンロードに失敗しました")
                success = False
        
        print(f"{category} 推奨モデル: {success_count}/{len(models)}個のダウンロードが成功しました")
    
    return success

def parse_args():
    parser = argparse.ArgumentParser(description='超解像モデルのダウンロードツール')
    parser.add_argument('--category', type=str, choices=['opencv', 'realesrgan', 'swinir', 'all', 'recommended'],
                        default='recommended', help='ダウンロードするモデルカテゴリ (デフォルト: recommended)')
    parser.add_argument('--output', type=str, default=None,
                        help='モデルの保存先ディレクトリ (デフォルト: ./models)')
    return parser.parse_args()

def main():
    # コマンドライン引数の解析
    args = parse_args()
    
    # カテゴリに応じてダウンロード
    if args.category == 'all':
        success = download_all_models(args.output)
    elif args.category == 'recommended':
        success = download_recommended_models(args.output)
    else:
        success = download_model_category(args.category, args.output)
    
    # 結果表示
    if success:
        print("すべてのモデルのダウンロードが完了しました。")
        return 0
    else:
        print("一部のモデルのダウンロードに失敗しました。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
