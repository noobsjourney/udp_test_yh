# SignalManager 类 API 文档

## 一、概述

- SignalManager 类是一个用于管理 PyQt5 信号的工具类，它提供了对常规信号和 UI 信号的注册、连接、断开连接、注销以及触发等功能。该类支持模块化信号管理，确保信号的统一管理和线程安全的信号触发机制。
## 二、类定义和初始化

###   1. 类定义
      class SignalManager(QObject):
          ...
      SignalManager 继承自 QObject，这是 PyQt5 中所有对象的基类，用于支持信号和槽机制。

### 2. 初始化方法
    def __init__(self):
        super().__init__()
        self._regular_signals: Dict[str, SignalManager.SignalContainer] = {}
        self._ui_signals: Dict[str, SignalManager.SignalContainer] = {}
        self._lock = threading.RLock()
        print("SignalManager 初始化完成")

-   _regular_signals：一个字典，用于存储常规信号，键为 模块名.信号名，值为 SignalContainer 实例。
-   _ui_signals：一个字典，用于存储 UI 信号，键为 组件路径.信号名，值为 SignalContainer 实例。
-   _lock：锁用于保证线程安全。

### 3. SignalContainer 类

    class SignalContainer(QObject):
        def __init__(self, *types: Type):
            super().__init__()
            signal_class = type('DynamicSignal', (QObject,), {'signal': pyqtSignal(*types)})
            self.signal_instance = signal_class()
            print("SignalContainer 初始化完成")
-   SignalContainer 继承自 QObject，用于将信号正确绑定到 QObject 实例。
-   signal_instance：一个动态创建的 QObject 子类实例，包含一个 pyqtSignal 信号。

## 三、常规信号管理

### 1. 注册常规信号

    def register_regular_signal(self, module_name: str, signal_name: str, *types: Type) -> None:
        ...

#### 参数：

    module_name：模块名称，字符串类型。
    signal_name：信号名称，字符串类型。
    *types：信号参数的类型，可变参数。

#### 功能：
    注册一个常规信号，如果信号已存在则抛出 SignalManagerError 异常。

### 2. 连接常规信号到槽函数

    def connect_regular_signal(self, module_name: str, signal_name: str, slot: callable,
                           connection_type: Qt.ConnectionType = Qt.QueuedConnection) -> None:
    ...

#### 参数：

    module_name：模块名称，字符串类型。
    signal_name：信号名称，字符串类型。
    slot：槽函数，可调用对象。
    connection_type：连接类型，默认为 Qt.QueuedConnection。

#### 功能：
    将常规信号连接到指定的槽函数，如果信号不存在则抛出 SignalManagerError 异常。

### 3. 断开常规信号与槽函数的连接

    def disconnect_regular_signal(self, module_name: str, signal_name: str, slot: callable,
                              connection_type: Qt.ConnectionType = Qt.QueuedConnection) -> None:
    ...

#### 参数：
    module_name：模块名称，字符串类型。
    signal_name：信号名称，字符串类型。
    slot：槽函数，可调用对象。
    connection_type：连接类型，默认为 Qt.QueuedConnection。
#### 功能：
    断开常规信号与指定槽函数的连接，如果信号不存在则抛出 SignalManagerError 异常。

### 4. 注销常规信号
    def unregister_regular_signal(self, module_name: str, signal_name: str) -> None:
    ...

#### 参数：
    module_name：模块名称，字符串类型。
    signal_name：信号名称，字符串类型。
#### 功能：
    注销一个常规信号，如果信号不存在则抛出 SignalManagerError 异常。

## 四、UI 信号管理

### 1. 注册 UI 信号

    def register_ui_signal(self, component_path: str, signal_name: str, *types: Type) -> None:
    ...

#### 参数：

    component_path：组件路径，字符串类型。
    signal_name：信号名称，字符串类型。
    *types：信号参数的类型，可变参数。

#### 功能：
    注册一个 UI 信号，如果信号已存在则抛出 SignalManagerError 异常。

### 2. 连接 UI 信号到槽函数

    def connect_ui_signal(self, component_path: str, signal_name: str, slot: callable,
                      connection_type: Qt.ConnectionType = Qt.QueuedConnection) -> None:
    ...

