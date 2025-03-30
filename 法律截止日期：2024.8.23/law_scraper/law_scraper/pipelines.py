# law_scraper/pipelines.py
import json
import os
import logging
import re # For filename sanitization
from filelock import FileLock, Timeout
from itemadapter import ItemAdapter

logger = logging.getLogger(__name__)

# --- File Locking Parameters ---
LOCK_TIMEOUT = 10 # Seconds to wait for a file lock

class LawLinkPipeline:
    """Pipeline for saving items from link_spider to a JSON file."""
    def __init__(self, settings):
        self.links_file_path = settings.get('LINKS_OUTPUT_FILE', 'fl_links.json')
        self.file = None
        self.item_count = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def open_spider(self, spider):
        # This pipeline should only run for link_spider
        if spider.name == 'link_spider':
            logger.info(f"Initializing LawLinkPipeline for spider '{spider.name}'")
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.links_file_path) or '.', exist_ok=True)
            # Open file in write mode, overwriting previous content
            try:
                self.file = open(self.links_file_path, 'w', encoding='utf-8')
                # Start JSON array structure
                self.file.write('[\n')
                self.item_count = 0
                logger.info(f"Opened links output file for writing: {self.links_file_path}")
            except IOError as e:
                logger.error(f"Failed to open links output file {self.links_file_path}: {e}")
                self.file = None # Ensure file is None if open failed

    def close_spider(self, spider):
        if spider.name == 'link_spider' and self.file:
            logger.info(f"Closing links output file: {self.links_file_path}")
            # End JSON array structure - handle case where no items were written
            if self.item_count > 0:
                # Go back one character to overwrite the last comma if needed (simplistic)
                 self.file.seek(self.file.tell() - 2) # Seek before ',\n'
                 self.file.truncate()
                 self.file.write('\n]')
            else:
                 # If no items, just close the opening bracket
                 self.file.write(']')

            self.file.close()
            self.file = None
            logger.info(f"Saved {self.item_count} link items to {self.links_file_path}")

    def process_item(self, item, spider):
        # Only process items from link_spider and if file is open
        if spider.name == 'link_spider' and self.file:
            adapter = ItemAdapter(item)
            line = json.dumps(adapter.asdict(), ensure_ascii=False)
            # Add comma before every item except the first one
            if self.item_count > 0:
                self.file.write(',\n')
            self.file.write(line)
            self.item_count += 1
            # logger.debug(f"Saved link item: {adapter.get('title')}") # Verbose
        # Always return the item for potential further processing by other pipelines
        return item


