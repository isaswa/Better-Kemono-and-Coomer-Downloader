import os
import sys
import subprocess
import re
import json
import time
import importlib
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse


def install_requirements() -> None:
    """Verify and install dependencies from requirements.txt."""
    requirements_file = "requirements.txt"

    if not os.path.exists(requirements_file):
        print(f"Error: File {requirements_file} not found.")
        return

    with open(requirements_file, "r", encoding="utf-8") as req_file:
        for line in req_file:
            # Read each line, ignore empty or comments
            package = line.strip()
            if package and not package.startswith("#"):
                try:
                    # Try to import the package to check if it's already installed
                    package_name = package.split("==")[
                        0
                    ]  # Ignore specific version when importing
                    importlib.import_module(package_name)
                except ImportError:
                    # If it fails, install the package using pip
                    print(f"Installing the package: {package}")
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", package]
                    )


def clear_screen() -> None:
    """Clear console screen in a cross-platform compatible way"""
    os.system("cls" if os.name == "nt" else "clear")


def display_logo() -> None:
    """Display the project logo"""
    logo = """
 _  __                                                   
| |/ /___ _ __ ___   ___  _ __   ___                     
| ' // _ \ '_ ` _ \ / _ \| '_ \ / _ \                    
| . \  __/ | | | | | (_) | | | | (_) |                   
|_|\_\___|_| |_| |_|\___/|_| |_|\___/                    
 / ___|___   ___  _ __ ___   ___ _ __                    
| |   / _ \ / _ \| '_ ` _ \ / _ \ '__|                   
| |__| (_) | (_) | | | | | |  __/ |                      
 \____\___/ \___/|_| |_| |_|\___|_|          _           
|  _ \  _____      ___ __ | | ___   __ _  __| | ___ _ __ 
| | | |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|
| |_| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |   
|____/ \___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|   

Project Repository: https://github.com/isaswa/Better-Kemono-and-Coomer-Downloader
Modified from: Kemono-and-Coomer-Downloader by e43b
License: MIT License
"""
    print(logo)


def normalize_path(path: str) -> str:
    """
    Normalize file path to handle non-ASCII characters
    """
    try:
        # If the original path exists, return it
        if os.path.exists(path):
            return path

        # Extract the filename and path components
        filename = os.path.basename(path)
        path_parts = path.split(os.sep)

        # Identify if searching in kemono or coomer
        base_dir = None
        if "kemono" in path_parts:
            base_dir = "kemono"
        elif "coomer" in path_parts:
            base_dir = "coomer"

        if base_dir:
            # Search in all subdirectories of the base directory
            for root, dirs, files in os.walk(base_dir):
                if filename in files:
                    return os.path.join(root, filename)

        # If still not found, try the normalized path
        return os.path.abspath(os.path.normpath(path))

    except Exception as e:
        print(f"Error when normalizing path: {e}")
        return path


