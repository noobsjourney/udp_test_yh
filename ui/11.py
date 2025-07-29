from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QObject, QThread,pyqtSignal, pyqtSlot

class PageBase(QtCore.QObject):
    """页面基类，包含通用功能"""
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name  # 保存页面名称
        self.page = QtWidgets.QWidget(parent)
        self.add_page()
    
    def add_page(self):
        self.page.setObjectName(self.name)
        self.page.setStyleSheet("border: 1px solid black;")
        
        # 添加页面特定的布局和控件
        self.comboBox = QtWidgets.QComboBox(self.page)
        self.comboBox.setGeometry(QtCore.QRect(190, 30, 390, 20))
        self.comboBox.setObjectName("comboBox")
        self.comboBox.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #8f8f91;
                border-radius: 3px;
                padding: 1px 18px 1px 3px;
                min-width: 6em;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 1px;
                border-left-color: darkgray;
                border-left-style: solid;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            QComboBox::down-arrow {
                image: url(images/down_arrow.png);
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid darkgray;
                selection-background-color: #a0c0ff;
                selection-color: black;
            }
        """)
        self.comboBox.currentIndexChanged.connect(self.handle_combo_selection)
        
        self.textEdit = QtWidgets.QTextEdit(self.page)
        self.textEdit.setGeometry(QtCore.QRect(90, 140, 251, 311))
        self.textEdit.setObjectName("textEdit")
        self.textEdit.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.textEdit.setReadOnly(True)
        self.textEdit.ensureCursorVisible()
        
        self.textEdit_2 = QtWidgets.QTextEdit(self.page)
        self.textEdit_2.setGeometry(QtCore.QRect(550, 140, 221, 321))
        self.textEdit_2.setObjectName("textEdit_2")
        self.textEdit_2.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.textEdit_2.setReadOnly(True)
        self.textEdit_2.ensureCursorVisible()
        
        self.imageLabel = QtWidgets.QLabel(self.page)
        self.imageLabel.setGeometry(QtCore.QRect(110, 490, 601, 110))
        self.imageLabel.setObjectName("imageLabel")
        self.imageLabel.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #8f8f91;
                border-radius: 3px;
            }
        """)
        self.imageLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        self.pushButton = QtWidgets.QPushButton(self.page)
        self.pushButton.setGeometry(QtCore.QRect(160, 70, 75, 23))
        self.pushButton.setObjectName("pushButton")
        self.pushButton.clicked.connect(self.on_button1_clicked)
        
        self.pushButton_2 = QtWidgets.QPushButton(self.page)
        self.pushButton_2.setGeometry(QtCore.QRect(590, 80, 75, 23))
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_2.clicked.connect(self.on_button2_clicked)
    
    def set_label_image(self, image_path: str):
        if not image_path:
            self.imageLabel.clear()
            return
        
        pixmap = QtGui.QPixmap(image_path)
        if pixmap.isNull():
            print(f"错误：无法加载图片 '{image_path}'")
            return
        
        scaled_pixmap = pixmap.scaled(
            self.imageLabel.width(),
            self.imageLabel.height(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.imageLabel.setPixmap(scaled_pixmap)

    def set_combo_options(self, options: list):
        self.comboBox.clear()
        if len(options) > 8:
            options = options[:8]
            print(f"警告：下拉框最多支持8个选项，已截断为前8项") 
        for option in options:
            self.comboBox.addItem(option)            
        if options:
            self.comboBox.setCurrentIndex(0)
    
    def handle_combo_selection(self, index):
        selected_text = self.comboBox.currentText()
        if index == 0:
            self.comboBox1_1(selected_text)
        elif index == 1:
            self.comboBox1_2(selected_text)
        elif index == 2:
            self.comboBox1_3(selected_text)
        elif index == 3:
            self.comboBox1_4(selected_text)
        elif index == 4:
            self.comboBox1_5(selected_text)
        elif index == 5:
            self.comboBox1_6(selected_text)
        elif index == 6:
            self.comboBox1_7(selected_text)
        elif index == 7:
            self.comboBox1_8(selected_text)
    
    # 定义8个槽函数，用户可在子类中重写
    def comboBox1_1(self, selected_text): pass
    def comboBox1_2(self, selected_text): pass
    def comboBox1_3(self, selected_text): pass
    def comboBox1_4(self, selected_text): pass
    def comboBox1_5(self, selected_text): pass
    def comboBox1_6(self, selected_text): pass
    def comboBox1_7(self, selected_text): pass
    def comboBox1_8(self, selected_text): pass
    
    # 按钮点击事件处理函数 - 需要在子类中重写
    def on_button1_clicked(self):
        print(f"Button 1 clicked on {self.name} (default handler)")
        self.set_textEdit_text(f"Button 1 clicked on {self.name}")
    
    def on_button2_clicked(self):
        print(f"Button 2 clicked on {self.name} (default handler)")
        self.set_textEdit_2_text(f"Button 2 clicked on {self.name}")
    
    def set_pushButton_text(self, text: str):
        self.pushButton.setText(text)
    
    def set_pushButton_2_text(self, text: str):
        self.pushButton_2.setText(text)
    
    def set_textEdit_text(self, text: str):
        formatted_text = text.replace('\n', '<br>').replace(' ', '&nbsp;')
        current_html = self.textEdit.toHtml()
        if current_html:
            current_html += "<br>"
        new_html = current_html + formatted_text
        self.textEdit.setHtml(new_html)
        self.scroll_to_bottom(self.textEdit)
    
    def set_textEdit_2_text(self, text: str):
        formatted_text = text.replace('\n', '<br>').replace(' ', '&nbsp;')
        current_html = self.textEdit_2.toHtml()
        if current_html:
            current_html += "<br>"
        new_html = current_html + formatted_text
        self.textEdit_2.setHtml(new_html)
        self.scroll_to_bottom(self.textEdit_2)
    
    def scroll_to_bottom(self, text_edit):
        cursor = text_edit.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        text_edit.setTextCursor(cursor)
        text_edit.ensureCursorVisible()
        scrollbar = text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class DeviceMonitorPage(PageBase,QObject):
    """设备监控页面 - 定制化实现"""
    test=pyqtSignal(str)
    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
  
        
        self.set_pushButton_text("开始监控")
        self.set_pushButton_2_text("停止监控")
        self.set_textEdit_text("设备监控页面已加载")
        devices = ["设备1: 频谱分析仪", "设备2: 信号发生器", "设备3: 网络分析仪", 
                   "设备4: 功率计", "设备5: 示波器", "设备6: 逻辑分析仪"]
        self.set_combo_options(devices)
        self.pushButton.clicked.connect(self.on_button1_clicked1)
        self.test.connect(self.on_test)
    def on_test(str):
        str=str
        print("测试emit",str)
    def on_button1_clicked1(self):
        print("槽函数复用")
    def on_button1_clicked(self):
        print("开始监控按钮被点击")
        self.set_textEdit_text("开始监控设备...")
        self.test.emit("1")
    def on_button2_clicked(self):
        print("停止监控按钮被点击")
        self.set_textEdit_text("停止监控设备...")
        self.test.emit("2")
    def comboBox1_1(self, selected_text):
        self.set_label_image(r"E:\aliyun\ui\1.png")
    
    def comboBox1_2(self, selected_text):
        self.set_label_image(r"E:\aliyun\ui\2.png")

class SpectrumAnalysisPage(PageBase):
    """频谱分析页面 - 定制化实现"""
    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
        self.set_pushButton_text("分析频谱")
        self.set_pushButton_2_text("导出数据")
        self.set_textEdit_text("频谱分析页面已加载")
    
    def on_button1_clicked(self):
        print("分析频谱按钮被点击")
        self.set_textEdit_text("正在分析频谱数据...")
    
    def on_button2_clicked(self):
        print("导出数据按钮被点击")
        self.set_textEdit_text("正在导出频谱数据...")

class LogViewPage(PageBase):
    """日志查看页面 - 定制化实现"""
    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
        self.set_pushButton_text("刷新日志")
        self.set_pushButton_2_text("清除日志")
        self.set_textEdit_text("日志查看页面已加载")
    
    def on_button1_clicked(self):
        print("刷新日志按钮被点击")
        self.set_textEdit_text("正在刷新日志...")
    
    def on_button2_clicked(self):
        print("清除日志按钮被点击")
        self.set_textEdit_text("正在清除日志...")

class PluginPage1(PageBase):
    """插件页面1 - 定制化实现"""
    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
        self.set_pushButton_text("运行插件")
        self.set_pushButton_2_text("停止插件")
        self.set_textEdit_text("插件页面1已加载")
        plugins = ["插件功能1", "插件功能2", "高级分析", "数据导出", "系统优化"]
        self.set_combo_options(plugins)
    
    def on_button1_clicked(self):
        print("运行插件按钮被点击")
        self.set_textEdit_text("正在运行插件功能...")
    
    def on_button2_clicked(self):
        print("停止插件按钮被点击")
        self.set_textEdit_text("插件功能已停止")

class PluginPage2(PageBase):
    """插件页面2 - 定制化实现"""
    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
        self.set_pushButton_text("启动工具")
        self.set_pushButton_2_text("保存结果")
        self.set_textEdit_text("插件页面2已加载")
        tools = ["工具A", "工具B", "工具C", "工具D"]
        self.set_combo_options(tools)
    
    def on_button1_clicked(self):
        print("启动工具按钮被点击")
        self.set_textEdit_text("工具已启动...")
    
    def on_button2_clicked(self):
        print("保存结果按钮被点击")
        self.set_textEdit_text("结果已保存")

class CreateStackedWidget():
    """创建和管理堆叠窗口的类，自动生成页面切换按钮"""
    def __init__(self, parent=None):
        self.container = QtWidgets.QWidget(parent)
        self.container.setObjectName("stackedWidgetContainer")
        
        self.layout = QtWidgets.QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.button_container = QtWidgets.QWidget(self.container)
        self.button_container.setFixedHeight(30)
        self.button_container.setStyleSheet("background-color: #f0f0f0; border-bottom: 1px solid #ccc;")
        
        self.button_layout = QtWidgets.QHBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(5, 0, 5, 0)
        self.button_layout.setSpacing(5)
        
        self.layout.addWidget(self.button_container)
        
        self.stackedWidget = QtWidgets.QStackedWidget(self.container)
        self.stackedWidget.setObjectName("stackedWidget")
        self.layout.addWidget(self.stackedWidget)
        
        self.pages = {}  # 存储所有页面的字典
        self.buttons = {}  # 存储所有按钮的字典
    
    def add_page(self, page_instance):
        page_name = page_instance.name
        
        self.stackedWidget.addWidget(page_instance.page)
        self.pages[page_name] = page_instance
        
        button = QtWidgets.QPushButton(self.button_container)
        button.setText(page_name)
        button.setFixedSize(80, 25)
        button.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                border: 1px solid #aaa;
                border-radius: 4px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:checked {
                background-color: #a0c0ff;
                font-weight: bold;
            }
        """)
        button.setCheckable(True)
        button.clicked.connect(lambda: self.set_current_page(page_name))
        self.button_layout.addWidget(button)
        self.buttons[page_name] = button
        
        if len(self.pages) == 1:
            button.setChecked(True)
        
        return page_instance
    
    def get_page(self, page_name: str):
        return self.pages.get(page_name)
    
    def set_current_page(self, page_name: str):
        for name, button in self.buttons.items():
            button.setChecked(name == page_name)
        
        for i in range(self.stackedWidget.count()):
            if self.stackedWidget.widget(i).objectName() == page_name:
                self.stackedWidget.setCurrentIndex(i)
                return True
        return False
    
    def widget(self):
        return self.container

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1128, 867)
        MainWindow.setStyleSheet("")
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setStyleSheet("background-color: rgb(255, 255, 255);")
        self.centralwidget.setObjectName("centralwidget")
        
        # 创建主垂直布局
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        
        # 顶部标题栏
        self.textBrowser = QtWidgets.QTextBrowser()
        self.textBrowser.setMinimumSize(QtCore.QSize(0, 60))
        self.textBrowser.setMaximumSize(QtCore.QSize(16777215, 60))
        self.textBrowser.setObjectName("textBrowser")
        self.verticalLayout.addWidget(self.textBrowser)
        
        # 主内容区域（水平布局：侧边栏 + 堆叠窗口）
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        
        # 左侧面板
        self.leftPanel = QtWidgets.QWidget()
        self.leftPanel.setMinimumSize(QtCore.QSize(170, 0))
        self.leftPanel.setMaximumSize(QtCore.QSize(170, 16777215))
        self.leftPanel.setObjectName("leftPanel")
        
        # 左侧面板内容
        self.textBrowser_2 = QtWidgets.QTextBrowser(self.leftPanel)
        self.textBrowser_2.setGeometry(QtCore.QRect(0, 0, 171, 241))
        self.textBrowser_2.setObjectName("textBrowser_2")
        
        self.textBrowser_3 = QtWidgets.QTextBrowser(self.leftPanel)
        self.textBrowser_3.setGeometry(QtCore.QRect(0, 300, 171, 341))
        self.textBrowser_3.setObjectName("textBrowser_3")
        
        self.button_note_name = QtWidgets.QPushButton(self.leftPanel)
        self.button_note_name.setGeometry(QtCore.QRect(80, 240, 75, 23))
        self.button_note_name.setObjectName("button_note_name")
        self.button_note_name.clicked.connect(self.on_note_name_clicked)
        
        self.horizontalLayout.addWidget(self.leftPanel)
        
        # 创建外层堆叠窗口，用于切换两个堆叠窗口管理器
        self.outer_stacked_widget = QtWidgets.QStackedWidget()
        
        # 创建主堆叠窗口管理器（主功能）
        self.main_stacked_manager = CreateStackedWidget()
        # 创建插件堆叠窗口管理器（插件功能）
        self.plugin_stacked_manager = CreateStackedWidget()
        
        # 将两个堆叠窗口管理器添加到外层堆叠窗口
        self.outer_stacked_widget.addWidget(self.main_stacked_manager.widget())
        self.outer_stacked_widget.addWidget(self.plugin_stacked_manager.widget())
        
        # 设置默认显示主堆叠窗口
        self.outer_stacked_widget.setCurrentIndex(0)
        
        # 为主堆叠窗口添加页面
        self.device_page = DeviceMonitorPage("设备监控")
        self.spectrum_page = SpectrumAnalysisPage("频谱分析")
        self.log_page = LogViewPage("日志查看")
        self.main_stacked_manager.add_page(self.device_page)
        self.main_stacked_manager.add_page(self.spectrum_page)
        self.main_stacked_manager.add_page(self.log_page)
        
        # 为插件堆叠窗口添加页面
        self.plugin_page1 = PluginPage1("插件功能1")
        self.plugin_page2 = PluginPage2("插件功能2")
        self.plugin_stacked_manager.add_page(self.plugin_page1)
        self.plugin_stacked_manager.add_page(self.plugin_page2)
        
        # 创建右侧布局（包含外层堆叠窗口）
        self.rightLayout = QtWidgets.QVBoxLayout()
        self.rightLayout.setContentsMargins(0, 0, 0, 0)
        self.rightLayout.setSpacing(0)
        self.rightLayout.addWidget(self.outer_stacked_widget)
        
        self.horizontalLayout.addLayout(self.rightLayout)
        self.verticalLayout.addLayout(self.horizontalLayout)
        
        MainWindow.setCentralWidget(self.centralwidget)
        
        # 菜单栏
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1128, 23))
        self.menubar.setObjectName("menubar")
        self.menu = QtWidgets.QMenu(self.menubar)
        self.menu.setObjectName("menu")
        self.menu_2 = QtWidgets.QMenu(self.menubar)
        self.menu_2.setObjectName("menu_2")
        self.menu_3 = QtWidgets.QMenu(self.menubar)
        self.menu_3.setObjectName("menu_3")
        MainWindow.setMenuBar(self.menubar)
        
        # 创建动作
        self.actionaadd = QtWidgets.QAction(MainWindow)
        self.actionaadd.setObjectName("actionaadd")
        self.actionadddd = QtWidgets.QAction(MainWindow)
        self.actionadddd.setObjectName("actionadddd")
        self.actionjiazai = QtWidgets.QAction(MainWindow)
        self.actionjiazai.setObjectName("actionjiazai")
        self.actionxiezai = QtWidgets.QAction(MainWindow)
        self.actionxiezai.setObjectName("actionxiezai")
        self.actiongengxin = QtWidgets.QAction(MainWindow)
        self.actiongengxin.setObjectName("actiongengxin")
        self.actionzhuye = QtWidgets.QAction(MainWindow)
        self.actionzhuye.setObjectName("actionzhuye")
        self.actionzhuye2 = QtWidgets.QAction(MainWindow)
        self.actionzhuye2.setObjectName("actionzhuye2")
        self.actionzhuye3 = QtWidgets.QAction(MainWindow)
        self.actionzhuye3.setObjectName("actionzhuye3")
        self.actionrizhichakan = QtWidgets.QAction(MainWindow)
        self.actionrizhichakan.setObjectName("actionrizhichakan")
        self.actiondakai = QtWidgets.QAction(MainWindow)
        self.actiondakai.setObjectName("actiondakai")
        self.actionc = QtWidgets.QAction(MainWindow)
        self.actionc.setObjectName("actionc")
        self.action_back = QtWidgets.QAction(MainWindow)  # 新增返回主界面动作
        self.action_back.setObjectName("action_back")
        
        # 添加动作到菜单
        self.menu.addAction(self.actionzhuye)
        self.menu.addAction(self.actionzhuye2)
        self.menu.addAction(self.actionzhuye3)
        self.menu_2.addAction(self.actionaadd)
        self.menu_2.addAction(self.actionadddd)
        self.menu_2.addAction(self.actionrizhichakan)
        self.menu_2.addAction(self.actionc)
        self.menu_3.addAction(self.actionjiazai)
        self.menu_3.addAction(self.actionxiezai)
        self.menu_3.addAction(self.actiongengxin)
        self.menu_3.addAction(self.actiondakai)
        self.menu_3.addAction(self.action_back)  # 添加返回主界面动作
        
        # 添加菜单到菜单栏
        self.menubar.addAction(self.menu.menuAction())
        self.menubar.addAction(self.menu_2.menuAction())
        self.menubar.addAction(self.menu_3.menuAction())

        # 连接菜单动作信号
        self.actiondakai.triggered.connect(self.open_plugin)  # 打开插件
        self.action_back.triggered.connect(self.back_to_main)  # 返回主界面
        
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
    
    def open_plugin(self):
        """打开插件，切换到插件堆叠窗口"""
        self.outer_stacked_widget.setCurrentIndex(1)
        print("切换到插件页面")
    
    def back_to_main(self):
        """返回主界面，切换到主堆叠窗口"""
        self.outer_stacked_widget.setCurrentIndex(0)
        print("返回主界面")
    
    def on_note_name_clicked(self):
        print("修改名称按钮被点击")
    
    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "频谱信息平台"))
        self.textBrowser_2.setHtml(_translate("MainWindow", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'SimSun\'; font-size:9pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">节点信息</p></body></html>"))
        self.textBrowser_3.setHtml(_translate("MainWindow", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'SimSun\'; font-size:9pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">设备信息</p></body></html>"))
        self.button_note_name.setText(_translate("MainWindow", "修改名称"))
        self.textBrowser.setHtml(_translate("MainWindow", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'SimSun\'; font-size:9pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:18pt;\">频谱信息平台</span></p></body></html>"))
        
        self.menu.setTitle(_translate("MainWindow", "主页"))
        self.menu_2.setTitle(_translate("MainWindow", "帮助"))
        self.menu_3.setTitle(_translate("MainWindow", "插件"))
        self.actionaadd.setText(_translate("MainWindow", "查看所有表和model类"))
        self.actionadddd.setText(_translate("MainWindow", "查看所有的信号"))
        self.actionjiazai.setText(_translate("MainWindow", "安装插件"))
        self.actionxiezai.setText(_translate("MainWindow", "卸载插件"))
        self.actiongengxin.setText(_translate("MainWindow", "更新插件"))
        self.actionzhuye.setText(_translate("MainWindow", "主页1"))
        self.actionzhuye2.setText(_translate("MainWindow", "主页2"))
        self.actionzhuye3.setText(_translate("MainWindow", "主页3"))
        self.actionrizhichakan.setText(_translate("MainWindow", "日志查看"))
        self.actiondakai.setText(_translate("MainWindow", "打开插件"))
        self.actionc.setText(_translate("MainWindow", "关于"))
        self.action_back.setText(_translate("MainWindow", "返回主界面"))  # 设置返回主界面文本


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
