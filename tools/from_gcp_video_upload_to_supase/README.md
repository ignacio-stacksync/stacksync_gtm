# GCP Video Upload to Supabase

Async API to transfer videos from GCP signed URLs to Supabase Storage.

## Setup

### 1. Supabase Database

Run `setup.sql` in your Supabase SQL Editor to create the jobs table.

### 2. Supabase Storage

Create a bucket named `circleback-meeting-recording` in Supabase Storage (set to private).

### 3. Environment Variables

Set these in Vercel:

```
SUPABASE_PROJECT_ID=nlrfqkoaclpsbttzuqdv
SUPABASE_SERVICE_KEY=your_service_role_key
CRON_SECRET=your_random_secret  # optional, for securing cron endpoint
```

### 4. Deploy

```bash
cd tools/from_gcp_video_upload_to_supase
vercel
```

## API Usage

### Submit Transfer Job

```bash
POST /api/transfer
Content-Type: application/json

{
  "source_url": "https://storage.googleapis.com/...",
  "meeting_name": "Q4 Planning Call"
}
```

Response:
```json
{
  "success": true,
  "job_id": "uuid-here",
  "status": "pending",
  "message": "Job queued. Poll /api/status?job_id=<job_id> for updates."
}
```

### Check Status

```bash
GET /api/status?job_id=<job_id>
```

Response (completed):
```json
{
  "success": true,
  "job_id": "uuid-here",
  "status": "completed",
  "meeting_name": "Q4 Planning Call",
  "result_url": "https://...supabase.co/storage/v1/..."
}
```

Response (failed):
```json
{
  "success": false,
  "job_id": "uuid-here",
  "status": "failed",
  "error": "Error message"
}
```

## Cron Limitation (Free Tier)

Vercel Hobby (free) plan only supports **daily** cron jobs. For minute-by-minute processing, either:

1. **Upgrade to Vercel Pro** - supports `* * * * *` (every minute)
2. **Use external cron** - Use [cron-job.org](https://cron-job.org) (free) to hit `/api/cron/process` every minute
3. **Manual trigger** - Call `/api/cron/process` manually when needed

If using external cron, set `CRON_SECRET` env var and call with:
```bash
curl -H "Authorization: Bearer YOUR_CRON_SECRET" https://your-app.vercel.app/api/cron/process
```
