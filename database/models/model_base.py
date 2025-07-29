from sqlalchemy import create_engine, URL, text
from sqlalchemy.orm import session, sessionmaker, declarative_base, scoped_session
from sqlalchemy.ext.declarative import declared_attr  # 新增关键导入
from typing import TypeVar,Any, Dict, List, Union, Optional
from sqlalchemy import inspect
# 数据存储专用基类
from sqlalchemy.ext.declarative import declarative_base
DataStorageBase = declarative_base()
GeneralStorageBase = declarative_base()
class DataStorageBaseModel(DataStorageBase):
    __abstract__ = True
    __table_args__ = {
        'comment': 'Data storage base table'
    }
    __model_registry__ = {}  # 模型注册表（类属性，存储所有子类实例）

    def __init_subclass__(cls, **kwargs):
        """
        自动注册模型子类到注册表
        触发条件：继承 DataStorageBaseModel 且非抽象类
        异常：当重复注册时会抛出 ValueError
        """
        super().__init_subclass__(**kwargs)
        if not cls.__abstract__:
            cls.register_model()
    @classmethod
    def register_model(cls, alias: str = None):
        """
        显式注册模型到注册表
        参数：
            alias - 模型别名（可选），默认使用类名小写
        异常：
            ValueError - 当模型名称已存在时抛出
        """
        registry_name = alias or cls.__name__.lower()
        if registry_name in cls.__model_registry__:
            raise ValueError(f"模型 {registry_name} 已存在")
        cls.__model_registry__[registry_name] = cls
    @classmethod
    def get_model_class(cls, name: str):
        """
        根据名称获取已注册模型类
        参数：
            name - 注册时使用的模型名称或别名
        返回：
            Model类 或 None（未找到时）
        """
        return cls.__model_registry__.get(name)

    @classmethod
    def get_all_modelname(cls):
        """获取所有已注册模型名称"""
        return cls.__model_registry__.keys()
    @classmethod
    def get_all_tabelname(cls):
        """获取所有已注册模型db表名"""
        return [cls.__model_registry__[name].__tablename__ for name in cls.__model_registry__.keys()]
    @classmethod
    def model_schema(cls) -> Dict[str, Any]:
        """
        获取模型元数据结构
        返回：
            dict - 包含表名、字段信息、关联关系的字典
        结构：
        {
            'table': 表名,
            'columns': {字段名: 字段类型},
            'relationships': [关联关系名称列表]
        }
        """
        mapper = inspect(cls)
        return {
            'table': cls.__tablename__,
            'columns': {col.key: str(col.type) for col in mapper.columns},
            'relationships': [rel.key for rel in mapper.relationships]
        }
    

    @classmethod
    def from_dict(cls, data: dict, exclude_auto_fields=True, validate_required=True, ignore_extra_fields=False):
        """
        从字典创建模型实例（带完整验证）
        参数：
            data - 输入数据字典
            exclude_auto_fields - 是否排除自增/默认字段（默认True）
            validate_required - 是否验证必填字段（默认True）
            ignore_extra_fields - 是否忽略多余字段（默认False）
        返回：
            已验证的模型实例
        异常：
            ValueError - 当数据不符合模型要求时抛出
        """
        mapper = inspect(cls).mapper
        instance = cls()

        # 字段校验
        valid_keys = {column.name for column in mapper.columns}
        extra_keys = set(data.keys()) - valid_keys
        if extra_keys and not ignore_extra_fields:
            raise ValueError(f"非法字段: {extra_keys}")

        # 必填字段检查
        if validate_required:
            required_columns = {
                column.name
                for column in mapper.columns
                if not column.nullable
                and not column.default
                and not column.server_default
                and not column.autoincrement
            }
            missing_keys = required_columns - data.keys()
            if missing_keys:
                raise ValueError(f"缺失必填字段: {missing_keys}")

        # 动态赋值
        for key, value in data.items():
            if key not in valid_keys:
                continue  # 已通过 ignore_extra_fields 控制是否报错

            column = mapper.columns[key]
            if exclude_auto_fields and (
                column.autoincrement
                or column.server_default
            ):
                raise ValueError(f"禁止手动设置自动生成字段: {key}")

            # 类型转换（可选）
            if isinstance(value, str) and isinstance(column.type, DateTime):
                value = datetime.fromisoformat(value)
            setattr(instance, key, value)

        return instance
    @classmethod
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# 添加数据库方言特定配置
# 添加数据库方言特定配置
def _apply_dialect_specific_options(target, connection, **kw):
    dialect_name = connection.dialect.name
    if dialect_name == 'mysql':
        target.kwargs['mysql_engine'] = 'InnoDB'
        target.kwargs['mysql_charset'] = 'utf8mb4'
    elif dialect_name == 'sqlite':
        target.kwargs['sqlite_autoincrement'] = True

