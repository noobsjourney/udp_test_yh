import json
import os
import time
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
        self.coreServiceBus = coreServiceBus
        self.signal_manager = self.coreServiceBus.get_service("signal") if self.coreServiceBus else None
        if self.signal_manager:
            self.signal_manager.register_regular_signal(self.module_name,"netsend",str,dict) 
            self.signal_manager.connect_regular_signal(self.module_name,"netsend",self._queue_send_data)
            self.signal_manager.register_regular_signal("node","received",dict)
            self.signal_manager.register_regular_signal(self.module_name,"portStatusChanged",bool)
        # 创建网络管理器
        self.net_mgr = UDPNetworkManager(bind_addr[0], bind_addr[1])
        self.net_mgr.dataReceived.connect(self._handle_received_data)
        # 端口状态缓存和信号绑定
        self.port_status = {}   #{ (ip, port): (is_online: bool}
        self.net_mgr.portStatusChanged.connect(self._on_port_status_changed)  # 连接端口状态更新信号
        self.PORT_CHECK_INTERVAL = 60  # 检测间隔  1min or 2min
        self.running = True  # 线程标志位（检查目标端口/发送数据）
        # 发送队列
        self.send_queue = queue.Queue()
        self.thread_que = self.coreServiceBus.get_service("thread") if self.coreServiceBus else None
        if self.thread_que:
            print(f"成功获取线程池服务: {type(self.thread_que)}")
            self.thread_que.submit(self._send_worker)
            self.thread_que.submit(self._port_check_worker)
        else:
            print("错误：线程池服务 'thread' 未注册，请检查 CoreServiceBus")  
        
        
    @property
    def module_name(self):
        return "net_udp_que"
            
    def _queue_send_data(self, mode_name: str, data: dict):
        """将发送请求加入队列"""
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
                
    def _port_check_worker(self):
        """
        守护线程：定期检测目标端口状态
        """
        while self.running:
            try:
                # 1. 检查线程池是否已关闭
                if self.thread_que and "qt_default" not in self.thread_que.get_active_pools():
                    break
                
                # 2. 仅当目标地址已设置时执行检测
                if self.dest_addr:
                    print(f"\n=== 定期端口状态检测 (间隔 {self.PORT_CHECK_INTERVAL}秒) ===")
                    # {{ 保持调用：仅发送检测包，状态通过信号异步更新 }}
                    self._check_port_online()
                    status = "在线" if self.port_status.get(self.dest_addr, False) else "离线/未响应"
                    print(f"当前目标端口 {self.dest_addr} 状态: {status}")  # 直接读取缓存
                
                # 3. 拆分休眠为1秒间隔，频繁检查self.running
                for _ in range(self.PORT_CHECK_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
            except Exception as e:
                print(f"定期端口检测线程错误: {e}")
                # 出错时短暂等待后重试，避免无限循环报错
                time.sleep(5)
        print("定期端口检测线程已退出")
    
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
            
    @pyqtSlot(tuple,bool)
    def _on_port_status_changed(self, addr: Tuple[str, int], online: bool):
        """更新目标端口在线状态（由UDPNetworkManager信号触发）"""
        # 记录状态
        self.port_status[addr] = online
        print(f"端口状态更新: {addr} {'在线' if online else '离线'}")  
        # 将目标端口的在线状态通过信号传输出去
        if self.signal_manager:
            self.signal_manager.emit_regular_signal(self.module_name,"portStatusChanged",online)
        
    def _emit_netsend(self, mode_name: str, data: dict):
        """触发发送信号 执行槽函数将数据加入发送队列"""
        if self.signal_manager:
            getsingal = self.signal_manager.get_regular_signal(self.module_name,"netsend")
            getsingal.emit(mode_name,data)

    def set_destination(self, dest_addr: Tuple[str, int]):
        """设置目标地址并触发初始端口检测"""
        self.dest_addr = dest_addr
        if self.dest_addr:
            self._check_port_online()  
            print(f"目标地址已设置，触发初始端口检测: {dest_addr}")
    
    def get_local_address(self) -> Tuple[str, int]:
        """获取本地绑定地址"""
        return self.net_mgr.get_local_addr()
    
    def _check_port_online(self):
        """
        端口在线检测（仅发送检测包，状态变更通过信号异步更新缓存）
        """
        # 防止意外触发
        if not self.dest_addr:
            print("警告: 目标地址未设置，跳过端口检测")
            return
        # 发送检测包
        print(f"发送端口检测包: {self.dest_addr}")
        self.net_mgr.check_port(dest_addr = self.dest_addr,node_id=self.node_id)  # 调用网络管理器发送检测包
    
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
    from base_module import BaseModule
    
    print("客户端测试开始(传输字典/.jpg/.py/.zip)")

    # 定义 nodeInfo_dict 测试传输字典
    nodeInfo_dict = {
        1: { 
            "message" :"test form client"
        }
    }

    def handle_received_data(data_dict):
        """接收服务器响应后释放资源"""
        print(f"\n收到服务器响应: {data_dict}")
        print("开始手动释放资源...")
        client.close()  # 释放客户端资源（线程/队列/网络连接）
        app.quit()      # 退出应用

    # 初始化客户端和相关配置
    app = QCoreApplication(sys.argv)
    core_service_bus = CoreServiceBus()
    client = NetUDPQue(bind_addr=('0.0.0.0', 8888), node_id=1001,coreServiceBus=core_service_bus)
    client.set_destination(('192.168.230.128', 60000))  # 设置服务器地址
    # 连接 received 信号到处理函数
    client.signal_manager.connect_regular_signal("node", "received", handle_received_data)

    
    # 发送数据(可以传输 字典/.jpg/.py/.zip)
    client._emit_netsend("node", nodeInfo_dict)
    # client.send_file("test.jpg")
    # client.send_file("test.py")
    # client.send_file("test.zip")

    sys.exit(app.exec_())
    
    
    
    
    # def send_file(self, file_path: str):
    # """统一发送任意文件（支持图片、.py、.zip等）"""     
    # try:
    #     if not self.dest_addr:
    #         print("警告: 未设置目标地址，忽略发送请求")
    #         return
        
    #     if not self.port_status.get(self.dest_addr, False):  # 直接读取缓存
    #         print(f"错误: 目标端口 {self.dest_addr} 离线或未检测，取消文件发送")
    #         return
        
    #     # 读取文件字节流
    #     with open(file_path, 'rb') as f:
    #         file_bytes = f.read()
        
    #     # 提取文件名（用于服务器识别类型）
    #     filename = os.path.basename(file_path)  
        
    #     # 构造发送数据：前缀+文件名+文件字节流（前缀为文件名长度，4字节无符号整数）
    #     filename_bytes = filename.encode('utf-8')
    #     filename_len = len(filename_bytes).to_bytes(4, byteorder='big')  # 4字节存储文件名长度
    #     data_to_send = filename_len + filename_bytes + file_bytes  # 组合数据
        
    #     # 加入发送队列
    #     self.send_queue.put({
    #         'mode_name': "node",  # 统一标识文件传输
    #         'data': data_to_send,
    #         'dest_addr': self.dest_addr
    #     })
    #     print(f"文件 '{filename}' 已加入发送队列 (大小: {len(file_bytes)} bytes)")
    # except Exception as e:
    #     print(f"文件发送失败: {e}")