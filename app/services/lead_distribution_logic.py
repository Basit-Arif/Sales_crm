from datetime import datetime
from sqlalchemy import func
from app.models.models import SalesRep, Lead 

def get_next_sales_rep(session):
    today = datetime.utcnow().date()

    active_reps = session.query(SalesRep).filter_by(status="active", active=True).all()

    rep_lead_counts = {
        rep.id: session.query(Lead).filter(
            Lead.sales_rep_id == rep.id,
            func.date(Lead.assigned_at) == today
        ).count()
        for rep in active_reps
    }

    # Return the rep with the fewest leads today
    least_busy_id = min(rep_lead_counts, key=rep_lead_counts.get)
    return next(rep for rep in active_reps if rep.id == least_busy_id)
