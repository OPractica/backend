from database import base
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://office:office@localhost:5432/office_booking"

engine = create_engine(DATABASE_URL)

base.metadata.create_all(bind=engine)
print("Таблицы созданы")
