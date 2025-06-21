from app import create_app, socketio ,db
from app.celery_app import make_celery
 # Don't import `app` here
from app.database import init_db
from flask_socketio import join_room, leave_room
from flask import session
from flask_migrate import Migrate
from app.services.helper_function import send_reset_email

app = create_app()


migrate = Migrate(app, init_db)
make_celery(app=app)


@socketio.on('connect')
def handle_connect():
    print("🟢 A client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("🔴 A client disconnected")

@app.route('/test-broadcast')
def test_broadcast():
    user_id = session.get("user_id")
    room = f"user_{user_id}"
    socketio.emit("new_message", {
        "lead_id": "1",
        "content": "📢 Real-time test",
        "timestamp": "Now"
    }, to=room)
    return f"Test emitted from server to room {room}"

@socketio.on('join_room')
def handle_join_room(data):
    requested_id = int(data.get("user_id"))
    actual_id = session.get("user_id")


    if actual_id != requested_id:
        print(f"🚫 Unauthorized room join attempt: session {actual_id} tried to join user_{requested_id}")
        return

    room = f"user_{actual_id}"
    join_room(room)
    print(f"✅ User {actual_id} joined room {room}")

@app.route('/test-mail')
def test_mail():
    send_reset_email("basitarif235@gmail.com", "http://dummy-link.com/reset")
    return "✅ Mail sent if configuration is correct"

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    port = int(os.getenv("PORT", 5005))
    socketio.run(app, debug=True,host="0.0.0.0",port=port)