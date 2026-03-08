import redis
import json
import hashlib
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from dotenv import load_dotenv
import os
import re
import random
import time

# Load environment variables
load_dotenv()

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Redis client
_redis_client = None
CACHE_TTL_SECONDS = 2 * 60 * 60  # 2 hours
CACHE_PREFIX = "job_search:"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]


def _get_headers(referer=None):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "same-origin"
    return headers


def _get_redis():
    """Get or create Redis connection"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            _redis_client.ping()
            print("Redis connected successfully")
        except redis.ConnectionError as e:
            print(f"Redis connection failed: {e}")
            return None
    return _redis_client


def _get_cache_key(query, location, date_posted="week", sort_by="date"):
    return f"{CACHE_PREFIX}{query.lower().strip()}|{location.lower().strip()}|{date_posted}|{sort_by}"


def _get_cached_jobs(cache_key):
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


def _set_cache(cache_key, jobs):
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(jobs))
        print(f"Cached {len(jobs)} jobs with key: {cache_key}")
    except Exception as e:
        print(f"Redis set error: {e}")


# Map date_posted to Indeed's fromage parameter (days)
DATE_POSTED_TO_DAYS = {
    "today": 1,
    "3days": 3,
    "week": 7,
    "month": 30,
    "all": None,
}


def _extract_ddg_url(raw_url):
    """Extract the actual URL from a DuckDuckGo redirect URL"""
    if "uddg=" in raw_url:
        parsed = urlparse(raw_url)
        params = parse_qs(parsed.query)
        if "uddg" in params:
            return unquote(params["uddg"][0])
    # Handle protocol-relative URLs
    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url
    return raw_url


def _make_job_id(title, company, url):
    """Generate a stable unique job ID"""
    source = f"{title}|{company}|{url}"
    return hashlib.md5(source.encode()).hexdigest()[:20]


def _parse_indeed_salary(salary_text):
    """Parse salary text like '$80,000 - $120,000 a year' into min/max"""
    if not salary_text:
        return None, None
    numbers = re.findall(r'[\d,]+\.?\d*', salary_text.replace(',', ''))
    if len(numbers) >= 2:
        try:
            return float(numbers[0]), float(numbers[1])
        except ValueError:
            pass
    elif len(numbers) == 1:
        try:
            return float(numbers[0]), None
        except ValueError:
            pass
    return None, None


# =============================================================================
# ATS Platform APIs (Greenhouse, Lever) — reliable public JSON APIs
# =============================================================================

# Popular companies and their ATS board slugs
# Format: (board_slug, display_name)
GREENHOUSE_COMPANIES = [
    ("airbnb", "Airbnb"), ("airtable", "Airtable"), ("brex", "Brex"),
    ("chime", "Chime"), ("cloudflare", "Cloudflare"), ("coinbase", "Coinbase"),
    ("databricks", "Databricks"), ("discord", "Discord"), ("doordash", "DoorDash"),
    ("duolingo", "Duolingo"), ("figma", "Figma"), ("flexport", "Flexport"),
    ("gusto", "Gusto"), ("hashicorp", "HashiCorp"), ("hubspot", "HubSpot"),
    ("instacart", "Instacart"), ("notion", "Notion"), ("navan", "Navan"),
    ("okta", "Okta"), ("openai", "OpenAI"), ("pagerduty", "PagerDuty"),
    ("palantir", "Palantir"), ("plaid", "Plaid"), ("ramp", "Ramp"),
    ("reddit", "Reddit"), ("remitly", "Remitly"), ("rippling", "Rippling"),
    ("robinhood", "Robinhood"), ("samsara", "Samsara"), ("scale", "Scale AI"),
    ("snyk", "Snyk"), ("sourcegraph", "Sourcegraph"), ("splice", "Splice"),
    ("squarespace", "Squarespace"), ("stripe", "Stripe"), ("thumbtack", "Thumbtack"),
    ("twitch", "Twitch"), ("vanta", "Vanta"), ("watershed", "Watershed"),
    ("webflow", "Webflow"),
]

LEVER_COMPANIES = [
    ("shopify", "Shopify"), ("spotify", "Spotify"),
    ("twilio", "Twilio"), ("postman", "Postman"),
    ("miro", "Miro"), ("loom", "Loom"),
    ("calendly", "Calendly"), ("cockroachlabs", "Cockroach Labs"),
    ("dbt-labs", "dbt Labs"), ("fivetran", "Fivetran"), ("grafana", "Grafana Labs"),
    ("linear", "Linear"),
    ("mux", "Mux"), ("nerdwallet", "NerdWallet"),
    ("podium81", "Podium"), ("retool", "Retool"), ("seismic", "Seismic"),
    ("sentry", "Sentry"), ("stytch", "Stytch"), ("supabase", "Supabase"),
    ("tailscale", "Tailscale"),
]


def _fetch_greenhouse_jobs(company_slug, company_name, query="", location="", max_jobs=10):
    """Fetch jobs from a company's Greenhouse board via their public JSON API."""
    jobs = []
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs",
                              params={"content": "true"})
        if resp.status_code != 200:
            return jobs

        data = resp.json()
        query_lower = query.lower()
        location_lower = location.lower()

        for job_data in data.get("jobs", []):
            if len(jobs) >= max_jobs:
                break

            title = job_data.get("title", "")
            job_location = job_data.get("location", {}).get("name", "")

            # Filter by query keywords
            if query_lower and not any(kw in title.lower() for kw in query_lower.split()):
                continue

            # Filter by location if provided
            if location_lower and location_lower not in job_location.lower():
                # Also check individual words (e.g. "New York" matches "New York, NY")
                loc_words = [w for w in location_lower.split(",") if w.strip()]
                if not any(w.strip() in job_location.lower() for w in loc_words):
                    continue

            job_url = job_data.get("absolute_url", "")
            content = job_data.get("content", "")
            # Strip HTML tags from content
            if content:
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()[:500]

            # Parse location
            loc_parts = [p.strip() for p in job_location.split(",")]
            city = loc_parts[0] if len(loc_parts) > 0 else ""
            state = loc_parts[1] if len(loc_parts) > 1 else ""
            country = loc_parts[2] if len(loc_parts) > 2 else ""

            # Parse updated date
            updated_at = job_data.get("updated_at", "")

            jobs.append({
                "job_id": _make_job_id(title, company_name, job_url),
                "job_title": title,
                "employer_name": company_name,
                "job_city": city,
                "job_state": state,
                "job_country": country,
                "job_description": content,
                "job_min_salary": None,
                "job_max_salary": None,
                "job_employment_type": "",
                "job_apply_link": job_url,
                "job_google_link": "",
                "job_posted_at_datetime_utc": updated_at[:10] if updated_at else "",
                "site": "greenhouse",
            })

    except Exception as e:
        print(f"Greenhouse error for {company_slug}: {e}")

    return jobs


