import re
import os

SKILL_DICTIONARY = [
    "python", "java", "c++", "sql", "mysql", "postgresql", "sqlite",
    "html", "css", "javascript", "flask", "django", "rest api", "api",
    "scikit-learn", "machine learning", "data analysis", "excel",
    "networking", "tcp/ip", "vlan", "routing", "switching", "linux",
    "windows server", "cybersecurity", "cloud computing", "aws", "azure",
    "docker", "git", "github", "communication", "troubleshooting",
    "pandas", "numpy", "statistics", "power bi", "tableau"
]

def allowed_pdf(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"

def extract_pdf_text(path):
    """Extract text from a text-based PDF using PyMuPDF."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is missing. Run: pip install -r requirements.txt") from exc
    try:
        document = fitz.open(path)
        try:
            if document.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported.")
            text = "\n".join(page.get_text("text") for page in document)
        finally:
            document.close()
    except Exception as exc:
        raise ValueError("PDF could not be opened or parsed.") from exc
    return normalize_text(text)

def normalize_text(text):
    text = (text or "").lower()
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()

def extract_skills(text):
    normalized = normalize_text(text)
    found = []
    for skill in SKILL_DICTIONARY:
        pattern = r"(?<![a-z0-9+#])" + re.escape(skill.lower()) + r"(?![a-z0-9+#])"
        if re.search(pattern, normalized):
            found.append(skill)
    return sorted(set(found), key=str.lower)

def analyze_resume(resume_text, job_text):
    """Explainable score: 70% skill overlap + 30% TF-IDF text similarity.
    If scikit-learn is unavailable or either text is empty, text similarity falls back to 0.
    This is a compatibility indicator, not a hiring probability.
    """
    resume_skills = set(extract_skills(resume_text))
    job_skills = set(extract_skills(job_text))
    matched = sorted(resume_skills & job_skills, key=str.lower)
    missing = sorted(job_skills - resume_skills, key=str.lower)
    skill_score = (len(matched) / len(job_skills) * 100) if job_skills else 0.0
    text_score = 0.0
    if (resume_text or "").strip() and (job_text or "").strip():
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            matrix = TfidfVectorizer(stop_words="english").fit_transform([resume_text, job_text])
            text_score = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0] * 100)
        except (ImportError, ValueError):
            text_score = 0.0
    score = round(max(0.0, min(100.0, skill_score * 0.70 + text_score * 0.30)), 1)
    if matched:
        explanation = "Matched skills: " + ", ".join(matched) + "."
    else:
        explanation = "No skills from the configured dictionary matched this job yet."
    if missing:
        explanation += " Skills to consider learning: " + ", ".join(missing) + "."
    explanation += f" Score combines 70% skill overlap and 30% text similarity (skill component {skill_score:.1f}%, text component {text_score:.1f}%)."
    return {"score": score, "matched": matched, "missing": missing,
            "skill_score": round(skill_score, 1), "text_score": round(text_score, 1),
            "resume_skills": sorted(resume_skills, key=str.lower), "job_skills": sorted(job_skills, key=str.lower),
            "explanation": explanation}
