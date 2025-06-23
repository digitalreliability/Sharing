import os
import sys
import subprocess
import time
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import wikipediaapi
import requests
import re
from datetime import datetime

# ===== AUTO-INSTALL DEPENDENCIES =====
def install_dependencies():
    required = {
        'pandas': 'pandas',
        'tqdm': 'tqdm',
        'wikipedia-api': 'wikipediaapi',
        'requests': 'requests',
        'beautifulsoup4': 'bs4'
    }
    
    missing = []
    for package, import_name in required.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("Installation complete. Please restart the script.")
        sys.exit(0)

install_dependencies()

# Now safely import BeautifulSoup
from bs4 import BeautifulSoup

# ===== CONFIG =====
INPUT_CSV = "birth_details.csv"
OUTPUT_CSV = "detailed_life_events.csv"
WORKERS = 3  # Reduced for stability
REQUEST_DELAY = 1.5  # More conservative delay
USER_AGENT = "LifeEventsResearch/1.0 (contact@example.com)"

# ===== WIKIPEDIA SCRAPER =====
class WikipediaScraper:
    def __init__(self):
        self.wiki = wikipediaapi.Wikipedia(
            language='en',
            user_agent=USER_AGENT,
            timeout=20
        )
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return ""
        text = re.sub(r'\[\d+\]', '', text)  # Remove citations [1]
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:2000]  # Limit to 2000 characters

    def extract_events(self, soup):
        """Extract life events from page sections"""
        events = []
        sections = {
            'Early Life': ['early life', 'childhood', 'education'],
            'Career': ['career', 'professional', 'work'],
            'Achievements': ['achievements', 'awards', 'honors'],
            'Personal Life': ['personal life', 'relationships', 'family'],
            'Later Years': ['later years', 'retirement', 'death']
        }

        for section_name, keywords in sections.items():
            content = []
            # Find section by heading
            for keyword in keywords:
                heading = soup.find(lambda tag: tag.name in ['h2', 'h3'] and 
                                            keyword in tag.get_text().lower())
                if heading:
                    # Extract content until next section
                    for elem in heading.find_next_siblings():
                        if elem.name in ['h2', 'h3']:
                            break
                        if elem.name == 'p':
                            text = self.clean_text(elem.get_text())
                            if text:
                                content.append(text)
                    
                    if content:
                        events.append({
                            'type': section_name,
                            'content': '\n'.join(content)[:3000]  # Limit length
                        })
                    break
        return events

    def get_person_data(self, name):
        """Get comprehensive data for a person"""
        time.sleep(REQUEST_DELAY)
        try:
            # Get Wikipedia page
            page = self.wiki.page(name.replace(' ', '_'))
            if not page.exists():
                return {'error': 'Page not found'}

            # Get HTML for detailed scraping
            url = f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}"
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract infobox data
            infobox = {}
            infobox_table = soup.find('table', {'class': 'infobox'})
            if infobox_table:
                for row in infobox_table.find_all('tr'):
                    if row.th and row.td:
                        key = self.clean_text(row.th.get_text())
                        value = self.clean_text(row.td.get_text())
                        if key and value:
                            infobox[key] = value

            # Extract life events
            events = self.extract_events(soup)

            return {
                'summary': page.summary[:3000],
                'infobox': infobox,
                'events': events,
                'url': url
            }

        except Exception as e:
            return {'error': str(e)}

# ===== MAIN PROCESSING =====
def process_person(person):
    """Process a single person's record"""
    scraper = WikipediaScraper()
    data = scraper.get_person_data(person['Name'])
    
    result = {
        'Name': person.get('Name', ''),
        'Gender': person.get('Gender', ''),
        'Birth_Date': f"{person.get('Day', '')}/{person.get('Month', '')}/{person.get('Year', '')}",
        'Birth_Time': person.get('Time', ''),
        'Birth_Location': person.get('Location', ''),
        'Latitude': person.get('Latitude', ''),
        'Longitude': person.get('Longitude', ''),
        'Time_Zone': person.get('Time Zone', ''),
        'Wikipedia_URL': data.get('url', ''),
        'Summary': data.get('summary', ''),
        'Error': data.get('error', '')
    }

    # Add infobox data
    for key, value in data.get('infobox', {}).items():
        result[f"Infobox_{key}"] = value

    # Add events (will be expanded later)
    result['Events'] = data.get('events', [])

    return result

def main():
    # Load data
    try:
        df = pd.read_csv(INPUT_CSV)
        records = df.to_dict('records')
        total = len(records)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return

    print(f"Processing {total} people with detailed Wikipedia extraction...")

    # Process with progress tracking
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(process_person, record) for record in records]
        
        for future in tqdm(as_completed(futures), total=total, desc="Processing"):
            try:
                results.append(future.result())
                # Save progress every 25 records
                if len(results) % 25 == 0:
                    # First save compact version
                    pd.DataFrame(results).to_csv(OUTPUT_CSV, index=False)
            except Exception as e:
                print(f"\nError: {str(e)[:100]}")

    # Expand events into separate rows
    expanded_data = []
    for person in results:
        base_info = {k:v for k,v in person.items() if k != 'Events'}
        if person.get('Events'):
            for event in person['Events']:
                expanded = base_info.copy()
                expanded.update({
                    'Event_Type': event['type'],
                    'Event_Details': event['content']
                })
                expanded_data.append(expanded)
        else:
            expanded_data.append(base_info)

    # Final save
    pd.DataFrame(expanded_data).to_csv(OUTPUT_CSV, index=False)
    print(f"\nCompleted! Results saved to {OUTPUT_CSV}")
    print(f"Total records processed: {len(expanded_data)}")

if __name__ == "__main__":
    print("Starting processing...")
    print("This will take several hours for large datasets")
    print("Progress will be saved periodically")
    main()
