#实现了一个插件管理系统
# 负责动态加载、卸载、重载、版本回滚等插件管理功能，且支持插件的线程管理和文件系统监听。
#关键功能:
#1.插件热加载与卸载：
# 通过 PluginEventHandler 来实时监听文件系统的变化，自动注册新的插件，卸载被删除的插件，并重新加载被修改的插件。
#2.插件线程管理：
# 每个插件运行在独立的线程中，支持启动、停止和错误处理。通过 threading 模块来实现并发运行。
#3.插件版本控制与备份：
# 在安装插件时，如果已有插件，则会备份旧版本。并支持版本回滚功能，从备份中恢复指定版本。
#4.插件元数据管理：
# 插件需要包含 Plugin 类，并且该类需包含 __plugin_metadata__ 属性，插件的元数据包括插件的名称、版本以及允许的 API 等信息。


import threading
import json
import importlib.util
import shutil
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# PluginEventHandler类
#监听插件文件的变化（如创建、删除、修改）
class PluginEventHandler(FileSystemEventHandler):
    def __init__(self, plugin_manager):
        super().__init__()
        self.plugin_manager = plugin_manager

    def on_created(self, event):
        #当新插件文件创建时，调用 plugin_manager._register_plugin 方法注册插件
        """处理新插件文件创建事件"""
        if not event.is_directory and event.src_path.endswith('.py'):
            plugin_path = Path(event.src_path)
            print(f"检测到新插件: {plugin_path.name}")
            self.plugin_manager._register_plugin(plugin_path)

    def on_deleted(self, event):
        #当插件文件被删除时，删除插件实例并调用_stop_plugin 停止插件
        """处理插件文件删除事件"""
        if not event.is_directory and event.src_path.endswith('.py'):
            plugin_name = Path(event.src_path).stem
            print(f"插件 {plugin_name} 已被删除")
            if plugin_name in self.plugin_manager.plugins:
                self.plugin_manager._stop_plugin(plugin_name)
                del self.plugin_manager.plugins[plugin_name]

    def on_modified(self, event):
        #当插件文件被修改时，调用 plugin_manager.reload_plugin 方法重新加载插件
        """处理插件文件修改事件"""
        if not event.is_directory and event.src_path.endswith('.py'):
            plugin_path = Path(event.src_path)
            print(f"检测到插件更新: {plugin_path.name}")
            self.plugin_manager.reload_plugin(plugin_path.stem)

class PluginManager:
    #PluginManager 类,插件管理系统的核心，负责插件的加载、注册、启动、卸载、重载、版本回滚等功能
    _instance = None
    _lock = threading.Lock()

    #确保 PluginManager 是单例模式。初始化插件管理器，加载配置文件，启动文件监控
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance.__initialized = False
        return cls._instance

    def __init__(self, core_bus=None):  # ✅ 添加参数
        if self.__initialized:
            return
        self.__initialized = True
        self.plugin_datatable ={
            "hello": "Users",
            "hello":"table2",
        }
        self.core_bus = core_bus  # ✅ 保存 core_bus
        print("PluginManager 初始化完成")
        # 在这里可以调用 self.load_plugins() 等等


        # 初始化配置
        self.plugins = {}
        self.plugin_dir = Path("plugins")
        self.plugin_dir.mkdir(exist_ok=True)

        # 加载配置
        self.config_path = Path("plugin_system_config.json")
        self.config = self._load_default_config()
        if self.config_path.exists():
            self.config.update(json.loads(self.config_path.read_text()))

        # 初始化监听
        self.observer = Observer()
        self.event_handler = PluginEventHandler(self)  # 使用已定义的类
        self.observer.schedule(self.event_handler, str(self.plugin_dir))
        self.observer.start()

        # 添加网络处理线程
        self.net_processor = threading.Thread(target=self._network_loop)
        self.net_processor.start()

    def _network_loop(self):
        while True:
            # 监听网络数据示例
            raw_data = self._receive_from_network()  # 伪代码，需实现真实网络接收
            packet = PluginPacket.deserialize(raw_data)
            self.core_bus.get_network_signal("net_in").emit(packet.plugin_id, packet.data)

    def _load_default_config(self):
        """默认配置模板"""
        return {
            "system": {
                "backup_dir": "backups",
                "max_backups": 3,
                "default_threads": 1,
                "api_whitelist": {
                    "basic": ["get_status", "log"],
                    "advanced": ["db_query", "file_upload"]
                }
            },
            "plugins": {}
        }


    # ------------------ 核心方法 ------------------
    #安装新插件，将插件文件复制到插件目录，并更新配置文件中的插件信息。
    def install_plugin(self, file_path: str):
        """安装插件方法"""
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 读取元数据
        spec = importlib.util.spec_from_file_location("temp_module", src)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "Plugin"):
            raise ValueError("插件必须包含 Plugin 类")

        metadata = getattr(module.Plugin, "__plugin_metadata__", {})
        if not metadata.get("name") or not metadata.get("version"):
            raise ValueError("插件缺少必要元数据")

        dest = self.plugin_dir / f"{metadata['name']}.py"

        # 🔁 新增：备份旧插件
        if dest.exists():
            backup_dir = Path("backups") / metadata['name']
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d%H%M%S")
            backup_file = backup_dir / f"{metadata['name']}_{timestamp}.py"
            shutil.copy(dest, backup_file)
            print(f"🗃 已备份旧版本至: {backup_file}")

        # 复制文件
        shutil.copy(src, dest)

        # 更新配置
        self.config["plugins"][metadata["name"]] = {
            "version": metadata["version"],
            "allowed_apis": metadata.get("allowed_apis", []),
            "enabled": True
        }
        self._save_config()

        # 注册插件
        self._register_plugin(dest)

