#为插件调用的 API 提供统一入口和权限校验机制，防止未授权的插件调用敏感操作

from functools import wraps

class APIGateway:
    def __init__(self, plugin_manager):
        self.pm = plugin_manager#插件管理器，用于获取每个插件的配置，判断是否有权限调用某个 API。
        self.api_whitelist = {
            'basic': ['get_status', 'log'],
            'advanced': ['db_access', 'network']
        }#备用白名单系统，可以按等级划分开放 API（代码中未使用）。

    #权限检查函数
    # 读取插件配置allowed_apis列表。
    # 如果插件未授权访问某API，就返回False。
    def check_permission(self, plugin_name, api_name):
        allowed_apis = self.pm.config['plugins'].get(plugin_name, {}).get('allowed_apis', [])
        return api_name in allowed_apis

    #API代理装饰器类APIProxy
    class APIProxy:
        """内部代理类解决作用域问题"""
        def __init__(self, gateway, api_name):
            self.gateway = gateway
            self.api_name = api_name

        def __call__(self, func):
            @wraps(func)
            def wrapper(plugin_name, *args, **kwargs):
                if not self.gateway.check_permission(plugin_name, self.api_name):
                    raise PermissionError(f"插件 {plugin_name} 无权访问 {self.api_name}")
                return func(plugin_name, *args, **kwargs)
            return wrapper

    def api_proxy(self, api_name=None):
        """装饰器工厂的正确实现"""
        return self.APIProxy(self, api_name)

    def db_query(self, plugin_name, query):
        return self._execute_query(plugin_name, query)

    def _execute_query(self, plugin_name, query):
        return f"[{plugin_name}] 执行查询: {query}"


if __name__ == "__main__":
    class MockManager:
        config = {
            "plugins": {
                "valid_plugin": {"allowed_apis": ["db_query"]},
                "invalid_plugin": {"allowed_apis": []}
            }
        }


    gateway = APIGateway(MockManager())

    # 在类定义完成后应用装饰器
    gateway.db_query = gateway.api_proxy(api_name="db_query")(gateway.db_query)

    # 合法请求
    print(gateway.db_query("valid_plugin", "SELECT * FROM users"))

    # 非法请求测试
    try:
        gateway.db_query("invalid_plugin", "DELETE *")
    except PermissionError as e:
        print(f"拦截非法请求: {e}")
