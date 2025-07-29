from path_cof import PROJECT_ROOT
from typing import Any, Dict, List
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
from dataclasses import dataclass
from signal_manager import SignalManager
from thread_executor import ThreadExecutor
from node_info import NodeInfo
from base_module import BaseModule
from database.database import DatabaseManager
from database.alembic_migrations import AutoDatabaseMigrator
from database.write_data import WriteData 
#from network_pro import NetworkProtocol
# from database_manager import initialize_database
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker

# 锁装饰器，用于代码复用
def with_mutex(lock):
    def decorator(func):
        def wrapper(*args, **kwargs):
            with QMutexLocker(lock):
                return func(*args, **kwargs)
        return wrapper
    return decorator
""""""

#  核心总线数据表结构定义
@dataclass
class ServiceMetadata:
    """服务元数据规范
        Attributes:
        instances (Dict[str, List[str]]): 实例与方法的映射，格式为{实例名称: [方法1, 方法2, ...]}
    """
    instances: Dict[str, List[str]]

# 插件总线数据表结构定义
@dataclass
class PluginServiceMetadata(ServiceMetadata):  # 继承核心总线数据结构
    """插件服务元数据规范（扩展自核心服务元数据）
        Attributes:
        instances (Dict[str, List[str]]): 继承自ServiceMetadata的实例方法映射
        version (str): 接口版本号，遵循语义化版本规范
        interface_format (str): 接口格式标准，如"json-rpc-2.0"
    """
    version: str
    interface_format: str

# 异常定义
class ServiceBusError(Exception):
    """服务总线基础异常
        Args:
            code (int): 错误代码
            message (str): 可读错误信息
    """

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class PermissionDeniedError(ServiceBusError):
    """权限校验失败异常"""

    def __init__(self, service: str, method: str):
        super().__init__(403, f"访问被拒绝: {service}.{method}")


class DatabaseConnectionError(ServiceBusError):
    """数据库连接异常"""

    def __init__(self, message: str):
        super().__init__(1002, message)

