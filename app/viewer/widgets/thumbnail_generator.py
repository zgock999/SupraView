"""
サムネイル生成モジュール

画像ファイルからサムネイルを生成するユーティリティ。
バックグラウンドでのサムネイル生成をサポートします。
"""

import os
import sys
from typing import Dict, List, Optional, Callable, Any, Tuple

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print, DEBUG, INFO, WARNING, ERROR

try:
    from PySide6.QtGui import QPixmap, QImage, QIcon
    from PySide6.QtCore import QSize, Qt, QByteArray
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# デコーダーモジュールをインポート
from decoder.interface import get_supported_image_extensions, decode_image

# スレッド処理モジュールをインポート
from app.threads import WorkerManager

# サポートされている画像拡張子のリストを取得
SUPPORTED_EXTENSIONS = get_supported_image_extensions()


class SequentialExtractor:
    """
    ファイルを順次抽出するクラス
    
    アーカイブからファイルを一つずつ順番に抽出し、
    抽出が完了するごとにコールバックを呼び出します。
    """
    
    def __init__(self, archive_manager, file_paths, current_directory=''):
        """
        初期化
        
        Args:
            archive_manager: アーカイブマネージャインスタンス
            file_paths: 抽出するファイルパスのリスト
            current_directory: 現在のディレクトリ
        """
        self.archive_manager = archive_manager
        self.file_paths = file_paths
        self.current_directory = current_directory
        self.debug_mode = False
    
    def extract_files(self, on_file_extracted, progress_callback=None, is_cancelled=None):
        """
        ファイルをシーケンシャルに抽出
        
        Args:
            on_file_extracted: 抽出完了時のコールバック(filename, file_data)
            progress_callback: 進捗通知用コールバック
            is_cancelled: キャンセル確認用関数
        
        Returns:
            Dict: 処理結果の辞書
        """
        results = {}
        total = len(self.file_paths)
        
        for i, path in enumerate(self.file_paths):
            # キャンセルチェック
            if is_cancelled and is_cancelled():
                break
            
            # 進捗報告
            if progress_callback:
                percent = int((i + 1) * 100 / total)
                progress_callback(percent, f"ファイル抽出中: {i+1}/{total}")
            
            if self.debug_mode:
                log_print(DEBUG, f"ファイル抽出中: '{path}'")
            
            # ファイルを抽出 - extract_fileからextract_itemに変更
            try:
                # extract_itemを使用して現在のディレクトリからの相対パスでファイルを抽出
                file_data = self.archive_manager.extract_item(path)
                
                # 抽出成功の記録
                results[path] = file_data is not None
                
                # コールバックを呼び出し
                if file_data and on_file_extracted:
                    on_file_extracted(path, file_data)
            except Exception as e:
                if self.debug_mode:
                    log_print(ERROR, f"ファイル抽出エラー ({path}): {e}")
                results[path] = False
        
        return results


