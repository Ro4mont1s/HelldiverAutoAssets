import json
import os
import sys
import threading
import time
from pynput import keyboard
import subprocess
import pyautogui
from pynput.keyboard import Key, Controller
import tkinter as tk
from tkinter import font
import logging
from datetime import datetime
import difflib
from PIL import Image, ImageEnhance
import pytesseract
import re
import gc
from functools import lru_cache
import io  # 添加io模块导入

# 加载配置文件
configDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Config")


def loadJson(filePath):
    """加载 JSON 文件"""
    try:
        with open(filePath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        mainLogger.error(f"未找到配置文件 {filePath}")
        print(f"错误：未找到配置文件 {filePath}")
        return {}
    except json.JSONDecodeError:
        mainLogger.error(f"{filePath} 不是合法的JSON文件")
        print(f"错误：{filePath} 不是合法的JSON文件")
        return {}
    except Exception as e:
        mainLogger.error(f"加载配置文件失败：{str(e)}")
        print(f"加载配置文件失败：{str(e)}")
        return {}


# 加载配置文件
vanillaConfigPath = os.path.join(configDir, "Vanilla.json")

# 根据OCR语言设置动态确定Assets配置文件路径
def getAssetsConfigPath():
    # 首先尝试加载基础配置获取OCR语言设置
    basicConfig = loadJson(vanillaConfigPath)
    ocrLanguage = basicConfig.get("ocr_language", "chi_sim")
    assetsDir = os.path.join(configDir, "Assets")
    return os.path.join(assetsDir, f"{ocrLanguage}.json")

assetsConfigPath = getAssetsConfigPath()

# 如果Vanilla.json不存在，使用默认配置并创建它
if not os.path.exists(vanillaConfigPath):
    defaultVanilla = {
        "screen_width": 2560,
        "screen_height": 1440,
        "reinforce": "0",
        "supply": ".",
        "map1": "7",
        "map2": "8",
        "map3": "9",
        "player1": "1",
        "player2": "2",
        "player3": "3",
        "player4": "4",
        "player5": "5",
        "ocr_language": "chi_sim"
    }
    # 确保Config目录存在
    if not os.path.exists(configDir):
        os.makedirs(configDir)
    with open(vanillaConfigPath, 'w', encoding='utf-8') as f:
        json.dump(defaultVanilla, f, ensure_ascii=False, indent=4)

# 加载实际配置文件
basicConfig = loadJson(vanillaConfigPath)
# 根据OCR语言设置加载Assets配置文件
assetsConfigPath = getAssetsConfigPath()
assetsData = loadJson(assetsConfigPath)

# TESSERACT结果存储（运行时更新）
tesseractResults = {}

# GUI数据存储（运行时更新）
guiData = []

# 标记：指示程序完全在内存中处理数据，不与文件交互
memoryOnlyMode = True

# 日志记录器相关代码
def setupLogger(name, level=logging.INFO):
    """设置日志记录器，所有模块共享一个日志文件"""
    # 创建logs目录
    logsDir = "logs"
    if not os.path.exists(logsDir):
        os.makedirs(logsDir)

    # 创建格式化的日志文件名（包含毫秒）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 保留毫秒（去掉微秒的后三位）
    logPath = os.path.join(logsDir, f"HelldiverAutoAssets_{timestamp}.log")

    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 创建文件处理器 - 只在第一次创建时添加
    if not hasattr(setupLogger, 'log_file_path'):
        setupLogger.logFilePath = logPath
        fileHandler = logging.FileHandler(logPath, encoding='utf-8')
        fileHandler.setLevel(level)

        # 创建控制台处理器
        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(level)

        # 创建格式器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fileHandler.setFormatter(formatter)
        consoleHandler.setFormatter(formatter)

        # 添加处理器到logger
        logger.addHandler(fileHandler)
        logger.addHandler(consoleHandler)
    else:
        # 如果不是第一次创建，使用已存在的日志文件路径
        fileHandler = logging.FileHandler(setupLogger.logFilePath, encoding='utf-8')
        fileHandler.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fileHandler.setFormatter(formatter)
        logger.addHandler(fileHandler)

    return logger

# 定义不同模块的日志记录器 - 全部使用同一个日志文件
mainLogger = setupLogger('main_app')
screenshotLogger = setupLogger('screenshot')
ocrLogger = setupLogger('ocr')
bindingLogger = setupLogger('binding')
guiLogger = setupLogger('gui')

# 安全地设置stdout编码 - 终极版本
def safe_set_stdout_encoding():
    """安全设置stdout编码，处理各种打包环境下的特殊情况"""
    try:
        # 尝试使用sys.stdout
        if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            return True

        # 尝试使用sys.__stdout__
        if hasattr(sys, '__stdout__') and sys.__stdout__ is not None and hasattr(sys.__stdout__, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.__stdout__.buffer, encoding='utf-8')
            return True

        # 创建一个新的stdout流
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False)
        sys.stdout = io.TextIOWrapper(temp_file, encoding='utf-8')
        return True

    except Exception as e:
        # 如果所有方法都失败，至少确保程序能继续运行
        # 可以选择记录错误到日志文件
        try:
            with open('error.log', 'a', encoding='utf-8') as f:
                f.write(f"Failed to set stdout encoding: {str(e)}\n")
        except:
            pass
        return False

# 调用安全设置函数
safe_set_stdout_encoding()

@lru_cache(maxsize=128)  # 缓存资产文本加载结果
def loadAssetsText():
    """加载assetsData中的【左侧中文文本】作为对比库 加载所有分类（Map, Player下的R/G/B）"""
    global assetsData
    # 仅在必要时重新加载配置文件
    try:
        if not isinstance(assetsData, dict):
            raise ValueError("assetsData 格式不正确，必须是字典类型")
        # 加载所有分类：Map, Player下的R/G/B
        combinedAssets = {}
        # 处理Map顶层分类
        if "Map" in assetsData and isinstance(assetsData["Map"], dict):
            combinedAssets.update(assetsData["Map"])
        # 处理Player下的R/G/B分类
        if "Player" in assetsData and isinstance(assetsData["Player"], dict):
            for subCat in ["R", "G", "B"]:
                if subCat in assetsData["Player"] and isinstance(assetsData["Player"][subCat], dict):
                    combinedAssets.update(assetsData["Player"][subCat])
        ocrLogger.info(f"成功加载对比文本数量：{len(combinedAssets)} 条")
        return combinedAssets
    except Exception as e:
        ocrLogger.error(f"加载配置数据失败：{str(e)}")
        return {}

