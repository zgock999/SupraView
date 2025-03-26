"""
プレビューウィンドウ用コンテキストメニュー

ImagePreviewWindowで使用するコンテキストメニューを提供します。
"""

from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup  # QActionGroupをQtGuiからインポート
from logutils import log_print, DEBUG, INFO, WARNING, ERROR


class PreviewContextMenu(QMenu):
    """プレビューウィンドウ用のコンテキストメニュー"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._create_actions()
        self._build_menu()
    
    def _create_actions(self):
        """メニューアクションの作成"""
        # 表示関連
        self.fit_to_window_action = QAction("ウィンドウに合わせる", self)
        self.fit_to_window_action.setCheckable(True)  # チェック可能に設定
        self.fit_to_window_action.triggered.connect(self._on_fit_to_window)
        
        self.original_size_action = QAction("原寸大表示", self)
        self.original_size_action.setCheckable(True)  # チェック可能に設定
        self.original_size_action.triggered.connect(self._on_original_size)
        
        # 表示モードをグループ化してラジオボタン動作に
        self.display_mode_group = QActionGroup(self)
        self.display_mode_group.addAction(self.fit_to_window_action)
        self.display_mode_group.addAction(self.original_size_action)
        self.display_mode_group.setExclusive(True)
        
        # デフォルトは原寸大表示にチェック
        self.original_size_action.setChecked(True)
        
        # 画像操作関連
        self.rotate_left_action = QAction("左に回転", self)
        self.rotate_left_action.triggered.connect(self._on_rotate_left)
        
        self.rotate_right_action = QAction("右に回転", self)
        self.rotate_right_action.triggered.connect(self._on_rotate_right)
        
        # 表示モード関連 - 新規追加
        self.mode_single_action = QAction("シングル", self)
        self.mode_single_action.setCheckable(True)
        self.mode_single_action.triggered.connect(lambda: self._on_set_view_mode("single"))
        
        self.mode_dual_rl_action = QAction("デュアル（右左）", self)
        self.mode_dual_rl_action.setCheckable(True)
        self.mode_dual_rl_action.triggered.connect(lambda: self._on_set_view_mode("dual_rl"))
        
        self.mode_dual_lr_action = QAction("デュアル（左右）", self)
        self.mode_dual_lr_action.setCheckable(True)
        self.mode_dual_lr_action.triggered.connect(lambda: self._on_set_view_mode("dual_lr"))
        
        self.mode_dual_rl_shift_action = QAction("デュアル（右左シフト）", self)
        self.mode_dual_rl_shift_action.setCheckable(True)
        self.mode_dual_rl_shift_action.triggered.connect(lambda: self._on_set_view_mode("dual_rl_shift"))
        
        self.mode_dual_lr_shift_action = QAction("デュアル（左右シフト）", self)
        self.mode_dual_lr_shift_action.setCheckable(True)
        self.mode_dual_lr_shift_action.triggered.connect(lambda: self._on_set_view_mode("dual_lr_shift"))
        
        # 表示モードをグループ化してラジオボタン動作に
        self.view_mode_group = QActionGroup(self)
        self.view_mode_group.addAction(self.mode_single_action)
        self.view_mode_group.addAction(self.mode_dual_rl_action)
        self.view_mode_group.addAction(self.mode_dual_lr_action)
        self.view_mode_group.addAction(self.mode_dual_rl_shift_action)
        self.view_mode_group.addAction(self.mode_dual_lr_shift_action)
        self.view_mode_group.setExclusive(True)
        
        # デフォルトはシングルモード
        self.mode_single_action.setChecked(True)
        
        # ファイル操作関連
        self.save_as_action = QAction("名前を付けて保存...", self)
        self.save_as_action.triggered.connect(self._on_save_as)
        
        self.copy_action = QAction("クリップボードにコピー", self)
        self.copy_action.triggered.connect(self._on_copy_to_clipboard)
        
        # ウィンドウ操作
        self.close_action = QAction("閉じる", self)
        self.close_action.triggered.connect(self._on_close)
    
    def _build_menu(self):
        """メニュー構造の構築"""
        # 表示メニュー
        view_menu = self.addMenu("表示")
        view_menu.addAction(self.fit_to_window_action)
        view_menu.addAction(self.original_size_action)
        
        # 表示モードメニュー - 新規追加
        mode_menu = self.addMenu("表示モード")
        mode_menu.addAction(self.mode_single_action)
        mode_menu.addSeparator()
        mode_menu.addAction(self.mode_dual_rl_action)
        mode_menu.addAction(self.mode_dual_lr_action)
        mode_menu.addSeparator()
        mode_menu.addAction(self.mode_dual_rl_shift_action)
        mode_menu.addAction(self.mode_dual_lr_shift_action)
        
        # 画像操作メニュー
        image_menu = self.addMenu("画像")
        image_menu.addAction(self.rotate_left_action)
        image_menu.addAction(self.rotate_right_action)
        
        # ファイル操作
        self.addSeparator()
        self.addAction(self.save_as_action)
        self.addAction(self.copy_action)
        
        # ウィンドウ操作
        self.addSeparator()
        self.addAction(self.close_action)
    
    def _on_fit_to_window(self):
        """ウィンドウに合わせる処理"""
        if hasattr(self.parent, 'fit_to_window'):
            self.parent.fit_to_window()
            self.fit_to_window_action.setChecked(True)
            self.original_size_action.setChecked(False)
            
            # 重複した画像調整を防ぐため、確認処理のみ実行
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._verify_display_mode)
    
    def _verify_display_mode(self):
        """表示モードが正しく適用されているか確認"""
        # 表示が更新されたことをログに出力
        from logutils import log_print, DEBUG
        log_print(DEBUG, "コンテキストメニューからの表示モード変更確認完了")
    
    def _on_original_size(self):
        """原寸大表示処理"""
        if hasattr(self.parent, 'show_original_size'):
            self.parent.show_original_size()
            self.fit_to_window_action.setChecked(False)
            self.original_size_action.setChecked(True)
            
            # 重複した画像調整を防ぐため、確認処理のみ実行
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._verify_display_mode)
    
    def _on_set_view_mode(self, mode: str):
        """
        表示モードを設定
        
        Args:
            mode: 表示モード
                - "single": シングルモード
                - "dual_rl": デュアルモード（右左）
                - "dual_lr": デュアルモード（左右）
                - "dual_rl_shift": デュアルモード（右左シフト）
                - "dual_lr_shift": デュアルモード（左右シフト）
        """
        if hasattr(self.parent, 'set_view_mode'):
            # モードを設定
            self.parent.set_view_mode(mode)
            
            # コンテキストメニューのチェック状態を更新
            self.update_view_mode(mode)
            
            # 処理後、少し遅延させて画像の読み込みと表示を確実にする
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200, lambda: self._ensure_display_updated(mode))
    
    def _ensure_display_updated(self, mode: str):
        """表示モード変更後に確実に画面が更新されるようにする"""
        if hasattr(self.parent, '_update_images_from_browser'):
            # ブラウザから画像を再取得して表示を更新
            self.parent._update_images_from_browser()
            
            # デュアルモードの場合は明示的にフィット表示を呼び出す
            if mode.startswith("dual_") and hasattr(self.parent, 'fit_to_window'):
                self.parent.fit_to_window()
                
        # ログ出力
        from logutils import log_print, DEBUG
        log_print(DEBUG, f"コンテキストメニューから表示モード変更後の画面更新を実行: {mode}")
    
    def _on_rotate_left(self):
        """左回転処理"""
        if hasattr(self.parent, 'rotate_left'):
            self.parent.rotate_left()
    
    def _on_rotate_right(self):
        """右回転処理"""
        if hasattr(self.parent, 'rotate_right'):
            self.parent.rotate_right()
    
    def _on_save_as(self):
        """名前を付けて保存処理"""
        if hasattr(self.parent, 'save_image_as'):
            self.parent.save_image_as()
    
    def _on_copy_to_clipboard(self):
        """クリップボードへコピー処理"""
        if hasattr(self.parent, 'copy_to_clipboard'):
            self.parent.copy_to_clipboard()
    
    def _on_close(self):
        """ウィンドウを閉じる処理"""
        self.parent.close()
    
    def update_view_mode(self, mode: str):
        """
        現在の表示モードに合わせてメニューのチェック状態を更新
        
        Args:
            mode: 現在の表示モード
        """
        if mode == "single":
            self.mode_single_action.setChecked(True)
        elif mode == "dual_rl":
            self.mode_dual_rl_action.setChecked(True)
        elif mode == "dual_lr":
            self.mode_dual_lr_action.setChecked(True)
        elif mode == "dual_rl_shift":
            self.mode_dual_rl_shift_action.setChecked(True)
        elif mode == "dual_lr_shift":
            self.mode_dual_lr_shift_action.setChecked(True)
    
    def update_display_mode(self, fit_to_window: bool):
        """
        現在の表示モード（ウィンドウに合わせる/原寸大）に合わせてチェック状態を更新
        
        Args:
            fit_to_window: ウィンドウに合わせるモードがONの場合はTrue
        """
        # メニューアクションのチェック状態を現在のモードに合わせて更新
        self.fit_to_window_action.setChecked(fit_to_window)
        self.original_size_action.setChecked(not fit_to_window)
        
        # デバッグログでチェック状態を確認
        log_print(DEBUG, f"コンテキストメニューの表示モード更新: fit_to_window={fit_to_window}")
