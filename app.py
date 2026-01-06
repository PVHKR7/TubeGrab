"""
TubeGrab - YouTube Video Downloader
A modern web app to download YouTube videos in highest quality
https://github.com/yourusername/tubegrab
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import subprocess
import shutil
import os
import uuid
import threading
import time
import re
import glob

app = Flask(__name__)
CORS(app)

# Configuration - can be overridden with environment variables
# Default to a "downloads" directory inside the project (writable on Render)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
DOWNLOAD_FOLDER = os.environ.get('TUBEGRAB_DOWNLOAD_FOLDER', DEFAULT_DOWNLOAD_FOLDER)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Auto-detect ffmpeg location
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', shutil.which('ffmpeg') or 'ffmpeg')

# Track download progress
downloads = {}


def get_video_info(url):
    """Get video information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'nocheckcertificate': True,
        # Use browser cookies to bypass bot detection
        'cookiesfrombrowser': ('chrome',),  # Try Chrome first, falls back to others
        # Additional options to avoid bot detection
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],  # Skip some formats that might trigger detection
            }
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'channel': info.get('uploader', 'Unknown'),
                'views': info.get('view_count', 0),
                'description': info.get('description', '')[:200] + '...' if info.get('description') else ''
            }
    except Exception as e:
        # If cookies fail, try without cookies but with different user agent
        ydl_opts_fallback = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'channel': info.get('uploader', 'Unknown'),
                'views': info.get('view_count', 0),
                'description': info.get('description', '')[:200] + '...' if info.get('description') else ''
            }


