from http.server import BaseHTTPRequestHandler
import json
import sys
import traceback

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging
        pass
    
    def do_POST(self):
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                return self.send_error_response(400, 'No content provided')
            
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            url = data.get('url', '')
            
            if not url:
                return self.send_error_response(400, 'No URL provided')
            
            if not YT_DLP_AVAILABLE:
                return self.send_error_response(500, 'yt-dlp not available. Please check dependencies.')
            
            # Get video info
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'nocheckcertificate': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                result = {
                    'title': info.get('title', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'channel': info.get('uploader', 'Unknown'),
                    'views': info.get('view_count', 0),
                    'description': (info.get('description', '')[:200] + '...') if info.get('description') else ''
                }
            
            return self.send_success_response(result)
            
        except json.JSONDecodeError as e:
            return self.send_error_response(400, f'Invalid JSON: {str(e)}')
        except Exception as e:
            error_trace = traceback.format_exc()
            error_msg = f'{str(e)}\n\nTraceback:\n{error_trace}'
            return self.send_error_response(500, error_msg)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def send_success_response(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def send_error_response(self, status_code, error_message):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error_data = {'error': error_message}
        self.wfile.write(json.dumps(error_data).encode('utf-8'))
