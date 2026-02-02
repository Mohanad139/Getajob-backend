from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from routers import auth, jobs, applications, dashboard, work_experience, education, skills, projects, resume, interview
from services.rate_limiter import limiter, rate_limit_exceeded_handler

app = FastAPI(title="Interview AI API")

# Add rate limiter with custom CORS-aware handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Enable CORS for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://mogetajob.vercel.app",  
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(dashboard.router)
app.include_router(work_experience.router)
app.include_router(education.router)
app.include_router(skills.router)
app.include_router(projects.router)
app.include_router(resume.router)
app.include_router(interview.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Interview AI API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
