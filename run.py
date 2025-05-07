from app import create_app, socketio
from requests import request
from app.database import init_db





app = create_app()


@socketio.on('connect')
def handle_connect():
    print("🟢 A client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("🔴 A client disconnected")

@app.route('/test-broadcast')
def test_broadcast():
    socketio.emit("new_message", {
        "lead_id": "1",
        "content": "📢 Real-time test",
        "timestamp": "Now"
    })
    return "Test emitted"

if __name__ == "__main__":
    socketio.run(app, debug=True,port=5005)  # Uses eventlet or gevent automatically