# 通用存储基类



class GeneralStorageBaseModel(GeneralStorageBase):
    __model_registry__ = {}  # 模型注册表
    __abstract__ = True
    __table_args__ = {
        'comment': '通用存储表（用于系统配置/日志等非核心数据）'
    }

    @declared_attr
    def __table_args__(cls):
        """
        动态生成表参数，根据连接方言自动适配：
        - MySQL：使用 InnoDB 引擎和 utf8mb4 编码
        - SQLite：启用自增主键
        - 其他数据库使用默认配置
        """
        mapper = inspect(cls)
        return {
            'table': cls.__tablename__,
            'columns': {col.key: str(col.type) for col in mapper.columns},
            'relationships': [rel.key for rel in mapper.relationships]
        }

    # 保留原有方法并添加详细注释
    @classmethod
    def register_model(cls, alias: str = None):
        """显式注册模型"""
        registry_name = alias or cls.__name__.lower()
        if registry_name in cls.__model_registry__:
            raise ValueError(f"模型 {registry_name} 已存在")
        cls.__model_registry__[registry_name] = cls
    @classmethod
    def get_model_class(cls, name: str) :
        """获取已注册模型类"""
        return cls.__model_registry__.get(name)

    @classmethod
    def get_all_modelname(cls):
        """获取所有已注册模型名称"""
        return cls.__model_registry__.keys()
    @classmethod
    def get_all_tabelname(cls):
        """获取所有已注册模型db表名"""
        return [cls.__model_registry__[name].__tablename__ for name in cls.__model_registry__.keys()]
    @classmethod
    def model_schema(cls) -> Dict[str, Any]:
        """获取模型结构元数据"""
        mapper = inspect(cls)
        return {
            'table': cls.__tablename__,
            'columns': {
                col.key: str(col.type) 
                for col in mapper.columns
            },
            'relationships': [
                rel.key for rel in mapper.relationships
            ]
        }
    

    @classmethod
    def from_dict(
        cls,
        data: dict,
        exclude_auto_fields=True,
        validate_required=True,
        ignore_extra_fields=False
    ):
        """将字典转换为模型实例，有效字段校验，排除了自动生成字段，允许忽略有默认值的字段"""
        mapper = inspect(cls).mapper
        instance = cls()

        # 字段校验
        valid_keys = {column.name for column in mapper.columns}
        extra_keys = set(data.keys()) - valid_keys
        if extra_keys and not ignore_extra_fields:
            raise ValueError(f"非法字段: {extra_keys}")

        # 必填字段检查
        if validate_required:
            required_columns = {
                column.name
                for column in mapper.columns
                if not column.nullable
                and not column.default
                and not column.server_default
                and not column.autoincrement
            }
            missing_keys = required_columns - data.keys()
            if missing_keys:
                raise ValueError(f"缺失必填字段: {missing_keys}")

        # 动态赋值
        for key, value in data.items():
            if key not in valid_keys:
                continue  # 已通过 ignore_extra_fields 控制是否报错

            column = mapper.columns[key]
            if exclude_auto_fields and (
                column.autoincrement
                or column.server_default
            ):
                raise ValueError(f"禁止手动设置自动生成字段: {key}")

            # 类型转换（可选）
            if isinstance(value, str) and isinstance(column.type, DateTime):
                value = datetime.fromisoformat(value)
            setattr(instance, key, value)

        return instance
    @classmethod
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# 统一注册事件监听
from sqlalchemy import event
event.listen(DataStorageBase.metadata, 'before_create', _apply_dialect_specific_options, propagate=True)
event.listen(GeneralStorageBase.metadata, 'before_create', _apply_dialect_specific_options, propagate=True)