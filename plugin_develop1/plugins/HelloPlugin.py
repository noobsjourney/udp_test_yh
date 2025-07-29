import time  # 添加导入

class Plugin:
    __plugin_metadata__ = {
        "name": "HelloPlugin",
        "version": "1.0.0",
        "author": "MHX",
        "allowed_apis": []  # 必须包含此字段
    }

    def __init__(self):
        self._running = True

    def run(self):
        while self._running:
            print("Hello Plugin 正在运行...")
            time.sleep(1)  # 添加延时

    def stop(self):
        self._running = False  # 添加停止方法
