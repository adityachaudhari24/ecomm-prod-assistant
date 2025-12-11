import csv
import time
import re
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By 
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

def get_chrome_driver(options=None, max_retries=3):
    """Initialize Chrome driver with retry logic using webdriver-manager."""
    chrome_options = Options()
    
    # Add essential options for stability
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    for attempt in range(max_retries):
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Chrome driver initialization failed (attempt {attempt + 1}/{max_retries}): {e}")
                print("Retrying in 5 seconds...")
                time.sleep(5)
            else:
                raise Exception(f"Failed to initialize Chrome driver after {max_retries} attempts: {e}")

class FlipkartScraper:
    def __init__(self, output_dir="data"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def get_top_reviews(self,product_url,count=2):
        """Get the top reviews for a product.
        """
        driver = get_chrome_driver()

        if not product_url.startswith("http"):
            driver.quit()
            return "No reviews found"

        try:
            driver.get(product_url)
            time.sleep(4)
            try:
                driver.find_element(By.XPATH, "//button[contains(text(), '✕')]").click()
                time.sleep(1)
            except Exception as e:
                print(f"Error occurred while closing popup: {e}")

            for _ in range(4):
                ActionChains(driver).send_keys(Keys.END).perform()
                time.sleep(1.5)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            review_blocks = soup.select("div._27M-vq, div.col.EPCmJX, div._6K-7Co")
            seen = set()
            reviews = []

            for block in review_blocks:
                text = block.get_text(separator=" ", strip=True)
                if text and text not in seen:
                    reviews.append(text)
                    seen.add(text)
                if len(reviews) >= count:
                    break
        except Exception:
            reviews = []

        driver.quit()
        return " || ".join(reviews) if reviews else "No reviews found"
    
    def scrape_flipkart_products(self, query, max_products=1, review_count=2):
        """Scrape Flipkart products based on a search query.
        """
        driver = get_chrome_driver()
        search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        driver.get(search_url)
        time.sleep(4)

        try:
            driver.find_element(By.XPATH, "//button[contains(text(), '✕')]").click()
        except Exception as e:
            print(f"Error occurred while closing popup: {e}")

        time.sleep(2)
        products = []

        items = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")[:max_products]
        for item in items:
            try:
                # Updated selectors for current Flipkart layout
                # Try multiple selectors for title
                title = None
                for selector in ["div.RG5Slk", "div.KzDlHZ", "a.wjcEIp", "div._4rR01T"]:
                    try:
                        title = item.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if title:
                            break
                    except:
                        continue
                if not title:
                    print("Could not find title, skipping item")
                    continue

                # Try multiple selectors for price
                price = "N/A"
                for selector in ["div.Nx9bqj", "div._30jeq3", "div._1_WHN1"]:
                    try:
                        price = item.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if price:
                            break
                    except:
                        continue

                # Try multiple selectors for rating
                rating = "N/A"
                for selector in ["div.MKiFS6", "div.XQDdHH", "div._3LWZlK", "span.CjyrHS div"]:
                    try:
                        rating = item.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if rating:
                            break
                    except:
                        continue

                # Try multiple selectors for reviews count
                total_reviews = "N/A"
                for selector in ["span.Wphh3N", "span._2_R_DZ", "span.Qx6dsP"]:
                    try:
                        reviews_text = item.find_element(By.CSS_SELECTOR, selector).text.strip()
                        match = re.search(r"[\d,]+(?=\s+Reviews?)", reviews_text, re.IGNORECASE)
                        if match:
                            total_reviews = match.group(0)
                            break
                    except:
                        continue

                # Get product link
                link_el = item.find_element(By.CSS_SELECTOR, "a[href*='/p/']")
                href = link_el.get_attribute("href")
                product_link = href if href.startswith("http") else "https://www.flipkart.com" + href
                match = re.findall(r"/p/(itm[0-9A-Za-z]+)", href)
                product_id = match[0] if match else "N/A"
            except Exception as e:
                print(f"Error occurred while processing item: {e}")
                continue

            top_reviews = self.get_top_reviews(product_link, count=review_count) if "flipkart.com" in product_link else "Invalid product URL"
            products.append([product_id, title, rating, total_reviews, price, top_reviews])

        driver.quit()
        return products
    
    def save_to_csv(self, data, filename="product_reviews.csv"):
        """Save the scraped product reviews to a CSV file."""
        if os.path.isabs(filename):
            path = filename
        elif os.path.dirname(filename):  # filename includes subfolder like 'data/product_reviews.csv'
            path = filename
            os.makedirs(os.path.dirname(path), exist_ok=True)
        else:
            # plain filename like 'output.csv'
            path = os.path.join(self.output_dir, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["product_id", "product_title", "rating", "total_reviews", "price", "top_reviews"])
            writer.writerows(data)
