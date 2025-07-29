#线程任务管理系统
# 结合了 PyQt5 的 QThreadPool 和 Python 标准库的 ThreadPoolExecutor
# 用于统一提交和管理不同类型的并发任务。

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, Qt, QThreadPool
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, Optional, Union, Tuple
import threading
import traceback
from dataclasses import dataclass
import os
import time
import uuid

from base_module import BaseModule


@dataclass
#封装了任务的执行结果
class TaskResult:
    success: bool#是否成功执行
    result: Any = None# 返回值
    error: Optional[Exception] = None#捕获的异常
    traceback: Optional[str] = None#异常的堆栈信息


class TaskSignals(QObject):
    #定义了任务各个阶段发出的信号
    started = pyqtSignal(str)#任务开始
    succeeded = pyqtSignal(str, str)#成功
    failed = pyqtSignal(str, str)#失败
    cancelled = pyqtSignal(str)#被取消
    finished = pyqtSignal(str)#无论成败都发出

    def __init__(self):
        super().__init__()

#任务执行器
class TaskWrapper(QRunnable):
    def __init__(self, task_id: str, fn: Callable, *args, **kwargs):
        super().__init__()
        print("任务执行容器初始化")
        self.task_id = task_id#任务唯一 ID
        self.fn = fn#执行函数
        self.args = args#参数
        self.kwargs = kwargs
        self.signals = TaskSignals()#定义了任务状态信号
        self._state_lock = threading.Lock()#内部状态管理，防止重复执行或取消。
        self._state = "PENDING"

    def run(self) -> None:
        #开始执行任务；发出 started 信号；如果成功，发出 succeeded 信号；失败则发出 failed 信号；最后一定发出 finished 信号。
        print("原子化任务执行流程")
        with self._state_lock:
            if self._state == "CANCELLED":
                self.signals.cancelled.emit(self.task_id)
                return
            self._state = "RUNNING"

        self.signals.started.emit(self.task_id)
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.succeeded.emit(self.task_id, str(result))
        except Exception as e:
            tb = traceback.format_exc()
            self.signals.failed.emit(self.task_id, f"{type(e).__name__}: {e}\n{tb}")
        finally:
            self.signals.finished.emit(self.task_id)

    def cancel(self) -> bool:
        #只在任务未开始前有效，变更状态为 CANCELLED
        with self._state_lock:
            if self._state == "PENDING":
                self._state = "CANCELLED"
                return True
            return False

