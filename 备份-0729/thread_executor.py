from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, Qt, QThreadPool, QTimer
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
class TaskResult:
    """标准化任务执行结果容器"""
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    traceback: Optional[str] = None


class TaskSignals(QObject):
    """任务生命周期信号集合"""
    started = pyqtSignal(str)  # 任务ID
    succeeded = pyqtSignal(str, str)  # 任务ID, 结果
    failed = pyqtSignal(str, str)  # 任务ID, 错误信息
    cancelled = pyqtSignal(str)  # 任务ID
    finished = pyqtSignal(str)  # 任务ID


class TaskWrapper(QRunnable):
    """任务执行容器"""

    def __init__(self, task_id: str, fn: Callable, *args, **kwargs):
        print("任务执行容器初始化")
        super().__init__()
        self.task_id = task_id
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()
        self._state_lock = threading.Lock()
        self._state = "PENDING"  # PENDING | RUNNING | CANCELLED

    def run(self) -> None:
        """原子化任务执行流程"""
        print("原子化任务执行流程")
        with self._state_lock:
            if self._state == "CANCELLED":
                self.signals.cancelled.emit(self.task_id)
                return
            self._state = "RUNNING"

        self.signals.started.emit(self.task_id)
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.succeeded.emit(self.task_id, result)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            tb = traceback.format_exc()
            self.signals.failed.emit(self.task_id, f"{error_msg}\nTraceback:\n{tb}")
        finally:
            self.signals.finished.emit(self.task_id)

    def cancel(self) -> bool:
        """原子化任务取消操作"""
        print("原子化任务取消操作")
        with self._state_lock:
            if self._state == "PENDING":
                self._state = "CANCELLED"
                return True
            return False

class DaemonTask:
    """守护任务包装器，用于管理周期性执行的任务"""
    def __init__(self, task_id: str, fn: Callable, interval: float, *args, **kwargs):
        self.task_id = task_id
        self.fn = fn
        self.interval = interval
        self.args = args
        self.kwargs = kwargs
        self.stop_event = threading.Event()
        self.last_execution = time.time()
        
    def run(self):
        """守护任务执行循环"""
        while not self.stop_event.is_set():
            try:
                # 执行用户函数
                result = self.fn(*self.args, **self.kwargs)
                self.last_execution = time.time()
                # 可以添加结果处理逻辑
            except Exception as e:
                error_msg = f"Daemon task error: {str(e)}"
                traceback.print_exc()
                # 可以添加错误处理逻辑
            
            # 等待直到下一个执行周期或停止事件
            self.stop_event.wait(self.interval)
    
    def stop(self):
        """停止守护任务"""
        self.stop_event.set()

