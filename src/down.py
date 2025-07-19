import os
import json
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor
import sys

def load_config(file_path):
    """Load configuration from a JSON file."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}  # Return an empty dictionary if the file doesn't exist

def sanitize_filename(filename):
    """Sanitize filename by removing invalid characters and replacing spaces with underscores."""
    filename = re.sub(r'[\\/*?\"<>|]', '', filename)
    return filename.replace(' ', '_')

def download_file(file_url, save_path):
    """Download a file from a URL and save it to the specified path."""
    try:
        response = requests.get(file_url, stream=True)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        print(f"Download failed {file_url}: {e}")

def process_post(post, base_folder):
    """Process a single post, downloading its files."""
    post_id = post.get("id")
    post_folder = os.path.join(base_folder, post_id)
    os.makedirs(post_folder, exist_ok=True)

    print(f"Processing post ID {post_id}")

    # Prepare downloads for this post
    downloads = []
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

def main():
    if len(sys.argv) < 2:
        print("Usage: python down.py {json_path}")
        sys.exit(1)

    # Get the JSON file path from command line argument
    json_file_path = sys.argv[1]

    # Check if the file exists
    if not os.path.exists(json_file_path):
        print(f"Error: The file '{json_file_path}' was not found.")
        sys.exit(1)

    # Load the JSON file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Base folder for posts
    base_folder = os.path.join(os.path.dirname(json_file_path), "posts")
    os.makedirs(base_folder, exist_ok=True)

    # Path to configuration file
    config_file_path = os.path.join("config", "conf.json")

    # Load configuration from JSON file
    config = load_config(config_file_path)

    # Get the value of 'process_from_oldest' from configuration
    process_from_oldest = config.get("process_from_oldest", True)  # Default value is True

    posts = data.get("posts", [])
    if process_from_oldest:
        posts = reversed(posts)

    # Process each post sequentially
    for post_index, post in enumerate(posts, start=1):
        process_post(post, base_folder)
        time.sleep(2)  # Wait 2 seconds between posts

if __name__ == "__main__":
    main()
