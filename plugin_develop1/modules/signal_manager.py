from PyQt5.QtCore import QObject, pyqtSignal, Qt
from typing import Any, Dict, List, Tuple, Optional, Type, Union
import threading
import inspect
from weakref import WeakMethod, ref
import re
from .base_module import BaseModule



# 异常定义
class SignalManagerError(Exception):
    """信号管理基础异常
        Args:
            message (str): 可读错误信息
    """

    def __init__(self, message: str):
        self.message = message # 可读错误信息
        super().__init__(message)

    def __str__(self):  # 添加字符串表示
        return self.message


class SignalManager(BaseModule):
    """
    信号管理器，负责统一管理应用程序中的Qt信号

    特性：
    - 支持模块化信号注册与管理
    - 线程安全的信号触发机制
    """
    ui_component_registered = pyqtSignal(str, str)  # (组件路径, 信号名称)
    ui_component_connected = pyqtSignal(str, str, str)  # (组件路径, 信号名称, 连接类型)
    ui_component_disconnected = pyqtSignal(str, str, str)  # (组件路径, 信号名称, 连接类型)
    ui_component_unregistered = pyqtSignal(str, str)  # (组件路径, 信号名称)

    regular_component_registered = pyqtSignal(str, str)  # (组件路径, 信号名称)
    regular_component_connected = pyqtSignal(str, str, str)  # (组件路径, 信号名称, 连接类型)
    regular_component_disconnected = pyqtSignal(str, str, str)  # (组件路径, 信号名称, 连接类型)
    regular_component_unregistered = pyqtSignal(str, str)  # (组件路径, 信号名称)



    """
         self._regular_signals: Dict[str, pyqtSignal] # 统一数据结构：常规信号 {模块.信号名: 信号实例}
         self._ui_signals: Dict[str, pyqtSignal] # 统一数据结构：常规信号 {模块.信号名: 信号实例}
    问题分析
        在 SignalContainer 类中，pyqtSignal 是动态创建的，但是它没有被正确绑定到一个 QObject 实例上，从而导致无法调用 connect 方法。
    解决方案
        要保证 pyqtSignal 被正确绑定到 QObject 实例上。可以通过在 SignalContainer 类里定义信号作为类属性来实现。
    """
    def __init__(self):
        super().__init__()
        # 统一数据结构：常规信号 {模块.信号名: 信号实例}
        self._regular_signals: Dict[str, SignalManager.SignalContainer] = {}
        # 统一数据结构：UI信号 {组件路径.信号名: 信号实例}
        self._ui_signals: Dict[str, SignalManager.SignalContainer] = {}
        # 线程锁，用于保护信号操作
        self._lock = threading.RLock() 
        print("SignalManager 初始化完成")
    #设置模块名称
    @property
    def module_name(self) -> str:
        return "signal"
        # 
    class SignalContainer(QObject):
        """信号容器用于正确绑定信号到QObject
        Args:
            *types: 信号参数类型
        Attributes:
            signal_instance: 动态创建的信号实例
        """
        def __init__(self, *types: Type):
            super().__init__()
            # 动态创建信号类
            signal_class = type('DynamicSignal', (QObject,), {'signal': pyqtSignal(*types)})
            # 实例化信号类
            self.signal_instance = signal_class()
            print("SignalContainer 初始化完成")
    
    # ------------------ 常规信号 ------------------
    def register_regular_signal(self, module_name: str, signal_name: str, *types: Type) -> None:
        """注册常规信号
        Args:
            module_name (str): 模块名称
            signal_name (str): 信号名称
            *types: 信号参数类型
        """
        try:
            regular_name = f"{module_name}.{signal_name}"  # 构建常规信号名称
            if regular_name in self._regular_signals:
                raise SignalManagerError(f"常规信号 '{regular_name}' 已存在")

            # 使用SignalContainer包装信号
            container = self.SignalContainer(*types)
            # 存储容器而非直接存储信号
            self._regular_signals[regular_name] = container  
            # 发射注册信号
            self.regular_component_registered.emit(module_name, signal_name)
            print(f"成功注册常规信号: {regular_name}")
        except SignalManagerError as e:
            print(f"注册常规信号失败: {e}")

    def connect_regular_signal(self, module_name: str, signal_name: str, slot: callable,
                               connection_type: Qt.ConnectionType = Qt.QueuedConnection) -> None:
        """连接常规信号到槽函数
        Args:
            module_name (str): 模块名称
            signal_name (str): 信号名称
            slot (callable): 槽函数
            connection_type (Qt.ConnectionType): 连接类型
        Raises:
            SignalManagerError: 连接失败时抛出
        """
        try:
            # 构建常规信号名称
            regular_name = f"{module_name}.{signal_name}" 
            # 检查信号是否存在
            if regular_name not in self._regular_signals:
                raise SignalManagerError(f"常规信号 '{regular_name}' 不存在")
            # 从容器获取信号实例
            signal = self._regular_signals[regular_name].signal_instance.signal
            # 连接信号到槽函数
            signal.connect(slot, type=connection_type)
            # 手动映射连接类型到名称
            connection_type_name = {
                Qt.AutoConnection: "AutoConnection",
                Qt.DirectConnection: "DirectConnection",
                Qt.QueuedConnection: "QueuedConnection",
                Qt.BlockingQueuedConnection: "BlockingQueuedConnection",
                Qt.UniqueConnection: "UniqueConnection"
            }.get(connection_type, "UnknownConnection")
            # 发射连接信号
            self.regular_component_connected.emit(module_name, signal_name, connection_type_name)
            print(f"成功连接常规信号 {regular_name} 到槽函数，连接类型: {connection_type_name}")
        except SignalManagerError as e:
            print(f"连接常规信号失败: {e}")

    def disconnect_regular_signal(self, module_name: str, signal_name: str, slot: callable,
                                  connection_type: Qt.ConnectionType = Qt.QueuedConnection) -> None:
        """断开常规信号与槽函数的连接
        Args:
            module_name (str): 模块名称
            signal_name (str): 信号名称
            slot (callable): 槽函数
            connection_type (Qt.ConnectionType): 连接类型
        Raises:
            SignalManagerError: 断开连接失败时抛出
        """
        try:
            # 构建常规信号名称
            regular_name = f"{module_name}.{signal_name}"
            # 检查信号是否存在
            if regular_name not in self._regular_signals:
                raise SignalManagerError(f"常规信号 '{regular_name}' 不存在")
            # 从容器获取信号实例
            signal = self._regular_signals[regular_name].signal_instance.signal
            # 断开信号与槽函数的连接
            signal.disconnect(slot)
            # 手动映射连接类型到名称
            connection_type_name = {
                Qt.AutoConnection: "AutoConnection",
                Qt.DirectConnection: "DirectConnection",
                Qt.QueuedConnection: "QueuedConnection",
                Qt.BlockingQueuedConnection: "BlockingQueuedConnection",
                Qt.UniqueConnection: "UniqueConnection"
            }.get(connection_type, "UnknownConnection")
            # 发射断开连接信号
            self.regular_component_disconnected.emit(module_name, signal_name, connection_type_name)
            print(f"成功断开常规信号 {regular_name} 与槽函数的连接，连接类型: {connection_type_name}")
        except SignalManagerError as e:
            print(f"断开常规信号失败: {e}")

    def unregister_regular_signal(self, module_name: str, signal_name: str) -> None:
        """注销常规信号
        Args:
            module_name (str): 模块名称
            signal_name (str): 信号名称
        Raises:
            SignalManagerError: 注销失败时抛出
        """
        try:
            # 构建常规信号名称
            regular_name = f"{module_name}.{signal_name}"
            # 检查信号是否存在
            if regular_name not in self._regular_signals:
                raise SignalManagerError(f"常规信号 '{regular_name}' 不存在")
            # 删除信号容器
            del self._regular_signals[regular_name]
            # 发射注销信号
            self.regular_component_unregistered.emit(module_name, signal_name)
            print(f"成功注销常规信号: {regular_name}")
        except SignalManagerError as e:
            print(f"注销常规信号失败: {e}")

    # ------------------ UI信号 ------------------
    def register_ui_signal(self, component_path: str, signal_name: str, *types: Type) -> None:
        """注册UI信号
        Args:
            component_path (str): 组件路径
            signal_name (str): 信号名称
            *types: 信号参数类型
        """
        try:
            # 构建UI信号名称
            ui_name = f"{component_path}.{signal_name}"
            # 检查UI信号是否已存在
            if ui_name in self._ui_signals:
                raise SignalManagerError(f"UI信号 '{ui_name}' 已存在")

            # 使用SignalContainer包装信号
            container = self.SignalContainer(*types)
            # 存储容器而非直接存储信号
            self._ui_signals[ui_name] = container
            # 发射注册信号
            self.ui_component_registered.emit(component_path, signal_name)
            print(f"成功注册UI信号: {ui_name}")
        except SignalManagerError as e:
            print(f"注册UI信号失败: {e}")

    def connect_ui_signal(self, component_path: str, signal_name: str, slot: callable,
                          connection_type: Qt.ConnectionType = Qt.QueuedConnection) -> None:
        """连接UI信号到槽函数
        Args:
            component_path (str): 组件路径
            signal_name (str): 信号名称
            slot (callable): 槽函数
            connection_type (Qt.ConnectionType): 连接类型
        Raises:
            SignalManagerError: 连接失败时抛出
        """
        try:
            # 构建UI信号名称
            ui_name = f"{component_path}.{signal_name}"
            # 检查UI信号是否存在
            if ui_name not in self._ui_signals:
                raise SignalManagerError(f"UI信号 '{ui_name}' 不存在")

            # 从容器获取信号实例    
            signal = self._ui_signals[ui_name].signal_instance.signal
            # 连接信号到槽函数
            signal.connect(slot, type=connection_type)
            # 手动映射连接类型到名称
            connection_type_name = {
                Qt.AutoConnection: "AutoConnection",
                Qt.DirectConnection: "DirectConnection",
                Qt.QueuedConnection: "QueuedConnection",
                Qt.BlockingQueuedConnection: "BlockingQueuedConnection",
                Qt.UniqueConnection: "UniqueConnection"
            }.get(connection_type, "UnknownConnection")
            # 发射连接信号
            self.ui_component_connected.emit(component_path, signal_name, connection_type_name)
            print(f"成功连接UI信号 {ui_name} 到槽函数，连接类型: {connection_type_name}")
        except SignalManagerError as e:
            print(f"连接UI信号失败: {e}")

    def disconnect_ui_signal(self, component_path: str, signal_name: str, slot: callable,
                             connection_type: Qt.ConnectionType = Qt.QueuedConnection) -> None:
        """断开UI信号与槽函数的连接
        Args:
            component_path (str): 组件路径
            signal_name (str): 信号名称
            slot (callable): 槽函数
            connection_type (Qt.ConnectionType): 连接类型
        Raises:
            SignalManagerError: 断开连接失败时抛出
        """
        try:
            # 构建UI信号名称
            ui_name = f"{component_path}.{signal_name}"
            # 检查UI信号是否存在
            if ui_name not in self._ui_signals:
                raise SignalManagerError(f"UI信号 '{ui_name}' 不存在")
            
            # 从容器获取信号实例
            signal = self._ui_signals[ui_name].signal_instance.signal
            # 断开信号与槽函数的连接
            signal.disconnect(slot)
            # 手动映射连接类型到名称
            connection_type_name = {
                Qt.AutoConnection: "AutoConnection",
                Qt.DirectConnection: "DirectConnection",
                Qt.QueuedConnection: "QueuedConnection",
                Qt.BlockingQueuedConnection: "BlockingQueuedConnection",
                Qt.UniqueConnection: "UniqueConnection"
            }.get(connection_type, "UnknownConnection")
            # 发射断开连接信号
            self.ui_component_disconnected.emit(component_path, signal_name, connection_type_name)
            print(f"成功断开UI信号 {ui_name} 与槽函数的连接，连接类型: {connection_type_name}")
        except SignalManagerError as e:
            print(f"断开UI信号失败: {e}")

    def unregister_ui_signal(self, component_path: str, signal_name: str) -> None:
        """注销UI信号
        Args:
            component_path (str): 组件路径
            signal_name (str): 信号名称
        Raises:
            SignalManagerError: 注销失败时抛出
        """
        try:
            # 构建UI信号名称
            ui_name = f"{component_path}.{signal_name}"
            # 检查UI信号是否存在
            if ui_name not in self._ui_signals:
                raise SignalManagerError(f"UI信号 '{ui_name}' 不存在")
            
            # 删除信号容器
            del self._ui_signals[ui_name]
            # 发射注销信号
            self.ui_component_unregistered.emit(component_path, signal_name)
            print(f"成功注销UI信号: {ui_name}")
        except SignalManagerError as e:
            print(f"注销UI信号失败: {e}")

    # ------------------ 信号获取 ------------------
    def get_ui_signal(self, component_path: str, signal_name: str) -> Optional[pyqtSignal]:
        """获取指定UI信号（只读）
        Args:
            component_path (str): 组件路径
            signal_name (str): 信号名称
        Returns:
            Optional[pyqtSignal]: 信号实例或None
        """
        # 构建UI信号名称
        container = self._ui_signals.get(f"{component_path}.{signal_name}")
        # 返回信号实例或None
        return container.signal_instance.signal if container else None

    def get_regular_signal(self, module_name: str, signal_name: str) -> Optional[pyqtSignal]:
        """获取指定常规信号（只读）"""
        # 构建常规信号名称
        container = self._regular_signals.get(f"{module_name}.{signal_name}")
        # 返回信号实例或None
        return container.signal_instance.signal if container else None

    # ------------------ 信号触发 ------------------
    def emit_ui_signal(self, component_path: str, signal_name: str, *args: Any) -> None:
        """触发UI信号
        Args:
            component_path (str): 组件路径
            signal_name (str): 信号名称
            *args: 信号参数
        Raises:
            SignalManagerError: 触发失败时抛出
        """
        # 构建UI信号名称
        ui_name = f"{component_path}.{signal_name}"
        # 检查UI信号是否存在
        if ui_name not in self._ui_signals:
            raise SignalManagerError(f"UI信号 '{ui_name}' 不存在")

        print(f"开始触发UI信号: {ui_name}")
        # 触发信号
        self._ui_signals[ui_name].signal_instance.signal.emit(*args) 
        print(f"UI信号 {ui_name} 触发完成")

    def emit_regular_signal(self, module_name: str, signal_name: str, *args: Any) -> None:
        """触发常规信号
        Args:
            module_name (str): 模块名称
            signal_name (str): 信号名称
            *args: 信号参数
        Raises:
            SignalManagerError: 触发失败时抛出
        """
        # 构建常规信号名称
        regular_name = f"{module_name}.{signal_name}"
        # 检查常规信号是否存在
        if regular_name not in self._regular_signals:
            raise SignalManagerError(f"常规信号 '{regular_name}' 不存在")

        print(f"开始触发常规信号: {regular_name}")
        # 触发信号
        self._regular_signals[regular_name].signal_instance.signal.emit(*args)
        print(f"常规信号 {regular_name} 触发完成")


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    
    # 实例化信号管理器
    signal_manager = SignalManager()

    # 定义槽函数
    def handle_data(num: int):
        print("Received data:", num)

    # 注册常规信号
    signal_manager.register_regular_signal("data_module", "data_updated", int)
    # 连接常规信号
    signal_manager.connect_regular_signal("data_module", "data_updated", handle_data)
    # 触发常规信号
    signal_manager.emit_regular_signal("data_module", "data_updated", 123)
    # 断开常规信号连接
    signal_manager.disconnect_regular_signal("data_module", "data_updated", handle_data)
    # 注销常规信号
    signal_manager.unregister_regular_signal("data_module", "data_updated")


    # 定义UI槽函数
    def handle_ui_event(clicked: bool):
        print("UI button clicked:", clicked)

    # 注册UI信号
    signal_manager.register_ui_signal("ui_component", "button_clicked", bool)
    # 连接UI信号
    signal_manager.connect_ui_signal("ui_component", "button_clicked", handle_ui_event)
    # 触发UI信号
    signal_manager.emit_ui_signal("ui_component", "button_clicked", True)
    # 断开UI信号连接
    signal_manager.disconnect_ui_signal("ui_component", "button_clicked", handle_ui_event)
    # 注销UI信号
    signal_manager.unregister_ui_signal("ui_component", "button_clicked")

    sys.exit(app.exec_())

