"""
画像モデルモジュール

プレビューウィンドウ内の画像情報を管理する集中型のモデルクラス
"""

import os
import sys
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
from PySide6.QtGui import QImage
import cv2

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print,log_trace, INFO, WARNING, ERROR, DEBUG, CRITICAL

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
                'modified': False,   # 画像が修正されたかどうか
                'sr_array': None,    # 超解像処理後のNumPy配列
                'sr_request': None,  # 超解像処理リクエストのGUID
                'display_update_needed': False,  # 表示の更新が必要かどうか
                'error': None        # エラー情報
            },
            {
                'pixmap': None,
                'data': None,
                'numpy_array': None,
                'info': {},
                'path': "",
                'modified': False,
                'sr_array': None,    # 超解像処理後のNumPy配列
                'sr_request': None,  # 超解像処理リクエストのGUID
                'display_update_needed': False  # 表示の更新が必要かどうか
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
        
        # 書き込み時はインデックスの反転を行わない
        actual_index = index
        
        # 画像設定時にエラー情報を明示的にクリア
        self._images[actual_index]['error'] = None
        
        self._images[actual_index]['pixmap'] = pixmap
        self._images[actual_index]['data'] = data
        self._images[actual_index]['numpy_array'] = numpy_array
        self._images[actual_index]['info'] = info or {}
        self._images[actual_index]['path'] = path
        self._images[actual_index]['modified'] = True  # 画像が変更されたことを示すフラグを立てる
        self._images[actual_index]['display_update_needed'] = True  # 表示更新が必要であることを示すフラグを立てる
        
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
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        self._images[actual_index]['pixmap'] = None
        self._images[actual_index]['data'] = None
        self._images[actual_index]['numpy_array'] = None
        self._images[actual_index]['info'] = {}
        self._images[actual_index]['path'] = ""
        self._images[actual_index]['modified'] = False
        self._images[actual_index]['sr_array'] = None
        self._images[actual_index]['sr_request'] = None
        self._images[actual_index]['display_update_needed'] = False  # 表示更新フラグもクリア
        self._images[actual_index]['error'] = None  # エラー情報もクリア
        
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
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        img = self._images[actual_index]
        return img['pixmap'], img['data'], img['numpy_array'], img['info'], img['path']
    
    def get_pixmap(self, index: int) -> Optional[QPixmap]:
        """
        指定インデックスの画像ピクスマップを取得
        
        Args:
            index: 取得する画像インデックス
            
        Returns:
            QPixmap: 画像のピクスマップ (または None)
        """
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
        
        # 反転後のインデックスが有効かチェック
        if actual_index not in [0, 1] or not self._images[actual_index]['pixmap']:
            return None
        
        return self._images[actual_index]['pixmap']
    
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
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
        
        return self._images[actual_index]['path']
    
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
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        return self._images[actual_index]['info']
    
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
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
        
        return self._images[actual_index]['pixmap'] is not None
    
    def get_status_info(self) -> str:
        """
        ステータスバーに表示する画像情報テキストを生成
        
        Returns:
            str: 表示用ステータステキスト
        """
        try:
            # 情報を保持するための配列
            status_info = []
            directory_info = None
            
            # 各画像インデックスに対して情報を取得
            for index in [0, 1]:
                # デュアルモードかつ右左表示の場合は、インデックスを反転させる
                actual_index = index
                if self._dual_view and self._right_to_left:
                    actual_index = 1 - index  # 0→1、1→0に反転
                    
                # エラーがある場合はエラー情報を表示
                error_info = self._images[actual_index].get('error')
                if error_info:
                    error_message = error_info.get('message', "エラー")
                    path = error_info.get('path', "")
                    filename = os.path.basename(path) if path else "画像"
                    
                    # ディレクトリ情報を抽出
                    if not directory_info and path:
                        directory = os.path.dirname(path)
                        if directory:
                            directory_info = f"[{directory}]"
                    
                    # エラー情報を含むステータステキスト
                    info_text = f"{filename} - {error_message}"
                    status_info.append(info_text)
                    continue
                
                # 画像があればその情報を追加
                if self._images[actual_index]['pixmap'] is not None:
                    pixmap = self._images[actual_index]['pixmap']
                    data = self._images[actual_index]['data']
                    path = self._images[actual_index]['path']
                    
                    # ディレクトリ情報を抽出（最初の有効なパスから取得）
                    if not directory_info and path:
                        directory = os.path.dirname(path)
                        if directory:
                            directory_info = f"[{directory}]"
                    
                    filename = os.path.basename(path) if path else "画像"
                    width = pixmap.width()
                    height = pixmap.height()
                    size_kb = len(data) / 1024 if data else 0
                    
                    # NumPy情報があれば追加
                    numpy_array = self._images[actual_index]['numpy_array']
                    if numpy_array is not None:
                        channels = 1 if len(numpy_array.shape) == 2 else numpy_array.shape[2]
                        info_text = f"{filename} - {width}x{height} - {channels}チャンネル ({size_kb:.1f} KB)"
                    else:
                        info_text = f"{filename} - {width}x{height} ({size_kb:.1f} KB)"
                        
                    # 超解像処理されていたら表示
                    if self._images[actual_index].get('sr_array') is not None:
                        info_text += " [超解像]"
                        
                    status_info.append(info_text)
            
            # 情報がない場合
            if not status_info:
                return ""
            
            # デュアルモードかつ右左表示の場合は配列の順序を反転（表示も逆に）
            if self._dual_view and self._right_to_left and len(status_info) > 1:
                status_info = status_info[::-1]
            
            # ディレクトリ情報を最初に追加（ある場合）
            final_status = " | ".join(status_info)
            if directory_info:
                final_status = f"{directory_info} {final_status}"
                
            return final_status
            
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
    
    # 超解像処理関連のメソッドを追加
    def set_sr_array(self, index: int, sr_array: Any) -> bool:
        """
        超解像処理された画像をnp.ndarray形式で設定
        
        Args:
            index: 画像インデックス
            sr_array: 超解像処理された画像データ（NumPy配列）
            
        Returns:
            bool: 成功したかどうか
        """
        if index not in [0, 1]:
            return False
        
        if not isinstance(sr_array, np.ndarray):
            return False
        
        # 書き込み時はインデックスの反転を行わない
        actual_index = index
        
        try:
            # ※※※ 新規コード追加：エラーがある場合は超解像処理の保存を拒否 ※※※
            if self._images[actual_index].get('error') is not None:
                log_print(WARNING, f"インデックス {index} にエラーがあるため、超解像処理結果を保存できません")
                return False
              
            original_info = self._images[index].get('info', {}).copy()
            
            # サイズ情報を更新
            h, w = sr_array.shape[:2]
            channels = 1 if len(sr_array.shape) == 2 else sr_array.shape[2]
            
            # 元情報に加えて新しいサイズ情報を設定
            info = original_info.copy()
            info.update({
                'width': w,
                'height': h,
                'channels': channels,
                'superres': True,  # 超解像処理されたことを示すフラグ
            })

            if not sr_array.flags['C_CONTIGUOUS']:
                sr_array = np.ascontiguousarray(sr_array)
            
            if channels == 1:  # グレースケール
                img = QImage(sr_array.data, w, h, w, QImage.Format_Grayscale8)
                log_print(DEBUG, "Format_Grayscale8のQImageを作成しました")
            elif channels == 3:  # RGB
                img = QImage(sr_array.data, w, h, w * 3, QImage.Format_RGB888)
                log_print(DEBUG, "Format_RGB888のQImageを作成しました")
            elif channels == 4:  # RGBA
                img = QImage(sr_array.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
                log_print(DEBUG, "Format_RGBA8888のQImageを作成しました")
            else:
                return False
            log_print(DEBUG, f"超解像処理された画像を設定しました: index={index}, size={w}x{h}, channels={channels}")               
            # QImageからQPixmapを作成
            pixmap = QPixmap.fromImage(img)
            log_print(DEBUG, f"pixmapを作成しました")
            
            # 情報を更新
            self._images[actual_index]['pixmap'] = pixmap
            self._images[actual_index]['info'] = info
            self._images[actual_index]['sr_array'] = sr_array
            self._images[actual_index]['sr_request'] = None  # 超解像リクエストIDをクリア   
            self._images[actual_index]['modified'] = True  # 修正されたことを示すフラグ
            self._images[actual_index]['display_update_needed'] = True  # 表示更新が必要なフラグを立てる
            
            log_print(INFO, f"超解像処理された画像を設定しました: index={index}, size={w}x{h}")
            
            return True
            
        except Exception as e:
            log_print(ERROR, f"超解像画像の設定でエラー: {e}")
            import traceback
            log_print(ERROR, traceback.format_exc())
            return False
    
    def set_sr_request(self, index: int, request_id: str) -> bool:
        """
        超解像処理リクエストIDを設定
        
        Args:
            index: 画像インデックス
            request_id: 処理リクエストのGUID
            
        Returns:
            bool: 設定に成功したかどうか
        """
        if index not in [0, 1]:
            log_print(ERROR, f"ImageModel: 無効なインデックス {index}")
            return False
        
        # 書き込み時はインデックスの反転を行わない
        actual_index = index
        
        self._images[actual_index]['sr_request'] = request_id
        
        log_print(DEBUG, f"ImageModel: インデックス {index} に超解像リクエストID {request_id} を設定")
        return True
    
    def get_sr_array(self, index: int) -> Any:
        """
        超解像処理後の画像データを取得
        
        Args:
            index: 画像インデックス
            
        Returns:
            Any: 超解像処理後のNumPy配列（データがない場合はNone）
        """
        if index not in [0, 1]:
            log_print(ERROR, f"ImageModel: 無効なインデックス {index}")
            return None
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        return self._images[actual_index]['sr_array']
    
    def get_sr_request(self, index: int) -> Optional[str]:
        """
        超解像処理リクエストIDを取得
        
        Args:
            index: 画像インデックス
            
        Returns:
            str: 処理リクエストのGUID（リクエストがない場合はNone）
        """
        if index not in [0, 1]:
            log_print(ERROR, f"ImageModel: 無効なインデックス {index}")
            return None
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        return self._images[actual_index]['sr_request']
    
    def has_sr_array(self, index: int) -> bool:
        """
        超解像処理後の画像データが存在するか確認
        
        Args:
            index: 画像インデックス
            
        Returns:
            bool: 超解像データが存在すればTrue
        """
        if index not in [0, 1]:
            return False
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        return self._images[actual_index]['sr_array'] is not None
    
    def has_sr_request(self, index: int) -> bool:
        """
        超解像処理リクエストが存在するか確認
        
        Args:
            index: 画像インデックス
            
        Returns:
            bool: 超解像リクエストが存在すればTrue
        """
        if index not in [0, 1]:
            return False
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        return self._images[actual_index]['sr_request'] is not None
    
    # 表示更新関連の新しいメソッドを追加
    def is_display_update_needed(self, index: int) -> bool:
        """
        表示更新が必要かどうかを確認
        
        Args:
            index: 画像インデックス
            
        Returns:
            bool: 表示更新が必要な場合はTrue
        """
        if index not in [0, 1]:
            return False
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        return self._images[actual_index]['display_update_needed']

    def clear_display_update_flag(self, index: int) -> bool:
        """
        表示更新フラグをクリア
        
        Args:
            index: 画像インデックス
            
        Returns:
            bool: 操作が成功した場合はTrue
        """
        if index not in [0, 1]:
            return False
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        self._images[actual_index]['display_update_needed'] = False
        return True
    
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
    
    def set_error_info(self, index: int, error_info: Dict) -> bool:
        """
        指定インデックスにエラー情報を設定
        
        Args:
            index: 画像インデックス (0または1)
            error_info: エラー情報を含む辞書
            
        Returns:
            bool: 設定に成功したかどうか
        """
        if index not in [0, 1]:
            log_print(ERROR, f"ImageModel: 無効なインデックス {index}")
            return False
        
        # 書き込み時はインデックスの反転を行わない
        actual_index = index
        
        self._images[actual_index]['error'] = error_info
        self._images[actual_index]['display_update_needed'] = True  # 表示更新が必要
        
        log_print(DEBUG, f"ImageModel: インデックス {index} にエラー情報を設定しました")
        return True
    
    def get_error_info(self, index: int) -> Optional[Dict]:
        """
        指定インデックスのエラー情報を取得
        
        Args:
            index: 画像インデックス
            
        Returns:
            Dict: エラー情報の辞書（エラーがない場合はNone）
        """
        if index not in [0, 1]:
            return None
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        return self._images[actual_index].get('error')
    
    def has_error(self, index: int) -> bool:
        """
        指定インデックスにエラーがあるか確認
        
        Args:
            index: 画像インデックス
            
        Returns:
            bool: エラーがある場合はTrue
        """
        if index not in [0, 1]:
            return False
        
        # デュアルモードかつ右左表示の場合は、インデックスを反転させる
        actual_index = index
        if self._dual_view and self._right_to_left:
            actual_index = 1 - index  # 0は1に、1は0に反転
            log_print(DEBUG, f"RTLモードのため、インデックスを反転: {index} → {actual_index}")
        
        return self._images[actual_index].get('error') is not None
    
    def clear_error_info(self, index: int) -> bool:
        """
        指定インデックスのエラー情報をクリア
        
        Args:
            index: 画像インデックス
            
        Returns:
            bool: 操作に成功した場合はTrue
        """
        if index not in [0, 1]:
            log_print(ERROR, f"ImageModel: 無効なインデックス {index}")
            return False
        
        # エラー情報をクリアして表示更新フラグを設定
        self._images[index]['error'] = None
        self._images[index]['display_update_needed'] = True
        
        log_print(DEBUG, f"ImageModel: インデックス {index} のエラー情報をクリアしました")
        return True
    
    def __del__(self):
        """
        デコンストラクタ
        
        オブジェクト破棄時に実行中の超解像処理リクエストをキャンセルする
        """
        try:
            # 画像ハンドラを取得（親ウィンドウから参照）
            image_handler = None
            
            # 親ウィンドウを探す
            parent = None
            for obj in sys._current_frames().values():
                if hasattr(obj, 'f_locals'):
                    for key, val in obj.f_locals.items():
                        if hasattr(val, 'image_handler') and hasattr(val, 'image_model') and val.image_model == self:
                            parent = val
                            break
                    if parent:
                        break
            
            if parent and hasattr(parent, 'image_handler'):
                image_handler = parent.image_handler
                log_print(DEBUG, "ImageModel: 親ウィンドウからimage_handlerを取得しました")
            
            # 処理中のリクエストがある場合はキャンセル
            for index in [0, 1]:
                if self._images[index]['sr_request'] is not None:
                    request_id = self._images[index]['sr_request']
                    log_print(INFO, f"ImageModel: インデックス {index} の超解像リクエスト {request_id} をキャンセルします")
                    
                    # image_handlerがあればキャンセル処理を委譲
                    if image_handler and hasattr(image_handler, 'cancel_superres_request'):
                        image_handler.cancel_superres_request(index)
                    else:
                        # sr_managerを直接探して処理
                        sr_manager = None
                        if parent and hasattr(parent, 'sr_manager'):
                            sr_manager = parent.sr_manager
                        elif hasattr(sys.modules.get('__main__', None), 'sr_manager'):
                            sr_manager = sys.modules['__main__'].sr_manager
                        
                        if sr_manager and hasattr(sr_manager, 'cancel_superres'):
                            sr_manager.cancel_superres(request_id)
                            log_print(INFO, f"ImageModel: 超解像リクエスト {request_id} をキャンセルしました")
            
            log_print(DEBUG, "ImageModel: デコンストラクタが実行されました")
            
        except Exception as e:
            # デコンストラクタ内で例外が発生してもプログラムが終了しないようにキャッチ
            try:
                import traceback
                log_print(ERROR, f"ImageModel: デコンストラクタで例外が発生しました: {e}")
                log_print(DEBUG, traceback.format_exc())
            except:
                pass  # 最後の手段としてエラーも無視
