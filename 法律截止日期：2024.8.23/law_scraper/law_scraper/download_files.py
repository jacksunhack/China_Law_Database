# download_files.py (place in the root project folder)
import os
import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from urllib.parse import urlparse
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration - ideally read from settings or command line
JSON_FILE = 'fl_down.json' # Input file with QR links
DOWNLOAD_DIR = 'output_docs/downloads' # Subdirectory for actual file downloads
MAX_WORKERS = 5 # Number of concurrent downloads
DOWNLOAD_DELAY = 0.5 # Seconds delay between starting downloads (per worker) - adjust as needed
REQUEST_TIMEOUT = 120 # Timeout for download requests in seconds

def sanitize_filename(url, title):
    """Creates a safe filename, prioritizing URL basename, then title."""
    # Try to get filename from URL path
    try:
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path:
            base = os.path.basename(path)
            if base:
                # Remove potentially problematic characters, keep extension separator
                name, ext = os.path.splitext(base)
                safe_name = re.sub(r'[\\/*?:"<>|]', '_', name) # Replace invalid chars with underscore
                safe_name = safe_name.strip()
                # Use provided extension or assume pdf if none likely
                safe_ext = ext if ext and len(ext) <= 5 else ".pdf"
                filename = f"{safe_name}{safe_ext}"
                # Limit overall length
                return filename[:200] # Limit length to avoid issues
    except Exception as e:
        logging.warning(f"Could not parse filename from URL {url}: {e}. Falling back to title.")

    # Fallback to title if URL parsing fails or yields no name
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', title) # Replace invalid chars
    safe_title = safe_title.strip()
    # Limit length and add default extension
    return safe_title[:200] + ".pdf"


def download_file(url, dest_path, title):
    """Downloads a single file."""
    try:
        logging.info(f"Starting download: '{title}' ({url}) -> {os.path.basename(dest_path)}")
        response = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # Check for HTTP errors (4xx or 5xx)

        # Ensure directory exists just before writing
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        with open(dest_path, 'wb') as file:
            downloaded_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
                downloaded_size += len(chunk)
        logging.info(f"Successfully downloaded: {os.path.basename(dest_path)} ({downloaded_size} bytes)")
        return True, url
    except requests.exceptions.Timeout:
        logging.error(f"Download timed out for {url} ({title})")
        if os.path.exists(dest_path): try: os.remove(dest_path) except OSError: pass
        return False, url
    except requests.exceptions.RequestException as e:
        logging.error(f"Download failed for {url} ({title}): {e}")
        if os.path.exists(dest_path): try: os.remove(dest_path) except OSError: pass
        return False, url
    except Exception as e:
         logging.error(f"An unexpected error occurred during download of {url} ({title}): {e}")
         if os.path.exists(dest_path): try: os.remove(dest_path) except OSError: pass
         return False, url


def main():
    if not os.path.exists(JSON_FILE):
        logging.error(f"Input JSON file not found: {JSON_FILE}")
        return

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as file:
            content = file.read()
            if not content:
                logging.info(f"{JSON_FILE} is empty. No links to download.")
                return
            links_data = json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Failed to read or parse {JSON_FILE}: {e}")
        return
    except Exception as e:
        logging.error(f"Unexpected error reading {JSON_FILE}: {e}")
        return

    if not isinstance(links_data, list):
        logging.error(f"Expected a list of items in {JSON_FILE}, but got {type(links_data)}. Cannot proceed.")
        return

    if not links_data:
         logging.info("No download links found in the JSON file.")
         return

    logging.info(f"Found {len(links_data)} potential download entries in {JSON_FILE}.")
    download_tasks = []
    processed_urls = set() # Avoid queueing the same URL multiple times
    skipped_missing_info = 0
    skipped_duplicate_url = 0
    skipped_file_exists = 0

    for entry in links_data:
        if not isinstance(entry, dict):
            logging.warning(f"Skipping non-dictionary entry: {entry}")
            skipped_missing_info += 1
            continue

        title = entry.get('title')
        download_link = entry.get('download_link')
        # original_link = entry.get('original_link') # Available if needed for logging

        if not title or not download_link:
            logging.warning(f"Skipping entry with missing title or download_link: {entry}")
            skipped_missing_info += 1
            continue

        if download_link in processed_urls:
             # Log less verbosely for duplicate URLs unless debugging
             # logging.info(f"Skipping duplicate download URL: {download_link}")
             skipped_duplicate_url += 1
             continue

        # Generate a safe filename
        file_name = sanitize_filename(download_link, title)
        file_path = os.path.join(DOWNLOAD_DIR, file_name)

        # Check if file already exists
        if os.path.exists(file_path):
             # logging.info(f"File already exists, skipping: {file_path}")
             skipped_file_exists += 1
             processed_urls.add(download_link) # Mark as processed even if skipped here
             continue

        download_tasks.append((download_link, file_path, title))
        processed_urls.add(download_link)

    logging.info(f"Skipped {skipped_missing_info} entries due to missing info.")
    logging.info(f"Skipped {skipped_duplicate_url} duplicate download URLs.")
    logging.info(f"Skipped {skipped_file_exists} files that already exist.")

    if not download_tasks:
         logging.info("No new files need to be downloaded.")
         return

    logging.info(f"Attempting downloads for {len(download_tasks)} files using up to {MAX_WORKERS} workers.")
    successful_downloads = 0
    failed_downloads = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {} # Map future to URL for better error reporting
        for url, dest_path, task_title in download_tasks:
            future = executor.submit(download_file, url, dest_path, task_title)
            futures[future] = (url, task_title)
            time.sleep(DOWNLOAD_DELAY) # Stagger the start of downloads

        for future in as_completed(futures):
            url, task_title = futures[future]
            try:
                success, result_url = future.result()
                if success:
                    successful_downloads += 1
                else:
                    failed_downloads += 1
                    # Error is already logged within download_file
            except Exception as e:
                # Catch errors from the future execution itself
                logging.error(f"Error processing download result for {url} ({task_title}): {e}")
                failed_downloads += 1

    logging.info(f"Download process finished.")
    logging.info(f"Successful downloads: {successful_downloads}")
    logging.info(f"Failed downloads: {failed_downloads}")

if __name__ == "__main__":
    main()