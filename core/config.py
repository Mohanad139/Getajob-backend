import os
from dotenv import load_dotenv

load_dotenv()

# JWT Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
