#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running automated web scraper..."
python3 automate_scraper.py

echo "Checking the resulting database structure and data..."
sqlite3 avspare_parts.db ".mode column" ".headers on" "SELECT * FROM parts;"
