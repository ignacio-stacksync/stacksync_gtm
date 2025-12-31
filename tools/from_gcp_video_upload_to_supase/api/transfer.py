from http.server import BaseHTTPRequestHandler
import json
import os
from supabase import create_client

SUPABASE_URL = f"https://{os.environ.get('SUPABASE_PROJECT_ID', 'nlrfqkoaclpsbttzuqdv')}.supabase.co"
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            source_url = data.get('source_url')
            meeting_name = data.get('meeting_name')

            if not source_url or not meeting_name:
                self._send_response(400, {
                    'success': False,
                    'error': 'Missing required fields: source_url and meeting_name'
                })
                return

            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

            result = supabase.table('video_transfer_jobs').insert({
                'source_url': source_url,
                'meeting_name': meeting_name,
                'status': 'pending'
            }).execute()

            job = result.data[0]

            self._send_response(200, {
                'success': True,
                'job_id': job['id'],
                'status': 'pending',
                'message': 'Job queued. Poll /api/status?job_id=<job_id> for updates.'
            })

        except json.JSONDecodeError:
            self._send_response(400, {
                'success': False,
                'error': 'Invalid JSON body'
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
