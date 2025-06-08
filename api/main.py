import logging
from fastapi import FastAPI, Depends, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc
from api.database import SessionLocal, engine, Base, ENVIRONMENT # Use absolute import
from api.models import User, Schedule, Link  # Use absolute import
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
from starlette.middleware.sessions import SessionMiddleware

from pandas import Timestamp

import os

from fastapi.staticfiles import StaticFiles

app = FastAPI()
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mount the static directory to serve static files
app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))





logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

app.mount("/static", StaticFiles(directory="static"), name="static")


# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Create the database tables if they don't exist
Base.metadata.create_all(bind=engine)

condition = ""

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# --------------------

@app.get("/", response_class=HTMLResponse)

# @app.get("/")
async def login_signup(request: Request):
    message = "Please Log in or Sing up"
    message_color = "#0f0"
    
    start_date_adjust = 0
    
    # start_date = datetime.today() - timedelta(days = datetime.today().weekday()) # set up monday is start_date
    start_date = datetime.today() - timedelta(days = datetime.today().weekday() + start_date_adjust ) # set up monday is start_date
    date_sequence = [str((start_date + timedelta(days=i)).strftime('%Y-%m-%d')) for i in range(7*10)]  # 7*10 days sequence
    today_date = datetime.today().strftime('%Y-%m-%d')
    
    request.session['start_date_adjust'] = start_date_adjust
    test_date = request.session.get('start_date_adjust')
    print(test_date)
    
    request.session['link_tab_page_active'] = "link_001"
    
    request.session['project_chart_switch'] = 1
    
    request.session['project_button_serect'] = "ID"
    
    request.session['project_id_order'] = 1
    
    
    if ENVIRONMENT == 'production':
        condition = "Production"
    else:
        condition = "Development"
        
    
    print(condition)
    
    
    
    # return templates.TemplateResponse("test01.html", {"request": request, "message": message, "message_color": message_color})
    # print("login_signup.html")
    return templates.TemplateResponse("login_signup.html", {"request": request, "message": message, "message_color": message_color, "request": request, "condition": condition})
    # return templates.TemplateResponse("login_signup.html", {"request": request, "message": message, "message_color": message_color})

# --------------------

@app.get("/download_db/")
async def download_db(request: Request, db: Session = Depends(get_db)):
    from api.database import get_database_path
    
    # Get the current database path (works for both local and Render)
    db_path = get_database_path()

    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_backup_{timestamp}.db"

    return FileResponse(db_path, media_type='application/octet-stream', filename=filename)


# @app.get("/download_db/")
# async def download_db(request: Request, db: Session = Depends(get_db)):
#     db_path = "../test_08_db_new_pp.db"  # Replace with the actual path to your SQLite database

#     if not os.path.exists(db_path):
#         raise HTTPException(status_code=404, detail="Database file not found")

#     return FileResponse(db_path, media_type='application/octet-stream', filename="test_08_db_new_pp.db")

# --------------------

@app.get("/debug-info")
async def debug_info():
    """Debug endpoint to check database configuration and environment."""
    from api.database import get_database_path, get_database_url, ENVIRONMENT
    
    db_path = get_database_path()
    is_render = bool(os.getenv("RENDER"))
    
    info = {
        "environment": ENVIRONMENT,
        "is_render": is_render,
        "database_path": db_path,
        "database_url": get_database_url(),
        "database_exists": os.path.exists(db_path),
        "current_working_directory": os.getcwd(),
        "render_env_var": os.getenv("RENDER", "Not set"),
        "environment_var": os.getenv("ENVIRONMENT", "Not set")
    }
    
    if os.path.exists(db_path):
        info["database_size"] = os.path.getsize(db_path)
        
        # Try to count records in main tables
        try:
            db = SessionLocal()
            user_count = db.query(User).count()
            schedule_count = db.query(Schedule).count()
            link_count = db.query(Link).count()
            db.close()
            
            info["table_counts"] = {
                "users": user_count,
                "schedules": schedule_count,
                "links": link_count
            }
        except Exception as e:
            info["database_read_error"] = str(e)
    
    return info

# --------------------

@app.post("/login_signup/add_user/")
async def add_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        # Check if the user already exists
        db_user_check = db.query(User).filter(User.email == email).first()
        if db_user_check:
            message = "Sign up failed. Email address is already used."
            message_color = "#f00"
            return templates.TemplateResponse("login_signup.html", {"request": request, "message": message, "message_color": message_color})

        # Check if the user exists in the CSV file
        df_user = pd.read_csv('user.csv')
        df_user_check = df_user[(df_user['username'] == username) & (df_user['email'] == email)]
        if not df_user_check.empty:
            message = "Sign up was accepted. Please proceed to Log in."
            message_color = "#0f0"

            # Add the new user to the database
            db_item = User(username=username, email=email, password=password)
            try:
                db.add(db_item)
                db.commit()
                db.refresh(db_item)
            except Exception as e:
                db.rollback()
                message = f"An error occurred: {str(e)}"
                message_color = "#f00"
                logger.error(f"Database error: {str(e)}")

            return templates.TemplateResponse("login_signup.html", {"request": request, "message": message, "message_color": message_color})
        else:
            message = "Sorry, but you are not authorized to sign up."
            message_color = "#f00"
            return templates.TemplateResponse("login_signup.html", {"request": request, "message": message, "message_color": message_color})
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return HTMLResponse(content=f"An unexpected error occurred: {str(e)}", status_code=500)
    
