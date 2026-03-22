import sqlite3
import requests
from bs4 import BeautifulSoup
import logging
from typing import List, Dict
import time
import os

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def setup_db(db_name="avspare_parts.db"):
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
    url = f"https://avspare.com/search/?q={part_number}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }

    logging.info(f"Searching for part: {part_number} at {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        results = []
        items = soup.select('.list-group-item.list-group-item-action')

        for item in items:
            title_elem = item.find('a')
            if title_elem:
                title = title_elem.text.strip()
                link = title_elem.get('href', '')
                if link and not link.startswith('http'):
                    link = 'https://avspare.com' + link

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

        return results

    except requests.exceptions.HTTPError as e:
        if response.status_code == 503:
            logging.error(f"HTTP Error 503: Service Temporarily Unavailable for part {part_number}. (Anti-bot protection active)")
        else:
            logging.error(f"HTTP Error encountered: {e}")
        return []
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return []

def save_to_db(conn, parts_data: List[Dict[str, str]]) -> int:
    cursor = conn.cursor()
    count = 0
    for data in parts_data:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO parts (search_query, title, description, category, link, timestamp)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (data['search_query'], data['title'], data['description'], data['category'], data['link']))
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            logging.error(f"Database error inserting {data['search_query']}: {e}")
    conn.commit()
    return count

def load_parts_from_file(filename="part_numbers.txt"):
    """Loads part numbers from a text file, one per line."""
    if not os.path.exists(filename):
        logging.warning(f"File {filename} not found. Creating a sample one.")
        with open(filename, 'w') as f:
            f.write("1R-0716\nRE504836\n84298115\n3936316\n11110022\n")

    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    logging.info("Starting automated AVSpare part scraper...")
    conn = setup_db()

    # Load thousands of part numbers from a file (if you provide one)
    part_numbers_to_search = load_parts_from_file("part_numbers.txt")

    logging.info(f"Loaded {len(part_numbers_to_search)} part numbers to search.")

    total_saved = 0
    for idx, part in enumerate(part_numbers_to_search):
        logging.info(f"Progress: {idx + 1}/{len(part_numbers_to_search)}")
        parts_data = search_part(part)

        if parts_data:
            count = save_to_db(conn, parts_data)
            logging.info(f"Successfully saved {count} new items for part number '{part}'.")
            total_saved += count
            # Be polite, sleep longer to avoid rate limits when actually scraping
            time.sleep(3)
        else:
            # If we hit a 503, sleep even longer
            time.sleep(5)

    if total_saved == 0:
        logging.warning("No live data could be retrieved. The site might be blocking automated access (503).")
        logging.info("Run this script locally on your own machine to bypass server-level IP blocks!")

    conn.close()
    logging.info("Automated scraping complete. Data is stored in 'avspare_parts.db'.")

if __name__ == "__main__":
    main()
