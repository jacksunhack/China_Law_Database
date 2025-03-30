# law_scraper/spiders/link_spider.py
import scrapy
from law_scraper.items import LawLinkItem
import time
import logging

# --- Selenium imports ---
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)

# --- Scrapy signals imports ---
from scrapy import signals
from pydispatch import dispatcher

# Use Scrapy's logger
logger = logging.getLogger(__name__)

class LinkSpider(scrapy.Spider):
    name = 'link_spider'
    allowed_domains = ['flk.npc.gov.cn']
    start_urls = ['']

    custom_settings = {
        'ITEM_PIPELINES': {
            'law_scraper.pipelines.LawLinkPipeline': 300,
        },
        'DOWNLOADER_MIDDLEWARES': {
            'law_scraper.middlewares.SeleniumMiddleware': 543,
        },
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.driver = None
        self.page_number = 1  # Track page number for logging
        self.consecutive_empty_pages = 0  # Track empty pages to avoid infinite loops
        dispatcher.connect(self.handle_spider_opened, signal=signals.spider_opened)

    def handle_spider_opened(self, spider):
        if spider is not self:
            return
        logger.info("Spider opened signal received. Attempting to find Selenium driver...")
        try:
            if not hasattr(self, 'crawler'): logger.error("'crawler' attribute not found..."); return
            if not hasattr(self.crawler, 'engine') or not self.crawler.engine: logger.error("'engine' attribute not found..."); return
            if not hasattr(self.crawler.engine, 'downloader') or not self.crawler.engine.downloader: logger.error("'downloader' attribute not found..."); return
            if not hasattr(self.crawler.engine.downloader, 'middleware') or not self.crawler.engine.downloader.middleware: logger.error("'middleware' attribute not found..."); return

            selenium_mw_cls = self.get_selenium_middleware_class()
            if not selenium_mw_cls: logger.error("Could not get SeleniumMiddleware class type."); return

            selenium_middleware_instance = None
            for mw in self.crawler.engine.downloader.middleware.middlewares:
                if isinstance(mw, selenium_mw_cls): selenium_middleware_instance = mw; break

            if selenium_middleware_instance:
                self.driver = getattr(selenium_middleware_instance, 'driver', None)
                if self.driver: logger.info("Successfully obtained driver reference via spider_opened signal.")
                else: logger.error("SeleniumMiddleware instance found, but 'driver' attribute is missing or None.")
            else: logger.error("SeleniumMiddleware instance not found in downloader middlewares!")
        except AttributeError as e: logger.error(f"AttributeError accessing crawler components: {e}.")
        except Exception as e: logger.error(f"Unexpected error finding SeleniumMiddleware via spider_opened: {e}.")

    @staticmethod
    def get_selenium_middleware_class():
        try:
            from law_scraper.middlewares import SeleniumMiddleware
            return SeleniumMiddleware
        except ImportError:
            logger.error("Could not import SeleniumMiddleware.")
            return None

    def start_requests(self):
        for url in self.start_urls:
            logger.info(f"Starting request for {url} using Selenium")
            yield scrapy.Request(url, meta={'use_selenium': True, 'wait_for': 'tr.list-b'})

    def parse(self, response):
        if not self.driver:
             if hasattr(self, 'crawler') and hasattr(self.crawler, 'engine'):
                 if hasattr(self.crawler.engine, 'downloader') and hasattr(self.crawler.engine.downloader, 'middleware'):
                     selenium_mw_cls = self.get_selenium_middleware_class()
                     if selenium_mw_cls:
                        for mw in self.crawler.engine.downloader.middleware.middlewares:
                            if isinstance(mw, selenium_mw_cls): self.driver = getattr(mw, 'driver', None); break
             if not self.driver:
                 logger.error("Selenium driver not available in parse method. Cannot perform pagination.")
                 yield from self._parse_rows(response)
                 return
             else: logger.debug("Driver reference re-acquired in parse method.")

        logger.info(f"Processing page {self.page_number}: {response.url}")

        # Make sure the page is fully loaded
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.list-box"))
            )
            # Add a more reliable wait condition - wait until the loading spinner is gone
            # or wait for a specific element that indicates the data is loaded
            time.sleep(3)  # Give extra time for data to load
        except Exception as e:
            logger.warning(f"Wait condition error: {e}")

        # Now parse the rows
        yielded_count, no_data_found = yield from self._parse_rows(response)
        
        logger.info(f"Page {self.page_number}: Found {yielded_count} items, no_data_message: {no_data_found}")

        # If we didn't find any data but detected the "no data" message
        if no_data_found and yielded_count == 0:
            self.consecutive_empty_pages += 1
            # Stop if we get multiple empty pages in a row (safety check)
            if self.consecutive_empty_pages >= 3:
                logger.info("Multiple consecutive empty pages. Stopping pagination.")
                return
            
            # Important: If we found the "no data" message but it might be temporary,
            # we'll attempt to verify with a retry
            logger.info("Found 'no data' message, but it might be temporary. Retrying...")
            time.sleep(5)  # Extended wait time for data to potentially load
            
            # Re-check if rows have appeared after the wait
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, 'tr.list-b')
                
                # Check if any row contains actual data (not the "no data" message)
                has_data = False
                for row in rows:
                    text = row.text.strip()
                    if text and "没有满足条件的数据" not in text:
                        has_data = True
                        break
                
                if has_data:
                    logger.info("Data appeared after additional wait! Continuing with pagination.")
                    yielded_count, no_data_found = yield from self._parse_rows(response)
                    
                    if yielded_count > 0:
                        self.consecutive_empty_pages = 0  # Reset counter if we found data
                    else:
                        logger.info("Still no data found after retry. Stopping pagination.")
                        return
                else:
                    logger.info("No data appeared after additional wait. This may be the true end.")
                    return
            except Exception as e:
                logger.error(f"Error during retry check: {e}")
                return
        elif yielded_count > 0:
            # If we found data, reset the consecutive empty pages counter
            self.consecutive_empty_pages = 0

        # Pagination logic
        next_button_selector = 'a.layui-laypage-next'
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, next_button_selector))
            )
            next_page_button = self.driver.find_element(By.CSS_SELECTOR, next_button_selector)

            button_classes = next_page_button.get_attribute('class') or ""
            if 'layui-disabled' in button_classes:
                logger.info(f"Next page button is disabled on page {self.page_number}. Reached the last page.")
                return

            logger.info(f"Clicking next page button for page {self.page_number}...")
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", next_page_button)
                time.sleep(0.5)
                next_page_button.click()
            except StaleElementReferenceException as stale_err:
                logger.warning(f"Next page button became stale: {stale_err}. Retrying...")
                next_page_button = self.driver.find_element(By.CSS_SELECTOR, next_button_selector)
                next_page_button.click()
            except Exception as click_err:
                logger.error(f"Error clicking next page button: {click_err}")
                return

            self.page_number += 1  # Increment page number after click

            # Wait for the page to reload
            wait_timeout = 20
            logger.info(f"Waiting up to {wait_timeout}s for pagination controls to reload...")
            try:
                WebDriverWait(self.driver, wait_timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, next_button_selector))
                )
                logger.info("Pagination controls (next button) re-appeared in DOM.")
                time.sleep(2)  # Increased wait time

                # Additional wait for table rows to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.list-box"))
                )

                # Check if next button is now disabled
                current_next_button = self.driver.find_element(By.CSS_SELECTOR, next_button_selector)
                current_classes = current_next_button.get_attribute('class') or ""
                if 'layui-disabled' in current_classes:
                    logger.info(f"Next page button re-appeared but is now disabled on page {self.page_number}. Reached the last page.")
                    return
                else:
                    logger.info(f"Next page button re-appeared and is not disabled on page {self.page_number}.")
            except TimeoutException:
                logger.warning(f"Timed out waiting for next button to re-appear after {wait_timeout}s. Assuming end.")
                return
            except Exception as e:
                logger.error(f"Unexpected error during pagination presence wait: {e}")
                return

            # Give extra time for data to fully load
            additional_wait = 5  # Increased from 2s to 5s
            logger.info(f"Adding additional sleep of {additional_wait}s for data table to load...")
            time.sleep(additional_wait)

            # Check for visible data before continuing
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, 'tr.list-b')
                visible_rows = [row for row in rows if row.is_displayed()]
                logger.info(f"Found {len(visible_rows)} visible rows after additional wait")
            except Exception as e:
                logger.warning(f"Error checking visible rows: {e}")

            logger.info(f"Yielding request to re-parse URL after pagination to page {self.page_number}: {response.url}")
            new_meta = response.meta.copy()
            yield scrapy.Request(url=response.url, callback=self.parse, meta=new_meta, dont_filter=True)

        except NoSuchElementException: 
            logger.info(f"Could not find the next page button on page {self.page_number}. Reached the end.")
        except StaleElementReferenceException: 
            logger.warning(f"Next page button became stale on page {self.page_number}. Stopping pagination.")
        except TimeoutException: 
            logger.warning(f"Timed out waiting for next page button on page {self.page_number}. Assuming end.")
        except WebDriverException as e: 
            logger.error(f"Selenium WebDriver error during pagination on page {self.page_number}: {e}")
        except Exception as e: 
            logger.error(f"Unexpected error during pagination logic on page {self.page_number}: {e}")

    def _parse_rows(self, response):
        """
        Helper method to parse rows on the current page and generate items.
        Returns: Tuple (yielded_count, no_data_found)
        """
        rows = response.css('tr.list-b')
        row_count = 0
        yielded_count = 0
        skipped_count = 0
        no_data_found = False

        for row in rows:
            row_count += 1
            no_data_header = row.css('td > h1.l-sx::text').get()
            if no_data_header and "没有满足条件的数据" in no_data_header.strip():
                logger.info(f"Found '没有满足条件的数据' row on page {self.page_number}.")
                no_data_found = True
                # Important: Don't break here! Continue checking if there are other rows with data
                continue

            # Skip this row if it's the "no data" message but continue checking other rows
            if not row.css('td.l-sx3 h2.l-wen1'):
                logger.debug(f"Row {row_count} on page {self.page_number} doesn't have expected structure, may be non-data row.")
                continue

            status_elements = row.css('td.l-sx3 h2.l-wen1::text').getall()
            if not status_elements:
                logger.debug(f"Row {row_count} on page {self.page_number}: No status elements found.")
                continue
                
            status = status_elements[-1].strip() if status_elements[-1].strip() else "Status Unknown"
            title_element = row.css('li.l-wen')
            title = title_element.css('::attr(title)').get()
            onclick_attr = title_element.css('::attr(onclick)').get()

            if not title or not onclick_attr:
                logger.warning(f"Row {row_count} on page {self.page_number}: Could not extract title or onclick from row.")
                continue
            title = title.strip()

            if '已废止' in status:
                logger.info(f"Row {row_count} on page {self.page_number}: Skipping '已废止': {title}")
                skipped_count += 1
                continue

            try:
                link_part_raw = onclick_attr.split("showDetail('")[1].split("')")[0]
                full_link = response.urljoin(link_part_raw)
            except IndexError: 
                logger.error(f"Row {row_count} on page {self.page_number}: Could not parse link from onclick: '{onclick_attr}' for '{title}'")
                continue
            except Exception as e: 
                logger.error(f"Row {row_count} on page {self.page_number}: Error processing onclick '{onclick_attr}' for '{title}': {e}")
                continue

            item = LawLinkItem(title=title, link=full_link, status=status)
            yield item
            yielded_count += 1

        logger.info(f"Page {self.page_number} processing complete: {yielded_count} items yielded, {skipped_count} skipped, no_data_found: {no_data_found}")
        return yielded_count, no_data_found

