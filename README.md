# Kemono and Coomer Downloader

[![Views](https://hits.sh/github.com/isaswa/hits.svg)](https://github.com/isaswa/Better-Kemono-and-Coomer-Downloader)

This is a forked better version of [**Kemono and Coomer Downloader**](https://github.com/e43b/Kemono-and-Coomer-Downloader/), since the original project has too many bugs and bad practices in the codebase, and also in a very inactive status in terms of maintaining the project.


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=isaswa/Better-Kemono-and-Coomer-Downloader&type=Date)](https://star-history.com/#isaswa/Better-Kemono-and-Coomer-Downloader&Date)

## How to Use

1. **Make sure you have Python installed on your system.**

2. **Clone this repository:**

```sh
git clone https://github.com/isaswa/Better-Kemono-and-Coomer-Downloader/
```

3. **Navigate to the project directory:**

```sh
cd Better-Kemono-and-Coomer-Downloader
```

4. **Install the dependencies**

```sh
pip install -r requirements.txt
```

5. **Run the main script:**
```sh
python main.py
```

6. **Follow the interactive terminal UI to choose what you want to download or customize the program.**

## File Organization

Posts are saved in folders to facilitate organization. The folder structure follows the pattern below:

### Folder Structure

1. **Platform**: A main folder is created for each platform (Kemono or Coomer).
2. **Author**: Within the platform folder, a folder is created for each author in the format **Name-Service-Id**.
3. **Posts**: Within the author's folder, there is a subfolder called `posts` where contents are organized.
   Each post is saved in a subfolder identified by the **post ID**.

### Example Folder Structure

```
Better-Kemono-and-Coomer-Downloader/
│
├── kemono/                                 # Kemono platform folder
│   ├── Name-Service-Id/                    # Author folder in Name-Service-Id format
│   │   ├── posts/                          # Author's posts folder
│   │   │   ├── postID1_postTitle1/         # Post folder with ID 1
│   │   │   │   ├── post_content            # Post content
│   │   │   │   ├── files.md                # (Optional) File with file information
│   │   │   │   └── ...                     # Other post files
│   │   │   ├── postID2_postTitle2/         # Post folder with ID 2
│   │   │   │   ├── post_content            # Post content
│   │   │   │   └── files.txt               # (Optional) File with file information
│   │   │   └── ...                         # Other posts
│   │   └── ...                             # Other author content
│   └── Name-Service-Id/                    # Another author folder in Name-Service-Id format
│       ├── posts/                          # Author's posts folder
│       └── ...                             # Other content
│
├── coomer/                                 # Coomer platform folder
│   ├── Name-Service-Id/                    # Author folder in Name-Service-Id format
│   │   ├── posts/                          # Author's posts folder
│   │   │   ├── postID1_postTitle1/         # Post folder with ID 1
│   │   │   │   ├── post_content            # Post content
│   │   │   │   ├── files.txt               # (Optional) File with file information
│   │   │   │   └── ...                     # Other post files
│   │   │   ├── postID2_postTitle2/         # Post folder with ID 2
│   │   │       ├── post_content            # Post content
│   │   │       └── ...                     # Other post files
│   │   └── ...                             # Other author content
│   └── Name-Service-Id/                    # Another author folder in Name-Service-Id format
│       ├── posts/                          # Author's posts folder
│       └── ...                             # Other content
│
│
└── failed_downloads.txt                    # A log buffer of links with failed downloads
```

![Folder Organization](img/pastas.png)

### About `failed_downloads.txt`

For any failed downloads attemp within a link when processing, the link will be automatically saved to this log file.
You can try following this work flow to retry your failed link downloads:
```
Choose an option:
1 - Download 1 post or a few separate posts
2 - Download all posts from a profile
3 - Customize the program settings
4 - Exit the program

Enter your choice (1/2/3/4): 1


Download 1 post or a few separate posts
------------------------------------
Choose the input method:
1 - Enter the links directly
2 - Loading links from a TXT file
3 - Back to the main menu

Enter your choice (1/2/3): 2
Enter the path to the TXT file: failed_downloads.txt
```

After a successful retry with all files downloaded completely, the link will be automatically removed from `failed_downloads.txt`.

### About the `files.md` or `files.txt` File

You can disable the download of this summary file by setting `save_info=false` in `config/config.json`

The `files.md` (or `files.txt`, depending on the chosen configuration) file contains the following information about each post:
- **Title**: The post title.
- **Description/Content**: The post content or description.
- **Embeds**: Information about embedded elements (if any).
- **File Links**: URLs of files present in the **Attachments**, **Videos**, and **Images** sections.

![Example of files.md](img/files.png)

## Contributions

Leave any comment or bug report in the [Issues page](https://github.com/isaswa/Better-Kemono-and-Coomer-Downloader/issues).

Any pull request is welcome, but it's better to provide a good evidence or tests for proving fixed bugs/issues.