"""
超解像処理モジュールのパッケージ定義
"""
# 基本クラスを直接インポート
from sr.sr_base import SuperResolutionBase, SRMethod, SRResult

# サブモジュールもインポートして利用可能に
try:
    from sr.sr_opencv import OpenCVSuperResolution
except ImportError:
    print("Warning: sr_opencvモジュールをインポートできませんでした")
    
try:
    from sr.sr_contrib import OpenCVDnnSuperResolution
except ImportError:
    print("Warning: sr_contribモジュールをインポートできませんでした")

# 公開するシンボルを指定
__all__ = [
    'SuperResolutionBase', 
    'SRMethod', 
    'SRResult', 
    'OpenCVSuperResolution',
    'OpenCVDnnSuperResolution'
]
