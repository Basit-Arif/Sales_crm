from . import admin_bp
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from app.models.models import Company, User, SalesRep, Lead
from werkzeug.security import check_password_hash
from app.routes.admin_dashboard import get_db


@admin_bp.route("/companies")
def list_companies():
    db = get_db()
    try:
        companies = db.query(Company).all()
        return render_template("admin/companies.html", companies=companies)
    finally:
        db.close()


@admin_bp.route("/companies/add", methods=["GET", "POST"])
def add_company():
    db = get_db()
    try:
        if request.method == "POST":
            name = request.form.get("name")
            messenger_page_id = request.form.get("messenger_page_id")
            messenger_access_token = request.form.get("messenger_access_token")
            instagram_page_id = request.form.get("instagram_page_id")
            instagram_access_token = request.form.get("instagram_access_token")

            company = Company(
                name=name,
                messenger_page_id=messenger_page_id,
                messenger_access_token=messenger_access_token,
                instagram_page_id=instagram_page_id,
                instagram_access_token=instagram_access_token
            )
            db.add(company)
            db.commit()
            flash("✅ Company added successfully.", "success")
            return redirect(url_for("admin.list_companies"))

        return render_template("admin/add_company.html")
    finally:
        db.close()


@admin_bp.route("/companies/edit/<int:company_id>", methods=["GET", "POST"])
def edit_company(company_id):
    db = get_db()
    try:
        company = db.query(Company).filter_by(id=company_id).first()
        if not company:
            flash("❌ Company not found.", "danger")
            return redirect(url_for("admin.list_companies"))

        if request.method == "POST":
            if request.is_json:
                data = request.get_json()
                company.name = data.get("name")
                company.messenger_page_id = data.get("messenger_page_id")
                company.messenger_access_token = data.get("messenger_access_token")
                company.instagram_page_id = data.get("instagram_page_id")
                company.instagram_access_token = data.get("instagram_access_token")
                db.commit()
                return jsonify({"message": "✅ Company updated successfully."}), 200
            company.name = request.form.get("name")
            company.messenger_page_id = request.form.get("messenger_page_id")
            company.messenger_access_token = request.form.get("messenger_access_token")
            company.instagram_page_id = request.form.get("instagram_page_id")
            company.instagram_access_token = request.form.get("instagram_access_token")
            db.commit()
            flash("✅ Company updated successfully.", "success")
            return redirect(url_for("admin.list_companies"))

        return jsonify({
            "id": company.id,
            "name": company.name,
            "messenger_page_id": company.messenger_page_id,
            "messenger_access_token": company.messenger_access_token,
            "instagram_page_id": company.instagram_page_id,
            "instagram_access_token": company.instagram_access_token
        })
    finally:
        db.close()



@admin_bp.route("/companies/delete", methods=["POST"])
def delete_company():
    db = get_db()
    try:
        company_id = request.form.get("company_id")
        admin_password = request.form.get("admin_password")

        # Get current logged-in admin
        current_user_id = session.get("user_id")
        user = db.query(User).filter_by(id=current_user_id, is_admin=True).first()
        print("this is user ")
        print(user)

        if not user or not check_password_hash(user.password, admin_password):
            flash("❌ Invalid admin password.", "danger")
            return redirect(url_for("admin.list_companies"))

        # Begin transaction
        company = db.query(Company).filter_by(id=company_id).first()
        if not company:
            flash("❌ Company not found.", "danger")
            return redirect(url_for("admin.list_companies"))

        sales_reps = db.query(SalesRep).filter_by(company_id=company.id).all()

        # Unassign leads
        for rep in sales_reps:
            db.query(Lead).filter_by(sales_rep_id=rep.id).update({"sales_rep_id": None})

        # Delete sales reps
        for rep in sales_reps:
            db.delete(rep)

        # Delete the company
        db.delete(company)
        db.commit()

        flash("✅ Company and associated sales reps deleted. Leads unassigned.", "success")
        return redirect(url_for("admin.list_companies"))

    except Exception as e:
        db.rollback()
        print("❌ Error deleting company:", e)
        flash("❌ Something went wrong. Operation cancelled.", "danger")
        return redirect(url_for("admin.list_companies"))

    finally:
        db.close()


import os 
from dotenv import load_dotenv
load_dotenv()

NGROK_URL = "https://a76d-2400-adc1-149-2b00-5517-2838-b8ac-de86.ngrok-free.app"

@admin_bp.route("/companies/connect-facebook")
def connect_facebook():
    fb_login_url = (
        "https://www.facebook.com/v17.0/dialog/oauth?"
        f"client_id={os.getenv('FB_APP_ID')}"
        f"&redirect_uri={NGROK_URL}/admin/companies/facebook-callback"
        "&scope=pages_show_list,pages_manage_metadata,pages_messaging,business_management"
        "&response_type=code"
        "&state=secure_random_value"
    )
    return redirect(fb_login_url)


import requests
@admin_bp.route("/companies/facebook-callback")
def facebook_callback():
    code = request.args.get("code")
    if not code:
        flash("❌ Facebook authorization failed.", "danger")
        return redirect(url_for("admin.list_companies"))

    # Step 1: Get access token
    token_res = requests.get(
        "https://graph.facebook.com/v17.0/oauth/access_token",
        params={
            "client_id": os.getenv("FB_APP_ID"),
            "redirect_uri": url_for("admin.facebook_callback", _external=True, _scheme="https"),
            "client_secret": os.getenv("FB_APP_SECRET"),
            "code": code
        }
    )
    access_token = token_res.json().get("access_token")

    if not access_token:
        flash("❌ Failed to retrieve access token.", "danger")
        return redirect(url_for("admin.list_companies"))

    # Step 2: Get all managed pages
    page_data = requests.get(
        "https://graph.facebook.com/v17.0/me/accounts",
        params={"access_token": access_token}
    ).json()
    print("Page data:", page_data)
    pages = page_data.get("data", [])
    if not pages:
        flash("❌ No pages found for this Facebook user.", "danger")
        return redirect(url_for("admin.list_companies"))

    # Step 3: Save all pages as companies
    db = get_db()
    added = 0
    skipped = 0
    try:
        for page in pages:
            name = page["name"]
            page_id = page["id"]
            page_token = page["access_token"]

            # Step 3: Check if company with this Messenger Page already exists
            existing = db.query(Company).filter_by(messenger_page_id=page_id).first()
            if existing:
                skipped += 1
                continue

            # Step 4: Check for connected Instagram Business Account
            ig_res = requests.get(
                f"https://graph.facebook.com/v17.0/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page_token
                }
            ).json()

            instagram_id = ig_res.get("instagram_business_account", {}).get("id")
            print("instagram_id",instagram_id)

            # Step 5: Save to database
            company = Company(
                name=name,
                messenger_page_id=page_id,
                messenger_access_token=page_token,
                instagram_page_id=instagram_id if instagram_id else None,
                instagram_access_token=page_token if instagram_id else None  # optional
            )
            db.add(company)
            added += 1

        db.commit()
        flash(f"✅ {added} page(s) connected. {skipped} already existed.", "success")
    except Exception as e:
        db.rollback()
        print("❌ Error saving pages:", e)
        flash("❌ Something went wrong while saving pages.", "danger")
    finally:
        db.close()

    return redirect(url_for("admin.list_companies"))