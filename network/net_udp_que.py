from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from typing import Tuple, Dict, Callable
import queue
from udp import UDPNetworkManager
from  base_module import BaseModule

class NetUDPQue(BaseModule):
    """
    UDP信号路由器
    使用UDPNetworkManager进行数据传输，提供基于模块名的信号路由功能
    
    特性:
    1. 提供netsend信号触发发送操作
    2. 自动管理发送队列，按序发送数据
    3. 按模块名(modeName)转发接收到的数据
    """
    
    # 发送信号: (modeName, data)
    #netsend = pyqtSignal(str, bytes)
    
    def __init__(self, bind_addr: Tuple[str, int] = ('0.0.0.0', 0), node_id: int = 1000,coreServiceBus):
        """
        初始化UDP信号路由器
        
        Args:
            bind_addr: 本地绑定地址 (host, port)
            node_id: 本节点ID
            parent: 父对象
        """
        super().__init__()
        
        self.node_id = node_id
        self.dest_addr = None  # 目标地址，需要在发送前设置
        self.coreServiceBus = coreServiceBus
        self.signal_manager = self.coreServiceBus.get_service("signal")
        self.signal_manager.register_regular_signal(self.module_name,"netsend",str,dict)
        self.signal_manager.connect_regular_signal(self.module_name,"netsend",self._queue_send_data)
        # 创建网络管理器
        self.net_mgr = UDPNetworkManager(bind_addr[0], bind_addr[1])
        self.net_mgr.dataReceived.connect(self._handle_received_data)
        # 发送队列
        self.send_queue = queue.Queue()
        self.thread_que=self.coreServiceBus.get_service("thread")
        self.thread_que.submit(self._send_worker)

        
        # 模块信号映射表
        
        
    
    
    @property
    def model_name(self):
        return "net_udp_que"

    def _queue_send_data(self, mode_name: str, data: bytes):
        """将发送请求加入队列"""
        if not self.dest_addr:
            print("警告: 未设置目标地址，忽略发送请求")
            return
            
        self.send_queue.put({
            'mode_name': mode_name,
            'data': data,
            'dest_addr': self.dest_addr
        })
    
    def _send_worker(self):
        """发送工作线程"""
        while True:
            try:
                task = self.send_queue.get()
                self.net_mgr.send_to(
                    task['mode_name'],
                    self.node_id,
                    task['data'],
                    task['dest_addr']
                )
                self.send_queue.task_done()
            except Exception as e:
                print(f"发送错误: {e}")
    
    @pyqtSlot(str, int, bytes, tuple)
    def _handle_received_data(self, modename: str, node_id: int, data: bytes, source_addr: Tuple[str, int]):
        """处理接收到的数据"""
        # 更新源地址为最新通信的节点
        self.dest_addr = source_addr
        
        # 转发到对应模块的信号
       
    
        self.signal_manager.emit_regular_signal(modename,"reversed", data)

    
    def set_destination(self, dest_addr: Tuple[str, int]):
        """设置目标地址"""
        self.dest_addr = dest_addr
    
    def get_local_address(self) -> Tuple[str, int]:
        """获取本地绑定地址"""
        return self.net_mgr.get_local_addr()
    
    def close(self):
        """关闭资源"""
        self.net_mgr.close()
        self.send_thread.join(timeout=1.0)
