-- Migration to update applications and interview_sessions tables
-- Run these SQL commands to update your database schema

-- ============ UPDATE APPLICATIONS TABLE ============
-- Drop the foreign key constraint if it exists
ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_job_id_fkey;

-- Drop the job_id column
ALTER TABLE applications DROP COLUMN IF EXISTS job_id;

-- Add new columns for job details
ALTER TABLE applications ADD COLUMN IF NOT EXISTS job_title VARCHAR(255);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS company VARCHAR(255);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS location VARCHAR(255);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS job_url TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS job_description TEXT;

-- ============ UPDATE INTERVIEW_SESSIONS TABLE ============
-- Drop the job_id column if it exists
ALTER TABLE interview_sessions DROP COLUMN IF EXISTS job_id;

-- Add job_description column
ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS job_description TEXT;

-- Make sure job_title exists
ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS job_title VARCHAR(255);

-- ============ UPDATE JOBS TABLE ============
-- Add user_id column to make jobs user-specific
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);

-- Create index for faster queries by user
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);

-- ============ UPDATE USERS TABLE ============
-- Add headline column for professional title (e.g., "Software Engineer")
ALTER TABLE users ADD COLUMN IF NOT EXISTS headline VARCHAR(255);

-- Add summary column for "About Me" section
ALTER TABLE users ADD COLUMN IF NOT EXISTS summary TEXT;

-- ============ CREATE SKIPPED_JOBS TABLE ============
-- Track jobs that users have skipped so they don't appear in future searches
CREATE TABLE IF NOT EXISTS skipped_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    skipped_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, title, company, location)
);

-- Create index for faster queries by user
CREATE INDEX IF NOT EXISTS idx_skipped_jobs_user_id ON skipped_jobs(user_id);