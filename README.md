# Helldivers AutoAssets

这是一个用于Helldivers游戏的自动化战备识别工具，包含截图、OCR文本识别等功能。

## 项目结构

- `HelldiverAutoAssets.py` - 主应用程序，包含启动界面、截图、Tesseract OCR处理等功能
- `AssetsEditor.py` - 资产编辑器工具，用于更新和管理资产配置
- `Config/` - 配置文件目录，包含资产配置等

## 功能特性

- 游戏界面自动化操作
- OCR文本识别
- 多语言战备配置支持
- 热键控制

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

从https://github.com/tesseract-ocr/tessdoc下载tesseract-ocr的安装包，勾选你想要使用的语言并安装，然后将程序根目录添加到系统path
运行主程序：
```bash
python HelldiverAutoAssets.py
```

运行资产编辑器：
```bash
python AssetsEditor.py
```

## 许可证

请参阅许可证文件（如果有的话）。