# --------------------

start_date = datetime.today() - timedelta(days = datetime.today().weekday()) # set up monday is start_date

date_sequence = [str((start_date + timedelta(days=i)).strftime('%Y-%m-%d')) for i in range(7*10)]  # 7*10 days sequence

today_date = datetime.today().strftime('%Y-%m-%d')

# --------------------

@app.post("/login_signup/check_user/")
async def check_user(request: Request, date_sequence = date_sequence, today_date = today_date, username: str = Form(...), email: str = Form(...), password: str = Form(None), db: Session = Depends(get_db), skip: int = Query(0), limit: int = Query(50)):
    db_user = db.query(User).filter(User.username == username, User.email == email, User.password == password).first()
    
    if db_user:
        login_username = username
        time_zone_message = "Please select Time zone :"
        message_color = "#f00"
        
        return templates.TemplateResponse("schedule_indicate_00.html", {
            "request": request,
            "dates": date_sequence,
            "today": today_date,
            "login_username": login_username,
            "time_zone_message": time_zone_message,
            "message_color": message_color,
            "skip": skip,
            "limit": limit,
            "has_more": False,
            "condition": condition# or True based on your logic
        })
    else:
        message = "Log in failed. Please try again!"
        message_color = "#f00"
        return templates.TemplateResponse("login_signup.html", {"request": request, "message": message, "message_color": message_color, "condition": condition})


    
# --------------------

