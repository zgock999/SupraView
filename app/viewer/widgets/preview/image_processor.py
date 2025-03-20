"""
画像処理モジュール

画像データのロード、変換、処理のためのユーティリティを提供します。
"""

import os
import sys
import io
from typing import Dict, Any, Optional, Tuple, Union
import numpy as np

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print, DEBUG, INFO, WARNING, ERROR

# デコーダーインターフェースをインポート
from decoder.interface import decode_image, get_supported_image_extensions

# PILを使用して画像形式の変換とメタデータ抽出を行う
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    HAS_PIL = True
except ImportError:
    log_print(WARNING, "PIL（Pillow）が見つかりません。一部の画像形式が表示できない可能性があります。")
    log_print(INFO, "pip install pillow でインストールすることをお勧めします。")
    HAS_PIL = False

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPixmap
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)


# サポートする画像形式の拡張子
SUPPORTED_EXTENSIONS = get_supported_image_extensions()


def get_supported_extensions() -> list:
    """
    サポートされている画像形式の拡張子のリストを取得
    
    Returns:
        サポートされている拡張子のリスト
    """
    return SUPPORTED_EXTENSIONS


def extract_image_info(image_data: bytes, path: str = None) -> Dict[str, Any]:
    """
    画像データからメタデータを抽出する
    
    Args:
        image_data: 画像のバイトデータ
        path: 画像のパス（オプション）
        
    Returns:
        画像情報の辞書
    """
    info = {}
    
    # 基本的なファイル情報
    if path:
        info['filename'] = os.path.basename(path)
        info['path'] = path
    
    info['size_bytes'] = len(image_data)
    
    # PILが利用可能な場合はメタデータを抽出
    if HAS_PIL:
        try:
            img = Image.open(io.BytesIO(image_data))
            
            # 基本情報
            info['format'] = img.format
            info['mode'] = img.mode
            info['width'] = img.width
            info['height'] = img.height
            
            # EXIF情報があれば抽出
            if hasattr(img, '_getexif') and callable(img._getexif):
                exif = img._getexif()
                if exif:
                    exif_data = {}
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        exif_data[tag] = value
                    info['exif'] = exif_data
            
        except Exception as e:
            log_print(ERROR, f"画像メタデータの抽出に失敗しました: {e}")
    
    return info


def load_image_from_bytes(image_data: bytes, path: str = None) -> Tuple[Optional[QPixmap], Optional[np.ndarray], Dict[str, Any]]:
    """
    バイトデータから画像を読み込み、QPixmapとNumPy配列を返す
    
    Args:
        image_data: 画像のバイトデータ
        path: 画像のパス（情報表示用、省略可能）
    
    Returns:
        (QPixmap, NumPy配列, 画像情報辞書) のタプル
        失敗した場合はそれぞれNoneが返される
    """
    pixmap = None
    numpy_array = None
    image_info = {}
    
    try:
        # 画像情報を抽出
        image_info = extract_image_info(image_data, path)
        
        # まずデコーダーでNumPy配列への変換を試みる
        if path:
            filename = os.path.basename(path)
            numpy_array = decode_image(filename, image_data)
            
            if numpy_array is not None:
                log_print(INFO, f"デコーダーでデコードしました: 形状={numpy_array.shape}, dtype={numpy_array.dtype}")
                
                # NumPy配列からQPixmapを作成
                pixmap = numpy_to_pixmap(numpy_array)
                if pixmap is not None:
                    log_print(INFO, "NumPy配列からQPixmapへの変換に成功しました")
                    return pixmap, numpy_array, image_info
        
        # デコーダーが失敗した場合、QPixmapで直接読み込みを試みる
        log_print(INFO, "デコーダーでのデコードに失敗したため、QPixmap直接読み込みを試みます")
        pixmap = QPixmap()
        loaded = pixmap.loadFromData(image_data)
        
        if not loaded:
            # 標準の方法で読み込めない場合、PILを使用して変換を試みる
            if HAS_PIL:
                log_print(INFO, "QPixmapで直接読み込めないため、PILを使用して変換を試みます")
                try:
                    img = Image.open(io.BytesIO(image_data))
                    # RGBAモードに変換して一貫性を確保
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    # PILのImageをQImageに変換
                    qim = QImage(img.tobytes(), img.width, img.height, QImage.Format_RGBA8888)
                    pixmap = QPixmap.fromImage(qim)
                    loaded = True
                except Exception as e:
                    log_print(ERROR, f"PIL変換中にエラーが発生しました: {e}")
                    return None, None, image_info
            else:
                log_print(ERROR, "画像形式がサポートされていません。PIL（Pillow）をインストールすると表示できる可能性があります")
                return None, None, image_info
        
        if loaded and not pixmap.isNull():
            return pixmap, numpy_array, image_info
        else:
            log_print(ERROR, "画像の読み込みに失敗しました")
            return None, None, image_info
            
    except Exception as e:
        log_print(ERROR, f"画像読み込み中にエラーが発生しました: {e}")
        return None, None, image_info