def get_similarity(text1, text2):
    """计算两个中文文本的相似度（0-1，1=完全相同），优化中文匹配精度"""
    # 快速检查：如果文本完全相同，直接返回1
    if text1 == text2:
        return 1.0

    # 过滤掉特殊字符，只比较中文字符
    clean_text1 = re.sub(r'[^\u4e00-\u9fff]', '', text1)
    clean_text2 = re.sub(r'[^\u4e00-\u9fff]', '', text2)

    # 如果其中一个没有中文字符，则使用原始文本
    if not clean_text1 or not clean_text2:
        return difflib.SequenceMatcher(None, text1, text2).ratio()
    else:
        return difflib.SequenceMatcher(None, clean_text1, clean_text2).ratio()

def find_most_similar(target_text, text_list, threshold=0.3):  # 降低阈值，让更多的匹配能够通过
    """从中文对比库中找出相似度最高的文本，增加阈值控制"""
    if not target_text or not text_list:
        return None, 0.0

    # 使用内置max函数和生成器表达式优化性能
    similarities = ((text, get_similarity(target_text, text)) for text in text_list)
    try:
        most_similar_text, max_similarity = max(similarities, key=lambda x: x[1])
        return most_similar_text, max_similarity
    except ValueError:  # 空序列
        return None, 0.0

def preprocessImage(imagePath):
    """优化图片预处理步骤，减少内存占用"""
    try:
        # 图片预处理【增强中文识别率】：灰度化→提高对比度→二值化→反色，解决模糊/浅色文字识别不到的问题
        img = Image.open(imagePath).convert('L')

        # 增强对比度
        enhancer = ImageEnhance.Contrast(img)
        imgEnhanced = enhancer.enhance(2.5)  # 进一步提高对比度

        # 应用锐化滤镜
        from PIL import ImageFilter
        imgSharpened = imgEnhanced.filter(ImageFilter.SHARPEN)

        # 二值化处理，使用Otsu算法或自适应阈值
        imgBinary = imgSharpened.point(lambda p: 255 if p > 230 else 0, 'L')

        return imgBinary
    except Exception as e:
        ocrLogger.error(f"预处理图片失败: {e}")
        # 返回原图作为备用
        return Image.open(imagePath).convert('L')


def preprocessImageFromMemory(image):
    """优化内存中图片预处理步骤，减少内存占用"""
    try:
        # 图片预处理【增强中文识别率】：灰度化→提高对比度→二值化→反色，解决模糊/浅色文字识别不到的问题
        img = image.convert('L')

        # 增强对比度
        enhancer = ImageEnhance.Contrast(img)
        imgEnhanced = enhancer.enhance(2.5)  # 进一步提高对比度

        # 应用锐化滤镜
        from PIL import ImageFilter
        imgSharpened = imgEnhanced.filter(ImageFilter.SHARPEN)

        # 二值化处理，使用Otsu算法或自适应阈值
        imgBinary = imgSharpened.point(lambda p: 255 if p > 230 else 0, 'L')

        return imgBinary
    except Exception as e:
        ocrLogger.error(f"预处理内存中图片失败: {e}")
        # 返回原图作为备用
        return image.convert('L')

def processImageFromMemory(image, imageName, assetsData, tesseractResults):
    """处理内存中的图片：高清中文识别 → 清洗识别结果 → 相似度对比 → 控制台输出"""
    imgBinary = None
    try:
        ocrLogger.info(f"处理图片: {imageName}")
        # 图片预处理
        imgBinary = preprocessImageFromMemory(image)

        # 从配置文件获取OCR语言设置
        ocrLang = basicConfig.get("ocr_language", "chi_sim")

        # 使用多种OCR配置尝试识别，选择最佳结果
        configs = [
            f'--oem 3 --psm 6 -l {ocrLang}',  # 默认配置
            f'--oem 3 --psm 13 -l {ocrLang}', # 纯文字行
            f'--oem 3 --psm 7 -l {ocrLang}',  # 单行
            f'--oem 3 --psm 8 -l {ocrLang}'   # 单词
        ]

        bestResult = ""

        for config in configs:
            try:
                # 获取带有置信度的识别结果
                data = pytesseract.image_to_data(imgBinary, config=config, output_type=pytesseract.Output.DICT)

                # 过滤出可信度高的文本 - 使用列表推导式优化
                textParts = [
                    text.strip()
                    for i, text in enumerate(data['text'])
                    if text.strip() and (int(data['conf'][i]) if data['conf'][i] != '' else 0) > 30
                ]

                currentResult = ''.join(textParts)

                if len(currentResult) > len(bestResult):
                    bestResult = currentResult

            except Exception as e:
                ocrLogger.warning(f"OCR配置 {config} 失败: {e}")
                continue  # 如果某个配置失败，继续尝试下一个

        # 如果所有配置都失败，使用基本识别
        if not bestResult:
            recognizedText = pytesseract.image_to_string(imgBinary, lang=ocrLang)
            bestResult = recognizedText

        # 清洗识别结果：去掉换行/空格/制表符，只保留纯中文文本
        recognizedText = bestResult.replace('\n', '').replace('\r', '').replace(' ', '').replace('\t', '').strip()

        # ======== 控制台格式化输出核心结果 ========
        print("-" * 60)
        print(f"[IMG] 处理图片：{imageName}")
        print(f"[TXT] 图片识别出的中文：{recognizedText if recognizedText else '【无识别结果】'}")

        # 相似度匹配+输出
        if recognizedText and assetsData:
            mostSimilarText, similarity = find_most_similar(recognizedText, list(assetsData.keys()))

            if mostSimilarText:
                print(f"[SUCCESS] 最相似的文本（JSON左侧）：{mostSimilarText} (相似度: {similarity:.2f})")
                ocrLogger.info(f"图片 {imageName} 识别成功: {mostSimilarText} (相似度: {similarity:.2f})")
                # 获取最相似文本对应的字段
                if mostSimilarText in assetsData:
                    correspondingField = assetsData[mostSimilarText]
                    # 将识别结果添加到有序字典中
                    tesseractResults[imageName] = {mostSimilarText: correspondingField}
                else:
                    ocrLogger.warning(f"未在 assetsData 中找到对应字段：{mostSimilarText}")
                    # 即使没找到对应字段也记录识别结果
                    tesseractResults[imageName] = {mostSimilarText: ""}
            else:
                print(f"[FAILED] 未找到相似文本 (最高相似度: {similarity:.2f})")
                ocrLogger.info(f"图片 {imageName} 未找到匹配项 (最高相似度: {similarity:.2f})")
                # 当完全找不到相似文本时，仍然记录识别结果，但使用原始识别文本作为键
                tesseractResults[imageName] = {recognizedText: ""}
        elif not assetsData:
            print("[FAILED] 未加载到JSON中的中文对比文本")
            ocrLogger.warning("未加载到JSON中的中文对比文本")
        else:
            print("[SKIPPED] 图片未识别到有效中文，跳过匹配")
            ocrLogger.info(f"图片 {imageName} 未识别到有效中文")
            # 记录空识别结果
            tesseractResults[imageName] = {"": ""}

    except Exception as e:
        ocrLogger.error(f"处理图片 {imageName} 失败：{str(e)}")
        # 记录错误情况
        tesseractResults[imageName] = {"": ""}
    finally:
        # 释放图片资源
        if imgBinary:
            imgBinary.close()
            imgBinary = None  # 清除引用
        # 强制垃圾回收
        gc.collect()

