from tokenize import Double
from sqlalchemy.types import REAL, Integer,String,DateTime,Boolean,Float,Enum,Text,Date,Time,Interval,JSON,BigInteger,SmallInteger,DECIMAL,Numeric,CHAR,VARCHAR,BINARY,VARBINARY,BOOLEAN,DATE,TIME,TIMESTAMP,TIMESTAMP
from .modelbase import DataStorageBaseModel,GeneralStorageBaseModel
from datetime import datetime
from sqlalchemy import Column

class  TestModel(DataStorageBaseModel):
    """ Model类，用于定义表结构和字段类型。
        其中属性名对应数据库表中的列名，类型对应数据库表中的列类型。
        __tablename__ 定义表名，
        __table_args__ 定义表的其他参数，此处定义了表的扩展参数，必须定义为True，否则会报错。
        __abstract__ 定义是否为抽象类，此处定义为False，即不是抽象类。必须定义为False，否则会报错。
        关于属性名和类型的定义，可以参考SQLAlchemy的文档。"""
    __tablename__ = "test"
    __table_args__ = {
        'extend_existing': True,  # 如果表已存在，允许扩展
    }
    __abstract__ =  False

    id = Column(Integer, primary_key=True, autoincrement=True)
    qdata = Column(REAL, default=0.0)
    idata = Column(REAL, default=0.0)
    time  = Column(DateTime, default=datetime.now)
    changedata = Column(REAL, default=0.0)

class  TestModel3(GeneralStorageBaseModel):
    __tablename__ = "test3"
    __table_args__ = {
        'extend_existing': True,  # 如果表已存在，允许扩展
    }
    __abstract__ =  False
    id = Column(Integer, primary_key=True, autoincrement=True)
    qdata = Column(REAL, default=0.0)    

class  TestModel2(GeneralStorageBaseModel):
    __tablename__ = "test2"
    __table_args__ = {
        'extend_existing': True,  # 如果表已存在，允许扩展
    }
    __abstract__ =  False

    id = Column(Integer, primary_key=True, autoincrement=True)
    qdata = Column(REAL, default=0.0)
    idata = Column(REAL, default=0.0)
    time  = Column(DateTime, default=datetime.now)
