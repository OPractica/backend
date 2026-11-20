from sqlalchemy import create_engine

from app.core.config import settings
from app.models.database import base

engine = create_engine(settings.database_url)

base.metadata.create_all(bind=engine)
print("Таблицы созданы")
