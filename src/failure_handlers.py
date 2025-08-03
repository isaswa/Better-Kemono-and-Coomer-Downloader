"""
Helper functions for handling failed downloads tracking.
"""
import os
from typing import Set

FAILED_DOWNLOAD_LOG_FILENAME = "failed_downloads.txt"


def load_failed_downloads(file_path: str = FAILED_DOWNLOAD_LOG_FILENAME) -> Set[str]:
    """Load failed download links from file."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_failed_downloads(
    failed_links: Set[str], file_path: str = FAILED_DOWNLOAD_LOG_FILENAME
) -> None:
    """Save failed download links to file."""
    with open(file_path, "w", encoding="utf-8") as f:
        for link in sorted(failed_links):
            f.write(f"{link}\n")


def add_failed_download(
    link: str, file_path: str = FAILED_DOWNLOAD_LOG_FILENAME
) -> None:
    """Add a failed download link to the file."""
    failed_links = load_failed_downloads(file_path)
    failed_links.add(link)
    save_failed_downloads(failed_links, file_path)


def remove_failed_download(
    link: str, file_path: str = FAILED_DOWNLOAD_LOG_FILENAME
) -> None:
    """Remove a successful download link from the failed downloads file."""
    failed_links = load_failed_downloads(file_path)
    failed_links.discard(link)
    save_failed_downloads(failed_links, file_path)