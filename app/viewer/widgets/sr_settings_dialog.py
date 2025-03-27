"""
超解像処理の設定ダイアログ
"""
import os
import sys
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, 
    QTabWidget, QWidget, QFormLayout, QGroupBox, 
    QDialogButtonBox, QMessageBox, QSlider
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon

from sr.sr_base import SRMethod
from app.viewer.superres import SuperResolutionManager
from app.viewer.superres.sr_enhanced import EnhancedSRManager


class SuperResolutionSettingsDialog(QDialog):
    """超解像処理の設定ダイアログ"""
    
    def __init__(self, parent=None, options: Dict[str, Any] = None, 
                 current_method: SRMethod = None, current_scale: int = 2,
                 sr_manager: EnhancedSRManager = None):
        super().__init__(parent)
        
        self.setWindowTitle("超解像処理設定")
        self.setMinimumWidth(500)
        
        # 現在の設定値を保存
        self.options = options or {}
        self.current_method = current_method or SRMethod.REALESRGAN
        self.current_scale = current_scale or 2
        
        # 超解像処理マネージャーの参照を保存
        self.sr_manager = sr_manager
        
        # 自動処理設定をマネージャから取得（マネージャがある場合）
        if self.sr_manager and hasattr(self.sr_manager, 'auto_process'):
            self.auto_process = self.sr_manager.auto_process
        else:
            self.auto_process = True  # デフォルト値
        
        # メソッドの利用可能性を確認
        self.available_methods = self.get_production_methods()
        
        # UIの構築
        self.setup_ui()
        
        # 初期値を設定
        self.set_initial_values()
    
    def get_production_methods(self) -> List[SRMethod]:
        """
        実運用に適した超解像メソッドのリストを取得
        (OpenCVメソッドを除外)
        """
        # EnhancedSRManagerが利用可能であればそちらから取得
        if self.sr_manager:
            return self.sr_manager.get_production_methods()
        
        # 従来のコード（フォールバック）
        all_methods = SuperResolutionManager.get_available_methods()
        production_methods = []
        
        # OpenCV以外のメソッドを抽出
        for method in all_methods:
            method_name = method.name.lower()
            if not method_name.startswith('opencv'):
                production_methods.append(method)
        
        return production_methods
    
    def setup_ui(self):
        """UIコンポーネントの設定"""
        main_layout = QVBoxLayout(self)
        
        # タブウィジェット
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 基本設定タブ
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        
        # メソッド選択グループ
        method_group = QGroupBox("拡大メソッド")
        method_layout = QFormLayout(method_group)
        
        # メソッド選択コンボボックス
        self.method_combo = QComboBox()
        self.populate_method_combo()
        self.method_combo.currentIndexChanged.connect(self.on_method_changed)
        method_layout.addRow("拡大エンジン:", self.method_combo)
        
        # スケール選択コンボボックス
        self.scale_combo = QComboBox()
        self.populate_scale_combo()
        method_layout.addRow("拡大倍率:", self.scale_combo)
        
        basic_layout.addWidget(method_group)
        
        # 処理設定グループ
        process_group = QGroupBox("処理設定")
        process_layout = QFormLayout(process_group)
        
        # タイルサイズ設定（画像が大きい場合のメモリ使用量を削減）
        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 1024)
        self.tile_spin.setSingleStep(64)
        self.tile_spin.setSpecialValueText("タイル無し") # 0の場合の表示
        self.tile_spin.setToolTip("大きな画像を小さなタイルに分割して処理します。0=タイル処理なし")
        process_layout.addRow("タイルサイズ:", self.tile_spin)
        
        # 自動処理チェックボックス
        self.auto_process_check = QCheckBox("有効")
        self.auto_process_check.setToolTip("画像読み込み後や設定変更後に自動的に処理を実行します")
        process_layout.addRow("自動処理:", self.auto_process_check)
        
        basic_layout.addWidget(process_group)
        
        # GPU情報グループ
        gpu_group = QGroupBox("GPU情報")
        gpu_layout = QFormLayout(gpu_group)
        
        # CUDA利用可能状態
        cuda_available = self._is_cuda_available()
        self.cuda_label = QLabel("利用可能" if cuda_available else "利用不可")
        gpu_layout.addRow("CUDA:", self.cuda_label)
        
        # GPU情報
        gpu_info = self._get_gpu_info()
        if gpu_info:
            gpu_name = gpu_info.get("name", "不明")
            vram_total = gpu_info.get("total_memory", 0) / (1024 * 1024) # MB単位
            self.gpu_label = QLabel(f"{gpu_name} ({vram_total:.0f} MB)")
        else:
            self.gpu_label = QLabel("情報なし")
        gpu_layout.addRow("GPU:", self.gpu_label)
        
        basic_layout.addWidget(gpu_group)
        
        # タブにウィジェットを追加
        self.tab_widget.addTab(basic_tab, "基本設定")
        
        # モデル固有のタブを追加
        self.add_realesrgan_tab()
        self.add_swinir_tab()
        
        # スペーサー
        basic_layout.addStretch()
        
        # OKとキャンセルボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def _is_cuda_available(self) -> bool:
        """CUDAが利用可能かどうか確認"""
        if self.sr_manager:
            return self.sr_manager.is_cuda_available()
        return SuperResolutionManager.is_cuda_available()
    
    def _get_gpu_info(self) -> Dict[str, Any]:
        """GPU情報を取得"""
        if self.sr_manager:
            return self.sr_manager.get_gpu_info()
        return SuperResolutionManager.get_gpu_info()
    
    def populate_method_combo(self):
        """メソッド選択コンボボックスの初期化"""
        # コンボボックスをクリア
        self.method_combo.clear()
        
        # メソッドの表示名とオプション
        method_display_names = {
            SRMethod.SWINIR_LIGHTWEIGHT: "SwinIR 軽量モデル",
            SRMethod.SWINIR_REAL: "SwinIR 実写向け",
            SRMethod.SWINIR_LARGE: "SwinIR 高品質モデル",
            SRMethod.SWINIR_CLASSICAL: "SwinIR 標準モデル",
            SRMethod.REALESRGAN: "Real-ESRGAN"
        }
        
        # 選択可能なメソッドの優先順位
        preferred_methods = [
            SRMethod.REALESRGAN,
            SRMethod.SWINIR_REAL,
            SRMethod.SWINIR_LIGHTWEIGHT
        ]
        
        # 優先順位に基づいて追加
        for method in preferred_methods:
            if method in self.available_methods:
                name = method_display_names.get(method, method.name)
                self.method_combo.addItem(name, method)
        
        # 残りのメソッドを追加
        for method in self.available_methods:
            if method not in preferred_methods:
                name = method_display_names.get(method, method.name)
                self.method_combo.addItem(name, method)
    
    def populate_scale_combo(self):
        """スケール選択コンボボックスの初期化"""
        # コンボボックスをクリア
        self.scale_combo.clear()
        
        # 現在選択されているメソッドに対応するスケールを取得
        method = self.get_current_method()
        if method:
            supported_scales = self._get_supported_scales(method)
            
            # サポートされているスケールがない場合はデフォルト値を設定
            if not supported_scales:
                supported_scales = [2, 3, 4]
                
            # スケールオプションを追加
            for scale in supported_scales:
                self.scale_combo.addItem(f"{scale}倍", scale)
    
    def _get_supported_scales(self, method: SRMethod) -> List[int]:
        """指定したメソッドでサポートされるスケールのリストを取得"""
        if self.sr_manager:
            return self.sr_manager.get_supported_scales(method)
        return SuperResolutionManager.get_supported_scales(method)
    
    def get_current_method(self) -> Optional[SRMethod]:
        """現在選択されているメソッドを取得"""
        index = self.method_combo.currentIndex()
        if index >= 0:
            return self.method_combo.itemData(index)
        return None
    
    def on_method_changed(self, index):
        """メソッド変更時のイベントハンドラ"""
        if index >= 0:
            # 選択されたメソッドに対応するスケールオプションを更新
            self.populate_scale_combo()
            
            # 対応するタブを表示/隠す
            method = self.get_current_method()
            if method:
                # RealESRGANタブの表示/非表示
                realesrgan_tab_index = self.tab_widget.indexOf(self.realesrgan_tab)
                if method == SRMethod.REALESRGAN:
                    if realesrgan_tab_index == -1:  # タブが存在しない場合
                        self.tab_widget.addTab(self.realesrgan_tab, "Real-ESRGAN")
                else:
                    if realesrgan_tab_index != -1:  # タブが存在する場合
                        self.tab_widget.removeTab(realesrgan_tab_index)
                
                # SwinIRタブの表示/非表示
                swinir_tab_index = self.tab_widget.indexOf(self.swinir_tab)
                if method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                             SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
                    if swinir_tab_index == -1:  # タブが存在しない場合
                        self.tab_widget.addTab(self.swinir_tab, "SwinIR")
                else:
                    if swinir_tab_index != -1:  # タブが存在する場合
                        self.tab_widget.removeTab(swinir_tab_index)
    
    def add_realesrgan_tab(self):
        """Real-ESRGAN設定タブの追加"""
        self.realesrgan_tab = QWidget()
        realesrgan_layout = QVBoxLayout(self.realesrgan_tab)
        
        # モデル選択グループ
        model_group = QGroupBox("モデル設定")
        model_layout = QFormLayout(model_group)
        
        # モデルタイプの選択
        self.realesrgan_model_combo = QComboBox()
        self.realesrgan_model_combo.addItem("デノイズ (推奨)", "denoise")
        self.realesrgan_model_combo.addItem("標準", "standard")
        self.realesrgan_model_combo.addItem("アニメ向け", "anime")
        self.realesrgan_model_combo.setToolTip("モデルタイプによって結果の見た目が変わります")
        model_layout.addRow("モデルタイプ:", self.realesrgan_model_combo)
        
        # デノイズ強度
        denoise_layout = QHBoxLayout()
        self.denoise_slider = QSlider(Qt.Horizontal)
        self.denoise_slider.setRange(0, 100)
        self.denoise_slider.setValue(50)  # デフォルト値
        self.denoise_slider.setToolTip("デノイズの適用強度 (0=無効, 1=最大)")
        
        self.denoise_value_label = QLabel("0.50")
        self.denoise_slider.valueChanged.connect(
            lambda v: self.denoise_value_label.setText(f"{v/100:.2f}")
        )
        
        denoise_layout.addWidget(self.denoise_slider)
        denoise_layout.addWidget(self.denoise_value_label)
        model_layout.addRow("デノイズ強度:", denoise_layout)
        
        # 顔強調オプション
        self.face_enhance_check = QCheckBox("有効")
        self.face_enhance_check.setToolTip("顔の部分を検出して品質を向上させます（処理が遅くなります）")
        model_layout.addRow("顔強調:", self.face_enhance_check)
        
        # 半精度オプション
        self.half_precision_check = QCheckBox("有効")
        self.half_precision_check.setToolTip("メモリ使用量を削減しますが、わずかに品質が低下する場合があります")
        model_layout.addRow("半精度処理:", self.half_precision_check)
        
        realesrgan_layout.addWidget(model_group)
        
        # スペーサー
        realesrgan_layout.addStretch()
    
    def add_swinir_tab(self):
        """SwinIR設定タブの追加"""
        self.swinir_tab = QWidget()
        swinir_layout = QVBoxLayout(self.swinir_tab)
        
        # モデル設定グループ
        model_group = QGroupBox("モデル設定")
        model_layout = QFormLayout(model_group)
        
        # ウィンドウサイズ設定
        self.window_size_combo = QComboBox()
        self.window_size_combo.addItem("8 (推奨)", 8)
        self.window_size_combo.addItem("16 (高品質/低速)", 16)
        self.window_size_combo.addItem("4 (低品質/高速)", 4)
        self.window_size_combo.setToolTip("ウィンドウサイズが大きいほど高品質になりますが、処理時間とメモリ使用量が増えます")
        model_layout.addRow("ウィンドウサイズ:", self.window_size_combo)
                      
        swinir_layout.addWidget(model_group)
        
        # スペーサー
        swinir_layout.addStretch()
    
    def set_initial_values(self):
        """現在の設定値を各UIコンポーネントに設定"""
        # メソッド選択の初期値
        current_method_found = False
        for i in range(self.method_combo.count()):
            if self.method_combo.itemData(i) == self.current_method:
                self.method_combo.setCurrentIndex(i)
                current_method_found = True
                break
        
        # 現在のメソッドが見つからない場合（OpenCVメソッドなど）は最初の項目を選択
        if not current_method_found and self.method_combo.count() > 0:
            self.method_combo.setCurrentIndex(0)
        
        # メソッドが変更された場合のイベントをトリガー
        self.on_method_changed(self.method_combo.currentIndex())
        
        # スケール選択の初期値
        for i in range(self.scale_combo.count()):
            if self.scale_combo.itemData(i) == self.current_scale:
                self.scale_combo.setCurrentIndex(i)
                break
        
        # 自動処理の初期値
        # マネージャから読み取った値を優先する
        self.auto_process_check.setChecked(self.auto_process)
        
        # メソッド固有の設定を取得
        current_method = self.get_current_method()
        method_options = {}
        
        # マネージャーから_get_processed_optionsを使用してメソッド固有のデフォルト設定を取得
        if self.sr_manager and hasattr(self.sr_manager, '_get_processed_options'):
            try:
                # 現在のメソッドとオプションを取得
                current_method = self.sr_manager._method if hasattr(self.sr_manager, '_method') else None
                # 直接内部変数を参照せず、メソッドを通じて処理済みオプションを取得
                method_options = self.sr_manager._get_processed_options(current_method, None)
                
                # ここでmethod_optionsを使用してUI要素を更新
                # ...existing code...
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"設定の初期化中にエラーが発生しました: {e}")
        
        # オプションの優先順位: 1. method_options(デフォルト値) 2. self.options(引数)
        
        # タイルサイズの初期値（全メソッド共通）
        tile_size = method_options.get('tile', self.options.get('tile', 512))
        self.tile_spin.setValue(tile_size)
        
        # RealESRGAN設定
        if current_method == SRMethod.REALESRGAN:
            # バリアント
            variant = method_options.get('variant', self.options.get('variant', 'denoise'))
            variant_map = {'denoise': 0, 'standard': 1, 'anime': 2}
            self.realesrgan_model_combo.setCurrentIndex(variant_map.get(variant, 0))
            
            # デノイズ強度
            denoise_strength = method_options.get('denoise_strength', self.options.get('denoise_strength', 0.5))
            self.denoise_slider.setValue(int(denoise_strength * 100))
            
            # 顔強調
            face_enhance = method_options.get('face_enhance', self.options.get('face_enhance', False))
            self.face_enhance_check.setChecked(face_enhance)
            
            # 半精度処理
            half_precision = method_options.get('half_precision', self.options.get('half_precision', False))
            self.half_precision_check.setChecked(half_precision)
            
        # SwinIR設定
        elif current_method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                               SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
            # ウィンドウサイズ
            window_size = method_options.get('window_size', self.options.get('window_size', 8))
            window_size_index = 0
            if window_size == 16:
                window_size_index = 1
            elif window_size == 4:
                window_size_index = 2
            self.window_size_combo.setCurrentIndex(window_size_index)
            
    
    def get_settings(self) -> Dict[str, Any]:
        """ダイアログから設定を取得"""
        result = {}
        
        # メソッドとスケール
        method = self.get_current_method()
        if method:
            result['method'] = method
        
        # スケール
        scale_index = self.scale_combo.currentIndex()
        if scale_index >= 0:
            result['scale'] = self.scale_combo.itemData(scale_index)
        
        # 自動処理設定
        result['auto_process'] = self.auto_process_check.isChecked()
        
        # 処理オプション
        options = {}
        
        # タイルサイズ
        options['tile'] = self.tile_spin.value()
        options['tile_pad'] = 32  # デフォルト値
        
        # メソッド固有のオプション
        if method:
            # RealESRGANオプション
            if method == SRMethod.REALESRGAN:
                realesrgan_options = {}
                
                # モデルタイプ
                model_index = self.realesrgan_model_combo.currentIndex()
                model_value = self.realesrgan_model_combo.itemData(model_index)
                
                # variantオプションをトップレベルに設定
                options['variant'] = model_value
                
                # デノイズ強度
                options['denoise_strength'] = self.denoise_slider.value() / 100.0
                
                # 顔強調
                options['face_enhance'] = self.face_enhance_check.isChecked()
                
                # 半精度処理
                options['half_precision'] = self.half_precision_check.isChecked()
                
                # RealESRGAN固有オプションをサブディクショナリに保存
                realesrgan_options['realesrgan_model'] = self.realesrgan_model_combo.currentText()
                realesrgan_options['denoise_strength'] = self.denoise_slider.value() / 100.0
                realesrgan_options['face_enhance'] = self.face_enhance_check.isChecked()
                realesrgan_options['half_precision'] = self.half_precision_check.isChecked()
                
                options['realesrgan'] = realesrgan_options
            
            # SwinIRオプション
            elif method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                          SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
                swinir_options = {}
                
                # ウィンドウサイズ
                window_index = self.window_size_combo.currentIndex()
                window_value = self.window_size_combo.itemData(window_index)
                options['window_size'] = window_value
                
                
                # SwinIR固有オプションをサブディクショナリに保存
                swinir_options['window_size'] = window_value
                
                options['swinir'] = swinir_options
        
        result['options'] = options
        
        return result
