import time
from typing import Any

class ExamplePlugin:
    """示例插件演示基本功能"""
    
    def __init__(self, service_proxy: Any):
        """
        初始化插件
        :param service_proxy: 服务代理对象，提供对核心服务的访问
        """
        self.service_proxy = service_proxy
        self.running = False
        
        # 获取所需服务
        self.thread_executor = service_proxy.get_service("thread")
        self.signal_manager = service_proxy.get_service("signal")
        
        # 注册信号
        self._register_signals()
    
    def _register_signals(self):
        """注册插件信号"""
        self.signal_manager.register_regular_signal(
            "example_plugin", "data_processed", str
        )
    
    def start(self):
        """启动插件主逻辑"""
        self.running = True
        print("示例插件启动")
        
        # 在独立线程中运行处理循环
        self.thread_executor.submit(
            self._process_loop,
            pool_name="plugin_workers"
        )
    
    def _process_loop(self):
        """数据处理循环"""
        while self.running:
            try:
                # 模拟数据处理
                processed_data = f"Processed at {time.time()}"
                
                # 发送处理完成信号
                self.signal_manager.emit_regular_signal(
                    "example_plugin", "data_processed", processed_data
                )
                
                time.sleep(2)
            except Exception as e:
                print(f"插件处理错误: {str(e)}")
                time.sleep(5)
    
    def stop(self):
        """停止插件"""
        self.running = False
        print("示例插件停止")
    
    def process_data(self, data: Any) -> Any:
        """处理数据的方法（可由其他插件或核心系统调用）"""
        return f"Processed: {data}"

# 插件入口点
Plugin = ExamplePlugin