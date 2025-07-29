from sqlalchemy.types import Integer,String,DateTime,Boolean,Float,Enum,Text,Date,Time,Interval,JSON,BigInteger,SmallInteger,DECIMAL,Numeric,CHAR,VARCHAR,BINARY,VARBINARY,BOOLEAN,DATE,TIME,TIMESTAMP,TIMESTAMP
from .model_base import DataStorageBaseModel,GeneralStorageBaseModel
from datetime import datetime
from sqlalchemy import Column

class Datas(DataStorageBaseModel):
    __tablename__ = 'datas'  # 表名
    __table_args__ = {
        'extend_existing': True  # 如果表已存在，允许扩展
    }
    __abstract__ =  False
    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    data = Column(Integer, default = 0)  # 整数字段
    # 日期时间字段，默认当前时间，更新时自动更新
    created_at = Column(DateTime, default=datetime.now)
class Users(GeneralStorageBaseModel):
    __tablename__ = 'users'  # 表名
    __table_args__ = {
        'extend_existing': True  # 如果表已存在，允许扩展
    }
    __abstract__ =  False
    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    name = Column(String(50), nullable=False)  # 非空字符串字段
    age = Column(Integer,default = 18)  # 整数字段
    email = Column(String(100), unique=True)  # 唯一字符串字段
    created_at = Column(DateTime, default=datetime)  # 日期时间字段，默认当前时间
    updated_at = Column(DateTime, default=datetime, onupdate=datetime.now)


class Datas2(DataStorageBaseModel):
    __tablename__ = 'datas2'  # 表名
    __table_args__ = {
        'extend_existing': True  # 如果表已存在，允许扩展
    }
    __abstract__ =  False
    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    data = Column(Integer, default = 0)  # 整数字段
    data2=Column(Integer, default = 0)  # 整数字段
    data3=Column(Integer, default = 0)  # 整数字段
    data4=Column(Integer, default = 0)
    data5=Column(Integer, default = 0)
    data6=Column(Integer, default = 0)
    # 日期时间字段，默认当前时间，更新时自动更新
    created_at = Column(DateTime, default=datetime.now)

class Users2(GeneralStorageBaseModel):
    __tablename__ = 'users2'  # 表名
    __table_args__ = {
        'extend_existing': True  # 如果表已存在，允许扩展
    }
    __abstract__ =  False
    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    name = Column(String(50), nullable=False)  # 非空字符串字段
    age = Column(Integer,default = 18)  # 整数字段
    email = Column(String(100), unique=True)  # 唯一字符串字段
    data = Column(Integer, default = 0)  # 整数字段
    created_at = Column(DateTime, default=datetime)  # 日期时间字段，默认当前时间
    updated_at = Column(DateTime, default=datetime, onupdate=datetime.now)

class Users3(GeneralStorageBaseModel):
    __tablename__ = 'users3'  # 表名
    __table_args__ = {
        'extend_existing': True  # 如果表已存在，允许扩展
    }
    __abstract__ =  False
    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    name = Column(String(50), nullable=False)  # 非空字符串字段
    age = Column(Integer,default = 18)  # 整数字段
    email = Column(String(100), unique=True)  # 唯一字符串字段
    data = Column(Integer, default = 0)  # 整数字段
    created_at = Column(DateTime, default=datetime)  # 日期时间字段，默认当前时间
    updated_at = Column(DateTime, default=datetime, onupdate=datetime.now)