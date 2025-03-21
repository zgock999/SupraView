"""超解像メソッド定義"""

import enum

class SRMethod(enum.Enum):
    """超解像メソッド"""
    BICUBIC = "bicubic"
    LANCZOS = "lanczos"
    EDSR = "edsr"
    ESPCN = "espcn"
    FSRCNN = "fsrcnn"
    LAPSRN = "lapsrn"
    
    # OpenCV系
    OPENCV_CUBIC = "opencv_cubic"
    OPENCV_LANCZOS4 = "opencv_lanczos4"
    OPENCV_NEAREST = "opencv_nearest"
    OPENCV_LINEAR = "opencv_linear"
    OPENCV_AREA = "opencv_area"
    
    # ESRGANシリーズ
    ESRGAN_GENERAL = "esrgan_general"
    ESRGAN_ANIME = "esrgan_anime"
    ESRGAN_PHOTO = "esrgan_photo"
    REAL_ESRGAN = "real_esrgan"
    
    # SwinIRシリーズ
    SWINIR_REAL_PHOTO = "swinir_real_photo"
    SWINIR_REAL_PHOTO_LARGE = "swinir_real_photo_large"
    SWINIR_CLASSICAL = "swinir_classical"
    SWINIR_LIGHTWEIGHT = "swinir_lightweight"
    
    # HAT
    HAT = "hat"
    
    @classmethod
    def get_method_display_name(cls, method):
        """メソッド名の表示用文字列を取得"""
        display_names = {
            cls.BICUBIC: "バイキュービック法",
            cls.LANCZOS: "ランチョス法",
            cls.EDSR: "EDSR",
            cls.ESPCN: "ESPCN",
            cls.FSRCNN: "FSRCNN",
            cls.LAPSRN: "LapSRN",
            
            cls.OPENCV_CUBIC: "OpenCV Bicubic",
            cls.OPENCV_LANCZOS4: "OpenCV Lanczos4",
            cls.OPENCV_NEAREST: "OpenCV Nearest",
            cls.OPENCV_LINEAR: "OpenCV Linear",
            cls.OPENCV_AREA: "OpenCV Area",
            
            cls.ESRGAN_GENERAL: "ESRGAN (一般)",
            cls.ESRGAN_ANIME: "ESRGAN (アニメ)",
            cls.ESRGAN_PHOTO: "ESRGAN (写真)",
            cls.REAL_ESRGAN: "Real-ESRGAN",
            
            cls.SWINIR_REAL_PHOTO: "SwinIR (実写)",
            cls.SWINIR_REAL_PHOTO_LARGE: "SwinIR (実写-大)",
            cls.SWINIR_CLASSICAL: "SwinIR (古典的)",
            cls.SWINIR_LIGHTWEIGHT: "SwinIR (軽量)",
            
            cls.HAT: "HAT",
        }
        return display_names.get(method, str(method))
