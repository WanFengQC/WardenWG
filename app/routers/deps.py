from fastapi import Depends

from app.core.security import admin_auth_dependency
from app.db.database import get_db

AdminAuth = admin_auth_dependency()
DBSession = Depends(get_db)

