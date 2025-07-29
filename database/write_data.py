from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from queue import Queue, Empty
import logging
from base_module import BaseModule
from datetime import datetime
from sqlalchemy import Column
import time
class WriteData(BaseModule):
    def __init__(self, coreServiceBus: 'CoreServiceBus'):
        super().__init__()
        self.coreServiceBus = coreServiceBus
        self.databaseManager = coreServiceBus.get_service('database')
        
        # 初始化任务队列
        self.task_queue = Queue()
        self._running = True  # 控制线程运行的标志
        
        # 获取服务
        self.signal_manager = coreServiceBus.get_service("signal")
        self.thread_executor = coreServiceBus.get_service("thread")
        
        # 注册信号
        self._register_signals()
        
        # 启动处理线程
        self._start_processing_thread()
        
        # 权限管理
        self._module_writer_per = {}
    
    @property
    def module_name(self) -> str:
        return "write_data"
    
    def _register_signals(self):
        """注册并连接信号"""
        # 注册"data_received"信号
        self.signal_manager.register_regular_signal(
            self.module_name, "data_received", str, object
        )
        
        # 连接信号到槽函数
        self.signal_manager.connect_regular_signal(
            self.module_name, "data_received", 
            self.on_data_received
        )
    
    def _start_processing_thread(self):
        """启动数据处理线程"""
        # 提交任务到线程执行器
        self.thread_task_id = self.thread_executor.submit(
            self._process_queue,
            pool_name="io_default"  # 使用IO线程池
        )
    
    def grant_write_permission(self, module_name: str, table_name: str):
        """授予指定模块写入特定表的权限"""
        self._module_writer_per[module_name] = table_name
    
    def _validate_permission(self, module_name, data):
        """验证模块是否有权限写入数据"""
        allowed_table = self._module_writer_per.get(module_name)
        if not allowed_table:
            return False
        
        # 获取数据对应的表名
        if isinstance(data, list) and data:
            table_name = data[0].__tablename__
        elif hasattr(data, '__tablename__'):
            table_name = data.__tablename__
        else:
            return False
        
        return allowed_table == table_name
    
    @pyqtSlot(str, object)
    def on_data_received(self, module_name, data):
        """处理接收到的数据信号"""
        if not self._validate_permission(module_name, data):
            logging.warning(f"模块 {module_name} 无权限写入数据")
            return
        
        # 将数据放入任务队列
        self.task_queue.put((module_name, data))
    
    def _process_queue(self):
        """处理任务队列中的写入任务"""
        # 在线程中初始化数据库连接
        self.sqlite_write = self.databaseManager.get_instance('sqlite_write')
        
        while self._running:
            try:
                # 从队列中获取任务（带超时）
                task = self.task_queue.get(timeout=0.5)
                module_name, data = task
                
                # 再次验证权限（确保状态未变）
                if not self._validate_permission(module_name, data):
                    logging.warning(f"处理时权限验证失败: {module_name}")
                    continue
                
                # 根据数据类型执行写入操作
                if isinstance(data, list):
                    self._write_bulk(data)
                else:
                    self._write_single(data)
                
            except Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                logging.error(f"写入失败: {str(e)}")
    
    def _write_single(self, instance):
        """写入单个数据实例"""
        self.sqlite_write.fifo_add_in_transaction(instance)
    
    def _write_bulk(self, instances):
        """批量写入数据"""
        self.sqlite_write.bulk_insert(instances)
    
    def shutdown(self):
        """安全停止模块"""
        self._running = False
        
        # 等待线程完成
        time.sleep(0.5) 