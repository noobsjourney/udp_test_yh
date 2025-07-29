import json
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from typing import Tuple, Dict, Callable
import queue
from network.udp import UDPNetworkManager
from base_module import BaseModule

class NetUDPQue(BaseModule):
    """
    UDP信号路由器
    使用UDPNetworkManager进行数据传输，提供基于模块名的信号路由功能
    
    特性:
    1. 提供netsend信号触发发送操作
    2. 自动管理发送队列，按序发送数据
    3. 按模块名(modeName)转发接收到的数据 通过模块信号映射
    """


    """ 
    nodeInfo_dict 字典结构（发送、接收信息）
    {
        命令类型：命令内容
        
        1：{
        发送节点所有信息
        node_name:
        node_id:
        nodeGenerateId:
        }
        2：{
            修改节点名称
            node_name:
        }
        3：{
            节点ID冲突
            node_id:
        }
        4：{
            服务器回传节点信息准确无误
            0：信息准确无误
            1：nodename冲突
            2：nodeid冲突
        }
        5：{
            服务器回传节点名称修改成功
            0：修改成功
            1：nodename冲突
        }
        6：{
            服务器回传节点名称修改失败
            0：修改失败
            1：nodename冲突
        }
    }
    """
    
    
    def __init__(self, bind_addr: Tuple[str, int] = ('0.0.0.0', 0), node_id: int = 1000, coreServiceBus=None):
        """
        初始化UDP信号路由器
        
        Args:
            bind_addr: 本地绑定地址 (host, port)
            node_id: 本节点的ID
            coreServiceBus: 核心服务总线，用于获取信号和线程服务
        """
        super().__init__()
        
        self.node_id = node_id
        self.dest_addr = None  # 目标地址，需要在发送前设置
        self.coreServiceBus = coreServiceBus
        self.signal_manager = self.coreServiceBus.get_service("signal") if self.coreServiceBus else None
        if self.signal_manager:
            self.signal_manager.register_regular_signal(self.module_name,"netsend",str,dict) 
            self.signal_manager.connect_regular_signal(self.module_name,"netsend",self._queue_send_data)
            self.signal_manager.register_regular_signal(self.module_name,"received",dict)
        # 创建网络管理器
        self.net_mgr = UDPNetworkManager(bind_addr[0], bind_addr[1])
        self.net_mgr.dataReceived.connect(self._handle_received_data)
        # 发送队列
        self.send_queue = queue.Queue()
        self.thread_que = self.coreServiceBus.get_service("thread") if self.coreServiceBus else None
        if self.thread_que:
            self.thread_que.submit(self._send_worker)
        
        
    @property
    def module_name(self):
        return "net_udp_que"

    def _queue_send_data(self, mode_name: str, data: dict):
        """将发送请求加入队列"""
        if not self.dest_addr:
            print("警告: 未设置目标地址，忽略发送请求")
            return
        # 增加一步操作 将字典转换为字节流
        try:
            data_bytes = json.dumps(data).encode('utf-8')
            self.send_queue.put({
                'mode_name': mode_name,
                'data': data_bytes,
                'dest_addr': self.dest_addr
            })
        except Exception as e:
            print(f"字典转换为字节流失败: {e}")
 
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
    def _handle_received_data(self, mode_name: str, node_id: int, data: bytes, source_addr: Tuple[str, int]):

        """处理接收到的数据"""
        # 更新源地址为最新通信的节点
        self.dest_addr = source_addr
        
        # 转发到对应模块的信号
        # 增加一步操作 将接受的到的字节流再转换为字典
        try:
            # 将接收到的字节流转换为字典
            data_dict = json.loads(data.decode('utf-8'))
            # 转发到对应模块的信号
            if self.signal_manager:
                self.signal_manager.emit_regular_signal(mode_name,"received",data_dict)
        except Exception as e:
            print(f"字节流转换为字典失败: {e}")

    def _emit_netsend(self, mode_name: str, data: dict):
        """触发发送信号 执行槽函数将数据加入发送队列"""
        if self.signal_manager:
            getsingal = self.signal_manager.get_regular_signal(self.module_name,"netsend")
            getsingal.emit(mode_name,data)

    def set_destination(self, dest_addr: Tuple[str, int]):
        """设置目标地址"""
        self.dest_addr = dest_addr
    
    def get_local_address(self) -> Tuple[str, int]:
        """获取本地绑定地址"""
        return self.net_mgr.get_local_addr()
    
    def close(self): 
        """关闭资源"""
        self.net_mgr.close()
        if self.thread_que:
            # 假设 thread_que 有停止任务的方法，这里简单示意
            pass
        # 等待队列任务完成
        self.send_queue.join()


if __name__ == "__main__":
    import sys
    from PyQt5.QtCore import QCoreApplication
    from service_bus import CoreServiceBus
    
    print("服务器端测试开始")

    # 定义服务器返回的 nodeInfo_dict
    server_response_dict = {
        4: {
            0: "信息准确无误",
            "detailed_check": {
                "node_name": {
                    "status": "valid",
                    "message": "Node name is unique."
                },
                "node_id": {
                    "status": "valid",
                    "message": "Node ID is unique."
                }
            }
        },
        5: {
            "update_status": "success",
            "updated_info": {
                "node_name": "updated_client_node",
                "update_time": "2025-07-23 18:00:00"
            }
        }
    }


    def handle_received_data(data_dict):
        print("服务器接收到客户端的数据:")
        print(data_dict)
        # 服务器返回数据给客户端
        server._emit_netsend("net_udp_que", server_response_dict)


    app = QCoreApplication(sys.argv)

    # 初始化服务器
    core_service_bus = CoreServiceBus()
    server = NetUDPQue(bind_addr=('0.0.0.0', 60000), node_id=2001,coreServiceBus=core_service_bus)

    # 连接 received 信号到处理函数
    server.signal_manager.connect_regular_signal("net_udp_que", "received", handle_received_data)

    sys.exit(app.exec_())