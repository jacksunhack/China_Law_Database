# law_scraper/middlewares.py
import time
import os
import cv2 # Keep cv2 import
import gc
from scrapy import signals
from scrapy.http import HtmlResponse, TextResponse

# --- 修改 Selenium 导入 ---
from selenium import webdriver
# from selenium.webdriver.chrome.service import Service # 不再需要 Chrome 的 Service
from selenium.webdriver.edge.service import Service as EdgeService # 导入 Edge 的 Service
from selenium.webdriver.edge.options import Options as EdgeOptions # 导入 Edge 的 Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
# --- 修改 webdriver-manager 导入 ---
# from webdriver_manager.chrome import ChromeDriverManager # 不再需要 ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager # 使用 EdgeDriverManager

# REMOVED: from pyzbar.pyzbar import decode
from bs4 import BeautifulSoup
import logging
import re # For filename sanitization if needed here (less likely)

# Configure logging specifically for the middleware
logger = logging.getLogger(__name__)

class SeleniumMiddleware:
    def __init__(self, settings):
        self.screenshot_dir = settings.get('SELENIUM_SCREENSHOT_DIR', 'screenshots')
        self.processed_links_file = settings.get('PROCESSED_LINKS_FILE')
        self.download_dir = settings.get('DOWNLOAD_DIR', 'output_docs')

        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)

        self.selenium_headless = settings.getbool('SELENIUM_HEADLESS', True)
        self.page_load_timeout = settings.getint('SELENIUM_PAGE_LOAD_TIMEOUT', 30)
        self.element_wait_timeout = settings.getint('SELENIUM_ELEMENT_WAIT_TIMEOUT', 10)
        self.qr_wait_time = settings.getint('SELENIUM_QR_WAIT_TIME', 5)

        self.driver = self._init_driver()

    def _init_driver(self):
        """Initializes and returns a Selenium WebDriver instance for Edge."""
        try:
            logger.info("Initializing Selenium WebDriver for Microsoft Edge...")
            # --- 使用 EdgeDriverManager 和 EdgeService ---
            service = EdgeService(EdgeChromiumDriverManager().install())

            # --- 使用 EdgeOptions ---
            options = EdgeOptions()
            # 如果Edge浏览器不在标准路径，可能需要下面这行，并替换路径
            # options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

            # 通用选项 (适用于基于 Chromium 的 Edge)
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--enable-javascript")
            options.add_argument("--mute-audio")
            # 禁用通知等弹出窗口
            options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
            # 避免 "controlled by automated test software" 信息栏
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            if self.selenium_headless:
                 # Edge 的 Headless 模式参数与 Chrome 相同
                 options.add_argument("--headless")
                 # 对于较新版本的 Selenium 和 Edge，可能需要下面这个参数
                 # options.add_argument("--headless=new")
                 logger.info("Running Selenium in HEADLESS mode.")
            else:
                 logger.info("Running Selenium with browser window visible.")

            # --- 使用 webdriver.Edge ---
            driver = webdriver.Edge(service=service, options=options)

            logger.info("Selenium Edge WebDriver initialized successfully.")
            return driver
        except WebDriverException as e:
            logger.error(f"Failed to initialize Selenium Edge WebDriver: {e}")
            # --- 修改错误提示 ---
            logger.error("Check if Microsoft Edge is installed and accessible, and if msedgedriver can be downloaded/managed.")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during Edge WebDriver initialization: {e}")
            raise

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls(crawler.settings)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    # _wait_for_page_load, _decode_qr_code, _extract_iframe_link, _fetch_iframe_content
    # 这几个辅助函数不需要修改，它们是通用的

    def _wait_for_page_load(self, driver, url, timeout=None, condition=None):
        """Waits for page readiness and optional specific condition."""
        wait_timeout = timeout if timeout is not None else self.page_load_timeout
        logger.debug(f"Waiting up to {wait_timeout}s for page load (readyState) at {url}")
        try:
            WebDriverWait(driver, wait_timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            logger.debug(f"Page readyState is 'complete' for {url}.")

            if condition:
                logger.debug(f"Waiting up to {self.element_wait_timeout}s for specific condition: {condition} at {url}")
                if isinstance(condition, str): # Treat string as CSS selector
                     WebDriverWait(driver, self.element_wait_timeout).until(
                         EC.presence_of_element_located((By.CSS_SELECTOR, condition))
                     )
                     logger.debug(f"Condition element '{condition}' found for {url}.")
                elif isinstance(condition, tuple) and isinstance(condition[0], By): # Allow (By.ID, 'elementId')
                     WebDriverWait(driver, self.element_wait_timeout).until(
                         EC.presence_of_element_located(condition)
                     )
                     logger.debug(f"Condition element '{condition}' found for {url}.")
                elif callable(condition): # Allow custom lambda/function condition
                     WebDriverWait(driver, self.element_wait_timeout).until(condition)
                     logger.debug("Custom condition met for {url}.")
            return True # Success

        except TimeoutException:
            logger.warning(f"Timeout waiting for page load or condition for {url}")
            return False # Failure due to timeout
        except Exception as e:
            logger.warning(f"Error waiting for page load/condition for {url}: {e}")
            return False # Failure due to other error

    def _decode_qr_code(self, image_path, url):
        """Decodes QR code from an image file using OpenCV's detector."""
        logger.debug(f"Attempting to decode QR code from: {image_path} using cv2.QRCodeDetector")
        qr_data = None
        detector = None # Initialize detector outside try block
        try:
            if not os.path.exists(image_path):
                 logger.error(f"Screenshot file not found for decoding: {image_path}")
                 return None

            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to load image for QR decoding (cv2.imread returned None): {image_path}")
                return None

            detector = cv2.QRCodeDetector()
            retval, points, straight_qrcode = detector.detectAndDecode(img)

            if retval and retval.strip():
                qr_data = retval.strip()
                logger.info(f"QR Code decoded using cv2.QRCodeDetector from {os.path.basename(image_path)} for {url}: {qr_data}")
            else:
                 logger.info(f"No QR code detected or decoded by cv2.QRCodeDetector in {os.path.basename(image_path)} for {url}.")

        except ImportError:
            logger.error("Error during QR decoding: OpenCV (cv2) might not be installed correctly.")
        except Exception as e:
            logger.error(f"QR code decoding using cv2.QRCodeDetector failed for {image_path}: {e}")
            logger.error(f"Detector state: {detector}")
        finally:
             if os.path.exists(image_path):
                  try:
                       os.remove(image_path)
                  except OSError as e:
                       logger.error(f"Error removing screenshot {image_path}: {e}")
        return qr_data

    def _extract_iframe_link(self, driver, url):
         """Attempts to extract the src attribute of the #viewDoc iframe."""
         logger.debug(f"Attempting to find iframe #viewDoc for {url}...")
         try:
              iframe_element = WebDriverWait(driver, self.element_wait_timeout).until(
                   EC.presence_of_element_located((By.ID, "viewDoc"))
              )
              iframe_src = iframe_element.get_attribute("src")
              if iframe_src and iframe_src.strip():
                   from urllib.parse import urljoin
                   resolved_src = urljoin(driver.current_url, iframe_src.strip())
                   logger.info(f"Found iframe #viewDoc src for {url}: {resolved_src}")
                   return resolved_src
              else:
                   logger.warning(f"Found iframe #viewDoc for {url} but it has no valid src attribute.")
                   return None
         except TimeoutException:
              logger.warning(f"Could not find iframe #viewDoc within {self.element_wait_timeout}s for {url}.")
              return None
         except Exception as e:
              logger.warning(f"Error extracting iframe #viewDoc src for {url}: {e}")
              return None

    def _fetch_iframe_content(self, iframe_link, driver, original_url):
        """Navigates the *same* driver to the iframe URL and gets text content."""
        logger.info(f"Attempting to fetch content from iframe URL: {iframe_link} (related to {original_url})")
        try:
            driver.get(iframe_link)
            if not self._wait_for_page_load(driver, iframe_link, condition=(By.TAG_NAME, "body")):
                logger.warning(f"Failed to confirm page load or find body tag in iframe: {iframe_link}")

            try:
                body_element = driver.find_element(By.TAG_NAME, "body")
                body_text_iframe = body_element.text
                invalid_texts = ["Please enable JavaScript", "JavaScript is not enabled", "requires JavaScript"]
                for invalid in invalid_texts:
                    if invalid.lower() in body_text_iframe.lower():
                        logger.warning(f"Invalid text detected in iframe content ('{invalid}') for {iframe_link}")
                        return None
            except NoSuchElementException:
                 logger.warning(f"Could not find body tag in iframe after loading: {iframe_link}")
                 return None
            except Exception as e:
                 logger.warning(f"Error checking body text in iframe {iframe_link}: {e}")

            page_source = driver.page_source
            if not page_source:
                logger.warning(f"Got empty page source from iframe: {iframe_link}")
                return None

            soup = BeautifulSoup(page_source, 'html.parser')
            text_content = soup.get_text(separator="\n", strip=True)

            if text_content:
                logger.info(f"Successfully fetched and extracted text from iframe {iframe_link} (length: {len(text_content)}).")
                return text_content
            else:
                logger.warning(f"Extracted empty text content from iframe {iframe_link} despite getting page source.")
                return None

        except WebDriverException as e:
            logger.error(f"Selenium error navigating to or processing iframe {iframe_link}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching/processing iframe content from {iframe_link}: {e}")
            return None

    def process_request(self, request, spider):
        # Process only requests marked for Selenium
        if not request.meta.get('use_selenium'):
            return None

        url = request.url
        title = request.meta.get('title', 'Unknown Title')
        logger.info(f"Processing with Selenium: '{title}' ({url})")

        if not self.driver:
             logger.error("Selenium driver not initialized. Cannot process request.")
             return TextResponse(url=url, status=500, body=b"Selenium Driver Not Initialized", encoding='utf-8', request=request)

        try:
            self.driver.get(url)
            wait_condition = request.meta.get('wait_for')
            if not self._wait_for_page_load(self.driver, url, condition=wait_condition):
                 logger.error(f"Page load or wait condition failed for: {url}")
                 return TextResponse(url=url, status=504, body=b"Page Load Timeout or Condition Failed", encoding='utf-8', request=request)

            if spider.name == 'document_spider':
                qr_link = None
                iframe_link = None
                iframe_content = None

                # 1. Try QR Code
                safe_title_part = re.sub(r'[\\/*?:"<>|]', '_', title)[:50]
                timestamp = int(time.time())
                screenshot_filename = f"qr_check_{safe_title_part}_{timestamp}.png"
                screenshot_path = os.path.join(self.screenshot_dir, screenshot_filename)

                logger.debug(f"Waiting {self.qr_wait_time}s before taking screenshot for QR check...")
                time.sleep(self.qr_wait_time)
                logger.debug(f"Attempting to capture screenshot to: {screenshot_path}")
                try:
                    if self.driver.save_screenshot(screenshot_path):
                        logger.debug(f"Screenshot saved: {screenshot_path}")
                        qr_link = self._decode_qr_code(screenshot_path, url)
                        if qr_link:
                           logger.info(f"QR code link found for '{title}' ({url})")
                           request.meta['qr_link'] = qr_link
                           return TextResponse(url=url, status=200, body=b"QR Link Found", request=request)
                        else:
                            logger.info(f"No QR code detected for '{title}' ({url}). Checking for iframe.")
                    else:
                         logger.error(f"Failed to save screenshot (save_screenshot returned False) for {url}")
                except WebDriverException as e:
                     logger.error(f"Error saving screenshot for {url}: {e}")

                # 2. If no QR, try iframe
                if not qr_link:
                    iframe_link = self._extract_iframe_link(self.driver, url)
                    if iframe_link:
                        iframe_content = self._fetch_iframe_content(iframe_link, self.driver, url)
                        if iframe_content:
                            request.meta['iframe_link'] = iframe_link
                            request.meta['iframe_content'] = iframe_content
                            return TextResponse(url=url, status=200, body=b"Iframe Content Found", encoding='utf-8', request=request)
                        else:
                             logger.error(f"Failed to fetch content from iframe {iframe_link} for '{title}' ({url})")
                             return TextResponse(url=url, status=500, body=b"Iframe Content Fetch Failed", encoding='utf-8', request=request)
                    else:
                         logger.warning(f"No QR code and no usable iframe found for '{title}' ({url})")
                         return TextResponse(url=url, status=404, body=b"No QR or Iframe Found", encoding='utf-8', request=request)

            # --- Logic for other spiders (like LinkSpider) ---
            else:
                 logger.debug(f"Returning rendered HTML for {spider.name}: {url}")
                 body = self.driver.page_source
                 current_url = self.driver.current_url
                 return HtmlResponse(
                     url=current_url,
                     body=body.encode('utf-8'),
                     encoding='utf-8',
                     request=request
                 )

        except WebDriverException as e:
            logger.exception(f"Selenium WebDriver error processing {url} for '{title}': {e}")
            return TextResponse(url=url, status=500, body=f"Selenium WebDriver Error: {e}".encode('utf-8'), encoding='utf-8', request=request)
        except Exception as e:
            logger.exception(f"Unexpected error in SeleniumMiddleware for {url} ('{title}'): {e}")
            return TextResponse(url=url, status=500, body=f"Middleware Error: {e}".encode('utf-8'), encoding='utf-8', request=request)
        finally:
             gc.collect()

    def spider_closed(self, spider):
        if hasattr(self, 'driver') and self.driver:
            logger.info(f"Closing Selenium WebDriver for spider {spider.name}...")
            self.driver.quit()
            self.driver = None
            logger.info("Selenium WebDriver closed.")
        gc.collect()