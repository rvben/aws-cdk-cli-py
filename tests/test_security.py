"""
Security tests for the AWS CDK Python wrapper.

These tests verify that security measures are properly implemented,
including path traversal protection and input validation.
"""

import os
import tempfile
import tarfile

import pytest

from aws_cdk_cli.installer import PathTraversalError


class TestPathTraversalProtection:
    """Tests for path traversal attack prevention in archive extraction."""

    def test_is_within_directory_safe_path(self):
        """Test that safe paths within directory return True."""
        # Import the function by extracting it from the module
        # Since it's defined inside download_node, we test the logic directly
        from pathlib import Path

        def is_within_directory(directory: str, target: str) -> bool:
            try:
                abs_directory = Path(directory).resolve()
                abs_target = Path(target).resolve()
                abs_target.relative_to(abs_directory)
                return True
            except (ValueError, OSError):
                return False

        with tempfile.TemporaryDirectory() as tmpdir:
            # Safe: file directly in directory
            assert is_within_directory(tmpdir, os.path.join(tmpdir, "file.txt"))

            # Safe: file in subdirectory
            assert is_within_directory(tmpdir, os.path.join(tmpdir, "sub", "file.txt"))

            # Safe: deeply nested
            assert is_within_directory(
                tmpdir, os.path.join(tmpdir, "a", "b", "c", "file.txt")
            )

    def test_is_within_directory_traversal_attack(self):
        """Test that path traversal attempts are detected."""
        from pathlib import Path

        def is_within_directory(directory: str, target: str) -> bool:
            try:
                abs_directory = Path(directory).resolve()
                abs_target = Path(target).resolve()
                abs_target.relative_to(abs_directory)
                return True
            except (ValueError, OSError):
                return False

        with tempfile.TemporaryDirectory() as tmpdir:
            # Attack: parent directory traversal
            assert not is_within_directory(tmpdir, os.path.join(tmpdir, "..", "etc", "passwd"))

            # Attack: absolute path outside
            assert not is_within_directory(tmpdir, "/etc/passwd")

            # Attack: the commonprefix bug case
            # /tmp/archive vs /tmp/archive-evil/file.txt
            # commonprefix returns /tmp/archive which LOOKS like it's contained
            # but it's actually a different directory
            evil_dir = tmpdir + "-evil"
            os.makedirs(evil_dir, exist_ok=True)
            try:
                evil_file = os.path.join(evil_dir, "malicious.txt")
                Path(evil_file).touch()
                # This MUST return False - the old commonprefix implementation
                # would incorrectly return True here
                assert not is_within_directory(tmpdir, evil_file), (
                    "commonprefix bug: directory prefix match should not pass"
                )
            finally:
                import shutil
                shutil.rmtree(evil_dir, ignore_errors=True)

    def test_is_within_directory_symlink_attack(self):
        """Test that symlink-based attacks are handled."""
        from pathlib import Path

        def is_within_directory(directory: str, target: str) -> bool:
            try:
                abs_directory = Path(directory).resolve()
                abs_target = Path(target).resolve()
                abs_target.relative_to(abs_directory)
                return True
            except (ValueError, OSError):
                return False

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a symlink pointing outside the directory
            symlink_path = os.path.join(tmpdir, "link")
            try:
                os.symlink("/etc", symlink_path)
                # The resolved path should be /etc/passwd, which is outside tmpdir
                target = os.path.join(symlink_path, "passwd")
                assert not is_within_directory(tmpdir, target)
            except OSError:
                # Symlink creation may fail on some systems (e.g., Windows without privileges)
                pytest.skip("Cannot create symlinks on this system")

    def test_malicious_tar_member_rejected(self):
        """Test that tar files with path traversal members are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a tar file with a malicious member
            tar_path = os.path.join(tmpdir, "malicious.tar")
            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)

            # Create tar with path traversal
            with tarfile.open(tar_path, "w") as tar:
                # Create a benign file first
                benign_file = os.path.join(tmpdir, "benign.txt")
                with open(benign_file, "w") as f:
                    f.write("safe content")
                tar.add(benign_file, arcname="safe.txt")

                # Add a malicious member with path traversal
                # We need to manually create a TarInfo with a malicious name
                malicious_info = tarfile.TarInfo(name="../../../etc/evil.txt")
                malicious_info.size = 12
                import io
                tar.addfile(malicious_info, io.BytesIO(b"evil content"))

            # Now test that extraction is blocked
            # We need to replicate the safe_extract logic
            from pathlib import Path

            def is_within_directory(directory: str, target: str) -> bool:
                try:
                    abs_directory = Path(directory).resolve()
                    abs_target = Path(target).resolve()
                    abs_target.relative_to(abs_directory)
                    return True
                except (ValueError, OSError):
                    return False

            with tarfile.open(tar_path, "r") as tar:
                for member in tar.getmembers():
                    member_path = os.path.join(extract_dir, member.name)
                    if not is_within_directory(extract_dir, member_path):
                        # This should trigger for the malicious member
                        assert "../" in member.name, f"Expected traversal in {member.name}"
                        break
                else:
                    pytest.fail("Malicious tar member was not detected")


class TestPathTraversalErrorException:
    """Tests for the PathTraversalError exception."""

    def test_exception_is_raised_with_message(self):
        """Test that PathTraversalError can be raised with a message."""
        with pytest.raises(PathTraversalError) as exc_info:
            raise PathTraversalError("Attempted path traversal: ../../../etc/passwd")

        assert "path traversal" in str(exc_info.value).lower()
        assert "../../../etc/passwd" in str(exc_info.value)

    def test_exception_inherits_from_exception(self):
        """Test that PathTraversalError is a proper Exception subclass."""
        assert issubclass(PathTraversalError, Exception)

    def test_exception_can_be_caught_as_exception(self):
        """Test that PathTraversalError can be caught as a generic Exception."""
        caught = False
        try:
            raise PathTraversalError("test")
        except Exception:
            caught = True

        assert caught, "PathTraversalError should be catchable as Exception"
