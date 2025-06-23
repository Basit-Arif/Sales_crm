from flask import Blueprint,g
from app import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def get_db():
    if 'db' not in g:
        g.db = db.session
    return g.db

from app.routes.admin_dashboard import (
    dashboard,
    user,
    leads,
    companies,
    sales_rep,
    
)
