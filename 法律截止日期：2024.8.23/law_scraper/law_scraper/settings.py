# law_scraper/settings.py

BOT_NAME = 'law_scraper'

SPIDER_MODULES = ['law_scraper.spiders']
NEWSPIDER_MODULE = 'law_scraper.spiders'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
# !!! CHANGE THIS TO SOMETHING DESCRIPTIVE AND RESPECTFUL !!!
USER_AGENT = 'law_scraper (compatible; +http://your_contact_or_project_url.com)'

# Obey robots.txt rules? Check the target site's robots.txt first.
# Setting to False bypasses it, but ensure you are allowed to scrape.
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
# !!! Lower this significantly when using Selenium !!!
CONCURRENT_REQUESTS = 2 # Start low (1 or 2) and increase cautiously

# Configure a delay for requests for the same website (default: 0)
# Increase delay when using Selenium to be less aggressive
DOWNLOAD_DELAY = 5 # Start with a higher value (3-10 seconds)

# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 2 # Match CONCURRENT_REQUESTS
#CONCURRENT_REQUESTS_PER_IP = 16 # Less relevant if CONCURRENT_REQUESTS_PER_DOMAIN is set

# Disable cookies (enabled by default) - May break sites requiring login/session
# COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
TELNETCONSOLE_ENABLED = False

# Override the default request headers:
# DEFAULT_REQUEST_HEADERS = {
#   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#   'Accept-Language': 'en-US,en;q=0.9', # Example
# }

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#    'law_scraper.middlewares.LawScraperSpiderMiddleware': 543,
# }

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
   # Retry middleware is essential for handling network issues
   'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
   # Custom Selenium Middleware - runs after retry but before default HTTP handling
   'law_scraper.middlewares.SeleniumMiddleware': 543,
   # Default UserAgentMiddleware, HttpProxyMiddleware etc. run later
   'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None, # Disable default if setting custom one
   'scrapy_user_agents.middlewares.RandomUserAgentMiddleware': 400, # Example using external middleware
}
# Example setting for scrapy-user-agents (install it: pip install scrapy-user-agents)
# USER_AGENT_LIST = "user_agents.txt" # Path to a file with user agents, one per line

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
   # Pipeline for saving initial links (run ONLY by link_spider)
   'law_scraper.pipelines.LawLinkPipeline': 300,
   # Pipeline for processing documents (run ONLY by document_spider)
   'law_scraper.pipelines.DocumentPipeline': 400,
}

# Enable and configure the AutoThrottle extension (optional but recommended)
# Helps adjust crawling speed automatically based on server load
# AUTOTHROTTLE_ENABLED = True
# The initial download delay
# AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
# AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
# AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0 # Start low with Selenium
# Enable showing throttling stats for every response received:
# AUTOTHROTTLE_DEBUG = False # Set to True for debugging throttling

# Enable and configure HTTP caching (optional)
# Useful for development to avoid re-downloading same pages
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 0 # Never expire (for development)
# HTTPCACHE_DIR = 'httpcache'
# HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 408, 404] # Don't cache errors
# HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# --- Custom Settings ---

# 1. File Paths (relative to project root where scrapy.cfg is)
LINKS_OUTPUT_FILE = 'fl_links.json'          # Output from link_spider
LINKS_INPUT_FILE = 'fl_links_modified.json'  # Input for document_spider (after deduplication)
QR_LINKS_OUTPUT_FILE = 'fl_down.json'        # QR download links from DocumentPipeline
PROCESSED_LINKS_FILE = 'fl_processed_links.json' # Tracks processed original_links (DocumentPipeline)
DOWNLOAD_DIR = 'output_docs'                 # Dir for saved .txt files (DocumentPipeline) and downloads (download_files.py)

# 2. Selenium Settings
SELENIUM_HEADLESS = True                     # Run Chrome without UI (True/False)
SELENIUM_SCREENSHOT_DIR = 'screenshots'      # Directory for temporary QR screenshots (Middleware)
SELENIUM_PAGE_LOAD_TIMEOUT = 45              # Max seconds to wait for initial page load (readyState)
SELENIUM_ELEMENT_WAIT_TIMEOUT = 15           # Max seconds to wait for specific elements (e.g., iframe, wait_for condition)
SELENIUM_QR_WAIT_TIME = 5                    # Seconds to pause before taking QR screenshot

# 3. Logging Configuration
LOG_LEVEL = 'INFO' # Use 'DEBUG' for very verbose output including middleware/pipeline details
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'
# Optional: Log to a file
# LOG_FILE = 'scrapy_log.txt'
# LOG_FILE_APPEND = False # Overwrite log file each run

# Optional: Request Fingerprinter (if needed for complex duplicates)
# DUPEFILTER_CLASS = 'scrapy.dupefilters.RFPDupeFilter'
# DUPEFILTER_DEBUG = True # Show duplicate filter logs

# Retry settings (if defaults aren't enough)
RETRY_TIMES = 3 # Number of times to retry failed requests
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429] # Codes to retry on