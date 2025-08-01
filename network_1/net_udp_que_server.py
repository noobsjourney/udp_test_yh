import datetime
import json
import time
import threading
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from typing import Tuple, Dict, Callable
import queue
from network_1.udp import UDPNetworkManager
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
        # 添加线程锁保护共享字典
        self.dict_lock = threading.Lock()
        self.coreServiceBus = coreServiceBus
        self.signal_manager = self.coreServiceBus.get_service("signal") if self.coreServiceBus else None
        if self.signal_manager:
            self.signal_manager.register_regular_signal(self.module_name,"netsend",str,dict,int) 
            self.signal_manager.connect_regular_signal(self.module_name,"netsend",self._queue_send_data)
            self.signal_manager.register_regular_signal("node","received",dict,int)
        # 创建网络管理器
        self.net_mgr = UDPNetworkManager(bind_addr[0], bind_addr[1])
        self.net_mgr.dataReceived.connect(self._handle_received_data)
        # 端口状态缓存和信号绑定
        self.port_status = {}   #{ (ip, port): (is_online: bool}
        self.net_mgr.portCheckReceived.connect(self._on_port_check_received)
        self.running = True  # 线程标志位（检查目标端口/发送数据）
        # 节点ID-地址映射表 {node_id: (ip, port)}
        self.node_id_to_addr = {}  
        # 节点地址-最后活跃时间映射 { (ip, port): timestamp }
        self.source_port_last_active = {}  
        # 发送队列
        self.send_queue = queue.Queue()
        self.thread_que = self.coreServiceBus.get_service("thread") if self.coreServiceBus else None
        if self.thread_que:
            print(f"成功获取线程池服务: {type(self.thread_que)}")
            self.thread_que.submit(self._send_worker)
            self.thread_que.submit(self._source_port_scan_worker)
        else:
            print("错误：线程池服务 'thread' 未注册，请检查 CoreServiceBus")  
        
        
    @property
    def module_name(self):
        return "net_udp_que"
    
    def _queue_send_data(self, mode_name: str, data: dict, node_id: int):
        """将发送请求加入队列"""
        self.dest_addr = self.node_id_to_addr.get(node_id)
        if not self.dest_addr:
            print("警告: 未设置目标地址，忽略发送请求")
            return
        
        if not self.port_status.get(self.dest_addr, False):  # 直接读取缓存
            print(f"错误: 目标端口 {self.dest_addr} 离线或未检测，取消数据发送")
            return
        
        # 尝试将字典转换为字节流
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
        """发送工作线程（增加重试和超时退出机制）"""
        while self.running:
            try:
                try:
                    # 超时获取任务（非阻塞等待，避免永久阻塞）
                    task = self.send_queue.get(timeout=0.5)  # 设置 0.5 秒超时
                except queue.Empty:
                    # 队列为空且超时，检查线程池是否已关闭
                    if self.thread_que and "qt_default" not in self.thread_que.get_active_pools():
                        break  # 线程池已关闭，退出循环
                    continue  # 否则继续等待新任务   
                 
                # 最多重试3次
                max_retries = 3
                retry_delay = 1  # 秒
                try:
                    for attempt in range(max_retries):
                        if not self.running:
                            print(f"检测到退出标志，中断 {task['mode_name']} 重传")
                            break
                        try:
                            # 记录发送尝试日志
                            print(f"尝试发送 (第 {attempt+1}/{max_retries} 次): {task['mode_name']}, 目标: {task['dest_addr']}") 
                            # 调用发送方法
                            self.net_mgr.send_to(
                                task['mode_name'],
                                self.node_id,
                                task['data'],
                                task['dest_addr']
                            )   
                            # 如果发送成功，跳出重试循环
                            print("发送成功")
                            break    
                        except Exception as e:
                            # 发送失败，准备重试
                            print(f"发送尝试 {attempt+1} 失败: {e}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)  # 等待后重试 
                    # 如果所有重试都失败
                    if attempt == max_retries - 1:
                        print(f"所有 {max_retries} 次发送尝试均失败: {task['mode_name']}")
                finally:
                    self.send_queue.task_done()        
            except Exception as e:
                print(f"发送工作线程错误: {e}")
        print("发送工作线程已退出")
        
    def _source_port_scan_worker(self):
        """扫描客户端离线状态（每30秒检查一次，超过60秒无活动标记为离线）"""
        OFFLINE_THRESHOLD = 60  # 离线阈值（秒）
        SCAN_INTERVAL = 30      # 扫描间隔（秒）
        while self.running:
            try:
                current_time = time.time()
                offline_addrs = []
                # 遍历所有客户端地址，检查最后活跃时间
                for addr, last_active in self.source_port_last_active.items():
                    if current_time - last_active > OFFLINE_THRESHOLD:
                        offline_addrs.append(addr)
                        self.port_status[addr] = False  # 标记为离线
                # 输出离线日志
                if offline_addrs:
                    print(f"检测到离线客户端地址: {offline_addrs}")
                # 等待扫描间隔（拆分休眠，便于快速退出）
                for _ in range(SCAN_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
            except Exception as e:
                print(f"客户端离线扫描线程错误: {e}")
        print("客户端离线扫描线程已退出")
        
    @pyqtSlot(str, int, bytes, tuple)
    def _handle_received_data(self, mode_name: str, node_id: int, data: bytes, source_addr: Tuple[str, int]):

        """处理接收到的数据"""
        # 记录节点ID与客户端地址的映射关系（覆盖旧记录，确保地址实时更新）
        with self.dict_lock:
            self.node_id_to_addr[node_id] = source_addr
        print(f"已更新节点ID[{node_id}]的地址: {source_addr}")
        
        # 转发到对应模块的信号
        # 增加一步操作 将接受的到的字节流再转换为字典
        try:
            # 将接收到的字节流转换为字典
            data_dict = json.loads(data.decode('utf-8'))
            # 转发到对应模块的信号
            if self.signal_manager:
                self.signal_manager.emit_regular_signal(mode_name,"received",data_dict,node_id)
        except Exception as e:
            print(f"字节流转换为字典失败: {e}")

    @pyqtSlot(tuple,bool)
    def _on_port_check_received(self, addr: Tuple[str, int], online: bool):
        """确认接收到端口检测包 端口状态设置为在线"""
        # 记录状态与活跃时间
        with self.dict_lock:
            self.port_status[addr] = online
            self.source_port_last_active[addr] = time.time()
        # print(f"[{datetime.datetime.now()}] 端口状态更新: {addr} {'在线' if online else '离线'}")
            
    def _emit_netsend(self, mode_name: str, data: dict, node_id : int):
        """触发发送信号 执行槽函数将数据加入发送队列"""
        if self.signal_manager:
            getsingal = self.signal_manager.get_regular_signal(self.module_name,"netsend")
            getsingal.emit(mode_name,data,node_id)

    def set_destination(self, dest_addr: Tuple[str, int]):
        """设置目标地址"""
        self.dest_addr = dest_addr
        
    def get_local_address(self) -> Tuple[str, int]:
        """获取本地绑定地址"""
        return self.net_mgr.get_local_addr()
    
    
    def close(self): 
        """关闭资源"""
        self.running = False # 设置线程退出标志
        if self.thread_que and "qt_default" in self.thread_que.get_active_pools():
            print("等待端口检测线程退出...")
            time.sleep(2)  # 等待线程从休眠中唤醒并检查 self.running
        if self.thread_que:
            # 关闭目标线程池（qt_default）
            self.thread_que.shutdown_pool("qt_default", wait=False)  # 非阻塞关闭
            # 取消活跃任务
            running_tasks = self.thread_que.get_running_tasks()  # 返回 {task_id: pool_name}
            for task_id in running_tasks.keys():
                self.thread_que.cancel_task(task_id)  # 取消单个任务
            # 清空发送队列
            while not self.send_queue.empty():
                task = self.send_queue.get()
                self.send_queue.task_done()
        # 等待队列任务完成
        self.send_queue.join()
        self.net_mgr.close()
        print("NetUDPQue 资源已完全释放")

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


    def handle_received_data(data_dict,node_id):
        print(f"服务器接收到节点ID[{node_id}]的数据: {data_dict}")
        print(data_dict)
        # 服务器返回数据给客户端
        server._emit_netsend("node", server_response_dict,node_id)
        server.close()  # 释放客户端资源（线程/队列/网络连接）
        app.quit()      # 退出应用


    app = QCoreApplication(sys.argv)

    # 初始化服务器
    core_service_bus = CoreServiceBus()
    server = NetUDPQue(bind_addr=('0.0.0.0', 60000), node_id=2001,coreServiceBus=core_service_bus)

    # 连接 received 信号到处理函数
    server.signal_manager.connect_regular_signal("node", "received", handle_received_data)

    sys.exit(app.exec_())
    
    
    
    
    
    # def _save_file(self, file_bytes: bytes, filename: str = None):
    # """保存接收到的文件"""   
    # timestamp = int(time.time())
    # # 从文件名提取扩展名
    # if filename and '.' in filename:
    #     ext = filename.split('.')[-1].lower()
    #     filename_with_ext = f"received_{timestamp}.{ext}"
    # # 保存文件
    # try:
    #     with open(filename_with_ext, 'wb') as f:
    #         f.write(file_bytes)
    #     print(f"文件保存成功: {filename_with_ext} (大小: {len(file_bytes)} bytes)")
    # except Exception as e:
    #     print(f"文件保存失败: {e}")
    


    # @pyqtSlot(str, int, bytes, tuple)
    # def _handle_received_data(self, mode_name: str, node_id: int, data: bytes, source_addr: Tuple[str, int]):

    #     """处理接收到的数据"""
    #     # 更新源地址为最新通信的节点
    #     self.dest_addr = source_addr
    #     try:
    #         # 解析文件名（格式：[4字节文件名长度][文件名][文件内容]）
    #         if len(data) < 4:
    #             print("错误：文件数据不完整，无法解析文件名长度")
    #             return
            
    #         # 步骤1：提取4字节文件名长度（无符号整数，大端序）
    #         filename_len = int.from_bytes(data[:4], byteorder='big')         
    #         # 步骤2：提取文件名字节（长度为filename_len）
    #         filename_bytes = data[4 : 4 + filename_len]
    #         filename = filename_bytes.decode('utf-8')  # 解码为字符串
    #         # 步骤3：提取文件内容字节（剩余部分）
    #         file_bytes = data[4 + filename_len :]
    #         # 保存文件（传入解析出的文件名）
    #         self._save_file(file_bytes, filename)
    #     except Exception as e:
    #         print(f"字节流转换为字典失败: {e}")