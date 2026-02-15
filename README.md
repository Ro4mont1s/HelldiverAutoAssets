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
从https://github.com/tesseract-ocr/tessdoc下载tesseract-ocr的安装包  
勾选你想要使用的语言并安装  
将程序根目录添加到系统path  

## 系统设置

1. 显示器分辨率比例应为16：9
2. 字体设置为微软雅黑

## 游戏内设置

显示模式设置为无边框全屏
HUD-HUD弧度：0
HUD-HUD不透明度：高
HUD-HUD大小：0.90

## 使用方法

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
