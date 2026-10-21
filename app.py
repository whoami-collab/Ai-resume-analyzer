import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from resume_analyzer import analyze_resume, allowed_pdf

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-development-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "resume_analyzer.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="candidate")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    candidate_profile = db.relationship("CandidateProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    recruiter_profile = db.relationship("RecruiterProfile", backref="user", uselist=False, cascade="all, delete-orphan")

class CandidateProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(150), default="")
    phone = db.Column(db.String(30), default="")
    education = db.Column(db.String(200), default="")
    experience_years = db.Column(db.Float, default=0)
    summary = db.Column(db.Text, default="")

class RecruiterProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    company_name = db.Column(db.String(200), default="")
    designation = db.Column(db.String(100), default="")
    phone = db.Column(db.String(30), default="")

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(150), default="Remote")
    job_type = db.Column(db.String(50), default="Full-time")
    description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recruiter = db.relationship("User", backref="posted_jobs")

class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    extracted_text = db.Column(db.Text, default="")
    skills = db.Column(db.Text, default="")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="resumes")
    analyses = db.relationship("ResumeAnalysis", backref="resume", cascade="all, delete-orphan")

class ResumeAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resume.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=True)
    score = db.Column(db.Float, default=0)
    matched_skills = db.Column(db.Text, default="")
    missing_skills = db.Column(db.Text, default="")
    explanation = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    job = db.relationship("Job")

class JobApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey("resume.id"), nullable=True)
    status = db.Column(db.String(30), default="Submitted")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    candidate = db.relationship("User", foreign_keys=[candidate_id], backref="applications")
    job = db.relationship("Job", backref="applications")
    resume = db.relationship("Resume")

class SavedJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    job = db.relationship("Job")
    __table_args__ = (db.UniqueConstraint("user_id", "job_id", name="unique_saved_job"),)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

def notify(user_id, message):
    db.session.add(Notification(user_id=user_id, message=message))

@app.route("/")
def index():
    jobs = Job.query.filter_by(status="active").order_by(Job.created_at.desc()).limit(6).all()
    return render_template("index.html", jobs=jobs)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "candidate")
        if role not in ("candidate", "recruiter"):
            role = "candidate"
        if len(username) < 3 or len(password) < 8 or "@" not in email:
            flash("Enter a username (3+ characters), valid email and password (8+ characters).", "danger")
            return render_template("register.html")
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "danger")
            return render_template("register.html")
        user = User(username=username, email=email, password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.flush()
        if role == "candidate":
            db.session.add(CandidateProfile(user_id=user.id))
        else:
            db.session.add(RecruiterProfile(user_id=user.id))
        db.session.commit()
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter((db.func.lower(User.email) == identity) | (db.func.lower(User.username) == identity)).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username/email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if user.role == "recruiter":
        return redirect(url_for("recruiter_dashboard"))
    profile = user.candidate_profile
    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).all()
    applications = JobApplication.query.filter_by(candidate_id=user.id).order_by(JobApplication.created_at.desc()).all()
    recommendations = []
    latest_resume = resumes[0] if resumes else None
    if latest_resume:
        for job in Job.query.filter_by(status="active").all():
            result = analyze_resume(latest_resume.extracted_text, job.required_skills + " " + job.description)
            recommendations.append((job, result))
        recommendations.sort(key=lambda pair: pair[1]["score"], reverse=True)
        recommendations = recommendations[:4]
    return render_template("candidate_dashboard.html", profile=profile, resumes=resumes,
                           applications=applications, recommendations=recommendations)

@app.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("candidate", "recruiter")
def profile():
    user = current_user()
    if user.role == "candidate":
        p = user.candidate_profile
        if request.method == "POST":
            p.full_name = request.form.get("full_name", "").strip()
            p.phone = request.form.get("phone", "").strip()
            p.education = request.form.get("education", "").strip()
            try:
                p.experience_years = max(0, float(request.form.get("experience_years", "0") or 0))
            except ValueError:
                p.experience_years = 0
            p.summary = request.form.get("summary", "").strip()
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
        return render_template("candidate_profile.html", profile=p)
    p = user.recruiter_profile
    if request.method == "POST":
        p.company_name = request.form.get("company_name", "").strip()
        p.designation = request.form.get("designation", "").strip()
        p.phone = request.form.get("phone", "").strip()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    return render_template("recruiter_profile.html", profile=p)

