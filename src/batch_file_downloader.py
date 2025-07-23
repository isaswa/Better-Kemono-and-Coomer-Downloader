import os
import json
import re
import time
import requests
from typing import Dict, List, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
import sys

from .config import load_config, Config


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters and replacing spaces with underscores."""
    filename = re.sub(r"[\\/*?\"<>|]", "", filename)
    return filename.replace(" ", "_")


def download_file(file_url: str, save_path: str) -> None:
    """Download a file from a URL and save it to the specified path."""
    try:
        response = requests.get(file_url, stream=True)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        print(f"Download failed {file_url}: {e}")


def process_post(post: Dict[str, Any], base_folder: str) -> None:
    """Process a single post, downloading its files."""
    post_id = post.get("id")
    post_folder = os.path.join(base_folder, post_id)
    os.makedirs(post_folder, exist_ok=True)

    print(f"Processing post ID {post_id}")

    # Prepare downloads for this post
    downloads: List[Tuple[str, str]] = []
    for file_index, file in enumerate(post.get("files", []), start=1):
        original_name = file.get("name")
        file_url = file.get("url")
        sanitized_name = sanitize_filename(original_name)
        new_filename = f"{file_index}-{sanitized_name}"
        file_save_path = os.path.join(post_folder, new_filename)
        downloads.append((file_url, file_save_path))

    # Download files using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as executor:
        for file_url, file_save_path in downloads:
            executor.submit(download_file, file_url, file_save_path)

    print(f"Post {post_id} downloaded")


def batch_download_posts(json_file_path: str, post_id: str = None) -> None:
    """
    Download posts from JSON file in batch mode.

    :param json_file_path: Path to the JSON file containing post data
    :param post_id: Optional specific post ID to download, if None downloads all posts
    """
    # Check if the file exists
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"The file '{json_file_path}' was not found.")

    # Load the JSON file
    with open(json_file_path, "r", encoding="utf-8") as f:
        profile_metadata = json.load(f)

    # Base folder for posts
    base_folder = os.path.join(os.path.dirname(json_file_path), "posts")
    os.makedirs(base_folder, exist_ok=True)

    # Load configuration from JSON file
    config = load_config()

    # Get the value of 'process_from_oldest' from configuration
    process_from_oldest = config.process_from_oldest

    posts = profile_metadata.get("posts", [])

    # Filter for specific post if post_id is provided
    if post_id:
        posts = [post for post in posts if post.get("id") == post_id]
        if not posts:
            print(f"Post ID {post_id} not found in JSON file")
            return
    else:
        # Apply ordering if processing all posts
        if process_from_oldest:
            posts = list(reversed(posts))

    # Process each post sequentially
    for post_index, post in enumerate(posts, start=1):
        process_post(post, base_folder)
        time.sleep(2)  # Wait 2 seconds between posts


def main() -> None:
    """Command line interface for backward compatibility"""
    if len(sys.argv) < 2:
        print("Usage: python batch_file_downloader.py {json_path} [post_id]")
        sys.exit(1)

    json_file_path = sys.argv[1]
    post_id = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        batch_download_posts(json_file_path, post_id)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