#线程池和任务统一管理器，支持 QT 和标准线程池
class ThreadExecutor(BaseModule):
    pool_created = pyqtSignal(str, str)
    pool_closed = pyqtSignal(str)

    def __init__(self, parent=None):
        print("独立线程池管理系统初始化")
        super().__init__()
        self._pools: Dict[str, Tuple[str, Union[QThreadPool, ThreadPoolExecutor]]] = {}
        self._task_registry: Dict[str, Tuple[str, Union[TaskWrapper, Future]]] = {}
        self._registry_lock = threading.RLock()
        self._init_default_pools()

    @property
    def module_name(self) -> str:
        return "thread"


    def _init_default_pools(self):
        print("初始化默认线程池")
        self.create_pool("qt_default", "qt", max_threads=QThreadPool.globalInstance().maxThreadCount())
        self.create_pool("io_default", "standard", max_workers=8)
        self.create_pool("compute_default", "standard", max_workers=os.cpu_count())

    #根据类型创建线程池并注册。
    def create_pool(self, name: str, pool_type: str, **kwargs) -> bool:
        print("创建新线程池")
        with self._registry_lock:
            if name in self._pools:
                return False

            if pool_type == "qt":
                pool = QThreadPool()
                if 'max_threads' in kwargs:
                    pool.setMaxThreadCount(kwargs['max_threads'])
                self._pools[name] = (pool_type, pool)
                self.pool_created.emit(name, "QT")
                return True

            elif pool_type == "standard":
                workers = kwargs.get('max_workers', os.cpu_count())
                pool = ThreadPoolExecutor(max_workers=workers)
                self._pools[name] = (pool_type, pool)
                self.pool_created.emit(name, "STANDARD")
                return True

            return False

    #向指定线程池提交任务，流程：
    #封装为 TaskWrapper；
    # 注册信号处理；
    # 启动任务；
    # 记录到 _task_registry。
    def submit(self, fn: Callable, pool_name: str = "qt_default", *args, **kwargs) -> Optional[str]:
        print("提交任务到指定线程池")
        with self._registry_lock:
            if pool_name not in self._pools:
                return None

            task_id = f"{time.time():.3f}:{pool_name}:{uuid.uuid4().hex[:8]}"
            pool_type, pool = self._pools[pool_name]
            task = TaskWrapper(task_id, fn, *args, **kwargs)

            task.signals.started.connect(lambda t_id: self._update_task_state(t_id, "RUNNING"), Qt.QueuedConnection)
            task.signals.succeeded.connect(lambda t_id, res: self._finalize_task(t_id, res, None), Qt.QueuedConnection)
            task.signals.failed.connect(lambda t_id, err: self._finalize_task(t_id, None, err), Qt.QueuedConnection)
            task.signals.cancelled.connect(lambda t_id: self._update_task_state(t_id, "CANCELLED"), Qt.QueuedConnection)

            if pool_type == "qt":
                pool.start(task)
                self._task_registry[task_id] = (pool_name, task)
            else:
                future = pool.submit(task.run)
                self._task_registry[task_id] = (pool_name, future)

            self._update_task_state(task_id, "PENDING")
            return task_id

    #关闭并移除指定线程池。
    def shutdown_pool(self, name: str, wait: bool = True) -> bool:
        print("关闭指定线程池")
        with self._registry_lock:
            if name not in self._pools:
                return False

            pool_type, pool = self._pools[name]
            if pool_type == "qt":
                pool.waitForDone()
            else:
                pool.shutdown(wait=wait)
            del self._pools[name]
            self.pool_closed.emit(name)
            return True

    #尝试取消任务，仅支持尚未执行的任务。
    def cancel_task(self, task_id: str) -> bool:
        print("强制取消任务")
        with self._registry_lock:
            if task_id not in self._task_registry:
                return False

            pool_name, task = self._task_registry[task_id]
            success = False

            if isinstance(task, TaskWrapper):
                success = task.cancel()
                if success:
                    self._update_task_state(task_id, "CANCELLED")
                    self._finalize_task(task_id, None, "用户取消")
            elif isinstance(task, Future):
                success = task.cancel()
                if success:
                    del self._task_registry[task_id]
            return success

    #记录任务状态变更（如：PENDING、RUNNING、CANCELLED）
    def _update_task_state(self, task_id: str, state: str) -> None:
        print("原子化状态更新")
        with self._registry_lock:
            if task_id in self._task_registry:
                print(f"Task {task_id} state changed to {state}")

    #任务结束后的清理操作，会打印成功或失败信息，并移除任务记录
    def _finalize_task(self, task_id: str, result: Any, error: str) -> None:
        print("任务最终处理")
        with self._registry_lock:
            if task_id in self._task_registry:
                if error:
                    print(f"Task Failed [{task_id}]: {error}")
                else:
                    print(f"Task Completed [{task_id}] Result: {result}")
                del self._task_registry[task_id]

    #返回活跃线程池的信息（名称 -> 类型）
    def get_active_pools(self) -> Dict[str, str]:
        print("获取当前活跃线程池信息")
        return {name: typ for name, (typ, _) in self._pools.items()}

    #返回正在运行的任务列表（任务ID -> 所属线程池名）
    def get_running_tasks(self) -> Dict[str, str]:
        print("获取运行中任务列表")
        return {t_id: pool_name for t_id, (pool_name, _) in self._task_registry.items()}
