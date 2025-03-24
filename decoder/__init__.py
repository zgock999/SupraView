"""
画像デコーダーパッケージ

様々な画像形式をデコードするためのインターフェースとデコーダー実装を提供します。
"""

from .base import BaseDecoder
from .common import DecodingError
from .interface import (
    decode_image,
    get_supported_image_extensions,
    get_decoder_manager,
    select_image_decoder  # 新しい関数をインポート
)
from .decoder import ImageDecoder
from .cv2_decoder import CV2ImageDecoder
from .mag_decoder import MAGImageDecoder

__all__ = [
    'BaseDecoder',
    'DecodingError',
    'decode_image',
    'get_supported_image_extensions',
    'get_decoder_manager',
    'select_image_decoder',  # 新しい関数をエクスポートリストに追加
    'ImageDecoder',
    'CV2ImageDecoder',
    'MAGImageDecoder',
    'PIImageDecoder'  # PIデコーダーをエクスポートリストに追加
]