def captureScreenshotsToMemory():
    """一次性捕捉所有截图并保存在内存中，减少系统调用"""
    screenshotLogger.info("开始截图流程")
    screenshots = []  # 用于存储内存中的截图
    try:
        # 按住Ctrl键
        pyautogui.keyDown('ctrl')
        time.sleep(0.1)  # 减少延迟

        # 获取屏幕分辨率一次
        screenWidth = basicConfig.get("screen_width", 2560)
        screenHeight = basicConfig.get("screen_height", 1440)

        # 预计算坐标
        startX = round(screenWidth * 0.05859)
        startY = round(screenHeight * 0.075)

        # 一次性处理所有截图
        for i in range(8):
            try:
                # 计算当前截图区域
                region = (startX, startY + i * 70, 290, 30)

                # 截图并保存到内存列表中
                screenshot = pyautogui.screenshot(region=region)
                screenshots.append(screenshot)
                screenshotLogger.debug(f"已截取图片到内存 screenshot{i+1}.png")

                # 强制垃圾回收
                if i % 3 == 0:  # 每3次截图执行一次垃圾回收
                    gc.collect()
            except Exception as e:
                screenshotLogger.error(f"截图 {i+1} 失败: {e}")
                # 即使单个截图失败，也要继续下一个
                continue

    except Exception as e:
        screenshotLogger.error(f"截图过程中发生错误: {e}")
        # 确保Ctrl键被释放，即使在异常情况下
        try:
            pyautogui.keyUp('ctrl')
        except:
            pass
        raise
    finally:
        # 确保Ctrl键被释放
        try:
            pyautogui.keyUp('ctrl')
        except Exception as e:
            screenshotLogger.warning(f"释放Ctrl键时出错: {e}")

    screenshotLogger.info("截图完成，已将8张截图保存在内存中")
    print(f"已将8张截图保存在内存中。")
    return screenshots

def runOcrRecognition(screenshots):
    """执行OCR识别流程，接收内存中的截图列表"""
    ocrLogger.info("开始OCR识别流程")
    # 步骤1：加载JSON中【左侧的中文文本】
    assetsData = loadAssetsText()
    if not assetsData:
        ocrLogger.error("程序退出：无有效对比文本")
        print("程序退出：无有效对比文本")
        return

    # 有序字典存储识别结果
    localTesseractResults = {}

    # 顺序处理内存中的截图，避免同时处理过多图片占用内存
    for i, screenshot in enumerate(screenshots):
        imageName = f"screenshot{i+1}.png"
        processImageFromMemory(screenshot, imageName, assetsData, localTesseractResults)

    # 将识别结果存储到全局变量中
    global tesseractResults
    tesseractResults = localTesseractResults

    ocrLogger.info("OCR识别流程完成")
    print(f"[SAVED] 识别结果已更新")

    # 可选：在内存中维护tesseract结果的备份，不写入文件
    # 这样可以随时访问最新的识别结果
    return localTesseractResults

# ===================== 【核心配置 】 ================================
windowWidthScale = 0.1171875  # 窗口宽度 = 屏幕宽度 × 该比例
windowHeightScale = 0.48611  # 窗口高度 = 屏幕高度 × 该比例
# 文本颜色配置（Map/Player-R/G/B 对应颜色）
textColors = {
    "Map": "yellow",  # Map分类 → 金色（较柔和的黄色）- 使用标签名而非十六进制值
    "R": "red",  # Player-R → 浅珊瑚红（较柔和的红色）- 使用标签名而非十六进制值
    "G": "green",  # Player-G → 浅绿色（较柔和的绿色）- 使用标签名而非十六进制值
    "B": "blue"  # Player-B → 天蓝色（较柔和的蓝色）- 使用标签名而非十六进制值
}
# ==================================================================

# 全局状态存储
globalState = {
    "running": True,
    "screenshotTriggered": False,
    "bindProcess": None,  # 用于存储键盘监听器
    "initialWindow": None,
    "windowTextWidget": None,  # 替换原StringVar，改用Text组件
    "numpadBindings": None,  # 新增：存储绑定信息
    "activeThreads": {},  # 新增：跟踪活跃的按键模拟线程
    "mouseCenteringThread": None,  # 新增：用于存储鼠标中心固定线程
    "centerMouse": False  # 新增：标志位，控制是否持续固定鼠标在中心
}

