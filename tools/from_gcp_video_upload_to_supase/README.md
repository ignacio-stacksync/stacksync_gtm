# GCP Video Upload to Google Drive

Simple API to transfer videos from GCP signed URLs to Google Drive.

## Setup

### Environment Variables (Vercel)

```
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
GOOGLE_DRIVE_FOLDER_ID=0ANj2wQrOweOKUk9PVA
```

### Deploy

```bash
vercel
```

## API Usage

**POST /api/transfer**

```bash
curl -X POST https://stacksync-gtm.vercel.app/api/transfer \
  -H "Content-Type: application/json" \
  -d '{"source_url": "https://...", "meeting_name": "My Meeting"}'
```

**Response:**
```json
{
  "success": true,
  "url": "https://drive.google.com/file/d/.../view",
  "filename": "my_meeting_abc123_20240101_120000.mp4"
}
```