class ThreadExecutor(BaseModule):
    """独立线程池管理系统

    特性：
    - 支持三种线程池模式：QT/IO/COMPUTE
    - 全生命周期任务追踪
    - 增强的取消和超时机制
    - 线程安全的注册表操作
    """
    # 模块级信号
    pool_created = pyqtSignal(str, str)  # (池名称, 池类型)
    pool_closed = pyqtSignal(str)  # 池名称

    def __init__(self, parent=None):
        print("独立线程池管理系统初始化")
        super().__init__(parent)
        # 线程池配置 {name: (type, instance)}
        self._pools: Dict[str, Tuple[str, Union[QThreadPool, ThreadPoolExecutor]]] = {}
        # 任务注册表 {task_id: (pool_name, task)}
        self._task_registry: Dict[str, Tuple[str, Union[TaskWrapper, Future, DaemonTask]]] = {}
        self._registry_lock = threading.RLock()
        self._daemon_tasks: Dict[str, DaemonTask] = {}  # 守护任务注册表
        self._daemon_lock = threading.RLock()  # 守护任务专用锁

        # 重构 ThreadExecutor 的初始化流程，确保信号发射发生在对象完全初始化之后
        self._init_default_pools()  # 使用单次定时器延迟初始化
        # self._init_default_pools()

    @property
    def module_name(self) -> str:
        return "thread"
    def _init_default_pools(self):
        """初始化默认线程池"""
        print("初始化默认线程池")
        self.create_pool("qt_default", "qt", max_threads=QThreadPool.globalInstance().maxThreadCount())
        self.create_pool("io_default", "standard", max_workers=8)#串行执行，操作系统调度
        self.create_pool("compute_default", "standard", max_workers=os.cpu_count())
        self.create_pool("daemon_default", "daemon", max_workers=os.cpu_count())

    def create_pool(self, name: str, pool_type: str, **kwargs) -> bool:
        """创建新线程池

        :param pool_type: qt | standard
        :param kwargs:
            - qt: max_threads
            - standard: max_workers, etc
        """
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

    def submit(
            self,
            fn: Callable,
            pool_name: str = "qt_default",
            task_id: Optional[str] = None,
            *args, **kwargs
    ) -> Optional[str]:
        """提交任务到指定线程池

        返回格式：timestamp:pool_name:uuid
        示例：'1689123456.789:qt_default:abcd-1234'
        """
        print("提交任务到指定线程池")
        print("pool_name:",pool_name)
        with self._registry_lock:
            print("pool_name:",pool_name)
            print("self._pools:",self._pools)
            if pool_name not in self._pools:
                return None
            # 生成可读任务ID
            task_id = task_id or f"{time.time():.3f}:{pool_name}:{uuid.uuid4().hex[:8]}"
            pool_type, pool = self._pools[pool_name]
            task = TaskWrapper(task_id, fn, *args, **kwargs)

            # 连接任务信号
            task.signals.started.connect(
                lambda t_id: self._update_task_state(t_id, "RUNNING"),
                Qt.QueuedConnection
            )
            task.signals.succeeded.connect(
                lambda t_id, res: self._finalize_task(t_id, res, None),
                Qt.QueuedConnection
            )
            task.signals.failed.connect(
                lambda t_id, err: self._finalize_task(t_id, None, err),
                Qt.QueuedConnection
            )
            task.signals.cancelled.connect(
                lambda t_id: self._update_task_state(t_id, "CANCELLED"),
                Qt.QueuedConnection
            )

            # 提交到线程池
            if pool_type == "qt":
                pool.start(task)
            else:
                future = pool.submit(task.run)
                self._task_registry[task_id] = (pool_name, future)

            self._task_registry[task_id] = (pool_name, task)
            self._update_task_state(task_id, "PENDING")
            return task_id

    def shutdown_pool(self, name: str, wait: bool = True) -> bool:
        """关闭指定线程池"""
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

    def cancel_task(self, task_id: str) -> bool:
        """强制取消任务（包括运行中的任务）"""
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
                    self._finalize_task(task_id, None, "用户取消")  # 强制清理
            elif isinstance(task, Future):
                success = task.cancel()
                if success:
                    del self._task_registry[task_id]  # 立即移除
            return success

    def _update_task_state(self, task_id: str, state: str) -> None:
        """原子化状态更新"""
        print("原子化状态更新")
        with self._registry_lock:
            if task_id in self._task_registry:
                print(f"Task {task_id} state changed to {state}")

    def _finalize_task(self, task_id: str, result: Any, error: str) -> None:
        """任务最终处理"""
        print("任务最终处理")
        with self._registry_lock:
            if task_id in self._task_registry:
                # 记录执行结果
                if error:
                    print(f"Task Failed [{task_id}]: {error}")
                else:
                    print(f"Task Completed [{task_id}] Result: {result}")

                # 清理注册表
                del self._task_registry[task_id]

    def get_active_pools(self) -> Dict[str, str]:
        """获取当前活跃线程池信息"""
        print("获取当前活跃线程池信息")
        return {name: typ for name, (typ, _) in self._pools.items()}

    def get_running_tasks(self) -> Dict[str, str]:
        """获取运行中任务列表"""
        print("获取运行中任务列表")
        return {
            t_id: pool_name
            for t_id, (pool_name, _) in self._task_registry.items()
        }
    def submit_daemon(
        self,
        fn: Callable,
        interval: float,
        pool_name: str = "daemon_default",
        task_id: str = None,
        *args, **kwargs
    ) -> Optional[str]:
        """提交周期性执行的守护任务
        
        :param fn: 要执行的任务函数
        :param interval: 执行间隔(秒)
        :param pool_name: 使用的线程池名称
        :param task_id: 可选的任务ID
        :return: 任务ID或None(失败)
        """
        with self._daemon_lock:
            # 确保守护线程池存在
            if not self._ensure_daemon_pool_exists(pool_name):
                return None
            
            # 生成唯一任务ID
            task_id = task_id or f"daemon_{time.time():.3f}:{uuid.uuid4().hex[:8]}"
            
            # 创建守护任务实例
            daemon_task = DaemonTask(task_id, fn, interval, *args, **kwargs)
            
            # 提交到线程池
            _, pool = self._pools[pool_name]
            future = pool.submit(daemon_task.run)
            
            # 注册守护任务
            self._daemon_tasks[task_id] = {
                "task": daemon_task,
                "future": future,
                "pool": pool_name
            }
            
            return task_id
    
    def _ensure_daemon_pool_exists(self, pool_name: str) -> bool:
        """确保守护线程池存在，不存在则创建"""
        if pool_name not in self._pools:
            # 创建专用于守护任务的线程池
            # 设置较大的max_workers以支持多个守护任务
            return self.create_pool(pool_name, "standard", max_workers=20)
        return True
    
    def stop_daemon_task(self, task_id: str, wait: bool = True) -> bool:
        """停止守护任务
        
        :param task_id: 要停止的任务ID
        :param wait: 是否等待任务完成
        :return: 是否成功停止
        """
        with self._daemon_lock:
            if task_id not in self._daemon_tasks:
                return False
            
            task_info = self._daemon_tasks[task_id]
            task_info["task"].stop()  # 设置停止标志
            
            if wait:
                try:
                    # 等待任务完成，最多等待2个间隔周期
                    task_info["future"].result(timeout=task_info["task"].interval * 2)
                except:
                    pass
            
            # 从注册表中移除
            del self._daemon_tasks[task_id]
            return True
    
    def get_daemon_tasks(self) -> Dict[str, Dict]:
        """获取所有守护任务的状态信息"""
        with self._daemon_lock:
            return {
                task_id: {
                    "interval": task_info["task"].interval,
                    "last_execution": task_info["task"].last_execution,
                    "pool": task_info["pool"],
                    "running": not task_info["task"].stop_event.is_set()
                }
                for task_id, task_info in self._daemon_tasks.items()
            }
    
    def shutdown_all_daemons(self):
        """停止所有守护任务"""
        with self._daemon_lock:
            for task_id in list(self._daemon_tasks.keys()):
                self.stop_daemon_task(task_id, wait=True)
    
    # 修改原有shutdown_pool方法，添加守护任务清理
    def shutdown_pool(self, name: str, wait: bool = True) -> bool:
        """关闭指定线程池（重写以清理守护任务）"""
        # 先停止使用该线程池的所有守护任务
        with self._daemon_lock:
            for task_id, task_info in list(self._daemon_tasks.items()):
                if task_info["pool"] == name:
                    self.stop_daemon_task(task_id, wait=wait)
        
        # 调用原有关闭逻辑
        return super().shutdown_pool(name, wait)