class ThumbnailGenerator:
    """
    フォルダ内の画像ファイルからサムネイルを生成するクラス。
    バックグラウンドでの処理とタスクのキャンセルをサポートします。
    """
    
    def __init__(self, debug_mode=False):
        """
        サムネイルジェネレータの初期化
        
        Args:
            debug_mode: デバッグモードの有効/無効
        """
        self.debug_mode = debug_mode
        
        # ワーカーマネージャの初期化（スレッド処理を管理）
        self.worker_manager = WorkerManager(max_threads=4, debug_mode=debug_mode)
        
        # 現在処理中のタスクIDを保存
        self.current_task_id = None
        self.extraction_task_id = None
        
        # サムネイルキャッシュ
        self.thumbnail_cache: Dict[str, QIcon] = {}
        
        # デフォルトアイコン（拡張子ごと）
        self.default_icons: Dict[str, QIcon] = {}
        
        # ファイル種別ごとのデフォルトアイコンを初期化
        self._init_default_icons()
        
        if self.debug_mode:
            log_print(DEBUG, f"ThumbnailGeneratorを初期化しました。サポート拡張子: {SUPPORTED_EXTENSIONS}")
    
    def _init_default_icons(self):
        """
        ファイル種別ごとのデフォルトアイコンを初期化
        """
        # ここで必要に応じてデフォルトアイコンを設定できます
        pass
    
    def can_generate_thumbnail(self, filename: str) -> bool:
        """
        指定されたファイルのサムネイルを生成できるかどうかをチェック
        
        Args:
            filename: チェックするファイル名
            
        Returns:
            サムネイル生成可能な場合はTrue、そうでない場合はFalse
        """
        _, ext = os.path.splitext(filename.lower())
        return ext in SUPPORTED_EXTENSIONS
    
    def cancel_current_task(self):
        """
        現在のサムネイル生成タスクをキャンセル
        """
        if self.current_task_id:
            if self.debug_mode:
                log_print(DEBUG, f"サムネイル生成タスク {self.current_task_id} をキャンセルします")
            
            # ワーカーマネージャを通じてタスクをキャンセル
            self.worker_manager.cancel_task(self.current_task_id)
            self.current_task_id = None
        
        # 抽出タスクもキャンセル
        if self.extraction_task_id:
            if self.debug_mode:
                log_print(DEBUG, f"ファイル抽出タスク {self.extraction_task_id} をキャンセルします")
            
            self.worker_manager.cancel_task(self.extraction_task_id)
            self.extraction_task_id = None
        
        # 実行中の全サムネイル生成タスクをキャンセル（重要な改善）
        self.worker_manager.cancel_all_tasks()
        log_print(INFO, "すべてのサムネイル関連タスクをキャンセルしました")
        
        # 現在のコンテキスト情報を記録（コンテキスト変更検出用）
        self._context_current_directory = None
    
    def generate_thumbnails(
        self,
        archive_manager,
        file_items: List[Dict[str, Any]],
        on_thumbnail_ready: Callable[[str, QIcon], None],
        on_all_completed: Callable[[], None] = None,
        thumbnail_size: QSize = QSize(128, 128),
        current_directory: str = ''  # 現在のディレクトリ情報を追加
    ):
        """
        ファイルリストからサムネイルを生成
        
        Args:
            archive_manager: アーカイブからファイルを読み込むためのマネージャ
            file_items: ファイル情報のリスト
            on_thumbnail_ready: サムネイル生成完了時のコールバック(filename, icon)
            on_all_completed: 全サムネイル生成完了時のコールバック
            thumbnail_size: サムネイルのサイズ
            current_directory: 現在表示中のディレクトリパス（相対パス）
        """
        # 既存のタスクをキャンセル
        self.cancel_current_task()
        
        # 現在のコンテキスト情報を保存（重要: コンテキスト変更検出用）
        self._context_current_directory = current_directory
        
        # 画像ファイルだけをフィルタリング
        image_files = [
            item['name'] for item in file_items 
            if not item.get('is_dir', False) and self.can_generate_thumbnail(item['name'])
        ]
        
        if not image_files:
            # 画像ファイルがない場合は完了を通知して終了
            if on_all_completed:
                on_all_completed()
            return
        
        # 常にデバッグ情報を出力（debug_modeに関わらず）
        log_print(INFO, f"サムネイル生成開始: {len(image_files)}ファイル、現在ディレクトリ: '{current_directory}'")
        
        # シーケンシャルエクストラクタを作成
        extractor = SequentialExtractor(
            archive_manager=archive_manager,
            file_paths=image_files,
            current_directory=current_directory
        )
        extractor.debug_mode = self.debug_mode
        
        # ファイル抽出完了時のコールバック
        def on_file_extracted(filename, file_data):
            # デバッグ出力を強化
            log_print(INFO, f"ファイル '{filename}' の抽出完了（{len(file_data)}バイト）、サムネイル生成を開始")
            
            # 抽出後にコンテキストが変更されていないかチェック（重要な改善）
            if current_directory != self._context_current_directory:
                log_print(WARNING, f"ディレクトリが変更されたためサムネイル生成をスキップします: {filename}")
                return
            
            # ワーカータスクに明示的にファイル名をキーワード引数として渡す
            # context_directory は渡さず、ラムダ関数で _handle_thumbnail_result に渡す
            task_id = self.worker_manager.start_task(
                self._generate_thumbnail_from_data,
                file_data=file_data,
                thumbnail_size=thumbnail_size,
                # 重要: filenameは引数ではなくキーワード引数としてワーカーに保存
                filename=filename,
                # コールバックを渡す - context_directoryはここで利用
                on_result=lambda task_id, result: self._handle_thumbnail_result(task_id, result, on_thumbnail_ready, filename, current_directory),
                on_error=lambda task_id, error_info: log_print(ERROR, f"サムネイル生成エラー ({filename}): {error_info[1]}")
            )
            log_print(INFO, f"サムネイル生成タスク開始: {task_id} - {filename}")
        
        # すべてのファイル抽出完了時のコールバック
        def on_extraction_completed(task_id, result):
            log_print(INFO, f"すべてのファイル抽出が完了しました。結果: {len(result) if isinstance(result, dict) else 'N/A'}")
            
            # 抽出タスクIDを初期化
            self.extraction_task_id = None
            
            # 全処理完了時のコールバックを呼び出し
            if on_all_completed:
                # アクティブなサムネイル生成タスクがなければ完了を通知
                active_tasks = self.worker_manager.active_task_count()
                log_print(INFO, f"残りのアクティブタスク数: {active_tasks}")
                if active_tasks == 0:
                    on_all_completed()
        
        # 抽出エラー時のコールバック
        def on_extraction_error(task_id, error_info):
            log_print(ERROR, f"ファイル抽出エラー: {error_info[1]}")
            self.extraction_task_id = None  # タスクIDをクリア
        
        # ファイル抽出タスクを開始
        self.extraction_task_id = self.worker_manager.start_task(
            extractor.extract_files,
            on_file_extracted=on_file_extracted,
            on_result=on_extraction_completed,
            on_error=on_extraction_error
        )
        
        log_print(INFO, f"ファイル抽出タスク開始: {self.extraction_task_id}")
    
    def _generate_thumbnail_from_data(
        self,
        filename: str,
        file_data: bytes,
        thumbnail_size: QSize,
        progress_callback=None,
        is_cancelled=None
    ) -> Optional[QIcon]:
        """
        バイトデータからサムネイルを生成
        
        Args:
            filename: ファイル名
            file_data: 画像データのバイト列
            thumbnail_size: サムネイルのサイズ
            progress_callback: 進捗通知用コールバック
            is_cancelled: キャンセル確認用関数
            
        Returns:
            生成したQIcon、失敗した場合はNone
        """
        try:
            # 処理開始のログ
            log_print(INFO, f"サムネイル生成処理開始: {filename}")
            
            # キャンセルチェック
            if is_cancelled and is_cancelled():
                log_print(INFO, f"サムネイル生成がキャンセルされました: {filename}")
                return None
            
            # キャッシュにあればそれを使用
            if filename in self.thumbnail_cache:
                if self.debug_mode:
                    log_print(DEBUG, f"キャッシュからサムネイルを取得: {filename}")
                return self.thumbnail_cache[filename]
            
            # 進捗報告
            if progress_callback:
                progress_callback(10, f"画像デコード中: {filename}")
            
            # デコーダーでファイルをデコード
            img_array = decode_image(filename, file_data)
            
            if img_array is None:
                if self.debug_mode:
                    log_print(WARNING, f"画像のデコードに失敗: {filename}")
                return None
            
            # 進捗報告
            if progress_callback:
                progress_callback(50, f"サムネイル変換中: {filename}")
            
            # NumPy配列からQImageを作成
            height, width = img_array.shape[:2]
            channels = 1 if len(img_array.shape) == 2 else img_array.shape[2]
            
            if channels == 1:  # グレースケール
                img = QImage(img_array.data, width, height, width, QImage.Format_Grayscale8)
            elif channels == 3:  # RGB
                img = QImage(img_array.data, width, height, width * 3, QImage.Format_RGB888)
            elif channels == 4:  # RGBA
                img = QImage(img_array.data, width, height, width * 4, QImage.Format_RGBA8888)
            else:
                if self.debug_mode:
                    log_print(WARNING, f"サポートされていないチャンネル数: {channels}")
                return None
            
            # QImageからQPixmapを作成
            pixmap = QPixmap.fromImage(img)
            
            # サムネイルサイズに縮小
            thumb = pixmap.scaled(
                thumbnail_size.width(), 
                thumbnail_size.height(),
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            # 進捗報告
            if progress_callback:
                progress_callback(90, f"サムネイル完成: {filename}")
            
            # QIconを作成
            icon = QIcon(thumb)
            
            # キャッシュに保存
            self.thumbnail_cache[filename] = icon
            
            # 処理完了のログ
            log_print(INFO, f"サムネイル生成完了: {filename}")
            
            return icon
            
        except Exception as e:
            log_print(ERROR, f"サムネイル生成エラー ({filename}): {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _handle_thumbnail_result(self, task_id: str, icon: Optional[QIcon], callback: Callable, filename: str, context_directory: str):
        """
        サムネイル生成結果の処理
        
        Args:
            task_id: タスクID
            icon: 生成されたアイコン（失敗した場合はNone）
            callback: 通知するコールバック関数
            filename: ファイル名（明示的に渡す）
            context_directory: 生成時のディレクトリコンテキスト
        """
        # コンテキスト変更をチェック - 別のディレクトリに移動していたら結果を無視（重要な改善）
        if context_directory != self._context_current_directory:
            log_print(INFO, f"ディレクトリが変更されたため結果を破棄します: {filename} (元:{context_directory}, 現在:{self._context_current_directory})")
            return
            
        # ファイル名は引数から直接取得するように修正
        if not icon:
            log_print(WARNING, f"サムネイル生成に失敗しました: {filename}")
            return
        
        # コールバックでサムネイル完了を通知
        if callback:
            try:
                log_print(INFO, f"サムネイル通知: {filename}")
                callback(filename, icon)
            except Exception as e:
                log_print(ERROR, f"サムネイルコールバック実行エラー: {e}")
                import traceback
                traceback.print_exc()
        
        log_print(DEBUG, f"サムネイル結果通知完了: {filename}")
    
    def _handle_error(self, task_id: str, error_info: Tuple):
        """
        エラー発生時の処理
        
        Args:
            task_id: タスクID
            error_info: エラー情報
        """
        error_type, error_value, traceback_str = error_info
        log_print(ERROR, f"タスク処理中にエラーが発生しました: {error_value}")
        if self.debug_mode:
            log_print(ERROR, traceback_str)
        
        # タスクID初期化
        if task_id == self.current_task_id:
            self.current_task_id = None
        elif task_id == self.extraction_task_id:
            self.extraction_task_id = None


# 単体テスト用のコード
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow, QListWidget, QVBoxLayout, QWidget, QListWidgetItem
    import sys
    
    # テスト用アプリケーション
    class TestApp(QMainWindow):
        def __init__(self):
            super().__init__()
            
            self.setWindowTitle("サムネイルジェネレータテスト")
            self.setGeometry(100, 100, 800, 600)
            
            # UI作成
            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            
            self.layout = QVBoxLayout(self.central_widget)
            self.list_widget = QListWidget()
            
            self.layout.addWidget(self.list_widget)
            
            # サムネイルジェネレータ生成
            self.thumbnail_generator = ThumbnailGenerator(debug_mode=True)
            
            # テストアイテム追加
            self.add_test_items()
        
        def add_test_items(self):
            # 実際のコードでは、ここでサムネイル生成処理を開始します
            pass
    
    # テスト実行
    app = QApplication(sys.argv)
    window = TestApp()
    window.show()
    sys.exit(app.exec())
