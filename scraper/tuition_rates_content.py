import os
import requests
import logging
from bs4 import BeautifulSoup
import argparse
from configparser import ConfigParser
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import time

# Import the logging configuration function
from logging_config import configure_logging

# Configure logging
configure_logging(log_file="scraping.log", log_level=logging.INFO)

# Load configuration
config = ConfigParser()
config.read('config.ini')

# URL of the website to scrape
url = config.get('DEFAULT', 'URL', fallback="https://bursar.utdallas.edu/tuition/tuition-plans-rates/")

# Directory and file paths
output_dir = config.get('DEFAULT', 'OUTPUT_DIR', fallback="../scraped_data")
text_output_file = os.path.join(output_dir, "tuition_rates_content.txt")

# User-Agent header
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}


def setup_driver():
    """Set up and return a properly configured Chrome WebDriver."""
    options = Options()
    options.add_argument("--headless=new")  # New headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Determine the environment
    if os.getenv('GITHUB_ACTIONS'):
        # GitHub Actions environment - use WebDriver Manager
        service = Service(ChromeDriverManager().install())
    else:
        # Local development environment
        chrome_driver_path = "../chrome/chromedriver.exe"
        service = Service(executable_path=chrome_driver_path)

    return webdriver.Chrome(service=service, options=options)


def create_output_directory():
    """Create the output directory if it doesn't exist."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Created directory: {output_dir}")


def fetch_webpage(url):
    """Fetch the webpage content using Selenium."""
    logging.info(f"Fetching webpage using Selenium: {url}")

    driver = setup_driver()
    try:
        driver.get(url)
        # Use explicit wait instead of time.sleep()
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        page_source = driver.page_source
        return page_source
    except Exception as e:
        logging.error(f"Failed to fetch webpage using Selenium: {e}", exc_info=True)
        return None
    finally:
        driver.quit()


def extract_text_content(soup):
    """Extract text content only from elements with class 'card card-body', excluding tables."""
    logging.info("Extracting content from 'card card-body' elements (excluding tables).")
    card_contents = []

    # Find all divs with class 'card card-body'
    card_divs = soup.find_all('div', class_='card card-body')
    if not card_divs:
        logging.warning("No 'card card-body' elements found.")
        return card_contents

    for card in card_divs:
        # Remove all table elements from the card
        for table in card.find_all('table'):
            table.decompose()  # Remove the table from the card

        # Extract all text within the card (excluding tables)
        text = card.get_text(separator="\n", strip=True)
        card_contents.append(text)

    return card_contents


def save_text_content(text_content, file_path):
    """Save the extracted text content to a text file."""
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write("\n".join(text_content))
    logging.info(f"Text content saved to '{file_path}'.")


def main():
    """Main function to orchestrate the scraping process."""
    create_output_directory()

    # Fetch the webpage content
    webpage_content = fetch_webpage(url)
    if not webpage_content:
        return

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(webpage_content, 'html.parser')

    # Extract text content (headings, paragraphs, and lists)
    text_content = extract_text_content(soup)
    save_text_content(text_content, text_output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web Scraper for Tuition Plans and Rates")
    parser.add_argument('--url', type=str, default=url, help="URL of the website to scrape")
    args = parser.parse_args()

    url = args.url
    main()