"""
SwinIR画像超解像ビューア
PySide6を使用したGUIアプリケーション
"""
import os
import sys
import time
import cv2
import numpy as np
import torch
import traceback
from pathlib import Path

# プロジェクトルートディレクトリをPythonパスに追加
current_dir = Path(__file__).parent.absolute()
root_dir = current_dir.parent.parent.parent  # viewer/sr/swinir/viewer -> viewer
sys.path.insert(0, str(root_dir))

# 現在の作業ディレクトリを設定（モデルパスの相対参照のため）
os.chdir(root_dir)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFileDialog, QComboBox, QSlider, QSpinBox, 
    QCheckBox, QProgressBar, QSplitter, QSizePolicy, QScrollArea, 
    QGroupBox, QRadioButton, QButtonGroup
)
from PySide6.QtGui import QImage, QPixmap, QIcon
from PySide6.QtCore import Qt, QThread, Signal, QSize

# sr.swinir.swinir_modelを使用
try:
    from sr.swinir.swinir_model import SwinIR, SwinIRModelType, make_model
except ImportError:
    print("モジュールのインポートに失敗しました。Pythonパスを確認してください。")
    print(f"sys.path: {sys.path}")
    sys.exit(1)

class SuperResolutionWorker(QThread):
    """超解像処理を行うワーカースレッド"""
    progress_signal = Signal(int)
    result_signal = Signal(object)
    error_signal = Signal(str)
    
    def __init__(self, image, scale, model_type, tile_size=None, tile_overlap=32, cached_model=None):
        super().__init__()
        self.image = image
        self.scale = scale
        self.model_type = model_type
        self.tile_size = tile_size
        self.tile_overlap = tile_overlap
        self.cached_model = cached_model  # キャッシュされたモデルを受け取り
    
    def run(self):
        try:
            # デバイスの設定
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.progress_signal.emit(10)  # 10%進捗
            
            # キャッシュされたモデルがある場合はそれを使用
            if self.cached_model is not None:
                model = self.cached_model
                self.progress_signal.emit(30)  # 30%進捗
            else:
                # モデルを作成
                # x8のサポートを明示的に除外
                if self.scale == 8:
                    print("警告: 拡大率8x (スケール8) は現在サポートされていません。4xに変更します。")
                    self.scale = 4
                    self.error_signal.emit("警告: 拡大率8x (スケール8) は現在サポートされていません。4xに変更します。")
                
                # モデル作成
                model = self.create_model(device)
                self.progress_signal.emit(30)  # 30%進捗
            
            # 入力画像の前処理
            img_lq = self.preprocess_image(self.image)
            img_lq = img_lq.to(device)
            self.progress_signal.emit(50)  # 50%進捗
            
            # 推論実行
            with torch.no_grad():
                # WindowサイズでPaddingを確保
                window_size = 8
                _, _, h_old, w_old = img_lq.size()
                h_pad = (window_size - h_old % window_size) % window_size
                w_pad = (window_size - w_old % window_size) % window_size
                if h_pad > 0 or w_pad > 0:
                    img_lq = torch.nn.functional.pad(img_lq, (0, w_pad, 0, h_pad), mode='reflect')
                
                # タイル処理の有無で分岐
                if self.tile_size is None:
                    output = model(img_lq)
                else:
                    output = self.test_tile(img_lq, model, self.scale, 
                                          self.tile_size, self.tile_overlap, window_size, device)
                    
                # 元のサイズにクロップ
                output = output[..., :h_old * self.scale, :w_old * self.scale]
            
            self.progress_signal.emit(80)  # 80%進捗
            
            # 結果の後処理
            output = output.data.squeeze().float().cpu().clamp_(0, 1).numpy()
            if output.ndim == 3:
                output = np.transpose(output, (1, 2, 0))  # CHW -> HWC
            output = (output * 255.0).round().astype(np.uint8)
            
            self.progress_signal.emit(100)  # 100%進捗
            
            # 処理結果と使用したモデルを返す
            self.result_signal.emit((output, model))
            
        except Exception as e:
            traceback.print_exc()
            self.error_signal.emit(f"処理エラー: {str(e)}")
    
    def create_model(self, device):
        """SwinIRモデルを作成する"""
        # モデルタイプに応じた設定
        if self.model_type == 'real_sr_large':
            swinir_type = SwinIRModelType.REAL_SR_LARGE
        elif self.model_type == 'real_sr':
            swinir_type = SwinIRModelType.REAL_SR
        elif self.model_type == 'classical_sr':
            swinir_type = SwinIRModelType.CLASSICAL_SR
        elif self.model_type == 'lightweight_sr':
            swinir_type = SwinIRModelType.LIGHTWEIGHT_SR
        else:
            swinir_type = SwinIRModelType.REAL_SR  # デフォルト
        
        # sr.swinir.swinir_model内の関数を使用してモデルを作成
        model = make_model(swinir_type, self.scale)
        
        # 重み読み込み
        model_path = self.get_model_path(swinir_type)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"モデルファイル {model_path} が見つかりません")
        
        try:
            # 重みの読み込み
            pretrained_model = torch.load(model_path, map_location=device)
            
            # 'params_ema'か'params'を探す
            if 'params_ema' in pretrained_model:
                model.load_state_dict(pretrained_model['params_ema'], strict=True)
            elif 'params' in pretrained_model:
                model.load_state_dict(pretrained_model['params'], strict=True)
            else:
                model.load_state_dict(pretrained_model, strict=True)
                
        except Exception as e:
            self.error_signal.emit(f"モデル読み込みエラー: {str(e)}\nモデルパス: {model_path}")
            raise e
        
        model.eval()
        return model.to(device)
    
    def get_model_path(self, swinir_type):
        """モデルパスを取得"""
        if swinir_type == SwinIRModelType.REAL_SR_LARGE:
            return f'./torch_models/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x{self.scale}_GAN.pth'
        elif swinir_type == SwinIRModelType.REAL_SR:
            return f'./torch_models/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-M_x{self.scale}_GAN.pth'
        elif swinir_type == SwinIRModelType.CLASSICAL_SR:
            return f'./torch_models/001_classicalSR_DF2K_s64w8_SwinIR-M_x{self.scale}.pth'
        elif swinir_type == SwinIRModelType.LIGHTWEIGHT_SR:
            return f'./torch_models/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x{self.scale}.pth'
        else:
            return f'./torch_models/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-M_x{self.scale}_GAN.pth'
    
    def preprocess_image(self, img):
        """画像をモデル入力用に前処理"""
        img = img.astype(np.float32) / 255.0
        # 入力画像はBGR（OpenCVから読み込まれた形式）なので、RGBに変換する
        img = img[:, :, [2, 1, 0]]  # BGR -> RGB
        img = np.transpose(img, (2, 0, 1))  # HWC -> CHW
        img = torch.from_numpy(img).float().unsqueeze(0)  # CHW -> NCHW
        return img
    
    def test_tile(self, img, model, scale, tile_size, tile_overlap, window_size, device):
        """タイル方式で超解像処理を実行する関数"""
        # 画像サイズを取得
        b, c, h, w = img.size()
        
        # タイルサイズ調整
        tile = min(tile_size, h, w)
        
        # タイルサイズがwindow_sizeの倍数であることを確認
        if tile % window_size != 0:
            tile = (tile // window_size) * window_size
        
        # オーバーラップを考慮したストライド計算
        stride = tile - tile_overlap
        
        # タイル位置のインデックスを計算
        h_idx_list = list(range(0, h - tile, stride)) + [max(0, h - tile)]
        w_idx_list = list(range(0, w - tile, stride)) + [max(0, w - tile)]
        h_idx_list = sorted(list(set(h_idx_list)))
        w_idx_list = sorted(list(set(w_idx_list)))
        
        # 出力テンソルと重みテンソルを初期化
        output = torch.zeros(b, c, h*scale, w*scale, device=device)
        weight = torch.zeros_like(output)
        
        # 各タイルを処理
        for h_idx in h_idx_list:
            for w_idx in w_idx_list:
                # タイル範囲を計算
                h_end = min(h_idx + tile, h)
                w_end = min(w_idx + tile, w)
                
                # タイルの端がピッタリになるよう調整
                h_idx = max(0, h_end - tile)
                w_idx = max(0, w_end - tile)
                
                # タイルを抽出
                in_patch = img[..., h_idx:h_end, w_idx:w_end]
                
                # タイル処理
                out_patch = model(in_patch)
                
                # 出力位置を計算
                h_out_start = h_idx * scale
                w_out_start = w_idx * scale
                h_out_end = h_end * scale
                w_out_end = w_end * scale
                
                # オーバーラップ部分の加重平均のため、結果と重みを蓄積
                output[..., h_out_start:h_out_end, w_out_start:w_out_end].add_(out_patch)
                weight[..., h_out_start:h_out_end, w_out_start:w_out_end].add_(torch.ones_like(out_patch))
        
        # 重みで割って平均を求める（オーバーラップ部分のブレンド）
        output = output.div_(weight)
        
        return output


class ImageDisplayWidget(QWidget):
    """画像表示ウィジェット"""
    def __init__(self, title=""):
        super().__init__()
        self.layout = QVBoxLayout()
        
        # タイトルラベル
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title_label)
        
        # スクロール可能な画像表示領域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        # 画像ラベル
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # スクロールエリアに画像ラベルを設定
        self.scroll_area.setWidget(self.image_label)
        self.layout.addWidget(self.scroll_area)
        
        # 解像度表示ラベル
        self.resolution_label = QLabel()
        self.resolution_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.resolution_label)
        
        self.setLayout(self.layout)
        self.image = None
    
    def set_image(self, image):
        """画像を設定"""
        self.image = image
        if image is None:
            self.image_label.clear()
            self.resolution_label.setText("")
            return
        
        # 解像度表示を更新
        h, w = image.shape[:2]
        self.resolution_label.setText(f"{w} x {h} pixels")
        
        # QImageに変換する前に、メモリの連続性を保証するためコピーを作成
        # C_CONTIGUOUS なメモリレイアウトを確保
        image_contiguous = np.ascontiguousarray(image)
        
        # QImageに変換してラベルに表示（RGB形式を前提）
        bytes_per_line = 3 * w
        q_img = QImage(image_contiguous.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        # リサイズが必要な場合は適切なサイズに調整
        max_size = QSize(800, 600)
        if pixmap.width() > max_size.width() or pixmap.height() > max_size.height():
            pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.image_label.setPixmap(pixmap)
    
    def clear(self):
        """表示をクリア"""
        self.image = None
        self.image_label.clear()
        self.resolution_label.setText("")


class MainWindow(QMainWindow):
    """メインウィンドウ"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SwinIR 画像超解像ビューア")
        self.setMinimumSize(1200, 800)
        
        # メンバ変数の初期化
        self.input_image = None
        self.output_image = None
        self.worker = None
        self.cached_models = {}  # モデルをキャッシュする辞書: {モデル識別子: モデルオブジェクト}
        
        # UI構築
        self.setup_ui()
    
    def setup_ui(self):
        """UIの構築"""
        # メインウィジェット
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # コントロールエリア
        control_layout = QHBoxLayout()
        
        # ファイル選択ボタン
        self.btn_load = QPushButton("画像を開く")
        self.btn_load.clicked.connect(self.load_image)
        control_layout.addWidget(self.btn_load)
        
        # モデル選択コンボボックス
        control_layout.addWidget(QLabel("モデル:"))
        self.model_combo = QComboBox()
        self.model_combo.addItem("実写画像超解像 (大)", "real_sr_large")
        self.model_combo.addItem("実写画像超解像 (標準)", "real_sr")
        self.model_combo.addItem("古典的超解像", "classical_sr")
        self.model_combo.addItem("軽量超解像", "lightweight_sr")
        control_layout.addWidget(self.model_combo)
        
        # スケール選択コンボボックス - x8を除外
        control_layout.addWidget(QLabel("拡大倍率:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItem("2倍", 2)
        self.scale_combo.addItem("3倍", 3)
        self.scale_combo.addItem("4倍", 4)
        # x8は除外
        self.scale_combo.setCurrentIndex(2)  # デフォルトは4倍
        control_layout.addWidget(self.scale_combo)
        
        # タイル処理サイズ
        control_layout.addWidget(QLabel("タイルサイズ:"))
        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 1024)
        self.tile_spin.setValue(0)  # 0はタイルなし
        self.tile_spin.setSingleStep(64)
        control_layout.addWidget(self.tile_spin)
        
        # 実行ボタン
        self.btn_process = QPushButton("超解像処理実行")
        self.btn_process.clicked.connect(self.process_image)
        self.btn_process.setEnabled(False)
        control_layout.addWidget(self.btn_process)
        
        # 保存ボタン
        self.btn_save = QPushButton("結果を保存")
        self.btn_save.clicked.connect(self.save_result)
        self.btn_save.setEnabled(False)
        control_layout.addWidget(self.btn_save)
        
        # 進捗バー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        
        # イメージディスプレイ（スプリッター）
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 入力画像表示
        self.input_display = ImageDisplayWidget("入力画像")
        self.splitter.addWidget(self.input_display)
        
        # 出力画像表示
        self.output_display = ImageDisplayWidget("出力画像（超解像結果）")
        self.splitter.addWidget(self.output_display)
        
        # レイアウト配置
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.splitter, 1)
        
        # ステータスバー
        self.statusBar().showMessage("画像を開いてください")
        
        # レイアウト設定
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def load_image(self):
        """画像読み込みダイアログ"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "画像を開く", "", "画像ファイル (*.jpg *.jpeg *.png *.bmp *.webp)"
        )
        
        if file_path:
            try:
                # OpenCVで画像を読み込み (BGR)
                img = cv2.imread(file_path)
                if img is None:
                    self.statusBar().showMessage(f"エラー: 画像を読み込めませんでした - {file_path}")
                    return
                
                # 元の画像はBGRのまま保存
                self.input_image = img
                
                # 表示用にBGR -> RGB変換
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                self.input_display.set_image(img_rgb)
                
                # 出力画像をクリア
                self.output_display.clear()
                self.output_image = None
                
                # ファイル名をステータスバーに表示
                filename = os.path.basename(file_path)
                self.statusBar().showMessage(f"読み込み完了: {filename}")
                
                # 処理ボタンを有効化
                self.btn_process.setEnabled(True)
                self.btn_save.setEnabled(False)
                
            except Exception as e:
                self.statusBar().showMessage(f"エラー: {str(e)}")
    
    def process_image(self):
        """超解像処理を実行"""
        if self.input_image is None:
            return
        
        # パラメータ取得
        scale = self.scale_combo.currentData()
        model_type = self.model_combo.currentData()
        
        # タイルサイズ (0の場合はNoneに)
        tile_size = self.tile_spin.value()
        if tile_size == 0:
            tile_size = None
        
        # モデル識別子（モデルタイプと拡大倍率の組み合わせ）
        model_identifier = f"{model_type}_{scale}x"
        
        # モデルがキャッシュにあるか確認
        cached_model = self.cached_models.get(model_identifier)
        if cached_model:
            self.statusBar().showMessage(f"キャッシュ済みモデル {model_identifier} を使用します")
        else:
            self.statusBar().showMessage("モデルを読み込みます...")
        
        # 処理中UIを無効化
        self.btn_process.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.btn_load.setEnabled(False)
        
        # 処理中メッセージ
        self.statusBar().showMessage("超解像処理実行中...")
        self.progress_bar.setValue(0)
        
        # CUDA memory情報を表示（メモリ不足対策）
        try:
            if torch.cuda.is_available():
                total_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                used_mem = torch.cuda.memory_allocated(0) / (1024**3)
                free_mem = total_mem - used_mem
                self.statusBar().showMessage(f"GPU メモリ: 合計 {total_mem:.1f}GB / 使用中 {used_mem:.1f}GB / 空き {free_mem:.1f}GB")
        except Exception as e:
            print(f"GPU情報取得エラー: {e}")
        
        # ワーカースレッド開始
        self.worker = SuperResolutionWorker(
            self.input_image, scale, model_type, tile_size, 32, cached_model
        )
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.result_signal.connect(self.set_result)
        self.worker.error_signal.connect(self.show_error)
        self.worker.start()
    
    def update_progress(self, value):
        """進捗バー更新"""
        self.progress_bar.setValue(value)
    
    def set_result(self, result):
        """処理結果を設定"""
        output_image, model = result  # 結果とモデルを受け取る
        
        # モデルをキャッシュに保存
        scale = self.scale_combo.currentData()
        model_type = self.model_combo.currentData()
        model_identifier = f"{model_type}_{scale}x"
        self.cached_models[model_identifier] = model
        
        # モデル出力はRGBなので、そのまま表示
        self.output_image = output_image  # RGB形式で保存
        self.output_display.set_image(output_image)
        
        # 処理完了
        self.statusBar().showMessage("超解像処理完了")
        
        # UIを有効化
        self.btn_process.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.btn_load.setEnabled(True)
    
    def show_error(self, message):
        """エラーメッセージを表示"""
        self.statusBar().showMessage(message)
        
        # メッセージが長い場合はダイアログも表示
        if len(message) > 50:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "エラー", message)
        
        # UIを有効化
        self.btn_process.setEnabled(True)
        self.btn_load.setEnabled(True)
    
    def save_result(self):
        """処理結果を保存"""
        if self.output_image is None:
            return
        
        # 保存ダイアログ
        file_path, _ = QFileDialog.getSaveFileName(
            self, "結果の保存", "", "PNG画像 (*.png);;JPEG画像 (*.jpg);;すべてのファイル (*.*)"
        )
        
        if file_path:
            try:
                # 出力画像はRGB形式なので、保存前にBGR形式に変換
                save_image = cv2.cvtColor(self.output_image, cv2.COLOR_RGB2BGR)
                # コピーを作成して連続性を保証
                save_image = np.ascontiguousarray(save_image)
                # OpenCVで保存
                cv2.imwrite(file_path, save_image)
                self.statusBar().showMessage(f"保存完了: {file_path}")
            except Exception as e:
                self.statusBar().showMessage(f"保存エラー: {str(e)}")


if __name__ == "__main__":
    # ハイDPI対応
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