class CoreServiceBus(QObject):

    service_registered = pyqtSignal(str)  # 服务注册信号
    service_unregistered = pyqtSignal(str)  # 服务注销信号
    
    def __init__(self):
        """父类核心初始化"""
        super().__init__()
        print("服务总线初始化")
        self._service_registry: Dict[str, Any] = {}
        self._interface_metadata: Dict[str, ServiceMetadata] = {
            "thread": ServiceMetadata({"thread": ["submit", "create_pool", "shutdown_pool"]}),
            "database": ServiceMetadata({"database": ["read", "write"]}),
            "signal": ServiceMetadata({"signal": ["connect_signal", "disconnect_signal"]}),
            "plugin": ServiceMetadata({"plugin": ["register_service", "unregister_service", "get_service"]}),
            "window": ServiceMetadata({"window": ["create_window", "delete_window"]}),
            "network": ServiceMetadata({"network": ["connect", "send", "receive", "disconnect"]})
        }

        self.signal_manager = SignalManager()  # 初始化信号管理器
        self.__register_service(self.signal_manager.module_name, self.signal_manager)  # 注册信号管理器
        self.node_info = NodeInfo()  # 初始化节点信息
        self.__register_service(self.node_info.module_name, self.node_info)  # 注册节点信息
        # self.database_manager = DatabaseManager()  # 初始化数据库管理器
        # self.__register_service(str(self.database_manager.get_module_name), self.database_manager)  # 注册数据库管理器
        # self.auto_migrator = AutoDatabaseMigrator()  # 初始化数据库迁移器
        # self.__register_service(self.auto_migrator.get_module_name, self.auto_migrator)  # 注册数据库迁移器
        # self.write_data = WriteData()
        # self.__register_service(self.write_data.get_module_name, self.write_data)  # 注册数据库迁移器

        self.thread_executor = ThreadExecutor()  # 初始化线程执行器
        self.__register_service(self.thread_executor.module_name, self.thread_executor)  # 注册线程执行器
        
        self.__init_health_check_signal()
        self.plugin_bus = PluginServiceBus(self)



    def __init_health_check_signal(self) -> None:
        print("心跳监测定时器初始化")
        """初始化心跳监测定时器"""
        self.health_check_timer = QTimer()
        # 当定时器超时（到达设定时间）时，连接到_perform_health_checks方法
        self.health_check_timer.timeout.connect(self.__on_health_checks)
        self.health_check_timer.start(30000)  # 30秒检测一次


    @with_mutex(lock=QMutex(QMutex.Recursive))
    def __on_health_checks(self) -> None:
        """
        这里不能删掉，因为这个是作为心跳检测的槽函数的
        我修改了名称显示 槽函数以_on_开头。
        但具体要操作什么目前没想好(之前是检测数据库连接)
        """
        pass

    # 核心层基础方法
    @with_mutex(lock=QMutex(QMutex.Recursive))
    def __register_service(self, name: str, service: Any) -> None:
        """注册服务
        :param name: 服务名称
        :param service: 服务实例
        """
        print(f"注册服务: {name}")
        try:
            if not isinstance(service, object):
                raise ServiceBusError(400, "Service must be a Object")

            if name in self._service_registry:
                raise ServiceBusError(f"Service {name} is already registered")
            # 存储服务实例到注册表
            self._service_registry[name] = service
            # 发出服务注册信号
            self.service_registered.emit(name)
        except ServiceBusError as e:
            print(f"服务注册失败: {type(e).__name__} - {str(e)}")
            return None

    @with_mutex(lock=QMutex(QMutex.Recursive))
    def __unregister_service(self, name: str) -> None:
        """注销服务
        :param name: 要注销的服务名称
        """
        print(f"正在注销服务: {name}")  # 增强日志输出
        try:
            if name not in self._service_registry:
                raise ServiceBusError(404, f"Service '{name}' not found")

            # 先发出信号再删除服务
            self.service_unregistered.emit(name)
            del self._service_registry[name]

        except ServiceBusError as e:
            print(f"服务获取失败: {type(e).__name__} - {str(e)}")
            return None

    @with_mutex(lock=QMutex(QMutex.Recursive))
    def get_registered_services(self, include_metadata: bool = False) -> list:
        """获取已注册服务列表
        :param include_metadata: 是否包含元数据（默认只返回服务名称）
        :return: 服务名称列表或包含元数据的字典
        """
        if include_metadata:
            return list(self._interface_metadata.items())
        return list(self._service_registry.keys())


    @with_mutex(lock=QMutex(QMutex.Recursive))
    def get_service(self, name: str) -> Any:
        """获取已注册的服务实例
        使用示例：
        在其他模块中获取服务实例：
                __init__(self, core_bus: CoreServiceBus)
        注入核心总线实例：self.core_bus = core_bus
        获取信号中心实例：signal_center = core_bus.get_service("signal")
        使用信号中心注册信号：signal_center.register_signal("my_signal")
        """
        try:
            # 检查服务是否存在
            if name not in self._service_registry:
                raise ServiceBusError(404, f"Service '{name}' not found")
            # 权限校验（基于接口元数据白名单）
            if not self._check_access_permission(name):
                raise PermissionDeniedError(service=name, method="get_service")

            return self._service_registry[name]
        except (PermissionDeniedError, ServiceBusError) as e:
            print(f"服务获取失败: {type(e).__name__} - {str(e)}")
            return None


    def _check_access_permission(self, service_name: str) -> bool:
        """访问权限检查（需根据实际白名单机制实现）"""
        # 示例实现：检查服务是否在公开白名单中
        return service_name in self._interface_metadata


    @with_mutex(lock=QMutex(QMutex.Recursive))
    def shutdown(self) -> None:
        """
        关闭服务总线
        """
        print("关闭服务总线")
        # 停止心跳检测定时器
        self.health_check_timer.stop()
        # 清空服务注册表
        self._service_registry.clear()

class PluginServiceBus(QObject):

    plugin_registered = pyqtSignal(str)  # 插件注册信号
    plugin_unregistered = pyqtSignal(str)  # 插件注销信号

    def __init__(self,core_bus: CoreServiceBus):
        """子类插件总线初始化"""
        super().__init__()
        print("插件服务总线初始化")
        self._core_bus = core_bus
        # 初始化插件注册表
        self._plugin_registry: Dict[str, PluginServiceMetadata] = {
            name: PluginServiceMetadata(
                instances=metadata.instances,
                version="1.0.0",
                interface_format="core-service"
            )
            for name, metadata in self._core_bus._interface_metadata.items()
        }

    def register_plugin(self, name: str, service: Any) -> None:
        """注册插件
        :param name: 插件名称
        :param service: 插件实例
        """
        print("注册插件")
        try:
            if not isinstance(service, object):
                raise ServiceBusError(400, "Service must be a Object")

            if name in self._plugin_registry:
                raise ServiceBusError(f"Plugin {name} already registered")
            # 仅操作插件注册表，不再调用核心总线的注册方法
            plugin_metadata = PluginServiceMetadata(
                instances= {name: service},      # 插件实例
                version="1.0.0",  # 标记为插件服务
                interface_format="plugin-service"  # 内部接口格式
            )
            # 存储插件元数据到注册表
            self._plugin_registry[name] = plugin_metadata
            # 发出插件注册信号
            self.plugin_registered.emit(name)
        except ServiceBusError as e:
            print(f"插件服务注册失败: {type(e).__name__} - {str(e)}")
            return None

    def unregister_plugin(self, name: str) -> None:
        """注销插件
        :param name: 要注销的插件名称
        """
        try:
            if name not in self._plugin_registry:
                raise ServiceBusError(f"Plugin {name} not found")

            metadata = self._plugin_registry[name]
            if metadata.interface_format != "plugin-service":
                raise PermissionDeniedError(service=name, method="unregister_plugin")       
            # 仅操作插件注册表，不再调用核心总线的注销方法
            del self._plugin_registry[name]
            self.plugin_unregistered.emit(name)  # 触发注销信号

        except (ServiceBusError, PermissionDeniedError) as e:
            print(f"插件注销失败: {type(e).__name__} - {str(e)}")
            return None

    def get_plugin(self, name: str) -> PluginServiceMetadata:
        """获取插件元数据"""
        # 检查插件是否存在
        if name not in self._plugin_registry:
            raise ValueError(f"Plugin {name} not found")
        return self._plugin_registry[name]

    def shutdown(self) -> None:
        """
        关闭插件服务总线
        """
        print("关闭插件服务总线")
        # 遍历并注销所有插件
        for plugin_name in list(self._plugin_registry.keys()):
            self.unregister_plugin(plugin_name)
        # 清空插件注册表
        self._plugin_registry.clear()


