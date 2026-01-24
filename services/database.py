import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

import os
from urllib.parse import urlparse

def get_connection():
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Parse DATABASE_URL
        url = urlparse(database_url)
        return psycopg2.connect(
            dbname=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
    else:
        # Fallback to individual vars
        return psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )