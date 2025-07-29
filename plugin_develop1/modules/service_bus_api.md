# 服务总线 API 文档
- 本模块提供核心服务总线（`CoreServiceBus`）和插件服务总线（`PluginServiceBus`）的实现，用于管理服务/插件的注册、注销及元数据管理。支持线程安全操作，并通过信号机制通知服务状态变化。

## 异常类

### `ServiceBusError`
服务总线基础异常。

**参数**:
- `code` (int): 错误代码。
- `message` (str): 可读错误信息。

### `PermissionDeniedError`
权限校验失败异常（继承自 `ServiceBusError`）。

**触发条件**:
- 当尝试访问未授权的服务或方法时抛出。

### `DatabaseConnectionError`
数据库连接异常（继承自 `ServiceBusError`）。

**触发条件**:
- 数据库连接失败时抛出。

## 核心服务总线 (CoreServiceBus)

### 服务接口白名单(后期可添加)

| 服务名称 | 支持的操作 |
|----------|------------|
| database | read, write |
| signal | connect_signal, disconnect_signal |
| plugin | register_service, unregister_service, get_service |
| window | create_window, delete_window 
| network | connect, send, receive, disconnect |

### 数据结构

#### `ServiceMetadata`
服务元数据规范，用于描述服务实例及其方法。

**属性**:
- `instances` (Dict[str, List[str]]): 实例与方法的映射，格式为 `{实例名称: [方法1, 方法2, ...]}`。

#### `PluginServiceMetadata`
插件服务元数据规范，继承自 `ServiceMetadata`，扩展版本和接口格式信息。

**属性**:
- `instances` (继承自 `ServiceMetadata`): 实例方法映射。
- `version` (str): 接口版本号（遵循语义化版本规范）。
- `interface_format` (str): 接口格式标准（如 `"json-rpc-2.0"`）。

### 信号
    # 服务注册和注销均会发出信号
    service_registered = pyqtSignal(str)  # 服务注册信号
    service_unregistered = pyqtSignal(str)  # 服务注销信号
### 主要方法
#### 心跳监测
    def __init_health_check_signal(self) -> None:  
    def __on_health_checks(self) -> None:
#### 注册服务
    @with_mutex(lock=QMutex(QMutex.Recursive))
    def register_service(self, name: str, service: Any) -> None:
        """注册服务
        :param name: 服务名称
        :param service: 服务实例
        """
#### 注销服务
     @with_mutex(lock=QMutex(QMutex.Recursive))
        def unregister_service(self, name: str) -> None:
            """注销服务
            :param name: 要注销的服务名称
            """
#### 获取已注册服务列表
    @with_mutex(lock=QMutex(QMutex.Recursive))
    def get_registered_services(self, include_metadata: bool = False) -> list:
        """获取已注册服务列表
        :param include_metadata: 是否包含元数据（默认只返回服务名称）
        :return: 服务名称列表或包含元数据的字典
        """
#### 获取已注册的服务实例
    @with_mutex(lock=QMutex(QMutex.Recursive))
        def get_service(self, name: str) -> Any:
            """获取已注册的服务实例"""
#### 权限检测
    def _check_access_permission(self, service_name: str) -> bool:
        """访问权限检查（需根据实际白名单机制实现）"""
#### 关闭总线
    @with_mutex(lock=QMutex(QMutex.Recursive))
    def shutdown(self) -> None:
        """
        关闭服务总线
        """
## 插件服务总线 (PluginServiceBus)
### 信号
    # 插件注册和注销时均会触发信号
    plugin_registered = pyqtSignal(str)  # 插件注册信号
    plugin_unregistered = pyqtSignal(str)  # 插件注销信号
### 主要方法
#### 注册插件
     def register_plugin(self, name: str, service: Any) -> None:
            """注册插件
            :param name: 插件名称
            :param service: 插件实例
            """
#### 注销插件
    def unregister_plugin(self, name: str) -> None:
        """注销插件
        :param name: 要注销的插件名称
        """
#### 获取插件数据
    def get_plugin(self, name: str) -> PluginServiceMetadata:
        """获取插件元数据
        :param name: 插件名称
        :return: 插件元数据
        """
#### 关闭总线
    def shutdown(self) -> None:
        """
        关闭插件服务总线
        """

## examples
```python
if __name__ == "__main__":
    # 新建测试服务类
    class TestServices:
        def e(self):
            print("执行核心服务方法e")

        def f(self):
            print("执行核心服务方法f")

        def g(self):
            print("执行核心服务方法g")
            return "g方法返回值"


    class Windows:
        def create_window(self):
            print("创建窗口")

        def delete_window(self):
            print("删除窗口")


    # 测试核心服务总线功能
    print("\n=== 测试核心服务总线 ===")
    core_bus = CoreServiceBus()
    # 在白名单中的服务
    core_bus.register_service('window', Windows())
    test_service = core_bus.get_service('window')
    print("已注册的服务：", core_bus.get_registered_services())
    # 非白名单中的服务
    core_bus.register_service('Test_services', TestServices())
    test_service1 = core_bus.get_service('Test_services')
    print("已注册的服务：", core_bus.get_registered_services())
    # 注销存在的服务
    core_bus.unregister_service('Test_services')
    print("已注册的服务：", core_bus.get_registered_services())
    # 注销不存在的服务
    core_bus.unregister_service('Test_services1')

    print("\n=== 测试插件服务总线 ===")
    # 新增测试插件类
    class TestPlugin:
        def a(self):
            print("执行方法a")

        def b(self, param):
            print(f"执行方法b，参数：{param}")

        def c(self):
            return "方法c的返回值"

    # 测试白名单继承
    plugin_bus = PluginServiceBus(core_bus)
    # 测试核心服务白名单继承
    print("\n测试核心服务白名单继承:")
    for name in plugin_bus._plugin_registry:
        metadata = plugin_bus.get_plugin(name)
        print(f"插件总线包含核心服务: {name}  实例: {metadata.instances} "
              f"版本: {metadata.version} 接口格式: {metadata.interface_format}")
  # 测试插件注册功能
    print("测试插件注册:")
    plugin_bus.register_plugin("test_plugin", TestPlugin())
    print("当前注册的插件:", list(plugin_bus._plugin_registry.keys()))

    # 新增实例方法验证
    plugin = plugin_bus.get_plugin("test_plugin").instances["test_plugin"]
    print("\n")
    plugin.a()
    plugin.b("测试参数")
    print(plugin.c(),"\n")
    print("\n注册后--当前注册的插件详细信息:")
    for name in plugin_bus._plugin_registry:
        metadata = plugin_bus.get_plugin(name)
        print(f"插件名称: {name}  实例: {metadata.instances} "
              f"版本: {metadata.version} 接口格式: {metadata.interface_format}")

    plugin_bus.unregister_plugin("test_plugin")
    print("\n注销后--当前注册的插件详细信息:")
    for name in plugin_bus._plugin_registry:
        metadata = plugin_bus.get_plugin(name)
        print(f"插件名称: {name}  实例: {metadata.instances} "
              f"版本: {metadata.version} 接口格式: {metadata.interface_format}")

    plugin_bus.shutdown()

    print("\n注销总线后--当前注册的插件详细信息:")
    for name in plugin_bus._plugin_registry:
        metadata = plugin_bus.get_plugin(name)
        print(f"插件名称: {name}  实例: {metadata.instances} "
              f"版本: {metadata.version} 接口格式: {metadata.interface_format}")