if __name__ == "__main__":
    pass
#     # 新建测试服务类
#     class TestServices:
#         def e(self):
#             print("执行核心服务方法e")
#
#         def f(self):
#             print("执行核心服务方法f")
#
#         def g(self):
#             print("执行核心服务方法g")
#             return "g方法返回值"
#
#
#     class Windows:
#         def create_window(self):
#             print("创建窗口")
#
#         def delete_window(self):
#             print("删除窗口")
#
#
#     # 测试核心服务总线功能
#     print("\n=== 测试核心服务总线 ===")
#     core_bus = CoreServiceBus()
#     # 在白名单中的服务
#     core_bus.register_service('window', Windows())
#     test_service = core_bus.get_service('window')
#     print("已注册的服务：", core_bus.get_registered_services())
#     # 非白名单中的服务
#     core_bus.register_service('Test_services', TestServices())
#     test_service1 = core_bus.get_service('Test_services')
#     print("已注册的服务：", core_bus.get_registered_services())
#     # 注销存在的服务
#     core_bus.unregister_service('Test_services')
#     print("已注册的服务：", core_bus.get_registered_services())
#     # 注销不存在的服务
#     core_bus.unregister_service('Test_services1')
#
#     print("\n=== 测试插件服务总线 ===")
#     # 新增测试插件类
#     class TestPlugin:
#         def a(self):
#             print("执行方法a")
#
#         def b(self, param):
#             print(f"执行方法b，参数：{param}")
#
#         def c(self):
#             return "方法c的返回值"
#
#     # 测试白名单继承
#     plugin_bus = PluginServiceBus(core_bus)
#     # 测试核心服务白名单继承
#     print("\n测试核心服务白名单继承:")
#     for name in plugin_bus._plugin_registry:
#         metadata = plugin_bus.get_plugin(name)
#         print(f"插件总线包含核心服务: {name}  实例: {metadata.instances} "
#               f"版本: {metadata.version} 接口格式: {metadata.interface_format}")
#   # 测试插件注册功能
#     print("测试插件注册:")
#     plugin_bus.register_plugin("test_plugin", TestPlugin())
#     print("当前注册的插件:", list(plugin_bus._plugin_registry.keys()))
#
#     # 新增实例方法验证
#     plugin = plugin_bus.get_plugin("test_plugin").instances["test_plugin"]
#     print("\n")
#     plugin.a()
#     plugin.b("测试参数")
#     print(plugin.c(),"\n")
#     print("\n注册后--当前注册的插件详细信息:")
#     for name in plugin_bus._plugin_registry:
#         metadata = plugin_bus.get_plugin(name)
#         print(f"插件名称: {name}  实例: {metadata.instances} "
#               f"版本: {metadata.version} 接口格式: {metadata.interface_format}")
#
#     plugin_bus.unregister_plugin("test_plugin")
#     print("\n注销后--当前注册的插件详细信息:")
#     for name in plugin_bus._plugin_registry:
#         metadata = plugin_bus.get_plugin(name)
#         print(f"插件名称: {name}  实例: {metadata.instances} "
#               f"版本: {metadata.version} 接口格式: {metadata.interface_format}")
#
#     plugin_bus.shutdown()
#
#     print("\n注销总线后--当前注册的插件详细信息:")
#     for name in plugin_bus._plugin_registry:
#         metadata = plugin_bus.get_plugin(name)
#         print(f"插件名称: {name}  实例: {metadata.instances} "
#               f"版本: {metadata.version} 接口格式: {metadata.interface_format}")
