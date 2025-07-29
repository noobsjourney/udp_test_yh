import os
import json
import importlib
import threading
import shutil
import hashlib
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from base_module import BaseModule
from service_bus import PluginServiceBus, CoreServiceBus, ServiceBusError
from thread_executor import ThreadExecutor, DaemonTask
from signal_manager import SignalManager
from PyQt5.QtCore import pyqtSignal

import sys
sys.path.insert(0, os.getcwd())  # 确保当前目录在 sys.path 中

class PluginManagerError(Exception):
    """插件管理器基础异常"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

class PluginVersion:
    """插件版本信息容器"""
    def __init__(self, version: str, file_path: str, hash: str, timestamp: float):
        self.version = version
        self.file_path = file_path
        self.hash = hash
        self.timestamp = timestamp

class PluginMetadata:
    """插件元数据容器"""
    def __init__(self, name: str, author: str, description: str, 
                 entry_point: str, min_system_version: str, 
                 required_services: List[str], permissions: List[str], version: str):
        self.name = name
        self.author = author
        self.description = description
        self.entry_point = entry_point
        self.min_system_version = min_system_version
        self.required_services = required_services
        self.permissions = permissions
        self.version = version

class PluginInstance:
    """插件实例包装器"""
    def __init__(self, plugin_class: type, metadata: PluginMetadata, 
                 thread_executor: ThreadExecutor):
        self.plugin_class = plugin_class
        self.metadata = metadata
        self.instance = None
        self.thread_executor = thread_executor
        self.task_id = None
        self.status = "created"  # created, running, stopped, error
        self.error_message = ""
        
    def start(self, service_proxy: 'ServiceProxy'):
        """启动插件实例"""
        try:
            # 创建插件实例
            self.instance = self.plugin_class(service_proxy)
            
            # 在独立线程中运行插件
            self.task_id = self.thread_executor.submit(
                fn=self._run_plugin,
                pool_name="qt_default"
            )
            
            self.status = "running"
        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            raise PluginManagerError(500, f"插件启动失败: {str(e)}")
    
    def _run_plugin(self):
        """插件运行入口点"""
        try:
            if hasattr(self.instance, 'run'):
                self.instance.run()
            elif hasattr(self.instance, 'start'):
                self.instance.start()
            self.status = "stopped"
        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
    
    def stop(self):
        """停止插件实例"""
        if self.instance and hasattr(self.instance, 'stop'):
            try:
                self.instance.stop()
            except Exception:
                pass
        self.status = "stopped"
        
        # 取消插件线程
        if self.task_id:
            self.thread_executor.cancel_task(self.task_id)

class ServiceProxy:
    """服务总线代理，实现权限控制"""
    def __init__(self, plugin_name: str, core_bus: CoreServiceBus, 
                 allowed_services: List[str]):
        self.plugin_name = plugin_name
        self.core_bus = core_bus
        self.allowed_services = allowed_services
    
    def get_service(self, service_name: str) -> Any:
        """获取服务（带权限检查）"""
        if service_name not in self.allowed_services:
            raise PermissionError(f"插件 '{self.plugin_name}' 无权限访问服务 '{service_name}'")
        return self.core_bus.get_service(service_name)

class PluginManager(BaseModule):
    """插件管理系统
    目录结构：
        plugins/
        ├── using_plugins/           # 当前正在使用的插件
        │   └── example_plugin/
        │       ├── v1_0_0/
        │       │   ├── plugin.py
        │       │   └── metadata.json
        │       └── current -> v1_0_0/（符号链接）
        ├── update_plugins/          # 待更新的插件(zip格式)
        │   └── example_plugin_v1_1_0.zip
        └── rollback_plugins/        # 已回滚的插件(zip格式)
            └── example_plugin_v1_0_0_20250729_120000.zip
    """
    
    plugin_loaded = pyqtSignal(str, str)  # (插件名, 版本)
    plugin_unloaded = pyqtSignal(str)     # 插件名
    plugin_updated = pyqtSignal(str, str, str)  # (插件名, 旧版本, 新版本)
    
    def __init__(self, core_bus: CoreServiceBus, plugin_bus: PluginServiceBus):
        super().__init__()
        print("插件管理器初始化")
        self.core_bus = core_bus
        self.plugin_bus = plugin_bus
        
        # 获取依赖服务
        self.thread_executor = core_bus.get_service("thread")
        self.signal_manager = core_bus.get_service("signal")
        
        # 插件注册表
        self.plugin_registry: Dict[str, Dict[str, PluginVersion]] = {}
        # 活动插件
        self.active_plugins: Dict[str, PluginInstance] = {}
        # 插件元数据缓存
        self.metadata_cache: Dict[str, PluginMetadata] = {}
        
        # 插件根目录
        self.PLUGIN_ROOT       = Path(os.getcwd()) / "plugins"
        self.USING_PLUGINS     = self.PLUGIN_ROOT / "using_plugins"
        self.UPDATE_PLUGINS    = self.PLUGIN_ROOT / "update_plugins"
        self.ROLLBACK_PLUGINS  = self.PLUGIN_ROOT / "rollback_plugins"
        self.plugin_root = Path(os.getcwd()) / "plugins"

        # 确保目录存在
        for p in (self.USING_PLUGINS, self.UPDATE_PLUGINS, self.ROLLBACK_PLUGINS):
            p.mkdir(parents=True, exist_ok=True)
        
        # 注册信号
        self._register_signals()
    
    @property
    def module_name(self) -> str:
        return "plugin_manager"
    
    def _register_signals(self):
        """注册内部信号"""
        self.signal_manager.register_regular_signal("plugin_manager", "plugin_loaded", str, str)
        self.signal_manager.register_regular_signal("plugin_manager", "plugin_unloaded", str)

    def discover_plugins(self):
        """扫描 using_plugins 目录，构建注册表"""
        print("扫描插件目录...")
        self.plugin_registry.clear()

        for plugin_dir in self.USING_PLUGINS.iterdir():
            if not plugin_dir.is_dir():
                continue
            plugin_name = plugin_dir.name
            versions_dir = plugin_dir  # using_plugins/example_plugin/v1_0_0
            self.plugin_registry[plugin_name] = {}

            for version_dir in versions_dir.iterdir():
                if not version_dir.is_dir():
                    continue
                version = version_dir.name
                plugin_file = version_dir / "plugin.py"
                if plugin_file.exists():
                    file_hash = self._calculate_file_hash(plugin_file)
                    self.plugin_registry[plugin_name][version] = PluginVersion(
                        version=version,
                        file_path=str(plugin_file),
                        hash=file_hash,
                        timestamp=plugin_file.stat().st_mtime
                    )
        print(f"发现 {len(self.plugin_registry)} 个插件")
    
    def load_plugin(self, plugin_name: str, version: str):
        """从 using_plugins 中加载指定版本"""
        if plugin_name not in self.plugin_registry or version not in self.plugin_registry[plugin_name]:
            raise PluginManagerError(404, f"插件 {plugin_name} 版本 {version} 未找到")

        if plugin_name in self.active_plugins:
            self.unload_plugin(plugin_name)

        metadata = self._load_metadata(plugin_name, version)
        service_proxy = ServiceProxy(
            plugin_name=plugin_name,
            core_bus=self.core_bus,
            allowed_services=metadata.required_services
        )
        plugin_class = self._import_plugin(plugin_name, version, metadata.entry_point)
        plugin_instance = PluginInstance(
            plugin_class=plugin_class,
            metadata=metadata,
            thread_executor=self.thread_executor
        )
        plugin_instance.start(service_proxy)
        self.active_plugins[plugin_name] = plugin_instance

        self.plugin_loaded.emit(plugin_name, version)
        self.signal_manager.emit_regular_signal("plugin_manager", "plugin_loaded", plugin_name, version)
        print(f"插件 '{plugin_name}' v{version} 加载成功")
    
    def unload_plugin(self, plugin_name: str):
        if plugin_name not in self.active_plugins:
            raise PluginManagerError(404, f"插件 '{plugin_name}' 未加载")
        instance = self.active_plugins[plugin_name]
        instance.stop()
        del self.active_plugins[plugin_name]
        self.plugin_unloaded.emit(plugin_name)
        self.signal_manager.emit_regular_signal("plugin_manager", "plugin_unloaded", plugin_name)
        print(f"插件 '{plugin_name}' 已卸载")
    
    def get_plugin_status(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件状态"""
        if plugin_name not in self.active_plugins:
            return {"status": "not_loaded"}

        instance = self.active_plugins[plugin_name]
        return {
            "status": instance.status,                # created / running / stopped / error
            "version": instance.metadata.version,     # 当前版本
            "task_id": instance.task_id,              # 线程任务 id
            "error": instance.error_message           # 若出错，错误文本
        }
    
    def get_loaded_plugins(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已加载插件的状态"""
        loaded_plugins = {}
        for plugin_name, instance in self.active_plugins.items():
            loaded_plugins[plugin_name] = self.get_plugin_status(plugin_name)
        print("已加载插件状态:", loaded_plugins)
        return loaded_plugins

    def update_plugin(self, plugin_name: str, new_zip_path: str):
        """手动更新插件：从 update_plugins 读取 zip,解压到 using_plugins,旧版打包到 rollback_plugins"""
        print(f"更新插件: {plugin_name}")
        if plugin_name in self.active_plugins:
            old_version = self.active_plugins[plugin_name].metadata.version
            self.unload_plugin(plugin_name)
        else:
            old_version = "unknown"

        # 1. 备份旧版本
        if old_version != "unknown":
            self._backup_plugin(plugin_name, old_version)

        # 2. 安装新版本
        new_version = self._install_plugin_version(plugin_name, new_zip_path)

        # 3. 重新加载
        self.load_plugin(plugin_name, new_version)
        self._cleanup_old_versions(plugin_name, new_version)
        self.plugin_updated.emit(plugin_name, old_version, new_version)
        print(f"插件 '{plugin_name}' 已从 {old_version} 更新到 {new_version}")
    
    def rollback_plugin(self, plugin_name: str, target_version: str):
        """手动回滚插件：从 rollback_plugins 选择 zip，解压覆盖 using_plugins"""
        print(f"回滚插件: {plugin_name} 到 {target_version}")
        if plugin_name in self.active_plugins:
            current_version = self.active_plugins[plugin_name].metadata.version
            self.unload_plugin(plugin_name)
            self._backup_plugin(plugin_name, current_version)
        else:
            current_version = "unknown"

        # 构造回滚 zip 路径
        rollback_zip = self.ROLLBACK_PLUGINS / f"{plugin_name}_{target_version}.zip"
        matches = list(self.ROLLBACK_PLUGINS.glob(f"{plugin_name}_{target_version}.zip"))
        if not matches:
            raise PluginManagerError(404, f"回滚版本 {target_version} 未找到")
        rollback_zip = matches[-1]  # 选最新备份

        # 解压覆盖
        using_dir = self.USING_PLUGINS / plugin_name
        if using_dir.exists():
            shutil.rmtree(using_dir)
        using_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(rollback_zip, 'r') as zf:
            zf.extractall(using_dir)

        # 重新扫描并加载
        self.discover_plugins()
        self.load_plugin(plugin_name, target_version)
        self._cleanup_old_versions(plugin_name, target_version)
        print(f"插件 '{plugin_name}' 已回滚到 {target_version}")

    def _backup_plugin(self, plugin_name: str, version: str):
        """把 using_plugins 中的旧版本打包成 zip 存入 rollback_plugins"""
        src_dir = self.USING_PLUGINS / plugin_name / version
        if not src_dir.exists():
            return
        backup_name = f"{plugin_name}_{version}.zip"
        backup_path = self.ROLLBACK_PLUGINS / backup_name
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in src_dir.rglob("*"):
                zf.write(file, file.relative_to(src_dir.parent))
        print(f"已创建备份: {backup_path}")

    def _install_plugin_version(self, plugin_name: str, zip_path: str) -> str:
        """把 update_plugins 中的 zip 解压到 using_plugins"""
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise PluginManagerError(404, f"更新包 {zip_path} 不存在")

        # 读取元数据取得版本号
        with zipfile.ZipFile(zip_path, 'r') as zf:
            with zf.open("metadata.json") as mf:
                metadata = json.load(mf)
                version = metadata.get("version")
                if not version:
                    raise PluginManagerError(500, "元数据中缺少版本号")

        # 清空并解压
        target_dir = self.USING_PLUGINS / plugin_name / version
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(target_dir)

        # 更新符号链接
        current_link = self.USING_PLUGINS / plugin_name / "current"
        self._set_current_link(current_link, target_dir)

        # 重新扫描
        self.discover_plugins()
        return version

    def _set_current_link(self, link_path: Path, target_dir: Path):
        """跨平台设置 current -> version 符号链接（Windows 用 junction）"""
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(target_dir), str(link_path))
        else:
            link_path.symlink_to(target_dir)    
    
    def _import_plugin(self, plugin_name: str, version: str, entry_point: str) -> type:
        """使用文件路径动态导入插件模块"""
        # 获取插件文件路径
        file_path = self.USING_PLUGINS / plugin_name / version / "plugin.py"
        
        if not file_path.exists():
            raise PluginManagerError(404, f"插件文件未找到: {file_path}")
        
        # 创建唯一的模块名
        module_name = f"plugins_{plugin_name}_{version.replace('.', '_')}"
        
        try:
            # 使用 importlib 从文件路径加载模块
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None:
                raise PluginManagerError(500, f"无法创建模块规范: {file_path}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # 获取入口类
            if not hasattr(module, entry_point):
                raise PluginManagerError(500, f"入口点 '{entry_point}' 未找到")
            
            return getattr(module, entry_point)
        except Exception as e:
            raise PluginManagerError(500, f"插件导入失败: {str(e)}")
    
    def _load_metadata(self, plugin_name: str, version: str) -> PluginMetadata:
        """加载插件元数据"""
        # 检查缓存
        if plugin_name in self.metadata_cache:
            return self.metadata_cache[plugin_name]
        
        # 元数据文件路径
        metadata_file = self.USING_PLUGINS / plugin_name / version / "metadata.json"
        
        if not metadata_file.exists():
            raise PluginManagerError(404, f"插件 '{plugin_name}' 元数据文件未找到")
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                metadata = PluginMetadata(
                    name=data.get("name", plugin_name),
                    author=data.get("author", "未知作者"),
                    description=data.get("description", ""),
                    entry_point=data.get("entry_point", "Plugin"),
                    min_system_version=data.get("min_system_version"),
                    required_services=data.get("required_services", []),
                    permissions=data.get("permissions", []),
                    version=data.get("version")
                )
                
                # 缓存元数据
                self.metadata_cache[plugin_name] = metadata
                return metadata
        except json.JSONDecodeError as e:
            raise PluginManagerError(500, f"元数据解析失败: {str(e)}")
    
    def _cleanup_old_versions(self, plugin_name: str, keep_version: str):
        """删除 using_plugins/<plugin>/ 下除 keep_version 外的所有版本目录"""
        using_dir = self.USING_PLUGINS / plugin_name
        if not using_dir.exists():
            return
        for item in using_dir.iterdir():
            if item.is_dir() and item.name != keep_version and item.name != "current":
                shutil.rmtree(item)
                print(f"删除旧版本目录: {item}")

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希值"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def shutdown(self):
        """关闭插件管理器"""
        print("关闭插件管理器...")
        # 卸载所有插件
        for plugin_name in list(self.active_plugins.keys()):
            try:
                self.unload_plugin(plugin_name)
            except Exception as e:
                print(f"卸载插件 {plugin_name} 失败: {str(e)}")
        
        # 清理信号
        self.signal_manager.unregister_regular_signal("plugin_manager", "plugin_loaded")
        self.signal_manager.unregister_regular_signal("plugin_manager", "plugin_unloaded")

if __name__ == '__main__':
    # 初始化服务总线
    core_bus = CoreServiceBus()
    service_names = core_bus.get_registered_services()
    print("服务名称列表:", service_names)
    plugin_bus = PluginServiceBus(core_bus)
    # 创建插件管理器
    plugin_manager = PluginManager(core_bus, plugin_bus)

    # # 扫描可用插件
    plugin_manager.discover_plugins()
    print("发现插件:", list(plugin_manager.plugin_registry.keys()))

    # # 加载示例插件
    plugin_manager.load_plugin("example_plugin", "v1_0_0") 

    # 获取插件状态
    status = plugin_manager.get_plugin_status("example_plugin")
    print(f"插件状态: {status}")

    # 更新插件
    plugin_manager.update_plugin("example_plugin","plugins/update_plugins/example_plugin_v1_1_0.zip")

    # 获取插件状态
    status = plugin_manager.get_plugin_status("example_plugin")
    print(f"插件状态: {status}")

    # 回滚插件到旧版本
    plugin_manager.rollback_plugin("example_plugin", "v1_0_0")
    
    # 获取所有已加载插件的状态
    plugin_manager.get_loaded_plugins()

    # 卸载插件
    plugin_manager.unload_plugin("example_plugin")
    
    # 获取所有已加载插件的状态
    plugin_manager.get_loaded_plugins()

    # 关闭插件管理器
    plugin_manager.shutdown()