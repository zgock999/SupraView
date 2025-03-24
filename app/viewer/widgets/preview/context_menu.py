"""
プレビューウィンドウ用コンテキストメニュー

ImagePreviewWindowで使用するコンテキストメニューを提供します。
"""

from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup  # QActionGroupをQtGuiからインポート
from logutils import log_print, INFO, ERROR


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
    
    def _on_original_size(self):
        """原寸大表示処理"""
        if hasattr(self.parent, 'show_original_size'):
            self.parent.show_original_size()
            self.fit_to_window_action.setChecked(False)
            self.original_size_action.setChecked(True)
    
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
            self.parent.set_view_mode(mode)
    
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
        self.fit_to_window_action.setChecked(fit_to_window)
        self.original_size_action.setChecked(not fit_to_window)
