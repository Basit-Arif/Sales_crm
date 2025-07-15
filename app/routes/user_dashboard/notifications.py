from flask import Blueprint, jsonify, session
from app.models.models import Notification, Lead, SalesRep, LeadMessage
from app.models import db
from app.routes.user_dashboard import user_bp
from app.routes.auth import login_required
from sqlalchemy.orm import joinedload

@user_bp.route('/notifications/mark_read', methods=['POST'])
@login_required
def mark_notifications_read():
    session_db = db.session
    try:
       
        user_id = session.get("user_id") 

        notifications = session_db.query(Notification).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            Notification.is_read == False
        ).all()

        for notif in notifications:
            notif.is_read = True

        session_db.commit()
        return jsonify(success=True)
    except Exception as e:
        session_db.rollback()
        print("Error in mark_notifications_read:", e)
        return jsonify(success=False, error=str(e)), 500
    finally:
        session_db.close()

@user_bp.route("/notifications/unread")
@login_required
def unread_notifications():
    session_db = db.session
    try:
        
        user_id = session.get("user_id")

        # 🔔 Unread Notifications
        notifications = session_db.query(Notification).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            Notification.is_read == False
        ).all()

        notification_data = [
            {
                "sender_name": n.sender_name,
                "platform": n.platform,
                "time": n.created_at.strftime("%I:%M %p")
            } for n in notifications
        ]

        # 💬 Unread Messages (used for Live Messaging badge)
        messenger_msg_count = session_db.query(LeadMessage).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            LeadMessage.is_read == False,
            LeadMessage.sender == "user",
            Lead.platform == "messenger"
        ).count()

        instagram_msg_count = session_db.query(LeadMessage).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            LeadMessage.is_read == False,
            LeadMessage.sender == "user",
            Lead.platform == "instagram"
        ).count()

        return jsonify({
            "notifications": notification_data,
            "notification_count": len(notifications),
            "messenger_unread_messages": messenger_msg_count,
            "instagram_unread_messages": instagram_msg_count
        })

    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        session_db.close()