#### 参数：

    component_path：组件路径，字符串类型。
    signal_name：信号名称，字符串类型。
    slot：槽函数，可调用对象。
    connection_type：连接类型，默认为 Qt.QueuedConnection。

#### 功能：
    将 UI 信号连接到指定的槽函数，如果信号不存在则抛出 SignalManagerError 异常。

### 3. 断开 UI 信号与槽函数的连接

    def disconnect_ui_signal(self, component_path: str, signal_name: str, slot: callable,
                         connection_type: Qt.ConnectionType = Qt.QueuedConnection) -> None:
    ...

#### 参数：

    component_path：组件路径，字符串类型。
    signal_name：信号名称，字符串类型。
    slot：槽函数，可调用对象。
    connection_type：连接类型，默认为 Qt.QueuedConnection。

#### 功能：
    断开 UI 信号与指定槽函数的连接，如果信号不存在则抛出 SignalManagerError 异常。

### 4. 注销 UI 信号

    def unregister_ui_signal(self, component_path: str, signal_name: str) -> None:
    ...

#### 参数：

    component_path：组件路径，字符串类型。
    signal_name：信号名称，字符串类型。

#### 功能：
    注销一个 UI 信号，如果信号不存在则抛出 SignalManagerError 异常。

## 五、信号获取

### 1. 获取指定 UI 信号

    def get_ui_signal(self, component_path: str, signal_name: str) -> Optional[pyqtSignal]:
        ...

#### 参数：

    component_path：组件路径，字符串类型。
    signal_name：信号名称，字符串类型。
    返回值：如果信号存在，返回 pyqtSignal 实例；否则返回 None。

### 2. 获取指定常规信号

    def get_regular_signal(self, module_name: str, signal_name: str) -> Optional[pyqtSignal]:
    ...

#### 参数：

    module_name：模块名称，字符串类型。
    signal_name：信号名称，字符串类型。
    返回值：如果信号存在，返回 pyqtSignal 实例；否则返回 None。

## 六、信号触发

### 1. 触发 UI 信号

    def emit_ui_signal(self, component_path: str, signal_name: str, *args: Any) -> None:
    ...

#### 参数：

    component_path：组件路径，字符串类型。
    signal_name：信号名称，字符串类型。
    *args：信号传递的参数，可变参数。

#### 功能：
    触发指定的 UI 信号，如果信号不存在则抛出 SignalManagerError 异常。

### 2. 触发常规信号

    def emit_regular_signal(self, module_name: str, signal_name: str, *args: Any) -> None:
    ...

#### 参数：

    module_name：模块名称，字符串类型。
    signal_name：信号名称，字符串类型。
    *args：信号传递的参数，可变参数。

#### 功能：
    触发指定的常规信号，如果信号不存在则抛出 SignalManagerError 异常。

## 七、异常处理
SignalManager 类中定义了 SignalManagerError 异常，当信号已存在、信号不存在等情况发生时，会抛出该异常。

    class SignalManagerError(Exception):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

    def __str__(self):
        return self.message

## 八、测试例程

```python
if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    signal_manager = SignalManager()

    # 注册常规信号
    signal_manager.register_regular_signal("data_module", "data_updated", int)

    # 定义槽函数
    def handle_data(num: int):
        print("Received data:", num)

    # 连接常规信号
    signal_manager.connect_regular_signal("data_module", "data_updated", handle_data)

    # 触发常规信号
    signal_manager.emit_regular_signal("data_module", "data_updated", 123)

    # 断开常规信号连接
    signal_manager.disconnect_regular_signal("data_module", "data_updated", handle_data)

    # 注销常规信号
    signal_manager.unregister_regular_signal("data_module", "data_updated")

    # 注册UI信号
    signal_manager.register_ui_signal("ui_component", "button_clicked", bool)

    # 定义UI槽函数
    def handle_ui_event(clicked: bool):
        print("UI button clicked:", clicked)

    # 连接UI信号
    signal_manager.connect_ui_signal("ui_component", "button_clicked", handle_ui_event)

    # 触发UI信号
    signal_manager.emit_ui_signal("ui_component", "button_clicked", True)

    # 断开UI信号连接
    signal_manager.disconnect_ui_signal("ui_component", "button_clicked", handle_ui_event)

    # 注销UI信号
    signal_manager.unregister_ui_signal("ui_component", "button_clicked")

    sys.exit(app.exec_())
















