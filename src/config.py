import os
import json
from typing import Literal
from dataclasses import dataclass


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