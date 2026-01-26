import requests
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from .database import get_connection

# Load environment variables
load_dotenv()

RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')

# Simple in-memory cache with TTL
_job_cache = {}
CACHE_TTL_HOURS = 2  # Cache results for 2 hours


def _get_cache_key(query: str, location: str) -> str:
    """Generate a cache key from search parameters"""
    return f"{query.lower().strip()}|{location.lower().strip()}"


def _get_cached_jobs(cache_key: str):
    """Get cached jobs if not expired"""
    if cache_key in _job_cache:
        cached_data, cached_time = _job_cache[cache_key]
        if datetime.now() - cached_time < timedelta(hours=CACHE_TTL_HOURS):
            print(f"Cache hit for: {cache_key}")
            return cached_data
        else:
            # Cache expired, remove it
            del _job_cache[cache_key]
    return None


def _set_cache(cache_key: str, jobs: list):
    """Store jobs in cache with current timestamp"""
    _job_cache[cache_key] = (jobs, datetime.now())


def fetch_jobs(query="software engineer", location="", max_jobs=25):
    """Fetch jobs from JSearch API up to max_jobs limit (with caching)"""

    # Check cache first
    cache_key = _get_cache_key(query, location)
    cached_jobs = _get_cached_jobs(cache_key)
    if cached_jobs is not None:
        return cached_jobs[:max_jobs]

    url = "https://jsearch.p.rapidapi.com/search"

    all_jobs = []
    page = 1
    max_pages = 3  # Safety limit to prevent excessive API calls

    while len(all_jobs) < max_jobs and page <= max_pages:
        querystring = {
            "query": query,
            "page": str(page),
            "num_pages": "3"
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

            if 'data' in data and len(data['data']) > 0:
                all_jobs.extend(data['data'])
                print(f"Fetched page {page}: {len(data['data'])} jobs (total: {len(all_jobs)})")

                # Stop if we've reached enough jobs
                if len(all_jobs) >= max_jobs:
                    all_jobs = all_jobs[:max_jobs]  # Trim to exact limit
                    break
            else:
                print(f"No more jobs found on page {page}")
                break

        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break

        page += 1

    # Cache results for future requests
    if all_jobs:
        _set_cache(cache_key, all_jobs)

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
    jobs = fetch_jobs(query="python developer", max_jobs=100)
    print(f"\nTotal jobs fetched: {len(jobs)}")
    
    if jobs:
        print("\nSaving to database...")
        save_jobs_to_db(jobs)
        print("\nDone!")
    else:
        print("No jobs to save.")