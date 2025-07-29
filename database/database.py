from sqlalchemy import create_engine, URL, text
from sqlalchemy.orm import session, sessionmaker, declarative_base, scoped_session
from contextlib import contextmanager, AbstractContextManager
from typing import Type, TypeVar, Generic, Any, List,Union
import logging
import json
from pathlib import Path
from database.models.model_base import DataStorageBaseModel, GeneralStorageBaseModel
from base_module import BaseModule
logger = logging.getLogger(__name__)

Model = Union[DataStorageBaseModel, GeneralStorageBaseModel]

class Database:
    def __init__(self, db_type: str = 'mysql', **kwargs):
        """
        数据库连接管理器
        :param db_type: 数据库类型 (mysql/postgresql/sqlite)
        :param kwargs: 数据库连接参数
        """
        self.db_config = kwargs
        self.db_type = db_type
        self.engine = None
        self.session_factory = None
        
        if db_type == 'sqlite':
            print(f'SQLite数据库路径: {kwargs.get("database")}')
            
        self._setup_engine()

    def _setup_engine(self):
        """配置SQLAlchemy引擎和会话工厂"""
        connect_args = {}
        
        # 构建连接URL
        if self.db_type == 'mysql':
            url = URL.create(
                'mysql+pymysql',
                username=self.db_config.get('user'),
                password=self.db_config.get('password'),
                host=self.db_config.get('host'),
                port=self.db_config.get('port', 3306),
                database=self.db_config.get('database')
            )
            connect_args = {'connect_timeout': 10}
        elif self.db_type == 'postgresql':
            url = URL.create(
                'postgresql+psycopg2',
                username=self.db_config.get('user'),
                password=self.db_config.get('password'),
                host=self.db_config.get('host'),
                port=self.db_config.get('port', 5432),
                database=self.db_config.get('database')
            )
        elif self.db_type == 'sqlite':
            # 确保目录存在
            db_path = Path(self.db_config.get('database'))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 统一设置多线程参数
            connect_args['check_same_thread'] = False
            
            # 配置URI参数
            uri_params = ['mode=rwc', 'uri=true']
            if self.db_config.get('readonly'):
                uri_params = ['mode=ro']
            
            url = f"sqlite:///file:{db_path.as_posix()}?{'&'.join(uri_params)}"
        else:
            raise ValueError(f"不支持的数据库类型: {self.db_type}")

        # 连接池配置
        pool_config = {
            'pool_size': 20,
            'max_overflow': 50,
            'pool_recycle': 1800,
            'pool_pre_ping': True,
            'pool_use_lifo': True
        }
        print(url)
        self.engine = create_engine(url, connect_args=connect_args, **pool_config)
        self.session_factory = scoped_session(sessionmaker(bind=self.engine))

    @contextmanager
    def session_scope(self) -> AbstractContextManager:
        """提供事务管理的上下文会话"""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.exception("数据库操作异常")
            raise
        finally:
            session.close()

    # 通用CRUD操作
    def add(self, instance: Model) -> Model:
        """添加单个记录"""
        with self.session_scope() as session:
            session.add(instance)
        return instance

    def bulk_add(self, instances: list[Model]) -> list[Model]:
        """批量添加记录"""
        with self.session_scope() as session:
            session.bulk_save_objects(instances)
        return instances

    def get(self, model: Type[Model], **filters) -> Model | None:
        """获取单个记录"""
        with self.session_scope() as session:
            return session.query(model).filter_by(**filters).first()

    def list(self, model: Type[Model], **filters) -> list[Model]:
        """查询多个记录"""
        with self.session_scope() as session:
            return session.query(model).filter_by(**filters).all()

    def paginate(self, model: Type[Model], page: int = 1, per_page: int = 1000, **filters):
        """分页查询"""
        with self.session_scope() as session:
            return session.query(model).filter_by(**filters).offset((page-1)*per_page).limit(per_page)

    def stream(self, model: Type[Model], batch_size: int = 1000, **filters):
        """流式加载数据"""
        with self.session_scope() as session:
            query = session.query(model).filter_by(**filters)
            return query.yield_per(batch_size)

    def bulk_add_in_transaction(self, instances: List[Model], batch_size: int = 5000) -> None:
        """事务批量提交"""
        session = self.session_factory()
        try:
            for i in range(0, len(instances), batch_size):
                session.bulk_save_objects(instances[i:i+batch_size])
                session.commit()
        except Exception as e:
            session.rollback()
            logger.exception("批量提交异常")
            raise
        finally:
            session.close()
    def fifo_add_in_transaction(self, instances: List[Model], max_row_count: int = 500000) -> None:
        """获取当前数据库的行数,your_table替换为Model.__tablename__"""
        with self.session_scope() as session:
            model = instances[0].__class__
            current_row_count = session.execute(f"SELECT COUNT(*) FROM {model.__tablename__}").scalar()
            if current_row_count + len(instances) > max_row_count:
                # 删除最早的10%数据
                delete_count = int(current_row_count * 0.1)
                session.execute(f"DELETE FROM {model.__tablename__} ORDER BY id LIMIT {delete_count}")
                session.commit()
                session.bulk_save_objects(instances)
                session.commit()
            else:
                session.bulk_save_objects(instances)
                session.commit()
            

    def update(self, instance: Model, **update_data) -> Model:
        """更新记录"""
        with self.session_scope() as session:
            for key, value in update_data.items():
                setattr(instance, key, value)
            session.add(instance)
        return instance
                  
    def delete(self, instance: Model) -> None:
        """删除记录"""
        with self.session_scope() as session:
            session.delete(instance)

    def execute(self, sql: str, params: dict = None) -> Any:
        """执行原生SQL"""
        with self.session_scope() as session:
            return session.execute(text(sql), params or {})

  

