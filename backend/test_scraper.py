"""
Test runner for Bookwalker Scraper
"""
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Import your existing system components
# (Assumes your main file is named bookwalker_scraper.py)
from bookwalker_scraper import BookDatabase, BookwalkerScraper

def run_isolated_campaign_test(target_url: str, log_filename: str = "test_output.md"):
    """
    Fetches a specific target URL, processes it through the overview parser,
    and logs human-readable output to a separate Markdown file.
    """
    print(f"[*] Initializing test context...")
    db = BookDatabase()
    scraper = BookwalkerScraper(db)
    
    print(f"[*] Dispatching GET request to: {target_url}")
    try:
        response = scraper.session.get(target_url, timeout=12)
        response.raise_for_status()
    except Exception as e:
        print(f"[!] Network fetch failed: {e}")
        return

    print("[*] Page downloaded successfully. Injecting DOM into parser...")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # We pass the soup directly to bypass your default automated URL generation
    parsed_books = scraper._parse_overview_page(soup, site="isolated_test_run")
    
    print(f"[*] Parsing complete. Found {len(parsed_books)} valid book assets.")
    print(f"[*] Structuring output reports inside '{log_filename}'...")
    
    # Write to a cleanly formatted Markdown file (uses UTF-8 for Japanese text)
    with open(log_filename, "w", encoding="utf-8") as f:
        f.write("# Bookwalker Scraper Test Run Report\n")
        f.write(f"- **Execution Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Target Live URL:** [{target_url}]({target_url})\n")
        f.write(f"- **Total Extractions:** {len(parsed_books)} items matched\n")
        f.write("\n---\n\n")
        
        if not parsed_books:
            f.write("### ⚠️ No books detected.\n")
            f.write("The selector schemas might be failing or the layout differs.\n")
        else:
            for idx, book in enumerate(parsed_books, 1):
                f.write(f"### {idx}. {book.name or '⚠️ MISSING TITLE'}\n")
                f.write(f"- **UUID:** `{book.book_id}`\n")
                f.write(f"- **Product URL:** {book.book_url}\n")
                f.write(f"- **Author Line:** {book.author or '*None or Parsing Fail*'}\n")
                f.write(f"- **Label/Publisher:** {book.label or '*None*'}\n")
                f.write(f"- **Category Assigned:** `{book.category}`\n")
                f.write(f"- **Flagged On Sale:** `{book.is_currently_on_sale}`\n")
                f.write(f"- **Captured Temporary Tags:** {book.tags}\n")
                f.write("\n")
                
    print("[+] Evaluation complete! Open the generated file to review layout matches.")

if __name__ == "__main__":
    # Example live Bookwalker campaign page link to test your selectors on
    TEST_CAMPAIGN_LINK = "https://bookwalker.jp/campaign/47702/" 
    
    run_isolated_campaign_test(TEST_CAMPAIGN_LINK)