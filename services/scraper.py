import requests
import psycopg2
import redis
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from .database import get_connection

# Load environment variables
load_dotenv()

RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Redis client
_redis_client = None
CACHE_TTL_SECONDS = 2 * 60 * 60  # 2 hours in seconds
CACHE_PREFIX = "job_search:"


def _get_redis():
    """Get or create Redis connection"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            _redis_client.ping()  # Test connection
            print("Redis connected successfully")
        except redis.ConnectionError as e:
            print(f"Redis connection failed: {e}")
            return None
    return _redis_client


def _get_cache_key(query: str, location: str, date_posted: str = "week", sort_by: str = "date") -> str:
    """Generate a cache key from search parameters"""
    return f"{CACHE_PREFIX}{query.lower().strip()}|{location.lower().strip()}|{date_posted}|{sort_by}"


def _get_cached_jobs(cache_key: str):
    """Get cached jobs from Redis"""
    r = _get_redis()
    if r is None:
        return None
    try:
        cached_data = r.get(cache_key)
        if cached_data:
            print(f"Cache hit for: {cache_key}")
            return json.loads(cached_data)
    except Exception as e:
        print(f"Redis get error: {e}")
    return None


def _set_cache(cache_key: str, jobs: list):
    """Store jobs in Redis with TTL"""
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(jobs))
        print(f"Cached {len(jobs)} jobs with key: {cache_key}")
    except Exception as e:
        print(f"Redis set error: {e}")


def fetch_jobs(query="software engineer", location="", max_jobs=25, date_posted="week", sort_by="date", refresh=False):
    """
    Fetch jobs from JSearch API up to max_jobs limit (with caching)

    Args:
        query: Search query (e.g., "Software Engineer in Canada")
        location: Location filter (optional, usually included in query)
        max_jobs: Maximum number of jobs to fetch
        date_posted: Filter by posting date - "all", "today", "3days", "week", "month"
        sort_by: Sort results by - "relevance" or "date"
        refresh: If True, bypass cache and fetch fresh results
    """

    # Check cache first (unless refresh is requested)
    cache_key = _get_cache_key(query, location, date_posted, sort_by)
    if not refresh:
        cached_jobs = _get_cached_jobs(cache_key)
        if cached_jobs is not None:
            return cached_jobs[:max_jobs]

    url = "https://jsearch.p.rapidapi.com/search"

    all_jobs = []
    seen_ids = set()
    page = 1
    max_pages = 3  # Safety limit to prevent excessive API calls

    while len(all_jobs) < max_jobs and page <= max_pages:
        querystring = {
            "query": query,
            "page": str(page),
            "num_pages": "1",
            "date_posted": date_posted,
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
                for job in data['data']:
                    jid = job.get('job_id')
                    if jid and jid not in seen_ids:
                        seen_ids.add(jid)
                        all_jobs.append(job)
                print(f"Fetched page {page}: {len(data['data'])} jobs (unique total: {len(all_jobs)})")

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