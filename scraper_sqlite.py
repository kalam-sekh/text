import sqlite3
import requests
from bs4 import BeautifulSoup
import argparse
import logging
from typing import List, Dict

# Set up simple logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def setup_db(db_name="avspare_parts.db"):
    """
    Sets up the SQLite database and creates the `parts` table if it doesn't exist.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_query TEXT,
            title TEXT,
            description TEXT,
            category TEXT,
            link TEXT UNIQUE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def search_part(part_number: str) -> List[Dict[str, str]]:
    """
    Searches AVSpare for the given part number and extracts the results.
    """
    url = f"https://avspare.com/search/?q={part_number}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    logging.info(f"Searching for part: {part_number} at {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        results = []
        # Attempt to parse standard list items on the search page
        items = soup.select('.list-group-item.list-group-item-action')

        for item in items:
            title_elem = item.find('a')
            if title_elem:
                title = title_elem.text.strip()
                link = title_elem.get('href', '')
                if link and not link.startswith('http'):
                    link = 'https://avspare.com' + link

                # Try to find a description and category if possible from the layout
                # Often it's structured within spans or small tags inside the list item
                description = item.text.strip().replace('\n', ' ')
                category = 'Unknown'
                category_elem = item.find('small')
                if category_elem:
                    category = category_elem.text.strip()

                results.append({
                    'search_query': part_number,
                    'title': title,
                    'description': description,
                    'category': category,
                    'link': link
                })

        if not results:
            logging.warning("No standard list items found. The layout may have changed, or there are no results for this part number.")

        return results

    except requests.exceptions.HTTPError as e:
        if response.status_code == 503:
            logging.error("HTTP Error 503: Service Temporarily Unavailable. AVSpare might be blocking requests from this IP or automated agents.")
        else:
            logging.error(f"HTTP Error encountered: {e}")
        return []
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return []

def save_to_db(conn, parts_data: List[Dict[str, str]]) -> int:
    """
    Saves the extracted parts data to the SQLite database.
    """
    cursor = conn.cursor()
    count = 0
    for data in parts_data:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO parts (search_query, title, description, category, link, timestamp)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (data['search_query'], data['title'], data['description'], data['category'], data['link']))
            count += 1
        except Exception as e:
            logging.error(f"Database error inserting {data['search_query']}: {e}")
    conn.commit()
    return count

def main():
    parser = argparse.ArgumentParser(description="AVSpare Part Data Scraper by Part Number")
    parser.add_argument("part_number", help="The part number to search for (e.g., '1234', '1R-0716')", type=str)
    args = parser.parse_args()

    conn = setup_db()

    parts_data = search_part(args.part_number)

    if parts_data:
        count = save_to_db(conn, parts_data)
        logging.info(f"Successfully saved/updated {count} items for part number '{args.part_number}' to the database.")
    else:
        logging.warning("No valid data was returned and saved to the database. This is likely due to anti-bot measures (like Cloudflare 503 errors) on AVSpare or an invalid part number.")

    conn.close()

if __name__ == "__main__":
    main()
