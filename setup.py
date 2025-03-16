from setuptools import setup, find_packages

setup(
    name="supraview",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.20.0",
        "opencv-python>=4.5.0",
        "Pillow>=8.0.0",
    ],
    extras_require={
        "viewer": [
            "dash>=2.0.0",
            "dash-bootstrap-components>=1.0.0",
        ],
        "dev": [
            "pytest>=6.0.0",
        ],
    },
    author="SupraView開発者",
    author_email="example@example.com",
    description="複数の画像フォーマットに対応した画像ビューワーアプリケーション",
    keywords="image, viewer, decoder, mag, retro",
    url="https://github.com/yourusername/supraview",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.7",
)
