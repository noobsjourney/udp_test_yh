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
import os
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
    
    功能：
    - 插件热拔插
    - 基于配置文件的插件加载/卸载
    - 插件版本管理
    - 服务代理和权限控制
    - 插件线程隔离
    
    目录结构：
    plugins/
      plugin_name/
        versions/
          v1.0.0/
            plugin.py
            metadata.json
          v1.1.0/
            plugin.py
            metadata.json
        current -> v1.1.0 (符号链接)
        backups/
          plugin_v1.0.0_20230101.zip
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
        self.signal_manager = core_bus.get_service(core_bus.signal_manager.get_module_name())
        
        # 插件注册表 {plugin_name: {version: PluginVersion}}
        self.plugin_registry: Dict[str, Dict[str, PluginVersion]] = {}
        # 活动插件 {plugin_name: PluginInstance}
        self.active_plugins: Dict[str, PluginInstance] = {}
        # 插件元数据缓存 {plugin_name: PluginMetadata}
        self.metadata_cache: Dict[str, PluginMetadata] = {}
        
        # 插件根目录
        self.plugin_root = Path(os.getcwd()) / "plugins"
        self.plugin_root.mkdir(exist_ok=True)
        
        # 注册信号
        self._register_signals()
    
    @property
    def module_name(self) -> str:
        return "plugin_manager"
    
    def _register_signals(self):
        """注册内部信号"""
        self.signal_manager.register_regular_signal(
            "plugin_manager", "plugin_loaded", str, str
        )
        self.signal_manager.register_regular_signal(
            "plugin_manager", "plugin_unloaded", str
        )
    
    def discover_plugins(self):
        """发现可用插件"""
        print("扫描插件目录...")
        self.plugin_registry.clear()
        
        for plugin_dir in self.plugin_root.iterdir():
            if plugin_dir.is_dir():
                plugin_name = plugin_dir.name
                versions_dir = plugin_dir / "versions"
                
                if versions_dir.exists() and versions_dir.is_dir():
                    self.plugin_registry[plugin_name] = {}
                    
                    for version_dir in versions_dir.iterdir():
                        if version_dir.is_dir():
                            version = version_dir.name
                            plugin_file = version_dir / "plugin.py"
                            
                            if plugin_file.exists():
                                # 计算文件哈希
                                file_hash = self._calculate_file_hash(plugin_file)
                                
                                # 添加到注册表
                                self.plugin_registry[plugin_name][version] = PluginVersion(
                                    version=version,
                                    file_path=str(plugin_file),
                                    hash=file_hash,
                                    timestamp=plugin_file.stat().st_mtime
                                )
        
        print(f"发现 {len(self.plugin_registry)} 个插件")
    
    def load_plugin(self, plugin_name: str, version: str):
        """加载指定插件（手动指定版本）"""
        print(f"加载插件: {plugin_name} 版本: {version}")

        # 强制检查版本号
        if version is None:
            raise PluginManagerError(400, f"必须手动指定插件 '{plugin_name}' 的版本号")

        # 检查插件是否存在
        if plugin_name not in self.plugin_registry:
            raise PluginManagerError(404, f"插件 '{plugin_name}' 未找到")

        # 检查版本是否存在
        if version not in self.plugin_registry[plugin_name]:
            raise PluginManagerError(404, f"插件 '{plugin_name}' 版本 '{version}' 未找到")

        # 如果已加载，先卸载
        if plugin_name in self.active_plugins:
            self.unload_plugin(plugin_name)

        # 加载元数据
        metadata = self._load_metadata(plugin_name, version)

        # 创建服务代理
        service_proxy = ServiceProxy(
            plugin_name=plugin_name,
            core_bus=self.core_bus,
            allowed_services=metadata.required_services
        )

        # 动态导入插件
        plugin_class = self._import_plugin(plugin_name, version, metadata.entry_point)

        # 创建插件实例
        plugin_instance = PluginInstance(
            plugin_class=plugin_class,
            metadata=metadata,
            thread_executor=self.thread_executor
        )

        # 启动插件
        plugin_instance.start(service_proxy)

        # 添加到活动插件
        self.active_plugins[plugin_name] = plugin_instance

        # 发送信号
        self.plugin_loaded.emit(plugin_name, version)
        self.signal_manager.emit_regular_signal("plugin_manager", "plugin_loaded", plugin_name, version)

        print(f"插件 '{plugin_name}' v{version} 加载成功")
    
    def unload_plugin(self, plugin_name: str):
        """卸载插件"""
        print(f"卸载插件: {plugin_name}")
        
        if plugin_name not in self.active_plugins:
            raise PluginManagerError(404, f"插件 '{plugin_name}' 未加载")
        
        plugin_instance = self.active_plugins[plugin_name]
        
        # 停止插件
        plugin_instance.stop()
        
        # 从活动插件中移除
        del self.active_plugins[plugin_name]
        
        # 发送信号
        self.plugin_unloaded.emit(plugin_name)
        self.signal_manager.emit_regular_signal("plugin_manager", "plugin_unloaded", plugin_name)
        
        print(f"插件 '{plugin_name}' 已卸载")
    
    def update_plugin(self, plugin_name: str, new_version_file: str):
        """更新插件到新版本"""
        print(f"更新插件: {plugin_name}")
        
        # 检查插件是否已加载
        if plugin_name in self.active_plugins:
            current_version = self.active_plugins[plugin_name].metadata.version
            self.unload_plugin(plugin_name)
        else:
            current_version = "unknown"
        
        # 备份当前版本
        self._backup_plugin(plugin_name)
        
        # 安装新版本
        new_version = self._install_plugin_version(plugin_name, new_version_file)
        
        # 重新加载插件
        self.load_plugin(plugin_name, new_version)
        
        # 发送更新信号
        self.plugin_updated.emit(plugin_name, current_version, new_version)
        
        print(f"插件 '{plugin_name}' 已从 v{current_version} 更新到 v{new_version}")
    
    def rollback_plugin(self, plugin_name: str, target_version: str):
        """回滚插件到指定版本"""
        print(f"回滚插件: {plugin_name} 到版本 {target_version}")
        
        # 检查目标版本是否存在
        if plugin_name not in self.plugin_registry or target_version not in self.plugin_registry[plugin_name]:
            raise PluginManagerError(404, f"版本 '{target_version}' 未找到")
        
        # 卸载当前版本
        if plugin_name in self.active_plugins:
            current_version = self.active_plugins[plugin_name].metadata.version
            self.unload_plugin(plugin_name)
        else:
            current_version = "unknown"
        
        # 切换版本
        self._activate_plugin_version(plugin_name, target_version)
        
        # 重新加载插件
        self.load_plugin(plugin_name, target_version)
        
        print(f"插件 '{plugin_name}' 已从 v{current_version} 回滚到 v{target_version}")
    
    def get_plugin_status(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件状态"""
        if plugin_name not in self.active_plugins:
            return {"status": "not_loaded"}
        
        instance = self.active_plugins[plugin_name]
        return {
            "status": instance.status,
            "version": instance.metadata.version,
            "task_id": instance.task_id,
            "error": instance.error_message
        }
    
    def _import_plugin(self, plugin_name: str, version: str, entry_point: str) -> type:
        """使用文件路径动态导入插件模块"""
        # 获取插件文件路径
        file_path = Path(self.plugin_root) / plugin_name / "versions" / version / "plugin.py"
        
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
        metadata_file = self.plugin_root / plugin_name / "versions" / version / "metadata.json"
        
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
                    min_system_version=data.get("min_system_version", "1_0_0"),
                    required_services=data.get("required_services", []),
                    permissions=data.get("permissions", []),
                    version=data.get("version", "1_0_0")
                )
                
                # 缓存元数据
                self.metadata_cache[plugin_name] = metadata
                return metadata
        except json.JSONDecodeError as e:
            raise PluginManagerError(500, f"元数据解析失败: {str(e)}")
    
    def _backup_plugin(self, plugin_name: str):
        """备份当前插件版本"""
        plugin_dir = self.plugin_root / plugin_name
        versions_dir = plugin_dir / "versions"
        backups_dir = plugin_dir / "backups"
        backups_dir.mkdir(exist_ok=True)
        
        # 获取当前版本
        current_version = self.active_plugins[plugin_name].metadata.version
        current_version_dir = versions_dir / current_version
        
        # 创建备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backups_dir / f"{plugin_name}_v{current_version}_{timestamp}.zip"
        
        # 压缩当前版本
        with zipfile.ZipFile(backup_file, 'w') as zipf:
            for root, _, files in os.walk(current_version_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, current_version_dir)
                    zipf.write(file_path, arcname)
        
        print(f"已创建插件备份: {backup_file}")
    
    def _install_plugin_version(self, plugin_name: str, plugin_file: str) -> str:
        """安装新插件版本"""
        plugin_dir = self.plugin_root / plugin_name
        versions_dir = plugin_dir / "versions"
        
        # 加载插件包元数据
        with zipfile.ZipFile(plugin_file, 'r') as zipf:
            # 从ZIP中提取元数据
            with zipf.open('metadata.json') as meta_file:
                metadata = json.load(meta_file)
                version = metadata.get("version", "1_0_0")
        
        # 创建版本目录
        version_dir = versions_dir / version
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # 解压文件
        with zipfile.ZipFile(plugin_file, 'r') as zipf:
            zipf.extractall(version_dir)
        
        # 激活新版本
        self._activate_plugin_version(plugin_name, version)
        
        # 更新注册表
        self.discover_plugins()
        
        return version
    
    def _activate_plugin_version(self, plugin_name: str, version: str):
        """激活指定插件版本"""
        plugin_dir = self.plugin_root / plugin_name
        
        # 创建符号链接 (Windows使用junction)
        current_link = plugin_dir / "current"
        target_dir = plugin_dir / "versions" / version
        
        if current_link.exists():
            if os.name == 'nt':  # Windows
                import _winapi
                _winapi.CreateJunction(str(target_dir), str(current_link))
            else:  # Unix-like
                if current_link.is_symlink():
                    current_link.unlink()
                current_link.symlink_to(target_dir, target_is_directory=True)
        else:
            if os.name == 'nt':
                import _winapi
                _winapi.CreateJunction(str(target_dir), str(current_link))
            else:
                current_link.symlink_to(target_dir, target_is_directory=True)
    
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

    # 扫描可用插件
    plugin_manager.discover_plugins()

    # 加载示例插件
    plugin_manager.load_plugin("example_plugin", "1_0_0") 

    # # 获取插件状态
    status = plugin_manager.get_plugin_status("example_plugin")
    print(f"插件状态: {status}")

    # 更新插件 (假设有新版本文件)
    # plugin_manager.update_plugin("example_plugin", "1_1_0")

    # 回滚插件到旧版本
    # plugin_manager.rollback_plugin("example_plugin", "1_0_0")

    # # 卸载插件
    plugin_manager.unload_plugin("example_plugin")

    # # 关闭插件管理器
    plugin_manager.shutdown()