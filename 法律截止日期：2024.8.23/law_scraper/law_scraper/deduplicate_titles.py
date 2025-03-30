# deduplicate_titles.py (place in the root project folder)
import json
from collections import defaultdict
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Use settings from Scrapy project if possible, or define paths here
INPUT_FILE = 'fl_links.json' # Output from link_spider
OUTPUT_FILE = 'fl_links_modified.json' # Input for document_spider

def deduplicate():
    if not os.path.exists(INPUT_FILE):
        logging.error(f"Input file '{INPUT_FILE}' not found. Run the link_spider first.")
        return

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error reading input file '{INPUT_FILE}': {e}")
        return

    logging.info(f"Loaded {len(data)} entries from {INPUT_FILE}.")

    title_counts = defaultdict(int)
    modified_data = []
    duplicates_found = 0
    processed_count = 0

    for entry in data:
        processed_count += 1
        title = entry.get('title')
        if not title:
             logging.warning(f"Entry {processed_count} missing title, skipping: {entry}")
             continue

        original_title = title # Keep track for logging
        # Use the original title for counting duplicates
        count = title_counts[original_title]
        title_counts[original_title] += 1 # Increment count for this original title

        if count > 0: # This means it's a duplicate (count was already 1 or more)
            # Start numbering from 2 for duplicates
            entry['title'] = f"{original_title}_{count + 1}" # Modify the title in the entry
            duplicates_found += 1
            logging.info(f"Modified duplicate title: '{original_title}' -> '{entry['title']}'")
        # If count == 0, it's the first time seeing this title, keep entry['title'] as is

        modified_data.append(entry)

    logging.info(f"Processed {processed_count} entries.")

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
            json.dump(modified_data, file, ensure_ascii=False, indent=4)
        logging.info(f"Deduplication complete. Found and renamed {duplicates_found} duplicates based on original titles.")
        logging.info(f"Modified data saved to '{OUTPUT_FILE}'. Total entries: {len(modified_data)}")
    except IOError as e:
        logging.error(f"Error writing output file '{OUTPUT_FILE}': {e}")

if __name__ == "__main__":
    deduplicate()