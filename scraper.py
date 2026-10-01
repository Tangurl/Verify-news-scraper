import csv
import datetime
import os
import sys
from playwright.sync_api import sync_playwright

CSV_FILE = 'scraped_news.csv'
BASE_URL = 'https://www.thaipbs.or.th'
START_URL = f'{BASE_URL}/verify/category/all'

THAI_MONTHS = {
    'ม.ค.': 1, 'ก.พ.': 2, 'มี.ค.': 3, 'เม.ย.': 4,
    'พ.ค.': 5, 'มิ.ย.': 6, 'ก.ค.': 7, 'ส.ค.': 8,
    'ก.ย.': 9, 'ต.ค.': 10, 'พ.ย.': 11, 'ธ.ค.': 12
}

def parse_thai_date(date_str):
    """Parse a Thai date string (e.g. '3 มิ.ย. 69 13:30') into a sortable datetime object."""
    if not date_str:
        return datetime.datetime.min
    try:
        parts = date_str.strip().split()
        if len(parts) >= 4:
            day = int(parts[0])
            month_str = parts[1]
            month = THAI_MONTHS.get(month_str, 1)
            
            year_val = int(parts[2])
            if year_val < 100:
                # Buddhist Era 2569 is mapped correctly
                year = 2500 + year_val
            else:
                year = year_val
                
            time_parts = parts[3].split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            return datetime.datetime(year, month, day, hour, minute)
    except Exception:
        pass
    return datetime.datetime.min

def load_scraped_titles():
    """Load already scraped news titles from the CSV file."""
    scraped_titles = set()
    existing_rows = []
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        existing_rows.append(row)
                        scraped_titles.add(row[1]) # Title is in column 2 (index 1)
            print(f"Loaded {len(scraped_titles)} existing articles from {CSV_FILE}.")
        except Exception as e:
            print(f"Warning: Could not read {CSV_FILE}: {e}")
    return scraped_titles, existing_rows

def save_news_to_csv(new_rows, existing_rows):
    """Save new and existing rows to the CSV file, keeping oldest items at the top and newest at the bottom."""
    all_rows = new_rows + existing_rows
    
    # 1. Sort all rows by parsed date ascending (oldest on top, newest at bottom)
    all_rows.sort(key=lambda r: parse_thai_date(r[0]), reverse=False)
    
    # 2. Deduplicate rows by title, keeping the newest occurrence (the one closest to the end)
    seen_titles = set()
    deduped_rows = []
    for row in reversed(all_rows):
        if len(row) >= 2:
            title = row[1]
            if title not in seen_titles:
                seen_titles.add(title)
                deduped_rows.append(row)
        else:
            deduped_rows.append(row)
            
    # Reverse back to keep oldest at the top and newest at the bottom
    deduped_rows.reverse()
            
    try:
        with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['วันที่', 'ชื่อข่าว', 'หมวดข่าว', 'ชนิดข่าว', 'ลิงก์ข่าว'])
            writer.writerows(deduped_rows)
        print(f"Successfully saved {len(deduped_rows)} articles ({len(new_rows)} new) to {CSV_FILE}.")
    except Exception as e:
        print(f"Error: Could not write to {CSV_FILE}: {e}")

