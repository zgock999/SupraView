"""
超解像処理のビジュアルテストツール
"""
import os
import sys
import time
import cv2
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
import threading
import queue
import torch
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QComboBox, 
    QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QSplitter,
    QScrollArea, QSlider, QGroupBox, QCheckBox, QSpinBox,
    QMessageBox, QProgressBar, QSizePolicy, QDoubleSpinBox,
    QDialog, QFormLayout, QDialogButtonBox, QTabWidget,
    QProgressDialog
)
from PySide6.QtGui import QPixmap, QImage, QResizeEvent, QPainter, QColor
from PySide6.QtCore import Qt, Signal, QSize, QThread, QTimer

# sr_baseをインポート
from sr.sr_base import SuperResolutionBase, SRMethod, SRResult

# 画像処理ユーティリティをインポート
# sr_utils.pyから必要な関数をインポートする
from sr.sr_utils import is_cuda_available, get_gpu_info, get_sr_method_from_string

# 超解像設定ダイアログをインポート
from sr.viewer.sr_settings_dialog import SuperResolutionSettingsDialog

# 現在使用しているエラーのある関数をコメントアウトして代替関数を定義
def get_available_memory() -> Dict[str, int]:
    """メモリ情報を取得（仮実装）"""
    try:
        from sr.sr_utils import get_available_memory
        return get_available_memory()
    except ImportError:
        # sr_utilsに実装されていない場合の代替実装
        return {'total': 0, 'free': 0, 'used': 0}

def get_cuda_devices() -> List[str]:
    """CUDAデバイス情報を取得（仮実装）"""
    try:
        from sr.sr_utils import get_cuda_devices
        return get_cuda_devices()
    except ImportError:
        # sr_utilsに実装されていない場合の代替実装
        if is_cuda_available():
            return ["CUDA Device"]
        return []