# 固定提示文本（始终显示在窗口顶部）
fixedPrompt = "按下 F12 重新识别\n按下 F11 退出程序\n\n"

def setup_global_hotkeys():
    """设置全局热键"""
    def on_f11():
        # F11 退出程序：关闭窗口+终止所有子进程+退出
        globalState["running"] = False
        mainLogger.info("收到F11退出指令")
        print("程序已停止")
        if globalState["initialWindow"] is not None:
            globalState["initialWindow"].quit()
        if globalState["bindProcess"] is not None:
            try:
                globalState["bindProcess"].stop()  # 停止键盘监听器
                mainLogger.info("键盘监听器已停止")
                print("键盘监听器已停止")
            except Exception as e:
                mainLogger.error(f"停止键盘监听器失败: {e}")
                print(f"停止键盘监听器失败: {e}")
        
        # 停止鼠标居中功能（如果正在运行）
        globalState["centerMouse"] = False
        if globalState["mouseCenteringThread"]:
            try:
                globalState["mouseCenteringThread"].join(timeout=1)  # 等待最多1秒让线程结束
            except:
                pass
        os._exit(0)

    def on_f12():
        # 检查是否已经有截图线程在运行，避免重复触发
        if globalState["screenshotTriggered"]:
            mainLogger.info("F12已被触发，当前识别流程正在进行中，忽略新的触发")
            print("F12已被触发，当前识别流程正在进行中，忽略新的触发")
            return
        # F12 触发识别流程：防重复触发+更新窗口文本+开线程执行任务（支持重复触发）
        mainLogger.info("收到F12重新识别指令")
        # 移动鼠标到屏幕中心以确保截图一致性
        try:
            screenWidth, screenHeight = pyautogui.size()
            centerX, centerY = screenWidth // 2, screenHeight // 2
            pyautogui.moveTo(centerX, centerY)
        except Exception as e:
            mainLogger.error(f"移动鼠标到屏幕中心失败: {e}")
        # 设置触发状态，防止重复点击
        globalState["screenshotTriggered"] = True
        updateWindowContent("识别中...")
        screenshotThread = threading.Thread(target=runScreenshot)
        screenshotThread.start()

    # 创建全局热键监听器
    hotkey_listener = keyboard.GlobalHotKeys({
        '<f11>': on_f11,
        '<f12>': on_f12
    })
    return hotkey_listener


# 创建统一的键盘事件处理函数（处理小键盘按键）
def unifiedOnPress(key):
    """统一的键盘事件处理函数，处理小键盘按键（F11/F12由全局热键处理）"""
    try:
        # 处理小键盘按键（仅在绑定完成后）
        if globalState["numpadBindings"]:
            onPressHandler(key, globalState["numpadBindings"], Controller())
    except Exception as e:
        mainLogger.error(f"键盘事件处理出错: {e}")


def onPress(key):
    # 调用统一的键盘事件处理函数，只处理非全局热键
    try:
        # 检查是否是全局热键（F11或F12），如果是则跳过处理
        if hasattr(key, 'vk'):
            if key.vk in [122, 123]:  # F11=122, F12=123
                return  # 跳过全局热键，由GlobalHotKeys处理
        else:
            if key in [Key.f11, Key.f12]:
                return  # 跳过全局热键，由GlobalHotKeys处理
        unifiedOnPress(key)
    except Exception as e:
        mainLogger.error(f"键盘事件处理出错: {e}")


def loadJsonFromEmbeddedData(configName):
    """从内嵌数据加载配置"""
    if configName == "basic":
        return basicConfig
    elif configName == "assets":
        return assetsData
    else:
        return {}


# 从内嵌数据提取所有「中文名称:指令」键值对
def extractTesseractData(tesseractData):
    """解析 tesseractResults 嵌套结构，返回 {中文名称: 指令} 的扁平字典"""
    combinedData = {}
    if not isinstance(tesseractData, dict):
        mainLogger.error("tesseractResults 格式错误，不是字典类型")
        print("tesseractResults 格式错误，不是字典类型")
        return combinedData

    # 遍历每个截图的识别结果，提取中文-指令对
    for screenshotName, content in tesseractData.items():
        if isinstance(content, dict) and len(content) == 1:
            # 取出唯一的中文名称和对应指令
            chineseName = list(content.keys())[0]
            command = content[chineseName]
            # 只有当中文名称不为空时才添加，但即使是空的也要处理
            if chineseName:  # 如果识别到了中文名称
                combinedData[chineseName] = command
            else:
                # 如果识别失败（中文名称为空），跳过此项
                mainLogger.warning(f"截图 {screenshotName} 识别结果为空，跳过")
        else:
            mainLogger.warning(f"截图 {screenshotName} 的识别结果格式异常，跳过")
            print(f"截图 {screenshotName} 的识别结果格式异常，跳过")

    mainLogger.info(f"从 tesseractResults 提取到 {len(combinedData)} 条有效绑定数据")
    return combinedData


# 解析 Assets语言配置文件，提取 Map/Player 分类的所有名称
def parseAssetsCategory(assetsData):
    """从assetsData中提取Map分类和Player分类的所有中文名称集合"""
    mapCategory = set()
    playerCategory = set()

    # 提取Map分类的所有项
    if "Map" in assetsData and isinstance(assetsData["Map"], dict):
        mapCategory = set(assetsData["Map"].keys())

    # 提取Player分类（包含R/G/B子分类）的所有项
    if "Player" in assetsData and isinstance(assetsData["Player"], dict):
        for subCategory in ["R", "G", "B"]:
            if subCategory in assetsData["Player"] and isinstance(assetsData["Player"][subCategory], dict):
                playerCategory.update(assetsData["Player"][subCategory].keys())

    mainLogger.info(f"从assetsData解析到Map分类项：{len(mapCategory)} 个, Player分类项：{len(playerCategory)} 个")
    return mapCategory, playerCategory