def convert_to_mp4(input_file, download_id):
    """Convert video to MP4 format using FFmpeg"""
    if input_file.endswith('.mp4'):
        return input_file  # Already MP4
    
    # Create output filename with .mp4 extension
    base_name = os.path.splitext(input_file)[0]
    output_file = base_name + '.mp4'
    
    # Check if output file already exists - if so, add a number suffix
    if os.path.exists(output_file):
        counter = 1
        while os.path.exists(output_file):
            output_file = f'{base_name} ({counter}).mp4'
            counter += 1
    
    try:
        # Use FFmpeg to convert/remux to MP4
        # -c copy tries to copy streams without re-encoding (fast)
        # If that fails, we'll re-encode
        cmd = [
            FFMPEG_PATH,
            '-i', input_file,
            '-c', 'copy',  # Try to copy streams without re-encoding
            '-y',  # Overwrite output file (safe now since we checked for duplicates)
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and os.path.exists(output_file):
            # Remove original file
            os.remove(input_file)
            return output_file
        else:
            # If copy failed, try re-encoding
            cmd = [
                FFMPEG_PATH,
                '-i', input_file,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-y',
                output_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            
            if result.returncode == 0 and os.path.exists(output_file):
                os.remove(input_file)
                return output_file
    except Exception:
        pass
    
    return input_file  # Return original if conversion failed


def download_video(url, download_id):
    """Download video using yt-dlp command line (works better for JS challenges)"""
    try:
        downloads[download_id]['status'] = 'downloading'
        
        # Output template - use YouTube title only, no download_id prefix
        # Add number suffix if file already exists to prevent overwriting
        output_template = os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')
        
        # Check if we need to add a number suffix to avoid overwriting
        # We'll let yt-dlp handle this with its built-in duplicate handling
        # But we'll add --no-overwrites to be safe (though yt-dlp handles duplicates by default)
        
        # Use yt-dlp command line - works better for solving YouTube's JS challenges
        ffmpeg_dir = os.path.dirname(FFMPEG_PATH) if FFMPEG_PATH else ''
        cmd = [
            'yt-dlp',
            '--no-check-certificate',
            '--cookies-from-browser', 'chrome',  # Use Chrome cookies to bypass bot detection
            '-o', output_template,
            '--newline',  # Print progress on new lines for parsing
            '--remote-components', 'ejs:github',  # Enable JS challenge solver
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--no-overwrites',  # Don't overwrite existing files
            '--restrict-filenames',  # Ensure safe filenames
            url
        ]
        
        # Add ffmpeg location if available
        if ffmpeg_dir:
            # Insert after --no-check-certificate
            cmd.insert(2, '--ffmpeg-location')
            cmd.insert(3, ffmpeg_dir)
        
        # Run yt-dlp and capture output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        title = 'video'
        
        # Parse output for progress
        for line in process.stdout:
            line = line.strip()
            
            # Extract title from destination line
            if 'Destination:' in line or '[download] Destination:' in line:
                # Extract title from filename (format: title.ext)
                # Remove the download folder path and get just the filename
                if DOWNLOAD_FOLDER in line:
                    filename_part = line.split(DOWNLOAD_FOLDER)[-1].strip()
                    # Remove leading slash if present
                    filename_part = filename_part.lstrip('/').lstrip('\\')
                    # Extract title (everything before the extension)
                    match = re.search(r'(.+?)\.(mp4|webm|mkv|m4a|f\d+\.)', filename_part)
                    if match:
                        title = match.group(1)
                        downloads[download_id]['title'] = title
            
            # Parse download progress
            if '[download]' in line and '%' in line:
                match = re.search(r'(\d+\.?\d*)%', line)
                if match:
                    percent = float(match.group(1))
                    downloads[download_id]['progress'] = percent
            
            # Detect merge
            if '[Merger]' in line:
                downloads[download_id]['status'] = 'processing'
                downloads[download_id]['progress'] = 100
        
        process.wait()
        
        # Find the final merged file - look for the most recently created video file
        time.sleep(2)  # Give it a bit more time to finish
        
        filename = None
        largest_size = 0
        most_recent_time = 0
        
        # Get the title from downloads dict if available
        video_title = downloads[download_id].get('title', 'video')
        
        # Find the most recently created video file (should be the one we just downloaded)
        for f in os.listdir(DOWNLOAD_FOLDER):
            filepath = os.path.join(DOWNLOAD_FOLDER, f)
            
            # Skip partial and intermediate files
            if '.part' in f or re.search(r'\.f\d+\.', f):
                continue
            # Skip files that start with download_id (old format)
            if f.startswith(download_id):
                continue
            # Skip if it's already an MP4 (might be from previous conversion)
            if f.endswith('.mp4') and os.path.getmtime(filepath) < time.time() - 10:
                continue
            
            # Accept video formats
            if f.endswith(('.mp4', '.webm', '.mkv', '.m4a')):
                size = os.path.getsize(filepath)
                file_time = os.path.getmtime(filepath)
                
                # Prefer the most recently created file that's large enough
                if size > 1000000 and file_time > most_recent_time:  # > 1MB and most recent
                    most_recent_time = file_time
                    largest_size = size
                    filename = filepath
        
        if filename and os.path.exists(filename) and largest_size > 1000000:  # > 1MB
            # Convert to MP4 if not already
            if not filename.endswith('.mp4'):
                downloads[download_id]['status'] = 'converting'
                filename = convert_to_mp4(filename, download_id)
            
            downloads[download_id]['status'] = 'completed'
            downloads[download_id]['filename'] = filename
            downloads[download_id]['title'] = title
        else:
            files_found = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(download_id)]
            downloads[download_id]['status'] = 'error'
            downloads[download_id]['error'] = f'Merge may have failed. Files found: {files_found}'
            
    except Exception as e:
        downloads[download_id]['status'] = 'error'
        downloads[download_id]['error'] = str(e)


@app.route('/')
def index():
    """Serve the frontend"""
    return render_template('index.html')


@app.route('/api/info', methods=['POST'])
def video_info():
    """Get video information"""
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/download', methods=['POST'])
def start_download():
    """Start a video download"""
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    download_id = str(uuid.uuid4())[:8]
    downloads[download_id] = {
        'status': 'starting',
        'progress': 0,
        'url': url,
        'error': None,
        'filename': None
    }
    
    # Start download in background thread
    thread = threading.Thread(target=download_video, args=(url, download_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'download_id': download_id})


@app.route('/api/progress/<download_id>')
def check_progress(download_id):
    """Check download progress"""
    if download_id not in downloads:
        return jsonify({'error': 'Download not found'}), 404
    
    return jsonify(downloads[download_id])


@app.route('/api/file/<download_id>')
def get_file(download_id):
    """Download the completed file"""
    if download_id not in downloads:
        return jsonify({'error': 'Download not found'}), 404
    
    download = downloads[download_id]
    
    if download['status'] != 'completed':
        return jsonify({'error': 'Download not completed'}), 400
    
    filename = download.get('filename')
    if not filename or not os.path.exists(filename):
        return jsonify({'error': 'File not found'}), 404
    
    # Get the original filename without path
    original_filename = os.path.basename(filename)
    # If it's already .mp4, use it as-is, otherwise change extension to .mp4
    if original_filename.endswith('.mp4'):
        download_name = original_filename
    else:
        # Change extension to .mp4 while keeping the original title
        base_name = os.path.splitext(original_filename)[0]
        download_name = f'{base_name}.mp4'
    
    # Always serve as MP4 since we convert everything to MP4
    return send_file(
        filename,
        as_attachment=True,
        download_name=download_name,
        mimetype='video/mp4'
    )


@app.route('/api/cleanup/<download_id>', methods=['DELETE'])
def cleanup(download_id):
    """Clean up downloaded file"""
    if download_id in downloads:
        filename = downloads[download_id].get('filename')
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass
        del downloads[download_id]
    
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, port=5001)

