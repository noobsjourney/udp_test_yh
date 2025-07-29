import os
import time
import importlib.util
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class MockPluginBus:
    def __init__(self):
        self.plugins = {}

    def register_plugin(self, name, plugin):
        self.plugins[name] = plugin
        print(f"✅ 注册成功: {name}")

    def unregister_plugin(self, name):
        if name in self.plugins:
            del self.plugins[name]
            print(f"🗑️ 卸载完成: {name}")


class PluginHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.plugin_bus = MockPluginBus()
        self.plugins_dir = self.get_plugins_dir()
        print("🔍 监控目录:", self.plugins_dir)  # 路径确认

    def get_plugins_dir(self):
        dir_path = os.path.join(os.getcwd(), "plugins")
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    def on_created(self, event):
        print(f"🕵️ 检测到新文件: {event.src_path}")  # 事件触发确认
        if event.is_directory:
            return
        if event.src_path.endswith(".py"):
            print("🔧 尝试加载插件...")
            self.load_plugin(event.src_path)

    def load_plugin(self, path):
        try:
            print(f"📦 加载文件: {path}")
            # 动态导入
            spec = importlib.util.spec_from_file_location("dynamic_plugin", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 类检查
            if not hasattr(module, "Plugin"):
                raise AttributeError("插件必须包含Plugin类")

            # 实例化
            plugin_class = module.Plugin
            instance = plugin_class()

            # 注册
            plugin_name = os.path.basename(path).replace(".py", "")
            self.plugin_bus.register_plugin(plugin_name, instance)

        except Exception as e:
            print("❌ 加载失败详情:")
            traceback.print_exc()  # 打印完整错误栈


if __name__ == "__main__":
    print("=== 插件加载器调试版 ===")
    handler = PluginHandler()

    observer = Observer()
    observer.schedule(handler, path=handler.plugins_dir, recursive=False)
    observer.start()

    try:
        print("👂 监听已启动，请将插件拖入plugins文件夹...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