#注册插件，加载插件文件并创建插件实例，启动插件线程。
    def _register_plugin(self, path: Path):
        plugin_name = path.stem
        print(f"📦 开始注册插件: {plugin_name}")

        try:
            spec = importlib.util.spec_from_file_location(plugin_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin_instance = module.Plugin()

            self.plugins[plugin_name] = {
                "module": module,
                "instance": plugin_instance,
                "status": "stopped",
                "thread": None
            }

            # ✅ 关键步骤：注册到总线
            if self.core_bus:
                self.core_bus.plugin_bus.register_plugin(plugin_name, plugin_instance)

            self._start_plugin(plugin_name)
            print(f"✅ 插件注册完成: {plugin_name}")
        except Exception as e:
            print(f"❌ 插件注册失败: {e}")

#启动插件线程，插件的主循环运行在一个新的线程中。
    def _start_plugin(self, plugin_name: str):
        """启动插件线程"""
        def plugin_loop():
            while True:
                try:
                    self.plugins[plugin_name]["instance"].run()
                except Exception as e:
                    self._handle_error(plugin_name, e)

        if self.plugins[plugin_name]["status"] == "running":
            return

        thread = threading.Thread(
            target=plugin_loop,
            name=f"PluginThread-{plugin_name}",
            daemon=True
        )
        thread.start()
        self.plugins[plugin_name]["thread"] = thread
        self.plugins[plugin_name]["status"] = "running"

    # ------------------ 其他关键方法 ------------------
    def uninstall_plugin(self, plugin_name: str):
        """卸载插件"""
        plugin_path = self.plugin_dir / f"{plugin_name}.py"
        if plugin_path.exists():
            plugin_path.unlink()
        if plugin_name in self.plugins:
            self._stop_plugin(plugin_name)
            del self.plugins[plugin_name]
        print(f"插件 {plugin_name} 已卸载")

#重新加载插件，先停止插件，删除旧的插件实例，再注册新插件实例。
    def reload_plugin(self, plugin_name: str):
        """重新加载插件"""
        print(f"🔁 重新加载插件: {plugin_name}")

        plugin_path = self.plugin_dir / f"{plugin_name}.py"
        if not plugin_path.exists():
            print(f"⚠️ 插件文件不存在: {plugin_path}")
            return

        try:
            # ✅ 新增：先停止插件线程，再安全地删除旧实例
            self._stop_plugin(plugin_name)
        except Exception as e:
            print(f"⚠️ 停止插件时出错: {e}")

        try:
            # ✅ 安全移除插件字典项
            self.plugins.pop(plugin_name, None)
        except Exception as e:
            print(f"⚠️ 删除插件实例时出错: {e}")

        # ✅ 调用注册方法（重新导入新版本）
        self._register_plugin(plugin_path)

#回滚插件版本，从备份中恢复插件到指定版本。
    def rollback_plugin(self, plugin_name: str, version: str):
        """版本回滚"""
        backup_dir = Path("backups") / plugin_name
        backup_file = next((f for f in backup_dir.glob(f"{plugin_name}_{version}*.py")), None)
        if backup_file:
            current_path = self.plugin_dir / f"{plugin_name}.py"
            shutil.copy(backup_file, current_path)
            self.reload_plugin(plugin_name)
            print(f"已回滚到版本 {version}")
        else:
            raise FileNotFoundError(f"找不到版本 {version} 的备份")

#保存插件配置文件。
    def _save_config(self):
        """保存配置文件"""
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

#插件运行出错时的处理方法，停止插件并记录错误。
    def _handle_error(self, plugin_name: str, error: Exception):
        """错误处理"""
        print(f"插件 {plugin_name} 运行错误: {str(error)}")
        self.plugins[plugin_name]["status"] = "error"

        # ✅ 新增：如果插件出错，强制关闭它（否则会进入死循环）
        self._stop_plugin(plugin_name)

#停止插件线程，安全地停止插件运行。
    def _stop_plugin(self, plugin_name: str):
        """安全停止插件线程"""
        if plugin_name not in self.plugins:
            return

        # 调用插件的stop方法
        if hasattr(self.plugins[plugin_name]["instance"], "stop"):
            self.plugins[plugin_name]["instance"].stop()

        # 等待线程结束
        if self.plugins[plugin_name]["thread"]:
            self.plugins[plugin_name]["thread"].join(timeout=2)
            if self.plugins[plugin_name]["thread"].is_alive():
                print(f"警告: 插件 {plugin_name} 线程未正常退出")

        self.plugins[plugin_name]["status"] = "stopped"

#静态方法，用来获取 PluginManager 的实例
    @staticmethod
    def instance():
        return PluginManager()


