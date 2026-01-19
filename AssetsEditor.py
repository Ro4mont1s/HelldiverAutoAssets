import tkinter as tk
from tkinter import messagebox
import json
import os

# -------------------------- 全局配置 & 工具函数 --------------------------
# 使用绝对路径
scriptDir = os.path.dirname(os.path.abspath(__file__))
configDir = os.path.join(scriptDir, "Config")
# 默认使用简体中文配置文件
assetsJson = os.path.join(configDir, "Assets", "chi_sim.json")
wasdToArrow = {"w": "↑", "a": "←", "s": "↓", "d": "→"}
arrowToWasd = {v: k for k, v in wasdToArrow.items()}


def loadAssets():
    """加载Assets.json，适配Player下R/G/B子分类结构"""
    if not os.path.exists(configDir):
        os.makedirs(configDir)
    
    # 确保Assets子目录存在
    assetsDir = os.path.join(configDir, "Assets")
    if not os.path.exists(assetsDir):
        os.makedirs(assetsDir)
        
    try:
        with open(assetsJson, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 确保基础结构完整（Map/Player + Player下R/G/B）
            if not isinstance(data, dict):
                data = {"Map": {}, "Player": {"R": {}, "G": {}, "B": {}}}
            if "Map" not in data:
                data["Map"] = {}
            if "Player" not in data:
                data["Player"] = {"R": {}, "G": {}, "B": {}}
            else:
                # 确保Player下有R/G/B子分类
                for subCat in ["R", "G", "B"]:
                    if subCat not in data["Player"] or not isinstance(data["Player"][subCat], dict):
                        data["Player"][subCat] = {}
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        # 初始化默认结构（包含R/G/B）
        defaultData = {"Map": {}, "Player": {"R": {}, "G": {}, "B": {}}}
        saveAssets(defaultData)
        return defaultData


def saveAssets(assetsDict):
    """保存Assets.json，适配嵌套结构（箭头转WASD）"""

    # 递归转换箭头为WASD（适配Map/Player/R/G/B多层结构）
    def convertArrowToWasd(data):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    # 字符串则转换箭头→WASD
                    data[k] = "".join(arrowToWasd.get(char, char) for char in v)
                elif isinstance(v, dict):
                    # 字典则递归处理
                    convertArrowToWasd(v)

    # 深拷贝避免修改原字典
    import copy
    saveData = copy.deepcopy(assetsDict)
    convertArrowToWasd(saveData)

    # 确保Assets目录存在
    assetsDir = os.path.dirname(assetsJson)
    if not os.path.exists(assetsDir):
        os.makedirs(assetsDir)

    with open(assetsJson, "w", encoding="utf-8") as f:
        json.dump(saveData, f, ensure_ascii=False, indent=4)


# -------------------------- 窗口核心逻辑 --------------------------
class AssetsEditorWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("编辑战备")
        self.assetsDict = loadAssets()
        self.selectedKey = None
        self.listMapping = []
        self.category = "Map"  # 主类别：Map/Player
        self.playerSubCat = "R"  # Player子分类：R/G/B（默认R）

        # 窗口600x450居中（加高适配新增的子分类选择）
        self.centerWindow(600, 450)

        # 左右分栏
        self.leftFrame = tk.Frame(root, width=300, height=450, padx=8, pady=8)
        self.rightFrame = tk.Frame(root, width=300, height=450, padx=8, pady=8)
        self.leftFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.rightFrame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # -------------------------- 左侧布局 --------------------------
        tk.Label(self.leftFrame, text="添加战备", font=("微软雅黑", 14)).pack(anchor=tk.NW, pady=(0, 8))
        tk.Label(self.leftFrame, text="输入战备名称：").pack(anchor=tk.NW)
        self.entry1 = tk.Entry(self.leftFrame, width=20, font=("微软雅黑", 12))
        self.entry1.pack(anchor=tk.NW, pady=(0, 8))

        # 输入框2（支持删除/方向键 + 仅显示箭头）
        tk.Label(self.leftFrame, text="输入对应的QTE：").pack(anchor=tk.NW)
        self.entry2 = tk.Entry(self.leftFrame, width=20, font=("微软雅黑", 12))
        self.entry2.pack(anchor=tk.NW, pady=(0, 8))
        # 绑定按键事件（精准过滤）
        self.entry2.bind("<Key>", self.onWasdInput)

        self.addBtn = tk.Button(self.leftFrame, text="添加", font=("微软雅黑", 12), width=8, command=self.addAsset)
        self.addBtn.pack(anchor=tk.NW, pady=(15, 0))

        # 主类别选择（Map/Player）
        tk.Label(self.leftFrame, text="主分类：", font=("微软雅黑", 10)).pack(anchor=tk.NW, pady=(10, 0))
        self.categoryVar = tk.StringVar(value="Map")
        self.mapRadio = tk.Radiobutton(self.leftFrame, text="地图战备", variable=self.categoryVar, value="Map",
                                        command=self.updateCategory)
        self.playerRadio = tk.Radiobutton(self.leftFrame, text="自选战备", variable=self.categoryVar, value="Player",
                                           command=self.updateCategory)
        self.mapRadio.pack(anchor=tk.NW, pady=(0, 0))
        self.playerRadio.pack(anchor=tk.NW, pady=(0, 8))

        # Player子分类选择（R/G/B，仅Player选中时显示）
        self.playerSubFrame = tk.Frame(self.leftFrame)
        tk.Label(self.playerSubFrame, text="战备分类：", font=("微软雅黑", 10)).pack(anchor=tk.NW)
        self.subCatVar = tk.StringVar(value="R")
        self.rRadio = tk.Radiobutton(self.playerSubFrame, text="红战备", variable=self.subCatVar, value="R",
                                      command=self.updateSubCategory)
        self.gRadio = tk.Radiobutton(self.playerSubFrame, text="绿战备", variable=self.subCatVar, value="G",
                                      command=self.updateSubCategory)
        self.bRadio = tk.Radiobutton(self.playerSubFrame, text="蓝战备", variable=self.subCatVar, value="B",
                                      command=self.updateSubCategory)
        self.rRadio.pack(anchor=tk.NW, side=tk.LEFT, padx=(0, 10))
        self.gRadio.pack(anchor=tk.NW, side=tk.LEFT, padx=(0, 10))
        self.bRadio.pack(anchor=tk.NW, side=tk.LEFT)
        # 默认隐藏子分类选择框（仅选Player时显示）
        self.playerSubFrame.pack_forget()  # 初始隐藏，替代错误的state设置

        # -------------------------- 右侧布局 --------------------------
        tk.Label(self.rightFrame, text="已读取配置，选中项可删除", font=("微软雅黑", 14)).pack(anchor=tk.NW,
                                                                                               pady=(0, 8))

        # 列表框
        self.listBoxFrame = tk.Frame(self.rightFrame)
        self.listBox = tk.Listbox(self.listBoxFrame, width=25, height=12, font=("微软雅黑", 12))
        self.scrollbar = tk.Scrollbar(self.listBoxFrame, orient=tk.VERTICAL, command=self.listBox.yview)
        self.listBox.config(yscrollcommand=self.scrollbar.set)
        self.listBox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listBoxFrame.pack(anchor=tk.NW, pady=(0, 5), fill=tk.X)

        self.listBox.bind("<<ListboxSelect>>", self.onListboxSelect)
        self.delBtn = tk.Button(self.rightFrame, text="删除", font=("微软雅黑", 12), width=8, state=tk.DISABLED,
                                 command=self.deleteAsset)
        self.delBtn.pack(anchor=tk.NW)

        self.refreshListbox()

    def centerWindow(self, width, height):
        screenWidth = self.root.winfo_screenwidth()
        screenHeight = self.root.winfo_screenheight()
        x = (screenWidth - width) // 2
        y = (screenHeight - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def onWasdInput(self, event):
        """精准过滤：WASD转箭头，保留删除/方向键，阻止无关按键"""
        key = event.keysym.lower()
        # 1. 允许的功能键：删除（BackSpace）、左方向键（Left）、右方向键（Right）
        allowKeys = ["backspace", "left", "right"]
        if key in allowKeys:
            return  # 放行，允许正常操作

        # 2. 处理WASD键（转箭头，阻止原始字母）
        if key in wasdToArrow:
            # 获取当前光标位置
            cursorPos = self.entry2.index(tk.INSERT)
            # 获取当前输入框内容
            currentText = self.entry2.get()
            # 插入对应箭头（在光标位置插入）
            newText = currentText[:cursorPos] + wasdToArrow[key] + currentText[cursorPos:]
            # 更新输入框
            self.entry2.delete(0, tk.END)
            self.entry2.insert(0, newText)
            # 恢复光标位置（后移一位）
            self.entry2.icursor(cursorPos + 1)
            return "break"  # 阻止WASD字母显示

        # 3. 其他无关按键（数字/其他字母）：阻止输入
        return "break"

    def updateCategory(self):
        """切换主分类（Map/Player）"""
        self.category = self.categoryVar.get()
        # 显示/隐藏Player子分类选择框
        if self.category == "Player":
            self.playerSubFrame.pack(anchor=tk.NW, pady=(0, 10))
            self.playerSubCat = self.subCatVar.get()
        else:
            self.playerSubFrame.pack_forget()
        self.refreshListbox()

    def updateSubCategory(self):
        """切换Player子分类（R/G/B）"""
        self.playerSubCat = self.subCatVar.get()
        self.refreshListbox()

    def refreshListbox(self):
        """刷新列表框，适配Map/Player-R/G/B结构"""
        self.listBox.delete(0, tk.END)
        self.listMapping = []
        # 根据主分类加载对应数据
        if self.category == "Map":
            # Map分类：单层结构
            data = self.assetsDict["Map"]
            for key, value in data.items():
                arrowValue = "".join(wasdToArrow.get(char, char) for char in value)
                self.listMapping.append((key, value))
                self.listBox.insert(tk.END, f"{key} : {arrowValue}")
        elif self.category == "Player":
            # Player分类：加载选中的R/G/B子分类数据
            data = self.assetsDict["Player"][self.playerSubCat]
            for key, value in data.items():
                arrowValue = "".join(wasdToArrow.get(char, char) for char in value)
                self.listMapping.append((key, value))
                self.listBox.insert(tk.END, f"{key} : {arrowValue}")
        # 重置选中状态
        self.selectedKey = None
        self.delBtn.config(state=tk.DISABLED)

    def onListboxSelect(self, event):
        """列表选中事件"""
        selectedIndices = self.listBox.curselection()
        if selectedIndices:
            idx = selectedIndices[0]
            self.selectedKey = self.listMapping[idx][0]
            self.delBtn.config(state=tk.NORMAL)
        else:
            self.selectedKey = None
            self.delBtn.config(state=tk.DISABLED)

    def addAsset(self):
        """添加战备（适配新结构）"""
        key = self.entry1.get().strip()
        value = self.entry2.get().strip()
        if not key:
            messagebox.warning("提示", "输入框1不能为空！")
            return
        if not value:
            messagebox.warning("提示", "输入框2不能为空！")
            return

        # 根据主分类写入对应位置
        if self.category == "Map":
            self.assetsDict["Map"][key] = value
        elif self.category == "Player":
            self.assetsDict["Player"][self.playerSubCat][key] = value

        # 保存并刷新
        saveAssets(self.assetsDict)
        self.refreshListbox()
        # 清空输入框
        self.entry1.delete(0, tk.END)
        self.entry2.delete(0, tk.END)
        messagebox.showinfo("成功", f"已添加：{key} : {value}")

    def deleteAsset(self):
        """删除战备（适配新结构）"""
        if not self.selectedKey:
            messagebox.warning("提示", "请先选中要删除的项！")
            return
        if not messagebox.askyesno("确认", f"是否删除：{self.selectedKey}？"):
            return

        # 根据主分类删除对应位置的项
        if self.category == "Map":
            if self.selectedKey in self.assetsDict["Map"]:
                del self.assetsDict["Map"][self.selectedKey]
        elif self.category == "Player":
            if self.selectedKey in self.assetsDict["Player"][self.playerSubCat]:
                del self.assetsDict["Player"][self.playerSubCat][self.selectedKey]

        # 保存并刷新
        saveAssets(self.assetsDict)
        self.refreshListbox()
        messagebox.showinfo("成功", f"已删除：{self.selectedKey}")


# -------------------------- 程序入口 --------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = AssetsEditorWindow(root)
    root.mainloop()