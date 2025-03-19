"""
Simple file download functionality.
"""

import urllib.request
import os


def download_file(url, file_path):
    """
    Download a file from a URL.

    Args:
        url: URL to download from
        file_path: Path to save the file to

    Returns:
        The path to the downloaded file

    Raises:
        Exception: If download fails
    """
    try:
        # Download the file
        with urllib.request.urlopen(url) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
    except Exception as e:
        # Clean up partially downloaded file
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise e

    return file_path
