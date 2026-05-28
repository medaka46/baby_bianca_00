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


class AllowedUser(Base):
    """Pre-approved sign-up allowlist.

    Admin pre-populates rows here (via SQLite CLI / DB browser) for each
    user permitted to sign up. The /login_signup/add_user/ route accepts a
    sign-up only if (username, email, password) all match a row in this table.

    Passwords stored as plaintext for now (per agreed roadmap); a future step
    will add a 'change my password' flow that re-hashes with bcrypt.
    """
    __tablename__ = "allowed_users"
    id = Column(Integer, Sequence('allowed_user_id_seq'), primary_key=True, index=True)
    username = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)



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

    # Daily-task fields. is_daily_task=1 means the row has no clock time;
    # task_date is the fixed calendar date (TZ-independent) shown on the grid.
    is_daily_task = Column(Integer, default=0, index=True)
    task_date = Column(Date, index=True)

    # Repeat-task fields. is_repeat_task=1 means the row is a template that
    # expands to multiple occurrences between range_start and range_end. The
    # Today area reads templates and decides whether today matches the pattern;
    # no per-occurrence rows are written.
    #   repeat_type: 'every_day' | 'every_weekday' | 'every_specific_weekday'
    #   repeat_weekdays: CSV of Python weekday ints, e.g. '0,2,4' (Mon=0..Sun=6)
    #     — only used when repeat_type='every_specific_weekday'.
    is_repeat_task = Column(Integer, default=0, index=True)
    repeat_type = Column(String, index=True)
    repeat_weekdays = Column(String)
    range_start = Column(Date, index=True)
    range_end = Column(Date, index=True)
    today_only = Column(Integer, default=0, index=True)
    repeat_start_time = Column(String)
    repeat_end_time = Column(String)

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


class Todo(Base):
    __tablename__ = "todo"

    id = Column(Integer, Sequence('todo_id_seq'), primary_key=True, index=True)

    title = Column(String, index=True)
    description = Column(String)
    category = Column(String, index=True)
    priority = Column(String, index=True)
    status = Column(String, index=True)
    due_date = Column(Date)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    id_user = Column(Integer, index=True)
    username = Column(String, index=True)


class Diary(Base):
    __tablename__ = "diary"

    id = Column(Integer, Sequence('diary_id_seq'), primary_key=True, index=True)

    title = Column(String, index=True)
    content = Column(String)
    type = Column(String, index=True)
    category = Column(String, index=True)
    entry_date = Column(Date, index=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    id_user = Column(Integer, index=True)
    username = Column(String, index=True)


