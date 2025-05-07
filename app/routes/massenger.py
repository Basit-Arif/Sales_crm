from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash


massenger_bp=Blueprint("massenger",__name__,url_prefix="/massenger")

@massenger_bp.route('/')
def index():
    return "hello this is messenger page"