def _fetch_lever_jobs(company_slug, company_name, query="", location="", max_jobs=10):
    """Fetch jobs from a company's Lever board via their public JSON API."""
    jobs = []
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"https://api.lever.co/v0/postings/{company_slug}",
                              params={"mode": "json"})
        if resp.status_code != 200:
            return jobs

        data = resp.json()
        query_lower = query.lower()
        location_lower = location.lower()

        for posting in data:
            if len(jobs) >= max_jobs:
                break

            title = posting.get("text", "")
            job_location = posting.get("categories", {}).get("location", "")
            team = posting.get("categories", {}).get("team", "")

            # Filter by query keywords
            if query_lower:
                combined = f"{title} {team}".lower()
                if not any(kw in combined for kw in query_lower.split()):
                    continue

            # Filter by location
            if location_lower and job_location:
                if location_lower not in job_location.lower():
                    loc_words = [w for w in location_lower.split(",") if w.strip()]
                    if not any(w.strip() in job_location.lower() for w in loc_words):
                        continue

            job_url = posting.get("hostedUrl", "") or posting.get("applyUrl", "")
            description = posting.get("descriptionPlain", "")
            if description:
                description = description[:500]

            # Parse location
            loc_parts = [p.strip() for p in job_location.split(",")] if job_location else []
            city = loc_parts[0] if len(loc_parts) > 0 else ""
            state = loc_parts[1] if len(loc_parts) > 1 else ""
            country = loc_parts[2] if len(loc_parts) > 2 else ""

            created_at = posting.get("createdAt", 0)
            posted_date = ""
            if created_at:
                try:
                    posted_date = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Lever sometimes provides salary/compensation in additional fields
            salary_range = posting.get("categories", {}).get("commitment", "")

            jobs.append({
                "job_id": _make_job_id(title, company_name, job_url),
                "job_title": title,
                "employer_name": company_name,
                "job_city": city,
                "job_state": state,
                "job_country": country,
                "job_description": description,
                "job_min_salary": None,
                "job_max_salary": None,
                "job_employment_type": salary_range,
                "job_apply_link": job_url,
                "job_google_link": "",
                "job_posted_at_datetime_utc": posted_date,
                "site": "lever",
            })

    except Exception as e:
        print(f"Lever error for {company_slug}: {e}")

    return jobs


