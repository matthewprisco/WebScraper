#!/usr/bin/env python3
"""
Glassdoor URL Finder
Searches for Glassdoor URLs for companies without URLs and updates Airtable
"""

import re
import requests
import urllib.parse
import json
import time
import random
import csv
import os
from datetime import datetime
from seleniumbase import SB
from selenium.webdriver.common.by import By

class GlassdoorURLFinder:
    def __init__(self):
        self.sb = None
        self.CRM_BASE_ID = 'appjvhsxUUz6o0dzo'
        self.CRM_TABLE = 'tblf4Ed9PaDo76QHH'
        self.API_KEY = 'patQIAmVOLuXelY42.df469e641a30f1e69d29195be1c1b1362c9416fffc0ac17fd3e1a0b49be8b961'
        self.headers = {'Authorization': 'Bearer ' + self.API_KEY}
        self.post_headers = {'Authorization': 'Bearer ' + self.API_KEY, 'Content-Type': 'application/json'}
        
        # File paths
        self.INPUT_FILE = "companies_without_glassdoor.json"
        self.FOUND_URLS_FILE = "new-search-urls.csv"
        self.FOUND_URLS_JSON = "new-search-urls.json"
        self.NOT_FOUND_FILE = "new-search-NOT_FOUND_URLS.csv"
        
        # Initialize CSV files
        self.initialize_csv_files()

    def initialize_csv_files(self):
        """Initialize CSV files with headers"""
        # Initialize found URLs CSV
        if not os.path.exists(self.FOUND_URLS_FILE):
            with open(self.FOUND_URLS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Company Name', 'GD URL', 'Website', 'Record ID', 'Glassdoor ID', 'Search Timestamp'])
            print(f"✅ Created found URLs CSV: {self.FOUND_URLS_FILE}")
        
        # Initialize found URLs JSON
        if not os.path.exists(self.FOUND_URLS_JSON):
            with open(self.FOUND_URLS_JSON, 'w', encoding='utf-8') as jsonfile:
                json.dump([], jsonfile, indent=2)
            print(f"✅ Created found URLs JSON: {self.FOUND_URLS_JSON}")
        
        # Initialize not found URLs CSV
        if not os.path.exists(self.NOT_FOUND_FILE):
            with open(self.NOT_FOUND_FILE, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Company Name', 'Website', 'Record ID', 'Search Timestamp'])
            print(f"✅ Created not found URLs CSV: {self.NOT_FOUND_FILE}")

    def login_glassdoor(self):
        """No login needed for Google search"""
        print("🔍 Starting Google search (no login required)")
        pass

    def filter_domain(self, url):
        match = re.search(r"https?://(?:www\\.)?([^/]+)", url)
        return match.group(1) if match else None

    def search_glassdoor_url(self, company, website):
        """Search for Glassdoor URL using DuckDuckGo search"""
        print(f"🔍 Searching Glassdoor URL for: {company}")
        query = f"site:glassdoor.com \"{company}\" Overview"
        self.sb.open(f"https://duckduckgo.com/?q={urllib.parse.quote_plus(query)}")
        time.sleep(3)

        try:
            # Try multiple selectors for DuckDuckGo search results
            selectors = [
                "//a[contains(@href, 'glassdoor.com')]",
                "//a[contains(@href, 'glassdoor.com/Overview')]",
                "//div[@class='result__a']//a",
                "//div[@class='result']//a",
                "//div[contains(@class, 'result')]//a",
                "//h2[@class='result__title']//a",
                "//a[contains(@class, 'result__a')]"
            ]
            
            gdurl = None
            for selector in selectors:
                try:
                    links = self.sb.find_elements(selector, By.XPATH)
                    print(f"🔍 Found {len(links)} links with selector: {selector}")
                    for link in links:
                        href = link.get_attribute("href")
                        if href and "/Overview/Working-at-" in href:
                            gdurl = href
                            print(f"✅ Found Glassdoor URL: {gdurl}")
                            break
                    if gdurl:
                        break
                except Exception as e:
                    print(f"⚠️ Selector failed: {selector} - {e}")
                    continue
            
            # If no URL found with specific selectors, try getting all links
            if not gdurl:
                print("🔍 Trying to get all links on page...")
                try:
                    all_links = self.sb.find_elements("//a", By.XPATH)
                    print(f"🔍 Found {len(all_links)} total links on page")
                    for link in all_links:
                        href = link.get_attribute("href")
                        if href and "glassdoor.com/Overview/Working-at-" in href:
                            gdurl = href
                            print(f"✅ Found Glassdoor URL from all links: {gdurl}")
                            break
                except Exception as e:
                    print(f"⚠️ Error getting all links: {e}")
            
            if gdurl:
                # Verify the URL by visiting it
                try:
                    self.sb.open(gdurl)
                    time.sleep(2)
                    current_url = self.sb.get_current_url()
                    if "glassdoor.com" in current_url:
                        print(f"✅ Verified Glassdoor URL: {current_url}")
                        return current_url
                    else:
                        print(f"⚠️ URL verification failed, but using found URL: {gdurl}")
                        return gdurl
                except Exception as e:
                    print(f"⚠️ URL verification failed: {e}, but using found URL: {gdurl}")
                    return gdurl
            else:
                print(f"❌ No Glassdoor URL found for: {company}")
                return None
                
        except Exception as e:
            print(f"❌ DuckDuckGo search error for {company}: {e}")
            return None

    def extract_glassdoor_id(self, url):
        """Extract Glassdoor ID from URL"""
        if "EI_IE" in url:
            gd_id = url.split("EI_IE")[1].split(".")[0]
            return gd_id
        return None

    def update_airtable(self, company, gdurl, record_id):
        """Update Airtable with Glassdoor URL and ID"""
        print(f"📥 Updating Airtable for: {company}")
        
        gd_id = self.extract_glassdoor_id(gdurl)
        
        data = {
            "fields": {
                "Glassdoor URL": gdurl
            }
        }
        
        if gd_id:
            data["fields"]["Glassdoor ID"] = gd_id
        
        patch_url = f"https://api.airtable.com/v0/{self.CRM_BASE_ID}/{self.CRM_TABLE}/{record_id}"
        res = requests.patch(patch_url, headers=self.post_headers, data=json.dumps(data))
        
        success = res.status_code == 200
        print(f"📤 Airtable update result: {res.status_code}")
        
        if not success:
            print(f"❌ Airtable error: {res.json()}")
        
        return success, gd_id

    def save_found_url(self, company_data, gdurl, gd_id):
        """Save found URL to CSV and JSON"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Save to CSV
        try:
            with open(self.FOUND_URLS_FILE, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    company_data['Company Name'],
                    gdurl,
                    company_data.get('Website', ''),
                    company_data['Record ID'],
                    gd_id or '',
                    timestamp
                ])
            print(f"✅ Saved found URL to CSV: {company_data['Company Name']}")
        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")
        
        # Save to JSON
        try:
            # Read existing JSON data
            with open(self.FOUND_URLS_JSON, 'r', encoding='utf-8') as jsonfile:
                found_data = json.load(jsonfile)
            
            # Add new entry
            found_entry = {
                "Company Name": company_data['Company Name'],
                "GD URL": gdurl,
                "Website": company_data.get('Website', ''),
                "Record ID": company_data['Record ID'],
                "Glassdoor ID": gd_id or "",
                "Search Timestamp": timestamp
            }
            found_data.append(found_entry)
            
            # Write back to JSON
            with open(self.FOUND_URLS_JSON, 'w', encoding='utf-8') as jsonfile:
                json.dump(found_data, jsonfile, indent=2, ensure_ascii=False)
            print(f"✅ Saved found URL to JSON: {company_data['Company Name']}")
        except Exception as e:
            print(f"❌ Error saving to JSON: {e}")

    def save_not_found(self, company_data):
        """Save not found company to CSV"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(self.NOT_FOUND_FILE, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    company_data['Company Name'],
                    company_data.get('Website', ''),
                    company_data['Record ID'],
                    timestamp
                ])
            print(f"✅ Saved not found to CSV: {company_data['Company Name']}")
        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")

    def load_companies(self):
        """Load companies from JSON file"""
        print(f"📋 Loading companies from: {self.INPUT_FILE}")
        
        try:
            with open(self.INPUT_FILE, 'r', encoding='utf-8') as jsonfile:
                companies = json.load(jsonfile)
            
            # Filter companies that don't have valid Glassdoor URLs
            companies_to_search = []
            for company in companies[0:7]:
                gd_url = company.get('GD URL')
                if not gd_url or gd_url == '\n' or gd_url.strip() == '':
                    companies_to_search.append(company)
            
            print(f"✅ Loaded {len(companies)} companies, {len(companies_to_search)} need URL search")
            return companies_to_search
            
        except Exception as e:
            print(f"❌ Error loading companies: {e}")
            return []

    def main(self):
        """Main function to search for Glassdoor URLs"""
        # Start timing
        start_time = time.time()
        
        with SB(uc=True, headless=False) as sb:
            self.sb = sb
            print("🔍 Starting URL search (no login required)")
            
            # Load companies
            companies = self.load_companies()
            
            if not companies:
                print("❌ No companies to search for URLs")
                return
            
            print(f"🚀 Starting URL search for {len(companies)} companies...")
            
            found_count = 0
            not_found_count = 0
            
            for index, company_data in enumerate(companies, 1):
                company_name = company_data['Company Name']
                website = company_data.get('Website', '')
                record_id = company_data['Record ID']
                
                # Show progress with timing
                print(f"\n{'='*60}")
                print(f"📊 Processing: {company_name} ({index}/{len(companies)})")
                print(f"{'='*60}")
                
                # Start timing for this company
                company_start_time = time.time()
                
                try:
                    # Search for Glassdoor URL
                    gdurl = self.search_glassdoor_url(company_name, website)
                    
                    if gdurl:
                        # Update Airtable
                        success, gd_id = self.update_airtable(company_name, gdurl, record_id)
                        # Save to found URLs CSV
                        self.save_found_url(company_data, gdurl, gd_id)
                        
                        found_count += 1
                        print(f"✅ Successfully found URL for {company_name}")
                    else:
                        # Save to not found CSV
                        self.save_not_found(company_data)
                        
                        not_found_count += 1
                        print(f"❌ No URL found for {company_name}")
                    
                    # Calculate timing for this company
                    company_time_spent = time.time() - company_start_time
                    company_minutes = company_time_spent / 60
                    
                    # Calculate total time and estimated remaining
                    total_time_spent = time.time() - start_time
                    total_minutes_spent = total_time_spent / 60
                    
                    # Calculate average time per company and estimated remaining
                    if index > 0:
                        avg_time_per_company = total_minutes_spent / index
                        remaining_companies = len(companies) - index
                        estimated_remaining = avg_time_per_company * remaining_companies
                        
                        print(f"⏱️  Company time: {company_minutes:.1f} minutes")
                        print(f"⏱️  Total time spent: {total_minutes_spent:.1f} minutes")
                        print(f"⏱️  Estimated time remaining: {estimated_remaining:.1f} minutes")
                    
                    # Add delay between searches
                    time.sleep(random.uniform(2, 5))
                    
                except Exception as e:
                    print(f"❌ Error processing {company_name}: {e}")
                    # Save to not found CSV
                    self.save_not_found(company_data)
                    not_found_count += 1
                    
                    # Calculate timing even for errors
                    company_time_spent = time.time() - company_start_time
                    company_minutes = company_time_spent / 60
                    
                    total_time_spent = time.time() - start_time
                    total_minutes_spent = total_time_spent / 60
                    
                    if index > 0:
                        avg_time_per_company = total_minutes_spent / index
                        remaining_companies = len(companies) - index
                        estimated_remaining = avg_time_per_company * remaining_companies
                        
                        print(f"⏱️  Company time: {company_minutes:.1f} minutes")
                        print(f"⏱️  Total time spent: {total_minutes_spent:.1f} minutes")
                        print(f"⏱️  Estimated time remaining: {estimated_remaining:.1f} minutes")
            
            # Calculate final timing
            total_time_spent = time.time() - start_time
            total_minutes_spent = total_time_spent / 60
            
            print(f"\n🎉 URL search completed!")
            print(f"📊 Results:")
            print(f"  ✅ Found URLs: {found_count}")
            print(f"  ❌ Not Found: {not_found_count}")
            print(f"  ⏱️  Total time: {total_minutes_spent:.1f} minutes")
            print(f"  📁 Results saved to:")
            print(f"    - Found URLs CSV: {self.FOUND_URLS_FILE}")
            print(f"    - Found URLs JSON: {self.FOUND_URLS_JSON}")
            print(f"    - Not Found: {self.NOT_FOUND_FILE}")

if __name__ == "__main__":
    GlassdoorURLFinder().main() 