# ThreadExecutor 模块 API 文档

## 概述

ThreadExecutor 是一个独立线程池管理系统，支持三种线程池模式（QT/IO/COMPUTE），具备全生命周期任务追踪、增强的取消和超时机制以及线程安全的注册表操作。

## 类和数据结构

### TaskResult

    @dataclass
    class TaskResult:
        success: bool
        result: Any = None
        error: Optional[Exception] = None
        traceback: Optional[str] = None

#### 描述：
    标准化任务执行结果容器。

#### 属性：

    success (bool)：任务是否成功执行。
    result (Any)：任务执行结果，默认为 None。
    error (Optional[Exception])：任务执行过程中出现的错误，默认为 None。
    traceback (Optional[str])：错误的堆栈跟踪信息，默认为 None。

### TaskSignals

    class TaskSignals(QObject):
        started = pyqtSignal(str)  # 任务ID
        succeeded = pyqtSignal(str, str)  # 任务ID, 结果
        failed = pyqtSignal(str, str)  # 任务ID, 错误信息
        cancelled = pyqtSignal(str)  # 任务ID
        finished = pyqtSignal(str)  # 任务ID

#### 描述：

    任务生命周期信号集合。

### 信号：

    started (pyqtSignal(str)): 任务开始时发出，携带任务 ID。
    succeeded (pyqtSignal(str, str)): 任务成功完成时发出，携带任务 ID 和结果。
    failed (pyqtSignal(str, str)): 任务失败时发出，携带任务 ID 和错误信息。
    cancelled (pyqtSignal(str)): 任务取消时发出，携带任务 ID。
    finished (pyqtSignal(str)): 任务结束时发出，携带任务 ID。

### TaskWrapper

    class TaskWrapper(QRunnable):
        def __init__(self, task_id: str, fn: Callable, *args, **kwargs):
            ...
    
        def run(self) -> None:
            ...
    
        def cancel(self) -> bool:
            ...

#### 描述：

    任务执行容器。

### __init__(self, task_id: str, fn: Callable, *args, **kwargs)


#### 描述：
    初始化任务执行容器。
    
#### 参数：

    task_id (str)：任务 ID。
    fn (Callable)：要执行的任务函数。
    *args：任务函数的位置参数。
    **kwargs：任务函数的关键字参数。

### run(self) -> None

#### 描述：
    原子化任务执行流程。

#### cancel(self) -> bool

#### 描述：
    原子化任务取消操作。

#### 返回：
    bool：如果任务成功取消返回 True，否则返回 False。

## ThreadExecutor

    class ThreadExecutor(QObject):
        pool_created = pyqtSignal(str, str)  # (池名称, 池类型)
        pool_closed = pyqtSignal(str)  # 池名称
    
        def __init__(self, parent=None):
            ...
    
        def _init_default_pools(self):
            ...
    
        def create_pool(self, name: str, pool_type: str, **kwargs) -> bool:
            ...
    
        def submit(self, fn: Callable, pool_name: str = "qt_default", task_id: Optional[str] = None, *args, **kwargs) -> Optional[str]:
            ...
    
        def shutdown_pool(self, name: str, wait: bool = True) -> bool:
            ...
    
        def cancel_task(self, task_id: str) -> bool:
            ...
    
        def _update_task_state(self, task_id: str, state: str) -> None:
            ...
    
        def _finalize_task(self, task_id: str, result: Any, error: str) -> None:
            ...
    
        def get_active_pools(self) -> Dict[str, str]:
            ...
    
        def get_running_tasks(self) -> Dict[str, str]:
        ...

#### 描述：
    独立线程池管理系统。

#### 信号：

    pool_created (pyqtSignal(str, str)): 线程池创建时发出，携带池名称和池类型。
    pool_closed (pyqtSignal(str)): 线程池关闭时发出，携带池名称。

#### 方法：

    __init__(self, parent=None)

##### 描述：
    初始化独立线程池管理系统。

##### 参数：

    parent (Optional[QObject])：父对象，默认为 None。

#### _init_default_pools(self)

##### 描述：
    初始化默认线程池。

#### create_pool(self, name: str, pool_type: str, **kwargs) -> bool

##### 描述：
    创建新线程池。

##### 参数：

    name (str)：线程池名称。
    pool_type (str)：线程池类型，可选值为 "qt" 或 "standard"。
    **kwargs：线程池配置参数：
    对于 "qt" 类型，可指定 max_threads。
    对于 "standard" 类型，可指定 max_workers 等。

##### 返回：

    bool：如果线程池创建成功返回 True，否则返回 False。

#### submit(self, fn: Callable, pool_name: str = "qt_default", task_id: Optional[str] = None, *args, **kwargs) -> Optional[str]

##### 描述：
    提交任务到指定线程池。

##### 参数：

    fn (Callable)：要执行的任务函数。
    pool_name (str)：线程池名称，默认为 "qt_default"。
    task_id (Optional[str])：任务 ID，默认为 None。
    *args：任务函数的位置参数。
    **kwargs：任务函数的关键字参数。

##### 返回：

    Optional[str]：任务 ID，如果线程池不存在则返回 None。

#### shutdown_pool(self, name: str, wait: bool = True) -> bool

##### 描述：
    闭指定线程池。

##### 参数：

    name (str)：线程池名称。
    wait (bool)：是否等待所有任务完成，默认为 True。

##### 返回：

    bool：如果线程池关闭成功返回 True，否则返回 False。

#### cancel_task(self, task_id: str) -> bool

##### 描述：
    强制取消任务（包括运行中的任务）。

##### 参数：

    task_id (str)：任务 ID。

##### 返回：

    bool：如果任务成功取消返回 True，否则返回 False。

#### _update_task_state(self, task_id: str, state: str) -> None

##### 描述：
    原子化状态更新。

##### 参数：

    task_id (str)：任务 ID。
    state (str)：任务状态。

#### _finalize_task(self, task_id: str, result: Any, error: str) -> None

##### 描述：
    任务最终处理。

##### 参数：

    task_id (str)：任务 ID。
    result (Any)：任务执行结果。
    error (str)：任务执行错误信息。

#### get_active_pools(self) -> Dict[str, str]

##### 描述：
    获取当前活跃线程池信息。

##### 返回：

    Dict[str, str]：键为线程池名称，值为线程池类型。

#### get_running_tasks(self) -> Dict[str, str]

##### 描述：
    获取运行中任务列表。

##### 返回：

    Dict[str, str]：键为任务 ID，值为线程池名称。