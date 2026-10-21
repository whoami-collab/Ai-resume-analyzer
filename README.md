# AI-Based Resume Analyzer & Job Recommendation System

A student major-project starter application built with **HTML, CSS, Python (Flask), SQLAlchemy, and SQL**. There is no React or custom JavaScript.

## Features included

- Candidate/recruiter registration and login with password hashing
- Server-side role checks for candidate, recruiter, and admin pages
- Candidate profile and recruiter profile editing
- PDF upload validation (PDF extension, PDF signature, 5 MB maximum)
- PDF text extraction using PyMuPDF
- Configurable technical-skill dictionary
- Explainable compatibility score using 70% skill overlap + 30% TF-IDF/cosine similarity
- Job search by keyword and location
- Job detail, saved jobs, applications, and status tracking
- Recruiter job posting, editing, closing/deleting, applicant list, status updates
- Admin dashboard and role management
- Notifications
- Demo jobs and demo admin/recruiter accounts
- SQLite default database; optional MySQL configuration

> This project uses a traditional, explainable matching algorithm, not a deep-learning model. Scores are compatibility indicators, not probabilities of being hired. PDF text extraction works with text-based PDFs; scanned-image PDFs need OCR, which is not included.

## Requirements

- Python 3.10+ (Python 3.12 recommended)
- VS Code
- Internet connection for installing packages
- Optional: MySQL Server and MySQL Workbench if you want MySQL instead of SQLite

## Run in Windows / VS Code

1. Extract the ZIP file.
2. Open the `AI-Resume-Analyzer` folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

5. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this for the current terminal only, then activate again:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

6. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

7. Start the application:

   ```powershell
   python app.py
   ```

8. Open `http://127.0.0.1:5000` in your browser.

The app creates the SQLite database at `instance/resume_analyzer.db` and seeds demo jobs on first run.

## Demo accounts

- Admin: `admin@example.com` / `Admin@12345`
- Recruiter: `recruiter@example.com` / `Recruiter@123`

Create a candidate account using the registration page.

**For safety:** These demo credentials are for local development only. Change them before any public deployment. Do not expose the development server to the internet.

## Optional MySQL setup

1. Create a database and a dedicated user in MySQL:

   ```sql
   CREATE DATABASE resume_analyzer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'resume_user'@'localhost' IDENTIFIED BY 'replace_with_a_strong_password';
   GRANT ALL PRIVILEGES ON resume_analyzer.* TO 'resume_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

2. In PowerShell, set the connection string for the current terminal (replace credentials):

   ```powershell
   $env:DATABASE_URL = "mysql+pymysql://resume_user:replace_with_a_strong_password@localhost/resume_analyzer"
   ```

3. Start the app:

   ```powershell
   python app.py
   ```

Do not commit database passwords or secrets to Git. The MySQL connection string must be URL-encoded if its password contains special characters.

## Project structure

```text
AI-Resume-Analyzer/
├── app.py
├── resume_analyzer.py
├── requirements.txt
├── templates/          # HTML pages
├── static/css/         # CSS only
├── uploads/            # Uploaded PDF resumes
├── instance/           # Local SQLite database
├── .env.example
├── .gitignore
└── README.md
```

## Testing manually

1. Register a candidate and complete the profile.
2. Upload a text-based PDF resume.
3. Review extracted skills and job compatibility results.
4. Search for jobs, save one, and apply.
5. Log in as the recruiter demo account and open applicants for a job.
6. Change an application status and log back in as the candidate to see the status.
7. Log in as admin and review the dashboard/user list.

## Security and production notes

This is a local development project, not a production-hardened service. Before deployment, configure a strong `SECRET_KEY`, HTTPS, secure cookies, CSRF protection, rate limiting, private file storage, malware scanning, retention policies, logging, backups, and production server settings. The current HTML forms do not include a CSRF token library. Do not deploy publicly until these are added and reviewed.
