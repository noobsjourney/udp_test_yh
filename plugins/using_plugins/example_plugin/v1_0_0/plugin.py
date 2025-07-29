from base_module import BaseModule

class ExamplePlugin(BaseModule):
    def __init__(self, service_proxy):
        super().__init__()
        print("ExamplePlugin 初始化完成")

    @property
    def module_name(self):
        return "example_plugin"

    def run(self):
        print("ExamplePlugin 正在运行")