# ORM基类


class DatabaseManager(BaseModule):
    def __init__(self, config_path: str = None, config_dict: dict = None):
        self._dbs = {}
        self.current_db = None
        
        if config_path:
            self.parse_config(config_path)
            print(self._dbs)
        elif config_dict:
            for name, cfg in config_dict.items():
                db_type = cfg.pop('db_type', 'mysql')
                self._dbs[name] = Database(db_type=db_type, **cfg)
            if self._dbs:
                self.current_db = next(iter(self._dbs.values()))

    @property
    def module_name(self) -> str:
        return "database_manager"

    def parse_config(self, config_path: str):
        """
        从配置文件加载数据库配置
        :param config_path: 配置文件路径
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                configs = json.load(f)
                
            for name, cfg in configs.items():
                db_type = cfg.pop('db_type', 'mysql')
                self._dbs[name] = Database(db_type=db_type, **cfg)
                
            self.current_db = next(iter(self._dbs.values()))



            
        except Exception as e:
            raise RuntimeError(f"配置文件解析失败: {str(e)}")



    def select(self, db_name: str):
        """
        切换当前数据库实例
        :param db_name: 数据库名称 (mysql/sqlite)
        """
        if not self._initialized:
            raise RuntimeError("请先调用initialize()方法初始化数据库配置")
        if db_name in self._dbs:
            self.current_db = self._dbs[db_name]
        else:
            raise ValueError(f"未知数据库实例: {db_name}，可用实例: {list(self._dbs.keys())}")

    def get_instance(self, name: str) -> Database:
        """
        获取指定名称的数据库实例
        :param name: 实例名称
        """
        if not self._dbs:
            raise RuntimeError("数据库配置未初始化")
        if instance := self._dbs.get(name):
            return instance
        raise ValueError(f"数据库实例'{name}'不存在")

    def list_instances(self) -> dict:
        """
        获取所有数据库实例信息
        返回格式: {实例名称: {类型: ..., 参数: ...}}
        """
        return {
            name: {
                'db_type': db.db_type,
                'config': db.db_config
            } for name, db in self._dbs.items()
        }

    def __getattr__(self, name):
        """将未定义的方法转发给当前数据库实例"""
        return getattr(self.current_db, name)


    
    