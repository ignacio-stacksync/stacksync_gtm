from http.server import BaseHTTPRequestHandler
import json
import os
import re
import uuid
import io
from datetime import datetime
import httpx
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

GOOGLE_DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '0ANj2wQrOweOKUk9PVA')


def get_drive_service():
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
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name.lower()


def generate_filename(meeting_name: str) -> str:
    sanitized = sanitize_filename(meeting_name)
    short_uuid = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    return f"{sanitized}_{short_uuid}_{timestamp}.mp4"


def upload_to_drive(video_data: bytes, filename: str) -> str:
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
        fields='id, webViewLink',
        supportsAllDrives=True
    ).execute()

    service.permissions().create(
        fileId=file['id'],
        body={'type': 'anyone', 'role': 'reader'},
        supportsAllDrives=True
    ).execute()

    return file.get('webViewLink', f"https://drive.google.com/file/d/{file['id']}/view")


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

            # Download video from source
            with httpx.Client(timeout=300.0) as client:
                response = client.get(source_url)
                response.raise_for_status()
                video_data = response.content

            # Generate filename and upload to Google Drive
            filename = generate_filename(meeting_name)
            result_url = upload_to_drive(video_data, filename)

            self._send_response(200, {
                'success': True,
                'url': result_url,
                'filename': filename
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
