from http.server import BaseHTTPRequestHandler
import json
import os
import re
import uuid
import io
from datetime import datetime
import httpx
from supabase import create_client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SUPABASE_URL = f"https://{os.environ.get('SUPABASE_PROJECT_ID', 'nlrfqkoaclpsbttzuqdv')}.supabase.co"
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')
GOOGLE_DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '1C6fXJonJdlvD4al5NzaHFD-uejWzwWo9')


def get_drive_service():
    """Create Google Drive service using service account credentials."""
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON', '')
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")

    creds_dict = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return build('drive', 'v3', credentials=credentials)


def sanitize_filename(name: str) -> str:
    """Remove special characters and replace spaces with underscores."""
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name.lower()


def generate_filename(meeting_name: str) -> str:
    """Generate filename: {meeting_name}_{uuid}_{timestamp}.mp4"""
    sanitized = sanitize_filename(meeting_name)
    short_uuid = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    return f"{sanitized}_{short_uuid}_{timestamp}.mp4"


def upload_to_drive(video_data: bytes, filename: str) -> str:
    """Upload video to Google Drive and return shareable link."""
    service = get_drive_service()

    file_metadata = {
        'name': filename,
        'parents': [GOOGLE_DRIVE_FOLDER_ID]
    }

    media = MediaIoBaseUpload(
        io.BytesIO(video_data),
        mimetype='video/mp4',
        resumable=True
    )

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    # Make file accessible via link
    service.permissions().create(
        fileId=file['id'],
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    return file.get('webViewLink', f"https://drive.google.com/file/d/{file['id']}/view")


def process_job(supabase, job: dict) -> None:
    """Process a single transfer job."""
    job_id = job['id']

    # Mark as processing
    supabase.table('video_transfer_jobs').update({
        'status': 'processing'
    }).eq('id', job_id).execute()

    try:
        # Download video from GCP
        with httpx.Client(timeout=300.0) as client:
            response = client.get(job['source_url'])
            response.raise_for_status()
            video_data = response.content

        # Generate filename
        filename = generate_filename(job['meeting_name'])

        # Upload to Google Drive
        result_url = upload_to_drive(video_data, filename)

        # Mark as completed
        supabase.table('video_transfer_jobs').update({
            'status': 'completed',
            'result_url': result_url
        }).eq('id', job_id).execute()

    except Exception as e:
        # Mark as failed
        supabase.table('video_transfer_jobs').update({
            'status': 'failed',
            'error': str(e)
        }).eq('id', job_id).execute()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Verify cron secret (optional but recommended)
            auth_header = self.headers.get('Authorization', '')
            cron_secret = os.environ.get('CRON_SECRET', '')

            if cron_secret and auth_header != f'Bearer {cron_secret}':
                self._send_response(401, {
                    'success': False,
                    'error': 'Unauthorized'
                })
                return

            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

            # Get pending jobs (limit to 1 per cron run to avoid timeout)
            result = supabase.table('video_transfer_jobs').select('*').eq(
                'status', 'pending'
            ).order('created_at').limit(1).execute()

            if not result.data:
                self._send_response(200, {
                    'success': True,
                    'message': 'No pending jobs',
                    'processed': 0
                })
                return

            # Process the job
            job = result.data[0]
            process_job(supabase, job)

            self._send_response(200, {
                'success': True,
                'message': 'Job processed',
                'processed': 1,
                'job_id': job['id']
            })

        except Exception as e:
            self._send_response(500, {
                'success': False,
                'error': str(e)
            })

    def _send_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