@app.route("/resume/upload", methods=["GET", "POST"])
@login_required
@role_required("candidate")
def upload_resume():
    if request.method == "POST":
        file = request.files.get("resume")
        if not file or not file.filename:
            flash("Choose a PDF file.", "danger")
            return redirect(url_for("upload_resume"))
        if not allowed_pdf(file.filename):
            flash("Only PDF files are accepted.", "danger")
            return redirect(url_for("upload_resume"))
        original = secure_filename(file.filename)
        stored = f"user{current_user().id}_{int(datetime.utcnow().timestamp())}_{original}"
        path = os.path.join(app.config["UPLOAD_FOLDER"], stored)
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file.save(path)
        try:
            with open(path, "rb") as f:
                header = f.read(5)
            if header != b"%PDF-":
                os.remove(path)
                flash("The file does not appear to be a valid PDF.", "danger")
                return redirect(url_for("upload_resume"))
            text, skills = extract_resume(path)
            if not text.strip():
                os.remove(path)
                flash("No readable text was found. Please upload a text-based PDF.", "danger")
                return redirect(url_for("upload_resume"))
        except Exception as exc:
            if os.path.exists(path):
                os.remove(path)
            flash(f"Could not read this PDF: {str(exc)[:120]}", "danger")
            return redirect(url_for("upload_resume"))
        resume = Resume(user_id=current_user().id, original_filename=original,
                        stored_filename=stored, extracted_text=text[:50000], skills=", ".join(skills))
        db.session.add(resume)
        db.session.commit()
        flash("Resume uploaded and analyzed successfully.", "success")
        return redirect(url_for("analysis", resume_id=resume.id))
    return render_template("upload_resume.html")

def extract_resume(path):
    from resume_analyzer import extract_pdf_text, extract_skills
    text = extract_pdf_text(path)
    return text, extract_skills(text)

@app.route("/analysis/<int:resume_id>")
@login_required
@role_required("candidate")
def analysis(resume_id):
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user().id).first_or_404()
    jobs = Job.query.filter_by(status="active").all()
    results = []
    for job in jobs:
        result = analyze_resume(resume.extracted_text, job.required_skills + " " + job.description)
        analysis_row = ResumeAnalysis(resume_id=resume.id, job_id=job.id, score=result["score"],
                                      matched_skills=", ".join(result["matched"]),
                                      missing_skills=", ".join(result["missing"]),
                                      explanation=result["explanation"])
        db.session.add(analysis_row)
        results.append((job, result))
    db.session.commit()
    results.sort(key=lambda pair: pair[1]["score"], reverse=True)
    return render_template("analysis.html", resume=resume, results=results)

@app.route("/jobs")
def jobs():
    q = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    query = Job.query.filter_by(status="active")
    if q:
        like = f"%{q}%"
        query = query.filter((Job.title.ilike(like)) | (Job.company.ilike(like)) | (Job.required_skills.ilike(like)) | (Job.description.ilike(like)))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    listings = query.order_by(Job.created_at.desc()).all()
    return render_template("jobs.html", jobs=listings, q=q, location=location)

@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = Job.query.filter_by(id=job_id, status="active").first_or_404()
    applied = False
    saved = False
    user = current_user()
    if user and user.role == "candidate":
        applied = JobApplication.query.filter_by(candidate_id=user.id, job_id=job.id).first() is not None
        saved = SavedJob.query.filter_by(user_id=user.id, job_id=job.id).first() is not None
    score_result = None
    if user and user.role == "candidate" and user.resumes:
        resume = sorted(user.resumes, key=lambda r: r.uploaded_at, reverse=True)[0]
        score_result = analyze_resume(resume.extracted_text, job.required_skills + " " + job.description)
    return render_template("job_detail.html", job=job, applied=applied, saved=saved, score_result=score_result)

