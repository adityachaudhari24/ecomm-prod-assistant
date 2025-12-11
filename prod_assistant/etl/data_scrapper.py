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

    def get_top_reviews(self, product_url, count=2):
        """Get the top reviews for a product with updated selectors."""
        driver = get_chrome_driver()

        if not product_url.startswith("http"):
            driver.quit()
            return "No reviews found"

        try:
            driver.get(product_url)
            time.sleep(5)  # Increased initial wait for page load
            
            # Try to close popup if it appears
            try:
                driver.find_element(By.XPATH, "//button[contains(text(), '✕')]").click()
                time.sleep(1)
            except Exception:
                pass  # No popup or already closed

            # Scroll down to load reviews section - use JavaScript for more reliable scrolling
            for i in range(8):
                driver.execute_script(f"window.scrollTo(0, {(i+1) * 800});")
                time.sleep(1)
            
            # Scroll to bottom to ensure all dynamic content is loaded
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Scroll back up a bit to the reviews section
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            reviews = []
            seen = set()
            
            # Method 1: Look for review containers with the current Flipkart structure (2024-2025)
            # Reviews are typically in divs with specific class patterns
            review_container_selectors = [
                "div.ZmyHeo",      # Review text in some layouts
                "div.t-ZTKy",      # Review text container
                "div._11pzQk",     # Review content wrapper
                "div.qwjRop",      # Older review container
                "div._6K-7Co",     # Alternative container
                "div.cPHDOP",      # Another review text class
            ]
            
            for selector in review_container_selectors:
                if len(reviews) >= count:
                    break
                try:
                    elements = soup.select(selector)
                    for elem in elements:
                        text = elem.get_text(separator=" ", strip=True)
                        if text and len(text) > 50 and text not in seen:
                            # Filter out non-review content
                            if not any(skip in text.lower() for skip in ['add to cart', 'buy now', 'flipkart', 'seller', 'delivery']):
                                reviews.append(text[:500])  # Limit review length
                                seen.add(text)
                        if len(reviews) >= count:
                            break
                except Exception:
                    continue
            
            # Method 2: Look for reviews by finding rating stars followed by review text
            if len(reviews) < count:
                # Find all rating divs and get adjacent review text
                rating_divs = soup.find_all("div", class_=re.compile(r"XQDdHH|_3LWZlK|MKiFS6"))
                for rating_div in rating_divs:
                    if len(reviews) >= count:
                        break
                    # Look for review text in parent or sibling elements
                    parent = rating_div.find_parent("div", class_=re.compile(r"col|x_CUu6|EKxdNe"))
                    if parent:
                        # Find text content that looks like a review
                        for child in parent.find_all("div"):
                            text = child.get_text(separator=" ", strip=True)
                            if text and len(text) > 50 and text not in seen:
                                if not any(skip in text.lower() for skip in ['add to cart', 'buy now', 'flipkart', 'seller', 'delivery', 'helpful', 'report']):
                                    reviews.append(text[:500])
                                    seen.add(text)
                                    break
            
            # Method 3: Find reviews by looking for the "READ MORE" pattern (reviews often have this)
            if len(reviews) < count:
                # Look for parent containers of "Read more" links which often contain reviews
                read_more_elements = soup.find_all(string=re.compile(r"READ MORE|Read More|read more", re.IGNORECASE))
                for elem in read_more_elements:
                    if len(reviews) >= count:
                        break
                    parent = elem.find_parent("div")
                    if parent:
                        grandparent = parent.find_parent("div")
                        if grandparent:
                            text = grandparent.get_text(separator=" ", strip=True)
                            text = re.sub(r"READ MORE.*", "", text, flags=re.IGNORECASE).strip()
                            if text and len(text) > 50 and text not in seen:
                                reviews.append(text[:500])
                                seen.add(text)
            
            # Method 4: Generic approach - look for longer text blocks in review section
            if len(reviews) < count:
                # Find the ratings section first
                ratings_section = soup.find("div", string=re.compile(r"Ratings?\s*&?\s*Reviews?", re.IGNORECASE))
                if ratings_section:
                    # Get parent container and search for review text
                    section_parent = ratings_section.find_parent("div", class_=re.compile(r"col|MDzIYy"))
                    if section_parent:
                        all_divs = section_parent.find_all("div")
                        for div in all_divs:
                            if len(reviews) >= count:
                                break
                            text = div.get_text(separator=" ", strip=True)
                            # Look for text that appears to be a review (moderate length, not UI text)
                            if (text and 50 < len(text) < 1000 and text not in seen
                                and not any(skip in text.lower() for skip in 
                                    ['add to cart', 'buy now', 'flipkart', 'delivery by', 'rate product', 
                                     'ratings &', 'all reviews', 'helpful', 'report abuse'])):
                                reviews.append(text[:500])
                                seen.add(text)
            
            print(f"Total reviews found: {len(reviews)}")
            
        except Exception as e:
            print(f"Error occurred while scraping reviews: {e}")
            reviews = []
        finally:
            driver.quit()

        return " || ".join(reviews[:count]) if reviews else "No reviews found"
    
    def scrape_flipkart_products(self, query, max_products=1, review_count=2):
        """Scrape Flipkart products based on a search query."""
        driver = get_chrome_driver()
        search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        driver.get(search_url)
        time.sleep(4)

        try:
            driver.find_element(By.XPATH, "//button[contains(text(), '✕')]").click()
        except Exception:
            pass  # No popup

        time.sleep(2)
        products = []

        items = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")[:max_products]
        for item in items:
            try:
                # Updated selectors for title (try multiple)
                title = None
                for selector in ["div.RG5Slk", "div.KzDlHZ", "a.wjcEIp", "div._4rR01T", "div.s1Q9rs", "a.IRpwTa"]:
                    try:
                        title = item.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if title:
                            break
                    except:
                        continue
                
                if not title:
                    print("Could not find title, skipping item")
                    continue

                # Updated selectors for price
                price = "N/A"
                for selector in ["div.Nx9bqj", "div._30jeq3", "div._1_WHN1", "div.hl05eU", "div._2rQ-NK"]:
                    try:
                        price = item.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if price:
                            break
                    except:
                        continue

                # Updated selectors for rating
                rating = "N/A"
                for selector in ["div.XQDdHH", "div._3LWZlK", "span.Y1HWO0", "div.CjyrHS"]:
                    try:
                        rating = item.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if rating:
                            break
                    except:
                        continue

                # Updated selectors for reviews count
                total_reviews = "N/A"
                for selector in ["span.Wphh3N", "span._2_R_DZ", "span.Qx6dsP", "span._13vcmD"]:
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

            print(f"\nScraping reviews for: {title}")
            top_reviews = self.get_top_reviews(product_link, count=review_count) if "flipkart.com" in product_link else "Invalid product URL"
            products.append([product_id, title, rating, total_reviews, price, top_reviews])

        driver.quit()
        return products
    
    def save_to_csv(self, data, filename="product_reviews.csv"):
        """Save the scraped product reviews to a CSV file."""
        if os.path.isabs(filename):
            path = filename
        elif os.path.dirname(filename):
            path = filename
            os.makedirs(os.path.dirname(path), exist_ok=True)
        else:
            path = os.path.join(self.output_dir, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["product_id", "product_title", "rating", "total_reviews", "price", "top_reviews"])
            writer.writerows(data)
        
        print(f"\nData saved to: {path}")


# Example usage
if __name__ == "__main__":
    scraper = FlipkartScraper()
    
    # Scrape products
    query = "laptop"
    print(f"Searching for: {query}")
    products = scraper.scrape_flipkart_products(query, max_products=2, review_count=3)
    
    # Save to CSV
    if products:
        scraper.save_to_csv(products, "flipkart_products.csv")
        print(f"\nScraped {len(products)} products successfully!")
    else:
        print("No products found!")