"""
超解像処理の設定ダイアログ
"""
import os
import sys
from typing import Dict, Any, List, Optional, Tuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QCheckBox, QTabWidget, QWidget,
    QDialogButtonBox, QGroupBox, QSlider, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from sr.sr_base import SRMethod


class SuperResolutionSettingsDialog(QDialog):
    """
    超解像処理の設定を統合したダイアログ
    """
    
    def __init__(self, parent=None, options: Dict[str, Any] = None, 
                 current_method: SRMethod = None, current_scale: int = 4):
        super().__init__(parent)
        self.setWindowTitle("超解像設定")
        self.resize(500, 600)
        
        self.options = options or {}
        self.current_method = current_method or SRMethod.REALESRGAN
        self.current_scale = current_scale
        
        # 初期化パラメータを確認するデバッグログ
        print(f"設定ダイアログの初期化: method={self.current_method.name}, scale={self.current_scale}")
        
        self.method_controls = {}
        
        self.setup_ui()
        self.connect_signals()
        
        # 初期メソッドに基づいてUIを更新
        self.update_ui_for_method(self.current_method)
    
    def setup_ui(self):
        """UIの初期化"""
        # メインレイアウト
        main_layout = QVBoxLayout(self)
        
        # タブウィジェット
        self.tab_widget = QTabWidget()
        
        # === 基本設定タブ ===
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        
        # メソッド選択グループ
        method_group = QGroupBox("超解像メソッド")
        method_layout = QFormLayout(method_group)
        
        # メソッド選択プルダウン
        self.method_combo = QComboBox()
        
        # 基本的なOpenCVメソッド
        self.method_combo.addItem("OpenCV Bicubic", SRMethod.OPENCV_CUBIC.value)
        self.method_combo.addItem("OpenCV Lanczos4", SRMethod.OPENCV_LANCZOS.value)
        
        # OpenCV DNN モデル
        self.method_combo.addItem("OpenCV ESPCN", SRMethod.OPENCV_ESPCN.value)
        self.method_combo.addItem("OpenCV FSRCNN", SRMethod.OPENCV_FSRCNN.value)
        self.method_combo.addItem("OpenCV EDSR", SRMethod.OPENCV_EDSR.value)
        self.method_combo.addItem("OpenCV LapSRN", SRMethod.OPENCV_LAPSRN.value)
        
        # SwinIRモデル
        self.method_combo.addItem("SwinIR 軽量モデル", SRMethod.SWINIR_LIGHTWEIGHT.value)
        self.method_combo.addItem("SwinIR 標準モデル", SRMethod.SWINIR_CLASSICAL.value)
        self.method_combo.addItem("SwinIR 実写向け", SRMethod.SWINIR_REAL.value)
        self.method_combo.addItem("SwinIR 高品質モデル", SRMethod.SWINIR_LARGE.value)
        
        # ESRGANモデル
        self.method_combo.addItem("Real-ESRGAN", SRMethod.REALESRGAN.value)
        
        # 現在のメソッドを選択
        for i in range(self.method_combo.count()):
            if self.method_combo.itemData(i) == self.current_method.value:
                self.method_combo.setCurrentIndex(i)
                break
                
        method_layout.addRow("超解像エンジン:", self.method_combo)
        
        # 拡大倍率
        self.scale_combo = QComboBox()
        # スケールの追加はメソッド選択に応じて動的に行うので、初期値は空
        method_layout.addRow("拡大倍率:", self.scale_combo)
        
        # 自動処理設定
        self.auto_process_checkbox = QCheckBox("画像読み込み時に自動処理")
        self.auto_process_checkbox.setChecked(self.options.get('auto_process', True))
        method_layout.addRow("", self.auto_process_checkbox)
        
        basic_layout.addWidget(method_group)
        
        # === 共通オプション ===
        common_group = QGroupBox("共通オプション")
        common_layout = QFormLayout(common_group)
        
        # タイル処理サイズ
        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 2048)
        self.tile_spin.setSingleStep(64)
        self.tile_spin.setValue(self.options.get('tile', 512))
        self.tile_spin.setSpecialValueText("無効")  # 0の場合は「無効」と表示
        common_layout.addRow("タイルサイズ:", self.tile_spin)
        
        # タイルパディング
        self.tile_pad_spin = QSpinBox()
        self.tile_pad_spin.setRange(0, 256)
        self.tile_pad_spin.setSingleStep(8)
        self.tile_pad_spin.setValue(self.options.get('tile_pad', 32))
        common_layout.addRow("タイルパディング:", self.tile_pad_spin)
        
        basic_layout.addWidget(common_group)
        
        # エンジン説明
        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        basic_layout.addWidget(self.help_label)
        
        # スペーサー
        basic_layout.addStretch()
        
        # === 詳細設定タブ ===
        advanced_tab = QWidget()
        self.advanced_layout = QVBoxLayout(advanced_tab)
        
        # メソッド固有のオプションコンテナ（動的に更新）
        self.method_options_group = QGroupBox("エンジン固有のオプション")
        self.method_options_layout = QFormLayout(self.method_options_group)
        self.advanced_layout.addWidget(self.method_options_group)
        
        # スペーサー
        self.advanced_layout.addStretch()
        
        # タブを追加
        self.tab_widget.addTab(basic_tab, "基本設定")
        self.tab_widget.addTab(advanced_tab, "詳細設定")
        
        main_layout.addWidget(self.tab_widget)
        
        # ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def connect_signals(self):
        """シグナル接続"""
        self.method_combo.currentIndexChanged.connect(self.on_method_changed)
        self.scale_combo.currentIndexChanged.connect(self.on_scale_changed)
    
    def on_method_changed(self, index):
        """メソッドが変更されたときの処理"""
        if index >= 0:
            method_value = self.method_combo.itemData(index)
            self.current_method = SRMethod(method_value)
            
            # 更新前のスケール値を保存
            previous_scale = self.current_scale
            print(f"メソッド変更前のスケール: {previous_scale}x")
            
            # UIを更新（保存したスケール値を維持しつつ）
            self.update_ui_for_method(self.current_method)
            
            print(f"メソッド変更後のスケール: {self.current_scale}x")
    
    def on_scale_changed(self, index):
        """スケールが変更されたときの処理"""
        if index >= 0:
            new_scale = self.scale_combo.itemData(index)
            old_scale = self.current_scale
            self.current_scale = new_scale
            print(f"スケール明示的変更: {old_scale}x → {new_scale}x")
            
            # RealESRGANの場合のスケール依存の警告表示
            if self.current_method == SRMethod.REALESRGAN and new_scale != 4:
                self.update_method_controls(self.current_method)
    
    def update_ui_for_method(self, method: SRMethod):
        """選択されたメソッドに合わせてUIを更新"""
        # スケールコンボボックスの更新
        self.update_scale_combo(method)
        
        # メソッド固有のコントロールを更新
        self.update_method_controls(method)
        
        # ヘルプテキストを更新
        self.update_help_text(method)
    
    def update_scale_combo(self, method: SRMethod):
        """メソッドがサポートするスケールでコンボボックスを更新"""
        self.scale_combo.clear()
        
        try:
            # サポートされるスケールを取得
            from sr.sr_utils import get_method_supported_scales
            supported_scales = get_method_supported_scales(method)
            
            # デバッグログ: 受け取ったスケール値と現在の設定値
            print(f"スケール設定: メソッド={method.name}, 現在のスケール={self.current_scale}, サポート済みスケール={supported_scales}")
            
            # シグナル一時停止（スケール変更イベントが誤発火しないように）
            self.scale_combo.blockSignals(True)
            
            # コンボボックスに追加
            for scale in supported_scales:
                self.scale_combo.addItem(f"{scale}x", scale)
            
            # 現在の設定値を確実に反映（シグナルブロック中）
            if supported_scales:
                # 現在のスケールがサポートされているか確認
                if self.current_scale in supported_scales:
                    # サポートされている場合、そのインデックスを選択
                    index = supported_scales.index(self.current_scale)
                    print(f"現在のスケール {self.current_scale}x をインデックス {index} に設定します")
                else:
                    # サポートされていない場合、デフォルト値を選択して現在の設定を更新
                    default_scale = 4 if 4 in supported_scales else supported_scales[0]
                    index = supported_scales.index(default_scale)
                    print(f"現在のスケール {self.current_scale}x はサポートされていないため、{default_scale}x に設定します")
                    self.current_scale = default_scale
                
                # コンボボックスのインデックスを設定
                self.scale_combo.setCurrentIndex(index)
                
                # シグナルブロック解除後にも選択インデックスを再度確認
                selected_scale = self.scale_combo.currentData()
                print(f"選択インデックス設定後のスケール: {selected_scale}x (インデックス: {index})")
            
            # シグナルブロック解除
            self.scale_combo.blockSignals(False)
            
        except Exception as e:
            print(f"スケール更新中のエラー: {e}")
            # エラー時の最小限の対応
            self.scale_combo.blockSignals(True)
            for scale in [2, 3, 4]:
                self.scale_combo.addItem(f"{scale}x", scale)
                if scale == self.current_scale:
                    self.scale_combo.setCurrentIndex(self.scale_combo.count() - 1)
            self.scale_combo.blockSignals(False)
    
    def update_method_controls(self, method: SRMethod):
        """メソッド固有のコントロールを更新"""
        # 既存のコントロールをクリア
        self.method_controls.clear()
        
        # レイアウト内の既存のウィジェットをクリア
        while self.method_options_layout.count():
            item = self.method_options_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # メソッドに固有のコントロールを追加
        method_key = method.name.lower()
        method_options = self.options.get(method_key, {})
        
        if method in [SRMethod.OPENCV_EDSR, SRMethod.OPENCV_ESPCN, 
                     SRMethod.OPENCV_FSRCNN, SRMethod.OPENCV_LAPSRN]:
            # OpenCV DNNモデルのオプション
            model_combo = QComboBox()
            if method == SRMethod.OPENCV_EDSR:
                model_combo.addItems(["標準", "軽量版"])
            elif method == SRMethod.OPENCV_FSRCNN:
                model_combo.addItems(["標準", "軽量版", "高速版"])
            else:
                model_combo.addItem("標準")
            
            model_combo.setCurrentText(method_options.get('model_type', "標準"))
            self.method_options_layout.addRow("モデルタイプ:", model_combo)
            self.method_controls['model_type'] = model_combo
            
        elif method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                        SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
            # SwinIRオプション
            window_size_spin = QSpinBox()
            window_size_spin.setRange(4, 16)
            window_size_spin.setSingleStep(4)
            window_size_spin.setValue(method_options.get('window_size', 8))
            self.method_options_layout.addRow("ウィンドウサイズ:", window_size_spin)
            self.method_controls['window_size'] = window_size_spin
            
            # JPEG圧縮アーティファクト対応（SwinIR CLASSICのみ）
            if method == SRMethod.SWINIR_CLASSICAL:
                jpeg_check = QCheckBox("有効")
                jpeg_check.setChecked(method_options.get('jpeg_artifact', False))
                self.method_options_layout.addRow("JPEG圧縮対応:", jpeg_check)
                self.method_controls['jpeg_artifact'] = jpeg_check
            
        elif method == SRMethod.REALESRGAN:
            # RealESRGANオプション
            model_combo = QComboBox()
            model_combo.addItems(["デノイズ", "標準", "アニメ向け", "動画向け"])
            # 現在の設定値をロード（デフォルトはデノイズ）
            model_combo.setCurrentText(method_options.get('realesrgan_model', "デノイズ"))
            self.method_options_layout.addRow("モデルタイプ:", model_combo)
            self.method_controls['realesrgan_model'] = model_combo
            
            # RealESRGANの制約に関する注意
            if self.current_scale != 4:
                scale_warning = QLabel("※ RealESRGANは構造上4x用に設計されています。他のスケールで問題が発生する可能性があります。")
                scale_warning.setStyleSheet("QLabel { color: #c00; font-weight: bold; font-size: 10px; }")
                self.method_options_layout.addRow("", scale_warning)
            
            # 注: 半精度と顔強調の互換性警告は削除（テスト済みで問題ないため）
            
            # デノイズ強度
            denoise_layout = QHBoxLayout()
            denoise_slider = QSlider(Qt.Horizontal)
            denoise_slider.setRange(0, 100)
            # 現在の設定値をロード（デフォルトは0.5）
            denoise_value = method_options.get('denoise_strength', 0.5)
            denoise_slider.setValue(int(denoise_value * 100))
            
            denoise_label = QLabel(f"{denoise_value:.2f}")
            denoise_slider.valueChanged.connect(
                lambda v: denoise_label.setText(f"{v/100:.2f}")
            )
            
            denoise_layout.addWidget(denoise_slider)
            denoise_layout.addWidget(denoise_label)
            
            self.method_options_layout.addRow("デノイズ強度:", denoise_layout)
            self.method_controls['denoise_strength'] = denoise_slider
            
            # 顔強調
            face_enhance = QCheckBox("有効")
            # 現在の設定値をロード（デフォルトはFalse）
            face_enhance.setChecked(method_options.get('face_enhance', False))
            self.method_options_layout.addRow("顔強調:", face_enhance)
            self.method_controls['face_enhance'] = face_enhance
            
            # デバッグログ出力（設定の初期値を確認）
            print(f"RealESRGAN設定値のロード - モデル: {method_options.get('realesrgan_model', 'デノイズ')}, "
                  f"デノイズ強度: {denoise_value}, 顔強調: {method_options.get('face_enhance', False)}")
        
        # 半精度処理オプション（サポート時のみ）
        try:
            from sr.sr_utils import supports_half_precision
            if supports_half_precision(method):
                half_precision_check = QCheckBox("有効")
                half_precision_check.setChecked(method_options.get('half_precision', True))
                self.method_options_layout.addRow("半精度処理 (FP16):", half_precision_check)
                self.method_controls['half_precision'] = half_precision_check
        except ImportError:
            pass
    
    def update_help_text(self, method: SRMethod):
        """ヘルプテキストを更新"""
        help_texts = {
            SRMethod.OPENCV_EDSR: "EDSRは残差ブロックを多用した畳み込みニューラルネットワークです。高精度ですが計算コストが高めです。",
            SRMethod.OPENCV_ESPCN: "ESPCNはピクセルシャッフル層を使用した効率的な超解像モデルです。軽量で比較的高速です。",
            SRMethod.OPENCV_FSRCNN: "FSRCNNはESPCNの改良版で、より少ないパラメータ数で高速に動作します。",
            SRMethod.OPENCV_LAPSRN: "LapSRNはラプラシアンピラミッド構造を使用したモデルで、段階的に解像度を向上させます。",
            SRMethod.SWINIR_LIGHTWEIGHT: "SwinIR軽量モデルは、ビジョントランスフォーマーを使った高効率な超解像モデルです。",
            SRMethod.SWINIR_REAL: "SwinIR実写向けモデルは、実写画像の質感を保ちながら拡大します。",
            SRMethod.SWINIR_LARGE: "SwinIR高品質モデルは最高品質ですが、処理に時間と高いGPUメモリを要します。",
            SRMethod.SWINIR_CLASSICAL: "SwinIR標準モデルは、バランスの良い性能で一般的な画像に適しています。",
            SRMethod.REALESRGAN: "RealESRGANは実写画像のノイズやぼけを修正しながら超解像する優れたモデルです。顔強調機能もサポートしています。",
            SRMethod.OPENCV_NEAREST: "最近傍補間は最も単純な拡大方法で、処理は高速ですがブロックノイズが発生します。",
            SRMethod.OPENCV_BILINEAR: "バイリニア補間は滑らかな拡大を実現しますが、細部がぼやけます。",
            SRMethod.OPENCV_CUBIC: "バイキュービック補間はバイリニアよりも鮮明さを保持しますが、オーバーシュートが発生することがあります。",
            SRMethod.OPENCV_LANCZOS: "Lanczos補間は高品質な補間方法で、エッジをよく保存しますが計算コストが高めです。"
        }
        
        self.help_label.setText(help_texts.get(method, "このエンジンの説明はありません。"))
    
    def get_settings(self) -> Dict[str, Any]:
        """ダイアログの設定を取得"""
        settings = {}
        
        # 基本設定
        settings['method'] = self.current_method
        settings['scale'] = self.current_scale
        settings['auto_process'] = self.auto_process_checkbox.isChecked()
        
        # 設定内容をデバッグ出力
        print(f"設定ダイアログの結果: メソッド={self.current_method.name}, スケール={self.current_scale}, "
              f"自動処理={self.auto_process_checkbox.isChecked()}")
        
        # 共通オプション
        settings['tile'] = self.tile_spin.value()
        settings['tile_pad'] = self.tile_pad_spin.value()
        
        # メソッド固有のオプション
        method_key = self.current_method.name.lower()
        if method_key not in self.options:
            self.options[method_key] = {}
            
        method_options = {}
        
        # コントロールからオプションを取得
        for key, control in self.method_controls.items():
            if isinstance(control, QComboBox):
                method_options[key] = control.currentText()
            elif isinstance(control, QCheckBox):
                method_options[key] = control.isChecked()
            elif isinstance(control, QSpinBox) or isinstance(control, QDoubleSpinBox):
                method_options[key] = control.value()
            elif isinstance(control, QSlider) and key == 'denoise_strength':
                method_options[key] = control.value() / 100.0
        
        # メソッド固有オプションの内容をデバッグ出力
        print(f"メソッド固有オプション {method_key}: {method_options}")
        
        # options辞書を更新
        for key, value in method_options.items():
            self.options[method_key][key] = value
            
        settings['options'] = self.options
        
        # 特定のメソッドに対する警告（RealESRGANの場合）
        if self.current_method == SRMethod.REALESRGAN and self.current_scale != 4:
            print(f"警告: RealESRGANを{self.current_scale}xスケールで使用します。問題が発生する可能性があります。")
        
        return settings