# 按分类绑定按键（核心逻辑）
def bindKeys(tesseractCombined, keyConfig, mapCategory, playerCategory):
    # 初始化小键盘按键映射（基于basic.json配置）
    numpadKeys = {
        keyConfig["reinforce"]: None,  # 0 → 增援（Map分类）
        keyConfig["supply"]: None,  # . → 重新补给（Map分类）
        keyConfig["map1"]: None,  # 7 → Map分类剩余项第1个
        keyConfig["map2"]: None,  # 8 → Map分类剩余项第2个
        keyConfig["map3"]: None,  # 9 → Map分类剩余项第3个
        keyConfig["player1"]: None,  # 1 → Player分类剩余项第1个
        keyConfig["player2"]: None,  # 2 → Player分类剩余项第2个
        keyConfig["player3"]: None,  # 3 → Player分类剩余项第1个
        keyConfig["player4"]: None,  # 4 → Player分类剩余项第1个
        keyConfig["player5"]: None  # 5 → Player分类剩余项第1个
    }

    # ========== 第一步：处理Map分类 ==========
    # 筛选出Tesseract中属于Map分类的项
    mapItems = [item for item in tesseractCombined.keys() if item in mapCategory and item]
    # 优先绑定「增援」和「重新补给」
    if "增援" in mapItems:
        numpadKeys[keyConfig["reinforce"]] = ("增援", tesseractCombined["增援"])
        mapItems.remove("增援")  # 从剩余项中移除
    if "重新补给" in mapItems:
        numpadKeys[keyConfig["supply"]] = ("重新补给", tesseractCombined["重新补给"])
        mapItems.remove("重新补给")  # 从剩余项中移除
    # Map分类剩余项按顺序绑定到map1/map2/map3
    mapKeyOrder = [keyConfig["map1"], keyConfig["map2"], keyConfig["map3"]]
    for i, item in enumerate(mapItems):
        if i < len(mapKeyOrder):
            numpadKeys[mapKeyOrder[i]] = (item, tesseractCombined[item])

    # 额外功能：绑定地狱火炸弹到第一个可用的Map键
    # hellfireCommand = "wasd"  # 默认指令，可以根据需要修改
    # if "地狱火炸弹" in tesseractCombined:
    #     hellfireCommand = tesseractCombined["地狱火炸弹"]  # 如果在识别结果中有地狱火炸弹的指令，则使用该指令
    # elif "地狱火" in tesseractCombined:
    #     hellfireCommand = tesseractCombined["地狱火"]  # 或者检查是否有"地狱火"

    # 检查哪些map键还没有被绑定（在map1/map2/map3中找第一个空闲的键）
    for mapKey in mapKeyOrder:
        if numpadKeys[mapKey] is None:  # 如果该键还未被使用
            # numpadKeys[mapKey] = ("地狱火炸弹", hellfireCommand)
            mainLogger.info(f"已将'地狱火炸弹'绑定到小键盘 {mapKey} 键")
            print(f"已将'地狱火炸弹'绑定到小键盘 {mapKey} 键")
            break  # 只绑定到第一个可用的键

    # ========== 第二步：处理Player分类 ==========
    # 筛选出Tesseract中属于Player分类的项
    playerItems = [item for item in tesseractCombined.keys() if item in playerCategory and item]
    # Player分类项按顺序绑定到player1-player5
    playerKeyOrder = [
        keyConfig["player1"], keyConfig["player2"], keyConfig["player3"],
        keyConfig["player4"], keyConfig["player5"]
    ]
    for i, item in enumerate(playerItems):
        if i < len(playerKeyOrder):
            numpadKeys[playerKeyOrder[i]] = (item, tesseractCombined[item])

    # 打印绑定结果
    for key, value in numpadKeys.items():
        if value:
            print(f"小键盘 {key} 绑定到: {value[0]} - {value[1]}")

    return numpadKeys


# 将 wasd 转换为方向键
wasdToArrow = {
    "w": "↑",
    "a": "←",
    "s": "↓",
    "d": "→"
}

# 方向键映射，预定义常用键以提高性能
arrowKeysMap = {
    'w': Key.up,
    'a': Key.left,
    's': Key.down,
    'd': Key.right
}


def loadAssetsCategory():
    """从assetsData，返回{战备名称: 分类(Map/R/G/B)}的映射"""
    categoryMap = {}
    currentAssetsData = assetsData  # 使用内嵌数据
    # 处理Map分类
    if "Map" in currentAssetsData and isinstance(currentAssetsData["Map"], dict):
        for name in currentAssetsData["Map"].keys():
            categoryMap[name] = "Map"
    # 处理Player下的R/G/B分类
    if "Player" in currentAssetsData and isinstance(currentAssetsData["Player"], dict):
        for subCat in ["R", "G", "B"]:
            if subCat in currentAssetsData["Player"] and isinstance(currentAssetsData["Player"][subCat], dict):
                for name in currentAssetsData["Player"][subCat].keys():
                    categoryMap[name] = subCat
    return categoryMap


# 优化的按键模拟操作，减少延迟并避免与其他按键冲突
def simulateKeyPress(key, numpadBindings, keyboardController):
    binding = numpadBindings.get(key)
    if binding:
        item, command = binding
        # 将 wasd 转换为方向键字符串
        arrowCommand = "".join(wasdToArrow.get(char, char) for char in command)
        print(f"按下小键盘 {key}，执行命令: {arrowCommand}")

        try:
            # 按住 Ctrl 键
            keyboardController.press(Key.ctrl)
            time.sleep(0.03)  # 短暂等待确保Ctrl键生效

            # 执行组合键 - 按顺序逐个按键，包括重复按键
            for char in command:
                arrowKey = arrowKeysMap.get(char)  # 使用预定义的映射
                if arrowKey:
                    # 按下按键
                    keyboardController.press(arrowKey)
                    time.sleep(0.03)  # 短暂按下时间
                    # 立即释放按键
                    keyboardController.release(arrowKey)
                    time.sleep(0.03)  # 按键间隔

            # 等待一小段时间让游戏响应
            time.sleep(0.03)

            # 松开 Ctrl 键
            keyboardController.release(Key.ctrl)

        except Exception as e:
            mainLogger.error(f"按键模拟失败: {e}")
            print(f"按键模拟失败: {e}")
            # 确保即使出错也释放Ctrl键
            try:
                keyboardController.release(Key.ctrl)
            except:
                pass
            # 清理活跃线程状态
            globalState["activeThreads"].pop(key, None)


