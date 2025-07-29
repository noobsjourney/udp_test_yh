#基于 PyQt5 构建的插件管理系统图形界面（PluginManagerUI 类）
#与PluginManager 和 core_bus 总线系统集成
# 实现了插件的展示、上传、下载、启动/停止、服务调用、版本检查等功能。

#导入了PyQt5 中的常用 UI 控件类（如按钮、表格、输入框等）
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
    QFileDialog, QMessageBox, QInputDialog, QHeaderView
)
from PyQt5.QtCore import Qt
from pathlib import Path


class PluginManagerUI(QWidget):
    #这个类继承自 QWidget，是一个完整的插件管理窗口界面类。
    def __init__(self, plugin_manager, core_bus):
        #初始化 UI 组件；调用 refresh_table() 动态填充插件列表数据
        super().__init__()
        self.pm = plugin_manager
        self.core_bus = core_bus
        self._init_ui()
        self.refresh_table()


    def _init_ui(self):
        #构建窗口界面
        #设置窗口标题和大小
        self.setWindowTitle('插件管理系统')
        self.setGeometry(300, 300, 800, 600)

        #表格控件
        #用于显示插件信息，包括插件名、版本、运行状态、操作按钮和暴露的 API（日志列）
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['插件名称', '版本', '状态', '操作', '日志'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        #按钮控件
        #分别绑定了上传、下载、检查更新、调用服务四个操作。
        self.upload_btn = QPushButton('上传插件')
        self.upload_btn.clicked.connect(self.upload_plugin)

        self.download_btn = QPushButton('下载插件')
        self.download_btn.clicked.connect(self.download_plugin)

        self.check_update_btn = QPushButton('检查更新')
        self.check_update_btn.clicked.connect(self.check_update)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.upload_btn)
        layout.addWidget(self.download_btn)
        layout.addWidget(self.check_update_btn)

        self.setLayout(layout)

        self.call_service_btn = QPushButton("调用服务")
        self.call_service_btn.clicked.connect(self.call_service)
        layout.addWidget(self.call_service_btn)

    #通过总线调用插件暴露的服务
    def call_service(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "调用服务", "请输入名字：")
        if ok and name:
            try:
                result = self.core_bus.plugin_bus.call_plugin("hello_plugin", "hello", name)
                QMessageBox.information(self, "服务返回", result)
            except Exception as e:
                QMessageBox.critical(self, "调用失败", str(e))

    #动态刷新插件表格
    def refresh_table(self):
        self.table.setRowCount(len(self.pm.plugins))

#遍历所有插件，提取插件名、版本、状态、API权限；
#使用 QTableWidgetItem 和 QPushButton 动态更新每一行；
#根据插件状态设置颜色（运行中为绿色，停止为红色）；
#每个插件一行，并生成“加载/卸载”按钮。
        for row, (name, info) in enumerate(self.pm.plugins.items()):
            version = self.pm.config['plugins'].get(name, {}).get('version', '未知')
            status = info['status']
            apis = self.pm.config['plugins'].get(name, {}).get('allowed_apis', [])

            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(version))

            status_item = QTableWidgetItem(status)
            status_item.setForeground(Qt.green if status == 'running' else Qt.red)
            self.table.setItem(row, 2, status_item)

            action_btn = QPushButton('卸载' if status == 'running' else '加载')
            action_btn.clicked.connect(lambda _, n=name: self.toggle_plugin(n))
            self.table.setCellWidget(row, 3, action_btn)

            log_item = QTableWidgetItem(", ".join(apis) if apis else "无")
            self.table.setItem(row, 4, log_item)

    # 启停插件
    #点击按钮时判断插件是否在运行；
    #运行中则调用_stop_plugin停止它，否则启动；
    #最后刷新表格。
    def toggle_plugin(self, plugin_name: str):
        if self.pm.plugins[plugin_name]['status'] == 'running':
            self.pm._stop_plugin(plugin_name)
        else:
            self.pm._start_plugin(plugin_name)
        self.refresh_table()


    #上传插件文件到服务器
    #打开文件选择对话框（只允许 .py 文件）；
    # 使用 requests 向本地 Flask 服务发送 POST 请求上传文件；
    #上传成功后弹出提示框。
    def upload_plugin(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, '选择插件文件', '', 'Python Files (*.py)'
        )
        for file_path in files:
            try:
                import requests
                with open(file_path, 'rb') as f:
                    response = requests.post(
                        'http://127.0.0.1:5000/upload',
                        files={'file': (Path(file_path).name, f)}
                    )
                if response.ok:
                    QMessageBox.information(self, '上传成功', f'插件 {Path(file_path).name} 已上传')
                    self.refresh_table()
                else:
                    try:
                        msg = response.json().get("error", "未知错误")
                    except Exception as e:
                        msg = f"{str(e)}\n原始响应：{response.text}"
                    QMessageBox.critical(self, '上传失败', f"错误: {msg}")
            except Exception as e:
                QMessageBox.critical(self, '错误', str(e))

    #下载插件到本地
    #通过输入框输入插件名；
    # 向Flask后端发GET请求下载插件源码；
    #保存到用户指定路径；支持保存为.py文件。
    def download_plugin(self):
        plugin_name, ok = QInputDialog.getText(self, "下载插件", "输入插件名称:")
        if ok and plugin_name:
            try:
                import requests
                response = requests.get(f"http://127.0.0.1:5000/download/{plugin_name}")
                if response.status_code == 200:
                    save_path, _ = QFileDialog.getSaveFileName(
                        self, "保存插件", f"{plugin_name}.py", "Python Files (*.py)"
                    )
                    if save_path:
                        with open(save_path, "wb") as f:
                            f.write(response.content)
                        QMessageBox.information(self, "成功", f"插件 {plugin_name} 已保存")
                else:
                    QMessageBox.critical(self, "失败", f"下载失败: {response.json().get('error')}")
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))

    #检查插件是否有新版本
    #输入插件名；
    # 获取当前版本并构造URL；
    # 后端返回是否有更新、最新版本号等；
    # 根据返回提示用户是否有新版本。
    def check_update(self):
        plugin_name, ok = QInputDialog.getText(self, "检查插件更新", "输入插件名:")
        if ok and plugin_name:
            try:
                import requests
                version = self.pm.config['plugins'].get(plugin_name, {}).get("version", "0.0.0")
                url = f"http://127.0.0.1:5000/check-update/{plugin_name}?version={version}"
                res = requests.get(url)

                if res.status_code != 200:
                    QMessageBox.warning(self, "请求失败", f"状态码：{res.status_code}\n响应内容：{res.text}")
                    return

                try:
                    data = res.json()
                except Exception:
                    QMessageBox.critical(self, "错误", f"响应解析失败:\n{res.text}")
                    return

                if data.get("update_available"):
                    QMessageBox.information(self, "发现新版本", f"新版本: {data['latest_version']}")
                else:
                    QMessageBox.information(self, "已是最新", "插件已是最新版本")

            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))


