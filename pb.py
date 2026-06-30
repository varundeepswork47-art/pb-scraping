import streamlit as st
import pandas as pd
import time
import re

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== STREAMLIT UI SETUP =====
st.title("🚗 Cloud Insurance Web Scraper")
st.write("Upload your URL file below. Processing happens entirely on the cloud server.")

# File uploader for users
uploaded_excel = st.sidebar.file_uploader("Upload Input Excel File (with 'url' column)", type=["xlsx", "csv"])

# ===== CLEANING FUNCTIONS =====
def clean_price(text):
    try:
        text = text.replace(",", "")
        return re.findall(r"\d+", text)[0]
    except:
        return "NA"

def extract_km_from_text(text):
    try:
        km_match = re.search(r'(\d+(?:,\d+)?)\s*km', text, re.IGNORECASE)
        if km_match:
            return km_match.group(1).replace(",", "")
    except:
        pass
    return "NA"

# ===== CLOUD-OPTIMIZED SCRAPING ENGINE =====
def run_cloud_scraper(urls, status_container):
    options = webdriver.ChromeOptions()
    
    # Force the browser to use the exact location where Docker installs Chrome
    options.binary_location = "/usr/bin/google-chrome"
    
    # Critical flags to execute Chrome seamlessly inside Linux server containers
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Premium stealth configuration strings to reduce anti-bot triggering
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    status_container.info("🤖 Initializing stable container-bound Chrome driver...")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Strip automated identification property tags
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
    except Exception as e:
        status_container.error(f"Failed to start Chrome Driver: {e}")
        return []

    wait = WebDriverWait(driver, 30)
    all_scraped_data = []

    def ensure_filter_checked(filter_name):
        try:
            label = wait.until(EC.presence_of_element_located((By.XPATH, f"//label[contains(.//p, '{filter_name}')]")))
            checkbox = label.find_element(By.XPATH, ".//input[@type='checkbox']")
            if not checkbox.get_attribute("checked"):
                driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(2)
        except Exception as e:
            status_container.warning(f"Error filtering {filter_name}: {e}")

    def extract_description(card):
        try:
            info_box = card.find_element(By.XPATH, ".//div[contains(@class,'specialPlans infoMsg')]")
            desc_parts = []
            try:
                main_desc = info_box.find_element(By.XPATH, ".//span[contains(@class,'fontMedium')]").text.strip()
                desc_parts.append(main_desc)
            except: pass
            try:
                km_info = info_box.find_element(By.XPATH, ".//b").text.strip()
                if km_info and (not desc_parts or km_info not in desc_parts[0]):
                    desc_parts.append(km_info)
            except: pass
            return " ".join(desc_parts) if desc_parts else "NA"
        except:
            return "NA"

    def scrape_premium_breakdown(card):
        try:
            card.find_element(By.XPATH, ".//p[text()='View Coverage']").click()
            time.sleep(2)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(),'Premium Breakup')]"))).click()
            time.sleep(3)
            popup = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.breakupList")))

            third_party, own_damage, zero_dep = "NA", "NA", "NA"
            rows = popup.find_elements(By.CSS_SELECTOR, "div.row")
            for row in rows:
                try:
                    label = row.find_element(By.XPATH, ".//div[contains(@class,'col-8')]").text.lower()
                    value = clean_price(row.find_element(By.XPATH, ".//div[contains(@class,'col-4')]").text)
                    if "third party" in label: third_party = value
                    elif "own damage" in label: own_damage = value
                    elif "zero depreciation" in label: zero_dep = value
                except: continue

            driver.find_element(By.CSS_SELECTOR, "div.crossBg").click()
            time.sleep(2)
            return third_party, own_damage, zero_dep
        except Exception as e:
            return "NA", "NA", "NA"

    def check_and_switch_to_tab(target_tab):
        try:
            try:
                active_tab = driver.find_element(By.XPATH, "//li[contains(@class,'tabitem active')] | //li[contains(@class,'tabitem')][@class='active']")
                if target_tab in active_tab.text: return True
            except: pass
            tab_element = driver.find_element(By.XPATH, f"//*[contains(text(),'{target_tab}')]")
            driver.execute_script("arguments[0].click();", tab_element)
            time.sleep(3)
            return True
        except:
            return False

    def scrape_all_super_saver_plans(url):
        all_rows = []
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.planCard")))
            cards = driver.find_elements(By.CSS_SELECTOR, "div.planCard")
            for card_index in range(len(cards)):
                cards = driver.find_elements(By.CSS_SELECTOR, "div.planCard")
                card = cards[card_index]
                try:
                    company = card.find_element(By.XPATH, ".//div[contains(@class,'logo')]//img").get_attribute("alt")
                    km_options = card.find_elements(By.XPATH, ".//input[@type='radio']")
                    
                    if len(km_options) > 0:
                        km_values = []
                        for km_radio in km_options:
                            km_value = km_radio.get_attribute("value")
                            try: km_text = km_radio.find_element(By.XPATH, "./ancestor::label//p | ./ancestor::li//p").text
                            except: km_text = "N/A"
                            km_values.append({"value": km_value, "text": km_text})
                        
                        for km_option in km_values:
                            cards = driver.find_elements(By.CSS_SELECTOR, "div.planCard")
                            card = cards[card_index]
                            km_radio = card.find_element(By.XPATH, f".//input[@type='radio'][@value='{km_option['value']}']")
                            driver.execute_script("arguments[0].click();", km_radio)
                            time.sleep(2)
                            
                            cards = driver.find_elements(By.CSS_SELECTOR, "div.planCard")
                            card = cards[card_index]
                            
                            idv = clean_price(card.find_element(By.XPATH, ".//div[contains(@class,'idv')]").text)
                            premium = clean_price(card.find_elements(By.XPATH, ".//*[contains(text(),'₹')]")[-1].text)
                            description = extract_description(card)
                            description = f"{description} {km_option['value']} km/yr" if description != "NA" else f"Pay As You Drive {km_option['value']} km/yr"
                            third_party, own_damage, zero_dep = scrape_premium_breakdown(card)

                            all_rows.append([url, company, description, idv, premium, third_party, own_damage, zero_dep, km_option['value']])
                    else:
                        idv = clean_price(card.find_element(By.XPATH, ".//div[contains(@class,'idv')]").text)
                        premium = clean_price(card.find_elements(By.XPATH, ".//*[contains(text(),'₹')]")[-1].text)
                        description = extract_description(card)
                        third_party, own_damage, zero_dep = scrape_premium_breakdown(card)
                        all_rows.append([url, company, description, idv, premium, third_party, own_damage, zero_dep, "NA"])
                except: continue
        except: pass
        return all_rows

    # ===== RUN LOOP WITH VISUAL DIAGNOSTIC HOOKS =====
    try:
        for idx, url in enumerate(urls):
            status_container.warning(f"🌐 Scraping ({idx+1}/{len(urls)}): {url}")
            driver.get(url)
            time.sleep(8)  # Generous network synchronization allowance for remote clouds
            
            # DIAGNOSTIC HANDLER: Check if targeted network architecture blocks our cloud server
            page_src = driver.page_source.lower()
            if "access denied" in driver.title.lower() or "cloudflare" in page_src or "captcha" in page_src:
                status_container.error(f"❌ Security checkpoint or Block detected at URL #{idx+1}. Extracting debug snapshot...")
                driver.save_screenshot("debug_view.png")
                st.image("debug_view.png", caption=f"Live Cloud Engine Screenshot - URL #{idx+1}")
                continue

            try:
                try:
                    no_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//p[text()='No']")))
                    driver.execute_script("arguments[0].click();", no_btn)
                    time.sleep(2)
                except: pass

                ensure_filter_checked("Comprehensive/Package plans")
                ensure_filter_checked("Zero Depreciation")
                time.sleep(3)

                check_and_switch_to_tab("Complete Protection")
                
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.planCard")))
                cards = driver.find_elements(By.CSS_SELECTOR, "div.planCard")
                
                for i in range(len(cards)):
                    cards = driver.find_elements(By.CSS_SELECTOR, "div.planCard")
                    card = cards[i]
                    try:
                        company = card.find_element(By.XPATH, ".//div[contains(@class,'logo')]//img").get_attribute("alt")
                        idv = clean_price(card.find_element(By.XPATH, ".//div[contains(@class,'idv')]").text)
                        premium = clean_price(card.find_elements(By.XPATH, ".//*[contains(text(),'₹')]")[-1].text)
                        description = extract_description(card)
                        km_range = extract_km_from_text(description)
                        third_party, own_damage, zero_dep = scrape_premium_breakdown(card)

                        all_scraped_data.append([url, company, description, idv, premium, third_party, own_damage, zero_dep, km_range])
                    except: continue

                if check_and_switch_to_tab("Super Saver plans"):
                    time.sleep(2)
                    super_saver_rows = scrape_all_super_saver_plans(url)
                    all_scraped_data.extend(super_saver_rows)

            except Exception as e:
                continue
    finally:
        driver.quit()
        
    return all_scraped_data


# ===== INTERACTION LOGIC =====
if uploaded_excel:
    if uploaded_excel.name.endswith('.csv'):
        df = pd.read_csv(uploaded_excel)
    else:
        df = pd.read_excel(uploaded_excel)
        
    if "url" not in df.columns:
        st.error("❌ The uploaded file must contain a column named 'url'")
    else:
        urls = df["url"].dropna().tolist()
        st.success(f"📚 Loaded {len(urls)} URLs from file.")

        if st.button("🚀 Run Cloud Scraper"):
            log_box = st.empty()
            
            raw_data = run_cloud_scraper(urls, log_box)
            
            if raw_data:
                columns = ["URL", "Company", "Description", "IDV", "Premium", "Third Party", "Own Damage", "Zero Dep", "KM Range"]
                result_df = pd.DataFrame(raw_data, columns=columns)
                
                st.write("### 📊 Scraped Data Preview", result_df.head())
                
                csv = result_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv,
                    file_name="insurance_data.csv",
                    mime="text/csv",
                )
                log_box.success("🎯 Task finished completely!")
            else:
                log_box.error("❌ Cloud Chrome execution failed or could not read pages. Review any screenshots rendered above.")
else:
    st.info("💡 Upload your file on the sidebar to display the run button.")
