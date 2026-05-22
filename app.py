from flask import Flask, render_template, request, redirect, url_for, flash, session
import qrcode
import os
import cv2
import pandas as pd
from datetime import datetime
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Set up upload folder for files
UPLOAD_FOLDER = 'static/uploads'
QR_FOLDER = "static/qrcodes"
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif", "docx", "xlsx"}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

# Database simulation (replace with actual database in production)
users_db = {}
admins_db = {}

# Create default admin account
default_admin = {
    'name': 'Admin',
    'password': 'admin123'
}
admins_db['admin'] = default_admin

# Utility function to check if file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Login required decorators
def user_login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_email' not in session:
            flash('Please login first!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def admin_login_required(f):
    def wrapper(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Root route for login/signup page
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/user/login_page")
def user_login_page():
    return render_template("user_login.html")

@app.route("/admin/login_page")
def admin_login_page():
    return render_template("admin_login.html")

@app.route("/admin/signup_page")
def admin_signup_page():
    return render_template("admin_signup.html")

@app.route("/user/signup_page")
def user_signup_page():
    return render_template("user_signup.html")

# User authentication routes
@app.route("/user/signup", methods=["POST"])
def user_signup():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    
    if email in users_db:
        flash('Email already registered!', 'danger')
        return redirect(url_for('user_signup_page'))
    
    users_db[email] = {'name': name, 'password': password}
    flash('Registration successful! Please login.', 'success')
    return redirect(url_for('user_login_page'))

@app.route("/user/login", methods=["POST"])
def user_login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if email in users_db and users_db[email]['password'] == password:
        session['user_email'] = email
        flash('Login successful!', 'success')
        return redirect(url_for('scan_qr'))
    
    flash('Invalid credentials!', 'danger')
    return redirect(url_for('user_login_page'))

@app.route("/admin/login", methods=["POST"])
def admin_login():
    admin_id = request.form.get('admin_id')
    password = request.form.get('password')
    
    if admin_id in admins_db and admins_db[admin_id]['password'] == password:
        session['admin_id'] = admin_id
        flash('Admin login successful!', 'success')
        return redirect(url_for('generate_qr'))
    
    flash('Invalid admin credentials!', 'danger')
    return redirect(url_for('admin_login_page'))

@app.route("/admin/signup", methods=["POST"])
def admin_signup():
    name = request.form.get('name')
    admin_id = request.form.get('admin_id')
    password = request.form.get('password')

    if admin_id in admins_db:
        flash('Admin ID already taken!', 'danger')
        return redirect(url_for('admin_signup_page'))
    
    admins_db[admin_id] = {'name': name, 'password': password}
    flash('Admin registration successful! Please login.', 'success')
    return redirect(url_for('admin_login_page'))

@app.route("/logout")
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

# Generate QR Code route
# Remove or combine these two routes
@app.route("/generate", methods=["GET", "POST"])
@admin_login_required
def generate_qr():
    if request.method == "POST":
        name = request.form.get("name")
        amount = request.form.get("amount")
        fine = request.form.get("fine")  # Get fine value
        uploaded_files = request.files.getlist("upload_files")

        if not name or not amount or not fine:  # Add fine validation
            flash("Please fill in all fields!", "danger")
            return redirect(url_for("generate_qr"))

        saved_files = []
        for file in uploaded_files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)
                saved_files.append(file_path)

        # Include fine in QR data
        qr_data = {
            "name": name,
            "amount": amount,
            "fine": fine,  # Add fine to data
            "files": saved_files,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Include fine in data string
        data_str = f"Name: {name}\nAmount: {amount}\nFine: {fine}\nFiles: {','.join(saved_files)}"

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        qr_filename = f"{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        qr_path = os.path.join(QR_FOLDER, qr_filename)
        img.save(qr_path)

        flash("QR code generated successfully!", "success")
        return render_template("generate.html", qr_code=qr_path.replace('\\', '/'), user_data=qr_data)

    return render_template("generate.html", qr_code=None, user_data=None)

# Scan QR Code via webcam
@app.route("/scan", methods=["GET"])
@user_login_required
def scan_qr():
    return render_template("scan.html")

@app.route("/process_qr", methods=["POST"])
@user_login_required
def process_qr():
    try:
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            flash("Could not access the camera. Please make sure it's connected and not being used by another application.", "danger")
            return redirect(url_for("scan_qr"))
            
        detector = cv2.QRCodeDetector()
        
        # Display message to user
        flash("Camera activated. Please show QR code to the camera. Press 'q' to quit.", "info")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Try to detect and decode QR code
            data, bbox, _ = detector.detectAndDecode(frame)
            
            # If QR code is detected
            if data:
                cap.release()
                cv2.destroyAllWindows()

                # Parse QR data
                lines = data.split("\n")
                name = lines[0].split(":")[1].strip() if len(lines) > 0 and ":" in lines[0] else "Unknown"
                amount = lines[1].split(":")[1].strip() if len(lines) > 1 and ":" in lines[1] else "0"
                fine = lines[2].split(":")[1].strip() if len(lines) > 2 and ":" in lines[2] else "0"  # Parse fine
                
                # Parse files if available
                files_line = next((line for line in lines if line.startswith("Files:")), "")
                file_links = files_line.replace("Files:", "").strip().split(",") if files_line else []
                file_links = [link.strip() for link in file_links if link.strip()]

                return render_template("process.html", name=name, amount=amount, fine=fine, file_links=file_links, qr_data=data)

            # Display the frame
            cv2.imshow("QR Code Scanner", frame)
            
            # Exit on 'q' press
            if cv2.waitKey(1) == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()
        flash("No QR code detected or scanner was closed.", "warning")
        return redirect(url_for("scan_qr"))
        
    except Exception as e:
        flash(f"Error scanning QR code: {str(e)}", "danger")
        return redirect(url_for("scan_qr"))

@app.route("/mark_attendance", methods=["POST"])
@user_login_required
def mark_attendance():
    name = request.form.get("name")
    date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not name:
        flash("Invalid name data!", "danger")
        return redirect(url_for("scan_qr"))
        
    df = pd.DataFrame({"Name": [name], "DateTime": [date_time]})

    if not os.path.exists("attendance.csv"):
        df.to_csv("attendance.csv", index=False)
    else:
        df.to_csv("attendance.csv", mode="a", header=False, index=False)

    flash(f"Attendance marked for {name}!", "success")
    return redirect(url_for("attendance_sheet"))

@app.route("/attendance_sheet")
@user_login_required
def attendance_sheet():
    if not os.path.exists("attendance.csv"):
        flash("No attendance data available.", "warning")
        return redirect(url_for("scan_qr"))

    df = pd.read_csv("attendance.csv")
    return render_template("attendance.html", table=df.to_html(classes="data", index=False))

@app.route("/payment", methods=["GET", "POST"])
@user_login_required
def payment_page():
    if request.method == "GET":
        name = request.args.get("name", "Unknown")
        amount = request.args.get("amount", "0")
        fine = request.args.get("fine", "0")
        return render_template("payment.html", name=name, amount=amount, fine=fine)
    
    elif request.method == "POST":
        name = request.form.get("name")
        current_amount = float(request.form.get("amount", 0))
        fine_amount = float(request.form.get("fine", 0))
        payment_type = request.form.get("payment_type")
        
        if payment_type == "fine" and current_amount >= fine_amount:
            # Deduct fine from balance
            new_amount = current_amount - fine_amount
            flash(f"Fine payment successful! New balance: Rs. {new_amount}", "success")
            return render_template("payment.html", name=name, amount=str(new_amount), fine="0")
        
        flash("Insufficient balance or invalid payment type!", "danger")
        return render_template("payment.html", name=name, amount=str(current_amount), fine=str(fine_amount))

@app.route("/download_files", methods=["POST"])
@user_login_required
def download_files():
    file_links = request.form.getlist("file_links")
    
    if not file_links:
        flash("No files to download.", "warning")
        return redirect(url_for("scan_qr"))
    
    downloaded = []
    errors = []
    
    for path in file_links:
        try:
            if not path.strip():
                continue
                
            file_name = os.path.basename(path)
            # Create a static directory for downloads if it doesn't exist
            download_dir = os.path.join('static', 'downloads')
            os.makedirs(download_dir, exist_ok=True)
            
            dest_path = os.path.join(download_dir, file_name)
            shutil.copy(path, dest_path)
            downloaded.append(file_name)
        except Exception as e:
            errors.append(f"Failed to copy {path}: {str(e)}")
    
    if downloaded:
        flash(f"Downloaded files: {', '.join(downloaded)}", "success")
    if errors:
        for error in errors:
            flash(error, "danger")
    
    return redirect(url_for("scan_qr"))

if __name__ == "__main__":
    app.run(debug=True)