"""
Simple progress bar implementation without external dependencies.
"""

import sys
import time
import shutil


class ProgressBar:
    """A simple progress bar for downloading files."""
    
    def __init__(self, total, unit='B', unit_scale=True, desc=None, ncols=None):
        """
        Initialize a progress bar.
        
        Args:
            total: Total size/items to track
            unit: Unit of measurement (default: 'B' for bytes)
            unit_scale: Whether to scale units automatically (default: True)
            desc: Description to show before the progress bar
            ncols: Width of the progress bar (default: auto-detect)
        """
        self.total = total
        self.unit = unit
        self.unit_scale = unit_scale
        self.desc = desc
        self.current = 0
        self.start_time = time.time()
        self.last_update = 0
        self.ncols = ncols if ncols else self._get_terminal_width() - 1
        self.closed = False
        
        # Minimum time between updates in seconds
        self.min_interval = 0.1
        
    def _get_terminal_width(self):
        """Try to get terminal width, default to 80 if detection fails."""
        try:
            return shutil.get_terminal_size().columns
        except (AttributeError, OSError):
            return 80
            
    def _format_size(self, num):
        """Format a number with appropriate units."""
        if not self.unit_scale:
            return f"{num} {self.unit}"
            
        # Scale units
        for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}{self.unit}"
            num /= 1024.0
        return f"{num:.1f} Y{self.unit}"
    
    def _format_speed(self, speed):
        """Format transfer speed."""
        return f"{self._format_size(speed)}/s"
    
    def _format_time(self, seconds):
        """Format time in a readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes, seconds = divmod(seconds, 60)
        if minutes < 60:
            return f"{int(minutes)}m {int(seconds)}s"
        hours, minutes = divmod(minutes, 60)
        return f"{int(hours)}h {int(minutes)}m"
    
    def update(self, n=1):
        """Update the progress bar by n units."""
        self.current += n
        
        # Only update display if enough time has passed
        if time.time() - self.last_update < self.min_interval:
            return
            
        self.last_update = time.time()
        self._display()
        
    def _display(self):
        """Display the progress bar."""
        if self.closed:
            return
            
        # Clear the line and move to the beginning
        sys.stdout.write('\r')
        
        # Calculate percentage
        percent = 100 * (self.current / self.total) if self.total else 0
        percent = min(percent, 100)  # Cap at 100%
        
        # Calculate elapsed and estimated time
        elapsed = time.time() - self.start_time
        rate = self.current / elapsed if elapsed > 0 else 0
        remaining = (self.total - self.current) / rate if rate > 0 else 0
        
        # Determine the available width for the bar
        desc_str = f"{self.desc}: " if self.desc else ""
        stats_str = f" {self._format_size(self.current)}/{self._format_size(self.total)} " + \
                    f"[{self._format_speed(rate)} ETA: {self._format_time(remaining)}]"
        
        # Available width for the bar itself
        bar_width = self.ncols - len(desc_str) - len(stats_str) - 7  # 7 for percentage and brackets
        bar_width = max(10, bar_width)  # minimum reasonable width
        
        # Create the progress bar
        filled_length = int(bar_width * percent // 100)
        bar = '█' * filled_length + '-' * (bar_width - filled_length)
        
        # Assemble the full line
        line = f"{desc_str}[{bar}] {percent:3.0f}%{stats_str}"
        
        # Truncate if longer than terminal width
        if len(line) > self.ncols:
            line = line[:self.ncols-3] + "..."
            
        sys.stdout.write(line)
        sys.stdout.flush()
    
    def close(self):
        """Complete the progress bar."""
        if not self.closed:
            self.current = self.total
            self._display()
            sys.stdout.write('\n')
            sys.stdout.flush()
            self.closed = True
    
    def __enter__(self):
        """Support context manager protocol."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up on context exit."""
        self.close()


def download_with_progress(url, file_path, desc=None):
    """
    Download a file with a progress bar.
    
    Args:
        url: URL to download from
        file_path: Path to save the file to
        desc: Description to show in the progress bar
    
    Returns:
        The path to the downloaded file
    """
    import urllib.request
    import os
    
    try:
        # Get file size
        with urllib.request.urlopen(url) as response:
            file_size = int(response.headers.get("Content-Length", 0))
            
            # Create a progress bar
            bar = ProgressBar(total=file_size, unit='B', unit_scale=True, desc=desc or f"Downloading {os.path.basename(url)}")
                
            # Download with progress tracking
            with open(file_path, 'wb') as f:
                block_size = 8192
                downloaded = 0
                
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    
                    f.write(buffer)
                    downloaded += len(buffer)
                    bar.update(len(buffer))
                
                bar.close()
    except Exception as e:
        # Clean up partially downloaded file
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise e
        
    return file_path 