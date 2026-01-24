#Function to fetch all user data from database
#Get user, experience, skills, education, project.

#Function to call OpenAI API with the right prompt
#Function to analyze resume match
#Function to generate tailored resume

from openai import OpenAI
import os
from dotenv import load_dotenv
from .database import get_connection
from psycopg2.extras import RealDictCursor
import json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

def get_user_resume_data(user_id: int) -> dict:
    """Fetch all user resume data from database"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get user info
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise ValueError("User not found")
        
        # Get work experiences
        cursor.execute("""
            SELECT * FROM work_experiences 
            WHERE user_id = %s 
            ORDER BY start_date DESC
        """, (user_id,))
        work_experiences = cursor.fetchall()
        
        # Get education
        cursor.execute("""
            SELECT * FROM education 
            WHERE user_id = %s 
            ORDER BY end_date DESC NULLS FIRST
        """, (user_id,))
        education = cursor.fetchall()
        
        # Get skills
        cursor.execute("""
            SELECT * FROM skills 
            WHERE user_id = %s
        """, (user_id,))
        skills = cursor.fetchall()
        
        # Get projects
        cursor.execute("""
            SELECT * FROM projects 
            WHERE user_id = %s 
            ORDER BY start_date DESC NULLS LAST
        """, (user_id,))
        projects = cursor.fetchall()
        
        return {
            "user": dict(user),
            "work_experiences": [dict(w) for w in work_experiences],
            "education": [dict(e) for e in education],
            "skills": [dict(s) for s in skills],
            "projects": [dict(p) for p in projects]
        }
        
    finally:
        cursor.close()
        conn.close()

def analyze_resume_match(user_data: dict, job_description: str) -> dict:
    """
    Analyze how well the resume matches the job description
    Returns match score and suggestions
    """
    
    # Format user data for prompt
    user_summary = f"""
    Name: {user_data['user']['name']}
    
    Summary: {user_data['user'].get('summary', 'No summary provided')}
    
    Work Experience:
    {format_work_experience(user_data['work_experiences'])}
    
    Education:
    {format_education(user_data['education'])}
    
    Skills:
    {format_skills(user_data['skills'])}
    
    Projects:
    {format_projects(user_data['projects'])}
    """
    
    prompt = f"""
    You are an expert resume consultant and ATS (Applicant Tracking System) specialist.
    
    Analyze the following resume against this job description and provide:
    1. A match score (0-100%)
    2. Key strengths (what matches well)
    3. Gaps (what's missing)
    4. Specific suggestions for improvement
    5. Keywords to add
    
    Job Description:
    {job_description}
    
    Current Resume:
    {user_summary}
    
    Provide your analysis in the following JSON format:
    {{
        "match_score": <number 0-100>,
        "strengths": ["strength 1", "strength 2", ...],
        "gaps": ["gap 1", "gap 2", ...],
        "suggestions": ["suggestion 1", "suggestion 2", ...],
        "keywords_to_add": ["keyword1", "keyword2", ...]
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert resume consultant. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        response_format={"type": "json_object"}
    )
    
    analysis = json.loads(response.choices[0].message.content)
    return analysis

def tailor_resume(user_data: dict, job_description: str, job_title: str) -> dict:
    """
    Generate tailored resume content based on job description
    Returns complete tailored resume data for document generation
    """

    user_summary = f"""
    Current Resume Data:

    Name: {user_data['user']['name']}

    Work Experience:
    {format_work_experience_with_ids(user_data['work_experiences'])}

    Education:
    {format_education(user_data['education'])}

    Skills:
    {format_skills_with_names(user_data['skills'])}

    Projects:
    {format_projects_with_ids(user_data['projects'])}
    """

    prompt = f"""
    You are an expert resume writer. Your task is to REPHRASE the user's existing resume content to be stronger and more relevant for this specific job.

    Job Title: {job_title}

    Job Description:
    {job_description}

    {user_summary}

    CRITICAL RULES - YOU MUST FOLLOW THESE:
    1. ONLY rephrase and strengthen the EXISTING content from the resume above
    2. DO NOT invent, add, or fabricate ANY new skills, experiences, achievements, or qualifications
    3. DO NOT add skills the user doesn't have - only use skills from the "Skills" section above
    4. Work experience rewrites must contain ONLY information from the original responsibilities
    5. Project descriptions must be based ONLY on the original project details
    6. Make the language more impactful using action verbs and quantifiable results WHERE THEY EXIST

    Your task:
    1. Write a professional summary (2-3 sentences) using ONLY the user's actual experience
    2. Rephrase each work experience responsibility to be more impactful (keep same facts, better wording)
    3. Rephrase each project description to highlight relevance (keep same facts, better wording)
    4. List the user's existing skills ordered by relevance to this job (NO NEW SKILLS)

    Respond in this exact JSON format:
    {{
        "tailored_summary": "A strong summary using only the user's actual background",
        "tailored_work_experiences": [
            {{
                "id": <exact id number from above>,
                "company": "company name",
                "title": "job title",
                "responsibilities": "rephrased responsibilities - use bullet points separated by newlines"
            }}
        ],
        "tailored_skills": ["existing skill 1", "existing skill 2"],
        "tailored_projects": [
            {{
                "id": <exact id number from above>,
                "title": "project title",
                "description": "rephrased description - use bullet points separated by newlines"
            }}
        ]
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert resume writer. You must ONLY rephrase existing content - never add new information. Respond with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    tailored_content = json.loads(response.choices[0].message.content)

    # Merge tailored content with original user data for complete resume generation
    return {
        "user": user_data['user'],
        "education": user_data['education'],
        "original_work_experiences": user_data['work_experiences'],
        "original_projects": user_data['projects'],
        "original_skills": user_data['skills'],
        "tailored": tailored_content
    }

# Helper formatting functions
def format_work_experience(work_experiences):
    if not work_experiences:
        return "No work experience listed"

    formatted = []
    for work in work_experiences:
        formatted.append(f"""
        - {work['title']} at {work['company']}
          {work['start_date']} to {'Present' if work['is_current'] else work['end_date']}
          {work.get('responsibilities', 'No description')}
        """)
    return "\n".join(formatted)

def format_work_experience_with_ids(work_experiences):
    """Format work experience with IDs for AI to reference"""
    if not work_experiences:
        return "No work experience listed"

    formatted = []
    for work in work_experiences:
        formatted.append(f"""
        ID: {work['id']}
        Title: {work['title']}
        Company: {work['company']}
        Dates: {work['start_date']} to {'Present' if work['is_current'] else work['end_date']}
        Responsibilities: {work.get('responsibilities', 'No description')}
        """)
    return "\n".join(formatted)

def format_skills_with_names(skills):
    """Format skills as a simple list for AI"""
    if not skills:
        return "No skills listed"

    return ", ".join([s['skill_name'] for s in skills])

def format_projects_with_ids(projects):
    """Format projects with IDs for AI to reference"""
    if not projects:
        return "No projects listed"

    formatted = []
    for proj in projects:
        formatted.append(f"""
        ID: {proj['id']}
        Title: {proj['title']}
        Description: {proj.get('description', 'No description')}
        Technologies: {proj.get('technologies', 'Not specified')}
        """)
    return "\n".join(formatted)

def format_education(education):
    if not education:
        return "No education listed"
    
    formatted = []
    for edu in education:
        formatted.append(f"""
        - {edu['degree']} {f"in {edu['field_of_study']}" if edu.get('field_of_study') else ''} from {edu['school']}
          {f"{edu['start_date']} to {edu['end_date']}" if edu.get('start_date') else ''}
          {f"GPA: {edu['gpa']}" if edu.get('gpa') else ''}
        """)
    return "\n".join(formatted)

def format_skills(skills):
    if not skills:
        return "No skills listed"
    
    return ", ".join([f"{s['skill_name']} ({s.get('proficiency', 'Not specified')})" for s in skills])

def format_projects(projects):
    if not projects:
        return "No projects listed"
    
    formatted = []
    for proj in projects:
        formatted.append(f"""
        - {proj['title']}
          {proj.get('description', 'No description')}
          {f"Technologies: {proj['technologies']}" if proj.get('technologies') else ''}
        """)
    return "\n".join(formatted)