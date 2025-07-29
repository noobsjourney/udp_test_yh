class Plugin:
    __plugin_metadata__ = {
        "name": "hello_plugin",
        "version": "1.0.0",
        "author": "MHX",
        "allowed_apis": []
        "model_name":""
    }

    def __init__(self):
        self._running = True

    def hello(self, name):
        return f"你好，{name}！我是插件 hello_plugin！"

    def run(self):
        import time
        while self._running:
            print("[hello_plugin] 插件运行中...")
            time.sleep(2)

    def stop(self):
        self._running = False
