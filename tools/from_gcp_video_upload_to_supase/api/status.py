from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs
from supabase import create_client

SUPABASE_URL = f"https://{os.environ.get('SUPABASE_PROJECT_ID', 'nlrfqkoaclpsbttzuqdv')}.supabase.co"
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            job_id = params.get('job_id', [None])[0]

            if not job_id:
                self._send_response(400, {
                    'success': False,
                    'error': 'Missing required parameter: job_id'
                })
                return

            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

            result = supabase.table('video_transfer_jobs').select('*').eq('id', job_id).execute()

            if not result.data:
                self._send_response(404, {
                    'success': False,
                    'error': 'Job not found'
                })
                return

            job = result.data[0]

            response = {
                'success': job['status'] == 'completed',
                'job_id': job['id'],
                'status': job['status'],
                'meeting_name': job['meeting_name'],
                'created_at': job['created_at']
            }

            if job['status'] == 'completed':
                response['result_url'] = job['result_url']
            elif job['status'] == 'failed':
                response['error'] = job['error']

            self._send_response(200, response)

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
