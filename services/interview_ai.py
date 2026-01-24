from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_KEY"))  

def generate_interview_questions(job_description, job_title, num_questions=5):
    prompt = f"""
    You are an expert technical interviewer for {job_title}.

    Based on this job description:
    {job_description}

    Generate {num_questions} interview questions that are:
    1. Mix of behavioral and technical questions
    2. Based ONLY on skills/qualifications mentioned in the job description
    3. Real-world, practical questions (not just theoretical)
    4. Relevant to the actual responsibilities of the role
    
    Question types should include:
    - Behavioral (past experience, problem-solving, teamwork)
    - Technical (skills, technologies, methodologies mentioned in the job)
    - Situational (hypothetical scenarios based on job responsibilities)

    CRITICAL RULES:
    - ONLY ask about skills/technologies explicitly mentioned in the job description
    - Make questions specific and practical
    - Focus on qualifications section if available
    
    Respond in this exact JSON format:
    {{
        "questions": [
            {{
                "type": "behavioral",
                "text": "Tell me about a time when..."
            }},
            {{
                "type": "technical",
                "text": "How would you implement..."
            }}
        ]
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert interviewer. You must ONLY ask questions based on job description - never add new information. Respond with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        response_format={"type": "json_object"}
    )
    
    questions = json.loads(response.choices[0].message.content)
    return questions

def evaluate_answer(question, answer, job_title, job_description):
    prompt = f"""
    You are an expert interviewer evaluating a candidate's answer for a {job_title} position.

    Job Context:
    {job_description}

    Interview Question:
    {question}

    Candidate's Answer:
    {answer}

    Evaluate this answer and provide:
    1. Score (1-10) - Be realistic and fair
    2. Strengths (2-3 specific things they did well)
    3. Weaknesses (2-3 areas for improvement)
    4. Specific actionable suggestions

    Consider:
    - Relevance to the question
    - Depth of knowledge
    - Communication clarity
    - Specific examples provided
    - Alignment with job requirements

    Respond in this exact JSON format:
    {{
        "score": 7,
        "strengths": ["strength 1", "strength 2", "strength 3"],
        "weaknesses": ["weakness 1", "weakness 2"],
        "suggestions": ["suggestion 1", "suggestion 2", "suggestion 3"]
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert interviewer providing constructive feedback. Respond with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        response_format={"type": "json_object"}
    )
    
    feedback = json.loads(response.choices[0].message.content)
    return feedback

def get_overall_feedback(session_id):
    """Generate overall interview performance summary"""
    from .database import get_connection
    from psycopg2.extras import RealDictCursor
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get all questions and answers from session
        cursor.execute("""
            SELECT question_text, user_answer, score, strengths, weaknesses
            FROM interview_questions
            WHERE session_id = %s AND user_answer IS NOT NULL
        """, (session_id,))
        
        questions_data = cursor.fetchall()
        
        if not questions_data:
            return {"error": "No answered questions found"}
        
        # Calculate average score
        avg_score = sum(q['score'] for q in questions_data if q['score']) / len(questions_data)
        
        # Prepare summary for AI
        summary_text = f"""
        Interview Performance Summary:
        - Total Questions: {len(questions_data)}
        - Average Score: {avg_score:.1f}/10
        
        Questions and Performance:
        """
        
        for i, q in enumerate(questions_data, 1):
            summary_text += f"""
            Q{i}: {q['question_text']}
            Answer: {q['user_answer'][:200]}...
            Score: {q['score']}/10
            """
        
        # Get AI overall assessment
        prompt = f"""
        You are a senior interviewer providing final feedback on a candidate's interview performance.
        
        {summary_text}
        
        Provide an overall assessment including:
        1. Overall performance summary
        2. Top 3 strengths across all answers
        3. Top 3 areas for improvement
        4. Specific recommendations for interview preparation
        5. Overall readiness rating (Not Ready / Needs Work / Ready / Highly Ready)
        
        Respond in this exact JSON format:
        {{
            "average_score": {avg_score},
            "overall_summary": "brief summary paragraph",
            "top_strengths": ["strength 1", "strength 2", "strength 3"],
            "top_improvements": ["improvement 1", "improvement 2", "improvement 3"],
            "recommendations": ["rec 1", "rec 2", "rec 3"],
            "readiness": "Ready"
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a senior interviewer providing comprehensive feedback. Respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        overall_feedback = json.loads(response.choices[0].message.content)
        return overall_feedback
        
    finally:
        cursor.close()
        conn.close()