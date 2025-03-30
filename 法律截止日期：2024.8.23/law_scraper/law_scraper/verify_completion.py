# verify_completion.py (place in the root project folder)
import json
import os
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# Ensure these paths match your settings.py or actual output locations
LINKS_FILE = 'fl_links_modified.json' # The definitive list (after deduplication)
QR_LINKS_FILE = 'fl_down.json'        # Records items processed via QR code
TEXT_FILES_DIR = 'output_docs'        # Directory where .txt files (iframe content) are saved
PROCESSED_LINKS_FILE = 'fl_processed_links.json' # Tracks *all* processed original_links
# ---

def get_safe_filename_base(title):
    """
    Generates the expected base filename (without .txt) from a title.
    !!! MUST MATCH the sanitization logic in DocumentPipeline !!!
    """
    if not title: return "unknown_title"
    # Replace invalid filesystem characters with underscore
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
    # Remove leading/trailing whitespace and underscores
    safe_title = safe_title.strip().strip('_')
    # Limit length (e.g., to 200 chars) to avoid filesystem issues
    return safe_title[:200]


def main():
    # 1. Load the master list of expected items (from the deduplicated file)
    if not os.path.exists(LINKS_FILE):
        logging.error(f"Master links file not found: '{LINKS_FILE}'. Run link_spider and deduplicate_titles.py first.")
        return
    try:
        with open(LINKS_FILE, 'r', encoding='utf-8') as f:
            all_links_data = json.load(f)
        # Store as dict: {original_link: title}
        expected_items = {item['link']: item['title'] for item in all_links_data if item.get('link') and item.get('title')}
        if not expected_items:
             logging.error(f"No valid link/title pairs found in {LINKS_FILE}. Cannot verify.")
             return
        logging.info(f"Loaded {len(expected_items)} expected items from '{LINKS_FILE}'.")
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error reading or parsing master links file '{LINKS_FILE}': {e}")
        return
    except Exception as e:
        logging.error(f"Unexpected error loading master links file '{LINKS_FILE}': {e}")
        return

    # 2. Load the primary tracker: the processed links set
    processed_via_tracker = set()
    if os.path.exists(PROCESSED_LINKS_FILE):
         try:
             with open(PROCESSED_LINKS_FILE, 'r', encoding='utf-8') as f:
                 content = f.read()
                 if content:
                     tracker_data = json.loads(content)
                     if isinstance(tracker_data, list):
                         processed_via_tracker = set(tracker_data)
                     else:
                          logging.warning(f"Expected a list in {PROCESSED_LINKS_FILE}, found {type(tracker_data)}. Ignoring this file for verification.")
                 else:
                      logging.info(f"Processed links tracker file '{PROCESSED_LINKS_FILE}' is empty.")
             logging.info(f"Loaded {len(processed_via_tracker)} links from tracker file '{PROCESSED_LINKS_FILE}'. This will be used as the primary source of truth.")
         except (json.JSONDecodeError, IOError) as e:
              logging.warning(f"Could not read or parse processed links tracker '{PROCESSED_LINKS_FILE}': {e}. Verification might be incomplete.")
         except Exception as e:
              logging.warning(f"Unexpected error loading processed links tracker '{PROCESSED_LINKS_FILE}': {e}.")
    else:
         logging.warning(f"Processed links tracker file not found: '{PROCESSED_LINKS_FILE}'. Verification will rely on checking output files, which might be less accurate.")


    # --- Optional: Cross-check with output files (mainly for debugging if tracker seems wrong) ---
    # 3. Load links processed via QR code (recorded in fl_down.json)
    processed_via_qr = set()
    if os.path.exists(QR_LINKS_FILE):
        try:
            with open(QR_LINKS_FILE, 'r', encoding='utf-8') as f:
                 content = f.read()
                 if content:
                    qr_data = json.loads(content)
                    if isinstance(qr_data, list):
                        processed_via_qr = {item['original_link'] for item in qr_data if isinstance(item, dict) and item.get('original_link')}
                    else:
                         logging.warning(f"Expected list in {QR_LINKS_FILE}, found {type(qr_data)}. Cannot use for cross-check.")
            logging.info(f"(Cross-check) Found {len(processed_via_qr)} links recorded in QR file '{QR_LINKS_FILE}'.")
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"(Cross-check) Could not read/parse QR links file '{QR_LINKS_FILE}': {e}")
        except Exception as e:
            logging.warning(f"(Cross-check) Error loading QR links file '{QR_LINKS_FILE}': {e}")
    else:
         logging.info(f"(Cross-check) QR links file not found: '{QR_LINKS_FILE}'")


    # 4. Find links processed via saved text files (iframe content)
    processed_via_text = set()
    found_files_count = 0
    mapped_files_count = 0
    if os.path.isdir(TEXT_FILES_DIR):
        # Map expected text filenames back to original links using the loaded expected_items
        # {expected_filename_base: original_link}
        expected_filenames_to_links = {get_safe_filename_base(title): link for link, title in expected_items.items()}

        try:
            for filename in os.listdir(TEXT_FILES_DIR):
                if filename.endswith(".txt"):
                    found_files_count += 1
                    base_name = filename[:-4] # Remove .txt extension
                    if base_name in expected_filenames_to_links:
                        original_link = expected_filenames_to_links[base_name]
                        processed_via_text.add(original_link)
                        mapped_files_count += 1
                    else:
                        # This is less critical if relying on the tracker file, but good to know
                        logging.debug(f"Found text file '{filename}' but couldn't map its base name '{base_name}' back to an expected link/title.")
            logging.info(f"(Cross-check) Checked {found_files_count} .txt files in '{TEXT_FILES_DIR}'. Mapped {mapped_files_count} back to original links.")
        except OSError as e:
            logging.warning(f"(Cross-check) Error listing files in text dir '{TEXT_FILES_DIR}': {e}")
    else:
        logging.info(f"(Cross-check) Text files directory not found: '{TEXT_FILES_DIR}'")

    # --- Verification Logic ---
    # Primarily use the tracker file if available and loaded successfully
    if processed_via_tracker:
        all_processed_links = processed_via_tracker
        verification_source = f"tracker file ({PROCESSED_LINKS_FILE})"
    else:
        # Fallback to combining QR records and found text files
        all_processed_links = processed_via_qr.union(processed_via_text)
        verification_source = f"QR file and found text files ({len(processed_via_qr)} QR, {len(processed_via_text)} text)"
        if not all_processed_links:
             logging.warning("No processed links found from tracker, QR file, or text files. Verification cannot determine status.")


    # 5. Find missing links by comparing expected links to the identified processed links
    missing_items = []
    for link, title in expected_items.items():
        if link not in all_processed_links:
            missing_items.append({'title': title, 'link': link})

    # 6. Report results
    logging.info("-" * 40)
    logging.info("Verification Results")
    logging.info(f"Source of processed links: {verification_source}")
    logging.info(f"Total expected items (from {LINKS_FILE}): {len(expected_items)}")
    logging.info(f"Total processed items found: {len(all_processed_links)}")

    if missing_items:
        logging.warning(f"Found {len(missing_items)} items potentially missing or failed:")
        # Sort missing items by title for easier reading
        missing_items.sort(key=lambda x: x['title'])
        for item in missing_items:
            logging.warning(f"  - MISSING: {item['title']} ({item['link']})")
    elif len(expected_items) > 0:
        logging.info("Verification complete: All expected items appear to have been processed (marked in tracker or corresponding file found).")
    else:
        logging.info("Verification complete, but no expected items were loaded.")
    logging.info("-" * 40)

if __name__ == "__main__":
    main()