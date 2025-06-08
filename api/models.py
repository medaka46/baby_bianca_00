from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Float, Date, Sequence
from .database import Base 


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, Sequence('user_id_seq'), primary_key=True, index=True)
    username = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    # country = Column(String)
    # language = Column(String)
    
    
    
class Link(Base):
    __tablename__ = "links"

    # id = Column(Integer, primary_key=True, index=True)
    id = Column(Integer, Sequence('link_id_seq'), primary_key=True, index=True)
    
    name = Column(String, index=True)
    url = Column(String, unique=False, index=True)
    category = Column(String, index=True)
    status = Column(String, index=True)
    
    id_user = Column(Integer)
    
class Schedule(Base):
    __tablename__ = "schedules"

    # id = Column(Integer, primary_key=True, index=True)
    id = Column(Integer, Sequence('meeting_id_seq'), primary_key=True, index=True)
    
    
    name = Column(String, index=True)
    link = Column(String, index=True)
    category = Column(String, index=True)
    status = Column(String, index=True)
    
    start_datetime = Column(DateTime)
    end_datetime = Column(DateTime)
    # start_datetime = Column(DateTime, nullable=False)
    # end_datetime = Column(DateTime, nullable=False)
    
    id_user = Column(Integer)
    
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    id = Column(Integer, Sequence('project_id_seq'), primary_key=True, index=True)
    
    
    name = Column(String, index=True)
    country = Column(String, index=True)
    client = Column(String, index=True)
    type_of_building = Column(String, index=True)
    total_floor_area = Column(Float, index=True)
    m_amount = Column(Float, index=True)
    currency = Column(String)
    date_of_submission = Column(Date)
    
    id_user = Column(Integer)


