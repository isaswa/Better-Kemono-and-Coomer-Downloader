import os
import sys
import json
import requests
from datetime import datetime

def save_json(file_path, data):
    """Helper function to save JSON files with UTF-8 encoding and pretty formatting"""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_config(file_path):
    """Load configuration from a JSON file."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}  # Return an empty dictionary if the file doesn't exist

def get_base_config(profile_url):
    """
    Dynamically configure base URLs and directories based on the profile URL domain
    """
    # Extract domain from the profile URL
    domain = profile_url.split('/')[2]
    
    if domain not in ['kemono.su', 'coomer.su']:
        raise ValueError(f"Unsupported domain: {domain}")
    
    BASE_API_URL = f"https://{domain}/api/v1"
    BASE_SERVER = f"https://{domain}"
    BASE_DIR = domain.split('.')[0]  # 'kemono' or 'coomer'
    
    return BASE_API_URL, BASE_SERVER, BASE_DIR

def is_offset(value):
    """Determine if the value is an offset (up to 5 digits) or an ID."""
    try:
        # Try to convert to integer and check the length
        return isinstance(int(value), int) and len(value) <= 5
    except ValueError:
        # If not a number, it's not an offset
        return False

def parse_fetch_mode(fetch_mode, total_count):
    """
    Parse the fetch mode and return the corresponding offsets
    """
    # Special case: fetch all posts
    if fetch_mode == "all":
        return list(range(0, total_count, 50))
    
    # If it's a single number (specific page)
    if fetch_mode.isdigit():
        if is_offset(fetch_mode):
            return [int(fetch_mode)]
        else:
            # If it's a specific ID, return as such
            return ["id:" + fetch_mode]
    
    # If it's a range
    if "-" in fetch_mode:
        start, end = fetch_mode.split("-")
        
        # Handle "start" and "end" specifically
        if start == "start":
            start = 0
        else:
            start = int(start)
        
        if end == "end":
            end = total_count
        else:
            end = int(end)
        
        # If the values are offsets
        if start <= total_count and end <= total_count:
            # Calculate the number of pages needed to cover the range
            # Use ceil to ensure it includes the final page
            import math
            num_pages = math.ceil((end - start) / 50)
            
            # Generate list of offsets
            return [start + i * 50 for i in range(num_pages)]
        
        # If they appear to be IDs, return the ID range
        return ["id:" + str(start) + "-" + str(end)]
    
    raise ValueError(f"Invalid fetch mode: {fetch_mode}")

def get_artist_info(profile_url):
    # Extract service and user_id from URL
    parts = profile_url.split("/")
    service = parts[-3]
    user_id = parts[-1]
    return service, user_id

def fetch_posts(base_api_url, service, user_id, offset=0):
    # Fetch posts from API
    url = f"{base_api_url}/{service}/user/{user_id}/posts-legacy?o={offset}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def save_json_incrementally(file_path, new_posts, start_offset, end_offset):
    # Create a new dictionary with current posts
    data = {
        "total_posts": len(new_posts),
        "posts": new_posts
    }
    
    # Save the new file, replacing the existing one
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def process_posts(posts, previews, attachments_data, page_number, offset, base_server, save_empty_files=True, id_filter=None):
    # Process posts and organize file links
    processed = []
    for post in posts:
        # ID filter if specified
        if id_filter and not id_filter(post['id']):
            continue

        result = {
            "id": post["id"],
            "user": post["user"],
            "service": post["service"],
            "title": post["title"],
            "link": f"{base_server}/{post['service']}/user/{post['user']}/post/{post['id']}",
            "page": page_number,
            "offset": offset,
            "files": []
        }

        # Combine previews and attachments_data into a single list for searching
        all_data = previews + attachments_data

        # Process files in the file field
        if "file" in post and post["file"]:
            matching_data = next(
                (item for item in all_data if item["path"] == post["file"]["path"]),
                None
            )
            if matching_data:
                file_url = f"{matching_data['server']}/data{post['file']['path']}"
                if file_url not in [f["url"] for f in result["files"]]:
                    result["files"].append({"name": post["file"]["name"], "url": file_url})

        # Process files in the attachments field
        for attachment in post.get("attachments", []):
            matching_data = next(
                (item for item in all_data if item["path"] == attachment["path"]),
                None
            )
            if matching_data:
                file_url = f"{matching_data['server']}/data{attachment['path']}"
                if file_url not in [f["url"] for f in result["files"]]:
                    result["files"].append({"name": attachment["name"], "url": file_url})

        # Ignore posts without files if save_empty_files is False
        if not save_empty_files and not result["files"]:
            continue

        processed.append(result)

    return processed

def sanitize_filename(value):
    """Remove characters that can break folder creation."""
    return value.replace("/", "_").replace("\\", "_")

def main():
    # Check command line arguments
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python posts.py <profile_url> [fetch_mode]")
        print("Possible fetch modes:")
        print("- all")
        print("- <page number>")
        print("- start-end")
        print("- <start_id>-<end_id>")
        sys.exit(1)

    # Define profile_url from argument
    profile_url = sys.argv[1]
    
    # Define FETCH_MODE (default to "all" if not specified)
    FETCH_MODE = sys.argv[2] if len(sys.argv) == 3 else "all"
    
    config_file_path = os.path.join("config", "conf.json")

    # Load configuration from JSON file
    config = load_config(config_file_path)

    # Get the value of 'process_from_oldest' from configuration
    SAVE_EMPTY_FILES = config.get("get_empty_posts", False)  # Change to True if you want to save posts without files

    # Configure base URLs dynamically
    BASE_API_URL, BASE_SERVER, BASE_DIR = get_base_config(profile_url)
    
    # Base folder
    base_dir = BASE_DIR
    os.makedirs(base_dir, exist_ok=True)

    # Update the profiles.json file
    profiles_file = os.path.join(base_dir, "profiles.json")
    if os.path.exists(profiles_file):
        with open(profiles_file, "r", encoding="utf-8") as f:
            profiles = json.load(f)
    else:
        profiles = {}

    # Fetch first set of posts for general information
    service, user_id = get_artist_info(profile_url)
    initial_data = fetch_posts(BASE_API_URL, service, user_id, offset=0)
    name = initial_data["props"]["name"]
    count = initial_data["props"]["count"]

    # Save artist information
    artist_info = {
        "id": user_id,
        "name": name,
        "service": service,
        "indexed": initial_data["props"]["artist"]["indexed"],
        "updated": initial_data["props"]["artist"]["updated"],
        "public_id": initial_data["props"]["artist"]["public_id"],
        "relation_id": initial_data["props"]["artist"]["relation_id"],
    }
    profiles[user_id] = artist_info
    save_json(profiles_file, profiles)

    # Sanitize the values
    safe_name = sanitize_filename(name)
    safe_service = sanitize_filename(service)
    safe_user_id = sanitize_filename(user_id)

    # Artist folder
    artist_dir = os.path.join(base_dir, f"{safe_name}-{safe_service}-{safe_user_id}")
    os.makedirs(artist_dir, exist_ok=True)

    # Process fetch mode
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        offsets = parse_fetch_mode(FETCH_MODE, count)
    except ValueError as e:
        print(e)
        return

    # Check if it's a search for specific ID
    id_filter = None
    found_ids = set()
    if isinstance(offsets[0], str) and offsets[0].startswith("id:"):
        # Extract IDs for filter
        id_range = offsets[0].split(":")[1]
        
        if "-" in id_range:
            id1, id2 = map(str, sorted(map(int, id_range.split("-"))))
            id_filter = lambda x: id1 <= str(x) <= id2
        else:
            id_filter = lambda x: x == id_range

        # Redefine offsets to scan all pages
        offsets = list(range(0, count, 50))

    # JSON filename with offset range
    if len(offsets) > 1:
        file_path = os.path.join(artist_dir, f"posts-{offsets[0]}-{offsets[-1]}-{today}.json")
    else:
        file_path = os.path.join(artist_dir, f"posts-{offsets[0]}-{today}.json")

    new_posts= []
    # Main processing
    for offset in offsets:
        page_number = (offset // 50) + 1
        post_data = fetch_posts(BASE_API_URL, service, user_id, offset=offset)
        posts = post_data["results"]
        previews = [item for sublist in post_data.get("result_previews", []) for item in sublist]
        attachments = [item for sublist in post_data.get("result_attachments", []) for item in sublist]

        processed_posts = process_posts(
            posts, 
            previews, 
            attachments, 
            page_number, 
            offset, 
            BASE_SERVER,
            save_empty_files=SAVE_EMPTY_FILES,
            id_filter=id_filter
        )
        new_posts.extend(processed_posts)
        # Save incremental posts to JSON
        if processed_posts:
            save_json_incrementally(file_path, new_posts, offset, offset+50)
            
            # Check if found the desired IDs
            if id_filter:
                found_ids.update(post['id'] for post in processed_posts)
                
                # Check if found both IDs
                if (id1 in found_ids) and (id2 in found_ids):
                    print(f"Found both IDs: {id1} and {id2}")
                    break

    # Print the full path of the generated JSON file
    print(f"{os.path.abspath(file_path)}")

if __name__ == "__main__":
    main()
