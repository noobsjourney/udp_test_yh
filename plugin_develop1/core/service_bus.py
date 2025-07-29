#定义核心服务总线（CoreServiceBus）和插件调用中间层（PluginServiceBus）
# 插件系统中“通信与服务调用”

from modules.signal_manager import SignalManager
from modules.thread_executor import ThreadExecutor
from modules.base_module import BaseModule
from modules.node_info import NodeInfo

#插件系统枢纽，集中管理多个核心子系统，系统内的服务注册表和调度中心。
class CoreServiceBus:
    def __init__(self):
        self.signal_manager = SignalManager()#信号/事件调度系统（类似事件总线）
        self.thread_executor = ThreadExecutor()#线程任务调度器（控制后台任务）
        self.plugin_bus = PluginServiceBus()#插件服务调用中间件（你目前最常用的）
        self.node_info = NodeInfo()#节点信息模块（设备或系统元信息）

#插件服务调用总线，管理插件注册和提供服务调用的模块。
class PluginServiceBus:
    def __init__(self):
        self.plugins = {}

    #注册插件实例
    #将插件实例注册到总线中，便于后续调用。
    #插件名作为键，内部是一个instances字典（为将来多实例扩展留出空间）。
    def register_plugin(self, plugin_name, plugin_instance):
        if plugin_name not in self.plugins:
            self.plugins[plugin_name] = {"instances": {}}
        self.plugins[plugin_name]["instances"][plugin_name] = plugin_instance
        print(f"[总线] 插件 {plugin_name} 已注册")

    #调用插件方法
    #指定插件名和方法名后，动态调用该方法。
    # 支持位置参数 (*args) 和关键字参数 (**kwargs)。
    def call_plugin(self, plugin_name, method_name, *args, **kwargs):
        if plugin_name not in self.plugins:
            raise Exception(f"[总线] 插件 {plugin_name} 未注册")
        plugin_instance = self.plugins[plugin_name]["instances"][plugin_name]
        method = getattr(plugin_instance, method_name, None)
        if method is None:
            raise Exception(f"[总线] 插件 {plugin_name} 没有方法 {method_name}")
        return method(*args, **kwargs)
