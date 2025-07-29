#插件管理系统的入口点，整合了以下几个核心模块：
# 插件管理器 PluginManager
# API 网关 APIGateway
# 图形化管理界面 PluginManagerUI
# 插件版本管理和上传/下载服务 Flask update_server
# 跨插件通信的总线服务 CoreServiceBus


#环境修正与兼容性设置部分
#解决在某些机器上运行 Flask 时可能出现的 getfqdn DNS 解析问题
import socket
socket.getfqdn = lambda name='': 'localhost'
from base_module import BaseModule

#防止 Qt/Flask/Python 字符集错误，强制使用英文+UTF-8。
import os
os.environ['LC_ALL'] = 'C'
os.environ['LANG'] = 'C'
os.environ['PYTHONIOENCODING'] = 'utf-8'

import sys
import threading

import _locale
_locale._getdefaultlocale = (lambda *args: ['en_US', 'utf8'])

# 强制设置环境变量
os.environ["LC_ALL"] = "C"
os.environ["LANG"] = "C"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["FLASK_ENV"] = "development"
os.environ["FLASK_RUN_HOST"] = "127.0.0.1"

#核心模块初始化
from PyQt5.QtWidgets import QApplication

from core.plugin_manager import PluginManager#插件的动态加载、卸载、热更新等
from core.api_gateway import APIGateway#提供插件对外注册 API 的网关
from ui.plugin_ui import PluginManagerUI#基于 PyQt5 的图形界面
from core.update_server import app as update_server#Flask 应用（用于上传/下载/回滚等接口）
from core.service_bus import CoreServiceBus  # 总线服务导入

# ✅ 初始化总线服务
#总线服务先初始化，用于后续注入插件管理器。
# 插件管理器用总线来协调插件通信。
# API 网关可让插件暴露服务给其他模块。
core_bus = CoreServiceBus()

def run_update_server():
    update_server.run(
        host='127.0.0.1',  # 明确设置为本地地址
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )

if __name__ == '__main__':
    # ✅ 初始化核心组件（将总线服务注入插件管理器）
    pm = PluginManager(core_bus)
    gateway = APIGateway(pm)

    # ✅ 启动GUI（注入总线服务）
    gui_app = QApplication(sys.argv)
    window = PluginManagerUI(pm, core_bus)
    window.show()

    # ✅ 启动插件上传/下载 Flask 服务
    server_thread = threading.Thread(target=run_update_server, daemon=True)
    server_thread.start()

    sys.exit(gui_app.exec_())
