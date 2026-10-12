from sqlalchemy import create_engine
from database import base

DATABASE_URL = "postgresql://office:officed@localhost:5432/office_booking"

engine = create_engine(DATABASE_URL)

base.metadata.create_all(bind=engine)
print("Таблицы созданы")