# ImageComparisonWidgetを改良した統合画像表示ウィジェット
class EnhancedImageWidget(QWidget):
    """拡張された画像表示ウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # スクロール領域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)
        
        # 内部コンテンツウィジェット
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.scroll_area.setWidget(self.content_widget)
        
        # 単一の画像ラベル
        self.image_label = QLabel("画像が読み込まれていません")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.image_label)
        
        # 情報表示ラベル
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.info_label)
        
        # 画像データ
        self.original_image = None  # 元の画像
        self.sr_image = None        # 超解像処理された画像
        self.current_pixmap = None  # 現在表示中のピクスマップ
        self.display_original = True # 元画像を表示中かどうか
        
        # 表示設定
        self.fit_to_window = True   # ウィンドウにフィットさせるか
    
    def set_original_image(self, image):
        """入力画像を設定"""
        self.original_image = image
        self.display_original = True
        if isinstance(image, np.ndarray):
            self.display_image(image)
            self.info_label.setText("元の画像")
        self.update_display()
    
    def set_sr_image(self, image):
        """超解像画像を設定して表示を切り替える"""
        self.sr_image = image
        if isinstance(image, np.ndarray):
            self.display_original = False
            self.display_image(image)
            h, w = image.shape[:2]
            self.info_label.setText(f"超解像画像: {w}x{h} ピクセル")
        self.update_display()
    
    def display_image(self, image):
        """画像を表示用に変換して設定"""
        if not isinstance(image, np.ndarray):
            return
            
        try:
            # OpenCV形式からQImageへ変換
            h, w = image.shape[:2]
            
            # チャンネル数を明示的に確認
            if len(image.shape) == 3 and image.shape[2] == 3:
                # 連続したメモリ領域かどうか確認
                if not image.flags['C_CONTIGUOUS']:
                    # データが連続していない場合はコピーを作成
                    image = np.ascontiguousarray(image)
                    
                qimg = QImage(image.data, w, h, w * 3, QImage.Format_BGR888)
            elif len(image.shape) == 3 and image.shape[2] == 4:
                # アルファチャンネルがある場合
                if not image.flags['C_CONTIGUOUS']:
                    image = np.ascontiguousarray(image)
                qimg = QImage(image.data, w, h, w * 4, QImage.Format_ARGB32)
            elif len(image.shape) == 2:
                # グレースケール
                if not image.flags['C_CONTIGUOUS']:
                    image = np.ascontiguousarray(image)
                qimg = QImage(image.data, w, h, w, QImage.Format_Grayscale8)
            else:
                # その他の形式：変換してRGB形式にする
                print(f"未対応の画像形式: shape={image.shape}, dtype={image.dtype}")
                if len(image.shape) == 3 and image.shape[2] > 3:
                    # チャンネル数が多い場合は最初の3チャンネルだけ使用
                    image = image[:, :, :3]
                # BGRに変換
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                image_bgr = np.ascontiguousarray(image_bgr)
                qimg = QImage(image_bgr.data, w, h, w * 3, QImage.Format_BGR888)
            
            pixmap = QPixmap.fromImage(qimg)
            self.current_pixmap = pixmap
            
            # 表示サイズに調整してラベルに設定
            self.set_pixmap_to_label()
            
        except Exception as e:
            # エラー時は画像情報を出力してデバッグを容易にする
            print(f"画像変換エラー: {e}")
            print(f"画像情報: shape={image.shape}, dtype={image.dtype}, flags={image.flags}")
            # エラーメッセージを表示
            self.image_label.setText(f"画像を表示できません: {e}")
    
    def set_pixmap_to_label(self):
        """ピクスマップをラベルに適切なサイズで設定"""
        if self.current_pixmap is None:
            return
            
        pixmap = self.current_pixmap
        
        if self.fit_to_window:
            # スクロールエリアのサイズを取得
            viewport_size = self.scroll_area.viewport().size()
            
            # スクロールバーの状態を考慮
            scroll_width = self.scroll_area.verticalScrollBar().width() if self.scroll_area.verticalScrollBar().isVisible() else 0
            scroll_height = self.scroll_area.horizontalScrollBar().height() if self.scroll_area.horizontalScrollBar().isVisible() else 0
            
            # 実際の表示可能領域を計算
            available_width = viewport_size.width() - scroll_width - 20  # マージン用に少し小さく
            available_height = viewport_size.height() - scroll_height - 20  # マージン用に少し小さく
            
            # アスペクト比を保持してスケーリング
            pixmap = self.current_pixmap.scaled(
                available_width, 
                available_height, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
        
        self.image_label.setPixmap(pixmap)
    
    def toggle_fit_mode(self, fit_to_window: bool):
        """フィットモードを切り替える"""
        self.fit_to_window = fit_to_window
        self.update_display()
    
    def update_display(self):
        """表示を更新"""
        # 現在のモードに応じて表示を更新
        if self.current_pixmap is not None:
            self.set_pixmap_to_label()
    
    def toggle_display_mode(self):
        """元画像と超解像画像の表示を切り替える"""
        if self.display_original and self.sr_image is not None:
            # 超解像画像に切り替え
            self.display_original = False
            self.display_image(self.sr_image)
            h, w = self.sr_image.shape[:2]
            self.info_label.setText(f"超解像画像: {w}x{h} ピクセル")
        elif not self.display_original and self.original_image is not None:
            # 元画像に切り替え
            self.display_original = True
            self.display_image(self.original_image)
            h, w = self.original_image.shape[:2]
            self.info_label.setText(f"元の画像: {w}x{h} ピクセル")
        
        self.update_display()
    
    def resizeEvent(self, event):
        """ウィジェットのリサイズ時に画像表示を調整"""
        super().resizeEvent(event)
        self.update_display()


# モデル初期化スレッドクラスを追加
class ModelInitThread(QThread):
    """
    バックグラウンドでモデルの初期化を行うスレッド
    """
    initialization_finished = Signal(object, bool)  # モデルインスタンスと成功/失敗フラグ
    initialization_progress = Signal(str)  # 初期化の進捗メッセージ
    
    def __init__(self, method: SRMethod, scale: int, options: Dict[str, Any]):
        super().__init__()
        self.method = method
        self.scale = scale
        self.options = options or {}
        self.is_cancelled = False
        
    def cancel(self):
        """初期化をキャンセルする"""
        self.is_cancelled = True
        
    def run(self):
        try:
            # 初期化開始のメッセージ
            self.initialization_progress.emit(f"モデル {self.method.name} (x{self.scale}) の初期化中...")
            
            # キャンセルチェック
            if self.is_cancelled:
                self.initialization_finished.emit(None, False)
                return
            
            # モデルインスタンスの作成
            sr_instance = SuperResolutionBase.create(self.method, self.scale, self.options)
            if sr_instance is None:
                self.initialization_progress.emit(f"モデル {self.method.name} の作成に失敗しました")
                self.initialization_finished.emit(None, False)
                return
            
            # キャンセルチェック
            if self.is_cancelled:
                self.initialization_finished.emit(None, False)
                return
            
            # モデルの初期化
            if not sr_instance.is_initialized():
                self.initialization_progress.emit(f"モデル {self.method.name} の初期化中...")
                if not sr_instance.initialize(self.options):
                    self.initialization_progress.emit(f"モデル {self.method.name} の初期化に失敗しました")
                    self.initialization_finished.emit(None, False)
                    return
            
            # 初期化完了
            self.initialization_progress.emit(f"モデル {self.method.name} の初期化が完了しました")
            self.initialization_finished.emit(sr_instance, True)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.initialization_progress.emit(f"モデル初期化中にエラー: {str(e)}")
            self.initialization_finished.emit(None, False)


class ProcessingThread(QThread):
    """
    バックグラウンドで超解像処理を実行するスレッド
    """
    update_progress = Signal(int)
    processing_finished = Signal(SRResult)
    processing_error = Signal(str)
    processing_cancelled = Signal()  # キャンセル時のシグナルを追加
    
    def __init__(self, image_path: str, method: SRMethod, scale: int, options: Dict[str, Any], sr_instance=None):
        super().__init__()
        self.image_path = image_path
        self.method = method
        self.scale = scale
        self.options = options or {}
        self.sr_instance = sr_instance  # 既存のモデルインスタンス（Noneの場合は新規作成）
        self.is_cancelled = False  # キャンセルフラグの追加
        
    def cancel(self):
        """処理をキャンセルする"""
        self.is_cancelled = True
        # SRインスタンスにキャンセル要求を伝える（sr_baseがキャンセルをサポートしている場合）
        if self.sr_instance and hasattr(self.sr_instance, 'cancel'):
            self.sr_instance.cancel()
        
    def run(self):
        try:
            # プログレス表示用
            self.update_progress.emit(10)
            
            # キャンセルチェック
            if self.is_cancelled:
                self.processing_cancelled.emit()
                return
            
            # 画像を読み込み
            img = cv2.imread(self.image_path)
            if img is None:
                self.processing_error.emit(f"画像の読み込みに失敗しました: {self.image_path}")
                return
                
            self.update_progress.emit(20)
            
            # キャンセルチェック
            if self.is_cancelled:
                self.processing_cancelled.emit()
                return
            
            # 文字列からSRMethod列挙型へ変換
            sr_method = None
            if isinstance(self.method, str):
                sr_method = get_sr_method_from_string(self.method)
            else:
                sr_method = self.method
            
            # 超解像処理のインスタンスチェック - すでにモデルインスタンスが渡されていることを前提
            if self.sr_instance is None:
                self.processing_error.emit("モデルインスタンスが初期化されていません")
                return
            
            sr_instance = self.sr_instance
            
            # キャンセルチェック
            if self.is_cancelled:
                self.processing_cancelled.emit()
                return
            
            self.update_progress.emit(30)
            
            # 処理実行
            result = sr_instance.process(img, self.options)
            
            # 処理後のキャンセルチェック
            if self.is_cancelled:
                self.processing_cancelled.emit()
                return
            
            self.update_progress.emit(90)
            
            # 結果を通知
            self.processing_finished.emit(result)
            
            # 処理完了
            self.update_progress.emit(100)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # キャンセルされた場合は単にキャンセルシグナルを発行
            if self.is_cancelled:
                self.processing_cancelled.emit()
            else:
                # 通常のエラー処理
                self.processing_error.emit(f"処理中にエラーが発生しました: {str(e)}")


class MainWindow(QMainWindow):
    """
    超解像処理のビジュアルテストツールのメインウィンドウ
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("超解像処理テスト")
        self.setMinimumSize(1000, 600)
        
        # 内部状態の初期化
        self.input_image_path = None
        self.input_image = None
        self.output_image = None
        self.processing_thread = None
        self.model_init_thread = None  # モデル初期化スレッド
        self.current_scale = 4  # デフォルト拡大率を4に設定
        self.current_method = SRMethod.REALESRGAN  # デフォルトメソッドをRealESRGANに設定
        self.last_method = None
        self.is_processing = False  # 処理中フラグの追加
        self.is_model_initializing = False  # モデル初期化中フラグ
        self.auto_process = True  # 自動処理フラグ
        
        # GPUメモリ情報の取得
        self.gpu_available = is_cuda_available()
        self.vram_info = get_available_memory()
        self.cuda_devices = get_cuda_devices()
        
        # 処理オプション
        self.options = {
            'tile': 512,  # タイル処理のサイズ
            'tile_pad': 32,  # パディングサイズ
        }
        
        # モデルインスタンスキャッシュ
        self._sr_instances = {}
        
        # UIの設定
        self.setup_ui()
        
        # タイマー設定（リサイズ遅延用）
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.delayed_resize)
        
        # モデル初期化タイマー（変更後の遅延初期化用）
        self.model_init_timer = QTimer()
        self.model_init_timer.setSingleShot(True)
        self.model_init_timer.timeout.connect(self.delayed_model_initialization)
        
        # 初期化待ちダイアログのための変数
        self.init_progress_dialog = None
        
        # 状態更新
        self.update_gpu_status()
        
        # 初期モデルの事前ロード（起動直後）
        QTimer.singleShot(500, self.initialize_default_model)
        
    def setup_ui(self):
        """UIコンポーネントの設定"""
        # 中央ウィジェットの設定
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # メインレイアウト
        main_layout = QVBoxLayout(main_widget)
        
        # スプリッター作成（コントロールパネルと画像表示領域）
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # === コントロールパネル ===
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        
        # ファイル選択ボタン
        file_button = QPushButton("画像を開く...")
        file_button.clicked.connect(self.open_file)
        control_layout.addWidget(file_button)
        
        # 超解像設定ボタン
        sr_settings_btn = QPushButton("超解像設定...")
        sr_settings_btn.clicked.connect(self.show_sr_settings_dialog)
        control_layout.addWidget(sr_settings_btn)
        
        # --- 状態表示グループ ---
        status_group = QGroupBox("現在の設定")
        status_layout = QFormLayout(status_group)
        
        # 現在のエンジンと倍率の表示
        self.current_engine_label = QLabel("RealESRGAN")
        status_layout.addRow("超解像エンジン:", self.current_engine_label)
        
        self.current_scale_label = QLabel("4x")
        status_layout.addRow("拡大倍率:", self.current_scale_label)
        
        # 自動処理状態の表示
        self.auto_process_label = QLabel("有効")
        status_layout.addRow("自動処理:", self.auto_process_label)
        
        control_layout.addWidget(status_group)
        
        # --- システム情報グループ ---
        system_group = QGroupBox("システム情報")
        system_layout = QVBoxLayout(system_group)
        
        # GPU状態表示
        self.gpu_status_label = QLabel("GPU: 確認中...")
        system_layout.addWidget(self.gpu_status_label)
        
        # メモリ情報表示
        self.memory_label = QLabel("メモリ: 確認中...")
        system_layout.addWidget(self.memory_label)
        
        control_layout.addWidget(system_group)
        
        # 画像表示切替ボタン
        self.toggle_view_button = QPushButton("元画像/処理画像 切替")
        self.toggle_view_button.clicked.connect(self.toggle_image_display)
        self.toggle_view_button.setEnabled(False)  # 初期状態では無効
        control_layout.addWidget(self.toggle_view_button)
        
        # 実行ボタンとキャンセルボタンの水平レイアウト
        execute_layout = QHBoxLayout()
        
        # 実行ボタン
        self.run_button = QPushButton("処理実行")
        self.run_button.clicked.connect(self.run_processing)
        self.run_button.setEnabled(False)
        execute_layout.addWidget(self.run_button, 2)  # 2:1の幅比率
        
        # キャンセルボタン
        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.clicked.connect(self.cancel_processing)
        self.cancel_button.setEnabled(False)  # 初期状態では無効
        execute_layout.addWidget(self.cancel_button, 1)  # 2:1の幅比率
        
        control_layout.addLayout(execute_layout)
        
        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        control_layout.addWidget(self.progress_bar)
        
        # スペーサー
        control_layout.addStretch()
        
        # スプリッターにコントロールパネルを追加
        splitter.addWidget(control_panel)
        
        # === 画像表示領域 ===
        self.image_widget = EnhancedImageWidget()
        splitter.addWidget(self.image_widget)
        
        # スプリッターの初期サイズを設定
        splitter.setSizes([250, 750])
        
        # ステータスバー
        self.statusBar().showMessage("準備完了")
    
    def show_sr_settings_dialog(self):
        """超解像設定ダイアログを表示"""
        # モデル初期化中は設定ダイアログを開かない
        if self.is_model_initializing:
            QMessageBox.information(
                self,
                "初期化中",
                "モデルの初期化中です。しばらくお待ちください。"
            )
            return
            
        dialog = SuperResolutionSettingsDialog(
            self, 
            options=self.options,
            current_method=self.current_method,
            current_scale=self.current_scale
        )
        
        if dialog.exec():
            # ダイアログの設定を取得
            settings = dialog.get_settings()
            
            # 変更前の設定を保存
            old_method = self.current_method
            old_scale = self.current_scale
            
            # 設定を更新
            self.current_method = settings['method']
            self.current_scale = settings['scale']
            self.auto_process = settings['auto_process']
            self.options = settings['options']
            
            # 表示ラベルを更新
            self.update_settings_display()
            
            # 再初期化が必要かチェック
            reinit_needed = False
            
            # メソッドまたはスケールが変更された場合
            if old_method != self.current_method or old_scale != self.current_scale:
                # 既存のインスタンスへの参照を解除
                old_cache_key = f"{old_method.name}_{old_scale}"
                if old_cache_key in self._sr_instances:
                    print(f"モデル参照を解除: {old_cache_key}")
                    self._sr_instances[old_cache_key] = None
                        
                reinit_needed = True
                self.statusBar().showMessage(f"メソッドまたはスケールが変更されたため再初期化します")
            
            # RealESRGANのオプション変更チェック
            elif self.current_method == SRMethod.REALESRGAN:
                # 既存のインスタンスへの参照を解除
                model_cache_key = f"{self.current_method.name}_{self.current_scale}"
                if model_cache_key in self._sr_instances:
                    print(f"RealESRGANオプション変更のため参照を解除: {model_cache_key}")
                    self._sr_instances[model_cache_key] = None
                    
                reinit_needed = True
                self.statusBar().showMessage("RealESRGANオプションが変更されたため再初期化します")
            
            # 再初期化が必要なら初期化処理をスケジュール（ダイアログ表示あり）
            if reinit_needed:
                print("モデルの再初期化をスケジュール")
                self.schedule_model_initialization()
                
                # 重要: 再初期化が必要な場合は、初期化完了後に自動処理が実行されるのでここでは実行しない
                return
            
            # 再初期化が不要で、画像が読み込まれていて自動処理が有効なら処理を実行
            if self.input_image_path and self.auto_process and not self.is_model_initializing:
                # モデルが初期化されているか確認
                model_cache_key = f"{self.current_method.name}_{self.current_scale}"
                if model_cache_key in self._sr_instances and self._sr_instances[model_cache_key] is not None:
                    self.run_processing()
                else:
                    # モデル未初期化の場合は初期化を開始（初期化完了時に自動処理が実行される）
                    self.ensure_model_initialized()

    def update_settings_display(self):
        """現在の設定表示を更新"""
        # エンジン名をラベルに表示
        method_name = self.get_method_display_name(self.current_method)
        self.current_engine_label.setText(method_name)
        
        # 倍率をラベルに表示
        self.current_scale_label.setText(f"{self.current_scale}x")
        
        # 自動処理状態を表示
        self.auto_process_label.setText("有効" if self.auto_process else "無効")
    
    def get_method_display_name(self, method: SRMethod) -> str:
        """メソッドの表示名を取得"""
        method_names = {
            SRMethod.OPENCV_EDSR: "OpenCV EDSR",
            SRMethod.OPENCV_ESPCN: "OpenCV ESPCN",
            SRMethod.OPENCV_FSRCNN: "OpenCV FSRCNN",
            SRMethod.OPENCV_LAPSRN: "OpenCV LapSRN",
            SRMethod.OPENCV_CUBIC: "OpenCV Bicubic",
            SRMethod.OPENCV_LANCZOS: "OpenCV Lanczos4",
            SRMethod.SWINIR_LIGHTWEIGHT: "SwinIR 軽量モデル",
            SRMethod.SWINIR_CLASSICAL: "SwinIR 標準モデル",
            SRMethod.SWINIR_REAL: "SwinIR 実写向け",
            SRMethod.SWINIR_LARGE: "SwinIR 高品質モデル",
            SRMethod.REALESRGAN: "Real-ESRGAN"
        }
        return method_names.get(method, method.name)
    
    def toggle_auto_process(self, state):
        """自動処理の切り替え"""
        self.auto_process = state == Qt.Checked
    
    def toggle_image_display(self):
        """元画像と処理画像の表示を切り替え"""
        if hasattr(self, 'image_widget'):
            self.image_widget.toggle_display_mode()

    def initialize_default_model(self):
        """デフォルトモデルを事前に初期化する"""
        try:
            # 現在選択されているメソッドとスケールでモデルを初期化
            self.initialize_model(self.current_method, self.current_scale, show_dialog=True)
        except Exception as e:
            print(f"デフォルトモデル初期化エラー: {e}")
    
    def schedule_model_initialization(self):
        """モデル初期化を遅延実行するようにスケジュール"""
        # 既存の初期化タイマーをキャンセル
        if self.model_init_timer.isActive():
            self.model_init_timer.stop()
            
        # 1秒後に初期化処理を開始（連続した変更の場合に不要な初期化を防ぐ）
        self.model_init_timer.start(1000)
    
    def delayed_model_initialization(self):
        """遅延実行されるモデル初期化処理"""
        # 現在選択されているメソッドとスケールでモデルを初期化
        try:
            # モデル初期化の開始（ダイアログを表示）
            self.initialize_model(self.current_method, self.current_scale, show_dialog=True)
        except Exception as e:
            print(f"モデル初期化スケジュール中のエラー: {e}")
    
    def initialize_model(self, method: SRMethod, scale: int, show_dialog=False):
        """指定されたメソッドとスケールのモデルを初期化する"""
        # キャッシュキーを作成
        model_cache_key = f"{method.name}_{scale}"
        
        # 既に同じモデルが初期化されている場合は何もしない
        if model_cache_key in self._sr_instances and self._sr_instances[model_cache_key] is not None:
            print(f"モデル {model_cache_key} は既に初期化されています")
            return
        
        # 既存の初期化スレッドがあればキャンセル
        if self.model_init_thread and self.model_init_thread.isRunning():
            self.model_init_thread.cancel()
            self.model_init_thread.wait()
        
        # 処理中のUI状態を更新
        self.is_model_initializing = True
        self.update_ui_state_for_model_initialization(True)
        
        # オプション設定を準備
        options = self.prepare_options_for_method(method)
        
        print(f"モデル初期化開始: {method.name}_{scale}, オプション: {options}")
        
        # 初期化待ちのモードレスダイアログを表示
        if show_dialog:
            self.show_initialization_dialog(method, scale)
        
        # 初期化スレッドを作成して開始
        self.model_init_thread = ModelInitThread(method, scale, options)
        self.model_init_thread.initialization_progress.connect(self.update_initialization_progress)
        self.model_init_thread.initialization_finished.connect(self.model_initialization_completed)
        self.model_init_thread.start()
    
    def show_initialization_dialog(self, method: SRMethod, scale: int):
        """初期化待ちのモードレスダイアログを表示"""
        # 既存のダイアログを閉じる
        if self.init_progress_dialog is not None and self.init_progress_dialog.isVisible():
            self.init_progress_dialog.close()
        
        method_name = self.get_method_display_name(method)
        
        # 新しいダイアログを作成（モードレス）
        self.init_progress_dialog = QProgressDialog(
            f"{method_name} (x{scale}) モデルを初期化しています...",
            "バックグラウンドで実行",  # キャンセルボタンのテキスト
            0, 0,  # 進捗範囲（不定）
            self
        )
        self.init_progress_dialog.setWindowTitle("モデル初期化中")
        # モードレスに設定
        self.init_progress_dialog.setWindowModality(Qt.NonModal)
        # 自動クローズを無効化（手動で閉じる）
        self.init_progress_dialog.setAutoClose(False)
        self.init_progress_dialog.setAutoReset(False)
        # 最小表示時間を設定
        self.init_progress_dialog.setMinimumDuration(500)  # 500ms以上かかる場合のみ表示
        
        # キャンセルボタンが押された場合は、バックグラウンド処理に切り替え
        self.init_progress_dialog.canceled.connect(self.init_progress_dialog.close)
        
        # ダイアログを表示
        self.init_progress_dialog.show()
    
    def update_initialization_progress(self, message: str):
        """モデル初期化の進捗メッセージを更新"""
        self.statusBar().showMessage(message)
        
        # 進捗ダイアログの更新
        if self.init_progress_dialog and self.init_progress_dialog.isVisible():
            self.init_progress_dialog.setLabelText(message)
    
    def model_initialization_completed(self, model_instance, success: bool):
        """モデル初期化完了時のコールバック"""
        if success and model_instance:
            # モデルインスタンスをキャッシュに保存
            model_cache_key = f"{model_instance.method.name}_{model_instance.scale}"
            self._sr_instances[model_cache_key] = model_instance
            self.statusBar().showMessage(f"モデル {model_cache_key} の初期化が完了しました")
        else:
            # 初期化失敗の場合
            self.statusBar().showMessage("モデルの初期化に失敗しました")
        
        # 初期化中のUIステートを解除
        self.is_model_initializing = False
        self.update_ui_state_for_model_initialization(False)
        
        # 初期化待ちダイアログを閉じる
        if self.init_progress_dialog and self.init_progress_dialog.isVisible():
            self.init_progress_dialog.close()
            self.init_progress_dialog = None
        
        # 初期化が成功し、自動処理が有効で画像がロードされている場合のみ処理実行
        if success and model_instance and self.auto_process and self.input_image_path and not self.is_processing:
            print("モデル初期化完了後に自動処理を実行")
            # 少し遅延を入れてUIが更新される時間を確保
            QTimer.singleShot(200, self.run_processing)
    
    def update_ui_state_for_model_initialization(self, is_initializing: bool):
        """モデル初期化中のUI状態を更新"""
        # 初期化中はUIの一部を無効化
        if is_initializing:
            # プログレスバーを進行中表示
            self.progress_bar.setRange(0, 0)  # 無限進行状態
            
            # 実行ボタンを無効化
            if self.input_image_path:  # 画像がロードされている場合のみ
                self.run_button.setEnabled(False)
                self.run_button.setText("モデル初期化中...")
        else:
            # 初期化完了後は通常表示に戻す
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            
            # 画像がロードされていれば実行ボタンを有効化
            if self.input_image_path:
                self.run_button.setEnabled(True)
                self.run_button.setText("処理実行")
    
    def update_option(self, key, value):
        """処理オプションの更新"""
        self.options[key] = value
        # オプション変更後、遅延してモデル初期化を実行
        self.schedule_model_initialization()
    
    def open_file(self):
        """画像ファイルを選択するダイアログを表示"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "開く画像を選択",
            "",
            "画像ファイル (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)"
        )
        
        if not file_path:
            return
            
        try:
            # 実行中の処理があればキャンセル
            if self.processing_thread and self.processing_thread.isRunning():
                self.processing_thread.cancel()
                self.processing_thread.wait(1000)  # 最大1秒待機
            
            # 画像を読み込み
            img = cv2.imread(file_path)
            if img is None:
                QMessageBox.warning(self, "エラー", "画像の読み込みに失敗しました")
                return
                
            # 画像設定
            self.input_image_path = file_path
            self.input_image = img
            
            # まず元画像を表示
            self.image_widget.set_original_image(img)
            
            # 切替ボタンを有効化
            self.toggle_view_button.setEnabled(True)
            
            # モデル初期化中でなければ実行ボタン有効化
            if not self.is_model_initializing:
                self.run_button.setEnabled(True)
            
            # ウィンドウタイトル更新
            filename = os.path.basename(file_path)
            self.setWindowTitle(f"超解像処理テスト - {filename}")
            
            # ステータスバー更新
            h, w = img.shape[:2]
            file_size = os.path.getsize(file_path) / 1024  # KB単位
            self.statusBar().showMessage(f"画像読み込み完了: {w}x{h} ピクセル, {file_size:.1f} KB")
            
            # モデルが初期化されていることを確認
            self.ensure_model_initialized()
            
            # 自動処理が有効なら処理を開始
            if self.auto_process and not self.is_model_initializing:
                self.run_processing()
            
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"画像の読み込み中にエラーが発生しました: {str(e)}")
    
    def ensure_model_initialized(self):
        """現在選択されているモデルが初期化されていることを確認"""
        try:
            method = self.current_method
            scale = self.current_scale
            
            # キャッシュキーを作成
            model_cache_key = f"{method.name}_{scale}"
            
            # モデルがキャッシュにない場合は初期化を開始（ダイアログ表示あり）
            if model_cache_key not in self._sr_instances or self._sr_instances[model_cache_key] is None:
                self.initialize_model(method, scale, show_dialog=True)
        except Exception as e:
            print(f"モデル初期化確認中のエラー: {e}")
    
    def run_processing(self):
        """超解像処理を実行"""
        if not self.input_image_path:
            QMessageBox.warning(self, "警告", "まず画像を選択してください")
            return
            
        # モデル初期化中は処理を実行しない
        if self.is_model_initializing:
            QMessageBox.information(
                self,
                "初期化中",
                "モデルの初期化中です。初期化完了後に自動的に処理が実行されます。"
            )
            return
            
        # キャッシュキーを作成
        model_cache_key = f"{self.current_method.name}_{self.current_scale}"
        
        # モデルが初期化されていない場合は初期化してから実行
        if model_cache_key not in self._sr_instances or self._sr_instances[model_cache_key] is None:
            print(f"モデル {model_cache_key} が初期化されていないため、初期化を開始します")
            self.ensure_model_initialized()
            return
            
        # 処理中フラグを設定
        self.is_processing = True
        
        # UI状態を更新
        self.update_ui_state_for_processing(True)

        # 選択した手法とスケールを取得
        method = self.current_method
        scale = self.current_scale
        
        # メソッドを記憶
        self.last_method = method
        
        # キャッシュキーを作成
        model_cache_key = f"{method.name}_{scale}"
        
        # オプション設定
        options = self.prepare_options_for_method(method)
        print(f"処理オプション: {options}")
        
        # モデルが初期化されていない場合
        if model_cache_key not in self._sr_instances or self._sr_instances[model_cache_key] is None:
            # 初期化中でなければ初期化を開始
            if not self.is_model_initializing:
                QMessageBox.warning(
                    self, 
                    "モデル未初期化", 
                    "選択されたモデルが初期化されていません。\n"
                    "しばらく待ってから再試行してください。"
                )
                self.update_ui_state_for_processing(False)
                
                # モデル初期化を開始
                self.initialize_model(method, scale)
            return
        
        # ステータスバー更新
        self.statusBar().showMessage(f"処理中... {method} スケール {scale}x")
        
        # キャッシュからモデルインスタンスを取得
        sr_instance = self._sr_instances[model_cache_key]
        
        # スレッド実行
        self.processing_thread = ProcessingThread(
            self.input_image_path, 
            method, 
            scale, 
            options,
            sr_instance  # 既存のモデルインスタンスを渡す
        )
        self.processing_thread.update_progress.connect(self.update_progress)
        self.processing_thread.processing_finished.connect(self.processing_completed)
        self.processing_thread.processing_error.connect(self.processing_error)
        self.processing_thread.processing_cancelled.connect(self.processing_cancelled)
        self.processing_thread.start()
    
    def cancel_processing(self):
        """処理をキャンセルする"""
        if self.processing_thread and self.processing_thread.isRunning():
            # キャンセルボタンを無効化して連打防止
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("キャンセル中...")
            
            # ステータスバーの更新
            self.statusBar().showMessage("処理をキャンセル中...")
            
            # スレッドにキャンセル要求を送信
            self.processing_thread.cancel()
            
            # キャンセル要求後のUIは processing_cancelled シグナルで更新される
    
    def update_ui_state_for_processing(self, is_processing: bool):
        """処理中のUI状態を更新"""
        # 処理開始時
        if is_processing:
            # 実行ボタンを無効化
            self.run_button.setEnabled(False)
            # キャンセルボタンを有効化
            self.cancel_button.setEnabled(True)
            # プログレスバーをリセット
            self.progress_bar.setValue(0)
            # 各種設定項目を無効化
            self.toggle_view_button.setEnabled(False)
        # 処理終了時
        else:
            # 実行ボタンを有効化
            self.run_button.setEnabled(True)
            # キャンセルボタンを無効化
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("キャンセル")
            # 各種設定項目を有効化
            self.toggle_view_button.setEnabled(True)
            # 処理中フラグをクリア
            self.is_processing = False
    
    def update_progress(self, value):
        """進捗バーの更新"""
        self.progress_bar.setValue(value)
        
    def processing_completed(self, result: SRResult):
        """処理完了時のコールバック"""
        # 結果を保存
        self.output_image = result.image
        
        # 超解像画像をウィジェットに設定して表示を切り替え
        self.image_widget.set_sr_image(result.image)
        
        # 情報表示
        method_name = str(result.method).split('.')[-1]
        process_time = result.processing_time
        h, w = result.image.shape[:2]
        
        # ステータスバー更新
        self.statusBar().showMessage(f"処理完了: {method_name}, {w}x{h} ピクセル, 処理時間: {process_time:.1f}秒")
        
        # UIの状態を更新
        self.update_ui_state_for_processing(False)
        
        # プログレスバーを100%に
        self.progress_bar.setValue(100)
        
        # 切替ボタンを有効化
        self.toggle_view_button.setEnabled(True)
    
    def processing_error(self, error_message):
        """処理エラー時のコールバック"""
        QMessageBox.warning(self, "処理エラー", error_message)
        self.statusBar().showMessage("処理エラー")
        
        # UIの状態を更新
        self.update_ui_state_for_processing(False)
        self.progress_bar.setValue(0)
    
    def processing_cancelled(self):
        """処理キャンセル時のコールバック"""
        self.statusBar().showMessage("処理がキャンセルされました")
        
        # UIの状態を更新
        self.update_ui_state_for_processing(False)
        self.progress_bar.setValue(0)
    
    def update_gpu_status(self):
        """GPU状態の表示を更新"""
        if self.gpu_available:
            self.gpu_status_label.setText("GPU: 利用可能 (CUDA)")
            
            # デバイス情報の表示
            if self.cuda_devices:
                devices_text = "\n".join([f"- {dev}" for dev in self.cuda_devices])
                self.gpu_status_label.setToolTip(f"検出されたCUDAデバイス:\n{devices_text}")
        else:
            self.gpu_status_label.setText("GPU: 利用不可 (CPU処理)")
        
        # メモリ情報表示
        if self.vram_info:
            total_mb = self.vram_info['total'] / (1024 * 1024)  # MB単位
            used_mb = self.vram_info['used'] / (1024 * 1024)
            free_mb = self.vram_info['free'] / (1024 * 1024)
            self.memory_label.setText(f"VRAM: {free_mb:.0f}MB 利用可能 / {total_mb:.0f}MB")
            self.memory_label.setToolTip(f"総メモリ: {total_mb:.0f}MB\n使用中: {used_mb:.0f}MB\n空き: {free_mb:.0f}MB")
        else:
            self.memory_label.setText("VRAM: 情報なし")
    
    def delayed_resize(self):
        """リサイズ後の遅延処理"""
        # 画像ウィジェットのリサイズ
        if hasattr(self, 'image_widget'):
            self.image_widget.update_display()
    
    def closeEvent(self, event):
        """ウィンドウが閉じられる時のイベント"""
        # 処理スレッドが実行中ならキャンセル
        if self.processing_thread and self.processing_thread.isRunning():
            # キャンセル要求を送信
            self.processing_thread.cancel()
            # スレッドの終了を待機（最大1秒）
            if not self.processing_thread.wait(1000):
                # 1秒待っても終了しない場合は強制終了
                self.processing_thread.terminate()
                self.processing_thread.wait()
        
        # モデル初期化スレッドが実行中ならキャンセル
        if self.model_init_thread and self.model_init_thread.isRunning():
            self.model_init_thread.cancel()
            if not self.model_init_thread.wait(1000):
                self.model_init_thread.terminate()
                self.model_init_thread.wait()
        
        # 参照をクリア（明示的なリソース解放はSRMethodに任せる）
        self._sr_instances.clear()
        self.input_image = None
        self.output_image = None
        
        # スーパークラスのcloseEventを呼び出し
        super().closeEvent(event)

    def prepare_options_for_method(self, method: SRMethod) -> Dict[str, Any]:
        """指定されたメソッド用のオプションを準備する"""
        options = {}
        
        # グローバルオプション
        for key in ['tile', 'tile_pad']:
            if key in self.options:
                options[key] = self.options[key]
        
        # メソッド固有のオプションを取得
        method_key = method.name.lower()
        if method_key in self.options:
            method_options = self.options[method_key]
            if method_options:
                # RealESRGAN用のマッピング
                if method == SRMethod.REALESRGAN:
                    # バリアント設定
                    model_variant = method_options.get('realesrgan_model', 'デノイズ')
                    if model_variant == "デノイズ":
                        options['variant'] = 'denoise'
                    elif model_variant == "標準":
                        options['variant'] = 'standard'
                    elif model_variant == "アニメ向け":
                        options['variant'] = 'anime'
                    elif model_variant == "動画向け":
                        options['variant'] = 'video'
                    
                    # デノイズ強度
                    if 'denoise_strength' in method_options:
                        options['denoise_strength'] = method_options['denoise_strength']
                    
                    # 顔強調オプション
                    if 'face_enhance' in method_options:
                        options['face_enhance'] = method_options['face_enhance']
                        
                    # 半精度設定
                    if 'half_precision' in method_options:
                        options['half_precision'] = method_options['half_precision']
                
                # SwinIR用のオプション
                elif method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                               SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
                    # ウィンドウサイズ
                    if 'window_size' in method_options:
                        options['window_size'] = method_options['window_size']
                    
                    # JPEG圧縮アーティファクト対応
                    if 'jpeg_artifact' in method_options:
                        options['jpeg_artifact'] = method_options['jpeg_artifact']
                    
                    # 半精度設定
                    if 'half_precision' in method_options:
                        options['half_precision'] = method_options['half_precision']
                
                # OpenCV DNNモデル用のオプション
                elif method in [SRMethod.OPENCV_EDSR, SRMethod.OPENCV_ESPCN, 
                               SRMethod.OPENCV_FSRCNN, SRMethod.OPENCV_LAPSRN]:
                    # モデルタイプ
                    if 'model_type' in method_options:
                        options['model_type'] = method_options['model_type']
        
        # 初期化オプションを詳細に出力
        print(f"{method.name} 初期化オプション: {options}")
        return options


def run():
    """アプリケーションのエントリーポイント"""
    # OpenCVバージョン情報の表示
    print(f"OpenCVバージョン: {cv2.__version__}")
    
    app = QApplication(sys.argv)
    
    # スタイル設定
    app.setStyle("Fusion")
    
    # メインウィンドウの作成と表示
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())



