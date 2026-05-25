# Bookwalker DB Development Guide

## Architecture Overview

The scraping system follows your described workflow:

```
Main Loop (Daily)
├── Phase 1: Overview Scraping (All Sites)
│   ├── Campaigns
│   ├── Sales
│   ├── Coin Up
│   └── New Releases
│
└── Phase 2: Detail Scraping (Books marked as `details_needed`)
    └── For each book → fetch detail page & populate all fields
```

## Key Components

### Data Models
- **Book**: Full book information with metadata
- **PriceEntry**: Price history + coin back tracking
- **Campaign**: Campaign/promotion information

### Main Classes
- **BookDatabase**: In-memory DB (replace with SQLAlchemy/PostgreSQL later)
- **BookwalkerScraper**: Core scraping logic
- **BookwalkerScheduler**: Orchestrates daily runs

## TODO: Next Steps

### 1. **Setup Parser & Test**
```bash
pip install -r requirements.txt
```

### 2. **Find Bookwalker HTML Selectors**
Use your HTML examples in `Html-Examples/` to determine CSS selectors for:
- Overview pages (Campaign1.htm, CoinUp1.htm)
- Product list item containers
- Price/coin-back information
- Book detail pages (need to get one example)

Key files to inspect:
- `Campaign1_files/` - Contains JS that renders the page
- Look for class names like `book-item`, `product`, `title`, `price`, etc.

### 3. **Implement `_parse_overview_page()`**
Find selectors for overview cards containing:
- Book title
- Author
- Prices (normal vs sale)
- Coin back %
- Book link/ID
- Category/tags

### 4. **Implement `_parse_detail_page()`**
Extract from detail page:
- Full description
- ISBN, page count
- Release date, announcement date
- Series info + volume number
- All price details

### 5. **Implement Database Layer**
Replace `BookDatabase` dict storage with actual DB:
```python
# Suggested: SQLAlchemy + SQLite (development) or PostgreSQL (production)
# This will provide:
# - Persistence across runs
# - Query capabilities
# - Price history tracking
# - Duplicate detection
```

### 6. **Add Scheduler Integration**
For daily automated runs:
- **Option A**: GitHub Actions (free, cloud-based)
- **Option B**: APScheduler (local)
- **Option C**: Docker + cron job

### 7. **Test Goal #1**
Find a book currently on sale and test:
```python
scheduler = BookwalkerScheduler()
scheduler.test_single_book("https://bookwalker.jp/de000000000001/")
# Should print all extracted data
```

## Database Schema (Future)

```sql
-- Books
id (UUID)
name, author, publisher
isbn, pages
category, series, volume
price (current normal)
coin_back (current)
is_currently_on_sale
created_at, updated_at

-- Price History
id
book_id (FK)
normal_price, sale_price, coin_back
sale_type (NORMAL, ON_SALE, COIN_UP, etc)
campaign_id (FK)
date

-- Campaigns  
id
name, description
start_date, end_date
campaign_type
```

## Error Handling Notes

- **Popups**: Some pages may have overlays - use Selenium if BeautifulSoup can't handle
- **Rate Limiting**: Add delays between requests
- **Stale Content**: Bookwalker may load content via JS - may need Selenium
- **CSRF Protection**: Check if cookies/tokens needed

## Current Limitations

✓ Models & structure ready  
✗ HTML selectors (need examples)  
✗ Database persistence  
✗ Scheduler (cron/GitHub Actions)  
✗ Error recovery  
✗ Duplicate detection logic

---

Next: Inspect your HTML examples to find CSS selectors!

function for going through campaigns -> overview scraping

implement going to next page on bigger campaign sites

since the sale period and coin up period are visible on the pages, maybe implement date for the next review, since these dont need to be reviewed multiple times during the period

2. Smart Scraping: The "Next Review Date"This is a brilliant optimization. Since the overview page tells us exactly when a sale ends (～6/4 (木)まで) or a preorder releases (5/28(木)配信予定), we don't need to detail-scrape these books every single day.How to implement it:Update your Model: Add self.next_review_date: Optional[datetime] = None to your Book class.Update your Database/Logic: In your daily scheduler, instead of scraping all books, you only scrape books where next_review_date is None OR next_review_date <= datetime.now().Parsing the Date: You will need a helper function to turn "5/28" into a Python datetime object.Note on years: Bookwalker doesn't show the year. You have to assume the current year, but if you scrape a book in December that says "1/5", your logic needs to safely assume it means next year.For now, storing the raw string in your tags list (as we are doing) is perfect. You can build the "Date String $\rightarrow$ Datetime Object" converter as a separate utility function later.

TODO Later:
User-Agent Rotation (Optional but Recommended)
You have a hardcoded User-Agent. If you plan to scrape daily, it helps to rotate this slightly so you don't look like a static bot. For now, the one you have is fine, but keep it in mind if you start getting HTTP 403 (Forbidden) errors.