from openai import OpenAI
from PyPDF2 import PdfReader
import os
import io
import json
from dotenv import load_dotenv
from .database import get_connection
from psycopg2.extras import RealDictCursor

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_KEY"))


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text content from a PDF file"""
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    if not text.strip():
        raise ValueError("Could not extract text from the PDF. The file may be image-based or empty.")

    return text.strip()


def parse_resume_with_ai(resume_text: str) -> dict:
    """Use OpenAI GPT-4o to parse resume text into structured data"""

    prompt = f"""
    You are an expert resume parser. Extract structured data from the following resume text.

    Resume Text:
    {resume_text}

    Extract the following and return as JSON:
    {{
        "headline": "Professional title/headline (e.g. 'Software Engineer')",
        "summary": "Professional summary or objective (2-3 sentences). If not explicitly stated, write one based on the resume content.",
        "work_experiences": [
            {{
                "company": "Company name",
                "title": "Job title",
                "start_date": "YYYY-MM-DD (use first day of month if only month/year given)",
                "end_date": "YYYY-MM-DD or null if current",
                "is_current": true/false,
                "responsibilities": "Bullet points of responsibilities/achievements separated by newlines"
            }}
        ],
        "education": [
            {{
                "school": "School/University name",
                "degree": "Degree type (e.g. Bachelor of Science)",
                "field_of_study": "Major/Field or null",
                "start_date": "YYYY-MM-DD or null",
                "end_date": "YYYY-MM-DD or null",
                "gpa": "GPA string or null"
            }}
        ],
        "skills": [
            {{
                "skill_name": "Skill name",
                "proficiency": "Beginner/Intermediate/Advanced/Expert or null"
            }}
        ],
        "projects": [
            {{
                "title": "Project name",
                "description": "Project description",
                "technologies": "Comma-separated technologies or null",
                "url": "Project URL or null",
                "start_date": "YYYY-MM-DD or null",
                "end_date": "YYYY-MM-DD or null"
            }}
        ]
    }}

    Important rules:
    - Only extract information that is actually present in the resume
    - Use null for fields that are not available
    - Dates must be in YYYY-MM-DD format. If only year is given, use YYYY-01-01
    - If only month and year, use the first day of that month
    - For skills without explicit proficiency, set proficiency to null
    - Return empty arrays [] if a section is not found in the resume
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert resume parser. Always respond with valid JSON. Extract only what is present in the resume - do not fabricate information."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    parsed_data = json.loads(response.choices[0].message.content)
    return parsed_data


def save_parsed_resume_data(user_id: int, parsed_data: dict) -> dict:
    """Save AI-parsed resume data into the database tables, replacing existing data"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Clear existing profile data for this user
        cursor.execute("DELETE FROM work_experiences WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM education WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM skills WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM projects WHERE user_id = %s", (user_id,))

        # Update user headline and summary
        if parsed_data.get("headline") or parsed_data.get("summary"):
            cursor.execute("""
                UPDATE users SET headline = %s, summary = %s WHERE id = %s
            """, (
                parsed_data.get("headline"),
                parsed_data.get("summary"),
                user_id
            ))

        # Insert work experiences
        work_count = 0
        for work in parsed_data.get("work_experiences", []):
            cursor.execute("""
                INSERT INTO work_experiences (user_id, company, title, start_date, end_date, is_current, responsibilities)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                work.get("company"),
                work.get("title"),
                work.get("start_date"),
                work.get("end_date"),
                work.get("is_current", False),
                work.get("responsibilities")
            ))
            work_count += 1

        # Insert education
        edu_count = 0
        for edu in parsed_data.get("education", []):
            cursor.execute("""
                INSERT INTO education (user_id, school, degree, field_of_study, start_date, end_date, gpa)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                edu.get("school"),
                edu.get("degree"),
                edu.get("field_of_study"),
                edu.get("start_date"),
                edu.get("end_date"),
                edu.get("gpa")
            ))
            edu_count += 1

        # Insert skills
        skill_count = 0
        for skill in parsed_data.get("skills", []):
            cursor.execute("""
                INSERT INTO skills (user_id, skill_name, proficiency)
                VALUES (%s, %s, %s)
            """, (
                user_id,
                skill.get("skill_name"),
                skill.get("proficiency")
            ))
            skill_count += 1

        # Insert projects
        project_count = 0
        for proj in parsed_data.get("projects", []):
            cursor.execute("""
                INSERT INTO projects (user_id, title, description, technologies, url, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                proj.get("title"),
                proj.get("description"),
                proj.get("technologies"),
                proj.get("url"),
                proj.get("start_date"),
                proj.get("end_date")
            ))
            project_count += 1

        conn.commit()

        return {
            "work_experiences_added": work_count,
            "education_added": edu_count,
            "skills_added": skill_count,
            "projects_added": project_count
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