@app.route("/jobs/<int:job_id>/apply", methods=["POST"])
@login_required
@role_required("candidate")
def apply_job(job_id):
    job = Job.query.filter_by(id=job_id, status="active").first_or_404()
    if JobApplication.query.filter_by(candidate_id=current_user().id, job_id=job.id).first():
        flash("You have already applied for this job.", "info")
    else:
        resume = Resume.query.filter_by(user_id=current_user().id).order_by(Resume.uploaded_at.desc()).first()
        app_row = JobApplication(candidate_id=current_user().id, job_id=job.id, resume_id=resume.id if resume else None)
        db.session.add(app_row)
        notify(job.recruiter_id, f"New application received for {job.title}.")
        db.session.commit()
        flash("Application submitted.", "success")
    return redirect(url_for("job_detail", job_id=job.id))

@app.route("/jobs/<int:job_id>/save", methods=["POST"])
@login_required
@role_required("candidate")
def save_job(job_id):
    job = Job.query.filter_by(id=job_id, status="active").first_or_404()
    if not SavedJob.query.filter_by(user_id=current_user().id, job_id=job.id).first():
        db.session.add(SavedJob(user_id=current_user().id, job_id=job.id))
        db.session.commit()
        flash("Job saved.", "success")
    else:
        flash("This job is already saved.", "info")
    return redirect(url_for("job_detail", job_id=job.id))

@app.route("/saved-jobs")
@login_required
@role_required("candidate")
def saved_jobs():
    saved = SavedJob.query.filter_by(user_id=current_user().id).order_by(SavedJob.created_at.desc()).all()
    return render_template("saved_jobs.html", saved=saved)

@app.route("/applications")
@login_required
@role_required("candidate")
def my_applications():
    applications = JobApplication.query.filter_by(candidate_id=current_user().id).order_by(JobApplication.created_at.desc()).all()
    return render_template("applications.html", applications=applications)

@app.route("/recruiter")
@login_required
@role_required("recruiter")
def recruiter_dashboard():
    user = current_user()
    my_jobs = Job.query.filter_by(recruiter_id=user.id).order_by(Job.created_at.desc()).all()
    total_apps = JobApplication.query.join(Job).filter(Job.recruiter_id == user.id).count()
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(8).all()
    return render_template("recruiter_dashboard.html", jobs=my_jobs, total_apps=total_apps, notifications=notifications)

@app.route("/recruiter/jobs/new", methods=["GET", "POST"])
@login_required
@role_required("recruiter")
def create_job():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        description = request.form.get("description", "").strip()
        skills = request.form.get("required_skills", "").strip()
        if not all([title, company, description, skills]):
            flash("Please complete all required fields.", "danger")
            return render_template("job_form.html", job=None)
        job = Job(recruiter_id=current_user().id, title=title, company=company,
                  location=request.form.get("location", "Remote").strip(),
                  job_type=request.form.get("job_type", "Full-time"),
                  description=description, required_skills=skills)
        db.session.add(job)
        db.session.commit()
        flash("Job published.", "success")
        return redirect(url_for("recruiter_dashboard"))
    return render_template("job_form.html", job=None)