def run_download_script(json_path: str) -> None:
    """Run the download script with the generated JSON and do detailed real-time tracking"""
    try:
        # Normalize the JSON path
        json_path = normalize_path(json_path)

        # Check if the JSON file exists
        if not os.path.exists(json_path):
            print(f"Error: JSON file not found: {json_path}")
            return

        # Read configurations
        config_path = normalize_path(os.path.join("config", "conf.json"))
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)

        # Read the posts JSON
        with open(json_path, "r", encoding="utf-8") as posts_file:
            posts_data = json.load(posts_file)

        # Initial analysis
        total_posts = posts_data["total_posts"]
        post_ids = [post["id"] for post in posts_data["posts"]]

        # File count
        total_files = sum(len(post["files"]) for post in posts_data["posts"])

        # Print initial information
        print(f"Post extraction completed: {total_posts} posts found")
        print(f"Total number of files to download: {total_files}")
        print("Starting post downloads")

        # Determine processing order
        if config["process_from_oldest"]:
            post_ids = sorted(post_ids)  # Order from oldest to newest
        else:
            post_ids = sorted(post_ids, reverse=True)  # Order from newest to oldest

        # Base folder for posts using path normalization
        posts_folder = normalize_path(os.path.join(os.path.dirname(json_path), "posts"))
        os.makedirs(posts_folder, exist_ok=True)

        # Process each post
        for idx, post_id in enumerate(post_ids, 1):
            # Find specific post data
            post_data = next(
                (p for p in posts_data["posts"] if p["id"] == post_id), None
            )

            if post_data:
                # Specific post folder with normalization
                post_folder = normalize_path(os.path.join(posts_folder, post_id))
                os.makedirs(post_folder, exist_ok=True)

                # Count number of files in JSON for this post
                expected_files_count = len(post_data["files"])

                # Count existing files in the folder
                existing_files = [
                    f
                    for f in os.listdir(post_folder)
                    if os.path.isfile(os.path.join(post_folder, f))
                ]
                existing_files_count = len(existing_files)

                # If all files exist, skip the download
                if existing_files_count == expected_files_count:
                    continue

                try:
                    # Normalize download script path
                    download_script = normalize_path(os.path.join("src", "down.py"))

                    # Use subprocess.Popen with normalized path and Unicode support
                    download_process = subprocess.Popen(
                        [sys.executable, download_script, json_path, post_id],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        encoding="utf-8",
                    )

                    # Capture and print output in real time
                    while True:
                        output = download_process.stdout.readline()
                        if output == "" and download_process.poll() is not None:
                            break
                        if output:
                            print(output.strip())

                    # Check return code
                    download_process.wait()

                    # After download, check files again
                    current_files = [
                        f
                        for f in os.listdir(post_folder)
                        if os.path.isfile(os.path.join(post_folder, f))
                    ]
                    current_files_count = len(current_files)

                    # Check download result
                    if current_files_count == expected_files_count:
                        print(
                            f"Post {post_id} downloaded completely ({current_files_count}/{expected_files_count} files)"
                        )
                    else:
                        print(
                            f"Post {post_id} partially downloaded: {current_files_count}/{expected_files_count} files"
                        )

                except Exception as e:
                    print(f"Error while downloading post {post_id}: {e}")

                # Small delay to avoid overload
                time.sleep(0.5)

        print("\nAll posts have been processed!")

    except Exception as e:
        print(f"Unexpected error: {e}")
        # Add more details for diagnosis
        import traceback

        traceback.print_exc()


def download_specific_posts() -> None:
    """Option to download specific posts"""
    clear_screen()
    display_logo()
    print("Download 1 post or a few separate posts")
    print("------------------------------------")
    print("Choose the input method:")
    print("1 - Enter the links directly")
    print("2 - Loading links from a TXT file")
    print("3 - Back to the main menu")
    choice = input("\nEnter your choice (1/2/3): ")

    links: List[str] = []

    if choice == "3":
        return
    elif choice == "1":
        print("Paste the links to the posts (separated by commas or space):")
        content = input("Links: ")
        links = re.split(r"[,\s]+", content)
    elif choice == "2":
        file_path = input("Enter the path to the TXT file: ").strip()
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                # Split by comma, space, or linebreak
                links = re.split(r"[,\s\n]+", content)
        else:
            print(f"Error: The file '{file_path}' was not found.")
            input("\nPress Enter to continue...")
            return
    else:
        print("Invalid option. Return to the previous menu.")
        input("\nPress Enter to continue...")
        return

    links = [link.strip() for link in links if link.strip()]

    for link in links:
        try:
            domain = urlparse(link).netloc
            if domain == "kemono.su" or domain == "coomer.su":
                script_path = os.path.join("src", "kcposts.py")
            else:
                print(f"Domain not supported: {domain}")
                continue

            # Execute the specific script for the domain
            subprocess.run(["python", script_path, link], check=True)
        except IndexError:
            print(f"Link format error: {link}")
        except subprocess.CalledProcessError:
            print(f"Error downloading the post: {link}")

    input("\nPress Enter to continue...")


