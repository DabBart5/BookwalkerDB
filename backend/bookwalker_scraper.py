"""
Bookwalker DB - Web scraping system for tracking book prices and details
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
BOOKWALKER_BASE_URL = "https://bookwalker.jp"
SCRAPING_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

SCRAPE_SITES = ['campaigns', 'sales', 'coin_up', 'new_releases']


class BookCategory(Enum):
    """Enum for book categories"""
    LIGHT_NOVEL = "light_novel"
    MANGA = "manga"
    NOVEL = "novel"
    BOOK = "book"
    COMIC = "comic"


class SaleType(Enum):
    """Type of sale/promotion"""
    NORMAL = "normal"
    ON_SALE = "on_sale"
    COIN_UP = "coin_up"
    CAMPAIGN = "campaign"


# =============================================================================
# MODELS / DATA STRUCTURES
# =============================================================================

class Book:
    """Represents a book with all its attributes"""
    
    def __init__(self):
        self.book_id: str = None  # Bookwalker UUID
        self.name: str = None
        self.release_date: datetime = None
        self.announcement_date: datetime = None
        self.isbn: str = None
        self.category: BookCategory = None
        self.series: str = None # Foreign key to Series
        self.volume_number: Optional[int] = None
        self.page_count: Optional[int] = None
        self.image_url: str = None
        self.book_url: str = None
        self.currency: str = "JPY"
        self.is_currently_on_sale: bool = False
        self.details_needed: bool = True  # Mark for detailed scraping
        self.tags: List[str] = [] # TODO: Remove this?
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()
        self.next_review_date: Optional[datetime] = None



class PriceEntry:
    """Represents a price history entry for a book"""
    
    def __init__(self):
        self.book_id: str = None # Foreign key to Book
        self.normal_price: float = None
        self.sale_price: Optional[float] = None
        self.coin_back: Optional[float] = None  # % or absolute value
        self.is_free: bool = False
        self.campaign_name: Optional[str] = None
        self.sale_type: SaleType = SaleType.NORMAL
        self.entry_date: datetime = datetime.now()
        self.end_date: Optional[datetime] = None


class Campaign:
    """Represents a promotion campaign"""
    
    def __init__(self):
        self.campaign_id: str = None
        self.name: str = None
        self.description: Optional[str] = None
        self.start_date: datetime = None
        self.end_date: datetime = None
        self.campaign_type: str = None  # e.g., "60% coin up"
        self.created_at: datetime = datetime.now()

class Series:
    """Represents a book series"""
    
    def __init__(self):
        self.series_id: str = None
        self.name: str = None
        self.author: str = None
        self.publisher: str = None
        self.label: str = None

# =============================================================================
# DATABASE INTERFACE (placeholder for future DB implementation)
# =============================================================================

class BookDatabase:
    """Interface for database operations"""
    
    def __init__(self):
        """Initialize database connection"""
        logger.info("Initializing database...")
        # TODO: Implement actual database connection (SQLite, PostgreSQL, etc.)
        self.books: Dict[str, Book] = {}
        self.prices: List[PriceEntry] = []
        self.campaigns: Dict[str, Campaign] = {}
        self.series: Dict[str, Series] = {}
    def add_or_update_book(self, book: Book) -> bool:
        """Add new book or update existing one"""
        if book.book_id in self.books:
            existing = self.books[book.book_id]
            existing.updated_at = datetime.now()
            logger.info(f"Updated book: {book.name}")
        else:
            logger.info(f"Added new book: {book.name}")
        self.books[book.book_id] = book
        return True
    
    def add_price_entry(self, price_entry: PriceEntry) -> bool:
        """Add price history entry"""
        self.prices.append(price_entry)
        logger.info(f"Added price entry for book {price_entry.book_id}")
        return True
    
    def get_book(self, book_id: str) -> Optional[Book]:
        """Retrieve book by ID"""
        return self.books.get(book_id)
    
    def get_books_needing_details(self) -> List[Book]:
        """Get all books marked as needing detailed scraping"""
        return [b for b in self.books.values() if b.details_needed]
    
    def mark_details_complete(self, book_id: str):
        """Mark book details as scraped"""
        if book_id in self.books:
            self.books[book_id].details_needed = False
            logger.info(f"Marked details complete for {book_id}")


# =============================================================================
# WEB SCRAPING FUNCTIONS
# =============================================================================

class BookwalkerScraper:
    """Main scraper for Bookwalker website"""
    
    def __init__(self, db: BookDatabase):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update(SCRAPING_HEADERS)
        retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
    
    def overview_web_scraping(self, site: str, sort_by_date: bool = True) -> List[Book]:
        """
        Scrape overview pages (sales, campaigns, new releases, coin up)
        Returns newly found books
        
        Args:
            site: Type of site to scrape (campaigns, sales, coin_up, new_releases)
            sort_by_date: Sort results by date descending
        
        Returns:
            List of newly discovered books
        """
        logger.info(f"Starting overview scraping for: {site}")
        new_books = []
        
        try:

            #leave out sorting by new since thats the standard anyway

            # Build URL based on site type
            url = self._build_overview_url(site)
            
            # Fetch page
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse book items from overview page
            books = self._parse_overview_page(soup, site)
            logger.info(f"Found {len(books)} books on {site}")
            
            # Check if already in DB and add if new
            for book in books:
                existing = self.db.get_book(book.book_id)
                
                if not existing:
                    new_books.append(book)
                    self.db.add_or_update_book(book)
                    logger.info(f"New book found: {book.name}")
                else:
                    # Update if necessary (price changed, etc.)
                    self._update_book_if_changed(existing, book)
            
            logger.info(f"Overview scraping for {site} complete. {len(new_books)} new books.")
            
        except Exception as e:
            logger.error(f"Error during overview scraping for {site}: {e}")
        
        return new_books
    
    def detail_web_scraping(self, book_id: str) -> Optional[Book]:
        """
        Scrape detailed information from a book's detail page
        
        Args:
            book_id: The Bookwalker book ID
        
        Returns:
            Book object with detailed information
        """
        logger.info(f"Starting detail scraping for book: {book_id}")
        
        try:
            book = self.db.get_book(book_id)
            if not book:
                logger.warning(f"Book {book_id} not found in database")
                return None
            
            # Construct detail page URL
            url = f"{BOOKWALKER_BASE_URL}/product/{book_id}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse detailed information
            self._parse_detail_page(soup, book)
            
            # Mark as complete
            self.db.mark_details_complete(book_id)
            logger.info(f"Detail scraping complete for: {book.name}")
            
            return book
            
        except Exception as e:
            logger.error(f"Error during detail scraping for {book_id}: {e}")
            return None
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _build_overview_url(self, site: str) -> str:
        """Build URL for overview page based on site type"""
        site_urls = {
            'campaigns': f"{BOOKWALKER_BASE_URL}/campaign/",
            'sales': f"{BOOKWALKER_BASE_URL}/search/?category=&sub_category=&age=&order=&search=&series=&tag=",
            'coin_up': f"{BOOKWALKER_BASE_URL}/campaign/coin_up/",
            'new_releases': f"{BOOKWALKER_BASE_URL}/search/?order=release_date_desc&"
        }
        return site_urls.get(site, BOOKWALKER_BASE_URL)
    
    def _parse_overview_page(self, soup: BeautifulSoup, site: str) -> List[Book]:
        """
        Parse overview page and extract high-level book information.
        Prices and precise Coin Up values are deferred to the detail page.
        """
        books = []
        
        # Find all book containers
        book_items = soup.find_all('div', class_='m-book-item')
        logger.debug(f"Found {len(book_items)} book item containers on {site}")
        
        for item in book_items:
            try:
                book = Book()
                
                # 1. Title, UUID, and URL
                title_link = item.select_one('.m-book-item__title a')
                if title_link:
                    book.name = title_link.get_text(strip=True)
                    book.book_id = title_link.get('data-uuid')
                    book.book_url = title_link.get('href')

                # If there's no UUID, we can't track it. Skip.
                if not book.book_id:
                    continue

                # 2. Author
                author_tag = item.find('p', class_='m-book-item__author')
                if author_tag:
                    # 1. Get text, replacing <br> with spaces
                    raw_author = author_tag.get_text(separator=' ', strip=True)
                    
                    # 2. Strip ALL known prefixes using Regex (e.g., "著者: ", "監修: ")
                    clean_author = re.sub(r'^(著|著者|監修|原作|作画|イラスト|キャラクター原案|原案)[\s:]*', '', raw_author)
                    
                    # 3. Collapse multiple spaces into a single space (Fixes the "    他" issue)
                    book.author = re.sub(r'\s+', ' ', clean_author).strip()
                # 3. Label / Publisher
                label_tag = item.find('p', class_='m-book-item__label')
                
                if label_tag:
                    label_text = label_tag.get_text(strip=True)
                    book.label = None if label_text == '――' else label_text

                # 4. Category Mapping (Added 文芸 / Literature)
                tag_box = item.find('div', class_='m-book-item__tag-box')
                if tag_box:
                    category_span = tag_box.find('span')
                    if category_span:
                        cat_text = category_span.get_text(strip=True)
                        if 'マンガ' in cat_text or 'コミック' in cat_text:
                            book.category = BookCategory.MANGA
                        elif 'ラノベ' in cat_text:
                            book.category = BookCategory.LIGHT_NOVEL
                        elif '小説' in cat_text or '文芸' in cat_text:
                            book.category = BookCategory.NOVEL
                        else:
                            book.category = BookCategory.BOOK
                
                # Completed tag
                if item.find('span', class_='a-tag-comp'):
                    book.tags.append('Completed')
                
                # Preorder logic
                if item.find('span', class_='a-label-reserve') or item.find('a', class_='a-icon-btn--reserve'):
                    book.tags.append('Preorder')
                    schedule_tag = item.find('span', class_='m-book-item__schedule')
                    if schedule_tag:
                        book.tags.append(schedule_tag.get_text(strip=True))

                # Sale Period logic (e.g., ～6/4 (木)まで)
                period_tag = item.find('span', class_='m-book-item__period')
                if period_tag:
                    book.is_currently_on_sale = True
                    period_text = period_tag.get_text(strip=True)
                    book.tags.append(f"Sale: {period_text}")

                # 6. Mark that this needs detail scraping
                # (We rely on the detail scrape for exact price, coin up, ISBN, etc.)
                book.details_needed = True
                
                books.append(book)
                
            except Exception as e:
                logger.error(f"Error parsing an individual book item: {e}")
                continue
                
        return books
    
    def _parse_detail_page(self, soup: BeautifulSoup, book: Book):
        """
        Parse detail page and populate book object with information
        
        TODO: Implement actual parsing logic
        """
        try:
            # TODO: Extract all fields from detail page
            # - Title, author, publisher
            # - Price, coin back percentage
            # - ISBN, page count
            # - Release date, description
            # - Tags, series information
            # - Watch for popups that might interfere
            
            logger.debug("Detail page parsing (implementation needed)")
            
        except Exception as e:
            logger.error(f"Error parsing detail page: {e}")
    
    def _update_book_if_changed(self, existing: Book, new: Book):
        """Compare existing book with new data and update if different"""
        # TODO: Compare relevant fields and create price history entry if changed
        pass

# =============================================================================
# MAIN ORCHESTRATION
# =============================================================================

class BookwalkerScheduler:
    """Main scheduler for daily scraping tasks"""
    
    def __init__(self):
        self.db = BookDatabase()
        self.scraper = BookwalkerScraper(self.db)
    
    def run_daily_scrape(self):
        """
        Main loop: runs daily to scrape all sites and update details
        """
        logger.info("=" * 60)
        logger.info("Starting daily Bookwalker scrape")
        logger.info("=" * 60)
        
        # Phase 1: Overview scraping for all sites
        for site in SCRAPE_SITES:
            self.scraper.overview_web_scraping(site)
            time.sleep(random.uniform(1.5, 3.5)) # Sleeps for 1.5 to 3.5 seconds
        
        # Phase 2: Detail scraping for books that need it
        books_needing_details = self.db.get_books_needing_details()
            
        for book in books_needing_details:
            # 1. Update the next_review_date based on current tags
            book.next_review_date = calculate_next_review(book)
            
            # 2. Check if we actually need to scrape right now
            if book.next_review_date and book.next_review_date > datetime.now():
                logger.info(f"Skipping {book.name}: Review not needed until {book.next_review_date.strftime('%Y-%m-%d')}")
                continue
                    
            # 3. If we pass the check, perform the scrape
            self.scraper.detail_web_scraping(book.book_id)
                
            # 4. Optional: Clear the review date after a successful scrape
            # so it calculates the *new* end date from the fresh data
            book.next_review_date = None
            time.sleep(random.uniform(1.5, 3.5)) # Sleeps for 1.5 to 3.5 seconds
        
        logger.info("Daily scrape complete")
    
    def test_single_book(self, book_url: str):
        """
        Test scraping a single book for debugging
        Useful for goal #1: get data from currently on-sale book
        """
        logger.info(f"Testing scrape for: {book_url}")
        # TODO: Extract book_id from URL and scrape
        pass



# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def calculate_next_review(book: Book) -> Optional[datetime]:
    """
    Parses tags to find the end-date of a sale or a release date.
    Returns the date as a datetime object, or None if no date found.
    """
    current_year = datetime.now().year
        
    for tag in book.tags:
        # Regex looks for patterns like 6/4 or 5/28
        match = re.search(r'(\d+)/(\d+)', tag)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            
            # Create a prospective date
            target_date = datetime(current_year, month, day)
            
            # Safety: If the date is in the past (e.g., scraping in Jan, date is Dec), 
            # assume it's for the next year.
            if target_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                target_date = target_date.replace(year=current_year + 1)
                    
            return target_date
                
        return None
    
# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Create scheduler and run
    scheduler = BookwalkerScheduler()
    
    # Test run
    scheduler.run_daily_scrape()

