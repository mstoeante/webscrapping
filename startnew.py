from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.265 Safari/537.36"
)

print("Installing/checking ChromeDriver...", flush=True)
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
driver.set_page_load_timeout(15)
print("Chrome started.", flush=True)


def safe_get(url):
    try:
        driver.get(url)
        return True
    except (TimeoutException, WebDriverException) as error:
        print(f"Skipping unreachable page {url}: {error.__class__.__name__}", flush=True)
        return False

url = "https://umsu.unimelb.edu.au/buddy-up/clubs/clubs-listing/"
print(f"Loading club listing: {url}", flush=True)
if not safe_get(url):
    driver.quit()
    raise SystemExit("Could not load the club listing page.")

try:
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CLASS_NAME, "msl_organisation_list"))
    )
except TimeoutException:
    driver.quit()
    raise SystemExit("The club listing did not load within 30 seconds.")

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

results = []


def is_social_url(url):
    social_domains = (
        "facebook.com", "instagram.com", "twitter.com", "x.com",
        "youtube.com", "tiktok.com", "linkedin.com"
    )
    return any(domain in urlparse(url).netloc.lower() for domain in social_domains)



def find_official_website(soup):
        msl_link = soup.select_one('a.msl_web')
        if msl_link:
            href = (msl_link.get('href') or '').strip()
            if href:
                return href
        
        for link in soup.select('a[href]'):
            href = link.get('href', '').strip()
            if href.startswith(('http://', 'https://')) and not is_social_url(href):
                domain = urlparse(href).netloc.lower()
                if 'umsu.unimelb.edu.au' not in domain and domain != '':
                    return href
        return None


# ... (imports and setup)

def find_sponsor_page(driver, website_url):
    """Navigates to the external website and looks for a 'Sponsors' page."""
    if not safe_get(website_url):
        return None

    soup = BeautifulSoup(driver.page_source, "html.parser")
    home_domain = urlparse(driver.current_url).netloc.lower()
    candidates = []

    for link in soup.select('a[href]'):
        href = urljoin(driver.current_url, link.get('href', '').strip())
        text = link.get_text(' ', strip=True).lower()
        parsed_url = urlparse(href)
        searchable = f"{text} {parsed_url.path.lower()}"

        # Only look for pages on the same external domain
        if parsed_url.netloc.lower() != home_domain or is_social_url(href):
            continue

        score = sum(keyword in searchable for keyword in (
            'sponsor', 'partner', 'supporter', 'our friends', 'commercial'
        ))
        if score:
            candidates.append((score, href))

    # Return the link with the highest score
    return max(candidates, default=(0, None))[1]

def extract_sponsors(soup):
    """Extracts text or image alts that likely represent sponsors."""
    labels = []
    
    # 1. Look for specific sponsor classes/IDs (works on many external sites)
    for element in soup.select('[class*="sponsor"], [id*="sponsor"], [class*="partner"]'):
        text = element.get_text(' ', strip=True)
        if text and len(text) < 100: # Avoid grabbing huge paragraphs
            labels.append(text)

    # 2. Look for images with alt text in the description or main content
    # UMSU profile specific
    desc = soup.select_one('.msl_organisation_description')
    target = desc if desc else soup.body
    
    if target:
        for image in target.select('img[alt]'):
            label = image.get('alt').strip()
            if label and not any(x in label.lower() for x in ('logo', 'image', 'banner', 'club')):
                labels.append(label)

    return list(dict.fromkeys(labels))

# ... (rest of the loop)

for club in club_data:
    profile_url = club['url'].replace('/join/', '/club/')
    print(f"Checking {club['name']} at {profile_url}...", flush=True)
    
    if not safe_get(profile_url):
        continue

    sub_soup = BeautifulSoup(driver.page_source, "html.parser")
    website_url = find_official_website(sub_soup)
    sponsor_page = None
    sponsors = []

    if website_url:
        sponsor_page = find_sponsor_page(driver, website_url)
        if sponsor_page:
            if safe_get(sponsor_page):
                sponsors = extract_sponsors(
                    BeautifulSoup(driver.page_source, "html.parser")
                )

    results.append({
        "name": club['name'],
        "url": club['url'],
        "website_url": website_url,
        "sponsor_page": sponsor_page,
        "sponsors": sponsors,
    })

for item in results:
    print(f"Club Name: {item['name']}", flush=True)
    print(f"URL: {item['url']}", flush=True)
    print(f"Website: {item['website_url'] or 'None found'}", flush=True)
    print(f"Sponsor Page: {item['sponsor_page'] or 'None found'}", flush=True)
    print(f"Sponsors: {', '.join(item['sponsors']) if item['sponsors'] else 'None found'}", flush=True)
    print("-" * 30, flush=True)
