from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, jobs, applications, dashboard, work_experience, education, skills, projects, resume, interview

app = FastAPI(title="Interview AI API")

# Enable CORS for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://getajob-frontend.vercel.app",  
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