def scrape_detail_page(page, url):
    """Scrape details of a specific news article page."""
    print(f"Scraping detail page: {url}")
    try:
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_selector('h1.single-title', timeout=10000)
    except Exception as e:
        print(f"Failed to load article detail page {url}: {e}")
        return None

    # 1. News's title (h1.single-title)
    title = ""
    try:
        title = page.locator('h1.single-title').inner_text().strip()
    except Exception as e:
        print(f"Failed to extract title from {url}: {e}")
        return None

    # Try exact user selectors with very short timeout so they don't block
    user_date = ""
    user_time = ""
    user_category = ""
    user_validity = ""

    try:
        user_date = page.locator('div.text-tp-gray > span:nth-child(2) > span:nth-child(2) > time:nth-child(1)').inner_text(timeout=500).strip()
    except:
        pass

    try:
        user_time = page.locator('div.text-tp-gray > span:nth-child(2) > span:nth-child(2) > span:nth-child(3)').inner_text(timeout=500).strip()
    except:
        pass

    try:
        user_category = page.locator('div.text-tp-gray > span:nth-child(2) > span:nth-child(2) > a.text-primary:nth-child(5)').inner_text(timeout=500).strip()
    except:
        pass

    try:
        user_validity = page.locator('div.text-tp-gray > span.inline-flex:nth-child(1)').inner_text(timeout=500).strip()
    except:
        pass

    # Dynamic/JS robust extraction helper (runs instantly in page context)
    meta_info = page.evaluate("""() => {
        const div = document.querySelector('div.text-tp-gray');
        if (!div) return {};
        
        const timeEl = div.querySelector('time');
        let dateStr = '';
        if (timeEl) {
            dateStr = timeEl.textContent.trim();
        }
        
        let timeStr = '';
        const timeContainer = timeEl ? timeEl.parentElement : null;
        if (timeContainer) {
            const spans = timeContainer.querySelectorAll('span');
            for (const s of spans) {
                const txt = s.textContent.trim();
                if (/^\\d{2}:\\d{2}$/.test(txt)) {
                    timeStr = txt;
                    break;
                }
            }
        }
        
        const catEl = div.querySelector('a.text-primary') || div.querySelector('a[href*="/category/"]');
        let category = '';
        if (catEl) {
            category = catEl.textContent.trim();
        }
        
        let validity = '';
        // Extract validity from ClaimReview JSON-LD (most reliable)
        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (const script of scripts) {
            try {
                const data = JSON.parse(script.textContent);
                const items = data['@graph'] || (Array.isArray(data) ? data : [data]);
                for (const item of items) {
                    if (item['@type'] === 'ClaimReview') {
                        if (item.reviewRating && item.reviewRating.alternateName) {
                            validity = item.reviewRating.alternateName;
                            break;
                        }
                    }
                }
            } catch (e) {}
            if (validity) break;
        }
        
        // Fallback: Check if the first child of metadata div is a validity stamp badge
        if (!validity && div.firstElementChild) {
            const first = div.firstElementChild;
            if (first.tagName.toLowerCase() === 'span' && 
                (first.classList.contains('rounded-full') || first.textContent.match(/(จริง|ปลอม|บิดเบือน)/))) {
                validity = first.textContent.trim();
            }
        }
        
        return { date: dateStr, time: timeStr, category: category, validity: validity };
    }""")

    # Combine selectors with fallbacks
    date_val = user_date or meta_info.get('date', '')
    time_val = user_time or meta_info.get('time', '')
    category_val = user_category or meta_info.get('category', '')
    
    # Prioritize JSON-LD validity over user selector to prevent selector collision with date metadata
    validity_val = meta_info.get('validity', '')
    if not validity_val or "\n" in validity_val:
        validity_val = user_validity

    # Sanitize and validate validity text (reject if it contains date/time/separator details)
    if validity_val:
        validity_val = validity_val.strip()
        if "\n" in validity_val or "|" in validity_val or any(c.isdigit() for c in validity_val):
            validity_val = ""

    # Print warnings for any missing fields
    if not date_val:
        print(f"Warning: Date missing for {url}")
    if not time_val:
        print(f"Warning: Time missing for {url}")
    if not category_val:
        print(f"Warning: Category missing for {url}")
    if not validity_val:
        print(f"Warning: Validity missing for {url}")

    date_time_combined = f"{date_val} {time_val}".strip()

    return [date_time_combined, title, category_val, validity_val, url]

