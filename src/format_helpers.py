"""
Helper functions for formatting and sanitizing file and folder names.
"""
import os
import re
from urllib.parse import unquote


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters and replacing spaces with underscores.
    This is for individual file names within folders.
    """
    if not filename:
        return ""
    
    # Remove invalid characters for filenames
    sanitized = re.sub(r"[\\/*?\"<>|]", "", filename)
    # Replace spaces with underscores
    return sanitized.replace(" ", "_")


def sanitize_folder_name(value: str) -> str:
    """
    Remove characters that can break folder creation.
    This is for folder/directory names.
    """
    if not value:
        return ""
    
    return value.replace("/", "_").replace("\\", "_")


def sanitize_title(unsanitized: str) -> str:
    """
    Sanitize title string for use in folder names.
    Removes invalid characters and strips trailing dots.
    """
    if not unsanitized:
        return ""
    
    title = unsanitized
    
    # Ensure the title is valid for use in filenames
    invalid_chars = '<>:"/\\|?*.'
    for char in invalid_chars:
        title = title.replace(char, "_")
    
    title = title.strip()
    
    while title.endswith("."):
        title = title.rstrip(".")
    
    return title if title else ""


def adapt_file_name(name: str) -> str:
    """
    Sanitize file name by removing special characters and reducing its size.
    Handles URL-encoded filenames and limits to 50 UTF-8 characters.
    """
    if not name:
        return ""

    # Decode utf-8 characters (Japanese text) in URL filename
    try:
        decoded_name = unquote(name, encoding="utf-8")
    except (UnicodeDecodeError, LookupError):
        decoded_name = name

    name_without_ext = os.path.splitext(decoded_name)[0]
    extension = os.path.splitext(decoded_name)[1]

    # Replace problematic characters with underscores, but preserve Unicode characters
    # Keep alphanumeric, spaces, hyphens, underscores, and Unicode characters
    sanitized_name = re.sub(r'[<>:"/\\|?*]', "_", name_without_ext)

    # Replace multiple consecutive underscores or spaces with single underscore
    sanitized_name = re.sub(r"[_\s]+", "_", sanitized_name)

    # Strip leading/trailing underscores and spaces
    sanitized_name = sanitized_name.strip("_ ")

    if len(sanitized_name.encode("utf-8")) > 50:
        truncated_name = sanitized_name
        while len(truncated_name.encode("utf-8")) > 50 and truncated_name:
            truncated_name = truncated_name[:-1]
        sanitized_name = truncated_name

    if not sanitized_name:
        sanitized_name = "unknown_filename"

    return sanitized_name