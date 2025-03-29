import setuptools
import os

# READMEファイルがあれば読み込む
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()

# パッケージ設定
setuptools.setup(
    name="supraview",
    version="0.1.0",
    author="SupraView Team",
    author_email="your-email@example.com",
    description="A versatile viewer application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zgock999/supraview",
    project_urls={
        "Bug Tracker": "https://github.com/zgock999/supraview/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "."},
    packages=setuptools.find_packages(where="."),
    python_requires=">=3.8",
    install_requires=[
        "PySide6>=6.0.0",
        # プロジェクトの他の依存関係をここに追加
    ],
    entry_points={
        "console_scripts": [
            "supraview=app.main:main",
        ],
    },
    include_package_data=True,
)
