# Helldivers AutoAssets

这是一个用于Helldivers游戏的自动化资产识别工具，包含截图、OCR文本识别等功能。

## 项目结构

- `HelldiverAutoAssets.py` - 主应用程序，包含启动界面、截图、Tesseract OCR处理等功能
- `AssetsEditor.py` - 资产编辑器工具，用于更新和管理资产配置
- `Config/` - 配置文件目录，包含资产配置等

## 功能特性

- 游戏界面自动化操作
- OCR文本识别
- 多语言资产配置支持
- 热键控制

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

运行主程序：
```bash
python HelldiverAutoAssets.py
```

运行资产编辑器：
```bash
python AssetsEditor.py
```

## 上传到GitHub

项目包含自动上传工具，可在修改后一键上传到GitHub：

1. 确保已安装Git（https://git-scm.com/download/win）
2. 配置Git用户信息：
   ```bash
   git config --global user.name "你的GitHub用户名"
   git config --global user.email "你的GitHub邮箱"
   ```
3. 在GitHub上创建一个新的仓库
4. 运行自动上传脚本：
   ```bash
   python upload_to_github.py "你的提交信息"
   ```
   或使用批处理脚本：
   ```bash
   upload.bat "你的提交信息"
   ```
   或使用PowerShell脚本：
   ```powershell
   .\upload.ps1 "你的提交信息"
   ```

首次上传时，脚本会引导你配置远程仓库地址。

## 打包

项目可以通过BuildFile/build_project.py脚本自动打包成exe文件。

## 许可证

请参阅许可证文件（如果有的话）。