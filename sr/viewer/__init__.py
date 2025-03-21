"""
超解像処理のビジュアルテストツール
"""
import sys
from pathlib import Path
from .viewer import MainWindow, run

__all__ = ['MainWindow', 'run']

if __name__ == "__main__":
    sys.exit(run())
