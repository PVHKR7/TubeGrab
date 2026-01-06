from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse
import re

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                return self.send_error_response(400, 'No content provided')
            
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            url = data.get('url', '')
            
            if not url:
                return self.send_error_response(400, 'No URL provided')
            
            # Extract video ID
            video_id = self.extract_video_id(url)
            if not video_id:
                return self.send_error_response(400, 'Invalid YouTube URL')
            
            # Use YouTube oEmbed API (no dependencies needed)
            oembed_url = f'https://www.youtube.com/oembed?url={urllib.parse.quote(url)}&format=json'
            
            try:
                with urllib.request.urlopen(oembed_url) as response:
                    oembed_data = json.loads(response.read().decode('utf-8'))
                    
                    result = {
                        'title': oembed_data.get('title', 'Unknown'),
                        'thumbnail': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
                        'duration': 0,  # oEmbed doesn't provide duration
                        'channel': oembed_data.get('author_name', 'Unknown'),
                        'views': 0,  # oEmbed doesn't provide views
                        'description': ''  # oEmbed doesn't provide description
                    }
                    
                    return self.send_success_response(result)
            except urllib.error.HTTPError as e:
                return self.send_error_response(400, f'Failed to fetch video info: {e.code}')
            
        except json.JSONDecodeError as e:
            return self.send_error_response(400, f'Invalid JSON: {str(e)}')
        except Exception as e:
            return self.send_error_response(500, f'Error: {str(e)}')
    
    def extract_video_id(self, url):
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/shorts\/)([^&\n?#]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
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

