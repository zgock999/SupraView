"""
PILLOWを使用したGIFデコーダー

PILLOWライブラリを使用して、GIFファイル（アニメーション含む）をデコードする
アニメーションGIFの場合は先頭フレームのみを表示する
"""

import numpy as np
from io import BytesIO
from typing import List, Optional, Tuple

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    import warnings
    warnings.warn("PILLOWがインストールされていないため、GIFデコーダーは使用できません。pip install pillow でインストールしてください。")

from .decoder import ImageDecoder
from .common import DecodingError


class GIFImageDecoder(ImageDecoder):
    """
    PILLOWを使用したGIFデコーダー
    
    GIFファイルに特化したデコーダー。アニメーションGIFの場合は先頭フレームのみを表示する。
    """
    
    def __init__(self):
        """初期化時に必要なPILLOWライブラリが利用可能か確認"""
        super().__init__()
        if not HAS_PILLOW:
            raise ImportError("PILLOWライブラリがインストールされていません。pip install pillow でインストールしてください。")
    
    @property
    def supported_extensions(self) -> List[str]:
        """
        このデコーダーがサポートする拡張子のリスト
        
        Returns:
            List[str]: サポートされている拡張子のリスト
        """
        return ['.gif']
    
    def decode(self, data: bytes) -> Optional[np.ndarray]:
        """
        バイトデータからGIF画像をデコードしてnumpy配列に変換する
        アニメーションGIFの場合は先頭フレームのみを返す
        
        Args:
            data (bytes): デコードする画像のバイトデータ
            
        Returns:
            Optional[np.ndarray]: デコードされた画像のnumpy配列
                                  デコードに失敗した場合はNone
        """
        try:
            # PILLOWでデータを読み込み
            with BytesIO(data) as buffer:
                # 先頭フレームのみをロード
                with Image.open(buffer) as img:
                    # 画像が透過情報を持っているか確認
                    has_transparency = img.info.get('transparency') is not None or 'transparency' in img.info
                    
                    # パレットモードで透過がある場合の特別処理
                    if img.mode == 'P' and has_transparency:
                        # パレットモードの場合、RGBAに変換して透過を保持
                        img = img.convert('RGBA')
                    elif img.mode == 'P':
                        # 透過情報がないパレットモードはRGBに変換
                        img = img.convert('RGB')
                    elif img.mode != 'RGBA' and img.mode != 'RGB':
                        # その他のモードは適切な形式に変換
                        if has_transparency:
                            img = img.convert('RGBA')
                        else:
                            img = img.convert('RGB')
                    
                    # numpy配列に変換
                    img_array = np.array(img)
                    
                    # 単一フレームのみを返す
                    return img_array
                    
        except Exception as e:
            print(f"GIFデコードエラー: {e}")
            raise DecodingError(f"GIFのデコードに失敗しました: {str(e)}")
        
        return None
    
    def get_image_info(self, data: bytes) -> Optional[Tuple[int, int, int]]:
        """
        GIF画像の基本情報を取得する
        
        Args:
            data (bytes): 情報を取得する画像のバイトデータ
            
        Returns:
            Optional[Tuple[int, int, int]]: (幅, 高さ, チャンネル数) の形式の情報、
                                           取得できない場合は None
        """
        try:
            # PILLOWでデータを読み込み
            with BytesIO(data) as buffer:
                with Image.open(buffer) as img:
                    width, height = img.size
                    
                    # モードに基づいてチャンネル数を判断
                    if img.mode == 'RGB':
                        channels = 3
                    elif img.mode == 'RGBA':
                        channels = 4
                    elif img.mode == 'L':
                        channels = 1
                    elif img.mode == 'P':
                        # パレットモードの場合、通常はRGBAに変換されるので4
                        channels = 4
                    else:
                        # その他のモード（グレースケールなど）は1チャンネルと見なす
                        channels = 1
                    
                    # アニメーションGIFの場合はフレーム数の情報も表示
                    is_animated = hasattr(img, 'n_frames') and img.n_frames > 1
                    
                    # アニメーション情報を含めた詳細情報を返す
                    if is_animated:
                        print(f"アニメーションGIF: {img.n_frames}フレーム、先頭フレームのみ表示")
                    
                    return (width, height, channels)
                    
        except Exception as e:
            print(f"GIF情報取得エラー: {e}")
            return None


# デコーダーがロード可能かテストするコード
if __name__ == "__main__":
    try:
        decoder = GIFImageDecoder()
        print(f"GIFデコーダーを初期化しました。サポート形式: {decoder.supported_extensions}")
    except ImportError as e:
        print(f"GIFデコーダーの初期化に失敗しました: {e}")
