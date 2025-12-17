"""
Simple file download functionality.
"""

import os
import urllib.error
import urllib.request


class DownloadError(Exception):
    """Raised when a file download fails."""

    pass


def download_file(url: str, file_path: str) -> str:
    """
    Download a file from a URL.

    Args:
        url: URL to download from
        file_path: Path to save the file to

    Returns:
        The path to the downloaded file

    Raises:
        DownloadError: If download fails due to network issues
        OSError: If file cannot be written
    """
    try:
        with urllib.request.urlopen(url) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
    except urllib.error.URLError as e:
        # Network-related errors (DNS, connection refused, timeout, etc.)
        _cleanup_partial_download(file_path)
        raise DownloadError(f"Failed to download {url}: {e}") from e
    except urllib.error.HTTPError as e:
        # HTTP errors (404, 500, etc.)
        _cleanup_partial_download(file_path)
        raise DownloadError(f"HTTP error downloading {url}: {e.code} {e.reason}") from e
    except OSError:
        # File system errors (permission denied, disk full, etc.)
        _cleanup_partial_download(file_path)
        raise  # Re-raise OSError as-is for caller to handle

    return file_path


def _cleanup_partial_download(file_path: str) -> None:
    """Remove a partially downloaded file if it exists."""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except OSError:
        pass  # Best effort cleanup
