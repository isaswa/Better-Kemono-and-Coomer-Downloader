import os
import sys
import json
from typing import Literal, Dict, Optional
from dataclasses import dataclass

# Singleton cache for domains
DOMAINS: Optional[Dict[str, str]] = None


@dataclass
class Config:
    """Configuration class with type hints for all config fields"""

    get_empty_posts: bool = False
    process_from_oldest: bool = False
    post_info: Literal["md", "txt"] = "md"
    save_info: bool = False
    save_preview: bool = False
    skip_existed_files: bool = True
    post_folder_name: Literal["id", "title"] = "id"

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create Config instance from dictionary with validation"""
        return cls(
            get_empty_posts=data.get("get_empty_posts", False),
            process_from_oldest=data.get("process_from_oldest", False),
            post_info=data.get("post_info", "md"),
            save_info=data.get("save_info", False),
            save_preview=data.get("save_preview", False),
            skip_existed_files=data.get("skip_existed_files", True),
            post_folder_name=data.get("post_folder_name", "id"),
        )

    def to_dict(self) -> dict:
        """Convert Config instance to dictionary for JSON serialization"""
        return {
            "get_empty_posts": self.get_empty_posts,
            "process_from_oldest": self.process_from_oldest,
            "post_info": self.post_info,
            "save_info": self.save_info,
            "save_preview": self.save_preview,
            "skip_existed_files": self.skip_existed_files,
            "post_folder_name": self.post_folder_name,
        }


def load_config(config_path: str = "config/conf.json") -> Config:
    """
    Load configurations from conf.json file
    If the file doesn't exist, return default configurations
    """
    try:
        with open(config_path, "r") as file:
            config_data = json.load(file)
        return Config.from_dict(config_data)
    except FileNotFoundError:
        print(f"Config file {config_path} not found. Using default settings.")
        return Config()
    except json.JSONDecodeError:
        print(f"Error decoding {config_path}. Using default settings.")
        return Config()


def save_config(config: Config, config_path: str = "config/conf.json") -> None:
    """
    Save Config instance to JSON file
    """
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as file:
            json.dump(config.to_dict(), file, indent=4)
    except Exception as e:
        print(f"Error saving config to {config_path}: {e}")


def get_domains() -> Dict[str, str]:
    """
    Get the current domain mappings for Kemono and Coomer from domain.json file.
    Uses singleton pattern to cache the result and avoid repeated file I/O.
    Returns a dictionary with service names as keys and domains as values.

    To update domains, edit config/domain.json and restart the application.

    If any error occurs, the process will terminate.
    """
    global DOMAINS

    if DOMAINS is not None:
        return DOMAINS

    domain_file_path = os.path.join("config", "domain.json")

    try:
        with open(domain_file_path, "r", encoding="utf-8") as file:
            domains = json.load(file)

        # Validate that we have the required domains
        if "kemono" not in domains:
            print(f"CRITICAL ERROR: 'kemono' key not found in {domain_file_path}")
            print("domain.json must contain both 'kemono' and 'coomer' keys")
            sys.exit(1)

        if "coomer" not in domains:
            print(f"CRITICAL ERROR: 'coomer' key not found in {domain_file_path}")
            print("domain.json must contain both 'kemono' and 'coomer' keys")
            sys.exit(1)

        DOMAINS = domains
        return domains

    except FileNotFoundError:
        print(f"CRITICAL ERROR: Configuration file {domain_file_path} not found!")
        print("Please ensure config/domain.json exists with the following format:")
        print("{")
        print('    "kemono": "kemono.cr",')
        print('    "coomer": "coomer.su"')
        print("}")
        sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"CRITICAL ERROR: Failed to parse {domain_file_path}")
        print(f"JSON Error: {e}")
        print("Please ensure domain.json contains valid JSON format:")
        print("{")
        print('    "kemono": "kemono.cr",')
        print('    "coomer": "coomer.su"')
        print("}")
        sys.exit(1)

    except Exception as e:
        print(f"CRITICAL ERROR: Unexpected error reading {domain_file_path}")
        print(f"Error: {e}")
        sys.exit(1)


def reload_domains() -> Dict[str, str]:
    """
    Force reload of domain configuration from file.
    Useful if domain.json has been updated during runtime.
    """
    global DOMAINS
    DOMAINS = None
    return get_domains()
