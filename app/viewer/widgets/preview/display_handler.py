"""
画像表示処理ハンドラ

画像の表示と調整に関する処理を担当するクラス
"""

import os
from typing import Optional, Dict, List, Tuple, Any
from PySide6.QtWidgets import QScrollArea, QLabel, QSizePolicy, QFrame
from PySide6.QtCore import Qt, QSize, QMetaObject, Signal, Slot, QObject
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
        self.image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")  # テキスト色を白に設定
        
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
        
        # スクロールバーのポリシーを設定 (常に表示)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 再調整中フラグを追加
        self._adjusting_size = False
        # 後続の調整要求を一時保存
        self._adjustment_pending = False

        # 画像更新中フラグを追加
        self._update_in_progress = False
    
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
        if pixmap is None:
            log_print(DEBUG, "設定するピクスマップがNoneです")
            self._current_pixmap = None
            self.image_label.setText("画像がありません")
            self.image_label.setPixmap(QPixmap())  # 空のピクスマップをクリア
            return
            
        if pixmap.isNull():
            log_print(WARNING, "設定するピクスマップが無効です")
            self._current_pixmap = None
            self.image_label.setText("無効な画像です")
            self.image_label.setPixmap(QPixmap())  # 空のピクスマップをクリア
            return
        
        # 有効なピクスマップを設定
        self._current_pixmap = pixmap
        
        # テキストを明示的にクリア
        self.image_label.setText("")
        
        log_print(DEBUG, f"ピクスマップを設定: {pixmap.width()}x{pixmap.height()}")
        
        # 画像設定時に必ず表示を調整
        self._adjust_image_size()
    
    def _adjust_image_size(self):
        """画像のサイズを現在の表示モードに合わせて調整"""
        try:
            # 画像更新中フラグをセット
            self._update_in_progress = True

            # 既に調整中の場合は後続処理としてマーク
            if self._adjusting_size:
                self._adjustment_pending = True
                log_print(DEBUG, "既に調整中のため後続処理としてマーク")
                return
            
            try:
                # 調整中フラグをセット
                self._adjusting_size = True
                self._adjustment_pending = False
                
                if not self._current_pixmap:
                    log_print(WARNING, "現在のピクスマップがNoneです")
                    # ピクスマップがない場合はテキストだけ設定して処理を終了
                    self.image_label.setText("画像が読み込まれていません")
                    self.image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
                    self.image_label.setAlignment(Qt.AlignCenter)
                    return
            
                # デュアルモードの状態を明示的にログに出力
                log_print(DEBUG, f"画像サイズ調整: {self._current_pixmap.width()}x{self._current_pixmap.height()}, dual_mode={self._is_dual_mode}, right_side={self._is_right_side}")     
            
                # 最新のpixmapを使用
                latest_pixmap = self._current_pixmap
          
                # ビューポートのサイズを取得
                viewport_size = self.viewport().size()
            
                # 画像のサイズを取得
                img_size = latest_pixmap.size()
            
                if self._fit_to_window:
                    # スクロールバーを一時的に無効化してちらつきを防止
                    old_h_policy = self.horizontalScrollBarPolicy()
                    old_v_policy = self.verticalScrollBarPolicy()
                    self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                    self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                
                    # スケーリングされた画像を作成 - 最新のpixmapを使用
                    scaled_pixmap = latest_pixmap.scaled(
                        viewport_size.width(), viewport_size.height(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                
                    # デュアルモードの場合、左右の画像をそれぞれの側に寄せる
                    if self._is_dual_mode:
                        # スケーリング後のサイズを取得
                        scaled_width = scaled_pixmap.width()
                        scaled_height = scaled_pixmap.height()
                    
                        # 必ず出力されるようにログレベルをINFOに上げる
                        log_print(INFO, f"デュアル配置: スケーリングサイズ={scaled_width}x{scaled_height}, dual={self._is_dual_mode}, right={self._is_right_side}")
                    
                        # 配置を設定: 左側の画像は右寄せ、右側の画像は左寄せ（隣り合う部分で接するように）
                        if self._is_right_side:
                            # 右側の画像は左寄せ
                            log_print(DEBUG, "右側の画像は左寄せ")
                            self.image_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        else:
                            # 左側の画像は右寄せ
                            log_print(DEBUG, "左側の画像は右寄せ")
                            self.image_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        # 単一画面モードの場合はセンター配置
                        log_print(DEBUG, "単一画面モード: センター配置")
                        self.image_label.setAlignment(Qt.AlignCenter)
                
                    # スケーリングされた画像を設定
                    self.image_label.setPixmap(scaled_pixmap)
                    log_print(DEBUG, f"スケーリングされた画像を設定: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
                
                    # スクロールエリアの内容を明示的に更新
               
                
                    # スクロールバーポリシーを元に戻す
                    self.setHorizontalScrollBarPolicy(old_h_policy)
                    self.setVerticalScrollBarPolicy(old_v_policy)
                    return
            
                # 通常モード（ズーム係数に基づく）
                # 表示サイズを計算（ズーム係数を適用）
                scaled_width = int(img_size.width() * self._zoom_factor)
                scaled_height = int(img_size.height() * self._zoom_factor)
            
                # スケーリングされた画像を作成 - 最新のpixmapを使用
                scaled_pixmap = latest_pixmap.scaled(
                    scaled_width, scaled_height, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
            
                # デュアルモードの場合、左右の画像をそれぞれの側に寄せる
                if self._is_dual_mode:
                    # 配置を設定: 左側の画像は右寄せ、右側の画像は左寄せ（隣り合う部分で接するように）
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
            
                # スクロールエリアの内容を明示的に更新
                self.image_label.resize(scaled_pixmap.size())
                self.image_label.adjustSize()
                log_print(DEBUG, f"原寸大表示: ラベルサイズ={self.image_label.size().width()}x{self.image_label.size().height()}")
                self.widget().update()
                self.update()
                log_print(DEBUG, f"原寸大表示: スクロールエリアサイズ={self.size().width()}x{self.size().height()}")
            
                # スクロールバーの位置を適切に調整
                if not self._fit_to_window:
                    # 原寸表示時にはスクロールバーの位置をリセット
                    self.horizontalScrollBar().setValue(0)
                    self.verticalScrollBar().setValue(0)
            finally:
                # 調整中フラグをクリア
                self._adjusting_size = False
                
                # 後続の調整要求があれば遅延実行
                if self._adjustment_pending:
                    log_print(DEBUG, "後続の調整要求を処理")
                    # 直接呼び出しではなく、イベントループでの実行をスケジュール
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(10, self._adjust_image_size)
        finally:
            # 処理完了後にフラグをクリア
            self._update_in_progress = False
    
    def set_zoom(self, factor: float):
        """ズーム係数を設定（原寸大表示とウィンドウに合わせる機能用に維持）"""
        self._zoom_factor = factor
        self._fit_to_window = False  # 通常のズームモードに戻す
        self._adjust_image_size()
    
    def set_fit_to_window(self, enabled: bool):
        """ウィンドウに合わせるモードを設定"""
        self._fit_to_window = enabled
        log_print(DEBUG, f"フィットモード変更: {enabled}")
        self._adjust_image_size()
    
    def resizeEvent(self, event: QResizeEvent):
        """リサイズイベント時に画像サイズを調整"""
        super().resizeEvent(event)
        
        # 画像更新中の場合はリサイズ処理をスキップ
        if self._update_in_progress:
            return
        
        # 画像サイズを調整
        if self._current_pixmap:
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


# スレッドセーフな通信を行うためのシグナルクラス
class UpdateSignals(QObject):
    """スレッド間通信のためのシグナルクラス"""
    
    # エラー表示用シグナル
    show_error = Signal(object, str, str)  # (area, error_message, filename)
    # 画像表示用シグナル
    show_image = Signal(object, object, bool, float, bool, bool)  # (area, pixmap, fit_to_window, zoom_factor, is_dual, is_right_side)


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
        
        # スレッド間通信用のシグナルオブジェクト
        self._signals = UpdateSignals()
        self._signals.show_error.connect(self._on_show_error)
        self._signals.show_image.connect(self._on_show_image)
        
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
            
            # デュアルモードの判定をモデルから取得
            is_dual = self._image_model.is_dual_view() if self._image_model else False
            
            # デバッグログを追加
            log_print(INFO, f"setup_image_areas: デュアルモード={is_dual}, 画像エリア数={len(image_areas)}")
            
            # デュアルモードなのに画像エリアが1つだけの場合、警告
            if is_dual and len(image_areas) < 2:
                log_print(WARNING, f"デュアルモードなのに画像エリアが不足: {len(image_areas)}")
                
            if is_dual and len(image_areas) >= 2 and image_areas[1] is None:
                log_print(WARNING, "デュアルモードなのに2つ目の画像エリアがNone")
                       
            # デュアルモードの場合、左右の画像エリアに適切な配置情報を設定
            if is_dual:
                # デュアルモード
                # 明示的に内部プロパティも設定
                image_areas[0]._is_dual_mode = True
                image_areas[0]._is_right_side = False
                image_areas[1]._is_dual_mode = True
                image_areas[1]._is_right_side = True
                
                # set_sideメソッドを呼び出し
                image_areas[0].set_side(is_right=False, is_dual=True)  # 左側
                image_areas[1].set_side(is_right=True, is_dual=True)   # 右側
                
                # 初期状態でスクロールバーを表示するための設定を強化
                for area in image_areas:
                    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    area.setWidgetResizable(True)
                
                log_print(DEBUG, f"DisplayHandler: デュアルモードでセットアップしました (zoom={self.get_zoom_factor()}, fit={self.is_fit_to_window_mode()})")
            elif len(image_areas) >= 1 and image_areas[0]:
                # シングルモード
                # 明示的に内部プロパティも設定
                image_areas[0]._is_dual_mode = False
                image_areas[0]._is_right_side = False
                
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
                
                    # スクロールバーの表示設定を強化
                    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    area.setWidgetResizable(True)
            
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
            
            # エラー情報をチェック
            error_info = self._image_model.get_error_info(0)
            if error_info:
                # エラー情報がある場合はエラーメッセージを表示
                error_message = error_info.get('message', "画像を読み込めませんでした")
                path = error_info.get('path', "")
                filename = os.path.basename(path) if path else ""
                
                # ファイル名を添えたエラーメッセージ
                display_message = f"{error_message}\n\n{filename}" if filename else error_message
                
                self._image_areas[0]._current_pixmap = None
                self._image_areas[0].image_label.setText(display_message)
                self._image_areas[0].image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
                self._image_areas[0].image_label.setAlignment(Qt.AlignCenter)
                self._image_areas[0].image_label.setPixmap(QPixmap())  # 空のピクスマップをクリア
                log_print(INFO, f"エラー情報を表示: {error_message} (ファイル: {filename})")
            else:
                # エラーがない場合のみ通常の画像表示処理を実行
                # 通常の画像表示処理
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
                else:
                    # ピクスマップがない場合はエラーメッセージを表示
                    self._image_areas[0]._current_pixmap = None
                    self._image_areas[0].image_label.setText("画像がありません")
                    self._image_areas[0].image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
                    self._image_areas[0].image_label.setPixmap(QPixmap())  # 空のピクスマップを明示的にセット
        
        # 画像エリア1（右）の更新（デュアルモードの場合）
        if len(self._image_areas) > 1 and self._image_areas[1] is not None:  # Noneチェックを明示的に追加
            # 表示モードの設定を明示的に更新
            self._image_areas[1]._fit_to_window = current_fit_mode
            self._image_areas[1]._zoom_factor = current_zoom
            
            # エラー情報をチェック
            error_info = self._image_model.get_error_info(1)
            if error_info:
                # エラー情報がある場合はエラーメッセージを表示
                error_message = error_info.get('message', "画像を読み込めませんでした")
                path = error_info.get('path', "")
                filename = os.path.basename(path) if path else ""
                
                # ファイル名を添えたエラーメッセージ
                display_message = f"{error_message}\n\n{filename}" if filename else error_message
                
                self._image_areas[1]._current_pixmap = None
                self._image_areas[1].image_label.setText(display_message)
                self._image_areas[1].image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
                self._image_areas[1].image_label.setAlignment(Qt.AlignCenter)
                self._image_areas[1].image_label.setPixmap(QPixmap())  # 空のピクスマップをクリア
                log_print(INFO, f"エラー情報を表示: {error_message} (ファイル: {filename})")
            else:
                # エラーがない場合のみ通常の画像表示処理を実行
                # 通常の画像表示処理
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
                else:
                    # ピクスマップがない場合はエラーメッセージを表示
                    self._image_areas[1]._current_pixmap = None
                    self._image_areas[1].image_label.setText("画像がありません")
                    self._image_areas[1].image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
                    self._image_areas[1].image_label.setPixmap(QPixmap())  # 空のピクスマップを明示的にセット

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
        
        # 画像が無効な場合のエラーメッセージ表示
        if pixmap is None or pixmap.isNull():
            error_msg = "画像を読み込めませんでした"
            if pixmap is None:
                log_print(WARNING, f"画像がNoneです: {path}")
            else:
                log_print(WARNING, f"無効な画像です: {path}")
            
            self._image_areas[index].image_label.setText(error_msg)
            self._image_areas[index].image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
            self._image_areas[index]._current_pixmap = None
            self._image_areas[index].image_label.setPixmap(QPixmap())  # 空のピクスマップをクリア
            
            # 画像モデルにもエラー情報を記録
            if self._image_model:
                error_info = {"error": "画像読み込みエラー", "path": path}
                self._image_model.set_error_info(index, error_info)
                
            return
        
        # 現在の表示モードを保存
        current_fit_mode = self.is_fit_to_window_mode()
        current_zoom = self.get_zoom_factor()
        
        # デュアルモードとRTL情報をモデルから取得
        is_dual = self._image_model.is_dual_view() if self._image_model else False
        
        # ログを追加
        log_print(INFO, f"set_image: index={index}, デュアルモード={is_dual}, 画像エリア数={len(self._image_areas)}")
        
        # 画像エリアの内部状態を更新
        self._image_areas[index]._current_pixmap = pixmap
        self._image_areas[index]._fit_to_window = current_fit_mode
        self._image_areas[index]._zoom_factor = current_zoom
        
        # 明示的にデュアルモード情報を設定し、set_sideを呼び出す
        self._image_areas[index]._is_dual_mode = is_dual
        self._image_areas[index]._is_right_side = (index == 1)
        self._image_areas[index].set_side(is_right=(index==1), is_dual=is_dual)
        
        # 画像モデルに画像情報を設定
        if self._image_model:
            self._image_model.set_image(index, pixmap, data, numpy_array, info, path)
            
            # モデルの表示モードを明示的に現在の設定に維持
            self._image_model.set_display_mode(current_fit_mode)
            self._image_model.set_zoom_factor(current_zoom)
        
        # 表示モードを先に設定して画面のちらつきを防止
        if index < len(self._image_areas) and self._image_areas[index]:
            area = self._image_areas[index]
            
            # 明示的に表示モードを設定
            if hasattr(area, 'set_fit_to_window'):
                area.set_fit_to_window(current_fit_mode)
                
                # 非fit_to_windowモードの場合はズーム倍率も設定
                if not current_fit_mode and hasattr(area, 'set_zoom'):
                    area.set_zoom(current_zoom)
                
                log_print(DEBUG, f"表示モードを先に設定: fit_to_window={current_fit_mode}")
        
        # 次に画像を表示（現在の表示モードは既に適用済み）
        if current_fit_mode:
            # ウィンドウに合わせるモード
            # テキストを明示的にクリア
            self._image_areas[index].image_label.setText("")
            
            self._image_areas[index].image_label.setPixmap(pixmap)
            log_print(DEBUG, f"pixmapを設定: {pixmap.width()}x{pixmap.height()}")
            
            # スクロールエリア全体を更新
            self._image_areas[index]._adjust_image_size()
            
            # イベント処理を強制的に実行してUIを更新
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        else:
            # 原寸大表示モード - 画像を設定してから調整
            # テキストを明示的にクリア
            self._image_areas[index].image_label.setText("")
            
            self._image_areas[index].image_label.setPixmap(pixmap)
            self._image_areas[index].image_label.adjustSize()
            self._image_areas[index]._adjust_image_size()
            
            # イベント処理を強制的に実行してUIを更新
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            
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
        self._image_areas[index].image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
        self._image_areas[index].image_label.setPixmap(QPixmap())  # 空のピクスマップ
        
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
        
        # デュアルモードとRTL情報を取得
        is_dual = self._image_model.is_dual_view() if self._image_model else False
        
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
        
        # デュアルモードかチェック - モデルから直接取得
        is_dual = self._image_model.is_dual_view() if self._image_model else False
        
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
        old_right_to_left = parent_window._right_to_left if hasattr(parent_window, '_right_to_left') else False
        old_browser_shift = parent_window._browser_shift if hasattr(parent_window, '_browser_shift') else False
        
        # 重要な設定変更があったかどうかを画像モデルのset_view_modeで確認
        layout_change_needed = self._image_model.set_view_mode(mode)
        
        # 画像モデルから新しい設定を取得
        new_dual_view = self._image_model.is_dual_view()
        browser_pages = self._image_model.get_browser_pages()
        browser_shift = self._image_model.is_browser_shift()
        right_to_left = self._image_model.is_right_to_left()
        
        log_print(INFO, f"表示モード変更: {mode}, dual_view={new_dual_view}, right_to_left={right_to_left}, shift={browser_shift}")
        
        # ブラウザの設定を更新
        if hasattr(parent_window, '_browser') and parent_window._browser:
            try:
                # ブラウザのプロパティを直接変更
                parent_window._browser._pages = browser_pages
                parent_window._browser._shift = browser_shift
                
                # 親ウィンドウの変数を同期
                parent_window._browser_pages = browser_pages
                parent_window._browser_shift = browser_shift
                parent_window._dual_view = new_dual_view
                parent_window._right_to_left = right_to_left
                
                log_print(INFO, f"ブラウザ設定を更新: pages={browser_pages}, shift={browser_shift}")
                
                # デバッグ出力を追加（ブラウザの内部状態を確認）
                log_print(DEBUG, f"ブラウザ設定更新確認: pages={parent_window._browser._pages}, shift={parent_window._browser._shift}")
            except Exception as e:
                log_print(ERROR, f"ブラウザの更新に失敗しました: {e}")
                import traceback
                log_print(ERROR, traceback.format_exc())
        else:
            # ブラウザがなくても親ウィンドウの変数を同期
            parent_window._browser_pages = browser_pages
            parent_window._browser_shift = browser_shift
            parent_window._dual_view = new_dual_view
            parent_window._right_to_left = right_to_left
        
        # デュアルモードの切り替えが発生した場合、UIを再構築
        if old_dual_view != new_dual_view:
            log_print(INFO, f"デュアルモード切替: {old_dual_view} → {new_dual_view}")
            
            # 画面を再構築する前に現在の画像情報を保存
            saved_pixmaps = []
            saved_datas = []
            saved_numpy_arrays = []
            saved_infos = []
            saved_paths = []
            
            for i in range(2):
                if self._image_model and self._image_model.has_image(i):
                    pixmap, data, numpy_array, info, path = self._image_model.get_image(i)
                    saved_pixmaps.append(pixmap)
                    saved_datas.append(data)
                    saved_numpy_arrays.append(numpy_array)
                    saved_infos.append(info)
                    saved_paths.append(path)
                else:
                    saved_pixmaps.append(None)
                    saved_datas.append(None)
                    saved_numpy_arrays.append(None)
                    saved_infos.append({})
                    saved_paths.append("")
            
            # 表示モードも保存
            saved_fit_mode = self._image_model.is_fit_to_window()
            saved_zoom = self._image_model.get_zoom_factor()
            
            # 内部状態をリセット
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
                parent_window.splitter.setContentsMargins(0, 0, 0, 0)
                parent_window.splitter.setOpaqueResize(False)
                parent_window.splitter.setHandleWidth(1)
                parent_window.main_layout.addWidget(parent_window.splitter)
                
                # 左右の画像エリアを作成
                for i in range(2):
                    scroll_area = ImageScrollArea()
                    scroll_area.setFocusPolicy(Qt.StrongFocus)
                    from PySide6.QtWidgets import QFrame
                    scroll_area.setFrameShape(QFrame.NoFrame)
                    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    scroll_area.setWidgetResizable(True)  # 明示的に設定を追加
                    parent_window.image_areas.append(scroll_area)
                
                # 明示的にハンドラの内部配列を更新
                self._image_areas = parent_window.image_areas
                
                # スプリッターには常に left->right の順で追加
                # (RTLの場合の表示順序の反転はImageModelで処理されるため)
                parent_window.splitter.addWidget(parent_window.image_areas[0])  # 左側用
                parent_window.splitter.addWidget(parent_window.image_areas[1])  # 右側用
                log_print(DEBUG, f"デュアルモード（{mode}）でスプリッター作成")
                
                # スプリッターの位置を50:50に設定
                parent_window.splitter.setSizes([500, 500])
                
                # マウストラッキングを設定
                parent_window.splitter.setMouseTracking(True)
                parent_window.image_areas[0].setMouseTracking(True)
                parent_window.image_areas[1].setMouseTracking(True)
            else:
                # シングルビューの場合は単純にスクロールエリアを追加
                scroll_area = ImageScrollArea()
                scroll_area.setFocusPolicy(Qt.StrongFocus)
                parent_window.image_areas.append(scroll_area)
                parent_window.main_layout.addWidget(scroll_area)
                
                # スクロールエリア配列に空の2枚目要素を追加（統一的な処理のため）
                parent_window.image_areas.append(None)
                
                # 明示的にハンドラの内部配列を更新
                self._image_areas = parent_window.image_areas
            
            # 再構築したエリアをハンドラに設定
            self._image_areas = parent_window.image_areas
            
            # 表示モードと配置情報をセットアップ
            for i, area in enumerate(self._image_areas):
                if area:
                    # RTLとデュアルモード情報を設定
                    area._is_dual_mode = new_dual_view
                    area._is_right_side = (i == 1)
                    area._fit_to_window = saved_fit_mode
                    area._zoom_factor = saved_zoom
                    
                    # スクロールバー設定を強化
                    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    area.setWidgetResizable(True)
            
            # ナビゲーションバーの右左モードも更新
            if hasattr(parent_window, 'navigation_bar'):
                parent_window.navigation_bar.set_right_to_left_mode(right_to_left)
                log_print(DEBUG, f"ナビゲーションバーを更新: right_to_left={right_to_left}")
            
            # 重要な部分: 画像の復元処理
            if parent_window._browser:
                # ブラウザがある場合は _update_images_from_browser() を使用
                log_print(INFO, "ブラウザから画像を再取得します")
                try:
                    parent_window._update_images_from_browser()
                except Exception as e:
                    log_print(ERROR, f"ブラウザからの画像再取得に失敗: {e}")
                    import traceback
                    log_print(ERROR, traceback.format_exc())
            else:
                # ブラウザがない場合は保存した画像を復元
                log_print(INFO, "保存した画像情報から復元します")
                
                if new_dual_view:
                    # デュアルモードに切り替わった場合
                    for i in range(2):
                        if i < len(saved_pixmaps) and saved_pixmaps[i]:
                            log_print(DEBUG, f"インデックス {i} の画像を復元: {saved_paths[i]}")
                            
                            # 画像情報をセット
                            self.set_image(
                                saved_pixmaps[i], 
                                saved_datas[i], 
                                saved_numpy_arrays[i], 
                                saved_infos[i], 
                                saved_paths[i], 
                                i
                            )
                else:
                    # シングルモードに切り替わった場合は0番目に表示
                    # インデックス0に画像があればそれを使い、なければインデックス1の画像を使う
                    if saved_pixmaps[0]:
                        idx = 0
                    elif saved_pixmaps[1]:
                        idx = 1
                    else:
                        idx = -1
                    
                    if idx >= 0:
                        log_print(DEBUG, f"シングルモードで画像を復元: {saved_paths[idx]}")
                        
                        # 画像情報をセット
                        self.set_image(
                            saved_pixmaps[idx], 
                            saved_datas[idx], 
                            saved_numpy_arrays[idx], 
                            saved_infos[idx], 
                            saved_paths[idx], 
                            0  # シングルモードでは必ずインデックス0に表示
                        )
            
            # 表示モードも適切に復元
            if saved_fit_mode:
                self.fit_to_window()
            else:
                self.show_original_size()
        else:
            # デュアルモードの切り替えがない場合（右左切り替えやシフトモード切り替えのみ）
            if old_right_to_left != right_to_left:
                log_print(INFO, f"左右配置を変更: {old_right_to_left} → {right_to_left}")
                
                # ナビゲーションバーを更新
                if hasattr(parent_window, 'navigation_bar'):
                    parent_window.navigation_bar.set_right_to_left_mode(right_to_left)
                
                # 画像エリアの情報を更新
                for i, area in enumerate(self._image_areas):
                    if area:
                        area._is_dual_mode = right_to_left
                
                # スプリッターが存在する場合はウィジェットを入れ替え
                if hasattr(parent_window, 'splitter') and parent_window.splitter and new_dual_view:
                    # ウィジェットを一度取り外す
                    for area in self._image_areas:
                        if area:
                            area.setParent(None)
                    
                    # 常に同じ順序で追加（RTLの場合の表示順序の反転はImageModelで処理）
                    parent_window.splitter.addWidget(self._image_areas[0])  # 左側用
                    parent_window.splitter.addWidget(self._image_areas[1])  # 右側用
                    
                    # スプリッターの位置を設定
                    parent_window.splitter.setSizes([500, 500])
                    
                    # 画像表示を更新
                    self.refresh_display_mode(self.is_fit_to_window_mode())
                
                # ブラウザから画像を再取得
                if parent_window._browser:
                    try:
                        parent_window._update_images_from_browser()
                    except Exception as e:
                        log_print(ERROR, f"ブラウザからの画像再取得に失敗: {e}")
            
            # シフトモードのみの変更
            elif old_browser_shift != browser_shift:
                log_print(INFO, f"シフトモードを変更: {old_browser_shift} → {browser_shift}")
                
                # ブラウザから画像を再取得
                if parent_window._browser:
                    try:
                        parent_window._update_images_from_browser()
                    except Exception as e:
                        log_print(ERROR, f"ブラウザからの画像再取得に失敗: {e}")
            
            # コンテキストメニューを更新
            if hasattr(parent_window, 'context_menu'):
                parent_window.context_menu.update_view_mode(mode)
        
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
        
        # デュアルモードか確認して設定を更新 - モデルから直接取得
        is_dual = self._image_model.is_dual_view() if self._image_model else False
        
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

    @Slot(object, str, str)
    def _on_show_error(self, area, error_message, filename):
        """エラーメッセージを表示するスロット（UIスレッドで実行）"""
        try:
            if not area:
                log_print(ERROR, "エリアが無効です")
                return
                
            # 表示するメッセージの整形
            display_message = f"{error_message}\n\n{filename}" if filename else error_message
            
            # 画像情報をクリアして、エラーメッセージを設定
            area._current_pixmap = None
            area.image_label.setText(display_message)
            area.image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
            area.image_label.setAlignment(Qt.AlignCenter)
            area.image_label.setPixmap(QPixmap())  # 空のピクスマップを明示的にセット
            
            log_print(INFO, f"エラー情報を表示: {error_message} (ファイル: {filename})")
        except Exception as e:
            log_print(ERROR, f"エラー表示中にエラーが発生: {e}")
            import traceback
            log_print(ERROR, traceback.format_exc())

    @Slot(object, object, bool, float, bool, bool)
    def _on_show_image(self, area, pixmap, fit_to_window, zoom_factor, is_dual, is_right_side):
        """画像を表示するスロット（UIスレッドで実行）"""
        try:
            if not area:
                log_print(ERROR, "エリアが無効です")
                return
                
            # ピクスマップを更新
            area._current_pixmap = pixmap
            
            # 設定を更新
            area._fit_to_window = fit_to_window
            area._zoom_factor = zoom_factor
            area._is_dual_mode = is_dual
            area._is_right_side = is_right_side
            
            # テキストを明示的にクリア
            area.image_label.setText("")
            
            # 表示モードに応じて適切に画像表示を更新
            if fit_to_window:
                area.set_fit_to_window(True)
                log_print(DEBUG, "表示モードをウィンドウに合わせるに設定")  
            else:
                area.set_zoom(zoom_factor)
                log_print(DEBUG, "表示モードを原寸大に設定")
            
            # ラベルの設定を強化
            area.image_label.setStyleSheet("color: white; background-color: black;")
            
        except Exception as e:
            log_print(ERROR, f"画像表示中にエラーが発生: {e}")
            import traceback
            log_print(ERROR, traceback.format_exc())

    def check_model_updates(self):
        """画像モデルをチェックして必要な表示更新を行う"""
        if not self._image_model:
            return False
        
        updates_applied = False
        
        # 表示モードの現在状態を取得
        fit_to_window = self._image_model.is_fit_to_window()
        zoom_factor = self._image_model.get_zoom_factor()
        
        # デュアルモードの状態とRTL情報をモデルから直接取得
        is_dual = self._image_model.is_dual_view()
        
        # インデックスの検証を強化
        for index in range(2):
            # 更新が必要かつ画像エリアが有効な場合のみ処理
            if not self._image_model.is_display_update_needed(index):
                continue
            
            # 明示的に画像エリアの有効性を確認
            if index >= len(self._image_areas):
                log_print(ERROR, f"インデックス {index} が範囲外: エリア数 {len(self._image_areas)}")
                continue
                
            if self._image_areas[index] is None:
                log_print(ERROR, f"インデックス {index} の画像エリアが不正: None")
                continue
            
            log_print(DEBUG, f"画像インデックス {index} の表示更新が必要です")
            
            # エリアオブジェクト取得
            area = self._image_areas[index]
            
            # 通常の画像表示処理
            # 画像モデルから最新の情報を取得
            pixmap = self._image_model.get_pixmap(index)
            
            # 有効なピクスマップがあれば表示設定
            if pixmap:
                try:
                    # ピクスマップを更新
                    area._current_pixmap = pixmap
                    
                    # 設定を更新
                    area._fit_to_window = fit_to_window
                    area._zoom_factor = zoom_factor
                    area._is_dual_mode = is_dual
                    area._is_right_side = (index == 1)
                    
                    # テキストを明示的にクリア
                    area.image_label.setText("")
                    
                    # 表示モードに応じて適切に画像表示を更新
                    if fit_to_window:
                        area.set_fit_to_window(True)
                        log_print(DEBUG, "表示モードをウィンドウに合わせるに設定")  
                    else:
                        area.set_zoom(zoom_factor)
                        log_print(DEBUG, "表示モードを原寸大に設定")
                    
                    # ラベルの設定を強化
                    area.image_label.setStyleSheet("color: white; background-color: black;")
                except Exception as e:
                    log_print(ERROR, f"画像表示中にエラーが発生: {e}")
                    import traceback
                    log_print(ERROR, traceback.format_exc())
            else:
                try:
                    # ピクスマップがない場合はエラーメッセージ表示
                    area._current_pixmap = None
                    area.image_label.setText("画像がありません")
                    area.image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
                    area.image_label.setAlignment(Qt.AlignCenter)
                    area.image_label.setPixmap(QPixmap())  # 空のピクスマップを明示的にセット
                    log_print(WARNING, f"インデックス {index} の画像を読み込めませんでした")
                except Exception as e:
                    log_print(ERROR, f"エラー表示中にエラーが発生: {e}")
                    import traceback
                    log_print(ERROR, traceback.format_exc())
            
            updates_applied = True
            
            # 更新フラグをクリア
            self._image_model.clear_display_update_flag(index)
        
        return updates_applied