def run(max_pages=3):
    scraped_titles, existing_rows = load_scraped_titles()
    
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        page = context.new_page()
        
        page_num = 1
        stop_scraping = False
        collected_links_and_titles = []
        
        while not stop_scraping:
            url = f"{START_URL}?page={page_num}"
            print(f"Navigating to {url}...")
            
            try:
                page.goto(url, wait_until='domcontentloaded')
                # Wait for either cards/list to load OR "no data" element (.text-lg)
                page.wait_for_selector('div.-card, div.-list, .text-lg', timeout=15000)
            except Exception as e:
                print(f"Failed to load or find content on page {page_num}: {e}")
                break
                
            # Check if "ไม่พบข้อมูล" is present in .text-lg element
            no_data_found = False
            no_data_els = page.locator('.text-lg')
            for i in range(no_data_els.count()):
                txt = no_data_els.nth(i).inner_text()
                if "ไม่พบข้อมูล" in txt:
                    no_data_found = True
                    break
                    
            if no_data_found:
                print("Reached the end: found 'ไม่พบข้อมูล' at .text-lg.")
                break
                
            # 1. Perform Check on the first news title of page 1
            if page_num == 1:
                first_card_title = ""
                first_card_selectors = [
                    'div.-card:nth-child(1) > div:nth-child(1) > div:nth-child(2) > h3:nth-child(1) > a:nth-child(1)',
                    'div.-card h3 a',
                    'div.-list h3 a'
                ]
                for sel in first_card_selectors:
                    try:
                        first_card_locator = page.locator(sel).first
                        if first_card_locator.count() > 0:
                            first_card_title = first_card_locator.inner_text().strip()
                            if first_card_title:
                                break
                    except Exception as e:
                        pass
                        
                if not first_card_title:
                    print("Error: Could not retrieve the first card's title.")
                    browser.close()
                    return
                    
                print(f"First card title on site: '{first_card_title}'")
                if first_card_title in scraped_titles:
                    print("The latest news has already been scraped. Stopping scraper.")
                    # Still run save/sort to ensure existing data order is clean
                    save_news_to_csv([], existing_rows)
                    browser.close()
                    return
            
            # 2. Extract news cards and news lists from the current page
            cards = page.locator('div.-card, div.-list')
            card_count = cards.count()
            print(f"Found {card_count} items (cards + list items) on page {page_num}.")
            
            if card_count == 0:
                print("No content found on this page. Stopping.")
                break
                
            for i in range(card_count):
                card = cards.nth(i)
                link_el = card.locator('h3 a')
                if link_el.count() == 0:
                    continue
                    
                title = link_el.inner_text().strip()
                href = link_el.get_attribute('href')
                if not href:
                    continue
                    
                # Standardize link to absolute URL
                full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                
                # Check duplicate
                if title in scraped_titles:
                    print(f"Reached already scraped article: '{title}'. Stopping link collection.")
                    stop_scraping = True
                    break
                    
                collected_links_and_titles.append((full_url, title))
                
            if stop_scraping:
                break
                
            if max_pages is not None and page_num >= max_pages:
                print(f"Reached max pages limit ({max_pages}). Stopping page traversal.")
                break
                
            page_num += 1
            
        print(f"Collected {len(collected_links_and_titles)} new article links to scrape details for.")
        
        # 3. Visit each detail page and extract information
        new_rows = []
        for url, title in collected_links_and_titles:
            row = scrape_detail_page(page, url)
            if row:
                new_rows.append(row)
                
        # 4. Save results to CSV (always sort and deduplicate)
        save_news_to_csv(new_rows, existing_rows)
            
        browser.close()

if __name__ == '__main__':
    max_pages = 3
    if '--all' in sys.argv:
        max_pages = None
    elif len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.isdigit():
                max_pages = int(arg)
                break
                
    print(f"Starting scraper (max_pages={max_pages})...")
    if max_pages is not None:
        print("Note: Scraping is limited to 3 pages for testing. Run with '--all' to scrape all pages.")
    run(max_pages=max_pages)
