

# 测试模块类定义
class TestModuleA(BaseModule):
    @property
    def module_name(self):
        return "test_module_a"

class TestModuleB(BaseModule):
    @property
    def module_name(self):
        return "test_module_b"

class TestModuleC(BaseModule):
    @property
    def module_name(self):
        return "test_module_c"

# 在应用启动前验证模块注册
print("当前注册模块：", list(BaseModule._registry.values()))