# 键盘事件处理函数 - 优化性能
def onPressHandler(key, numpadBindings, keyboardController):
    try:
        # 使用字典查找优化性能
        if hasattr(key, 'vk'):
            # 优化键值判断
            if 96 <= key.vk <= 105:  # 小键盘数字键 0-9
                numKey = str(key.vk - 96)
            elif key.vk == 110:  # 小键盘小数点键
                numKey = "."
            else:
                return  # 不是目标按键，直接返回

            binding = numpadBindings.get(numKey)
            if binding:
                item, command = binding
                # 将 wasd 转换为方向键字符串
                arrowCommand = "".join(wasdToArrow.get(char, char) for char in command)
                print(f"按下了小键盘 {numKey}，绑定到: {item} - {arrowCommand}")

                # 检查是否已有相同按键的线程正在运行
                activeThreads = globalState["activeThreads"]
                if numKey not in activeThreads or not activeThreads[numKey].is_alive():
                    # 在新线程中执行按键模拟，避免阻塞监听器
                    thread = threading.Thread(
                        target=simulateKeyPress,
                        args=(numKey, numpadBindings, keyboardController)
                    )
                    thread.daemon = True  # 设置为守护线程
                    thread.start()
                    # 记录活跃线程
                    activeThreads[numKey] = thread
                else:
                    # 只在调试模式下输出重复触发信息
                    if os.getenv('DEBUG_MODE'):
                        print(f"小键盘 {numKey} 的按键模拟仍在执行中，忽略重复触发")

    except AttributeError:
        pass
    except Exception as e:
        mainLogger.error(f"键盘事件处理出错: {e}")


# 获取绑定信息
def getBindingInfo(numpadBindings):
    bindingInfo = []
    for key, value in numpadBindings.items():
        if value:
            item, command = value
            arrowCommand = "".join(wasdToArrow.get(char, char) for char in command)
            bindingInfo.append(f"{item} \n[{key}] （{arrowCommand}）")
    return bindingInfo


def updateGuiWithMemoryData():
    """使用内存中的数据更新GUI显示"""
    # 从内存中的绑定信息生成显示文本
    if globalState["numpadBindings"]:
        bindingInfo = getBindingInfo(globalState["numpadBindings"])
        if bindingInfo:
            # 拼接为换行分隔的文本（供上色处理）
            displayText = "\n\n".join(bindingInfo) if bindingInfo else "无绑定信息"
            updateWindowContent(displayText)
        else:
            updateWindowContent("识别完成\n暂无绑定信息")
    else:
        updateWindowContent("暂无绑定信息")


def updateWindowContent(text):
    """更新窗口文本：
    1. 顶部固定提示（白色）
    2. 动态内容按assetsData分类上色（Map→黄/R→红/G→绿/B→蓝）
    """
    if not (globalState["initialWindow"] and globalState["windowTextWidget"]):
        return

    # 计算窗口尺寸和位置
    winW, winH, winX, winY = getWindowGeometry()
    try:
        # 清空Text组件
        globalState["windowTextWidget"].delete(1.0, tk.END)

        # 1. 插入固定提示文本（白色）
        globalState["windowTextWidget"].insert(tk.END, fixedPrompt, "fixed")

        # 2. 处理动态内容（区分普通文本和带分类的gui数据）
        if text == "识别中..." or "识别失败" in text:
            # 普通文本（无分类）→ 白色
            globalState["windowTextWidget"].insert(tk.END, text, "normal")
        else:
            # 解析gui.json格式的内容，按分类上色
            categoryMap = loadAssetsCategory()
            # 拆分每行数据（gui.json的每条是一行）
            lines = text.split("\n\n")
            for line in lines:
                if not line.strip():
                    continue
                # 提取战备名称（格式："增援 \n[0] （↑↓→←↑）" → 取"增援"）
                name = line.split(" \n")[0].strip()
                # 获取分类（默认白色）
                cat = categoryMap.get(name, "")
                colorTag = textColors.get(cat, "normal")  # 获取颜色标签名
                # 插入行并设置颜色
                globalState["windowTextWidget"].insert(tk.END, line + "\n\n", colorTag)

        # 更新窗口尺寸+位置
        globalState["initialWindow"].geometry(f"{winW}x{winH}+{winX}+{winY}")
        # 使用after方法延迟刷新，避免在打包环境中出现问题
        globalState["initialWindow"].after(100, lambda: globalState["initialWindow"].update_idletasks())
        globalState["initialWindow"].after(200, lambda: globalState["initialWindow"].update())
    except Exception as e:
        mainLogger.error(f"更新窗口内容失败: {e}")


# 内存中的数据管理函数
def saveTesseractResultsToMemoryOnly(results):
    """仅在内存中保存tesseract结果，不写入文件"""
    global tesseractResults
    tesseractResults = results
    mainLogger.info(f"Tesseract结果已保存到内存，共{len(results)}个项目")


def getGuiDisplayDataFromMemory():
    """从内存中的tesseract结果生成GUI显示数据"""
    if not tesseractResults:
        return []

    # 提取绑定信息并格式化为GUI显示格式
    displayData = []
    for screenshotName, content in tesseractResults.items():
        if isinstance(content, dict):
            for name, command in content.items():
                if name:  # 如果名称不为空
                    arrowCommand = "".join(wasdToArrow.get(char, char) for char in command)
                    displayItem = f"{name} \n[{screenshotName}] （{arrowCommand}）"
                    displayData.append(displayItem)

    return displayData