@app.get("/schedule/")
async def schedule(request: Request, time_zone: str = "UTC", db: Session = Depends(get_db), skip: int = Query(0), limit: int = Query(200)):
    login_username = request.session.get('login_username')
    time_zone = request.session.get('time_zone', time_zone)
    logger.info(f"Time zone is {time_zone}")

    # Fetch the tasks with pagination
    tasks = db.query(Schedule).with_entities(
        Schedule.id,
        Schedule.name,
        Schedule.start_datetime,
        Schedule.end_datetime,
        Schedule.link,
        
        # Schedule.category,
        # Schedule.status,
        # Schedule.id_user
    # ).order_by(Schedule.start_datetime).offset(skip).limit(limit).all()
    ).order_by(Schedule.start_datetime).all()
    # ).order_by(desc(Schedule.start_datetime)).offset(skip).limit(limit).all()
    
    # print('tasks[0]', tasks[0])
    # print('tasks length', tasks[0])

    # Check if there are more records to fetch
    total_tasks = db.query(Schedule).count()
    has_more = skip + limit < total_tasks

    # Calculate current page and total pages
    current_page = (skip // limit) + 1
    total_pages = (total_tasks // limit) + (1 if total_tasks % limit > 0 else 0)

    start_date_adjust = request.session.get('start_date_adjust', 0)
    start_date = datetime.today() - timedelta(days=datetime.today().weekday() + start_date_adjust)
    date_sequence = [str((start_date + timedelta(days=i)).strftime('%Y-%m-%d')) for i in range(7*50)]
    today_date = datetime.today().astimezone(ZoneInfo(time_zone)).strftime('%Y-%m-%d')
    # today_date = datetime.today().strftime('%Y-%m-%d')

    data = [{
        'id': task.id,
        'name': task.name,
        # 'start_datetime': task.start_datetime.astimezone(ZoneInfo(time_zone)),
        # 'end_datetime': task.end_datetime.astimezone(ZoneInfo(time_zone)),
        'link': task.link,
        
        
        'start_datetime': task.start_datetime,
        'end_datetime': task.end_datetime,
        # 'category': task.category,
        # 'status': task.status,
        # 'id_user': task.id_user
    } for task in tasks]

    df_tasks = pd.DataFrame(data)
    df_tasks['start_datetime'] = pd.to_datetime(df_tasks['start_datetime']).dt.tz_localize('UTC')
    df_tasks['end_datetime'] = pd.to_datetime(df_tasks['end_datetime']).dt.tz_localize('UTC')

    local_start_dates = []
    local_start_times = []
    local_end_dates = []
    local_end_times = []

    for i in range(len(df_tasks)):
        df_task = df_tasks.iloc[i]
        local_start_datetime = df_task["start_datetime"].astimezone(ZoneInfo(time_zone))
        local_start_date = local_start_datetime.date()
        local_start_time = local_start_datetime.time().strftime("%H:%M")
        local_start_dates.append(str(local_start_date))
        local_start_times.append(str(local_start_time))

        local_end_datetime = df_task["end_datetime"].astimezone(ZoneInfo(time_zone))
        local_end_date = local_end_datetime.date()
        local_end_time = local_end_datetime.time().strftime("%H:%M")
        local_end_dates.append(str(local_end_date))
        local_end_times.append(str(local_end_time))

    df_local_start_dates = pd.DataFrame(local_start_dates, columns=['local_start_date'])
    df_local_start_times = pd.DataFrame(local_start_times, columns=['local_start_time'])
    df_local_end_dates = pd.DataFrame(local_end_dates, columns=['local_end_date'])
    df_local_end_times = pd.DataFrame(local_end_times, columns=['local_end_time'])

    df_combined = pd.concat([df_tasks, df_local_start_dates, df_local_start_times, df_local_end_dates, df_local_end_times], axis=1)
    
    # Convert Timestamp objects to strings
    df_combined = df_combined.apply(lambda col: col.map(lambda x: x.isoformat() if isinstance(x, pd.Timestamp) else x))
    
    df_combined_dict = df_combined.to_dict(orient='records')
    length_df_combined = len(df_combined)

    time_zone_message = "Current time zone :"
    message_color = "#0f0"
    tab_page_active = "schedule"

    # Log the size of the response content
    response_content = json.dumps(df_combined_dict)
    response_size = len(response_content)
    logger.info(f"Response size: {response_size} bytes")

    return templates.TemplateResponse("schedule_indicate_00.html", {
        "request": request,
        "df_combined": df_combined_dict,
        "dates": date_sequence,
        "today": today_date,
        "time_zone": time_zone,
        "length_df_combined": length_df_combined,
        "local_start_date": local_start_date,
        "local_start_time": local_start_time,
        "time_zone_message": time_zone_message,
        "message_color": message_color,
        "login_username": login_username,
        "tab_page_active": tab_page_active,
        "skip": skip,
        "limit": limit,
        "has_more": has_more,
        "next_skip": skip + limit if has_more else None,
        "current_page": current_page,
        "total_pages": total_pages,
        "condition": condition
        
    })


# --------------------
@app.get("/schedule_reload/", response_class=JSONResponse)
async def get_schedule_data(db: Session = Depends(get_db)):
    tasks = db.query(Link).all()
    data = [{
        'id': task.id,
        'name': task.name,
        'url': task.url,
        'category': task.category,
        'status': task.status
    } for task in tasks]
    return data
    
# --------------------


@app.post("/schedule/select_time_zone/")
async def select_time_zone(request: Request, login_username: str = Form(...), time_zone: str = Form(...), db: Session = Depends(get_db)):
    request.session['login_username'] = login_username  # Save to session
    request.session['time_zone'] = time_zone  # Save to session

    # Log the size of the response content
    response_content = json.dumps({"login_username": login_username, "time_zone": time_zone})
    response_size = len(response_content)
    logger.info(f"Time zone: {time_zone}, Response size: {response_size} bytes")

    return RedirectResponse("/schedule/", status_code=303)

# --------------------

@app.get("/schedule/edit_task/{item_id}")
async def edit_task(item_id: int, request: Request, db: Session = Depends(get_db), skip: int = Query(0), limit: int = Query(50)):
    # Fetch the task from the database
    db_item = db.query(Schedule).filter(Schedule.id == item_id).first()
    
    # Check if the item exists
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # The timestamp to UTC
    utc_start_datetime = pd.Timestamp(db_item.start_datetime).tz_localize("UTC")
    utc_end_datetime = pd.Timestamp(db_item.end_datetime).tz_localize("UTC")
    
    time_zone = request.session.get('time_zone', 'UTC')
    local_start_datetime = utc_start_datetime.astimezone(ZoneInfo(time_zone))
    local_end_datetime = utc_end_datetime.astimezone(ZoneInfo(time_zone))
    
    selected_local_start_date = local_start_datetime.date()
    selected_local_start_time = local_start_datetime.time().strftime("%H:%M")
    selected_local_end_time = local_end_datetime.time().strftime("%H:%M")

    # Generate date sequence for the template
    start_date_adjust = request.session.get('start_date_adjust', 0)
    start_date = datetime.today() - timedelta(days=datetime.today().weekday() + start_date_adjust)
    date_sequence = [str((start_date + timedelta(days=i)).strftime('%Y-%m-%d')) for i in range(7*10)]
    today_date = datetime.today().strftime('%Y-%m-%d')
    
    # Fetch tasks with pagination
    tasks = db.query(Schedule).with_entities(
        Schedule.id,
        Schedule.name,
        Schedule.start_datetime,
        Schedule.end_datetime,
        # Schedule.category,
        # Schedule.status,
        # Schedule.id_user
    ).order_by(Schedule.start_datetime).all()

    # Check if there are more records to fetch
    total_tasks = db.query(Schedule).count()
    has_more = skip + limit < total_tasks

    # Calculate current page and total pages
    current_page = (skip // limit) + 1
    total_pages = (total_tasks // limit) + (1 if total_tasks % limit > 0 else 0)

    data = [{
        'id': task.id,
        'name': task.name,
        'start_datetime': task.start_datetime,
        'end_datetime': task.end_datetime,
        # 'category': task.category,
        # 'status': task.status,
        # 'id_user': task.id_user
    } for task in tasks]

    df_tasks = pd.DataFrame(data)
    df_tasks['start_datetime'] = pd.to_datetime(df_tasks['start_datetime']).dt.tz_localize('UTC')
    df_tasks['end_datetime'] = pd.to_datetime(df_tasks['end_datetime']).dt.tz_localize('UTC')

    local_start_dates = []
    local_start_times = []
    local_end_dates = []
    local_end_times = []

    for i in range(len(df_tasks)):
        df_task = df_tasks.iloc[i]
        local_start_datetime = df_task["start_datetime"].astimezone(ZoneInfo(time_zone))
        local_start_date = local_start_datetime.date()
        local_start_time = local_start_datetime.time().strftime("%H:%M")
        local_start_dates.append(str(local_start_date))
        local_start_times.append(str(local_start_time))

        local_end_datetime = df_task["end_datetime"].astimezone(ZoneInfo(time_zone))
        local_end_date = local_end_datetime.date()
        local_end_time = local_end_datetime.time().strftime("%H:%M")
        local_end_dates.append(str(local_end_date))
        local_end_times.append(str(local_end_time))

    df_local_start_dates = pd.DataFrame(local_start_dates, columns=['local_start_date'])
    df_local_start_times = pd.DataFrame(local_start_times, columns=['local_start_time'])
    df_local_end_dates = pd.DataFrame(local_end_dates, columns=['local_end_date'])
    df_local_end_times = pd.DataFrame(local_end_times, columns=['local_end_time'])

    df_combined = pd.concat([df_tasks, df_local_start_dates, df_local_start_times, df_local_end_dates, df_local_end_times], axis=1)
    
    # Convert Timestamp objects to strings
    df_combined = df_combined.apply(lambda col: col.map(lambda x: x.isoformat() if isinstance(x, pd.Timestamp) else x))
    
    df_combined_dict = df_combined.to_dict(orient='records')

    # Render the template with the task data
    return templates.TemplateResponse("schedule_edit_00.html", {
        "request": request,
        "item": db_item,
        "selected_local_start_date": selected_local_start_date,
        "selected_local_start_time": selected_local_start_time,
        "selected_local_end_time": selected_local_end_time,
        "time_zone": time_zone,
        "dates": date_sequence,
        "today": today_date,
        "df_combined": df_combined_dict,
        "skip": skip,
        "limit": limit,
        "has_more": has_more,
        "current_page": current_page,
        "total_pages": total_pages
    })


    
# --------------------

@app.post("/schedule/add_task/")

# async def create_item(name: str = Form(...), date1: str = Form(...), link: str = Form(...), tel: str = Form(...), db: Session = Depends(get_db)):
# async def create_item(name: str = Form(...), date1: date1 = Form(...), link: str = Form(...), tel: str = Form(...), db: Session = Depends(get_db)):
async def create_item(request: Request, name: str = Form(...), date1: str = Form(...), start_time: str = Form(...), end_time: str = Form(...), link: str = Form(None), category: str = Form(None), status: str = Form(None), username: str = Form(None), time_zone: str = Form(None), db: Session = Depends(get_db)):
# async def create_item(request: Request, name: str = Form(...), date1: str = Form(...), start_time: str = Form(...), end_time: str = Form(...), link: str = Form(None), category: str = Form(None), status: str = Form(None), username: str = Form(None), local_time_zone = local_time_zone, db: Session = Depends(get_db)):
    date1 = datetime.strptime(date1, '%Y-%m-%d').date()
    if start_time == '00:00' and end_time == '00:00':
        start_time = "00:01"
        end_time = "00:01"
    else:
        pass
    # global active_meeting
    # date1 = date1.date()
# Assuming date1 is a string in the format 'YYYY-MM-DD'
    
    # print("test")
    print(f"{time_zone} @ schedule/add_task")
    # local_time_zone = "Asia/Singapore"
    
    # print(f"local_start_datetime : {local_start_datetime}")
    # print(f"local_end_datetime : {local_end_datetime}")
    
    # local_start_datetime_with_tz  = local_start_datetime.astimezone(ZoneInfo(get_current_timezone()))
    # local_start_datetime_with_tz  = local_start_datetime.astimezone(ZoneInfo(time_zone))
    
    local_start_datetime = datetime.combine(date1, datetime.strptime(start_time, '%H:%M').time())
    local_start_datetime_with_tz  = local_start_datetime.replace(tzinfo=ZoneInfo(time_zone))
    utc_start_datetime_with_tz  = local_start_datetime_with_tz.astimezone(timezone.utc)
    local_start_datetime_without_tz  = local_start_datetime_with_tz.replace(tzinfo=None)
    utc_start_datetime_without_tz  = utc_start_datetime_with_tz.replace(tzinfo=None)
    
    local_end_datetime = datetime.combine(date1, datetime.strptime(end_time, '%H:%M').time())
    local_end_datetime_with_tz  = local_end_datetime.replace(tzinfo=ZoneInfo(time_zone))
    utc_end_datetime_with_tz  = local_end_datetime_with_tz.astimezone(timezone.utc)
    local_end_datetime_without_tz  = local_end_datetime_with_tz.replace(tzinfo=None)
    utc_end_datetime_without_tz  = utc_end_datetime_with_tz.replace(tzinfo=None)
    
    # local_end_datetime_with_tz  = local_end_datetime.astimezone(ZoneInfo(get_current_timezone()))
    # local_end_datetime_with_tz  = local_end_datetime.astimezone(ZoneInfo(time_zone))
    # utc_end_datetime_with_tz  = local_end_datetime_with_tz.astimezone(timezone.utc)
    # local_end_datetime_with_tz  = local_end_datetime.replace(tzinfo=ZoneInfo(time_zone))
    # local_end_datetime_without_tz  = local_end_datetime_with_tz.replace(tzinfo=None)
    # utc_end_datetime_without_tz  = utc_end_datetime_with_tz.replace(tzinfo=None)
    
    print("local startdatetime with tz", local_start_datetime_with_tz)
    print("utc startdatetime with tz", utc_start_datetime_with_tz)
    print("local startdatetime without tz", local_start_datetime_without_tz)
    print("utc startdatetime without tz", utc_start_datetime_without_tz)
    print("-------------------")
    print("local enddatetime with tz", local_end_datetime_with_tz)
    print("utc enddatetime with tz", utc_end_datetime_with_tz)
    print("local enddatetime without tz", local_end_datetime_without_tz)
    print("utc enddatetime without tz", utc_end_datetime_without_tz)
    
    
    
    
    
    end_datetime  = local_end_datetime.astimezone(ZoneInfo(time_zone))
    
    
    db_item = Schedule(name=name, start_datetime=utc_start_datetime_without_tz, end_datetime=utc_end_datetime_without_tz, link=link, category=category, status=status)
    # db_item = Schedule(name=name, start_datetime=utc_start_datetime_with_tz, end_datetime=utc_end_datetime_with_tz, link=link, category=category, status=status)
    # db_item = Schedule(name=name, start_datetime=utc_start_datetime_without_tz, end_datetime=utc_end_datetime_without_tz, link=link, category=category, status=status)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return RedirectResponse("/schedule/", status_code=303)
    

# --------------------

    
# --------------------

@app.post("/schedule/update_task/{item_id}")

async def create_item(request: Request, item_id: int, action: str = Form(...), name: str = Form(...), date1: str = Form(...), start_time: str = Form(...), end_time: str = Form(...), link: str = Form(None), category: str = Form(None), status: str = Form(None), username: str = Form(None), time_zone: str = Form(None), db: Session = Depends(get_db)):

    print(action)
    
    # if action == "update":
    
    
    date1 = datetime.strptime(date1, '%Y-%m-%d').date()
    login_username = request.session.get('login_username')# login_username
    time_zone = request.session.get('time_zone')# login_username
    
    # print("test")
    print("update/time_zone", time_zone)
    # local_time_zone = "Asia/Singapore"
    
    print("login_username", login_username)
    
    local_start_datetime = datetime.combine(date1, datetime.strptime(start_time, '%H:%M').time())
    print(f"local_start_datetime : {local_start_datetime}")
    local_end_datetime = datetime.combine(date1, datetime.strptime(end_time, '%H:%M').time())
    
    local_start_datetime_with_tz = local_start_datetime.replace(tzinfo=ZoneInfo(time_zone))
    utc_start_datetime_with_tz  = local_start_datetime_with_tz.astimezone(timezone.utc)
    local_start_datetime_without_tz  = local_start_datetime_with_tz.replace(tzinfo=None)
    utc_start_datetime_without_tz  = utc_start_datetime_with_tz.replace(tzinfo=None)
    
    local_end_datetime_with_tz = local_end_datetime.replace(tzinfo=ZoneInfo(time_zone))
    utc_end_datetime_with_tz  = local_end_datetime_with_tz.astimezone(timezone.utc)
    local_end_datetime_without_tz  = local_end_datetime_with_tz.replace(tzinfo=None)
    utc_end_datetime_without_tz  = utc_end_datetime_with_tz.replace(tzinfo=None)
    
    
    # local_start_datetime_with_tz  = local_start_datetime.tz_localize(time_zone)
    # local_start_datetime_with_tz  = local_start_datetime.astimezone(ZoneInfo(time_zone))
    
    
    # local_end_datetime_with_tz  = local_end_datetime.replace(tzinfo=ZoneInfo(time_zone))
    # # local_end_datetime_with_tz  = local_end_datetime.astimezone(ZoneInfo(time_zone))
    # utc_end_datetime_with_tz  = local_end_datetime_with_tz.replace(tzinfo=None)
    # # local_end_datetime_without_tz  = datetime.strptime(local_end_datetime_with_tz, "%Y-%m-%d %H:%H").replace(tzinfo=None), 
    # utc_end_datetime_without_tz  = utc_end_datetime_with_tz.replace(tzinfo=None)
    
    # utc_start_datetime_without_tz = datetime.strptime(utc_start_datetime_without_tz, "%Y-%m-%d %H:%H")
    
    
    print("local startdatetime", local_start_datetime)
    print("local startdatetime with tz", local_start_datetime_with_tz)
    print("utc startdatetime with tz", utc_start_datetime_with_tz)
    print("local startdatetime without tz", local_start_datetime_without_tz)
    print("utc startdatetime without tz", utc_start_datetime_without_tz)
    print("------------------------")
    print("local startdatetime", local_start_datetime)
    print("local startdatetime with tz", local_start_datetime_with_tz)
    print("utc startdatetime with tz", utc_start_datetime_with_tz)
    print("local startdatetime without tz", local_start_datetime_without_tz)
    print("utc startdatetime without tz", utc_start_datetime_without_tz)
    
    
    
    
    
    end_datetime  = local_end_datetime.astimezone(ZoneInfo(time_zone))

    
    db_item = db.query(Schedule).filter(Schedule.id == item_id).first()
    if db_item:
        if action == "update":
        # db_item = Schedule(name=name, start_datetime=utc_start_datetime_with_tz, end_datetime=utc_end_datetime_with_tz, link=link, category=category, status=status)
        
        
            db_item.name = name
            db_item.start_datetime = utc_start_datetime_without_tz
            # db_item.start_datetime = datetime.strptime(utc_start_datetime_without_tz.strftime("%Y-%m-%d %H:%H"), "%Y-%m-%d %H:%H")
            db_item.end_datetime = utc_end_datetime_without_tz
            # db_item.end_datetime = datetime.strptime(utc_end_datetime_without_tz, "%Y-%m-%d %H:%H")
            db_item.link = link
            db_item.category = category
            db_item.status = status
            # db_item.end_datetime = local_end_date
            # db_item.id_user = id_user
            db.commit()
            db.refresh(db_item)
            return RedirectResponse("/schedule/", status_code=303)
        
        else:
            print("else")
            db_item = Schedule(name=name, start_datetime=utc_start_datetime_with_tz, end_datetime=utc_end_datetime_with_tz, link=link, category=category, status=status)
    # db_item = Schedule(name=name, start_datetime=utc_start_datetime_without_tz, end_datetime=utc_end_datetime_without_tz, link=link, category=category, status=status)
            db.add(db_item)
            db.commit()
            db.refresh(db_item)
            # return templates.TemplateResponse("link_indicate_00.html", {"request": request,  "dates": date_sequence, "today": today_date, "time_zone": time_zone,    "login_username": login_username, })
            # return templates.TemplateResponse("link_indicate_00.html", {"request": request, "df_combined": df_combined_dict, "dates": date_sequence, "today": today_date, "time_zone": time_zone, "length_df_combined": length_df_combined, "time_zone_massage": time_zone_massage, "message_color": message_color, "login_username": login_username, "tab_page_active": tab_page_active, "link_tab_page_active": link_tab_page_active, "name_items": name_items})
            # return RedirectResponse(f"/schedule/update_task/{item_id}", status_code=303)
            return RedirectResponse("/schedule/", status_code=303)
            
    else:
        raise HTTPException(status_code=404, detail="Item not found")

# --------------------

@app.post("/schedule/delete_task/")
async def delete_item(item_id: int = Form(...), db: Session = Depends(get_db)):
    db_item = db.query(Schedule).filter(Schedule.id == item_id).first()
    if db_item:
        db.delete(db_item)
        db.commit()
    return RedirectResponse("/schedule/", status_code=303)

# --------------------
    
@app.post("/schedule/up/")
# @app.get("/schedule/up/")
async def schedule_up(request: Request):
    
    test_date = request.session.get('start_date_adjust')
    test_date = test_date - 7
    request.session['start_date_adjust'] = test_date
    test_date = request.session.get('start_date_adjust')
    
    print(test_date)
    

    return RedirectResponse("/schedule/", status_code=303)

# --------------------


@app.post("/schedule/down/")
# @app.get("/schedule/down/")
async def schedule_up(request: Request):
    
    test_date = request.session.get('start_date_adjust')
    test_date = test_date + 7
    request.session['start_date_adjust'] = test_date
    test_date = request.session.get('start_date_adjust')
    
    print(test_date)
    

    return RedirectResponse("/schedule/", status_code=303)

# --------------------
@app.get("/link_001/")
async def get_tasks(request: Request, time_zone: str = "UTC", db: Session = Depends(get_db), date_sequence = date_sequence, today_date = today_date):  

    link_tab_page_active = "link_001"
    request.session['link_tab_page_active'] = link_tab_page_active
    return RedirectResponse("/link_00/", status_code=303)
    
@app.get("/link_002/")
async def get_tasks(request: Request, time_zone: str = "UTC", db: Session = Depends(get_db), date_sequence = date_sequence, today_date = today_date):  

    link_tab_page_active = "link_002"
    request.session['link_tab_page_active'] = link_tab_page_active
    
    
    return RedirectResponse("/link_00/", status_code=303)






@app.get("/link_00/")
async def get_tasks(request: Request, time_zone: str = "UTC", db: Session = Depends(get_db), date_sequence = date_sequence, today_date = today_date):  
# async def get_tasks(request: Request, db: Session = Depends(get_db), date_sequence = date_sequence, today_date = today_date):
# async def get_tasks(request: Request, db: Session = Depends(get_db), date_sequence = date_sequence, today_date = today_date, login_username = login_username):
    # global local_time_zone
    # global active_meeting
    login_username = request.session.get('login_username')
    time_zone = request.session.get('time_zone')
    print(f"time_zone is {time_zone}")
    
    # tasks = db.query(Meeting).order_by(Meeting.name).all()
    tasks = db.query(Link).order_by(Link.id).all()
    
    name_items = ["Intra Net", 'Sharepoint', 'Estimation Server', 'Authrities/consultants', 'Sub-contractors/Suppliers', 'Options', 'Others', 'SIN', 'BKK', 'MLY', 'MNL','JKT', 'CHN', 'HK', 'TWN', 'VNM', 'IND', 'BGD', 'ZAM', 'GUM', 'DJI']
    # users = db.query(User).order_by(User.start_datetime).all()
    
    data = [{
    'id': task.id,
    'name': task.name,
    # 'start_datetime': task.start_datetime,
    # 'end_datetime': task.end_datetime,
    'link': task.url,
    'category': task.category,
    'status': task.status,
    'id_user': task.id_user
    } for task in tasks]

    # df_tasks = pd.DataFrame(data)
    # print(tasks.start_datetime)
    
    
    df_tasks = pd.DataFrame(data)
    print("df_tasks", df_tasks)
    # print(df_tasks)
    
   

    
    df_combined = df_tasks
    # df_combined = pd.concat([df_tasks, df_local_start_dates, df_local_start_times, df_local_end_dates, df_local_end_times], axis=1)
    # request.session['df_combined'] = df_combined  # Save to session
    print("df_combined", df_combined)
    
    
    df_combined_dict = df_combined.to_dict(orient='records')
    
    length_df_combined = len(df_combined)
    
    time_zone_massage = "Current time zone :"
    
    message_color = "#0f0"
    
    print("df_combined", df_combined)
    
    tab_page_active = "link_00"
    # request.session['link_tab_page_active'] = link_tab_page_active
    link_tab_page_active = request.session.get('link_tab_page_active')
    
    
    
    
    
    return templates.TemplateResponse("link_indicate_00.html", {"request": request, "df_combined": df_combined_dict, "dates": date_sequence, "today": today_date, "time_zone": time_zone, "length_df_combined": length_df_combined, "time_zone_massage": time_zone_massage, "message_color": message_color, "login_username": login_username, "tab_page_active": tab_page_active, "link_tab_page_active": link_tab_page_active, "name_items": name_items})
    # return templates.TemplateResponse("schedule_indicate_00.html", {"request": request, "df_combined": df_combined_dict, "dates": date_sequence, "today": today_date, "time_zone": time_zone, "length_df_combined": length_df_combined, "local_start_date": local_start_date,"local_start_time": local_start_time, "time_zone_massage": time_zone_massage, "message_color": message_color, "login_username": login_username, "tab_page_active": tab_page_active})
# --------------------
@app.post("/link/add_task_01/")

# async def create_item(name: str = Form(...), date1: str = Form(...), link: str = Form(...), tel: str = Form(...), db: Session = Depends(get_db)):
# async def create_item(name: str = Form(...), date1: date1 = Form(...), link: str = Form(...), tel: str = Form(...), db: Session = Depends(get_db)):
async def create_item(request: Request, name: str = Form(...), link: str = Form(None), category: str = Form(None), status: str = Form(None), username: str = Form(None), time_zone: str = Form(None), db: Session = Depends(get_db)):
# async def create_item(request: Request, name: str = Form(...), link: str = Form(None), category: str = Form(None), status: str = Form(None), username: str = Form(None), time_zone: str = Form(None), db: Session = Depends(get_db)):
# async def create_item(request: Request, name: str = Form(...), date1: str = Form(...), start_time: str = Form(...), end_time: str = Form(...), link: str = Form(None), category: str = Form(None), status: str = Form(None), username: str = Form(None), local_time_zone = local_time_zone, db: Session = Depends(get_db)):
  
    # global active_meeting
    # date1 = date1.date()
# Assuming date1 is a string in the format 'YYYY-MM-DD'
    # date1 = datetime.strptime(date1, '%Y-%m-%d').date()
    
    # print("test")
    print(f"{time_zone} @ link/add_task")
    # local_time_zone = "Asia/Singapore"
    
   
    
    
    db_item = Link(name=name, url=link, category=category, status=status)
    # db_item = Schedule(name=name, start_datetime=utc_start_datetime_without_tz, end_datetime=utc_end_datetime_without_tz, link=link, category=category, status=status)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return RedirectResponse("/link_00/", status_code=303)

@app.get("/link/edit_task/{item_id}")
# @app.get("/tab_00/edit_task/{item_id}")
async def edit_task(item_id: int, request: Request, db: Session = Depends(get_db), date_sequence = date_sequence, today_date = today_date, link: str = Query(None)):
# async def edit_task(item_id: int, request: Request, db: Session = Depends(get_db), date_sequence = date_sequence, today_date = today_date, local_start_date_selected: str = Query(None)):
# async def edit_task(item_id: int, request: Request, db: Session = Depends(get_db), date_sequence = date_sequence, today_date = today_date, login_username: Optional[str] = None, local_start_date: str = Query(None, description="The date to edit the task")):
    db_item = db.query(Link).filter(Link.id == item_id).first()
    tasks = db.query(Link).order_by(Link.id).all()
    
    # tasks = db.query(Schedule).all()
    
    login_username = request.session.get('login_username')# login_username
    time_zone = request.session.get('time_zone')# login_username
    # df_combined = request.session.get('df_combined')# login_username
    print("user :", login_username)
    print("time_zone :", time_zone)

    
    # print("local_end_date", local_end_date)
    # print(type(local_start_date_selected))
    # start_date_selected = db_item.start_datetime.date()
    
    data = [{
    'id': task.id,
    'name': task.name,
    'url': task.url,
    'category': task.category,
    'status': task.status,
    'id_user': task.id_user
    } for task in tasks]

    # df_tasks = pd.DataFrame(data)
    # print(tasks.start_datetime)
    
    
    df_tasks = pd.DataFrame(data)
    
    df_combined = df_tasks
    
    df_combined_dict = df_combined.to_dict(orient='records')
    
    link_tab_page_active = request.session.get('link_tab_page_active')
    
    

    
    if db_item:
        return templates.TemplateResponse("link_edit_00.html", {"request": request, "df_combined": df_combined_dict, "item": db_item, "dates": date_sequence, "today": today_date, "time_zone": time_zone, "login_username": login_username, "link_tab_page_active": link_tab_page_active})
        # return templates.TemplateResponse("schedule_edit_00.html", {"request": request, "time_zone": time_zone, "item": db_item, "tasks": tasks, "dates": date_sequence, "today": today_date, "local_start_date": local_start_date, "local_start_time": local_start_time, "local_end_time": local_end_time, "login_username": login_username})
        # return templates.TemplateResponse("schedule_indicate_00.html", {"request": request, "df_combined": df_combined_dict, "dates": date_sequence, "today": today_date, "time_zone": time_zone, "length_df_combined": length_df_combined, "local_start_time": local_start_time, "time_zone_massage": time_zone_massage, "message_color": message_color, "login_username": login_username})
    
        # return templates.TemplateResponse("edit_00.html", {"request": request, "item": db_item, "tasks": tasks, "dates": date_sequence, "today": today_date, "local_start_date": local_start_date, "local_start_time": local_start_time, "local_end_time": local_end_time, login_username: login_username})
        # return templates.TemplateResponse("index_00.html", {"request": request, "item": db_item})
    else:
        raise HTTPException(status_code=404, detail="Item not found")
    
    
@app.post("/link/update_task/{item_id}")

async def create_item(request: Request, item_id: int, name: str = Form(...), link: str = Form(None), category: str = Form(None), status: str = Form(None), username: str = Form(None), time_zone: str = Form(None), db: Session = Depends(get_db)):


    # date1 = datetime.strptime(date1, '%Y-%m-%d').date()
    login_username = request.session.get('login_username')# login_username
    time_zone = request.session.get('time_zone')# login_username
    
    
    
    
    
    
    
    # end_datetime  = local_end_datetime.astimezone(ZoneInfo(time_zone))

    
    db_item = db.query(Link).filter(Link.id == item_id).first()
    if db_item:
        # db_item = Schedule(name=name, start_datetime=utc_start_datetime_with_tz, end_datetime=utc_end_datetime_with_tz, link=link, category=category, status=status)
        
        
        db_item.name = name
        # db_item.start_datetime = utc_start_datetime_without_tz
        # db_item.start_datetime = datetime.strptime(utc_start_datetime_without_tz.strftime("%Y-%m-%d %H:%H"), "%Y-%m-%d %H:%H")
        # db_item.end_datetime = utc_end_datetime_without_tz
        # db_item.end_datetime = datetime.strptime(utc_end_datetime_without_tz, "%Y-%m-%d %H:%H")
        db_item.link = link
        db_item.category = category
        db_item.status = status
        # db_item.end_datetime = local_end_date
        # db_item.id_user = id_user
        db.commit()
        db.refresh(db_item)
        return RedirectResponse("/link_00/", status_code=303)
    else:
        raise HTTPException(status_code=404, detail="Item not found")  
    
    
@app.post("/link/delete_task/")
async def delete_item(item_id: int = Form(...), db: Session = Depends(get_db)):
    
    print("delete!!")
    db_item = db.query(Link).filter(Link.id == item_id).first()
    if db_item:
        db.delete(db_item)
        db.commit()
    return RedirectResponse("/link_00/", status_code=303)

