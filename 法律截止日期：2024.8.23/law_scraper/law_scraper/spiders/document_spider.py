# law_scraper/spiders/document_spider.py
import scrapy
import json
import os
import logging
from law_scraper.items import DocumentItem
from filelock import FileLock

logger = logging.getLogger(__name__)

class DocumentSpider(scrapy.Spider):
    name = 'document_spider'
    # No start_urls needed, we generate requests from a file

    # Define custom settings directly or ensure they are in settings.py
    custom_settings = {
        'ITEM_PIPELINES': {
            'law_scraper.pipelines.DocumentPipeline': 400,
        },
        'DOWNLOADER_MIDDLEWARES': {
            'law_scraper.middlewares.SeleniumMiddleware': 543,
        },
        # Consider adjusting these based on observations
        'CONCURRENT_REQUESTS': 2, # Lower concurrency is crucial for Selenium stability
        'DOWNLOAD_DELAY': 5,      # Increase delay helps avoid getting blocked/errors
        'RETRY_TIMES': 2,
        # Ensure these match settings.py or define them here if not using global settings
        # 'LINKS_INPUT_FILE': 'fl_links_modified.json',
        # 'PROCESSED_LINKS_FILE': 'fl_processed_links.json',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # It's best practice to rely on settings loaded by Scrapy
        self.links_input_file = self.settings.get('LINKS_INPUT_FILE', 'fl_links_modified.json') # Use modified file
        self.processed_links_file = self.settings.get('PROCESSED_LINKS_FILE', 'fl_processed_links.json')
        self.processed_links_lock = FileLock(self.processed_links_file + ".lock")
        self.processed_links = self._load_processed_links()
        logger.info(f"Loaded {len(self.processed_links)} previously processed links from {self.processed_links_file}.")

    def _load_processed_links(self):
        """Loads the set of already processed original links."""
        processed = set()
        with self.processed_links_lock:
            if os.path.exists(self.processed_links_file):
                try:
                    with open(self.processed_links_file, 'r', encoding='utf-8') as f:
                         content = f.read()
                         if content: # Handle empty file case
                             data = json.loads(content)
                             if isinstance(data, list):
                                 processed = set(data)
                             else:
                                 logger.warning(f"Expected a list in {self.processed_links_file}, found {type(data)}. Starting fresh.")
                         else:
                             logger.info(f"Processed links file {self.processed_links_file} is empty.")
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Error loading processed links file {self.processed_links_file}: {e}. Starting fresh.")
                except Exception as e:
                     logger.error(f"Unexpected error loading processed links file {self.processed_links_file}: {e}. Starting fresh.")
            else:
                logger.info(f"Processed links file {self.processed_links_file} not found. Starting fresh.")
        return processed

    def start_requests(self):
        if not os.path.exists(self.links_input_file):
            logger.error(f"Input file not found: {self.links_input_file}. Run link_spider and deduplicate_titles.py first.")
            return

        try:
            with open(self.links_input_file, 'r', encoding='utf-8') as f:
                links_to_process = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Could not read or parse input file {self.links_input_file}: {e}")
            return
        except Exception as e:
             logger.error(f"Unexpected error reading input file {self.links_input_file}: {e}")
             return


        queued_count = 0
        skipped_count = 0
        total_links = len(links_to_process)
        logger.info(f"Found {total_links} links in {self.links_input_file}. Comparing against {len(self.processed_links)} processed links.")

        for i, link_info in enumerate(links_to_process):
            original_link = link_info.get('link')
            title = link_info.get('title') # This is the potentially deduplicated title

            if not original_link or not title:
                 logger.warning(f"Skipping invalid entry #{i+1} in input file: {link_info}")
                 continue

            if original_link in self.processed_links:
                # logger.debug(f"Skipping already processed link: {title} ({original_link})") # DEBUG level might be too verbose
                skipped_count += 1
                continue

            queued_count += 1
            logger.info(f"Queueing request {queued_count}/{total_links - skipped_count}: {title} ({original_link})")
            yield scrapy.Request(
                url=original_link,
                callback=self.parse_document,
                meta={
                    'use_selenium': True, # Crucial: Tells middleware to handle this
                    'original_link': original_link, # Pass original link for tracking
                    'title': title, # Pass the (potentially modified) title
                    # Optional: Add specific wait condition for document pages if needed
                    # E.g., wait for the iframe or a container around the QR code
                    # 'wait_for': '#viewDoc, .qrcode-container' # Example: wait for either
                    },
                errback=self.handle_error # Add error callback
            )

        logger.info(f"Finished queueing requests. Total Queued: {queued_count}, Skipped (already processed): {skipped_count}")


    def parse_document(self, response):
        original_link = response.meta['original_link']
        title = response.meta['title']
        qr_link = response.meta.get('qr_link') # Set by middleware if found
        iframe_link = response.meta.get('iframe_link') # Set by middleware if found
        iframe_content = response.meta.get('iframe_content') # Set by middleware if found

        item = DocumentItem(title=title, original_link=original_link)

        # The middleware returns specific responses on error/not found
        # Handle these first
        if response.status == 503 and b"JavaScript Error Page" in response.body:
             logger.error(f"Middleware indicated JavaScript error for: {title} ({original_link})")
             item['processed_status'] = 'error'
             yield item
             return
        if response.status == 500 and b"Iframe Content Fetch Failed" in response.body:
             logger.error(f"Middleware indicated Iframe Content Fetch Failed for: {title} ({original_link})")
             item['processed_status'] = 'error'
             yield item
             return
        if response.status == 404 and b"No QR or Iframe Found" in response.body:
             logger.warning(f"Middleware indicated no QR or Iframe found for: {title} ({original_link})")
             item['processed_status'] = 'skipped' # Or 'error', depending on desired handling
             yield item
             return
        if response.status == 500: # General middleware error
             logger.error(f"Middleware indicated general processing error ({response.status}) for: {title} ({original_link}) - Body: {response.text[:200]}")
             item['processed_status'] = 'error'
             yield item
             return
        if response.status != 200:
             # Catch other non-200 responses that might slip through
             logger.error(f"Received non-200 status ({response.status}) for: {title} ({original_link}) - Body: {response.text[:200]}")
             item['processed_status'] = 'error'
             yield item
             return

        # If we reach here, middleware likely found something
        if qr_link:
            logger.info(f"Processing QR link found by middleware for: {title}")
            item['download_link'] = qr_link
            item['processed_status'] = 'qr'
        elif iframe_link and iframe_content:
            logger.info(f"Processing iframe content found by middleware for: {title}")
            item['iframe_link'] = iframe_link
            item['text_content'] = iframe_content
            item['processed_status'] = 'iframe'
        else:
             # This case should ideally be caught by the 404 check above
             logger.warning(f"Reached processing logic but no QR link or iframe content found in meta for: {title} ({original_link}) - This might indicate an issue in middleware logic.")
             item['processed_status'] = 'skipped'

        yield item

    def handle_error(self, failure):
         # Logs Scrapy-level request failures (timeouts, DNS errors, etc.)
        request = failure.request
        original_link = request.meta.get('original_link', request.url)
        title = request.meta.get('title', 'Unknown Title')
        logger.error(f"Scrapy Request failed for '{title}' ({original_link}): {failure.value}")

        # Yield an item indicating error so it's marked as processed
        item = DocumentItem(
            title=title,
            original_link=original_link,
            processed_status='error'
        )
        yield item