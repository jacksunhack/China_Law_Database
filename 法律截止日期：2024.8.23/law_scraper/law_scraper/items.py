# law_scraper/items.py
import scrapy

class LawLinkItem(scrapy.Item):
    # Item for the initial link scraping (from LinkSpider)
    title = scrapy.Field()
    link = scrapy.Field()
    status = scrapy.Field() # Added status field from original script

class DocumentItem(scrapy.Item):
    # Item for the detailed document processing (from DocumentSpider)
    title = scrapy.Field()           # Original (possibly deduplicated) title
    original_link = scrapy.Field()   # The link visited by DocumentSpider
    download_link = scrapy.Field()   # Link obtained from QR code (nullable)
    iframe_link = scrapy.Field()     # Link of the iframe (nullable)
    text_content = scrapy.Field()    # Text content from the iframe (nullable)
    processed_status = scrapy.Field() # 'qr', 'iframe', 'error', 'skipped'