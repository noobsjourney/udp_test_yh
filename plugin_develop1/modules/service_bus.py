from typing import Any, Dict, List
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
from dataclasses import dataclass
from modules.signal_manager import SignalManager
from modules.thread_executor import ThreadExecutor
from .node_info import NodeInfo
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
        if self.__class__._instance is not None:
            raise RuntimeError("请使用instance()方法获取单例")
        super().__init__()

# ---------- 核心服务总线 ----------
class CoreServiceBus(QObject):
    # ========== 单例模式实现 ==========
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls):
        """获取单例实例 (线程安全版)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # 绕过__init__创建实例
                    instance = cls.__new__(cls)
                    # 手动初始化
                    instance.__init__()
                    cls._instance = instance
        return cls._instance

    # ========== 初始化方法 ==========
    def __init__(self):
        """禁止直接实例化"""
        if self.__class__._instance is not None:
            raise RuntimeError("请使用instance()方法获取单例")

        super().__init__()

        # ---------- 服务元数据 ----------
        self._service_registry: Dict[str, Any] = {}
        self._interface_metadata: Dict[str, ServiceMetadata] = {
            "database": ServiceMetadata({"database": ["read", "write"]}),
            "signal": ServiceMetadata({"signal": ["connect", "disconnect"]}),
            "plugin": ServiceMetadata({"plugin": ["register", "unregister"]}),
            "network": ServiceMetadata({"network": ["send", "receive"]})
        }

        # ---------- 核心子系统初始化 ----------
        self.signal_manager = SignalManager(self)
        self.thread_executor = ThreadExecutor(self)
        self.node_info = NodeInfo()

        # ---------- 服务注册 ----------
        self.__register_service("signal", self.signal_manager)
        self.__register_service("thread", self.thread_executor)
        self.__register_service("node", self.node_info)

        # ---------- 网络通信系统 ----------
        self._network_signals = {
            "net_out": self.SignalContainer(str, bytes),
            "net_in": self.SignalContainer(str, bytes)
        }

        # ---------- 健康监测 ----------
        self.health_check_timer = QTimer()
        self.health_check_timer.timeout.connect(self.__on_health_check)
        self.health_check_timer.start(30000)  # 30秒间隔

        # ---------- 插件总线 ----------
        self.plugin_bus = PluginServiceBus(self)

        print("[CoreServiceBus] 初始化完成")

    # ========== 信号定义 ==========
    service_registered = pyqtSignal(str)
    service_unregistered = pyqtSignal(str)

    class SignalContainer(QObject):
        def __init__(self, *types):
            super().__init__()
            self.signal = pyqtSignal(*types)

    # ========== 网络通信接口 ==========
    def get_network_signal(self, name: str) -> pyqtSignal:
        """获取网络信号实例"""
        if name not in self._network_signals:
            raise ValueError(f"未知网络信号: {name}")
        return self._network_signals[name].signal

    # ========== 服务管理方法 ==========
    @with_mutex(QMutex(QMutex.Recursive))
    def __register_service(self, name: str, service: Any):
        """内部服务注册方法"""
        if name in self._service_registry:
            raise ServiceBusError(1001, f"服务 {name} 已存在")

        self._service_registry[name] = service
        self.service_registered.emit(name)
        print(f"[服务注册] {name}")

    @with_mutex(QMutex(QMutex.Recursive))
    def get_service(self, name: str) -> Any:
        """获取已注册服务"""
        if name not in self._service_registry:
            raise ServiceBusError(1002, f"服务 {name} 未注册")
        return self._service_registry[name]

    @with_mutex(QMutex(QMutex.Recursive))
    def get_registered_services(self) -> List[str]:
        """获取已注册服务列表"""
        return list(self._service_registry.keys())

    # ========== 系统维护方法 ==========
    def __on_health_check(self):
        """健康检查回调"""
        print("[健康检查] 系统运行正常")

    @with_mutex(QMutex(QMutex.Recursive))
    def shutdown(self):
        """关闭服务总线"""
        print("正在关闭服务总线...")
        self.health_check_timer.stop()
        self._service_registry.clear()
        print("服务总线已关闭")


class PluginServiceBus(QObject):

    plugin_registered = pyqtSignal(str)  # 插件注册信号
    plugin_unregistered = pyqtSignal(str)  # 插件注销信号

    def forward_network_data(self, plugin_id: str, data: bytes):
        self.core_bus.get_network_signal("net_out").emit(plugin_id, data)

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


# if __name__ == "__main__":
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