def numpy_to_pixmap(numpy_array: np.ndarray) -> Optional[QPixmap]:
    """
    NumPy配列からQPixmapを生成する
    
    Args:
        numpy_array: 変換する画像データのNumPy配列
    
    Returns:
        生成されたQPixmap、失敗した場合はNone
    """
    if numpy_array is None:
        return None
    
    try:
        # NumPy配列の形状を確認
        height, width = numpy_array.shape[:2]
        channels = 1 if len(numpy_array.shape) == 2 else numpy_array.shape[2]
        
        # QImageの形式を決定
        if channels == 1:
            # グレースケール画像
            q_image = QImage(numpy_array.data, width, height, width, QImage.Format_Grayscale8)
        elif channels == 3:
            # RGB画像
            q_image = QImage(numpy_array.data, width, height, width * 3, QImage.Format_RGB888)
        elif channels == 4:
            # RGBA画像
            q_image = QImage(numpy_array.data, width, height, width * 4, QImage.Format_RGBA8888)
        else:
            log_print(ERROR, f"サポートされていないチャンネル数です: {channels}")
            return None
        
        # QImageからQPixmapを作成
        pixmap = QPixmap.fromImage(q_image)
        
        if pixmap.isNull():
            log_print(ERROR, "QPixmapの作成に失敗しました")
            return None
        
        return pixmap
        
    except Exception as e:
        log_print(ERROR, f"NumPy配列からQPixmapへの変換に失敗しました: {e}")
        return None


def format_image_info(info: Dict[str, Any]) -> str:
    """
    画像情報を人間が読みやすい形式にフォーマットする
    
    Args:
        info: 画像情報の辞書
    
    Returns:
        フォーマットされた情報文字列
    """
    if not info:
        return "画像情報なし"
    
    lines = []
    
    # ファイル情報
    if 'filename' in info:
        lines.append(f"ファイル: {info['filename']}")
    
    # 画像サイズ
    if 'width' in info and 'height' in info:
        lines.append(f"サイズ: {info['width']}x{info['height']}ピクセル")
    
    # ファイルサイズ
    if 'size_bytes' in info:
        size_kb = info['size_bytes'] / 1024
        lines.append(f"ファイルサイズ: {size_kb:.1f} KB ({info['size_bytes']:,} バイト)")
    
    # 画像形式
    if 'format' in info:
        lines.append(f"形式: {info['format']}")
    
    # カラーモード
    if 'mode' in info:
        lines.append(f"カラーモード: {info['mode']}")
    
    # EXIF情報（重要なものだけ）
    if 'exif' in info:
        exif = info['exif']
        
        # カメラモデル
        if 'Model' in exif:
            lines.append(f"カメラ: {exif['Model']}")
        
        # 撮影日時
        if 'DateTime' in exif:
            lines.append(f"撮影日時: {exif['DateTime']}")
        
        # 露出時間
        if 'ExposureTime' in exif:
            exposure = exif['ExposureTime']
            if isinstance(exposure, tuple) and len(exposure) == 2:
                lines.append(f"露出時間: {exposure[0]}/{exposure[1]}秒")
            else:
                lines.append(f"露出時間: {exposure}")
        
        # ISO感度
        if 'ISOSpeedRatings' in exif:
            lines.append(f"ISO感度: {exif['ISOSpeedRatings']}")
    
    return "\n".join(lines)
