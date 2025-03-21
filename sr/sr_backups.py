"""
超解像モデルのバックアップと診断ツール
"""
import os
import sys
import importlib
import platform

def create_environment_files():
    """モデル切り替え用の環境変数設定バッチファイルを作成"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # RealESRGANを無効化するバッチファイル
    disable_realesrgan_path = os.path.join(base_dir, "disable_realesrgan.bat")
    with open(disable_realesrgan_path, 'w') as f:
        f.write("@echo off\n")
        f.write("echo RealESRGANを無効化します...\n")
        f.write("set DISABLE_REALESRGAN=1\n")
        f.write("echo 環境変数を設定しました: DISABLE_REALESRGAN=1\n")
        f.write(f"cd {base_dir}\n")
        f.write("python main.py %*\n")
    
    # SwinIRを無効化するバッチファイル
    disable_swinir_path = os.path.join(base_dir, "disable_swinir.bat")
    with open(disable_swinir_path, 'w') as f:
        f.write("@echo off\n")
        f.write("echo SwinIRを無効化します...\n")
        f.write("set DISABLE_SWINIR=1\n")
        f.write("echo 環境変数を設定しました: DISABLE_SWINIR=1\n")
        f.write(f"cd {base_dir}\n")
        f.write("python main.py %*\n")
    
    # OpenCVのみを使用するバッチファイル
    opencv_only_path = os.path.join(base_dir, "use_opencv_only.bat")
    with open(opencv_only_path, 'w') as f:
        f.write("@echo off\n")
        f.write("echo OpenCV DNNのみを使用します...\n")
        f.write("set FORCE_OPENCV_SR=1\n")
        f.write("echo 環境変数を設定しました: FORCE_OPENCV_SR=1\n")
        f.write(f"cd {base_dir}\n")
        f.write("python main.py %*\n")
    
    # 全てのモデルを有効化するバッチファイル
    enable_all_path = os.path.join(base_dir, "enable_all_models.bat")
    with open(enable_all_path, 'w') as f:
        f.write("@echo off\n")
        f.write("echo 全ての超解像モデルを有効化します...\n")
        f.write("set DISABLE_REALESRGAN=\n")
        f.write("set DISABLE_SWINIR=\n")
        f.write("set FORCE_OPENCV_SR=\n")
        f.write("echo 環境変数をクリアしました\n")
        f.write(f"cd {base_dir}\n")
        f.write("python main.py %*\n")
    
    print(f"環境変数設定バッチファイルを作成しました:")
    print(f"  - {disable_realesrgan_path}")
    print(f"  - {disable_swinir_path}")
    print(f"  - {opencv_only_path}")
    print(f"  - {enable_all_path}")

def diagnose_sr_environment():
    """超解像環境の診断"""
    print("超解像環境の診断を行います...")
    print(f"Python バージョン: {platform.python_version()}")
    print(f"OS: {platform.system()} {platform.release()}")
    
    # 各モジュールの存在チェック
    modules_to_check = [
        ("numpy", "Numpy"),
        ("cv2", "OpenCV"),
        ("torch", "PyTorch"),
        ("basicsr", "BasicSR (RealESRGAN用)"),
    ]
    
    print("\n依存モジュールのチェック:")
    for module_name, display_name in modules_to_check:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "__version__"):
                print(f"  - {display_name}: 利用可能 ({module.__version__})")
            else:
                print(f"  - {display_name}: 利用可能 (バージョン不明)")
                
            # PyTorchの詳細情報
            if module_name == "torch":
                print(f"    - CUDA利用可能: {module.cuda.is_available()}")
                if module.cuda.is_available():
                    print(f"    - CUDA バージョン: {module.version.cuda}")
                    device_count = module.cuda.device_count()
                    print(f"    - 利用可能CUDA デバイス数: {device_count}")
                    for i in range(device_count):
                        print(f"    - デバイス {i}: {module.cuda.get_device_name(i)}")
            
            # OpenCVの詳細情報
            if module_name == "cv2":
                print(f"    - dnn_superres モジュールあり: {hasattr(module, 'dnn_superres')}")
                try:
                    # CUDA対応確認
                    cuda_devices = module.cuda.getCudaEnabledDeviceCount() if hasattr(module, 'cuda') else 0
                    print(f"    - OpenCV CUDA デバイス数: {cuda_devices}")
                except:
                    print(f"    - OpenCV CUDA サポートなし")
        except ImportError:
            print(f"  - {display_name}: インストールされていません")
        except Exception as e:
            print(f"  - {display_name}: エラー: {str(e)}")
    
    # エラーかもしれない特殊なケースを特定
    print("\n潜在的な問題の診断:")
    
    # Python 3.10以下でtyping.Self問題の可能性を確認
    if sys.version_info.major == 3 and sys.version_info.minor <= 10:
        try:
            import torch
            has_torch = True
        except ImportError:
            has_torch = False
        
        if has_torch:
            print("  - Python 3.10でのPyTorch typing.Self問題: 以下のエラーが発生する場合は、disable_realesrgan.batを使用してください")
            print("    Error: Plain typing.Self is not valid as type argument")
    
    create_environment_files()
    
    print("\n診断完了")
    print("問題が発生する場合は、生成されたバッチファイルを使用して特定のモデルを無効化して実行することをお試しください")

if __name__ == "__main__":
    diagnose_sr_environment()
