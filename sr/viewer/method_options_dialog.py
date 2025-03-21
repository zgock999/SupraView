"""
超解像メソッドごとの固有オプション設定ダイアログ
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QCheckBox, QTabWidget, QWidget,
    QDialogButtonBox, QGroupBox, QSlider
)
from PySide6.QtCore import Qt, Signal
from typing import Dict, Any, Optional, List
from sr.sr_base import SRMethod

class MethodOptionsDialog(QDialog):
    """
    超解像メソッドごとの固有オプション設定ダイアログ
    """
    options_changed = Signal(dict)
    
    def __init__(self, parent=None, method: SRMethod = None, options: Dict[str, Any] = None):
        super().__init__(parent)
        self.setWindowTitle("超解像メソッドオプション")
        self.resize(450, 400)
        
        self.method = method
        self.options = options or {}
        self.setup_ui()
        
    def setup_ui(self):
        """UIの初期化"""
        # メインレイアウト
        main_layout = QVBoxLayout(self)
        
        # メソッド固有オプションの表示
        if self.method:
            self.method_group = QGroupBox(f"{self.method.name} のオプション")
            self.method_layout = QVBoxLayout(self.method_group)
            
            # メソッドに応じたコントロールを追加
            self.add_method_specific_controls()
            
            main_layout.addWidget(self.method_group)
        else:
            # メソッドが指定されていない場合のメッセージ
            lbl = QLabel("メソッドが選択されていません")
            lbl.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(lbl)
        
        # 共通オプション
        self.common_group = QGroupBox("共通オプション")
        self.common_layout = QFormLayout(self.common_group)
        
        # タイル処理サイズ
        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 2048)
        self.tile_spin.setSingleStep(64)
        self.tile_spin.setValue(self.options.get('tile', 512))
        self.tile_spin.setSpecialValueText("無効")  # 0の場合は「無効」と表示
        self.common_layout.addRow("タイルサイズ:", self.tile_spin)
        
        # タイルパディング
        self.tile_pad_spin = QSpinBox()
        self.tile_pad_spin.setRange(0, 256)
        self.tile_pad_spin.setSingleStep(8)
        self.tile_pad_spin.setValue(self.options.get('tile_pad', 32))
        self.common_layout.addRow("タイルパディング:", self.tile_pad_spin)
        
        main_layout.addWidget(self.common_group)
        
        # 説明テキスト
        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        self.update_help_text()
        
        main_layout.addWidget(self.help_label)
        
        # スペーサー
        main_layout.addStretch()
        
        # ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        button_box.accepted.connect(self.accept_and_emit)
        button_box.rejected.connect(self.reject)
        reset_button = button_box.button(QDialogButtonBox.Reset)
        reset_button.clicked.connect(self.reset_options)
        
        main_layout.addWidget(button_box)
    
    def add_method_specific_controls(self):
        """メソッドに固有のコントロールを追加"""
        form_layout = QFormLayout()
        self.method_controls = {}
        
        if self.method is None:
            return
            
        # OpenCV DNN系のオプション
        if self.method in [SRMethod.OPENCV_EDSR, SRMethod.OPENCV_ESPCN, 
                           SRMethod.OPENCV_FSRCNN, SRMethod.OPENCV_LAPSRN]:
            # モデルタイプ
            model_combo = QComboBox()
            if self.method == SRMethod.OPENCV_EDSR:
                model_combo.addItems(["標準", "軽量版"])
            elif self.method == SRMethod.OPENCV_FSRCNN:
                model_combo.addItems(["標準", "軽量版", "高速版"])
            model_combo.setCurrentText(self.options.get('model_type', "標準"))
            form_layout.addRow("モデルタイプ:", model_combo)
            self.method_controls['model_type'] = model_combo
            
        # SwinIR系のオプション
        elif self.method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                            SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
            # ウィンドウサイズ
            window_size_spin = QSpinBox()
            window_size_spin.setRange(4, 16)
            window_size_spin.setSingleStep(4)
            window_size_spin.setValue(self.options.get('window_size', 8))
            form_layout.addRow("ウィンドウサイズ:", window_size_spin)
            self.method_controls['window_size'] = window_size_spin
            
            # JPEG圧縮アーティファクト対応（SwinIR CLASSICのみ）
            if self.method == SRMethod.SWINIR_CLASSICAL:
                jpeg_check = QCheckBox("有効")
                jpeg_check.setChecked(self.options.get('jpeg_artifact', False))
                form_layout.addRow("JPEG圧縮対応:", jpeg_check)
                self.method_controls['jpeg_artifact'] = jpeg_check
            
            # 半精度処理のオプションをSwinIRから削除 (FP16非対応のため)
            # 半精度処理チェックボックスのコードをここから削除
            
        # Real-ESRGAN 関連のオプション
        elif self.method == SRMethod.REALESRGAN:
            # メソッド固有のオプションを取得
            method_key = self.method.name.lower()
            method_options = self.options.get(method_key, {})
            
            # モデルタイプ
            model_combo = QComboBox()
            model_combo.addItems(["デノイズ", "標準", "アニメ向け", "動画向け"])
            
            # 保存されているバリアント設定を反映
            saved_variant = method_options.get('realesrgan_model', "デノイズ")
            model_combo.setCurrentText(saved_variant)
            
            form_layout.addRow("モデルタイプ:", model_combo)
            self.method_controls['realesrgan_model'] = model_combo
            print(f"バリアント設定を読み込み: {saved_variant}")
            
            # デノイズ強度（スライダー）
            denoise_layout = QHBoxLayout()
            denoise_slider = QSlider(Qt.Horizontal)
            denoise_slider.setRange(0, 100)
            
            # 保存されているデノイズ強度を反映
            saved_denoise = method_options.get('denoise_strength', 0.5)
            denoise_slider.setValue(int(saved_denoise * 100))
            
            denoise_value = QLabel(f"{saved_denoise:.2f}")
            denoise_slider.valueChanged.connect(
                lambda v: denoise_value.setText(f"{v/100:.2f}")
            )
            
            denoise_layout.addWidget(denoise_slider)
            denoise_layout.addWidget(denoise_value)
            
            form_layout.addRow("デノイズ強度:", denoise_layout)
            self.method_controls['denoise_strength'] = denoise_slider
            print(f"デノイズ強度を読み込み: {saved_denoise}")
            
            # 顔強調
            face_enhance = QCheckBox("有効")
            face_enhance.setChecked(method_options.get('face_enhance', False))
            form_layout.addRow("顔強調:", face_enhance)
            self.method_controls['face_enhance'] = face_enhance
            
        # sr_utils.supports_half_precisionで確認してから表示
        from sr.sr_utils import supports_half_precision
        if supports_half_precision(self.method):
            half_precision_check = QCheckBox("有効")
            half_precision_check.setChecked(method_options.get('half_precision', True))
            form_layout.addRow("半精度処理 (FP16):", half_precision_check)
            self.method_controls['half_precision'] = half_precision_check
        
        self.method_layout.addLayout(form_layout)
        
    def update_help_text(self):
        """ヘルプテキストを更新"""
        if self.method is None:
            self.help_label.setText("")
            return
            
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
        
        self.help_label.setText(help_texts.get(self.method, "このメソッドの説明はありません。"))
        
    def accept_and_emit(self):
        """設定を保存してシグナルを発行"""
        # オプションを保存
        new_options = {}
        
        # 共通オプション
        new_options['tile'] = self.tile_spin.value()
        new_options['tile_pad'] = self.tile_pad_spin.value()
        
        # メソッド固有のオプション
        if self.method and hasattr(self, 'method_controls'):
            for key, control in self.method_controls.items():
                if isinstance(control, QComboBox):
                    new_options[key] = control.currentText()
                elif isinstance(control, QCheckBox):
                    new_options[key] = control.isChecked()
                elif isinstance(control, QSpinBox) or isinstance(control, QDoubleSpinBox):
                    new_options[key] = control.value()
                elif isinstance(control, QSlider) and key == 'denoise_strength':
                    # スライダーの値を0〜1の範囲に変換
                    new_options[key] = control.value() / 100.0
        
        # デバッグ出力
        print(f"保存されるオプション: {new_options}")
        
        # シグナルを発行して変更を通知
        self.options_changed.emit(new_options)
        self.accept()
        
    def save_options(self):
        """現在のUI状態からオプションを保存"""
        # 共通オプション
        self.options['tile'] = self.tile_spin.value()
        self.options['tile_pad'] = self.tile_pad_spin.value()
        
        # メソッド固有のオプション
        if self.method and hasattr(self, 'method_controls'):
            for key, control in self.method_controls.items():
                if isinstance(control, QComboBox):
                    self.options[key] = control.currentText()
                elif isinstance(control, QCheckBox):
                    self.options[key] = control.isChecked()
                elif isinstance(control, QSpinBox) or isinstance(control, QDoubleSpinBox):
                    self.options[key] = control.value()
                elif isinstance(control, QSlider) and key == 'denoise_strength':
                    # スライダーの値を0〜1の範囲に変換
                    self.options[key] = control.value() / 100.0
    
    def reset_options(self):
        """オプションをデフォルト値にリセット"""
        # デフォルト値の設定
        defaults = {
            'tile': 512,
            'tile_pad': 32,
            'model_type': '標準',
            'window_size': 8,
            'jpeg_artifact': False,
            'half_precision': True,
            'realesrgan_model': 'デノイズ',  # デフォルトをデノイズに変更
            'denoise_strength': 0.5,
            'face_enhance': False
        }
        
        # UIの更新
        self.tile_spin.setValue(defaults['tile'])
        self.tile_pad_spin.setValue(defaults['tile_pad'])
        
        if hasattr(self, 'method_controls'):
            for key, control in self.method_controls.items():
                if key in defaults:
                    if isinstance(control, QComboBox):
                        index = control.findText(defaults[key])
                        if index >= 0:
                            control.setCurrentIndex(index)
                    elif isinstance(control, QCheckBox):
                        control.setChecked(defaults[key])
                    elif isinstance(control, QSpinBox) or isinstance(control, QDoubleSpinBox):
                        control.setValue(defaults[key])
                    elif isinstance(control, QSlider) and key == 'denoise_strength':
                        control.setValue(int(defaults[key] * 100))

    def update_ui_for_method(self, method):
        """選択されたメソッドに応じてUIを更新する"""
        # ... existing code ...
        
        # 半精度オプションの表示/非表示を制御 (カプセルではなくsr_utilsを使用)
        from sr.sr_utils import supports_half_precision
        supports_fp16 = supports_half_precision(method)
        
        # 半精度設定ウィジェットを表示/非表示
        if hasattr(self, 'fp16_checkbox') and self.fp16_checkbox is not None:
            self.fp16_checkbox.setVisible(supports_fp16)
            if not supports_fp16:
                self.fp16_checkbox.setChecked(False)  # 非サポートの場合はオフにする
