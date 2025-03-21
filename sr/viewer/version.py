"""
ビューアーアプリケーションのバージョン情報
"""

__version__ = "1.0.0"
__author__ = "SR Viewer Developer"
__description__ = "Super Resolution Viewer Application"

# バージョン履歴
VERSION_HISTORY = {
    "1.0.0": "初期リリース: SwinIR, Real-ESRGAN, OpenCVベースの超解像モデルをサポート",
}

def get_version_info():
    """バージョン情報と依存関係情報を取得"""
    import sys
    import platform
    
    info = {
        "version": __version__,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
    }
    
    # 依存パッケージのバージョン情報を取得
    try:
        import torch
        info["torch"] = torch.__version__
    except ImportError:
        info["torch"] = "Not installed"
    
    try:
        import cv2
        info["opencv"] = cv2.__version__
    except ImportError:
        info["opencv"] = "Not installed"
    
    try:
        import numpy as np
        info["numpy"] = np.__version__
    except ImportError:
        info["numpy"] = "Not installed"
    
    try:
        from PySide6 import __version__ as pyside_version
        info["pyside"] = pyside_version
    except ImportError:
        info["pyside"] = "Not installed"
    
    return info
