import os
import json
import re
import time
import requests
import signal
from typing import Dict, List, Tuple, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import sys
from tqdm import tqdm

from .config import load_config, Config
from .format_helpers import sanitize_filename, sanitize_title
from .failure_handlers import add_failed_download, remove_failed_download


def download_file(file_url: str, save_path: str) -> Tuple[bool, Optional[str]]:
    """
    Download a file from a URL and save it to the specified path.
    Returns (success, error_message) tuple.
    """
    try:
        response = requests.get(file_url, stream=True)
        response.raise_for_status()

        # Get total file size
        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192

        # Create progress bar
        filename = os.path.basename(save_path)
        with tqdm(
            total=total_size, unit="B", unit_scale=True, desc=filename
        ) as progress_bar:
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        progress_bar.update(len(chunk))
                        f.write(chunk)

        # Verify download completeness
        if total_size != 0 and progress_bar.n != total_size:
            error_msg = f"Incomplete download: {progress_bar.n}/{total_size} bytes"
            print(f"⚠️ {error_msg}")
            add_failed_download(file_url)
            return False, error_msg

        # Download successful, remove from failed downloads if it was there
        remove_failed_download(file_url)
        return True, None

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error: {str(e)}"
        print(f"❌ Download failed {file_url}: {error_msg}")
        add_failed_download(file_url)
        return False, error_msg
    except IOError as e:
        error_msg = f"File I/O error: {str(e)}"
        print(f"❌ Failed to save file {save_path}: {error_msg}")
        add_failed_download(file_url)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ Download failed {file_url}: {error_msg}")
        add_failed_download(file_url)
        return False, error_msg


def process_post(
    post: Dict[str, Any], base_folder: str, config: Config
) -> Dict[str, Any]:
    """
    Process a single post, downloading its files.
    Returns statistics about the download.
    """
    post_id = post.get("id")

    # Determine folder name based on config
    if config.post_folder_name == "title":
        post_title = post.get("title", "").strip()
        if post_title:
            # Sanitize title for folder name
            sanitized_title = sanitize_title(post_title)[:50]  # Limit length
            folder_name = f"{post_id}_{sanitized_title}"
        else:
            folder_name = post_id
    else:
        folder_name = post_id

    post_folder = os.path.join(base_folder, folder_name)
    os.makedirs(post_folder, exist_ok=True)

    print(f"\nProcessing post ID {post_id}")
    if config.post_folder_name == "title" and post.get("title"):
        print(f"Title: {post.get('title')}")

    # Prepare downloads for this post
    downloads: List[Tuple[str, str]] = []
    for file_index, file in enumerate(post.get("files", []), start=1):
        original_name = file.get("name")
        file_url = file.get("url")
        sanitized_name = sanitize_filename(original_name)
        new_filename = f"{file_index}-{sanitized_name}"
        file_save_path = os.path.join(post_folder, new_filename)
        downloads.append((file_url, file_save_path))

    # Track download results
    total_files = len(downloads)
    successful = 0
    failed = []

    # Download files using ThreadPoolExecutor
    print(f"Downloading {total_files} files...")
    
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all downloads and collect futures
            futures = []
            for file_url, file_save_path in downloads:
                future = executor.submit(download_file, file_url, file_save_path)
                futures.append((future, file_url, file_save_path))

            # Wait for all downloads to complete
            for future, file_url, file_save_path in futures:
                try:
                    success, error_msg = future.result()
                    if success:
                        successful += 1
                    else:
                        failed.append(
                            {"url": file_url, "path": file_save_path, "error": error_msg}
                        )
                except KeyboardInterrupt:
                    print("\n⚠️ Download interrupted by user (Ctrl+C)")
                    print("Cancelling remaining downloads...")
                    # Cancel remaining futures
                    for remaining_future, _, _ in futures:
                        remaining_future.cancel()
                    break
    except KeyboardInterrupt:
        print("\n⚠️ Download interrupted by user (Ctrl+C)")
        print("Cancelling all downloads...")
        # The executor context manager will handle cleanup

    # Print summary
    if failed:
        print(
            f"⚠️ Post {post_id} completed with errors: {successful}/{total_files} files downloaded"
        )
        for fail in failed:
            print(f"   ❌ Failed: {os.path.basename(fail['path'])}")
    else:
        print(f"✅ Post {post_id} completed: all {successful} files downloaded")

    return {
        "post_id": post_id,
        "total_files": total_files,
        "successful": successful,
        "failed": failed,
    }


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
        process_post(post, base_folder, config)
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
