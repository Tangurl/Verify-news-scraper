# ThaiPBS Verify News Scraper

An automated web scraper for fact-checking and verification articles from [Thai PBS Verify](https://www.thaipbs.or.th/verify/category/all) using Python and Playwright.

---

## 📌 Features

- **Automated Article Scraping**: Extracts article title, date & time, category, fact-check rating/validity status, and article URL.
- **Incremental & Duplicate-Safe**:
  - Automatically loads existing records from `scraped_news.csv`.
  - Halts early on page 1 if the latest article has already been collected.
  - Prevents redundant requests by stopping link collection as soon as an existing article is encountered.
- **Robust Metadata Extraction**:
  - Leverages structured data (`ClaimReview` JSON-LD schema) for high-accuracy validity ratings (`จริง`, `ข่าวปลอม`, `บิดเบือน`, etc.) with fallback DOM selectors.
  - Parses Buddhist Era (B.E.) Thai dates and formats into standard chronological ordering.
- **Sorted & Clean Output**: Deduplicates and saves articles in `scraped_news.csv`, sorted chronologically (oldest on top, newest at bottom).

---

## 📂 Data Output Schema

Data is saved to `scraped_news.csv` with the following columns:

| Column Header | Description | Example |
| :--- | :--- | :--- |
| **วันที่** | Publication date and time (Thai B.E.) | `3 มิ.ย. 69 13:30` |
| **ชื่อข่าว** | Article headline / title | `เตือนภัย มิจฉาชีพหลอกลงทุน...` |
| **หมวดข่าว** | News category | `สังคม`, `สาธารณสุข` |
| **ชนิดข่าว** | Fact-check verification verdict | `ข่าวปลอม`, `บิดเบือน`, `จริง` |
| **ลิงก์ข่าว** | Full article URL | `https://www.thaipbs.or.th/news/content/...` |

---

## 🛠️ Prerequisites & Installation

1. **Python 3.8+** installed.
2. Clone or navigate into this directory:
   ```bash
   cd /path/to/VerifyNewsScraper
   ```
3. Set up a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```
4. Install Playwright and required browser binaries:
   ```bash
   pip install playwright
   playwright install chromium
   ```

---

## 🚀 Usage

### 1. Default Run (Scrapes first 3 pages)
```bash
python scraper.py
```

### 2. Custom Page Limit
Specify the number of pages to traverse (e.g., 5 pages):
```bash
python scraper.py 5
```

### 3. Full Crawl (All available pages)
Crawl all pages until reaching the end of the catalog or encountering previously scraped articles:
```bash
python scraper.py --all
```

---

## 📁 Project Structure

```text
VerifyNewsScraper/
├── .gitignore          # Git ignore rules (ignores .ipynb, venv, caches, etc.)
├── scraper.py          # Main scraping script with Playwright
├── scraped_news.csv    # Output dataset (CSV format)
└── README.md           # Documentation
```
