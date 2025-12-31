from http.server import BaseHTTPRequestHandler
import json
import os
import re
import uuid
from datetime import datetime
import httpx
from supabase import create_client

SUPABASE_URL = f"https://{os.environ.get('SUPABASE_PROJECT_ID', 'nlrfqkoaclpsbttzuqdv')}.supabase.co"
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')
BUCKET_NAME = 'circleback-meeting-recording'


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

        # Upload to Supabase Storage
        supabase.storage.from_(BUCKET_NAME).upload(
            path=filename,
            file=video_data,
            file_options={'content-type': 'video/mp4'}
        )

        # Generate signed URL (valid for 1 year)
        signed_url_response = supabase.storage.from_(BUCKET_NAME).create_signed_url(
            path=filename,
            expires_in=31536000  # 1 year in seconds
        )
        result_url = signed_url_response['signedURL']

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