def download_profile_posts() -> None:
    """Option to download posts from a profile"""
    clear_screen()
    display_logo()
    print("Download Profile Posts")
    print("-----------------------")
    print("1 - Download all posts from a profile")
    print("2 - Download posts from a specific page")
    print("3 - Downloading posts from a range of pages")
    print("4 - Downloading posts between two specific posts")
    print("5 - Back to the main menu")

    choice = input("\nEnter your choice (1/2/3/4/5): ")

    if choice == "5":
        return

    profile_link = input("Paste the profile link: ")

    try:
        json_path: Optional[str] = None

        if choice == "1":
            posts_process = subprocess.run(
                ["python", os.path.join("src", "posts.py"), profile_link, "all"],
                capture_output=True,
                text=True,
                encoding="utf-8",  # Ensure output is correctly decoded
                check=True,
            )

            # Check if stdout contains data
            if posts_process.stdout:
                for line in posts_process.stdout.split("\n"):
                    if line.endswith(".json"):
                        json_path = line.strip()
                        break
            else:
                print("No output from the sub-process.")

        elif choice == "2":
            page = input("Enter the page number (0 = first page, 50 = second, etc.): ")
            posts_process = subprocess.run(
                ["python", os.path.join("src", "posts.py"), profile_link, page],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in posts_process.stdout.split("\n"):
                if line.endswith(".json"):
                    json_path = line.strip()
                    break

        elif choice == "3":
            start_page = input("Enter the start page (start, 0, 50, 100, etc.): ")
            end_page = input("Enter the final page (or use end, 300, 350, 400): ")
            posts_process = subprocess.run(
                [
                    "python",
                    os.path.join("src", "posts.py"),
                    profile_link,
                    f"{start_page}-{end_page}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in posts_process.stdout.split("\n"):
                if line.endswith(".json"):
                    json_path = line.strip()
                    break

        elif choice == "4":
            first_post = input("Paste the link or ID of the first post: ")
            second_post = input("Paste the link or ID from the second post: ")

            first_id = first_post.split("/")[-1] if "/" in first_post else first_post
            second_id = (
                second_post.split("/")[-1] if "/" in second_post else second_post
            )

            posts_process = subprocess.run(
                [
                    "python",
                    os.path.join("src", "posts.py"),
                    profile_link,
                    f"{first_id}-{second_id}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in posts_process.stdout.split("\n"):
                if line.endswith(".json"):
                    json_path = line.strip()
                    break

        if json_path:
            run_download_script(json_path)
        else:
            print("The JSON path could not be found.")

    except subprocess.CalledProcessError as e:
        print(f"Error generating JSON: {e}")
        print(e.stderr)

    input("\nPress Enter to continue...")


def customize_settings() -> None:
    """Option to customize settings"""
    config_path = os.path.join("config", "conf.json")
    
    with open(config_path, "r") as f:
        config: Dict[str, Any] = json.load(f)

    while True:
        clear_screen()
        display_logo()
        print("Customize Settings")
        print("------------------------")
        print(f"1 - Take empty posts: {config['get_empty_posts']}")
        print(f"2 - Download older posts first: {config['process_from_oldest']}")
        print(
            f"3 - For individual posts, create a file with information (title, description, etc.): {config['save_info']}"
        )
        print(
            f"4 - Choose the type of file to save the information (Markdown or TXT): {config['post_info']}"
        )
        print("5 - Back to the main menu")

        choice = input("\nChoose an option (1/2/3/4/5): ")

        if choice == "1":
            config["get_empty_posts"] = not config["get_empty_posts"]
        elif choice == "2":
            config["process_from_oldest"] = not config["process_from_oldest"]
        elif choice == "3":
            config["save_info"] = not config["save_info"]
        elif choice == "4":
            config["post_info"] = "txt" if config["post_info"] == "md" else "md"
        elif choice == "5":
            break
        else:
            print("Invalid option. Please try again.")

        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)

        print("\nUpdated configurations.")
        time.sleep(1)


def main_menu() -> None:
    """Application main menu"""
    while True:
        clear_screen()
        display_logo()
        print("Choose an option:")
        print("1 - Download 1 post or a few separate posts")
        print("2 - Download all posts from a profile")
        print("3 - Customize the program settings")
        print("4 - Exit the program")

        choice = input("\nEnter your choice (1/2/3/4): ")

        if choice == "1":
            download_specific_posts()
        elif choice == "2":
            download_profile_posts()
        elif choice == "3":
            customize_settings()
        elif choice == "4":
            print("Leaving the program. See you later!")
            break
        else:
            input("Invalid option. Press Enter to continue...")


if __name__ == "__main__":
    print("Checking dependencies...")
    install_requirements()
    print("Verified dependencies.\n")
    main_menu()
