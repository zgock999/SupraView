"""
画像表示処理ハンドラ

画像の表示と調整に関する処理を担当するクラス
"""

import os
from typing import Optional, Dict, List, Tuple, Any
from PySide6.QtWidgets import QScrollArea, QLabel, QSizePolicy, QFrame
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QResizeEvent
from logutils import log_print, INFO, WARNING, ERROR, DEBUG


class ImageScrollArea(QScrollArea):
    """画像表示用スクロールエリア"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignCenter)
        
        # 画像ラベルの作成
        self.image_label = QLabel("画像が読み込まれていません")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # スクロールエリアにラベルを設定
        self.setWidget(self.image_label)
        
        # キーボードフォーカスを有効化
        self.setFocusPolicy(Qt.StrongFocus)
        self.image_label.setFocusPolicy(Qt.StrongFocus)
        
        # 画像関連のプロパティ
        self._current_pixmap = None
        self._zoom_factor = 1.0
        self._fit_to_window = False
        self._is_right_side = False  # 右側表示かどうかのフラグ
        self._is_dual_mode = False   # デュアルモードかどうかのフラグ
    
    def reset_state(self):
        """内部状態をリセット"""
        self._current_pixmap = None
        self._zoom_factor = 1.0
        self._fit_to_window = False
        self.image_label.setText("画像が読み込まれていません")
        self.image_label.setPixmap(QPixmap())
        self.image_label.setAlignment(Qt.AlignCenter)
        log_print(DEBUG, "ImageScrollArea: 状態をリセットしました")
    
    def set_side(self, is_right: bool, is_dual: bool):
        """表示位置を設定"""
        self._is_right_side = is_right
        self._is_dual_mode = is_dual
        # 表示更新
        if self._current_pixmap:
            self._adjust_image_size()
    
    def set_pixmap(self, pixmap: QPixmap):
        """画像を設定"""
        self._current_pixmap = pixmap
        self._adjust_image_size()
    
    def _adjust_image_size(self):
        """画像サイズをウィンドウに合わせて調整する"""
        if not self._current_pixmap:
            return
        
        # スクロールエリアのサイズを取得
        viewport_size = self.viewport().size()
        
        # 原画像のサイズを取得
        img_size = self._current_pixmap.size()
        
        # ウィンドウに合わせるモードの場合
        if self._fit_to_window:
            # スケーリングされた画像を作成
            scaled_pixmap = self._current_pixmap.scaled(
                viewport_size.width(), viewport_size.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # デュアルモードの場合、左右の画像をそれぞれの側に寄せる
            if self._is_dual_mode:
                # スケーリング後のサイズを取得
                scaled_width = scaled_pixmap.width()
                scaled_height = scaled_pixmap.height()
                
                # 両方の画像がつながるように寄せる
                # 右から左モードと左から右モードで扱いを反転
                # まず親ウィジェットからルートウィンドウまで遡って_right_to_leftを探す
                parent_has_rtl = False
                parent_widget = self.parent()
                while parent_widget:
                    if hasattr(parent_widget, '_right_to_left'):
                        parent_has_rtl = parent_widget._right_to_left
                        break
                    parent_widget = parent_widget.parent()
                
                # デバッグログを追加
                log_print(DEBUG, f"親ウィジェットRTLモード: {parent_has_rtl}, 自分の位置: right={self._is_right_side}, dual={self._is_dual_mode}")
                
                # 右から左モードの場合、左右を反転
                if parent_has_rtl:
                    # 右から左モード: 左側の画像は左寄せ、右側の画像は右寄せ
                    if self._is_right_side:
                        # 右側の画像は右寄せ
                        self.image_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        log_print(DEBUG, f"RTLモード: 右側画像を右寄せで表示: {scaled_width}x{scaled_height}")
                    else:
                        # 左側の画像は左寄せ
                        self.image_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        log_print(DEBUG, f"RTLモード: 左側画像を左寄せで表示: {scaled_width}x{scaled_height}")
                else:
                    # 左から右モード: 左側の画像は右寄せ、右側の画像は左寄せ
                    if self._is_right_side:
                        # 右側の画像は左寄せ
                        self.image_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        log_print(DEBUG, f"LTRモード: 右側画像を左寄せで表示: {scaled_width}x{scaled_height}")
                    else:
                        # 左側の画像は右寄せ
                        self.image_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        log_print(DEBUG, f"LTRモード: 左側画像を右寄せで表示: {scaled_width}x{scaled_height}")
            else:
                # 単一画面モードの場合はセンター配置
                self.image_label.setAlignment(Qt.AlignCenter)
            
            # スケーリングされた画像を設定
            self.image_label.setPixmap(scaled_pixmap)
            return
        
        # 通常モード（ズーム係数に基づく）
        # 表示サイズを計算（ズーム係数を適用）
        scaled_width = int(img_size.width() * self._zoom_factor)
        scaled_height = int(img_size.height() * self._zoom_factor)
        
        # スケーリングされた画像を作成
        scaled_pixmap = self._current_pixmap.scaled(
            scaled_width, scaled_height, 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        
        # デュアルモードの場合、左右の画像をそれぞれの側に寄せる
        if self._is_dual_mode:
            # 両方の画像がつながるように寄せる
            # 右から左モードと左から右モードで扱いを反転
            # 親ウィジェットを遡って_right_to_leftを探す
            parent_has_rtl = False
            parent_widget = self.parent()
            while parent_widget:
                if hasattr(parent_widget, '_right_to_left'):
                    parent_has_rtl = parent_widget._right_to_left
                    break
                parent_widget = parent_widget.parent()
            
            # 右から左モードの場合、左右を反転
            if parent_has_rtl:
                # 右から左モード: 左側の画像は左寄せ、右側の画像は右寄せ
                if self._is_right_side:
                    # 右側の画像は右寄せ
                    self.image_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    # 左側の画像は左寄せ
                    self.image_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                # 左から右モード: 左側の画像は右寄せ、右側の画像は左寄せ
                if self._is_right_side:
                    # 右側の画像は左寄せ
                    self.image_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                else:
                    # 左側の画像は右寄せ
                    self.image_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            # 単一画面モードの場合はセンター配置
            self.image_label.setAlignment(Qt.AlignCenter)
        
        # ビューポートのサイズに収まるかどうかを確認
        if scaled_width <= viewport_size.width() and scaled_height <= viewport_size.height():
            # ビューポート内に収まる場合は、そのまま設定
            self.image_label.setPixmap(scaled_pixmap)
        else:
            # ビューポートより大きい場合は、ビューポートに合わせてサイズを調整
            viewport_scaled_pixmap = self._current_pixmap.scaled(
                viewport_size.width(), viewport_size.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(viewport_scaled_pixmap)
    
    def set_zoom(self, factor: float):
        """ズーム係数を設定（原寸大表示とウィンドウに合わせる機能用に維持）"""
        self._zoom_factor = factor
        self._fit_to_window = False  # 通常のズームモードに戻す
        self._adjust_image_size()
    
    def set_fit_to_window(self, enabled: bool):
        """ウィンドウに合わせるモードを設定"""
        self._fit_to_window = enabled
        self._adjust_image_size()
    
    def resizeEvent(self, event: QResizeEvent):
        """リサイズイベント時に画像サイズを調整"""
        super().resizeEvent(event)
        self._adjust_image_size()
    
    def keyPressEvent(self, event):
        """キーボードイベントを親ウィジェットに転送"""
        # 一旦デバッグ出力
        log_print(DEBUG, f"ImageScrollArea キー入力: {event.key()}")
        # 親ウィジェットを取得して、そちらにイベントを送信
        parent = self.parent()
        while parent and not hasattr(parent, 'keyPressEvent'):
            parent = parent.parent()
        
        if parent:
            # 親ウィジェットのkeyPressEventメソッドを直接呼び出す
            parent.keyPressEvent(event)
        else:
            # 親が見つからない場合は基底クラスの処理を呼び出す
            super().keyPressEvent(event)


class DisplayHandler:
    """画像表示処理を担当するハンドラクラス"""
    
    def __init__(self, parent=None):
        """
        画像表示ハンドラの初期化
        
        Args:
            parent: 親ウィジェット
        """
        self.parent = parent
        self._image_areas = []
        self._zoom_factor = 1.0
        
        # 画像データを保持する変数
        self._current_image_paths = ["", ""]
        self._current_image_data = [None, None]
        self._original_pixmaps = [None, None]
        self._numpy_images = [None, None]
        self._image_infos = [{}, {}]
        
        # 表示モード（True: ウィンドウに合わせる, False: 原寸大）
        self._fit_to_window_mode = False
    
    def reset_state(self):
        """内部状態をリセット"""
        # 表示モードと拡大率は維持したまま、画像データのみリセット
        self._current_image_paths = ["", ""]
        self._current_image_data = [None, None]
        self._original_pixmaps = [None, None]
        self._numpy_images = [None, None]
        self._image_infos = [{}, {}]
        
        # 各画像エリアもリセット
        for area in self._image_areas:
            if area:
                area.reset_state()
                # 表示モードと拡大率を再設定
                area._fit_to_window = self._fit_to_window_mode
                area._zoom_factor = self._zoom_factor
        
        log_print(DEBUG, f"DisplayHandler: 状態をリセットしました (fit_to_window={self._fit_to_window_mode}, zoom={self._zoom_factor})")
    
    def setup_image_areas(self, image_areas: List[ImageScrollArea]):
        """画像表示エリアをセットアップ"""
        # 画像エリアが変更されたら内部状態をリセット
        if self._image_areas != image_areas:
            # 現在の拡大率と表示モードを保存
            saved_zoom = self._zoom_factor
            saved_fit_mode = self._fit_to_window_mode
            
            # 現在の画像エリアを保存
            old_areas = self._image_areas
            
            # 新しい画像エリアを設定
            self._image_areas = image_areas

            # 現在の画像データを保存
            saved_image_data = []
            saved_paths = []
            
            # 画像データがあれば保存
            for i in range(2):
                if i < len(old_areas) and old_areas[i] and old_areas[i]._current_pixmap:
                    saved_image_data.append((i, old_areas[i]._current_pixmap))
                    if i < len(self._current_image_paths):
                        saved_paths.append((i, self._current_image_paths[i]))
            
            # 状態をリセットする前に画像データを保存
            old_image_data = self._current_image_data.copy()
            old_pixmaps = self._original_pixmaps.copy()
            old_numpy_images = self._numpy_images.copy()
            old_image_infos = self._image_infos.copy()
            
            # 新しい画像エリアに切り替える前に状態をリセット
            self.reset_state()
            
            # 保存した拡大率と表示モードを復元
            self._zoom_factor = saved_zoom
            self._fit_to_window_mode = saved_fit_mode
            
            # デュアルモードの場合、左右の画像エリアに適切な配置情報を設定
            if len(image_areas) >= 2 and image_areas[1]:
                # デュアルモード
                is_dual = True
                image_areas[0].set_side(is_right=False, is_dual=is_dual)  # 左側
                image_areas[1].set_side(is_right=True, is_dual=is_dual)   # 右側
                log_print(DEBUG, f"DisplayHandler: デュアルモードでセットアップしました (zoom={self._zoom_factor}, fit={self._fit_to_window_mode})")
            elif len(image_areas) >= 1 and image_areas[0]:
                # シングルモード
                image_areas[0].set_side(is_right=False, is_dual=False)  # 単一画面
                log_print(DEBUG, f"DisplayHandler: シングルモードでセットアップしました (zoom={self._zoom_factor}, fit={self._fit_to_window_mode})")
            
            # 各画像エリアに表示モードと拡大率を再設定
            for area in self._image_areas:
                if area:
                    area._fit_to_window = self._fit_to_window_mode
                    area._zoom_factor = self._zoom_factor
            
            # 画像データがあれば復元
            for idx, pixmap in saved_image_data:
                if idx < len(self._image_areas) and self._image_areas[idx]:
                    # パスと関連データも復元
                    path = ""
                    for i, p in saved_paths:
                        if i == idx:
                            path = p
                            break
                    
                    # 画像データを復元
                    if idx < len(old_image_data):
                        self._current_image_data[idx] = old_image_data[idx]
                    if idx < len(old_pixmaps):
                        self._original_pixmaps[idx] = old_pixmaps[idx]
                    if idx < len(old_numpy_images):
                        self._numpy_images[idx] = old_numpy_images[idx]
                    if idx < len(old_image_infos):
                        self._image_infos[idx] = old_image_infos[idx]
                    
                    # パスを復元
                    if path:
                        self._current_image_paths[idx] = path
                    
                    # ピクセルマップを設定
                    if old_pixmaps[idx]:
                        self._image_areas[idx].set_pixmap(old_pixmaps[idx])
                        self._image_areas[idx].set_fit_to_window(self._fit_to_window_mode)
                        log_print(DEBUG, f"画像エリア {idx} に画像データを復元しました")
    
    def set_image(self, pixmap: QPixmap, data: bytes, numpy_array: Any, info: Dict, path: str, index: int = 0):
        """
        画像情報をセット
        
        Args:
            pixmap: 表示する画像のQPixmap
            data: 画像の生データ
            numpy_array: NumPyで変換した画像データ
            info: 画像の情報辞書
            path: 画像のパス
            index: 画像を表示するインデックス（0: 左/単一, 1: 右）
        """
        # 引数チェック
        if index not in [0, 1] or index >= len(self._image_areas) or not self._image_areas[index]:
            log_print(WARNING, f"無効なインデックス: {index} または画像エリアがありません")
            return
        
        # 画像情報を保存
        self._current_image_paths[index] = path
        self._current_image_data[index] = data
        self._original_pixmaps[index] = pixmap
        self._numpy_images[index] = numpy_array
        self._image_infos[index] = info
        
        # 画像をスクロールエリアに設定
        self._image_areas[index].set_pixmap(pixmap)
        self._image_areas[index].set_fit_to_window(self._fit_to_window_mode)
        self._image_areas[index]._zoom_factor = self._zoom_factor
        
        # デュアルモードか確認して設定を更新
        is_dual = len(self._image_areas) >= 2 and self._image_areas[1] is not None
        self._image_areas[index].set_side(is_right=(index==1), is_dual=is_dual)
        
        log_print(DEBUG, f"画像を設定: index={index}, path={path}, fit_to_window={self._fit_to_window_mode}, zoom={self._zoom_factor}, is_dual={is_dual}")
    
    def clear_image(self, index: int):
        """指定インデックスの画像をクリア"""
        if index not in [0, 1] or index >= len(self._image_areas) or not self._image_areas[index]:
            return
        
        log_print(DEBUG, f"画像をクリア: インデックス {index}")
        
        # 画像ラベルのテキストとピクマップをクリア
        self._image_areas[index].image_label.setText("画像が読み込まれていません")
        self._image_areas[index].image_label.setPixmap(QPixmap())
        
        # 保存されている画像データをクリア
        self._current_image_paths[index] = ""
        self._current_image_data[index] = None
        self._original_pixmaps[index] = None
        self._numpy_images[index] = None
        self._image_infos[index] = {}
        
        # 画像エリア自体の内部状態もクリア
        self._image_areas[index]._current_pixmap = None
        
        # 表示モードと拡大率は維持
        self._image_areas[index]._fit_to_window = self._fit_to_window_mode
        self._image_areas[index]._zoom_factor = self._zoom_factor
    
    def fit_to_window(self):
        """画像をウィンドウに合わせて表示"""
        self._zoom_factor = 1.0
        self._fit_to_window_mode = True
        
        # デュアルモードかチェック
        is_dual = len(self._image_areas) >= 2 and self._image_areas[1] is not None
        
        # 各画像エリアに設定を反映
        for i, area in enumerate(self._image_areas):
            if area:
                area.set_fit_to_window(True)
                area.set_side(is_right=(i==1), is_dual=is_dual)
                
        log_print(DEBUG, f"ウィンドウに合わせるモードを設定: fit={self._fit_to_window_mode}, zoom={self._zoom_factor}")
        return True
    
    def show_original_size(self):
        """画像を原寸大で表示"""
        self._zoom_factor = 1.0
        self._fit_to_window_mode = False
        
        # デュアルモードかチェック
        is_dual = len(self._image_areas) >= 2 and self._image_areas[1] is not None
        
        # 各画像エリアに設定を反映
        for i, area in enumerate(self._image_areas):
            if area:
                area.set_fit_to_window(False)
                area.set_zoom(self._zoom_factor)
                area.set_side(is_right=(i==1), is_dual=is_dual)
                
        log_print(DEBUG, f"原寸大表示モードを設定: fit={self._fit_to_window_mode}, zoom={self._zoom_factor}")
        return True
    
    def is_fit_to_window_mode(self) -> bool:
        """
        現在の表示モードがウィンドウに合わせるモードかどうかを返す
        
        Returns:
            True: ウィンドウに合わせるモードの場合
            False: 原寸大表示モードの場合
        """
        return self._fit_to_window_mode
    
    def get_status_info(self) -> str:
        """
        ステータスバーに表示する画像情報テキストを生成
        
        Returns:
            表示用ステータステキスト
        """
        try:
            # シングルビューまたはデュアルビューの1画面目の情報
            status_msg = ""
            
            if self._original_pixmaps[0]:
                filename = os.path.basename(self._current_image_paths[0]) if self._current_image_paths[0] else "画像"
                width = self._original_pixmaps[0].width()
                height = self._original_pixmaps[0].height()
                size_kb = len(self._current_image_data[0]) / 1024 if self._current_image_data[0] else 0
                
                # NumPy情報があれば追加
                if self._numpy_images[0] is not None:
                    channels = 1 if len(self._numpy_images[0].shape) == 2 else self._numpy_images[0].shape[2]
                    status_msg = f"{filename} - {width}x{height} - {channels}チャンネル ({size_kb:.1f} KB)"
                else:
                    status_msg = f"{filename} - {width}x{height} ({size_kb:.1f} KB)"
            
            # デュアルビューの2画面目の情報
            if len(self._image_areas) > 1 and self._original_pixmaps[1]:
                if status_msg:
                    status_msg += " | "
                
                filename = os.path.basename(self._current_image_paths[1]) if self._current_image_paths[1] else "画像"
                width = self._original_pixmaps[1].width()
                height = self._original_pixmaps[1].height()
                size_kb = len(self._current_image_data[1]) / 1024 if self._current_image_data[1] else 0
                
                if self._numpy_images[1] is not None:
                    channels = 1 if len(self._numpy_images[1].shape) == 2 else self._numpy_images[1].shape[2]
                    status_msg += f"{filename} - {width}x{height} - {channels}チャンネル ({size_kb:.1f} KB)"
                else:
                    status_msg += f"{filename} - {width}x{height} ({size_kb:.1f} KB)"
            
            return status_msg
        except Exception as e:
            log_print(ERROR, f"ステータス情報の生成に失敗しました: {e}")
            return ""
    
    def get_image_info(self, index: int = 0) -> Dict:
        """
        画像情報を取得
        
        Args:
            index: 取得する画像のインデックス
            
        Returns:
            画像情報辞書
        """
        if 0 <= index < len(self._image_infos):
            return self._image_infos[index]
        return {}
    
    def has_image(self, index: int = 0) -> bool:
        """
        指定インデックスに画像があるかを確認
        
        Args:
            index: 確認する画像のインデックス
            
        Returns:
             画像が存在する場合はTrue
        """
        return bool(self._original_pixmaps[index]) if 0 <= index < len(self._original_pixmaps) else False
    
    def get_current_image_filename(self, index: int = 0) -> str:
        """
        現在表示中の画像のファイル名を取得
        
        Args:
            index: 取得する画像のインデックス
            
        Returns:
            ファイル名（パスなし）
        """
        if 0 <= index < len(self._current_image_paths) and self._current_image_paths[index]:
            return os.path.basename(self._current_image_paths[index])
        return ""