class DocumentPipeline:
    """Pipeline for processing items from document_spider:
       - Saves QR download links to fl_down.json.
       - Saves iframe text content to .txt files in output_docs/.
       - Maintains a set of processed original_links in fl_processed_links.json.
    """
    def __init__(self, settings):
        self.download_dir = settings.get('DOWNLOAD_DIR', 'output_docs')
        self.down_links_file = settings.get('QR_LINKS_OUTPUT_FILE', 'fl_down.json')
        self.processed_links_file = settings.get('PROCESSED_LINKS_FILE', 'fl_processed_links.json')

        # Initialize locks - ensure lock files are distinct if paths could be the same
        self.down_links_lock_path = self.down_links_file + ".lock"
        self.processed_links_lock_path = self.processed_links_file + ".lock"
        self.down_links_lock = FileLock(self.down_links_lock_path, timeout=LOCK_TIMEOUT)
        self.processed_links_lock = FileLock(self.processed_links_lock_path, timeout=LOCK_TIMEOUT)

        self.processed_links = set() # In-memory set of processed links for this run
        self.down_links_data = [] # In-memory list of QR links for this run

        os.makedirs(self.download_dir, exist_ok=True)
        # Ensure directories for JSON files exist
        os.makedirs(os.path.dirname(self.down_links_file) or '.', exist_ok=True)
        os.makedirs(os.path.dirname(self.processed_links_file) or '.', exist_ok=True)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def open_spider(self, spider):
        if spider.name == 'document_spider':
            logger.info(f"Initializing DocumentPipeline for spider '{spider.name}'")
            # Load existing state at the beginning
            self.processed_links = self._load_json_set(self.processed_links_file, self.processed_links_lock)
            self.down_links_data = self._load_json_list(self.down_links_file, self.down_links_lock)
            logger.info(f"Loaded {len(self.processed_links)} previously processed links from {self.processed_links_file}.")
            logger.info(f"Loaded {len(self.down_links_data)} existing QR download links from {self.down_links_file}.")

    def close_spider(self, spider):
         if spider.name == 'document_spider':
            logger.info("Closing DocumentPipeline, saving final state...")
            # Save the final state at the end
            # Note: This assumes the lists/sets contain the *complete* desired state.
            self._save_json_list(self.down_links_file, self.down_links_data, self.down_links_lock)
            self._save_json_set(self.processed_links_file, self.processed_links, self.processed_links_lock)
            logger.info(f"Saved {len(self.down_links_data)} QR links to {self.down_links_file}.")
            logger.info(f"Saved {len(self.processed_links)} processed links tracker to {self.processed_links_file}.")
            # Release lock files explicitly if needed, though context manager handles it
            # if os.path.exists(self.down_links_lock_path): os.remove(self.down_links_lock_path)
            # if os.path.exists(self.processed_links_lock_path): os.remove(self.processed_links_lock_path)


    def _load_json_set(self, filepath, lock):
        """Loads data from a JSON file expected to contain a list, returns a set."""
        data_set = set()
        logger.debug(f"Acquiring lock for loading set: {lock.lock_file}")
        try:
            with lock:
                logger.debug(f"Lock acquired for loading set: {lock.lock_file}")
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                data_set = set(data)
                            else:
                                logger.warning(f"Expected a list in {filepath}, found {type(data)}. Starting with an empty set.")
                    except (json.JSONDecodeError, IOError) as e:
                        logger.error(f"Error loading or parsing JSON set from {filepath}: {e}. Starting with an empty set.")
                    except Exception as e:
                         logger.error(f"Unexpected error loading JSON set from {filepath}: {e}. Starting with an empty set.")
                elif os.path.exists(filepath):
                     logger.info(f"File exists but is empty, starting with empty set: {filepath}")
                else:
                    logger.info(f"File not found, starting with empty set: {filepath}")
        except Timeout:
             logger.error(f"Timeout acquiring lock for loading set: {lock.lock_file}. Returning empty set.")
        except Exception as e:
             logger.error(f"Error acquiring lock for loading set {lock.lock_file}: {e}. Returning empty set.")
        finally:
            logger.debug(f"Lock released (implicitly) for loading set: {lock.lock_file}")
        return data_set

    def _save_json_set(self, filepath, data_set, lock):
        """Saves a set to a JSON file as a list."""
        logger.debug(f"Acquiring lock for saving set: {lock.lock_file}")
        try:
            with lock:
                logger.debug(f"Lock acquired for saving set: {lock.lock_file}")
                try:
                    # Convert set to list for JSON serialization
                    data_list = sorted(list(data_set)) # Sort for consistency
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data_list, f, ensure_ascii=False, indent=4)
                    # logger.debug(f"Saved {len(data_list)} items to {filepath}") # Verbose
                except IOError as e:
                    logger.error(f"Error saving JSON set to {filepath}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error saving JSON set to {filepath}: {e}")
        except Timeout:
             logger.error(f"Timeout acquiring lock for saving set: {lock.lock_file}. Save failed.")
        except Exception as e:
             logger.error(f"Error acquiring lock for saving set {lock.lock_file}: {e}. Save failed.")
        finally:
            logger.debug(f"Lock released (implicitly) for saving set: {lock.lock_file}")

    def _load_json_list(self, filepath, lock):
        """Loads data from a JSON file expected to contain a list, returns a list."""
        data_list = []
        logger.debug(f"Acquiring lock for loading list: {lock.lock_file}")
        try:
            with lock:
                logger.debug(f"Lock acquired for loading list: {lock.lock_file}")
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                data_list = data
                            else:
                                logger.warning(f"Expected a list in {filepath}, found {type(data)}. Starting with an empty list.")
                    except (json.JSONDecodeError, IOError) as e:
                        logger.error(f"Error loading or parsing JSON list from {filepath}: {e}. Starting with an empty list.")
                    except Exception as e:
                        logger.error(f"Unexpected error loading JSON list from {filepath}: {e}. Starting with an empty list.")
                elif os.path.exists(filepath):
                     logger.info(f"File exists but is empty, starting with empty list: {filepath}")
                else:
                    logger.info(f"File not found, starting with empty list: {filepath}")
        except Timeout:
             logger.error(f"Timeout acquiring lock for loading list: {lock.lock_file}. Returning empty list.")
        except Exception as e:
             logger.error(f"Error acquiring lock for loading list {lock.lock_file}: {e}. Returning empty list.")
        finally:
            logger.debug(f"Lock released (implicitly) for loading list: {lock.lock_file}")
        return data_list

    def _save_json_list(self, filepath, data_list, lock):
        """Saves a list to a JSON file."""
        logger.debug(f"Acquiring lock for saving list: {lock.lock_file}")
        try:
            with lock:
                logger.debug(f"Lock acquired for saving list: {lock.lock_file}")
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data_list, f, ensure_ascii=False, indent=4)
                    # logger.debug(f"Saved {len(data_list)} items to {filepath}") # Verbose
                except IOError as e:
                    logger.error(f"Error saving JSON list to {filepath}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error saving JSON list to {filepath}: {e}")
        except Timeout:
            logger.error(f"Timeout acquiring lock for saving list: {lock.lock_file}. Save failed.")
        except Exception as e:
            logger.error(f"Error acquiring lock for saving list {lock.lock_file}: {e}. Save failed.")
        finally:
            logger.debug(f"Lock released (implicitly) for saving list: {lock.lock_file}")

    def get_safe_filename_base(self, title):
        """
        Generates a safe base filename (without .txt) from a title.
        !!! MUST MATCH the sanitization logic in verify_completion.py !!!
        """
        if not title: return "unknown_title"
        # Replace invalid filesystem characters with underscore
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
        # Remove leading/trailing whitespace and underscores
        safe_title = safe_title.strip().strip('_')
         # Replace multiple consecutive underscores with a single one
        safe_title = re.sub(r'_+', '_', safe_title)
        # Limit length (e.g., to 200 chars) to avoid filesystem issues
        return safe_title[:200]

    def process_item(self, item, spider):
        if spider.name == 'document_spider':
            adapter = ItemAdapter(item)
            original_link = adapter.get('original_link')
            title = adapter.get('title', 'unknown_title') # Use the (potentially modified) title

            if not original_link:
                 logger.error(f"Item missing 'original_link', cannot process: {item}")
                 return item # Cannot track without link

            processed_status = adapter.get('processed_status')
            added_to_processed = False # Flag to ensure we add to set only once per item

            if processed_status == 'qr':
                download_link = adapter.get('download_link')
                if download_link:
                    # Prepare entry for the QR download list
                    entry = {"title": title, "download_link": download_link, "original_link": original_link}
                    # Avoid adding exact duplicates to the download list within this run
                    # Check based on original_link to prevent reprocessing same source link
                    if not any(e['original_link'] == original_link for e in self.down_links_data):
                         self.down_links_data.append(entry)
                         logger.info(f"Added QR link for '{title}' to save list.")
                    else:
                         logger.debug(f"QR link for '{title}' ({original_link}) already in save list.")
                    # Mark this original_link as processed
                    self.processed_links.add(original_link)
                    added_to_processed = True
                else:
                     logger.warning(f"Item has status 'qr' but missing 'download_link': {title}")
                     # Mark as processed even if link missing, to avoid retrying? Or mark as error?
                     self.processed_links.add(original_link) # Treat as processed (attempted)
                     added_to_processed = True


            elif processed_status == 'iframe':
                text_content = adapter.get('text_content')
                if text_content:
                    # Generate safe filename using the consistent function
                    safe_base_name = self.get_safe_filename_base(title)
                    filename = os.path.join(self.download_dir, f"{safe_base_name}.txt")
                    try:
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(text_content)
                        logger.info(f"Saved iframe text content to: {os.path.basename(filename)}")
                        # Mark this original_link as processed
                        self.processed_links.add(original_link)
                        added_to_processed = True
                    except IOError as e:
                        logger.error(f"Failed to save text file {filename}: {e}")
                        # Don't mark as processed if save failed, allow retry? Or mark as error?
                        # For now, let's NOT mark as processed if file write fails.
                    except Exception as e:
                        logger.error(f"Unexpected error saving text file {filename}: {e}")

                else:
                     logger.warning(f"Received iframe status for '{title}' but no text content found in item.")
                     # Mark as processed (attempted) even if content was empty/missing?
                     self.processed_links.add(original_link)
                     added_to_processed = True

            elif processed_status in ['error', 'skipped']:
                 logger.warning(f"Item for '{title}' ({original_link}) finished with status: '{processed_status}'")
                 # Mark errors/skipped items as processed to avoid retrying them indefinitely
                 self.processed_links.add(original_link)
                 added_to_processed = True

            else:
                 # Should not happen if spider and middleware work correctly
                 logger.error(f"Unknown processed_status '{processed_status}' for item: {title} ({original_link})")
                 # Decide whether to mark as processed or not
                 self.processed_links.add(original_link) # Mark as processed to be safe
                 added_to_processed = True


            # Optional: Periodically save progress (e.g., every N items)
            # This adds overhead but saves state more frequently in case of crashes.
            # N = 50 # Example: save every 50 items
            # if added_to_processed and len(self.processed_links) % N == 0:
            #    logger.info(f"Periodically saving state ({len(self.processed_links)} processed)...")
            #    self._save_json_set(self.processed_links_file, self.processed_links, self.processed_links_lock)
            #    self._save_json_list(self.down_links_file, self.down_links_data, self.down_links_lock)

        return item # Pass item along