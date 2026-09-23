from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

chrome_options = Options()
chrome_options.add_argument("--headless")  
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.265 Safari/537.36"
)

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

url = "https://umsu.unimelb.edu.au/buddy-up/clubs/clubs-listing/"
driver.get(url)

WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CLASS_NAME, "msl_organisation_list"))
    )


html = driver.page_source
soup = BeautifulSoup(html, "html.parser")
clubs = soup.select('li.show-item')

base_url = "https://umsu.unimelb.edu.au"
club_data = []

for club in clubs:
    name_link = club.select_one('a.msl-gl-link')
    if name_link:
        name = name_link.get_text(strip=True)
        href = name_link.get('href', '')
        full_url = base_url + href if href.startswith('/') else href
        club_data.append({"name": name, "url": full_url})

print(f"Found {len(club_data)} clubs. Starting deep scrape...\n")

def scrape_finance_club(club):
    try:
        request = Request(
            club['url'],
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.6778.265 Safari/537.36"
            },
        )

        with urlopen(request, timeout=30) as response:
            sub_soup = BeautifulSoup(response.read(), "html.parser")

        external_links = []
        social_area = sub_soup.select('a.msl_web, a.msl_facebook, a.msl_instagram, a.msl_twitter')
        for link in social_area:
            external_links.append(link.get('href'))

        all_links = sub_soup.select('.msl-content a[href^="http"], .msl_organisation a[href^="http"]')
        for link in all_links:
            href = link.get('href')
            if "umsu.unimelb.edu.au" not in href:
                external_links.append(href)

        return club, list(set(external_links)), None
    except Exception as error:
        return club, [], str(error)

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(scrape_finance_club, club) for club in club_data]
    for future in as_completed(futures):
        club, external_links, error = future.result()
        print(f"Club Name: {club['name']}", flush=True)
        print(f"URL: {club['url']}", flush=True)
        if error:
            print(f"Error: {error}", flush=True)
        else:
            print(f"External Links: {', '.join(external_links) if external_links else 'None found'}", flush=True)
        print("-" * 30, flush=True)

driver.quit()