def _scrape_ats_jobs(query, location, max_jobs=25, days=None):
    """Fetch jobs from Greenhouse and Lever company boards via their public APIs."""
    import concurrent.futures

    all_jobs = []
    per_company = max(2, max_jobs // 15)

    def fetch_gh(args):
        slug, name = args
        return _fetch_greenhouse_jobs(slug, name, query=query, location=location, max_jobs=per_company)

    def fetch_lv(args):
        slug, name = args
        return _fetch_lever_jobs(slug, name, query=query, location=location, max_jobs=per_company)

    # Fetch from all companies in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        gh_futures = list(executor.map(fetch_gh, GREENHOUSE_COMPANIES))
        lv_futures = list(executor.map(fetch_lv, LEVER_COMPANIES))

    for jobs in gh_futures:
        all_jobs.extend(jobs)
    for jobs in lv_futures:
        all_jobs.extend(jobs)

    # Filter by date if needed
    if days is not None and days < 30:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        filtered = []
        for job in all_jobs:
            posted = job.get("job_posted_at_datetime_utc", "")
            if not posted:
                filtered.append(job)  # Keep jobs without dates (can't filter)
                continue
            try:
                posted_dt = datetime.strptime(posted[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if posted_dt >= cutoff:
                    filtered.append(job)
            except ValueError:
                filtered.append(job)
        all_jobs = filtered

    return all_jobs[:max_jobs]


def _scrape_indeed(query, location, max_jobs=25, days=7, sort_by="date"):
    """Scrape Indeed job listings via DuckDuckGo site:indeed.com search (Indeed blocks direct requests)"""
    jobs = []
    seen = set()

    location_str = f" in {location}" if location else ""
    date_hint = ""
    if days is not None and days <= 1:
        date_hint = " today"
    elif days is not None and days <= 7:
        date_hint = " this week"

    search_query = f"site:indeed.com {query}{location_str}{date_hint}"

    try:
        headers = _get_headers(referer="https://duckduckgo.com/")
        resp = _ddg_search(search_query, headers)

        if resp is None:
            return jobs

        soup = BeautifulSoup(resp.text, "html.parser")
        results = _parse_ddg_results(soup)

        for result in results:
            if len(jobs) >= max_jobs:
                break

            try:
                raw_title = result["title"]
                url = result["url"]

                # Only keep indeed.com results
                if "indeed.com" not in url.lower():
                    continue

                snippet = result["snippet"]

                # Parse title - Indeed results are typically "Job Title - Company | Indeed.com"
                job_title = raw_title
                company = ""

                # Remove Indeed.com suffix
                for suffix in [" | Indeed.com", " - Indeed.com", " | Indeed", " - Indeed"]:
                    if suffix.lower() in job_title.lower():
                        idx = job_title.lower().index(suffix.lower())
                        job_title = job_title[:idx].strip()
                        break

                # Split remaining into job title and company
                for sep in [" - ", " | ", " — ", " – "]:
                    if sep in job_title:
                        parts = job_title.split(sep)
                        if len(parts) >= 2:
                            job_title = parts[0].strip()
                            company = parts[1].strip()
                        break

                if not job_title or len(job_title) < 3:
                    continue

                # Try to extract location from snippet
                loc_city, loc_state, loc_country = "", "", "US"
                # Indeed snippets often contain location info
                loc_match = re.search(r'(?:in\s+)?([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})', snippet)
                if loc_match:
                    loc_city = loc_match.group(1)
                    loc_state = loc_match.group(2)
                elif location:
                    loc_parts = [p.strip() for p in location.split(",")]
                    loc_city = loc_parts[0] if len(loc_parts) > 0 else ""
                    loc_state = loc_parts[1] if len(loc_parts) > 1 else ""

                # Extract salary from snippet
                min_sal, max_sal = _parse_indeed_salary(snippet)

                # Deduplicate
                dedup_key = (job_title.lower(), company.lower())
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                jobs.append({
                    "job_id": _make_job_id(job_title, company, url),
                    "job_title": job_title,
                    "employer_name": company,
                    "job_city": loc_city,
                    "job_state": loc_state,
                    "job_country": loc_country,
                    "job_description": snippet[:500] if snippet else "",
                    "job_min_salary": min_sal,
                    "job_max_salary": max_sal,
                    "job_employment_type": "",
                    "job_apply_link": url,
                    "job_google_link": "",
                    "job_posted_at_datetime_utc": "",
                    "site": "indeed",
                })

            except Exception as e:
                print(f"Error parsing Indeed/DDG result: {e}")
                continue

    except httpx.TimeoutException:
        print("DuckDuckGo (Indeed search) timed out")
    except Exception as e:
        print(f"Error scraping Indeed via DuckDuckGo: {e}")

    return jobs


def _scrape_linkedin(query, location, max_jobs=25, days=7, sort_by="date"):
    """Scrape job listings from LinkedIn public job search (no login required)"""
    jobs = []
    seen = set()
    start = 0

    # LinkedIn time filter: r86400=24h, r604800=week, r2592000=month
    time_filter = ""
    if days is not None:
        if days <= 1:
            time_filter = "r86400"
        elif days <= 7:
            time_filter = "r604800"
        elif days <= 30:
            time_filter = "r2592000"

    sort_param = "DD" if sort_by == "date" else "R"

    while len(jobs) < max_jobs and start < max_jobs + 50:
        params = {
            "keywords": query,
            "location": location,
            "start": start,
            "sortBy": sort_param,
            "position": 1,
            "pageNum": 0,
        }
        if time_filter:
            params["f_TPR"] = time_filter

        try:
            with httpx.Client(headers=_get_headers(), follow_redirects=True, timeout=15.0) as client:
                resp = client.get("https://www.linkedin.com/jobs/search/", params=params)

            if resp.status_code != 200:
                print(f"LinkedIn returned status {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")

            cards = soup.select("div.base-card, div.base-search-card, li.result-card")

            if not cards:
                print(f"No LinkedIn job cards found at start={start}")
                break

            found_new = False
            for card in cards:
                try:
                    # Title
                    title_el = card.select_one("h3.base-search-card__title, h3.base-card__title, h4.base-search-card__title")
                    title = title_el.get_text(strip=True) if title_el else ""
                    if not title:
                        continue

                    # URL
                    link_el = card.select_one("a.base-card__full-link, a.base-search-card__full-link")
                    job_url = link_el.get("href", "").split("?")[0] if link_el else ""

                    # Company
                    company_el = card.select_one("h4.base-search-card__subtitle a, a.hidden-nested-link")
                    company = company_el.get_text(strip=True) if company_el else ""

                    # Location
                    loc_el = card.select_one("span.job-search-card__location")
                    loc = loc_el.get_text(strip=True) if loc_el else ""

                    # Date
                    date_el = card.select_one("time.job-search-card__listdate, time.job-search-card__listdate--new")
                    posted_date = date_el.get("datetime", "") if date_el else ""

                    # Deduplicate
                    dedup_key = (title.lower(), company.lower())
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    found_new = True

                    loc_parts = [p.strip() for p in loc.split(",")]
                    city = loc_parts[0] if len(loc_parts) > 0 else ""
                    state = loc_parts[1] if len(loc_parts) > 1 else ""
                    country = loc_parts[2] if len(loc_parts) > 2 else ""

                    jobs.append({
                        "job_id": _make_job_id(title, company, job_url),
                        "job_title": title,
                        "employer_name": company,
                        "job_city": city,
                        "job_state": state,
                        "job_country": country,
                        "job_description": "",
                        "job_min_salary": None,
                        "job_max_salary": None,
                        "job_employment_type": "",
                        "job_apply_link": job_url,
                        "job_google_link": "",
                        "job_posted_at_datetime_utc": posted_date,
                        "site": "linkedin",
                    })

                except Exception as e:
                    print(f"Error parsing LinkedIn card: {e}")
                    continue

            if not found_new:
                break

        except httpx.TimeoutException:
            print(f"LinkedIn request timed out at start={start}")
            break
        except Exception as e:
            print(f"Error scraping LinkedIn page: {e}")
            break

        start += 25

    return jobs


def _ddg_search(search_query, headers, timeout=15.0):
    """Perform a DuckDuckGo HTML search, trying multiple endpoints on rate limit."""
    endpoints = [
        "https://html.duckduckgo.com/html/",
        "https://lite.duckduckgo.com/lite/",
    ]
    for endpoint in endpoints:
        try:
            with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
                resp = client.get(endpoint, params={"q": search_query})
            if resp.status_code == 200:
                return resp
            print(f"DuckDuckGo ({endpoint}) returned status {resp.status_code}")
            # 202 means rate limited / CAPTCHA - try next endpoint
            if resp.status_code == 202:
                time.sleep(random.uniform(1.0, 2.0))
                continue
        except httpx.TimeoutException:
            print(f"DuckDuckGo ({endpoint}) timed out")
        except Exception as e:
            print(f"DuckDuckGo ({endpoint}) error: {e}")
    return None


def _parse_ddg_results(soup):
    """Parse DuckDuckGo search results from both html and lite versions."""
    results = []
    # Standard HTML version
    cards = soup.select("div.result, div.web-result")
    for card in cards:
        title_el = card.select_one("a.result__a, h2.result__title a")
        snippet_el = card.select_one("a.result__snippet, div.result__snippet")
        if title_el:
            results.append({
                "title": title_el.get_text(strip=True),
                "url": _extract_ddg_url(title_el.get("href", "")),
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            })
    if results:
        return results

    # Lite version uses table-based layout
    # Each result has: a link row, a snippet row, and a URL row in a table
    for link in soup.select("a.result-link"):
        snippet = ""
        # The snippet is usually in the next table cell or row
        parent_td = link.find_parent("td")
        if parent_td:
            next_td = parent_td.find_next("td", class_="result-snippet")
            if next_td:
                snippet = next_td.get_text(strip=True)
        results.append({
            "title": link.get_text(strip=True),
            "url": _extract_ddg_url(link.get("href", "")),
            "snippet": snippet,
        })

    return results


def _scrape_web_jobs(query, location, max_jobs=25, days=7):
    """
    Scrape job postings from across the web using DuckDuckGo search.
    Finds jobs posted on individual company career pages, Glassdoor,
    ZipRecruiter, and other job boards beyond LinkedIn/Indeed.
    """
    jobs = []
    seen = set()

    # Build search queries to find jobs from various sources
    date_hint = ""
    if days is not None and days <= 1:
        date_hint = " today"
    elif days is not None and days <= 7:
        date_hint = " recent"

    location_str = f" in {location}" if location else ""
    search_queries = [
        f"{query}{location_str}{date_hint} jobs apply",
        f"{query}{location_str} careers hiring",
    ]

    headers = _get_headers(referer="https://duckduckgo.com/")

    for search_query in search_queries:
        if len(jobs) >= max_jobs:
            break

        try:
            resp = _ddg_search(search_query, headers)
            if resp is None:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            results = _parse_ddg_results(soup)

            for result in results:
                if len(jobs) >= max_jobs:
                    break

                try:
                    raw_title = result["title"]
                    url = result["url"]

                    # Skip non-job results and results from Indeed/LinkedIn (we already scrape those)
                    url_lower = url.lower()
                    if any(skip in url_lower for skip in [
                        "indeed.com", "linkedin.com", "youtube.com", "wikipedia.org",
                        "reddit.com", "quora.com", "facebook.com", "twitter.com",
                    ]):
                        continue

                    snippet = result["snippet"]

                    # Parse the title to extract job title and company
                    # Common patterns: "Job Title - Company", "Job Title at Company",
                    # "Job Title | Company", "Company - Job Title"
                    job_title = raw_title
                    company = ""

                    # Try to extract company from URL domain
                    domain = ""
                    try:
                        parsed = urlparse(url)
                        domain = parsed.netloc.replace("www.", "").split(".")[0]
                    except Exception:
                        pass

                    # Parse title patterns
                    for sep in [" - ", " | ", " — ", " – "]:
                        if sep in raw_title:
                            parts = raw_title.split(sep)
                            # Usually "Job Title - Company - Location" or "Company - Job Title"
                            if len(parts) >= 2:
                                # Check if first part looks like a company name (shorter, no job keywords)
                                job_keywords = ["engineer", "developer", "manager", "analyst",
                                                "designer", "specialist", "coordinator", "director",
                                                "lead", "senior", "junior", "intern", "associate"]
                                first_lower = parts[0].lower()
                                if any(kw in first_lower for kw in job_keywords):
                                    job_title = parts[0].strip()
                                    company = parts[1].strip()
                                else:
                                    company = parts[0].strip()
                                    job_title = parts[1].strip()
                            break

                    if " at " in raw_title and not company:
                        at_parts = raw_title.split(" at ")
                        if len(at_parts) == 2:
                            job_title = at_parts[0].strip()
                            company = at_parts[1].strip()

                    # Clean up company name - remove common suffixes
                    for suffix in [" Careers", " Jobs", " Hiring", " Career Page",
                                   " Job Board", " - Apply", " | Apply"]:
                        if company.endswith(suffix):
                            company = company[:-len(suffix)].strip()

                    # Fallback: use domain as company name
                    if not company and domain:
                        company = domain.capitalize()

                    # Skip if we can't determine a job title
                    if not job_title or len(job_title) < 3:
                        continue

                    # Skip results that don't look like job postings
                    combined = (raw_title + " " + snippet).lower()
                    job_signals = ["apply", "hiring", "job", "position", "career",
                                   "salary", "remote", "full-time", "part-time",
                                   "experience", "requirements", "qualifications"]
                    if not any(signal in combined for signal in job_signals):
                        continue

                    # Deduplicate
                    dedup_key = (job_title.lower(), company.lower())
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    # Try to extract location from snippet
                    loc_city, loc_state, loc_country = "", "", ""
                    if location:
                        loc_parts = [p.strip() for p in location.split(",")]
                        loc_city = loc_parts[0] if len(loc_parts) > 0 else ""
                        loc_state = loc_parts[1] if len(loc_parts) > 1 else ""
                        loc_country = loc_parts[2] if len(loc_parts) > 2 else ""

                    # Determine the source site from URL
                    source_site = "web"
                    known_boards = {
                        "glassdoor": "glassdoor", "ziprecruiter": "ziprecruiter",
                        "monster": "monster", "simplyhired": "simplyhired",
                        "dice": "dice", "careerbuilder": "careerbuilder",
                        "wellfound": "wellfound", "lever.co": "lever",
                        "greenhouse": "greenhouse", "workday": "workday",
                        "smartrecruiters": "smartrecruiters", "ashbyhq": "ashby",
                        "breezy": "breezy", "jobvite": "jobvite",
                    }
                    for board_key, board_name in known_boards.items():
                        if board_key in url_lower:
                            source_site = board_name
                            break

                    # If it's from a company career page, label it as such
                    career_keywords = ["career", "jobs.", "/jobs", "hiring",
                                       "openings", "positions", "apply"]
                    if source_site == "web" and any(kw in url_lower for kw in career_keywords):
                        source_site = "company_career"

                    jobs.append({
                        "job_id": _make_job_id(job_title, company, url),
                        "job_title": job_title,
                        "employer_name": company,
                        "job_city": loc_city,
                        "job_state": loc_state,
                        "job_country": loc_country,
                        "job_description": snippet[:500] if snippet else "",
                        "job_min_salary": None,
                        "job_max_salary": None,
                        "job_employment_type": "",
                        "job_apply_link": url,
                        "job_google_link": "",
                        "job_posted_at_datetime_utc": "",
                        "site": source_site,
                    })

                except Exception as e:
                    print(f"Error parsing web search result: {e}")
                    continue

        except httpx.TimeoutException:
            print(f"DuckDuckGo request timed out for: {search_query}")
            continue
        except Exception as e:
            print(f"Error searching web for jobs: {e}")
            continue

        # Small delay between search queries
        time.sleep(random.uniform(0.5, 1.0))

    return jobs


def fetch_jobs(query="software engineer", location="", max_jobs=25, date_posted="week", sort_by="date", refresh=False):
    """
    Fetch jobs by scraping real job boards (Indeed + LinkedIn + web/company career pages).

    Args:
        query: Search query (e.g., "Software Engineer in Canada")
        location: Location filter
        max_jobs: Maximum number of jobs to fetch
        date_posted: Filter by posting date - "all", "today", "3days", "week", "month"
        sort_by: Sort results by - "relevance" or "date"
        refresh: If True, bypass cache and fetch fresh results
    """

    # Check cache first
    cache_key = _get_cache_key(query, location, date_posted, sort_by)
    if not refresh:
        cached_jobs = _get_cached_jobs(cache_key)
        if cached_jobs is not None:
            return cached_jobs[:max_jobs]

    days = DATE_POSTED_TO_DAYS.get(date_posted)

    # Split target between sources
    per_source = max(max_jobs // 3, 8)

    print(f"Fetching jobs for: '{query}' location='{location}' max={max_jobs} days={days}")

    all_jobs = []

    # 1. ATS APIs (Greenhouse + Lever) — most reliable source
    try:
        ats_jobs = _scrape_ats_jobs(query, location, max_jobs=per_source, days=days)
        print(f"ATS (Greenhouse/Lever): fetched {len(ats_jobs)} jobs")
        all_jobs.extend(ats_jobs)
    except Exception as e:
        print(f"ATS fetching failed: {e}")

    # 2. LinkedIn — reliable HTML scraping
    try:
        linkedin_jobs = _scrape_linkedin(query, location, max_jobs=per_source, days=days, sort_by=sort_by)
        print(f"LinkedIn: scraped {len(linkedin_jobs)} jobs")
        all_jobs.extend(linkedin_jobs)
    except Exception as e:
        print(f"LinkedIn scraping failed: {e}")

    # 3. Indeed via DuckDuckGo — fallback
    try:
        indeed_jobs = _scrape_indeed(query, location, max_jobs=per_source, days=days, sort_by=sort_by)
        print(f"Indeed: scraped {len(indeed_jobs)} jobs")
        all_jobs.extend(indeed_jobs)
    except Exception as e:
        print(f"Indeed scraping failed: {e}")

    # 4. Web search via DuckDuckGo — fallback
    try:
        web_jobs = _scrape_web_jobs(query, location, max_jobs=per_source, days=days)
        print(f"Web/Company pages: scraped {len(web_jobs)} jobs")
        all_jobs.extend(web_jobs)
    except Exception as e:
        print(f"Web scraping failed: {e}")

    # Deduplicate across sources by (title, company)
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = (job["job_title"].lower(), job["employer_name"].lower())
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    all_jobs = unique_jobs[:max_jobs]

    print(f"Total unique jobs: {len(all_jobs)}")

    # Cache results
    if all_jobs:
        _set_cache(cache_key, all_jobs)

    return all_jobs


def find_hiring_companies(query="software engineer", location="", max_companies=10, refresh=False):
    """
    Search the web for companies actively hiring for the given role.
    Uses DuckDuckGo to find companies and their career pages.

    Returns a list of dicts with: name, careers_url, description, source_url
    """
    cache_key = f"{CACHE_PREFIX}companies:{query.lower().strip()}|{location.lower().strip()}"
    if not refresh:
        cached = _get_cached_jobs(cache_key)
        if cached is not None:
            return cached[:max_companies]

    search_query = f"companies hiring {query}"
    if location:
        search_query += f" in {location}"
    search_query += " careers jobs"

    companies = []
    seen_companies = set()

    # Search DuckDuckGo HTML version
    try:
        headers = _get_headers()
        headers["Referer"] = "https://duckduckgo.com/"

        resp = _ddg_search(search_query, headers)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = _parse_ddg_results(soup)

        for result in results:
            if len(companies) >= max_companies:
                break

            try:
                title = result["title"]
                url = result["url"]
                snippet = result["snippet"]

                # Extract company name from the result title
                # Common patterns: "Company - Careers", "Jobs at Company", "Company Careers"
                company_name = title
                for suffix in [" - Careers", " Careers", " Jobs", " - Jobs", " | Careers",
                               " | Jobs", " Hiring", " - Hiring", " Career Page",
                               " Job Openings", " Open Positions", " - Open Positions"]:
                    if suffix.lower() in company_name.lower():
                        idx = company_name.lower().index(suffix.lower())
                        company_name = company_name[:idx].strip()
                        break

                for prefix in ["Jobs at ", "Careers at ", "Work at ", "Join "]:
                    if company_name.lower().startswith(prefix.lower()):
                        company_name = company_name[len(prefix):].strip()
                        break

                # Clean up company name
                company_name = company_name.split(" - ")[0].split(" | ")[0].strip()

                if not company_name or len(company_name) < 2 or len(company_name) > 80:
                    continue

                # Skip duplicates
                name_lower = company_name.lower()
                if name_lower in seen_companies:
                    continue
                seen_companies.add(name_lower)

                # Determine if the URL looks like a careers page
                url_lower = url.lower()
                is_careers = any(kw in url_lower for kw in
                                 ["career", "jobs", "hiring", "openings", "positions",
                                  "work-with-us", "join-us", "join-our-team", "talent"])

                companies.append({
                    "name": company_name,
                    "careers_url": url,
                    "description": snippet[:300] if snippet else "",
                    "is_careers_page": is_careers,
                })

            except Exception as e:
                print(f"Error parsing DuckDuckGo result: {e}")
                continue

    except Exception as e:
        print(f"Error searching DuckDuckGo: {e}")

    # Also try to find companies from LinkedIn company search
    try:
        linkedin_query = f"{query} hiring"
        if location:
            linkedin_query += f" {location}"

        params = {"keywords": linkedin_query, "position": 1, "pageNum": 0}

        with httpx.Client(headers=_get_headers(), follow_redirects=True, timeout=15.0) as client:
            resp = client.get("https://www.linkedin.com/jobs/search/", params=params)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("div.base-card, div.base-search-card")

            for card in cards:
                if len(companies) >= max_companies:
                    break

                company_el = card.select_one("h4.base-search-card__subtitle a, a.hidden-nested-link")
                if not company_el:
                    continue

                company_name = company_el.get_text(strip=True)
                company_url = company_el.get("href", "").split("?")[0]

                if not company_name:
                    continue

                name_lower = company_name.lower()
                if name_lower in seen_companies:
                    continue
                seen_companies.add(name_lower)

                # Build careers URL from LinkedIn company page
                careers_url = company_url
                if "/company/" in company_url:
                    careers_url = company_url.rstrip("/") + "/jobs/"

                companies.append({
                    "name": company_name,
                    "careers_url": careers_url,
                    "description": "",
                    "is_careers_page": True,
                })

    except Exception as e:
        print(f"Error extracting companies from LinkedIn: {e}")

    print(f"Found {len(companies)} hiring companies for '{query}'")

    # Cache results
    if companies:
        _set_cache(cache_key, companies)

    return companies[:max_companies]


if __name__ == "__main__":
    print("Scraping jobs from job boards...")
    jobs = fetch_jobs(query="python developer", location="United States", max_jobs=10)
    print(f"\nTotal jobs fetched: {len(jobs)}")

    for job in jobs[:5]:
        print(f"\n  Title: {job['job_title']}")
        print(f"  Company: {job['employer_name']}")
        print(f"  Location: {job['job_city']}, {job['job_state']}")
        print(f"  URL: {job['job_apply_link']}")
        print(f"  Source: {job['site']}")