@app.route("/recruiter/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("recruiter")
def edit_job(job_id):
    job = Job.query.filter_by(id=job_id, recruiter_id=current_user().id).first_or_404()
    if request.method == "POST":
        job.title = request.form.get("title", "").strip()
        job.company = request.form.get("company", "").strip()
        job.location = request.form.get("location", "").strip()
        job.job_type = request.form.get("job_type", "Full-time")
        job.description = request.form.get("description", "").strip()
        job.required_skills = request.form.get("required_skills", "").strip()
        job.status = request.form.get("status", "active")
        if job.status not in ("active", "closed"):
            job.status = "active"
        db.session.commit()
        flash("Job updated.", "success")
        return redirect(url_for("recruiter_dashboard"))
    return render_template("job_form.html", job=job)

@app.route("/recruiter/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
@role_required("recruiter")
def delete_job(job_id):
    job = Job.query.filter_by(id=job_id, recruiter_id=current_user().id).first_or_404()
    if job.applications:
        job.status = "closed"
        flash("Job closed because it has applications.", "info")
    else:
        db.session.delete(job)
        flash("Job deleted.", "success")
    db.session.commit()
    return redirect(url_for("recruiter_dashboard"))

@app.route("/recruiter/jobs/<int:job_id>/applicants")
@login_required
@role_required("recruiter")
def applicants(job_id):
    job = Job.query.filter_by(id=job_id, recruiter_id=current_user().id).first_or_404()
    applications = JobApplication.query.filter_by(job_id=job.id).order_by(JobApplication.created_at.desc()).all()
    return render_template("applicants.html", job=job, applications=applications)

@app.route("/applications/<int:application_id>/status", methods=["POST"])
@login_required
@role_required("recruiter")
def update_application(application_id):
    application = JobApplication.query.get_or_404(application_id)
    if application.job.recruiter_id != current_user().id:
        abort(403)
    status = request.form.get("status", "Submitted")
    if status not in ("Submitted", "Under Review", "Shortlisted", "Rejected", "Hired"):
        abort(400)
    application.status = status
    notify(application.candidate_id, f"Your application for {application.job.title} is now: {status}.")
    db.session.commit()
    flash("Application status updated.", "success")
    return redirect(url_for("applicants", job_id=application.job_id))

@app.route("/notifications")
@login_required
def notifications():
    rows = Notification.query.filter_by(user_id=current_user().id).order_by(Notification.created_at.desc()).all()
    for row in rows:
        row.is_read = True
    db.session.commit()
    return render_template("notifications.html", notifications=rows)

@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html",
        users=User.query.count(), candidates=User.query.filter_by(role="candidate").count(),
        recruiters=User.query.filter_by(role="recruiter").count(), jobs=Job.query.count(),
        applications=JobApplication.query.count(), recent_users=User.query.order_by(User.created_at.desc()).limit(10).all(),
        recent_jobs=Job.query.order_by(Job.created_at.desc()).limit(10).all())

@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
@role_required("admin")
def admin_change_role(user_id):
    user = User.query.get_or_404(user_id)
    role = request.form.get("role")
    if user.id == current_user().id:
        flash("You cannot change your own role.", "danger")
    elif role not in ("candidate", "recruiter", "admin"):
        flash("Invalid role.", "danger")
    else:
        user.role = role
        if role == "candidate" and not user.candidate_profile:
            db.session.add(CandidateProfile(user_id=user.id))
        if role == "recruiter" and not user.recruiter_profile:
            db.session.add(RecruiterProfile(user_id=user.id))
        db.session.commit()
        flash("User role updated.", "success")
    return redirect(url_for("admin_users"))

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        flash("Thanks for your message. This demo stores no contact details yet.", "info")
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to access this page."), 403

@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The page or record could not be found."), 404

@app.errorhandler(413)
def too_large(_error):
    return render_template("error.html", code=413, message="File is too large. Maximum upload size is 5 MB."), 413

def seed_demo_data():
    if not Job.query.first():
        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin = User(username="admin", email="admin@example.com",
                         password_hash=generate_password_hash("Admin@12345"), role="admin")
            db.session.add(admin)
        recruiter = User.query.filter_by(username="demo_recruiter").first()
        if not recruiter:
            recruiter = User(username="demo_recruiter", email="recruiter@example.com",
                             password_hash=generate_password_hash("Recruiter@123"), role="recruiter")
            db.session.add(recruiter)
            db.session.flush()
            db.session.add(RecruiterProfile(user_id=recruiter.id, company_name="Demo Tech Solutions", designation="Talent Acquisition"))
        db.session.flush()
        jobs_seed = [
            Job(recruiter_id=recruiter.id, title="Python Developer Intern", company="Demo Tech Solutions",
                location="Pune / Hybrid", job_type="Internship",
                description="Build Python web applications, integrate REST APIs, write SQL queries and collaborate with a product team.",
                required_skills="Python, Flask, SQL, HTML, CSS, REST API"),
            Job(recruiter_id=recruiter.id, title="Junior Network Engineer", company="Demo Tech Solutions",
                location="Mumbai", job_type="Full-time",
                description="Support LAN/WAN operations, troubleshoot TCP/IP, configure VLANs and document network incidents. Linux knowledge is useful.",
                required_skills="Networking, TCP/IP, VLAN, Linux, Troubleshooting"),
            Job(recruiter_id=recruiter.id, title="Junior Data Analyst", company="Demo Tech Solutions",
                location="Remote", job_type="Full-time",
                description="Prepare reports, clean data, write SQL queries and communicate insights to stakeholders.",
                required_skills="SQL, Python, Excel, Data Analysis, Communication")
        ]
        db.session.add_all(jobs_seed)
    db.session.commit()

if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    with app.app_context():
        db.create_all()
        seed_demo_data()
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
