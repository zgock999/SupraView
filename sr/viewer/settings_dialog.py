"""
超解像処理の詳細設定ダイアログ
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QCheckBox, QTabWidget, QWidget,
    QDialogButtonBox, QGroupBox
)
from PySide6.QtCore import Qt
from typing import Dict, Any, Optional

class SettingsDialog(QDialog):
    """
    詳細設定ダイアログ
    """
    def __init__(self, parent=None, options: Dict[str, Any] = None):
        super().__init__(parent)
        self.setWindowTitle("超解像処理の詳細設定")
        self.resize(450, 350)
        
        self.options = options or {}
        self.setup_ui()
    
    def setup_ui(self):
        """UIの初期化"""
        # メインレイアウト
        main_layout = QVBoxLayout(self)
        
        # タブウィジェット
        self.tabs = QTabWidget()
        
        # 処理タブ
        self.process_tab = QWidget()
        self.process_layout = QVBoxLayout(self.process_tab)
        self.setup_process_tab()
        self.tabs.addTab(self.process_tab, "処理設定")
        
        # モデルタブ
        self.model_tab = QWidget()
        self.model_layout = QVBoxLayout(self.model_tab)
        self.setup_model_tab()
        self.tabs.addTab(self.model_tab, "モデル設定")
        
        # GPUタブ
        self.gpu_tab = QWidget()
        self.gpu_layout = QVBoxLayout(self.gpu_tab)
        self.setup_gpu_tab()
        self.tabs.addTab(self.gpu_tab, "GPU設定")
        
        main_layout.addWidget(self.tabs)
        
        # ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
    def setup_process_tab(self):
        """処理タブの設定"""
        # タイル処理グループ
        tile_group = QGroupBox("タイル処理設定")
        tile_layout = QFormLayout(tile_group)
        
        # タイルサイズ
        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 2048)
        self.tile_spin.setSingleStep(64)
        self.tile_spin.setValue(self.options.get('tile', 512))
        self.tile_spin.setSpecialValueText("無効")  # 0の場合は「無効」と表示
        tile_layout.addRow("タイルサイズ:", self.tile_spin)
        
        # タイルパディング
        self.tile_pad_spin = QSpinBox()
        self.tile_pad_spin.setRange(0, 256)
        self.tile_pad_spin.setSingleStep(8)
        self.tile_pad_spin.setValue(self.options.get('tile_pad', 32))
        tile_layout.addRow("タイルパディング:", self.tile_pad_spin)
        
        # 事前パディング
        self.pre_pad_spin = QSpinBox()
        self.pre_pad_spin.setRange(0, 256)
        self.pre_pad_spin.setSingleStep(4)
        self.pre_pad_spin.setValue(self.options.get('pre_pad', 0))
        tile_layout.addRow("事前パディング:", self.pre_pad_spin)
        
        self.process_layout.addWidget(tile_group)
        
        # その他の処理設定
        other_group = QGroupBox("その他の設定")
        other_layout = QFormLayout(other_group)
        
        # 半精度処理
        self.half_precision_check = QCheckBox("有効")
        self.half_precision_check.setChecked(self.options.get('half_precision', True))
        other_layout.addRow("半精度処理 (FP16):", self.half_precision_check)
        
        self.process_layout.addWidget(other_group)
        self.process_layout.addStretch()
    
    def setup_model_tab(self):
        """モデルタブの設定"""
        # モデルパスグループ
        model_group = QGroupBox("モデルパス設定")
        model_layout = QFormLayout(model_group)
        
        # モデル自動検出
        self.model_auto_detect_check = QCheckBox("自動検出")
        self.model_auto_detect_check.setChecked(self.options.get('model_auto_detect', True))
        model_layout.addRow("モデル検索:", self.model_auto_detect_check)
        
        # モデルディレクトリ
        self.model_dir_label = QLabel(self.options.get('model_dir', '標準の場所を使用'))
        browse_btn = QPushButton("参照...")
        browse_btn.clicked.connect(self.browse_model_dir)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.model_dir_label)
        dir_layout.addWidget(browse_btn)
        model_layout.addRow("モデルディレクトリ:", dir_layout)
        
        self.model_layout.addWidget(model_group)
        
        # モデルのダウンロード
        download_group = QGroupBox("モデルダウンロード")
        download_layout = QVBoxLayout(download_group)
        
        # ダウンロードボタン
        download_btn = QPushButton("モデルをダウンロード...")
        download_btn.clicked.connect(self.download_models)
        download_layout.addWidget(download_btn)
        
        # 説明テキスト
        download_layout.addWidget(QLabel(
            "※必要なモデルファイルがない場合は、\n"
            "  モデルダウンロードスクリプトを実行します。"
        ))
        
        self.model_layout.addWidget(download_group)
        self.model_layout.addStretch()
    
    def setup_gpu_tab(self):
        """GPUタブの設定"""
        # GPU使用設定グループ
        gpu_group = QGroupBox("GPU設定")
        gpu_layout = QFormLayout(gpu_group)
        
        # GPU使用設定
        self.use_gpu_check = QCheckBox("GPUを使用")
        self.use_gpu_check.setChecked(self.options.get('use_gpu', True))
        gpu_layout.addRow("GPU処理:", self.use_gpu_check)
        
        # GPUデバイス選択
        self.gpu_device_combo = QComboBox()
        self.gpu_device_combo.addItem("自動選択", -1)
        
        # 利用可能なGPUを列挙
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    device_name = torch.cuda.get_device_name(i)
                    self.gpu_device_combo.addItem(f"GPU {i}: {device_name}", i)
        except ImportError:
            pass
            
        current_device = self.options.get('gpu_id', -1)
        index = self.gpu_device_combo.findData(current_device)
        if index >= 0:
            self.gpu_device_combo.setCurrentIndex(index)
            
        gpu_layout.addRow("GPUデバイス:", self.gpu_device_combo)
        
        # メモリ使用量
        self.gpu_memory_spin = QSpinBox()
        self.gpu_memory_spin.setRange(0, 100)
        self.gpu_memory_spin.setSingleStep(5)
        self.gpu_memory_spin.setSuffix(" %")
        self.gpu_memory_spin.setValue(self.options.get('gpu_memory_fraction', 80))
        gpu_layout.addRow("メモリ使用量:", self.gpu_memory_spin)
        
        self.gpu_layout.addWidget(gpu_group)
        
        # GPUの詳細情報
        info_group = QGroupBox("GPU情報")
        info_layout = QVBoxLayout(info_group)
        
        try:
            import torch
            if torch.cuda.is_available():
                info_text = f"CUDA利用可能: はい\n"
                info_text += f"CUDAバージョン: {torch.version.cuda}\n"
                info_text += f"GPUデバイス数: {torch.cuda.device_count()}\n"
                
                for i in range(torch.cuda.device_count()):
                    device_name = torch.cuda.get_device_name(i)
                    info_text += f"\nGPU {i}: {device_name}\n"
                    props = torch.cuda.get_device_properties(i)
                    mem_gb = props.total_memory / (1024**3)
                    info_text += f"  メモリ: {mem_gb:.1f} GB\n"
            else:
                info_text = "CUDA利用不可"
        except ImportError:
            info_text = "PyTorchがインストールされていません。\nGPU情報を取得できません。"
        
        info_label = QLabel(info_text)
        info_layout.addWidget(info_label)
        
        self.gpu_layout.addWidget(info_group)
        self.gpu_layout.addStretch()
    
    def browse_model_dir(self):
        """モデルディレクトリの参照ダイアログ"""
        from PySide6.QtWidgets import QFileDialog
        import os
        
        current_dir = self.options.get('model_dir', '')
        if not current_dir:
            current_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
        
        dir_path = QFileDialog.getExistingDirectory(
            self, "モデルディレクトリを選択", current_dir
        )
        
        if dir_path:
            self.model_dir_label.setText(dir_path)
    
    def download_models(self):
        """モデルダウンロードスクリプトの実行"""
        try:
            import subprocess
            import sys
            import os
            
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'download_models.py'
            )
            
            if os.path.exists(script_path):
                from PySide6.QtWidgets import QMessageBox
                
                result = QMessageBox.question(
                    self,
                    "モデルダウンロード",
                    "モデルダウンロードスクリプトを実行します。\n"
                    "時間がかかる場合があります。続行しますか？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if result == QMessageBox.Yes:
                    # サブプロセスとしてスクリプトを実行
                    subprocess.Popen([sys.executable, script_path])
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "スクリプトが見つかりません",
                    f"モデルダウンロードスクリプトが見つかりません:\n{script_path}"
                )
        except Exception as e:
            print(f"モデルダウンロード実行エラー: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "モデルダウンロードエラー",
                f"モデルダウンロードの実行中にエラーが発生しました:\n{e}"
            )
    
    def set_options(self, options: Dict[str, Any]):
        """オプションの設定"""
        self.options = options.copy()
        
        # UIの更新
        self.tile_spin.setValue(self.options.get('tile', 512))
        self.tile_pad_spin.setValue(self.options.get('tile_pad', 32))
        self.pre_pad_spin.setValue(self.options.get('pre_pad', 0))
        self.half_precision_check.setChecked(self.options.get('half_precision', True))
        self.model_auto_detect_check.setChecked(self.options.get('model_auto_detect', True))
        self.model_dir_label.setText(self.options.get('model_dir', '標準の場所を使用'))
        self.use_gpu_check.setChecked(self.options.get('use_gpu', True))
        
        # GPUデバイス選択
        current_device = self.options.get('gpu_id', -1)
        index = self.gpu_device_combo.findData(current_device)
        if index >= 0:
            self.gpu_device_combo.setCurrentIndex(index)
            
        self.gpu_memory_spin.setValue(self.options.get('gpu_memory_fraction', 80))
    
    def get_options(self) -> Dict[str, Any]:
        """現在の設定を辞書として取得"""
        options = self.options.copy()
        
        # UI要素から値を更新
        options['tile'] = self.tile_spin.value()
        options['tile_pad'] = self.tile_pad_spin.value()
        options['pre_pad'] = self.pre_pad_spin.value()
        options['half_precision'] = self.half_precision_check.isChecked()
        options['model_auto_detect'] = self.model_auto_detect_check.isChecked()
        
        model_dir = self.model_dir_label.text()
        if model_dir != '標準の場所を使用':
            options['model_dir'] = model_dir
            
        options['use_gpu'] = self.use_gpu_check.isChecked()
        options['gpu_id'] = self.gpu_device_combo.currentData()
        options['gpu_memory_fraction'] = self.gpu_memory_spin.value()
        
        return options