def keepMouseCentered():
    """持续将鼠标保持在屏幕中心的函数"""
    while globalState["centerMouse"] and globalState["running"]:
        try:
            screenWidth, screenHeight = pyautogui.size()
            centerX, centerY = screenWidth // 2, screenHeight // 2
            currentX, currentY = pyautogui.position()
            
            # 只有当鼠标偏离中心超过一定距离时才移动它
            distanceThreshold = 50  # 设定阈值，只有偏离超过50像素才重新定位
            distance = ((currentX - centerX) ** 2 + (currentY - centerY) ** 2) ** 0.5
            
            if distance > distanceThreshold:
                pyautogui.moveTo(centerX, centerY)
            
            time.sleep(0.05)  # 每50ms检查一次
        except Exception as e:
            mainLogger.error(f"保持鼠标居中失败: {e}")
            time.sleep(0.5)  # 出错时稍长的休眠时间


def runScreenshot():
    """识别流程：截图 → OCR识别 → 执行绑定，读取并显示绑定信息"""
    mainLogger.info("开始执行识别流程")
    try:
        print("开始执行识别流程：截图 → OCR识别 → 内置绑定")
        # 启动鼠标居中线程（如果尚未启动）
        if not globalState["mouseCenteringThread"] or not globalState["mouseCenteringThread"].is_alive():
            globalState["centerMouse"] = True
            mouseCenteringThread = threading.Thread(target=keepMouseCentered, daemon=True)
            mouseCenteringThread.start()
            globalState["mouseCenteringThread"] = mouseCenteringThread
        
        # 1. 直接调用截图功能
        try:
            screenshots = captureScreenshotsToMemory()
            mainLogger.info("截图功能运行成功")
            print("截图功能运行成功")
        except Exception as e:
            mainLogger.error(f"截图失败: {str(e)}")
            raise Exception(f"截图失败: {str(e)}")

        # 2. 直接调用识别功能，传入内存中的截图
        try:
            runOcrRecognition(screenshots)
            mainLogger.info("OCR识别功能运行成功")
            print("OCR识别功能运行成功")
        except Exception as e:
            mainLogger.error(f"OCR识别失败: {str(e)}")
            raise Exception(f"OCR识别失败: {str(e)}")

        # 3. 直接执行绑定逻辑
        try:
            # 加载配置数据
            keyConfig = loadJsonFromEmbeddedData("basic")
            assetsData = loadJsonFromEmbeddedData("assets")

            # 验证核心配置是否有效
            if not tesseractResults or not keyConfig or not assetsData:
                mainLogger.error("tesseractResults/basic配置/assetsData 存在无效配置或数据缺失")
                print("程序退出：tesseractResults/basic配置/assetsData 存在无效配置或数据缺失")
                raise Exception("配置数据缺失或无效")

            # 提取Tesseract数据 + 解析Assets分类
            tesseractCombined = extractTesseractData(tesseractResults)
            mapCategory, playerCategory = parseAssetsCategory(assetsData)

            # 按分类绑定按键
            numpadBindings = bindKeys(tesseractCombined, keyConfig, mapCategory, playerCategory)

            # 输出并保存绑定信息
            bindingInfo = getBindingInfo(numpadBindings)
            for info in bindingInfo:
                print(info)

            # 保存绑定信息以便后续使用
            globalState["numpadBindings"] = numpadBindings
            # 注意：这里不再创建新的监听器，而是继续使用全局监听器

            mainLogger.info("绑定成功，键盘监听器已更新")
            print("绑定成功，键盘监听器已更新")

            # 更新窗口显示绑定信息
            updateGuiWithMemoryData()

        except Exception as e:
            mainLogger.error(f"绑定失败: {e}")
            raise Exception(f"绑定失败: {e}")

    except Exception as e:
        mainLogger.error(f"识别流程执行失败: {e}")
        errText = f"识别失败：\n{str(e)}"
        updateWindowContent(errText)
        print(f"识别流程执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 注意：不再停止鼠标居中，使其在识别后继续运行
        # globalState["centerMouse"] = False
        # if globalState["mouseCenteringThread"]:
        #     try:
        #         globalState["mouseCenteringThread"].join(timeout=1)  # 等待最多1秒让线程结束
        #     except:
        #         pass
        # 重置触发状态，确保无论发生什么情况都会重置
        try:
            globalState["screenshotTriggered"] = False
        except:
            pass
        mainLogger.info("识别流程完成")


def getWindowGeometry():
    """【核心】统一计算窗口尺寸+位置：按比例+最右侧+纵向居中"""
    try:
        screenWidth, screenHeight = pyautogui.size()
        # 按比例计算窗口宽高，强制转整数（像素必须为整数）
        winW = int(screenWidth * windowWidthScale)
        winH = int(screenHeight * windowHeightScale)
        # 原始位置：窗口靠右对齐
        # 计算原始靠右位置
        baseX = screenWidth - winW
        # 向右移动100像素
        winX = baseX
        # 确保窗口不会完全移出屏幕右边
        # 如果移动后窗口完全超出屏幕，则调整位置使窗口部分可见
        if winX + winW > screenWidth:
            # 窗口右边缘超出屏幕，调整到屏幕右边缘
            winX = screenWidth - winW
        # 纵向居中 = (屏幕高度 - 窗口高度) // 2
        winY = (screenHeight - winH) // 2
        return winW, winH, winX, winY
    except Exception as e:
        mainLogger.error(f"获取屏幕几何信息失败: {e}")
        # 返回默认值
        return 400, 800, 2160, 320  # 假设分辨率为2560x1440


def createInitialWindow():
    """创建初始窗口，尺寸/位置按比例计算，实现鼠标穿透+低透明度，适配多色Text组件"""
    mainLogger.info("创建初始窗口")
    root = tk.Tk()
    winW, winH, winX, winY = getWindowGeometry()

    # 窗口基础样式（无边框、黑色背景、置顶）
    root.geometry(f"{winW}x{winH}+{winX}+{winY}")
    root.overrideredirect(True)
    root.config(bg="#1a1a1a")  # 更浅一点的灰色背景，避免全黑

    # 设置窗口透明度，范围0.0到1.0，1.0为完全不透明
    root.attributes("-alpha", 0.95)  # 调整透明度，平衡文字清晰度与视觉效果
    # 2. 启用鼠标穿透设置
    if sys.platform == 'win32':
        try:
            # 尝试设置鼠标穿透
            root.attributes("-transparentcolor", "#1a1a1a")  # 浅灰色区域鼠标穿透
        except Exception as e:
            mainLogger.warning(f"鼠标穿透设置失败: {e}")
            # 如果失败，回退到不使用鼠标穿透
            pass
    root.attributes("-topmost", True)

    # 创建Text组件（替代原Label，支持多色文本）
    print("正在创建Text组件...")
    customFont = font.Font(family="微软雅黑", size=12)  # 增大字体从10到12
    textWidget = tk.Text(
        root, font=customFont, bg="#1a1a1a", fg="white",  # 匹配窗口背景色
        wrap=tk.WORD, bd=0, highlightthickness=0, padx=10, pady=10
    )
    print("Text组件创建完成")
    textWidget.pack(expand=True, fill=tk.BOTH)

    # 配置文本标签颜色
    print("正在配置文本标签颜色...")
    textWidget.tag_configure("fixed", foreground="white")  # 固定提示→白色
    textWidget.tag_configure("normal", foreground="white")  # 普通文本→白色
    textWidget.tag_configure("yellow", foreground="#FFD700")  # 金色（较柔和的黄色）
    textWidget.tag_configure("red", foreground="#FFA07A")  # 浅珊瑚红（较柔和的红色）
    textWidget.tag_configure("green", foreground="#98FB98")  # 浅绿色（较柔和的绿色）
    textWidget.tag_configure("blue", foreground="#87CEEB")  # 天蓝色（较柔和的蓝色）
    print("文本标签颜色配置完成")

    # 初始文本
    print("正在插入初始文本...")
    textWidget.insert(tk.END, fixedPrompt + "等待识别...", "fixed")
    print("初始文本插入完成")
    # 禁止编辑
    print("正在设置文本组件为只读状态...")
    textWidget.config(state=tk.DISABLED)  # 先禁用，更新时临时启用
    print("文本组件已设置为只读状态")

    # 添加滚动条支持
    print("正在添加滚动条...")
    scrollbar = tk.Scrollbar(root, command=textWidget.yview, bg='#333333', troughcolor='#222222')
    textWidget.config(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    print("滚动条添加完成")

    # 保存组件引用
    print("正在保存组件引用...")
    globalState["windowTextWidget"] = textWidget
    globalState["initialWindow"] = root
    print("组件引用保存完成")
    mainLogger.info(f"初始窗口已创建，尺寸 {winW}x{winH} | 位置 ({winX},{winY})")
    print(f"初始窗口参数：尺寸 {winW}x{winH} | 位置 ({winX},{winY})")
    print("初始窗口已创建并显示（透明度0.9，鼠标穿透）")
    
    # 添加额外的调试信息
    print("=== 窗口创建完成 ===")
    print(f"窗口宽度: {winW}")
    print(f"窗口高度: {winH}")
    print(f"窗口X坐标: {winX}")
    print(f"窗口Y坐标: {winY}")
    try:
        screenWidth, screenHeight = pyautogui.size()
        print(f"屏幕宽度: {screenWidth}")
        print(f"屏幕高度: {screenHeight}")
    except Exception as e:
        print(f"获取屏幕尺寸失败: {e}")
    return root


def main():
    mainLogger.info("程序启动")
    # 修复Text组件更新权限：封装updateWindowContent中临时启用/禁用
    def _safeUpdate(func):
        def wrapper(*args, **kwargs):
            if globalState["windowTextWidget"]:
                globalState["windowTextWidget"].config(state=tk.NORMAL)
            result = func(*args, **kwargs)
            if globalState["windowTextWidget"]:
                globalState["windowTextWidget"].config(state=tk.DISABLED)
            return result

        return wrapper

    global updateWindowContent
    updateWindowContent = _safeUpdate(updateWindowContent)

    # 获取屏幕分辨率并保存到basic.json
    try:
        screenWidth, screenHeight = pyautogui.size()
        mainLogger.info(f"当前屏幕分辨率: 宽={screenWidth}px, 高={screenHeight}px")
        print(f"当前屏幕分辨率: 宽={screenWidth}px, 高={screenHeight}px")
        # 更新内嵌配置数据
        global basicConfig
        basicConfig["screen_width"] = screenWidth
        basicConfig["screen_height"] = screenHeight
    except Exception as e:
        mainLogger.error(f"获取屏幕分辨率失败: {e}")
        print(f"获取屏幕分辨率失败: {e}")
        return

    # 创建窗口
    initialWindow = createInitialWindow()
    # 程序启动时先显示等待识别状态
    updateWindowContent("等待识别...")

    # 启动全局热键监听器（F11和F12）
    hotkey_listener = setup_global_hotkeys()
    # 在单独的线程中运行全局热键监听器
    hotkey_thread = threading.Thread(target=hotkey_listener.run)
    hotkey_thread.daemon = True
    hotkey_thread.start()
    
    # 启动键盘监听器（仅用于处理小键盘按键）
    listener = keyboard.Listener(on_press=onPress)
    listener.start()
    mainLogger.info("键盘监听器已启动")
    
    globalState["bindProcess"] = listener  # 将主监听器也存储在globalState中
    initialWindow.mainloop()

    # 程序退出清理
    try:
        hotkey_listener.stop()
    except:
        pass
    try:
        listener.stop()
    except:
        pass
    if globalState["bindProcess"] and globalState["bindProcess"] != listener:
        try:
            globalState["bindProcess"].stop()
        except Exception as e:
            mainLogger.error(f"终止键盘监听器失败: {e}")
    
    # 停止鼠标居中功能（如果正在运行）
    globalState["centerMouse"] = False
    if globalState["mouseCenteringThread"]:
        try:
            globalState["mouseCenteringThread"].join(timeout=1)  # 等待最多1秒让线程结束
        except:
            pass
    
    mainLogger.info("程序已退出")


if __name__ == "__main__":
    if sys.platform == 'win32':
        os.system('chcp 65001 >nul')  # Windows终端UTF-8编码
    main()