from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session,current_app,jsonify
from app.models import db
from app import socketio

user_bp=Blueprint("user",__name__,url_prefix="/user")

from app.routes.user_dashboard import (
    dashboard,
    messages,
    user,
    leads,
    meeting,
    notifications,
    lead_comments,

)