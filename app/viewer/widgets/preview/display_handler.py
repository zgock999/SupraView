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

# 画像モデルをインポート
from .image_model import ImageModel


class ImageScrollArea(QScrollArea):
    """画像表示用スクロールエリア"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignCenter)
        
        # 背景色を黒に設定
        self.setStyleSheet("background-color: black;")
        
        # 画像ラベルの作成
        self.image_label = QLabel("画像が読み込まれていません")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setStyleSheet("background-color: black;")
        
        # スクロールエリアにラベルを設定
        self.setWidget(self.image_label)
        
        # キーボードフォーカスを有効化
        self.setFocusPolicy(Qt.StrongFocus)
        self.image_label.setFocusPolicy(Qt.StrongFocus)
        
        # 画像関連のプロパティ
        self._current_pixmap = None
        self._zoom_factor = 1.0
        self._fit_to_window = True  # デフォルトはウィンドウに合わせる
        self._is_right_side = False  # 右側表示かどうかのフラグ
        self._is_dual_mode = False   # デュアルモードかどうかのフラグ
    
    def reset_state(self):
        """内部状態をリセット"""
        self._current_pixmap = None
        self._zoom_factor = 1.0
        self._fit_to_window = True  # デフォルトはウィンドウに合わせる
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
        # 画像設定時に必ず表示を調整
        self._adjust_image_size()
    
    def _adjust_image_size(self):
        """画像サイズをウィンドウに合わせて調整する"""
        if not self._current_pixmap:
            return
        
        # スクロールエリアのサイズを取得
        viewport_size = self.viewport().size()
        
        # 原画像のサイズを取得
        img_size = self._current_pixmap.size()
        
        # デバッグログを最適化（より分かりやすく）
        log_print(DEBUG, f"画像調整: fit_to_window={self._fit_to_window}, サイズ={img_size.width()}x{img_size.height()}, "
                         f"ビューポート={viewport_size.width()}x{viewport_size.height()}, "
                         f"zoom={self._zoom_factor}")
        
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
                
                # デバッグログを最適化
                log_print(DEBUG, f"デュアル配置: RTL={parent_has_rtl}, 位置=右側:{self._is_right_side}, "
                                 f"サイズ={scaled_width}x{scaled_height}")
                
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
        
        # 原寸大表示の場合は、ビューポートサイズに関係なく、そのまま表示
        # この修正により、原寸大表示が正しく機能するようになる
        self.image_label.setPixmap(scaled_pixmap)
        
        # 必要に応じてスクロールバーを調整するためにラベルのサイズを更新
        self.image_label.adjustSize()
    
    def set_zoom(self, factor: float):
        """ズーム係数を設定（原寸大表示とウィンドウに合わせる機能用に維持）"""
        self._zoom_factor = factor
        self._fit_to_window = False  # 通常のズームモードに戻す
        self._adjust_image_size()
    
    def set_fit_to_window(self, enabled: bool):
        """ウィンドウに合わせるモードを設定"""
        if self._fit_to_window != enabled:
            self._fit_to_window = enabled
            log_print(DEBUG, f"フィットモード変更: {enabled}")
            self._adjust_image_size()
    
    def resizeEvent(self, event: QResizeEvent):
        """リサイズイベント時に画像サイズを調整"""
        super().resizeEvent(event)
        # リサイズイベント時に画像サイズを再調整
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
    
    def __init__(self, parent=None, image_model=None):
        """
        画像表示ハンドラの初期化
        
        Args:
            parent: 親ウィジェット
            image_model: 画像情報を管理するモデル
        """
        self.parent = parent
        self._image_areas = []
        
        # 画像モデルの参照を保存
        self._image_model = image_model
        
        log_print(DEBUG, f"DisplayHandler: 初期化完了 (モデル参照: {self._image_model is not None}, fit={self.is_fit_to_window_mode()})")
    
    def reset_state(self):
        """内部状態をリセット"""
        # 各画像エリアもリセット
        for area in self._image_areas:
            if area:
                area.reset_state()
                # 表示モードと拡大率を再設定
                area._fit_to_window = self.is_fit_to_window_mode()
                area._zoom_factor = self.get_zoom_factor()
        
        log_print(DEBUG, f"DisplayHandler: 状態をリセットしました (fit_to_window={self.is_fit_to_window_mode()}, zoom={self.get_zoom_factor()})")
    
    def setup_image_areas(self, image_areas: List[ImageScrollArea]):
        """画像表示エリアをセットアップ"""
        # 画像エリアが変更されたら内部状態をリセット
        if self._image_areas != image_areas:
            # 現在の画像エリアを保存
            old_areas = self._image_areas
            
            # 新しい画像エリアを設定
            self._image_areas = image_areas
            
            # デュアルモードの場合、左右の画像エリアに適切な配置情報を設定
            if len(image_areas) >= 2 and image_areas[1]:
                # デュアルモード
                is_dual = True
                image_areas[0].set_side(is_right=False, is_dual=is_dual)  # 左側
                image_areas[1].set_side(is_right=True, is_dual=is_dual)   # 右側
                log_print(DEBUG, f"DisplayHandler: デュアルモードでセットアップしました (zoom={self.get_zoom_factor()}, fit={self.is_fit_to_window_mode()})")
            elif len(image_areas) >= 1 and image_areas[0]:
                # シングルモード
                image_areas[0].set_side(is_right=False, is_dual=False)  # 単一画面
                log_print(DEBUG, f"DisplayHandler: シングルモードでセットアップしました (zoom={self.get_zoom_factor()}, fit={self.is_fit_to_window_mode()})")
            
            # 各画像エリアに表示モードと拡大率を設定
            for area in self._image_areas:
                if area:
                    # 明示的に表示モードを設定
                    area._fit_to_window = self.is_fit_to_window_mode()
                    area._zoom_factor = self.get_zoom_factor()
                    # 明示的にset_fit_to_windowメソッドを呼び出し
                    if hasattr(area, 'set_fit_to_window'):
                        area.set_fit_to_window(self.is_fit_to_window_mode())
            
            # 画像モデルから画像データを取得して表示を更新
            self._update_image_areas_from_model()

    def _update_image_areas_from_model(self):
        """画像モデルから画像データを取得して表示エリアを更新"""
        if not self._image_model:
            return
        
        # 現在の表示設定を保存
        current_fit_mode = self.is_fit_to_window_mode()
        current_zoom = self.get_zoom_factor()
        
        log_print(DEBUG, f"画像エリアの表示モード更新: fit={current_fit_mode}, zoom={current_zoom}")
        
        # 画像エリア0（左/単一）の更新
        if len(self._image_areas) > 0 and self._image_areas[0]:
            # 表示モードの設定を明示的に更新
            self._image_areas[0]._fit_to_window = current_fit_mode
            self._image_areas[0]._zoom_factor = current_zoom
            
            pixmap = self._image_model.get_pixmap(0)
            if pixmap:
                # pixmapを設定
                self._image_areas[0]._current_pixmap = pixmap
                
                # 表示モードに応じて適切なメソッドを呼び出し
                if current_fit_mode:
                    self._image_areas[0].set_fit_to_window(True)
                else:
                    self._image_areas[0].set_zoom(current_zoom)
                
                log_print(DEBUG, f"画像エリア0に画像を設定: fit={current_fit_mode}")
                
        # 画像エリア1（右）の更新（デュアルモードの場合）
        if len(self._image_areas) > 1 and self._image_areas[1]:
            # 表示モードの設定を明示的に更新
            self._image_areas[1]._fit_to_window = current_fit_mode
            self._image_areas[1]._zoom_factor = current_zoom
            
            pixmap = self._image_model.get_pixmap(1)
            if pixmap:
                # pixmapを設定
                self._image_areas[1]._current_pixmap = pixmap
                
                # 表示モードに応じて適切なメソッドを呼び出し
                if current_fit_mode:
                    self._image_areas[1].set_fit_to_window(True)
                else:
                    self._image_areas[1].set_zoom(current_zoom)
                    
                log_print(DEBUG, f"画像エリア1に画像を設定: fit={current_fit_mode}")

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
        
        # 現在の表示モードを保存
        current_fit_mode = self.is_fit_to_window_mode()
        current_zoom = self.get_zoom_factor()
        
        # 画像モデルに画像情報を設定
        if self._image_model:
            self._image_model.set_image(index, pixmap, data, numpy_array, info, path)
            
            # モデルの表示モードを明示的に現在の設定に維持
            self._image_model.set_display_mode(current_fit_mode)
            self._image_model.set_zoom_factor(current_zoom)
        
        # デュアルモードか確認して設定を更新
        is_dual = len(self._image_areas) >= 2 and self._image_areas[1] is not None
        
        # まず画像エリアの内部状態を更新
        self._image_areas[index]._current_pixmap = pixmap
        self._image_areas[index]._fit_to_window = current_fit_mode
        self._image_areas[index]._zoom_factor = current_zoom
        self._image_areas[index].set_side(is_right=(index==1), is_dual=is_dual)
        
        # 次に画像を表示（現在の表示モードを維持）
        if current_fit_mode:
            # ウィンドウに合わせるモード
            self._image_areas[index].set_fit_to_window(True)
        else:
            # 原寸大表示モード
            self._image_areas[index].set_zoom(current_zoom)
            
        log_print(DEBUG, f"画像を設定: index={index}, path={path}, fit_to_window={current_fit_mode}, zoom={current_zoom}, is_dual={is_dual}")
    
    def clear_image(self, index: int):
        """指定インデックスの画像をクリア"""
        if index not in [0, 1] or index >= len(self._image_areas) or not self._image_areas[index]:
            return
        
        log_print(DEBUG, f"画像をクリア: インデックス {index}")
        
        # 画像モデルの情報をクリア
        if self._image_model:
            self._image_model.clear_image(index)
        
        # 画像ラベルのテキストとピクマップをクリア
        self._image_areas[index].image_label.setText("画像が読み込まれていません")
        self._image_areas[index].image_label.setPixmap(QPixmap())
        
        # 画像エリア自体の内部状態もクリア
        self._image_areas[index]._current_pixmap = None
        
        # 表示モードと拡大率は維持
        self._image_areas[index]._fit_to_window = self.is_fit_to_window_mode()
        self._image_areas[index]._zoom_factor = self.get_zoom_factor()
    
    def fit_to_window(self):
        """画像をウィンドウに合わせる"""
        # 以前の状態を保存して変更があった場合のみ処理する
        prev_mode = self.is_fit_to_window_mode()
        
        # 画像モデルに表示モードを設定
        if self._image_model:
            self._image_model.set_display_mode(True)
            self._image_model.set_zoom_factor(1.0)
        
        # デュアルモードかチェック
        is_dual = len(self._image_areas) >= 2 and self._image_areas[1] is not None
        
        # 状態変更のみ行い、実際の画像調整は一回だけにする
        areas_updated = False
        
        # 各画像エリアに設定を反映
        for i, area in enumerate(self._image_areas):
            if area:
                # 内部状態を直接設定
                area._fit_to_window = True
                area._zoom_factor = 1.0
                
                # 側面情報も設定（画像位置調整のため）
                area.set_side(is_right=(i==1), is_dual=is_dual)
                
                # pixmapがある場合のみ画像調整を実行
                if area._current_pixmap and not areas_updated:
                    # 最初の有効なエリアで一度だけ調整を実行
                    area.set_fit_to_window(True)
                    area._adjust_image_size()
                    areas_updated = True
                elif area._current_pixmap:
                    # 2つ目以降は内部状態だけ設定（_adjust_image_sizeを呼ばない）
                    area.set_fit_to_window(True)
                
        log_print(DEBUG, f"ウィンドウに合わせるモードを設定: fit={self.is_fit_to_window_mode()}, 状態変更={prev_mode != self.is_fit_to_window_mode()}")
        return True
    
    def show_original_size(self):
        """画像を原寸大で表示"""
        # 以前の状態を保存して変更があった場合のみ処理する
        prev_mode = self.is_fit_to_window_mode()
        
        # 画像モデルに表示モードを設定
        if self._image_model:
            self._image_model.set_display_mode(False)
            self._image_model.set_zoom_factor(1.0)  # 原寸大は倍率1.0
        
        # デュアルモードかチェック
        is_dual = len(self._image_areas) >= 2 and self._image_areas[1] is not None
        
        # 各画像エリアに設定を反映
        for i, area in enumerate(self._image_areas):
            if area:
                # 内部状態を直接設定
                area._fit_to_window = False
                area._zoom_factor = self.get_zoom_factor()
                
                # 側面情報も設定（画像位置調整のため）
                area.set_side(is_right=(i==1), is_dual=is_dual)
                
                # pixmapがある場合は必ず画像調整を実行（ここが問題）
                if area._current_pixmap:
                    area.set_fit_to_window(False)
                    area.set_zoom(self.get_zoom_factor())
                    area._adjust_image_size()  # 必ず明示的に画像調整を実行
                
        log_print(DEBUG, f"原寸大表示モードを設定: fit={self.is_fit_to_window_mode()}, 状態変更={prev_mode != self.is_fit_to_window_mode()}")
        return True
    
    def is_fit_to_window_mode(self) -> bool:
        """
        現在の表示モードがウィンドウに合わせるモードかどうかを返す
        
        Returns:
            True: ウィンドウに合わせるモードの場合
            False: 原寸大表示モードの場合
        """
        # 画像モデルから取得
        if self._image_model:
            return self._image_model.is_fit_to_window()
        return True  # モデルがない場合はデフォルト値
    
    def get_zoom_factor(self) -> float:
        """
        現在のズーム倍率を取得
        
        Returns:
            float: ズーム倍率
        """
        # 画像モデルから取得
        if self._image_model:
            return self._image_model.get_zoom_factor()
        return 1.0  # モデルがない場合はデフォルト値

    def get_status_info(self) -> str:
        """
        ステータスバーに表示する画像情報テキストを生成
        
        Returns:
            表示用ステータステキスト
        """
        # 画像モデルから取得
        if self._image_model:
            return self._image_model.get_status_info()
        return ""
    
    def get_image_info(self, index: int = 0) -> Dict:
        """
        画像情報を取得
        
        Args:
            index: 取得する画像のインデックス

        Returns:
            画像情報辞書
        """
        # 画像モデルから取得
        if self._image_model:
            return self._image_model.get_info(index)
        return {}
    
    def has_image(self, index: int = 0) -> bool:
        """
        指定インデックスに画像があるかを確認
        
        Args:
            index: 確認する画像のインデックス
            
        Returns:
             画像が存在する場合はTrue
        """
        # 画像モデルから取得
        if self._image_model:
            return self._image_model.has_image(index)
        return False
    
    def get_current_image_filename(self, index: int = 0) -> str:
        """
        現在表示中の画像のファイル名を取得
        
        Args:
            index: 取得する画像のインデックス
            
        Returns:
            ファイル名（パスなし）
        """
        # 画像モデルから取得
        if self._image_model and self._image_model.has_image(index):
            path = self._image_model.get_path(index)
            if path:
                return os.path.basename(path)
        return ""
    
    def set_view_mode(self, mode: str, parent_window):
        """
        表示モードを設定
        
        Args:
            mode: 表示モード
                - "single": シングルモード
                - "dual_rl": デュアルモード（右左）
                - "dual_lr": デュアルモード（左右）
                - "dual_rl_shift": デュアルモード（右左シフト）
                - "dual_lr_shift": デュアルモード（左右シフト）
            parent_window: 親ウィンドウへの参照（レイアウト再構築用）
        """
        # 画像モデルを確認
        if not self._image_model:
            log_print(ERROR, "画像モデルが設定されていません")
            return False
        
        # 現在のモードを保存
        old_dual_view = parent_window._dual_view if hasattr(parent_window, '_dual_view') else False
        
        # 画像モデルの現在の表示モードを取得（復元用に保存）
        fit_to_window_mode = self._image_model.is_fit_to_window()
        zoom_factor = self._image_model.get_zoom_factor()
        
        # 重要な設定変更があったかどうかを画像モデルのset_view_modeで確認
        layout_change_needed = self._image_model.set_view_mode(mode)
        
        # 画像モデルから新しい設定を取得
        new_dual_view = self._image_model.is_dual_view()
        browser_pages = self._image_model.get_browser_pages()
        browser_shift = self._image_model.is_browser_shift()
        right_to_left = self._image_model.is_right_to_left()
        
        log_print(DEBUG, f"表示モード変更: {mode}, dual_view={new_dual_view}, right_to_left={right_to_left}, shift={browser_shift}")
        
        # ブラウザの設定を更新
        if hasattr(parent_window, '_browser') and parent_window._browser:
            try:
                # ブラウザのプロパティを直接変更
                parent_window._browser._pages = browser_pages
                parent_window._browser._shift = browser_shift
                
                # 親ウィンドウの変数も同期
                parent_window._browser_pages = browser_pages
                parent_window._browser_shift = browser_shift
                parent_window._dual_view = new_dual_view
                parent_window._right_to_left = right_to_left
                
                log_print(INFO, f"ブラウザ表示モードを変更: mode={mode}, pages={browser_pages}, shift={browser_shift}, rtl={right_to_left}")
            except Exception as e:
                log_print(ERROR, f"ブラウザの更新に失敗しました: {e}")
        else:
            # ブラウザがなくても親ウィンドウの変数を同期
            parent_window._browser_pages = browser_pages
            parent_window._browser_shift = browser_shift
            parent_window._dual_view = new_dual_view
            parent_window._right_to_left = right_to_left
        
        # デュアルモードの切り替えが発生した場合、UIを再構築
        if old_dual_view != new_dual_view:
            # 画面を再構築する前に表示ハンドラの状態をリセット
            # 拡大率と表示モードを保存
            saved_fit_mode = self.is_fit_to_window_mode()
            saved_zoom = self.get_zoom_factor()
            
            self.reset_state()
            
            # 既存のレイアウトをクリア
            while parent_window.main_layout.count():
                item = parent_window.main_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            
            # 画像エリアを再作成
            parent_window.image_areas = []
            
            if new_dual_view:
                # デュアルビューの場合はスプリッターを使用
                from PySide6.QtWidgets import QSplitter
                parent_window.splitter = QSplitter(Qt.Horizontal)
                # マージンを0に設定して画像を隙間なく表示
                parent_window.splitter.setContentsMargins(0, 0, 0, 0)
                parent_window.splitter.setOpaqueResize(False)  # リサイズ中も滑らかに表示
                parent_window.splitter.setHandleWidth(1)  # ハンドルをほぼ見えなくする
                parent_window.main_layout.addWidget(parent_window.splitter)
                
                # 左右の画像エリアを作成
                for i in range(2):
                    scroll_area = ImageScrollArea()
                    scroll_area.setFocusPolicy(Qt.StrongFocus)  # キーボードフォーカスを有効化
                    from PySide6.QtWidgets import QFrame  # QFrameをインポート
                    scroll_area.setFrameShape(QFrame.NoFrame)  # フレームを非表示に設定
                    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    parent_window.image_areas.append(scroll_area)
                
                # 重要: 右から左モードの場合はウィジェットの順序を逆にして追加
                if right_to_left:
                    # 右側を第一画面として追加
                    parent_window.splitter.addWidget(parent_window.image_areas[1])  # 右側が先 (index=0)
                    parent_window.splitter.addWidget(parent_window.image_areas[0])  # 左側が後 (index=1)
                    log_print(DEBUG, "デュアルモード（右左）でスプリッター作成: 右側が第一画面")
                else:
                    # 左側を第一画面として追加
                    parent_window.splitter.addWidget(parent_window.image_areas[0])  # 左側が先 (index=0)
                    parent_window.splitter.addWidget(parent_window.image_areas[1])  # 右側が後 (index=1)
                    log_print(DEBUG, "デュアルモード（左右）でスプリッター作成: 左側が第一画面")
                
                # スプリッターの位置を50:50に設定
                parent_window.splitter.setSizes([500, 500])
                
                # マウストラッキングを設定
                parent_window.splitter.setMouseTracking(True)
                parent_window.image_areas[0].setMouseTracking(True)
                parent_window.image_areas[1].setMouseTracking(True)
            else:
                # シングルビューの場合は単純にスクロールエリアを追加
                scroll_area = ImageScrollArea()
                scroll_area.setFocusPolicy(Qt.StrongFocus)  # キーボードフォーカスを有効化
                parent_window.image_areas.append(scroll_area)
                parent_window.main_layout.addWidget(scroll_area)
                
                # 2画面用に配列を2要素にする（未使用でも統一的に扱えるように）
                parent_window.image_areas.append(None)
                
                # マウストラッキングを設定
                parent_window.image_areas[0].setMouseTracking(True)
            
            # 表示ハンドラに新しい画像エリアを設定
            self.setup_image_areas(parent_window.image_areas)
            
            # 画像ハンドラにも画像エリアを設定（重要）
            if hasattr(parent_window, 'image_handler'):
                parent_window.image_handler.setup_image_areas(parent_window.image_areas)
            
            # 保存した拡大率と表示モードを復元
            self._fit_to_window_mode = saved_fit_mode
            self._zoom_factor = saved_zoom
            
            # ナビゲーションバーの右左モードも更新
            if hasattr(parent_window, 'navigation_bar'):
                parent_window.navigation_bar.set_right_to_left_mode(right_to_left)
                log_print(DEBUG, f"ナビゲーションバーの右左モードを更新（レイアウト再構築時）: {right_to_left}")
            
            # 保存しておいた画像データを復元
            if hasattr(parent_window, '_browser') and parent_window._browser:
                # 明示的にブラウザを更新して現在の設定を反映
                try:
                    # ブラウザを再初期化
                    parent_window._browser._pages = browser_pages
                    parent_window._browser._shift = browser_shift
                    
                    # 画像を再読み込み
                    parent_window._update_images_from_browser()
                    
                    log_print(INFO, f"表示モード変更後に画像を再読み込み: {mode}")
                except Exception as e:
                    log_print(ERROR, f"画像の再読み込み中にエラーが発生しました: {e}")
        else:
            # デュアルモードの切り替えがない場合（右左切り替えやシフトモード切り替えのみ）
            # 右左モードが変更されたらナビゲーションバーの設定を更新
            if hasattr(parent_window, 'navigation_bar'):
                parent_window.navigation_bar.set_right_to_left_mode(right_to_left)
                log_print(DEBUG, f"ナビゲーションバーの右左モードを更新（モード変更時）: {right_to_left}")
            
            # ブラウザモードが変更された場合は画像を再読み込み
            if parent_window._browser and layout_change_needed:
                try:
                    # 画像を再読み込み
                    parent_window._update_images_from_browser()
                    log_print(INFO, f"ブラウザシフトモード変更後に画像を再読み込み: shift={browser_shift}")
                except Exception as e:
                    log_print(ERROR, f"画像の再読み込み中にエラーが発生しました: {e}")
        
        # コンテキストメニュー表示状態を更新
        if hasattr(parent_window, 'context_menu'):
            parent_window.context_menu.update_view_mode(mode)
            log_print(DEBUG, f"コンテキストメニューの表示モードを更新: {mode}")
        
        return True

    def refresh_display_mode(self, fit_to_window: bool = True):
        """
        現在の表示モードを再適用して表示を更新する
        
        Args:
            fit_to_window: ウィンドウに合わせるモードが有効かどうか
        """
        # 画像モデルに表示モードを設定
        if self._image_model:
            self._image_model.set_display_mode(fit_to_window)
        
        # デュアルモードか確認して設定を更新
        is_dual = len(self._image_areas) >= 2 and self._image_areas[1] is not None
        
        # 各画像エリアに設定を反映
        for i, area in enumerate(self._image_areas):
            if area and area._current_pixmap:
                # 内部状態を直接設定
                area._fit_to_window = fit_to_window
                
                # 側面情報も設定（画像位置調整のため）
                area.set_side(is_right=(i==1), is_dual=is_dual)
                
                # 表示モードに応じて画像を調整
                if fit_to_window:
                    area.set_fit_to_window(True)
                else:
                    area.set_zoom(self.get_zoom_factor())
                
                # 必ず明示的に画像調整を実行
                area._adjust_image_size()
        
        log_print(DEBUG, f"表示モードを更新: fit_to_window={fit_to_window}, zoom={self.get_zoom_factor()}")
