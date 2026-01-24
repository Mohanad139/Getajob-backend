import requests
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import os
from .database import get_connection

# Load environment variables
load_dotenv()

RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')

def fetch_jobs(query="software engineer", location="", num_pages=1):
    """Fetch jobs from JSearch API"""
    url = "https://jsearch.p.rapidapi.com/search"
    
    all_jobs = []
    
    for page in range(1, num_pages + 1):
        querystring = {
            "query": query,
            "page": str(page),
            "num_pages": "1"
        }
        
        if location:
            querystring["location"] = location
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
        
        try:
            response = requests.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data:
                all_jobs.extend(data['data'])
                print(f"Fetched page {page}: {len(data['data'])} jobs")
            else:
                print(f"No jobs found on page {page}")
                break
                
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break
    
    return all_jobs

def save_jobs_to_db(jobs):
    """Save jobs to PostgreSQL database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    saved_count = 0
    skipped_count = 0
    
    for job in jobs:
        try:
            # Extract job data
            job_id = job.get('job_id', '')
            title = job.get('job_title', '')
            company = job.get('employer_name', '')
            location = job.get('job_city', '') or job.get('job_country', '')
            
            # Handle salary
            salary_min = job.get('job_min_salary')
            salary_max = job.get('job_max_salary')
            salary = None
            if salary_min and salary_max:
                salary = f"{salary_min}-{salary_max}"
            elif salary_min:
                salary = str(salary_min)
            
            job_type = job.get('job_employment_type', '')
            description = job.get('job_description', '')
            url = job.get('job_apply_link', '')
            
            # Convert posted date
            posted_timestamp = job.get('job_posted_at_timestamp')
            posted_date = datetime.fromtimestamp(posted_timestamp) if posted_timestamp else None
            
            # Insert into database
            cursor.execute("""
                INSERT INTO jobs (
                    job_id, title, company, location, salary, 
                    job_type, description, url, source, posted_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO NOTHING
            """, (
                job_id, title, company, location, salary,
                job_type, description, url, 'jsearch', posted_date
            ))
            
            if cursor.rowcount > 0:
                saved_count += 1
            else:
                skipped_count += 1
                
        except Exception as e:
            print(f"Error saving job {job.get('job_id', 'unknown')}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\nSaved: {saved_count} jobs")
    print(f"Skipped (duplicates): {skipped_count} jobs")
    return saved_count

if __name__ == "__main__":
    print("Fetching jobs from JSearch API...")
    jobs = fetch_jobs(query="python developer", num_pages=1)
    print(f"\nTotal jobs fetched: {len(jobs)}")
    
    if jobs:
        print("\nSaving to database...")
        save_jobs_to_db(jobs)
        print("\nDone!")
    else:
        print("No jobs to save.")