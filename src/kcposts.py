import os
import sys
import json
import requests
import re
from typing import Dict, List, Tuple, Optional, Any, Set
from tqdm import tqdm
from html.parser import HTMLParser
from urllib.parse import quote, urlparse, unquote


def load_config(config_path: str = "config/conf.json") -> Dict[str, Any]:
    """
    Load configurations from conf.json file
    If the file doesn't exist, return default configurations
    """
    try:
        with open(config_path, "r") as file:
            config = json.load(file)
        return {
            # Boolean fields
            "save_info": config.get("save_info", False),
            "save_preview": config.get("save_preview", False),
            "skip_existed_files": config.get("skip_existed_files", True),
            # ---
            # "md" or "txt"
            "post_info": config.get("post_info", "md"),
            # "id" or "title"
            "post_folder_name": config.get("post_folder_name", "id"),
        }
    # Default configurations if file doesn't exist
    except FileNotFoundError:
        return {
            "save_info": False,
            "save_preview": False,
            "skip_existed_files": True,
            # ---
            "post_info": "md",
            "post_folder_name": "id",
        }
    except json.JSONDecodeError:
        print(f"Error decoding {config_path}. Using default settings.")
        return {
            "save_info": False,
            "save_preview": False,
            "skip_existed_files": True,
            # ---
            "post_info": "md",
            "post_folder_name": "id",
        }


