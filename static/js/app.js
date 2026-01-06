/**
 * TubeGrab - YouTube Video Downloader
 * Frontend JavaScript Application
 */

class YouTubeDownloader {
    constructor() {
        this.currentDownloadId = null;
        this.progressInterval = null;
        
        // DOM Elements
        this.urlInput = document.getElementById('urlInput');
        this.fetchBtn = document.getElementById('fetchBtn');
        this.videoPreview = document.getElementById('videoPreview');
        this.progressSection = document.getElementById('progressSection');
        this.completedSection = document.getElementById('completedSection');
        this.errorSection = document.getElementById('errorSection');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.saveFileBtn = document.getElementById('saveFileBtn');
        this.newDownloadBtn = document.getElementById('newDownloadBtn');
        this.retryBtn = document.getElementById('retryBtn');
        
        this.init();
    }
    
    init() {
        // Event listeners
        this.fetchBtn.addEventListener('click', () => this.fetchVideoInfo());
        this.downloadBtn.addEventListener('click', () => this.startDownload());
        this.saveFileBtn.addEventListener('click', () => this.saveFile());
        this.newDownloadBtn.addEventListener('click', () => this.reset());
        this.retryBtn.addEventListener('click', () => this.reset());
        
        // Enter key support
        this.urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.fetchVideoInfo();
            }
        });
        
        // Auto-focus input
        this.urlInput.focus();
    }
    
    async fetchVideoInfo() {
        const url = this.urlInput.value.trim();
        
        if (!url) {
            this.showError('Please enter a YouTube URL');
            return;
        }
        
        if (!this.isValidYouTubeUrl(url)) {
            this.showError('Please enter a valid YouTube URL');
            return;
        }
        
        this.setLoading(true);
        this.hideAllSections();
        
        try {
            const response = await fetch('/api/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch video info');
            }
            
            this.displayVideoInfo(data);
            
        } catch (error) {
            this.showError(error.message);
        } finally {
            this.setLoading(false);
        }
    }
    
    isValidYouTubeUrl(url) {
        const patterns = [
            /^(https?:\/\/)?(www\.)?youtube\.com\/watch\?v=[\w-]+/,
            /^(https?:\/\/)?(www\.)?youtube\.com\/shorts\/[\w-]+/,
            /^(https?:\/\/)?youtu\.be\/[\w-]+/,
            /^(https?:\/\/)?(www\.)?youtube\.com\/embed\/[\w-]+/,
            /^(https?:\/\/)?(www\.)?youtube\.com\/v\/[\w-]+/
        ];
        
        return patterns.some(pattern => pattern.test(url));
    }
    
    displayVideoInfo(info) {
        document.getElementById('thumbnail').src = info.thumbnail;
        document.getElementById('videoTitle').textContent = info.title;
        document.getElementById('channel').textContent = info.channel;
        document.getElementById('views').textContent = this.formatViews(info.views);
        document.getElementById('duration').textContent = this.formatDuration(info.duration);
        document.getElementById('description').textContent = info.description || 'No description available';
        
        this.videoPreview.classList.remove('hidden');
    }
    
    formatDuration(seconds) {
        if (!seconds) return '0:00';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
    
    formatViews(views) {
        if (!views) return '0 views';
        
        if (views >= 1000000000) {
            return (views / 1000000000).toFixed(1) + 'B views';
        }
        if (views >= 1000000) {
            return (views / 1000000).toFixed(1) + 'M views';
        }
        if (views >= 1000) {
            return (views / 1000).toFixed(1) + 'K views';
        }
        return views.toLocaleString() + ' views';
    }
    
    formatBytes(bytes) {
        if (!bytes) return '0 B';
        
        const units = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        let size = bytes;
        
        while (size >= 1024 && i < units.length - 1) {
            size /= 1024;
            i++;
        }
        
        return `${size.toFixed(1)} ${units[i]}`;
    }
    
    formatSpeed(bytesPerSecond) {
        if (!bytesPerSecond) return '';
        return `${this.formatBytes(bytesPerSecond)}/s`;
    }
    
    formatETA(seconds) {
        if (!seconds) return '';
        
        if (seconds < 60) {
            return `${Math.round(seconds)}s remaining`;
        }
        
        const minutes = Math.floor(seconds / 60);
        const secs = Math.round(seconds % 60);
        return `${minutes}m ${secs}s remaining`;
    }
    
    async startDownload() {
        const url = this.urlInput.value.trim();
        
        this.downloadBtn.disabled = true;
        this.videoPreview.classList.add('hidden');
        this.progressSection.classList.remove('hidden');
        
        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to start download');
            }
            
            this.currentDownloadId = data.download_id;
            this.startProgressPolling();
            
        } catch (error) {
            this.showError(error.message);
            this.progressSection.classList.add('hidden');
        }
    }
    
    startProgressPolling() {
        this.progressInterval = setInterval(() => this.checkProgress(), 500);
    }
    
    stopProgressPolling() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }
    
    async checkProgress() {
        if (!this.currentDownloadId) return;
        
        try {
            const response = await fetch(`/api/progress/${this.currentDownloadId}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to check progress');
            }
            
            this.updateProgress(data);
            
            if (data.status === 'completed') {
                this.stopProgressPolling();
                this.showCompleted(data);
            } else if (data.status === 'error') {
                this.stopProgressPolling();
                this.showError(data.error || 'Download failed');
            }
            
        } catch (error) {
            console.error('Progress check error:', error);
        }
    }
    
    updateProgress(data) {
        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const statusText = document.getElementById('statusText');
        const downloadSpeed = document.getElementById('downloadSpeed');
        const downloadETA = document.getElementById('downloadETA');
        
        progressBar.style.width = `${data.progress || 0}%`;
        progressPercent.textContent = `${Math.round(data.progress || 0)}%`;
        
        switch (data.status) {
            case 'starting':
                statusText.textContent = 'Preparing download...';
                break;
            case 'downloading':
                statusText.textContent = 'Downloading video...';
                break;
            case 'processing':
                statusText.textContent = 'Processing video...';
                break;
            case 'converting':
                statusText.textContent = 'Converting to MP4...';
                break;
            default:
                statusText.textContent = 'Working...';
        }
        
        downloadSpeed.textContent = this.formatSpeed(data.speed);
        downloadETA.textContent = this.formatETA(data.eta);
    }
    
    showCompleted(data) {
        this.progressSection.classList.add('hidden');
        this.completedSection.classList.remove('hidden');
        
        const filename = data.title || 'video';
        document.getElementById('completedFilename').textContent = filename + '.mp4';
    }
    
    saveFile() {
        if (!this.currentDownloadId) return;
        
        // Create download link
        const link = document.createElement('a');
        link.href = `/api/file/${this.currentDownloadId}`;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    
    showError(message) {
        this.hideAllSections();
        this.errorSection.classList.remove('hidden');
        document.getElementById('errorMessage').textContent = message;
    }
    
    hideAllSections() {
        this.videoPreview.classList.add('hidden');
        this.progressSection.classList.add('hidden');
        this.completedSection.classList.add('hidden');
        this.errorSection.classList.add('hidden');
    }
    
    reset() {
        // Cleanup old download
        if (this.currentDownloadId) {
            fetch(`/api/cleanup/${this.currentDownloadId}`, { method: 'DELETE' })
                .catch(() => {});
        }
        
        this.stopProgressPolling();
        this.currentDownloadId = null;
        
        // Reset UI
        this.hideAllSections();
        this.urlInput.value = '';
        this.downloadBtn.disabled = false;
        
        // Reset progress
        document.getElementById('progressBar').style.width = '0%';
        document.getElementById('progressPercent').textContent = '0%';
        document.getElementById('downloadSpeed').textContent = '';
        document.getElementById('downloadETA').textContent = '';
        
        this.urlInput.focus();
    }
    
    setLoading(isLoading) {
        this.fetchBtn.disabled = isLoading;
        this.urlInput.disabled = isLoading;
        
        const btnText = this.fetchBtn.querySelector('.btn-text');
        if (isLoading) {
            btnText.textContent = 'Loading...';
        } else {
            btnText.textContent = 'Fetch';
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new YouTubeDownloader();
});

