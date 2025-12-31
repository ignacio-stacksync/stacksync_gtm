-- Run this in Supabase SQL Editor to create the jobs table

CREATE TABLE IF NOT EXISTS video_transfer_jobs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    source_url TEXT NOT NULL,
    meeting_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    result_url TEXT,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster queries on pending jobs
CREATE INDEX IF NOT EXISTS idx_video_transfer_jobs_status ON video_transfer_jobs(status);

-- Function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_video_transfer_jobs_updated_at ON video_transfer_jobs;
CREATE TRIGGER update_video_transfer_jobs_updated_at
    BEFORE UPDATE ON video_transfer_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