def ensure_directory(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def load_profiles(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def save_profiles(path: str, profiles: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(profiles, file, indent=4)


def extract_data_from_link(link: str) -> Tuple[str, str, str, str]:
    """
    Extract service, user_id, and post_id from both kemono.su and coomer.su links
    """
    # Pattern for both kemono.su and coomer.su
    match = re.match(
        r"https://(kemono|coomer)\.su/([^/]+)/user/([^/]+)/post/([^/]+)", link
    )
    if not match:
        raise ValueError("Invalid link format")

    # Unpack the match groups
    domain, service, user_id, post_id = match.groups()

    return domain, service, user_id, post_id


def get_api_base_url(domain: str) -> str:
    """
    Dynamically generate API base URL based on the domain
    """
    return f"https://{domain}.su/api/v1/"


def fetch_profile(domain: str, service: str, user_id: str) -> Dict[str, Any]:
    """
    Fetch user profile with dynamic domain support
    """
    api_base_url = get_api_base_url(domain)
    url = f"{api_base_url}{service}/user/{user_id}/profile"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def fetch_post(domain: str, service: str, user_id: str, post_id: str) -> Dict[str, Any]:
    """
    Fetch post data with dynamic domain support
    """
    api_base_url = get_api_base_url(domain)
    url = f"{api_base_url}{service}/user/{user_id}/post/{post_id}"
    response = requests.get(url)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.json()


class HTMLToMarkdown(HTMLParser):
    """Parser to convert HTML content to Markdown and plain text."""

    def __init__(self) -> None:
        super().__init__()
        self.result: List[str] = []
        self.raw_content: List[str] = []
        self.current_link: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href", "")
            self.current_link = href
            self.result.append("[")  # Markdown link opening
        elif tag in ("p", "br"):
            self.result.append("\n")  # New line for Markdown
        self.raw_content.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current_link:
            self.result.append(f"]({self.current_link})")
            self.current_link = None
        self.raw_content.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        # Append visible text to the Markdown result
        if self.current_link:
            self.result.append(data.strip())
        else:
            self.result.append(data.strip())
        # Append all raw content for reference
        self.raw_content.append(data)

    def get_markdown(self) -> str:
        """Return the cleaned Markdown content."""
        return "".join(self.result).strip()

    def get_raw_content(self) -> str:
        """Return the raw HTML content."""
        return "".join(self.raw_content).strip()


def clean_html_to_text(html: str) -> Tuple[str, str]:
    """Converts HTML to Markdown and extracts raw HTML."""
    parser = HTMLToMarkdown()
    parser.feed(html)
    return parser.get_markdown(), parser.get_raw_content()


def adapt_file_name(name: str) -> str:
    """
    Sanitize file name by removing special characters and reducing its size.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9]", "_", unquote(name).split(".")[0])
    return sanitized[:50]  # Limit length to 50 characters


def download_files(
    file_list: List[Tuple[str, str]], folder_path: str, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Download files from a list of URLs and save them with unique names in the folder_path.

    :param file_list: List of tuples with original name and URL [(name, url), ...]
    :param folder_path: Directory to save downloaded files
    :param config: Configuration dictionary
    :return: Dictionary with download results {'success_count': int, 'failed_files': [{'name': str, 'url': str, 'error': str}]}
    """
    seen_files: Set[str] = set()
    failed_files: List[Dict[str, str]] = []
    success_count: int = 0

    for idx, (original_name, url) in enumerate(file_list, start=1):
        # Check if URL is from allowed domains
        parsed_url = urlparse(url)
        domain = (
            parsed_url.netloc.split(".")[-2] + "." + parsed_url.netloc.split(".")[-1]
        )  # Get main domain
        if domain not in ["kemono.su", "coomer.su"]:
            print(f"⚠️ Ignoring not allowed domain URL: {url}")
            continue

        # Derive file extension from original name if available, otherwise from URL path
        if original_name and original_name.strip():
            extension = os.path.splitext(original_name)[1]
        if not extension:
            extension = os.path.splitext(parsed_url.path)[1] or ".bin"

        if extension == ".jpeg":
            extension = ".jpg"

        # Handle case where no original name is provided
        if not original_name or original_name.strip() == "":
            sanitized_name = str(idx)
        else:
            sanitized_name = adapt_file_name(original_name)

        # Generate unique file name
        file_name = f"{idx}-{sanitized_name}{extension}"
        if file_name in seen_files:
            continue  # Skip duplicates

        seen_files.add(file_name)
        file_path = os.path.join(folder_path, file_name)

        if config["skip_existed_files"] and os.path.exists(file_path):
            try:
                # Check if existing file size matches expected size
                existing_size = os.path.getsize(file_path)
                response = requests.head(url, timeout=10)
                expected_size = int(response.headers.get("content-length", 0))

                if expected_size > 0 and existing_size == expected_size:
                    print(f"Skipped (complete): {file_name}")
                    success_count += 1
                    continue
                elif expected_size > 0:
                    print(
                        f"Re-downloading (incomplete): {file_name} ({existing_size}/{expected_size} bytes)"
                    )
            except Exception:
                # proceed with download If cannot check
                pass

        # Download the file
        block_size = 8192
        # for debugging
        # print(f"Start downloading: {url}")
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            with tqdm(total=total_size, unit="B", unit_scale=True) as progress_bar:
                with open(file_path, "wb") as file:
                    for data in response.iter_content(block_size):
                        progress_bar.update(len(data))
                        file.write(data)

            if total_size != 0 and progress_bar.n != total_size:
                raise RuntimeError("internal error: failed to download whole file ")

            print(f"Downloaded: {file_name}")
            success_count += 1
        except Exception as err:
            failed_files.append({"name": file_name, "url": url, "error": str(err)})
            print(f"Download failed {url}:")
            print(err)

    return {
        "success_count": success_count,
        "failed_files": failed_files,
        "total_files": len(file_list),
    }


def save_post_info(
    post_data: Dict[str, Any], folder_path: str, file_format: str
) -> None:
    """
    Save post information to a file (title, content, polls, embeds, and file links).

    :param post_data: Dictionary containing post information
    :param folder_path: Path to save the info file
    :param file_format: File format ('md' or 'txt')
    """
    file_extension = ".md" if file_format == "md" else ".txt"
    file_name = f"files{file_extension}"
    file_path = os.path.join(folder_path, file_name)

    title, raw_title = clean_html_to_text(post_data["post"]["title"])
    content, raw_content = clean_html_to_text(post_data["post"]["content"])

    with open(file_path, "w", encoding="utf-8") as file:
        if file_format == "md":
            file.write(f"# {title}\n\n")
        else:
            file.write(f"Title: {title}\n\n")

        file.write(f"{content}\n\n")

        poll = post_data["post"].get("poll")
        if poll:
            if file_format == "md":
                file.write("## Poll Information\n\n")
                file.write(f"**Poll Title:** {poll.get('title', 'No Title')}\n")
                if poll.get("description"):
                    file.write(f"\n**Description:** {poll['description']}\n")
                file.write(
                    f"\n**Multiple Choices Allowed:** {'Yes' if poll.get('allows_multiple') else 'No'}\n"
                )
                file.write(f"**Started:** {poll.get('created_at', 'N/A')}\n")
                file.write(f"**Closes:** {poll.get('closes_at', 'N/A')}\n")
                file.write(f"**Total Votes:** {poll.get('total_votes', 0)}\n\n")

                file.write("### Choices and Votes\n\n")
                for choice in poll.get("choices", []):
                    file.write(
                        f"- **{choice['text']}:** {choice.get('votes', 0)} votes\n"
                    )
            else:
                file.write("Poll Information:\n\n")
                file.write(f"Poll Title: {poll.get('title', 'No Title')}\n")
                if poll.get("description"):
                    file.write(f"Description: {poll['description']}\n")
                file.write(
                    f"Multiple Choices Allowed: {'Yes' if poll.get('allows_multiple') else 'No'}\n"
                )
                file.write(f"Started: {poll.get('created_at', 'N/A')}\n")
                file.write(f"Closes: {poll.get('closes_at', 'N/A')}\n")
                file.write(f"Total Votes: {poll.get('total_votes', 0)}\n\n")

                file.write("Choices and Votes:\n")
                for choice in poll.get("choices", []):
                    file.write(f"- {choice['text']}: {choice.get('votes', 0)} votes\n")

            file.write("\n")

        embed = post_data["post"].get("embed")
        if embed:
            if file_format == "md":
                file.write("## Embedded Content\n")
            else:
                file.write("Embedded Content:\n")
            file.write(f"- URL: {embed.get('url', 'N/A')}\n")
            file.write(f"- Subject: {embed.get('subject', 'N/A')}\n")
            file.write(f"- Description: {embed.get('description', 'N/A')}\n")

        file.write("\n---\n\n")

        if file_format == "md":
            file.write("## Raw Title and Content\n\n")
        else:
            file.write("Raw Title and Content:\n\n")
        file.write(f"Raw Title: {raw_title}\n\n")
        file.write(f"Raw Content:\n{raw_content}\n\n")

        attachments = post_data.get("attachments", [])
        if attachments:
            if file_format == "md":
                file.write("## Attachments\n\n")
            else:
                file.write("Attachments:\n\n")
            for attach in attachments:
                server_url = f"{attach['server']}/data{attach['path']}?f={adapt_file_name(attach['name'])}"
                file.write(f"- {attach['name']}: {server_url}\n")

        videos = post_data.get("videos", [])
        if videos:
            if file_format == "md":
                file.write("## Videos\n\n")
            else:
                file.write("Videos:\n\n")
            for video in videos:
                server_url = f"{video['server']}/data{video['path']}?f={adapt_file_name(video['name'])}"
                file.write(f"- {video['name']}: {server_url}\n")

        images = []
        for preview in post_data.get("previews", []):
            if "name" in preview and "server" in preview and "path" in preview:
                server_url = f"{preview['server']}/data{preview['path']}"
                images.append((preview.get("name", ""), server_url))

        if images:
            if file_format == "md":
                file.write("## Images\n\n")
            else:
                file.write("Images:\n\n")
            for idx, (name, image_url) in enumerate(images, 1):
                if file_format == "md":
                    file.write(f"![Image {idx}]({image_url}) - {name}\n")
                else:
                    file.write(f"Image {idx}: {image_url} (Name: {name})\n")


def save_post_content(
    post_data: Dict[str, Any], folder_path: str, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Save post content and download files based on configuration settings.
    Now includes support for poll data if present.

    :param post_data: Dictionary containing post information
    :param folder_path: Path to save the post files
    :param config: Configuration dictionary with 'post_info' and 'save_info' keys

    :return: Dictionary with download results from download_files
    """
    ensure_directory(folder_path)

    if config["save_info"]:
        save_post_info(post_data, folder_path, config["post_info"].lower())

    # Consolidate all files for download
    all_files_to_download = []

    for attach in post_data.get("attachments", []):
        if "name" in attach and "server" in attach and "path" in attach:
            url = f"{attach['server']}/data{attach['path']}?f={adapt_file_name(attach['name'])}"
            all_files_to_download.append((attach["name"], url))

    for video in post_data.get("videos", []):
        if "name" in video and "server" in video and "path" in video:
            url = f"{video['server']}/data{video['path']}?f={adapt_file_name(video['name'])}"
            all_files_to_download.append((video["name"], url))

    for image in post_data.get("previews", []):
        if "name" in image and "server" in image and "path" in image:
            url = f"{image['server']}/data{image['path']}"
            all_files_to_download.append((image.get("name", ""), url))

    # Remove duplicates based on URL
    unique_files_to_download = list(
        {url: (name, url) for name, url in all_files_to_download}.values()
    )

    # Download files to the specified folder and get results
    download_result = download_files(unique_files_to_download, folder_path, config)

    return download_result


def sanitize_filename(value: str) -> str:
    """Remove characters that can break folder creation."""
    return value.replace("/", "_").replace("\\", "_")


def get_post_title(post_data: Dict[str, Any]) -> str:
    """
    Extract the post title from post_data.
    Return empty string if failed to get the title.
    """
    try:
        title = post_data.get("post", {}).get("title", "")
        return title
    except Exception:
        return ""


def load_failed_downloads(file_path: str = "failed_downloads.txt") -> Set[str]:
    """Load failed download links from file."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_failed_downloads(
    failed_links: Set[str], file_path: str = "failed_downloads.txt"
) -> None:
    """Save failed download links to file."""
    with open(file_path, "w", encoding="utf-8") as f:
        for link in sorted(failed_links):
            f.write(f"{link}\n")


def add_failed_download(link: str, file_path: str = "failed_downloads.txt") -> None:
    """Add a failed download link to the file."""
    failed_links = load_failed_downloads(file_path)
    failed_links.add(link)
    save_failed_downloads(failed_links, file_path)


def remove_failed_download(link: str, file_path: str = "failed_downloads.txt") -> None:
    """Remove a successful download link from the failed downloads file."""
    failed_links = load_failed_downloads(file_path)
    failed_links.discard(link)
    save_failed_downloads(failed_links, file_path)


def process_posts(links: List[str]) -> None:
    # Load configurations
    config = load_config()

    for user_link in links:
        try:
            print(f"\n--- Processing link: {user_link} ---")

            # Extract data from the link
            domain, service, user_id, post_id = extract_data_from_link(user_link)

            # Setup paths
            base_path = domain  # Use domain as base path (kemono or coomer)
            profiles_path = os.path.join(base_path, "profiles.json")

            ensure_directory(base_path)

            # Load existing profiles
            profiles = load_profiles(profiles_path)

            # Fetch and save profile if not already in profiles.json
            if user_id not in profiles:
                profile_data = fetch_profile(domain, service, user_id)
                profiles[user_id] = profile_data
                save_profiles(profiles_path, profiles)
            else:
                profile_data = profiles[user_id]

            # Create specific folder for the user
            user_name = sanitize_filename(profile_data.get("name", "unknown_user"))
            safe_service = sanitize_filename(service)
            safe_user_id = sanitize_filename(user_id)

            user_folder = os.path.join(
                base_path, f"{user_name}-{safe_service}-{safe_user_id}"
            )
            ensure_directory(user_folder)

            # Create posts folder and post-specific folder
            posts_folder = os.path.join(user_folder, "posts")
            ensure_directory(posts_folder)

            # Fetch post data
            post_data = fetch_post(domain, service, user_id, post_id)

            # Decide folder name based on config setting
            if config["post_folder_name"] == "title":
                post_title = get_post_title(post_data)
                # Prevent duplicated title
                folder_name = f"{post_title}_{post_id}"
            else:
                folder_name = post_id

            post_folder = os.path.join(posts_folder, folder_name)
            ensure_directory(post_folder)

            # Save post content using configurations
            download_result = save_post_content(post_data, post_folder, config)

            # Handle download results
            if download_result["failed_files"]:
                print(
                    f"\n⚠️ Link processed with {len(download_result['failed_files'])} failed downloads:",
                    f"{user_link}",
                    sep="\n",
                )
                print(
                    f"✅ Successfully downloaded: {download_result['success_count']}/{download_result['total_files']} files"
                )
                print("❌ Failed downloads:")
                for failed in download_result["failed_files"]:
                    print(f"  - {failed['name']}")

                add_failed_download(user_link)
            else:
                print(f"\n✅ Link processed successfully: {user_link}")
                print(f"✅ Downloaded all {download_result['success_count']} files")

                remove_failed_download(user_link)

        except Exception as e:
            print(f"❌ Error processing link {user_link}: {e}")
            # Continue processing next links even if one fails
            continue
