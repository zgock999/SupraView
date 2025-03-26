"""
画像モデルモジュール

プレビューウィンドウ内の画像情報を管理する集中型のモデルクラス
"""

import os
import sys
from typing import Optional, Dict, Any, List, Tuple

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print, INFO, WARNING, ERROR, DEBUG, CRITICAL

try:
    from PySide6.QtGui import QPixmap
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)


class ImageModel:
    """プレビューウィンドウ内の画像情報を管理するモデルクラス"""
    
    def __init__(self):
        """モデルの初期化"""
        # 最大2枚の画像情報を保持（デュアルビュー用）
        self._images = [
            {
                'pixmap': None,      # 表示用のQPixmap
                'data': None,        # 元の画像データ（bytes）
                'numpy_array': None, # NumPy配列形式の画像データ
                'info': {},          # 画像の情報（サイズ、形式など）
                'path': "",          # 画像のパス
                'modified': False    # 画像が修正されたかどうか
            },
            {
                'pixmap': None,
                'data': None,
                'numpy_array': None,
                'info': {},
                'path': "",
                'modified': False
            }
        ]
        
        # 表示モード情報
        self._fit_to_window_mode = True  # デフォルトはウィンドウに合わせる
        self._zoom_factor = 1.0          # 拡大率
        
        # window.pyから移譲する表示モード関連の設定
        self._dual_view = False          # デュアルビューが有効かどうか
        self._browser_pages = 1          # ブラウザ表示ページ数（デフォルトは1）
        self._browser_shift = False      # ブラウザシフトモード
        self._right_to_left = False      # 右から左への表示（デフォルトは左から右）
        
        log_print(DEBUG, "ImageModel: 初期化されました")
    
    def set_image(self, index: int, pixmap: QPixmap, data: bytes, numpy_array: Any, info: Dict, path: str) -> bool:
        """
        指定インデックスに画像情報を設定
        
        Args:
            index: 画像インデックス (0または1)
            pixmap: 表示用画像
            data: 元の画像データ (bytes)
            numpy_array: NumPy配列形式の画像データ
            info: 画像情報の辞書
            path: 画像のパス
            
        Returns:
            bool: 設定に成功したかどうか
        """
        if index not in [0, 1]:
            log_print(ERROR, f"ImageModel: 無効なインデックス {index}")
            return False
            
        self._images[index]['pixmap'] = pixmap
        self._images[index]['data'] = data
        self._images[index]['numpy_array'] = numpy_array
        self._images[index]['info'] = info or {}
        self._images[index]['path'] = path
        self._images[index]['modified'] = False
        
        log_print(DEBUG, f"ImageModel: インデックス {index} に画像を設定 - {path}")
        return True
    
    def clear_image(self, index: int) -> bool:
        """
        指定インデックスの画像情報をクリア
        
        Args:
            index: クリアする画像インデックス
            
        Returns:
            bool: 成功したかどうか
        """
        if index not in [0, 1]:
            log_print(ERROR, f"ImageModel: 無効なインデックス {index}")
            return False
            
        self._images[index]['pixmap'] = None
        self._images[index]['data'] = None
        self._images[index]['numpy_array'] = None
        self._images[index]['info'] = {}
        self._images[index]['path'] = ""
        self._images[index]['modified'] = False
        
        log_print(DEBUG, f"ImageModel: インデックス {index} の画像をクリアしました")
        return True
    
    def get_image(self, index: int) -> Tuple[Optional[QPixmap], Optional[bytes], Any, Dict, str]:
        """
        指定インデックスの画像情報を取得
        
        Args:
            index: 取得する画像インデックス
            
        Returns:
            Tuple: (pixmap, data, numpy_array, info, path)
        """
        if index not in [0, 1]:
            log_print(ERROR, f"ImageModel: 無効なインデックス {index}")
            return None, None, None, {}, ""
        
        img = self._images[index]
        return img['pixmap'], img['data'], img['numpy_array'], img['info'], img['path']
    
    def get_pixmap(self, index: int) -> Optional[QPixmap]:
        """
        指定インデックスの画像ピクスマップを取得
        
        Args:
            index: 取得する画像インデックス
            
        Returns:
            QPixmap: 画像のピクスマップ (または None)
        """
        if index not in [0, 1] or not self._images[index]['pixmap']:
            return None
        
        return self._images[index]['pixmap']
    
    def get_path(self, index: int) -> str:
        """
        指定インデックスの画像パスを取得
        
        Args:
            index: 取得する画像インデックス
            
        Returns:
            str: 画像のパス
        """
        if index not in [0, 1]:
            return ""
        
        return self._images[index]['path']
    
    def get_info(self, index: int) -> Dict:
        """
        指定インデックスの画像情報を取得
        
        Args:
            index: 取得する画像インデックス
            
        Returns:
            Dict: 画像の情報辞書
        """
        if index not in [0, 1]:
            return {}
        
        return self._images[index]['info']
    
    def has_image(self, index: int) -> bool:
        """
        指定インデックスに画像が存在するか確認
        
        Args:
            index: 確認する画像インデックス
            
        Returns:
            bool: 画像が存在すればTrue
        """
        if index not in [0, 1]:
            return False
        
        return self._images[index]['pixmap'] is not None
    
    def get_status_info(self) -> str:
        """
        ステータスバーに表示する画像情報テキストを生成
        
        Returns:
            str: 表示用ステータステキスト
        """
        try:
            # シングルビューまたはデュアルビューの1画面目の情報
            status_msg = ""
            
            # 1枚目の画像情報
            if self.has_image(0):
                pixmap = self._images[0]['pixmap']
                data = self._images[0]['data']
                path = self._images[0]['path']
                filename = os.path.basename(path) if path else "画像"
                width = pixmap.width()
                height = pixmap.height()
                size_kb = len(data) / 1024 if data else 0
                
                # NumPy情報があれば追加
                numpy_array = self._images[0]['numpy_array']
                if numpy_array is not None:
                    channels = 1 if len(numpy_array.shape) == 2 else numpy_array.shape[2]
                    status_msg = f"{filename} - {width}x{height} - {channels}チャンネル ({size_kb:.1f} KB)"
                else:
                    status_msg = f"{filename} - {width}x{height} ({size_kb:.1f} KB)"
            
            # 2枚目の画像情報（あれば）
            if self.has_image(1):
                if status_msg:
                    status_msg += " | "
                
                pixmap = self._images[1]['pixmap']
                data = self._images[1]['data']
                path = self._images[1]['path']
                filename = os.path.basename(path) if path else "画像"
                width = pixmap.width()
                height = pixmap.height()
                size_kb = len(data) / 1024 if data else 0
                
                numpy_array = self._images[1]['numpy_array']
                if numpy_array is not None:
                    channels = 1 if len(numpy_array.shape) == 2 else numpy_array.shape[2]
                    status_msg += f"{filename} - {width}x{height} - {channels}チャンネル ({size_kb:.1f} KB)"
                else:
                    status_msg += f"{filename} - {width}x{height} ({size_kb:.1f} KB)"
            
            return status_msg
            
        except Exception as e:
            log_print(ERROR, f"ステータス情報の生成に失敗しました: {e}")
            return ""
    
    def set_display_mode(self, fit_to_window: bool) -> None:
        """
        表示モードを設定
        
        Args:
            fit_to_window: ウィンドウに合わせて表示する場合はTrue、原寸大表示の場合はFalse
        """
        # 状態が変わった場合のみ変更を記録
        changed = self._fit_to_window_mode != fit_to_window
        
        # 表示モードを更新
        self._fit_to_window_mode = fit_to_window
        
        # 表示モード変更時に modified フラグを設定（本当に画像がある場合のみ）
        for i in range(2):
            if self._images[i]['pixmap'] is not None:
                # 必ず変更フラグをセット（確実な更新のため）
                self._images[i]['modified'] = True
        
        # ログレベルを状態変更に応じて調整
        if changed:
            log_print(INFO, f"ImageModel: 表示モードを変更: fit_to_window={fit_to_window}")
        else:
            log_print(DEBUG, f"ImageModel: 表示モード確認: fit_to_window={fit_to_window}")
        
        # 明示的にウィンドウ合わせモードの場合はズーム係数も1.0にリセット
        if fit_to_window:
            self._zoom_factor = 1.0
    
    def set_zoom_factor(self, zoom: float) -> None:
        """
        ズーム倍率を設定
        
        Args:
            zoom: ズーム倍率 (1.0が原寸大)
        """
        # 状態が変わった場合のみログ出力
        if self._zoom_factor != zoom:
            log_print(DEBUG, f"ImageModel: ズーム倍率を変更: {self._zoom_factor} -> {zoom}")
        
        self._zoom_factor = zoom
    
    def is_fit_to_window(self) -> bool:
        """
        ウィンドウに合わせるモードかどうかを取得
        
        Returns:
            bool: ウィンドウに合わせるモードならTrue
        """
        return self._fit_to_window_mode
    
    def get_zoom_factor(self) -> float:
        """
        現在のズーム倍率を取得
        
        Returns:
            float: ズーム倍率
        """
        return self._zoom_factor
    
    def reset_state(self) -> None:
        """
        モデルの状態をリセット
        """
        # 画像情報をクリア
        self.clear_image(0)
        self.clear_image(1)
        
        # 表示モードをデフォルトに戻す
        self._fit_to_window_mode = True
        self._zoom_factor = 1.0
        
        log_print(DEBUG, "ImageModel: 状態をリセットしました")
        
    # 以下、window.pyから移譲する表示モード関連のメソッド
    def is_dual_view(self) -> bool:
        """
        デュアルビューモードかどうかを取得
        
        Returns:
            bool: デュアルビューモードならTrue
        """
        return self._dual_view
    
    def get_browser_pages(self) -> int:
        """
        ブラウザ表示ページ数を取得
        
        Returns:
            int: ブラウザ表示ページ数（1または2）
        """
        return self._browser_pages
    
    def is_browser_shift(self) -> bool:
        """
        ブラウザシフトモードが有効かどうかを取得
        
        Returns:
            bool: シフトモードが有効ならTrue
        """
        return self._browser_shift
    
    def is_right_to_left(self) -> bool:
        """
        右から左への表示かどうかを取得
        
        Returns:
            bool: 右から左への表示ならTrue
        """
        return self._right_to_left
    
    def set_view_mode(self, mode: str) -> bool:
        """
        表示モードを設定
        
        Args:
            mode: 表示モード
                - "single": シングルモード
                - "dual_rl": デュアルモード（右左）
                - "dual_lr": デュアルモード（左右）
                - "dual_rl_shift": デュアルモード（右左シフト）
                - "dual_lr_shift": デュアルモード（左右シフト）
                
        Returns:
            bool: 設定に成功したかどうか
        """
        # 古い設定を保存
        old_dual_view = self._dual_view
        old_right_to_left = self._right_to_left
        old_browser_shift = self._browser_shift
        
        # モードに応じて設定を変更
        if mode == "single":
            # シングルモード
            self._dual_view = False
            self._browser_pages = 1
            self._browser_shift = False
            self._right_to_left = False
        elif mode == "dual_rl":
            # デュアルモード（右左）
            self._dual_view = True
            self._browser_pages = 2
            self._browser_shift = False
            self._right_to_left = True
        elif mode == "dual_lr":
            # デュアルモード（左右）
            self._dual_view = True
            self._browser_pages = 2
            self._browser_shift = False
            self._right_to_left = False
        elif mode == "dual_rl_shift":
            # デュアルモード（右左シフト）
            self._dual_view = True
            self._browser_pages = 2
            self._browser_shift = True
            self._right_to_left = True
        elif mode == "dual_lr_shift":
            # デュアルモード（左右シフト）
            self._dual_view = True
            self._browser_pages = 2
            self._browser_shift = True
            self._right_to_left = False
        else:
            # 不明なモードの場合
            log_print(ERROR, f"不明な表示モード: {mode}")
            return False
        
        log_print(DEBUG, f"ImageModel: 表示モード変更: {mode}, dual_view={self._dual_view}, right_to_left={self._right_to_left}, shift={self._browser_shift}")
        
        # 重要な変更があったかどうかを返す
        return (old_dual_view != self._dual_view or
                old_right_to_left != self._right_to_left or
                old_browser_shift != self._browser_shift)
    
    def get_current_view_mode(self) -> str:
        """
        現在の表示モードを文字列で取得
        
        Returns:
            str: 現在の表示モード名
        """
        if not self._dual_view:
            return "single"
        else:
            if self._right_to_left:
                if self._browser_shift:
                    return "dual_rl_shift"
                else:
                    return "dual_rl"
            else:
                if self._browser_shift:
                    return "dual_lr_shift"
                else:
                    return "dual_lr"
