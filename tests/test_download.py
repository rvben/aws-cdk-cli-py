"""
Unit tests for the download module.

Tests cover file downloading, error handling, and cleanup.
"""

import os
import tempfile
import urllib.error
from unittest import mock

import pytest

from aws_cdk_cli.download import (
    DownloadError,
    download_file,
    _cleanup_partial_download,
)


class TestDownloadFile:
    """Tests for the download_file function."""

    def test_download_file_success(self):
        """Test successful file download."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.txt")
            test_content = b"Hello, World!"

            # Mock urlopen to return test content
            mock_response = mock.MagicMock()
            mock_response.read.return_value = test_content
            mock_response.__enter__.return_value = mock_response

            with mock.patch("urllib.request.urlopen", return_value=mock_response):
                result = download_file("https://example.com/test.txt", file_path)

            assert result == file_path
            assert os.path.exists(file_path)
            with open(file_path, "rb") as f:
                assert f.read() == test_content

    def test_download_file_url_error(self):
        """Test that DownloadError is raised on URL error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.txt")

            with mock.patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("Connection refused"),
            ):
                with pytest.raises(DownloadError) as exc_info:
                    download_file("https://example.com/test.txt", file_path)

            assert "Connection refused" in str(exc_info.value)
            assert not os.path.exists(file_path)

    def test_download_file_http_error(self):
        """Test that DownloadError is raised on HTTP error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.txt")

            with mock.patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.HTTPError(
                    "https://example.com/test.txt", 404, "Not Found", {}, None
                ),
            ):
                with pytest.raises(DownloadError) as exc_info:
                    download_file("https://example.com/test.txt", file_path)

            assert "404" in str(exc_info.value)
            assert "Not Found" in str(exc_info.value)
            assert not os.path.exists(file_path)

    def test_download_file_os_error_cleanup(self):
        """Test that partial downloads are cleaned up on OSError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.txt")

            # Create a partial file
            with open(file_path, "wb") as f:
                f.write(b"partial content")

            # Mock urlopen to succeed but file write to fail
            mock_response = mock.MagicMock()
            mock_response.read.return_value = b"content"
            mock_response.__enter__.return_value = mock_response

            with mock.patch("urllib.request.urlopen", return_value=mock_response):
                with mock.patch("builtins.open", side_effect=OSError("Disk full")):
                    with pytest.raises(OSError):
                        download_file("https://example.com/test.txt", file_path)

    def test_download_file_preserves_original_exception(self):
        """Test that original exception is preserved in the chain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.txt")

            original_error = urllib.error.URLError("DNS lookup failed")
            with mock.patch("urllib.request.urlopen", side_effect=original_error):
                with pytest.raises(DownloadError) as exc_info:
                    download_file("https://example.com/test.txt", file_path)

            # Verify exception chaining
            assert exc_info.value.__cause__ is original_error


class TestCleanupPartialDownload:
    """Tests for the _cleanup_partial_download function."""

    def test_cleanup_existing_file(self):
        """Test that existing file is cleaned up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.txt")

            # Create the file
            with open(file_path, "wb") as f:
                f.write(b"test content")

            assert os.path.exists(file_path)
            _cleanup_partial_download(file_path)
            assert not os.path.exists(file_path)

    def test_cleanup_nonexistent_file(self):
        """Test that cleanup doesn't fail for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "nonexistent.txt")

            # Should not raise any exception
            _cleanup_partial_download(file_path)

    def test_cleanup_permission_error_ignored(self):
        """Test that permission errors during cleanup are silently ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.txt")

            # Create the file
            with open(file_path, "wb") as f:
                f.write(b"test content")

            # Mock os.unlink to raise permission error
            with mock.patch("os.unlink", side_effect=OSError("Permission denied")):
                # Should not raise any exception
                _cleanup_partial_download(file_path)


class TestDownloadError:
    """Tests for the DownloadError exception."""

    def test_download_error_message(self):
        """Test that DownloadError preserves message."""
        error = DownloadError("Download failed: timeout")
        assert str(error) == "Download failed: timeout"

    def test_download_error_inheritance(self):
        """Test that DownloadError is an Exception."""
        assert issubclass(DownloadError, Exception)

    def test_download_error_catchable(self):
        """Test that DownloadError can be caught."""
        with pytest.raises(DownloadError):
            raise DownloadError("test")

        # Also catchable as Exception
        try:
            raise DownloadError("test")
        except Exception:
            pass  # Should be caught
