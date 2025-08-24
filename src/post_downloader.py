import os
import sys
import json
import requests
import re
from typing import Dict, List, Tuple, Optional, Any, Set
from tqdm import tqdm
from html.parser import HTMLParser
from urllib.parse import quote, urlparse, unquote

from .config import load_config, Config, get_domains
from .format_helpers import (
    sanitize_filename,
    sanitize_folder_name,
    sanitize_title,
    adapt_file_name,
    get_artist_dir,
)
from .failure_handlers import (
    FAILED_DOWNLOAD_LOG_FILENAME,
    load_failed_downloads,
    save_failed_downloads,
    add_failed_download,
    remove_failed_download,
)
from .session import cookie_map, headers


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
    Extract service, user_id, and post_id from kemono and coomer links
    """
    # Get current domain mappings
    domains = get_domains()

    # Parse the URL to get the domain
    parsed_url = urlparse(link)
    domain = parsed_url.netloc

    # Determine which service this is based on domain
    if domain == domains["kemono"]:
        service_type = "kemono"
    elif domain == domains["coomer"]:
        service_type = "coomer"
    else:
        raise ValueError(
            f"Invalid domain: {domain}. Supported domains: {list(domains.values())}"
        )

    # Extract path components
    path_parts = parsed_url.path.strip("/").split("/")

    # Expected format: service/user/user_id/post/post_id
    if len(path_parts) < 5 or path_parts[1] != "user" or path_parts[3] != "post":
        raise ValueError(
            "Invalid link format. Expected: https://domain/service/user/user_id/post/post_id"
        )

    service = path_parts[0]
    user_id = path_parts[2]
    post_id = path_parts[4]

    return service_type, service, user_id, post_id


def get_api_base_url(domain_type: str) -> str:
    """
    Dynamically generate API base URL based on the domain type
    """
    domains = get_domains()
    domain = domains.get(domain_type)
    if not domain:
        raise ValueError(f"Unknown domain type: {domain_type}")
    return f"https://{domain}/api/v1/"


def fetch_profile(domain: str, service: str, user_id: str) -> Dict[str, Any]:
    """
    Fetch user profile with dynamic domain support
    """
    api_base_url = get_api_base_url(domain)
    url = f"{api_base_url}{service}/user/{user_id}/profile"
    response = requests.get(url, cookies=cookie_map[domain], headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_post(domain: str, service: str, user_id: str, post_id: str) -> Dict[str, Any]:
    """
    Fetch post data with dynamic domain support
    """
    api_base_url = get_api_base_url(domain)
    url = f"{api_base_url}{service}/user/{user_id}/post/{post_id}"
    response = requests.get(url, cookies=cookie_map[domain], headers=headers)
    response.raise_for_status()
    response.encoding = "utf-8"
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



def download_files(
    file_list: List[Tuple[str, str]], folder_path: str, config: Config
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

    # Get valid domains for checking
    valid_domains = list(get_domains().values())

    for idx, (original_name, url) in enumerate(file_list, start=1):
        # Check if URL is from allowed domains
        parsed_url = urlparse(url)
        # would be cdn domain (e.g. n1.kemono.cr, n2.kemono.cr, ...)
        domain = parsed_url.netloc

        if all(valid_domain not in domain for valid_domain in valid_domains):
            print(f"⚠️ Ignoring not allowed domain URL: {url}")
            print(f"   Allowed domains: {', '.join(valid_domains)}")
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

        if config.skip_existed_files and os.path.exists(file_path):
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
            response = requests.get(url, cookies=cookie_map["kemono" if "kemono" in domain else "coomer"],
                                    headers=headers, stream=True)
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
    post_data: Dict[str, Any], folder_path: str, config: Config
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

    if config.save_info:
        save_post_info(post_data, folder_path, config.post_info.lower())

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



def get_post_title(post_data: Dict[str, Any]) -> str:
    """
    Extract the post title from post_data.
    Return empty string if failed to get the title.
    Handles proper Unicode support.
    """
    try:
        title = post_data.get("post", {}).get("title", "")
        return sanitize_title(title)
    except Exception:
        return ""



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
            user_name = profile_data.get("name", "unknown_user")
            artist_dir_name = get_artist_dir(user_name, service, user_id)
            user_folder = os.path.join(base_path, artist_dir_name)
            ensure_directory(user_folder)

            # Create posts folder and post-specific folder
            posts_folder = os.path.join(user_folder, "posts")
            ensure_directory(posts_folder)

            # Fetch post data
            post_data = fetch_post(domain, service, user_id, post_id)

            post_title = get_post_title(post_data)

            # Decide folder name based on config setting
            if config.post_folder_name == "title":
                # Check if old folder with just post_id exists and rename it
                old_folder_name = post_id
                old_post_folder = os.path.join(posts_folder, old_folder_name)
                
                # Prevent duplicated title
                folder_name = f"{post_id}_{post_title}"
                new_post_folder = os.path.join(posts_folder, folder_name)
                
                # If old folder exists and new folder doesn't, rename it
                if os.path.exists(old_post_folder) and not os.path.exists(new_post_folder):
                    try:
                        os.rename(old_post_folder, new_post_folder)
                        print(f"Renamed folder: {old_folder_name} -> {folder_name}")
                    except OSError as e:
                        print(f"Warning: Could not rename folder {old_folder_name}: {e}")
                        # If rename fails, use the old folder
                        folder_name = old_folder_name
            else:
                folder_name = post_id

            post_folder = os.path.join(posts_folder, folder_name)
            ensure_directory(post_folder)

            print(f"--- Post title: {post_title}")

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
                print(f"⚠️ Added link to {FAILED_DOWNLOAD_LOG_FILENAME}")
            else:
                print(f"\n✅ Link processed successfully: {user_link}")
                print(f"✅ Downloaded all {download_result['success_count']} files")

                remove_failed_download(user_link)
                print(f"✅ Removed link from {FAILED_DOWNLOAD_LOG_FILENAME}")

        except Exception as e:
            print(f"❌ Error processing link {user_link}: {e}")
            # Continue processing next links even if one fails
            continue
