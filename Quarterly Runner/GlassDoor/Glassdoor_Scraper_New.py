#!/usr/bin/env python3
"""
New Glassdoor Scraper - More Robust Approach
Gets complete HTML pages and systematically extracts data
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
from lxml import html
import traceback

class GlassdoorScraperNew:
    def __init__(self):
        self.sb = None
        self.VIEW_NAME = "Matt View"
        self.GLASSDOOR_LOGIN_EMAIL = "czgojueycxqdjnvzjr@tmmbt.net"
        self.GLASSDOOR_PASSWORD = "czgojueycxqdjnvzjr@tmmbt.net"
        self.CRM_BASE_ID = 'appjvhsxUUz6o0dzo'
        self.CRM_TABLE = 'tblf4Ed9PaDo76QHH'
        self.API_KEY = 'patQIAmVOLuXelY42.df469e641a30f1e69d29195be1c1b1362c9416fffc0ac17fd3e1a0b49be8b961'
        self.headers = {'Authorization': 'Bearer ' + self.API_KEY}
        self.post_headers = {'Authorization': 'Bearer ' + self.API_KEY, 'Content-Type': 'application/json'}
        self.Companies = []
        
        # File paths
        self.COMPANIES_JSON_FILE = "companies_with_gd_urls.json"
        self.CSV_LOG_FILE = "scraping_results_new.csv"
        self.JSON_LOG_FILE = "update_log_new.json"
        self.HTML_DUMP_DIR = "html_dumps"
        
        # Create HTML dump directory
        if not os.path.exists(self.HTML_DUMP_DIR):
            os.makedirs(self.HTML_DUMP_DIR)
        
        # Initialize logging files
        self.initialize_logging_files()

    def initialize_logging_files(self):
        """Initialize CSV and JSON logging files with headers"""
        # Initialize CSV file with headers
        if not os.path.exists(self.CSV_LOG_FILE):
            with open(self.CSV_LOG_FILE, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    'Company Name', 'Glassdoor ID', 'Glassdoor URL', 'GD Overall Review',
                    'GD # of Reviews (Overall)', 'GD Benefits Review', 'GD # of Reviews (Benefits)',
                    'GD Retirement Review', 'GD # of Reviews (Retirement)', 'GD Health Insurance Review',
                    'GD # of Reviews (Health Insurance)', 'Glassdoor Engaged', 'Update Timestamp'
                ])
            print(f"✅ Created new CSV log file: {self.CSV_LOG_FILE}")
        
        # Initialize JSON log file if it doesn't exist
        if not os.path.exists(self.JSON_LOG_FILE):
            with open(self.JSON_LOG_FILE, 'w', encoding='utf-8') as jsonfile:
                json.dump([], jsonfile, indent=2)
            print(f"✅ Created new JSON log file: {self.JSON_LOG_FILE}")

    def login_glassdoor(self):
        print("🔐 Logging into Glassdoor...")
        self.sb.uc_open_with_reconnect("https://www.glassdoor.com/index.htm", 3)
        for _ in range(3):
            try:
                self.sb.wait_for_element("#inlineUserEmail", timeout=5)
                self.sb.type("#inlineUserEmail", self.GLASSDOOR_LOGIN_EMAIL + "\n")
                self.sb.type('input[type="password"]', self.GLASSDOOR_PASSWORD + "\n")
                print("✅ Login successful")
                break
            except Exception:
                print("🔁 Retrying login...")
                continue

    def get_companies_from_airtable(self):
        print("📋 Loading companies data with Glassdoor URLs...")
        
        # Check if JSON file exists
        if os.path.exists(self.COMPANIES_JSON_FILE):
            print(f"📁 Loading companies from existing file: {self.COMPANIES_JSON_FILE}")
            try:
                with open(self.COMPANIES_JSON_FILE, 'r', encoding='utf-8') as jsonfile:
                    all_companies = json.load(jsonfile)
                
                # Filter only companies that have Glassdoor URLs
                self.Companies = []
                for company in all_companies:
                    gd_url = company.get("GD URL") or company.get("Glassdoor URL") or company.get("glassdoor_url")
                    if gd_url and gd_url.strip().startswith("http"):
                        self.Companies.append({
                            "Company Name": company.get("Company Name") or company.get("company_name"),
                            "GD URL": gd_url,
                            "Website": company.get("Website") or company.get("Website (from Companies)", ""),
                            "Record ID": company.get("Record ID") or company.get("record_id", "")
                        })
                        print(f"➡️  Loaded company with GD URL: {self.Companies[-1]['Company Name']}")
                
                print(f"✅ Loaded {len(self.Companies)} companies with Glassdoor URLs from JSON file")
                return
            except Exception as e:
                print(f"❌ Error reading JSON file: {e}")
                print("🔄 Falling back to Airtable...")
        
        # Fetch from Airtable if JSON doesn't exist or is corrupted
        print("📋 Fetching company records from Airtable...")
        offset = ''
        all_airtable_companies = []
        
        while True:
            params = {'offset': offset}
            if self.VIEW_NAME:
                params['view'] = self.VIEW_NAME

            url = f'https://api.airtable.com/v0/{self.CRM_BASE_ID}/{self.CRM_TABLE}'
            response = requests.get(url, headers=self.headers, params=params).json()

            for record in response.get("records", []):
                fields = record.get("fields", {})
                if "Company Name" in fields:
                    company_data = {
                        "Company Name": fields["Company Name"],
                        "GD URL": fields.get("Glassdoor URL", None),
                        "Website": fields.get("Website (from Companies)", ""),
                        "Record ID": record["id"]
                    }
                    all_airtable_companies.append(company_data)
                    
                    # Only add to processing list if has Glassdoor URL
                    gd_url = company_data["GD URL"]
                    if gd_url and gd_url.strip().startswith("http"):
                        self.Companies.append(company_data)
                        print(f"➡️  Loaded company with GD URL: {fields['Company Name']}")

            if "offset" not in response:
                break
            offset = response["offset"]
        
        print(f"✅ Total companies with Glassdoor URLs: {len(self.Companies)}")
        print(f"📊 Total companies in Airtable: {len(all_airtable_companies)}")
        
        # Save all companies to JSON file for future use
        try:
            with open(self.COMPANIES_JSON_FILE, 'w', encoding='utf-8') as jsonfile:
                json.dump(all_airtable_companies, jsonfile, indent=2, ensure_ascii=False)
            print(f"💾 Saved all companies data to: {self.COMPANIES_JSON_FILE}")
        except Exception as e:
            print(f"❌ Error saving to JSON file: {e}")

    def save_html_dump(self, company_name, page_type, html_content):
        """Save HTML content to file for debugging"""
        safe_name = re.sub(r'[^\w\-_\.]', '_', company_name)
        filename = f"{self.HTML_DUMP_DIR}/{safe_name}_{page_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"💾 Saved {page_type} HTML to: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Error saving HTML: {e}")
            return None

    def extract_data_from_html(self, html_content, page_type):
        """Extract data from HTML content using multiple approaches"""
        tree = html.fromstring(html_content)
        data = {}
        
        print(f"🔍 Analyzing {page_type} page...")
        
        # Method 1: Look for all numerical ratings (decimal numbers) - using Python regex instead of XPath matches
        rating_elements = tree.xpath('//span')
        numerical_ratings = []
        
        for elem in rating_elements:
            text = elem.text_content().strip()
            if text and re.match(r'^[0-9]+\.[0-9]+$', text):
                numerical_ratings.append(elem)
        
        print(f"  Found {len(numerical_ratings)} numerical rating elements")
        
        for i, elem in enumerate(numerical_ratings):
            rating_text = elem.text_content().strip()
            parent = elem.getparent()
            parent_text = parent.text_content() if parent is not None else ""
            print(f"    Rating {i+1}: '{rating_text}' (context: '{parent_text[:100]}...')")
        
        # Method 2: Look for review counts
        review_elements = tree.xpath('//*[contains(text(), "review") or contains(text(), "Review")]')
        print(f"  Found {len(review_elements)} review-related elements")
        
        for i, elem in enumerate(review_elements[:5]):  # Show first 5
            text = elem.text_content().strip()
            print(f"    Review {i+1}: '{text[:100]}...'")
        
        # Method 3: Look for benefits-related content
        benefits_elements = tree.xpath('//*[contains(text(), "benefit") or contains(text(), "Benefit")]')
        print(f"  Found {len(benefits_elements)} benefits-related elements")
        
        # Method 4: Look for engaged status
        engaged_elements = tree.xpath('//*[contains(text(), "Engaged")]')
        print(f"  Found {len(engaged_elements)} engaged-related elements")
        
        # Extract specific data based on page type
        if page_type == "overview":
            data = self.extract_overview_data(tree, numerical_ratings)
        elif page_type == "benefits":
            data = self.extract_benefits_data(tree, numerical_ratings)
        
        return data

    def extract_overview_data(self, tree, rating_elements):
        """Extract data from overview page using correct CSS classes"""
        data = {}
        
        # Overall rating - use the specific CSS class found in HTML analysis
        overall_rating = None
        
        # Method 1: Use the correct CSS class for rating headline
        rating_headline_elements = tree.xpath('//p[@class="rating-headline-average_rating__J5rIy"]')
        if rating_headline_elements:
            overall_rating = rating_headline_elements[0].text_content().strip()
            print(f"🔍 Found overall rating using rating-headline-average_rating__J5rIy: {overall_rating}")
        
        # Fallback method: look for the main rating in rating elements
        if not overall_rating:
            for elem in rating_elements:
                parent_text = elem.getparent().text_content() if elem.getparent() else ""
                if any(word in parent_text.lower() for word in ['overall', 'rating', 'score']):
                    overall_rating = elem.text_content().strip()
                    print(f"🔍 Found overall rating using fallback method: {overall_rating}")
                    break
        
        # Final fallback: use first rating element
        if not overall_rating and rating_elements:
            overall_rating = rating_elements[0].text_content().strip()
            print(f"🔍 Using first rating element as overall rating: {overall_rating}")
        
        data['overall_rating'] = overall_rating
        
        # Review count - use the specific CSS class found in HTML analysis
        review_count = 0
        
        # Method 1: Use the correct CSS class for review count
        review_count_elements = tree.xpath('//p[@class="review-overview_reviewCount__hQpzR"]')
        if review_count_elements:
            review_text = review_count_elements[0].text_content().strip()
            # Extract number from text like "(7 total reviews)"
            match = re.search(r'\((\d+)\s+total\s+reviews?\)', review_text, re.IGNORECASE)
            if match:
                review_count = int(match.group(1))
                print(f"🔍 Found review count using review-overview_reviewCount__hQpzR: {review_count}")
        
        # Fallback method: look for review count in various patterns
        if review_count == 0:
            review_elements = tree.xpath('//*[contains(text(), "review") or contains(text(), "Review")]')
            for elem in review_elements:
                text = elem.text_content()
                # Look for numbers in parentheses or followed by "reviews"
                match = re.search(r'\((\d+)\)|(\d+)\s*(?:total\s+)?reviews?', text, re.IGNORECASE)
                if match:
                    review_count = int(match.group(1) or match.group(2))
                    print(f"🔍 Found review count using fallback method: {review_count}")
                    break
        
        data['review_count'] = review_count
        
        # Engaged status - Look for the actual engagement trigger text
        # "Is this your company?" = NOT engaged
        # "Engaged Employer" = IS engaged
        engaged = "No"  # Default to not engaged
        
        # Look for "Is this your company?" text in the engagement trigger (indicates NOT engaged)
        unclaimed_elements = tree.xpath('//p[contains(@class, "employer-engagement-status_engementTrigger__V1qrR") and contains(text(), "Is this your company?")]')
        if unclaimed_elements:
            engaged = "No"
            print(f"🔍 Found 'Is this your company?' in trigger - Company is NOT engaged")
        else:
            # Look for "Engaged Employer" text in the engagement trigger
            engaged_elements = tree.xpath('//p[contains(@class, "employer-engagement-status_engementTrigger__V1qrR") and contains(text(), "Engaged Employer")]')
            if engaged_elements:
                engaged = "Yes"
                print(f"🔍 Found 'Engaged Employer' in trigger - Company IS engaged")
            else:
                print(f"🔍 No engagement indicator found - Company is NOT engaged")
        
        data['engaged'] = engaged
        
        return data

    def extract_benefits_data(self, tree, rating_elements):
        """Extract data from benefits page using correct CSS classes"""
        data = {}
        
        # Benefits overall rating and review count - use specific CSS classes found in HTML analysis
        benefits_rating = None
        benefits_review_count = 0
        
        # Method 1: Use the correct CSS classes for benefits header rating (FIXED: span instead of p)
        benefits_rating_elements = tree.xpath('//span[@class="HeroRatingWrapper_benefitsRatingNumber__fqpP8"]')
        if benefits_rating_elements:
            benefits_rating = benefits_rating_elements[0].text_content().strip()
            print(f"🔍 Found benefits rating using HeroRatingWrapper_benefitsRatingNumber__fqpP8: {benefits_rating}")
        
        # Benefits review count using correct CSS class (FIXED: div/p instead of p)
        benefits_total_elements = tree.xpath('//div[@class="HeroRatingWrapper_benefitsTotalWrapper__li_iK"]/p')
        if benefits_total_elements:
            review_text = benefits_total_elements[0].text_content().strip()
            # Extract number from text like "(0 Reviews)"
            match = re.search(r'\((\d+)\s+Reviews?\)', review_text, re.IGNORECASE)
            if match:
                benefits_review_count = int(match.group(1))
                print(f"🔍 Found benefits review count using HeroRatingWrapper_benefitsTotalWrapper__li_iK: {benefits_review_count}")
        
        # Categorize ratings by context for specific benefit types
        health_rating = None
        retirement_rating = None
        health_review_count = 0
        retirement_review_count = 0
        
        # Look for specific benefit categories in the HTML structure
        # Look for Health Insurance rating
        health_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Health Insurance")]/following-sibling::span[contains(@class, "benefit-category-card_ratingNumber__VyQzt")]')
        if health_elements:
            health_rating = health_elements[0].text_content().strip()
            print(f"🔍 Found Health Insurance rating: {health_rating}")
            
            # Get Health Insurance review count
            health_review_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Health Insurance")]/ancestor::div[contains(@class, "benefit-category-card_benefitCategoryCard__VjIA1")]//span[contains(@class, "benefit-category-card_primaryText__YvBX2")]')
            if health_review_elements:
                review_text = health_review_elements[0].text_content().strip()
                match = re.search(r'(\d+)\s*Ratings?', review_text, re.IGNORECASE)
                if match:
                    health_review_count = int(match.group(1))
                    print(f"🔍 Found Health Insurance review count: {health_review_count}")
        
        # Look for Dental Insurance rating (if Health Insurance not found)
        if not health_rating:
            dental_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Dental Insurance")]/following-sibling::span[contains(@class, "benefit-category-card_ratingNumber__VyQzt")]')
            if dental_elements:
                health_rating = dental_elements[0].text_content().strip()
                print(f"🔍 Found Dental Insurance rating: {health_rating}")
                
                # Get Dental Insurance review count
                dental_review_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Dental Insurance")]/ancestor::div[contains(@class, "benefit-category-card_benefitCategoryCard__VjIA1")]//span[contains(@class, "benefit-category-card_primaryText__YvBX2")]')
                if dental_review_elements:
                    review_text = dental_review_elements[0].text_content().strip()
                    match = re.search(r'(\d+)\s*Ratings?', review_text, re.IGNORECASE)
                    if match:
                        health_review_count = int(match.group(1))
                        print(f"🔍 Found Dental Insurance review count: {health_review_count}")
        
        # Look for Vision Insurance rating (if others not found)
        if not health_rating:
            vision_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Vision Insurance")]/following-sibling::span[contains(@class, "benefit-category-card_ratingNumber__VyQzt")]')
            if vision_elements:
                health_rating = vision_elements[0].text_content().strip()
                print(f"🔍 Found Vision Insurance rating: {health_rating}")
                
                # Get Vision Insurance review count
                vision_review_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Vision Insurance")]/ancestor::div[contains(@class, "benefit-category-card_benefitCategoryCard__VjIA1")]//span[contains(@class, "benefit-category-card_primaryText__YvBX2")]')
                if vision_review_elements:
                    review_text = vision_review_elements[0].text_content().strip()
                    match = re.search(r'(\d+)\s*Ratings?', review_text, re.IGNORECASE)
                    if match:
                        health_review_count = int(match.group(1))
                        print(f"🔍 Found Vision Insurance review count: {health_review_count}")
        
        # Look for 401K Plan rating
        retirement_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "401K Plan")]/following-sibling::span[contains(@class, "benefit-category-card_ratingNumber__VyQzt")]')
        if retirement_elements:
            retirement_rating = retirement_elements[0].text_content().strip()
            print(f"🔍 Found 401K Plan rating: {retirement_rating}")
            
            # Get 401K Plan review count
            retirement_review_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "401K Plan")]/ancestor::div[contains(@class, "benefit-category-card_benefitCategoryCard__VjIA1")]//span[contains(@class, "benefit-category-card_primaryText__YvBX2")]')
            if retirement_review_elements:
                review_text = retirement_review_elements[0].text_content().strip()
                match = re.search(r'(\d+)\s*Ratings?', review_text, re.IGNORECASE)
                if match:
                    retirement_review_count = int(match.group(1))
                    print(f"🔍 Found 401K Plan review count: {retirement_review_count}")
        
        # Look for Pension Plan rating (if 401K not found)
        if not retirement_rating:
            pension_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Pension Plan")]/following-sibling::span[contains(@class, "benefit-category-card_ratingNumber__VyQzt")]')
            if pension_elements:
                retirement_rating = pension_elements[0].text_content().strip()
                print(f"🔍 Found Pension Plan rating: {retirement_rating}")
                
                # Get Pension Plan review count
                pension_review_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Pension Plan")]/ancestor::div[contains(@class, "benefit-category-card_benefitCategoryCard__VjIA1")]//span[contains(@class, "benefit-category-card_primaryText__YvBX2")]')
                if pension_review_elements:
                    review_text = pension_review_elements[0].text_content().strip()
                    match = re.search(r'(\d+)\s*Ratings?', review_text, re.IGNORECASE)
                    if match:
                        retirement_review_count = int(match.group(1))
                        print(f"🔍 Found Pension Plan review count: {retirement_review_count}")
        
        # Look for Retirement Plan rating (if others not found)
        if not retirement_rating:
            retirement_plan_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Retirement Plan")]/following-sibling::span[contains(@class, "benefit-category-card_ratingNumber__VyQzt")]')
            if retirement_plan_elements:
                retirement_rating = retirement_plan_elements[0].text_content().strip()
                print(f"🔍 Found Retirement Plan rating: {retirement_rating}")
                
                # Get Retirement Plan review count
                retirement_plan_review_elements = tree.xpath('//span[contains(@class, "benefit-category-card_title__Nu__H") and contains(text(), "Retirement Plan")]/ancestor::div[contains(@class, "benefit-category-card_benefitCategoryCard__VjIA1")]//span[contains(@class, "benefit-category-card_primaryText__YvBX2")]')
                if retirement_plan_review_elements:
                    review_text = retirement_plan_review_elements[0].text_content().strip()
                    match = re.search(r'(\d+)\s*Ratings?', review_text, re.IGNORECASE)
                    if match:
                        retirement_review_count = int(match.group(1))
                        print(f"🔍 Found Retirement Plan review count: {retirement_review_count}")
        
        # Fallback method: Use rating elements if specific methods didn't work
        if not benefits_rating:
            for elem in rating_elements:
                rating_text = elem.text_content().strip()
                parent = elem.getparent()
                parent_text = parent.text_content() if parent is not None else ""
                parent_lower = parent_text.lower()
                
                # Categorize based on parent text (only if we haven't found specific ratings)
                if not health_rating and any(word in parent_lower for word in ['health', 'medical', 'insurance']):
                    health_rating = rating_text
                elif not retirement_rating and any(word in parent_lower for word in ['retirement', '401', 'pension']):
                    retirement_rating = rating_text
                elif any(word in parent_lower for word in ['benefit', 'overall']):
                    benefits_rating = rating_text
        
        # If we couldn't find benefits rating, assign the first rating to benefits
        if not benefits_rating and rating_elements:
            benefits_rating = rating_elements[0].text_content().strip()
            print(f"🔍 Using first rating element as benefits rating: {benefits_rating}")
        
        # Fallback for benefits review count if not found - but only if benefits rating exists and is > 0
        if benefits_review_count == 0 and benefits_rating and float(benefits_rating) > 0:
            review_elements = tree.xpath('//*[contains(text(), "rating") or contains(text(), "Rating")]')
            for elem in review_elements:
                text = elem.text_content()
                match = re.search(r'(\d+)\s*(?:ratings?|reviews?)', text, re.IGNORECASE)
                if match:
                    benefits_review_count = int(match.group(1))
                    print(f"🔍 Found benefits review count using fallback method: {benefits_review_count}")
                    break
        
        # Ensure consistency: if benefits rating is 0.0 or None, review count should be 0
        try:
            if not benefits_rating or (benefits_rating and float(benefits_rating) == 0.0):
                benefits_review_count = 0
                print(f"🔍 Benefits rating is 0.0 or None, setting review count to 0")
        except (ValueError, TypeError):
            # If we can't convert to float, check if it's a string "0" or "0.0"
            if benefits_rating in ["0", "0.0", "0.00"]:
                benefits_review_count = 0
                print(f"🔍 Benefits rating is '{benefits_rating}', setting review count to 0")
        
        # Set None for missing values (Airtable will handle as empty/null)
        if not health_rating:
            health_rating = None
        if not retirement_rating:
            retirement_rating = None
        if not benefits_rating:
            benefits_rating = None
        
        data['benefits_rating'] = benefits_rating
        data['health_rating'] = health_rating
        data['retirement_rating'] = retirement_rating
        data['benefits_review_count'] = benefits_review_count
        data['health_review_count'] = health_review_count
        data['retirement_review_count'] = retirement_review_count
        
        return data

    def clean_rating_value(self, text):
        """Clean and validate rating value"""
        if not text:
            return None
        
        # Handle N/A values - return None instead of "N/A" for Airtable compatibility
        if text.strip().upper() == "N/A":
            return None
        
        try:
            import re
            # Remove any non-numeric characters except decimal point
            cleaned = re.sub(r'[^\d.]', '', text.strip())
            if cleaned:
                # Check if it's a valid rating (between 0 and 5)
                rating = float(cleaned)
                if 0 <= rating <= 5:
                    return rating
            return None
        except:
            return None

    def check_existing_html_files(self, company_name):
        """Check if HTML files already exist for this company"""
        safe_name = re.sub(r'[^\w\-_\.]', '_', company_name)
        overview_files = []
        benefits_files = []
        
        print(f"🔍 Looking for existing files for company: '{company_name}'")
        print(f"🔍 Safe name pattern: '{safe_name}'")
        
        # Search for existing HTML files
        if os.path.exists(self.HTML_DUMP_DIR):
            print(f"🔍 Searching in directory: {self.HTML_DUMP_DIR}")
            all_files = os.listdir(self.HTML_DUMP_DIR)
            matching_files = [f for f in all_files if company_name in f and f.endswith('.html')]
            print(f"🔍 Files containing '{company_name}': {matching_files}")
            
            for filename in all_files:
                # More flexible matching - check if company name is in filename
                if (company_name.lower() in filename.lower() or safe_name in filename) and filename.endswith('.html'):
                    full_path = os.path.join(self.HTML_DUMP_DIR, filename)
                    if 'overview' in filename:
                        overview_files.append(full_path)
                        print(f"✅ Found overview file: {filename}")
                    elif 'benefits' in filename:
                        benefits_files.append(full_path)
                        print(f"✅ Found benefits file: {filename}")
        
        # Return the most recent files (if any)
        overview_file = max(overview_files, key=os.path.getmtime) if overview_files else None
        benefits_file = max(benefits_files, key=os.path.getmtime) if benefits_files else None
        
        print(f"🔍 Final results - Overview: {'Found' if overview_file else 'Not found'}, Benefits: {'Found' if benefits_file else 'Not found'}")
        
        return overview_file, benefits_file

    def load_html_from_file(self, filepath):
        """Load HTML content from existing file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"❌ Error reading HTML file {filepath}: {e}")
            return None

    def scrape_company_data(self, company, gdurl):
        """Main scraping function for a company"""
        print(f"🧲 Scraping data for: {company}")
        print(f"🔗 URL: {gdurl}")
        
        try:
            # Step 0: Check for existing HTML files first
            print("🔍 Step 0: Checking for existing HTML files...")
            existing_overview_file, existing_benefits_file = self.check_existing_html_files(company)
            
            if existing_overview_file:
                print(f"📁 Found existing overview file: {existing_overview_file}")
            else:
                print("📁 No existing overview file found")
                
            if existing_benefits_file:
                print(f"📁 Found existing benefits file: {existing_benefits_file}")
            else:
                print("📁 No existing benefits file found")
            
            overview_html = None
            benefits_html = None
            overview_file = existing_overview_file
            benefits_file = existing_benefits_file
            
            # Step 1: Get overview page (use existing file or scrape new)
            if existing_overview_file:
                print("� Step 1: Loading overview page from existing file...")
                overview_html = self.load_html_from_file(existing_overview_file)
                if overview_html:
                    print("✅ Successfully loaded existing overview HTML")
                else:
                    print("❌ Failed to load existing overview HTML, will scrape new")
            
            if not overview_html:
                print("📄 Step 1: Loading overview page from web...")
                self.sb.open(gdurl)
                time.sleep(8)
                overview_html = self.sb.get_page_source()
                
                # Save overview HTML
                overview_file = self.save_html_dump(company, "overview", overview_html)
            
            # Extract overview data
            overview_data = self.extract_data_from_html(overview_html, "overview")
            print(f"📊 Overview data: {overview_data}")
            
            # Step 2: Try to get benefits page (use existing file or scrape new)
            benefits_data = {}
            
            if existing_benefits_file:
                print("� Step 2: Loading benefits page from existing file...")
                benefits_html = self.load_html_from_file(existing_benefits_file)
                if benefits_html:
                    print("✅ Successfully loaded existing benefits HTML")
                    # Extract benefits data
                    benefits_data = self.extract_data_from_html(benefits_html, "benefits")
                    print(f"📊 Benefits data: {benefits_data}")
                else:
                    print("❌ Failed to load existing benefits HTML, will scrape new")
            
            if not benefits_html:
                print("📄 Step 2: Loading benefits page from web...")
                benefits_link = None
                
                # Look for benefits link - be more specific to avoid survey links
                tree = html.fromstring(overview_html)
                
                # First try to find the actual benefits page link (not survey links)
                benefits_links = tree.xpath('//a[contains(@href, "/Benefits/") and not(contains(@href, "create") or contains(@href, "survey"))]/@href')
                
                if not benefits_links:
                    # Fallback: look for any benefits link but exclude survey/create links
                    all_benefits_links = tree.xpath('//a[contains(@href, "benefits") or contains(text(), "Benefits")]/@href')
                    benefits_links = [link for link in all_benefits_links if 'create' not in link and 'survey' not in link]
                
                if benefits_links:
                    benefits_link = benefits_links[0]
                    print(f"🔗 Found benefits link: {benefits_link}")
                    
                    # Validate the link - it should contain the company ID
                    if 'EI_IE' in gdurl:
                        company_id = gdurl.split('EI_IE')[1].split('.')[0]
                        if company_id not in benefits_link:
                            print(f"⚠️ Benefits link doesn't contain company ID {company_id}, might be wrong link")
                    
                    try:
                        full_benefits_url = f"https://www.glassdoor.com{benefits_link}"
                        
                        # Check if browser window is still open
                        try:
                            current_url = self.sb.get_current_url()
                            print(f"🔍 Current URL: {current_url}")
                        except Exception as e:
                            print(f"❌ Browser window closed, reopening...")
                            self.sb.open(gdurl)  # Go back to overview page
                            time.sleep(3)
                        
                        self.sb.open(full_benefits_url)
                        time.sleep(8)
                        benefits_html = self.sb.get_page_source()
                        
                        # Save benefits HTML
                        benefits_file = self.save_html_dump(company, "benefits", benefits_html)
                        
                        # Extract benefits data
                        benefits_data = self.extract_data_from_html(benefits_html, "benefits")
                        print(f"📊 Benefits data: {benefits_data}")
                        
                    except Exception as e:
                        print(f"❌ Error loading benefits page: {e}")
                        print(f"🔍 Full error: {traceback.format_exc()}")
                        benefits_file = None
                else:
                    print("⚠️ No valid benefits link found (only found survey/create links)")
                    
                    # Try to construct benefits URL manually
                    if 'EI_IE' in gdurl:
                        company_id = gdurl.split('EI_IE')[1].split('.')[0]
                        manual_benefits_url = f"https://www.glassdoor.com/Benefits/Audience-US-Benefits-EI_IE{company_id}.0,8_IL.9,11_IN1.htm"
                        print(f"🔗 Trying manual benefits URL: {manual_benefits_url}")
                        
                        try:
                            print("📄 Step 2: Loading manual benefits page...")
                            self.sb.open(manual_benefits_url)
                            time.sleep(8)
                            benefits_html = self.sb.get_page_source()
                            
                            # Save benefits HTML
                            benefits_file = self.save_html_dump(company, "benefits_manual", benefits_html)
                            
                            # Extract benefits data
                            benefits_data = self.extract_data_from_html(benefits_html, "benefits")
                            print(f"📊 Benefits data: {benefits_data}")
                            
                        except Exception as e:
                            print(f"❌ Error loading manual benefits page: {e}")
                            print(f"🔍 Full error: {traceback.format_exc()}")
                            benefits_file = None
                    company_id = gdurl.split('EI_IE')[1].split('.')[0]
                    manual_benefits_url = f"https://www.glassdoor.com/Benefits/Audience-US-Benefits-EI_IE{company_id}.0,8_IL.9,11_IN1.htm"
                    print(f"🔗 Trying manual benefits URL: {manual_benefits_url}")
                    
                    try:
                        print("📄 Step 2: Loading manual benefits page...")
                        self.sb.open(manual_benefits_url)
                        time.sleep(8)
                        benefits_html = self.sb.get_page_source()
                        
                        # Save benefits HTML
                        benefits_file = self.save_html_dump(company, "benefits_manual", benefits_html)
                        
                        # Extract benefits data
                        benefits_data = self.extract_data_from_html(benefits_html, "benefits")
                        print(f"📊 Benefits data: {benefits_data}")
                        
                    except Exception as e:
                        print(f"❌ Error loading manual benefits page: {e}")
                        print(f"🔍 Full error: {traceback.format_exc()}")
                        benefits_file = None
            
            # Step 3: Combine and clean data
            print("🧹 Step 3: Cleaning and combining data...")
            
            # Clean rating values
            overall_rating_clean = self.clean_rating_value(overview_data.get('overall_rating'))
            benefits_rating_clean = self.clean_rating_value(benefits_data.get('benefits_rating'))
            health_rating_clean = self.clean_rating_value(benefits_data.get('health_rating'))
            retirement_rating_clean = self.clean_rating_value(benefits_data.get('retirement_rating'))
            
            print(f"🧹 Cleaned ratings:")
            print(f"  Overall: {overall_rating_clean}")
            print(f"  Benefits: {benefits_rating_clean}")
            print(f"  Health: {health_rating_clean}")
            print(f"  Retirement: {retirement_rating_clean}")
            
            # Extract Glassdoor ID
            gd_id = ""
            if "EI_IE" in gdurl:
                gd_id = gdurl.split("EI_IE")[1].split(".")[0]
            
            # Step 4: Update Airtable
            print("📤 Step 4: Updating Airtable...")
            
            # Get record ID from Airtable
            encoded_formula = urllib.parse.quote(f"{{Company Name}}='{company}'")
            res = requests.get(f"https://api.airtable.com/v0/{self.CRM_BASE_ID}/{self.CRM_TABLE}?filterByFormula={encoded_formula}", headers=self.headers).json()
            
            if not res.get("records"):
                print(f"❌ Company not found in Airtable: {company}")
                return False
            
            record_id = res["records"][0]["id"]
            
            # Prepare data for Airtable
            data = {
                "fields": {
                    "Glassdoor ID": gd_id,
                    "GD Overall Review": overall_rating_clean,
                    "GD # of Reviews (Overall)": overview_data.get('review_count', 0),
                    "GD Benefits Review": benefits_rating_clean,
                    "GD # of Reviews (Benefits)": benefits_data.get('benefits_review_count', 0),
                    "GD Retirement Review": retirement_rating_clean,
                    "GD # of Reviews (Retirement)": benefits_data.get('retirement_review_count', 0),
                    "GD Health Insurance Review": health_rating_clean,
                    "GD # of Reviews (Health Insurance)": benefits_data.get('health_review_count', 0),
                    "Glassdoor Engaged": overview_data.get('engaged', 'No'),
                }
            }
            
            print(f"📤 Sending data to Airtable: {data}")
            
            # Update Airtable
            patch_url = f"https://api.airtable.com/v0/{self.CRM_BASE_ID}/{self.CRM_TABLE}/{record_id}"
            r = requests.patch(patch_url, headers=self.post_headers, data=json.dumps(data))
            
            success = r.status_code == 200
            print(f"📤 Airtable update result: {r.status_code}")
            
            if not success:
                print(f"❌ Airtable error: {r.json()}")
            
            # Step 5: Log results
            print("📝 Step 5: Logging results...")
            self.log_results(company, record_id, gd_id, gdurl, data, success, overview_file, benefits_file)
            
            return success
            
        except Exception as e:
            print(f"❌ Error scraping {company}: {e}")
            print(f"🔍 Full error traceback: {traceback.format_exc()}")
            return False

    def log_results(self, company, record_id, gd_id, gdurl, data, success, overview_file, benefits_file):
        """Log results to CSV and JSON files"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Log to CSV
        try:
            with open(self.CSV_LOG_FILE, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    company,
                    gd_id,
                    gdurl,
                    data["fields"]["GD Overall Review"],
                    data["fields"]["GD # of Reviews (Overall)"],
                    data["fields"]["GD Benefits Review"],
                    data["fields"]["GD # of Reviews (Benefits)"],
                    data["fields"]["GD Retirement Review"],
                    data["fields"]["GD # of Reviews (Retirement)"],
                    data["fields"]["GD Health Insurance Review"],
                    data["fields"]["GD # of Reviews (Health Insurance)"],
                    data["fields"]["Glassdoor Engaged"],
                    timestamp
                ])
        except Exception as e:
            print(f"❌ Error writing to CSV: {e}")
        
        # Log to JSON
        try:
            with open(self.JSON_LOG_FILE, 'r', encoding='utf-8') as jsonfile:
                log_data = json.load(jsonfile)
            
            log_entry = {
                "company": company,
                "record_id": record_id,
                "glassdoor_id": gd_id,
                "glassdoor_url": gdurl,
                "overview_html_file": overview_file,
                "benefits_html_file": benefits_file,
                "update_time": timestamp,
                "update_successful": success,
                "data": data["fields"]
            }
            
            log_data.append(log_entry)
            
            with open(self.JSON_LOG_FILE, 'w', encoding='utf-8') as jsonfile:
                json.dump(log_data, jsonfile, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Error writing to JSON log: {e}")

    def main(self):
        # Start timing
        start_time = time.time()
        
        with SB(uc=True, headless=False) as sb:
            self.sb = sb
            self.login_glassdoor()
            self.get_companies_from_airtable()

            # TEST MODE: Process first 10 companies for testing
            test_mode = False  # Set to False to run complete script
            
            if test_mode:
                print("🧪 TEST MODE: Processing first 10 companies...")
                test_companies = self.Companies[:3]  # Limit to first 10 companies
                companies_to_process = test_companies
                print(f"📊 Test will process {len(companies_to_process)} companies")
            else:
                print("🚀 NORMAL MODE: Processing all companies...")
                companies_to_process = self.Companies
            total_companies = len(companies_to_process)
            
            print(f"🚀 Starting scraping process for {total_companies} companies...")
            
            for index, record in enumerate(companies_to_process, 1):
                company_start_time = time.time()
                company = record["Company Name"]
                gdurl = record["GD URL"]
                
                # Show progress: Company Name (x/total)
                print(f"\n{'='*60}")
                print(f"📊 Processing: {company} ({index}/{total_companies})")
                print(f"{'='*60}")
                
                if gdurl and gdurl.strip().startswith("http"):
                    success = self.scrape_company_data(company, gdurl)
                    if success:
                        print(f"✅ Successfully processed {company} ({index}/{total_companies})")
                    else:
                        print(f"❌ Failed to process {company} ({index}/{total_companies})")
                    
                    # Calculate timing for this company
                    company_time = time.time() - company_start_time
                    company_minutes = company_time / 60
                    
                    # Calculate total time spent so far
                    total_time_spent = time.time() - start_time
                    total_minutes_spent = total_time_spent / 60
                    
                    # Calculate average time per company
                    avg_time_per_company = total_time_spent / index
                    
                    # Calculate estimated time remaining
                    companies_remaining = total_companies - index
                    estimated_time_remaining = companies_remaining * avg_time_per_company
                    estimated_minutes_remaining = estimated_time_remaining / 60
                    
                    print(f"⏱️  Company time: {company_minutes:.1f} minutes")
                    print(f"⏱️  Total time spent: {total_minutes_spent:.1f} minutes")
                    print(f"⏱️  Estimated time remaining: {estimated_minutes_remaining:.1f} minutes")
                    
                    # Add delay between companies
                    time.sleep(random.uniform(2, 5))
                else:
                    print(f"❌ Skipping {company} ({index}/{total_companies}) — invalid or missing Glassdoor URL.")
            
            # Calculate final timing
            total_time_spent = time.time() - start_time
            total_minutes_spent = total_time_spent / 60
            total_hours_spent = total_minutes_spent / 60
            
            if test_mode:
                print(f"\n🧪 TEST COMPLETED! Processed {total_companies} companies.")
                print(f"📊 If results look good, change 'test_mode = False' to run all companies.")
            else:
                print(f"\n🎉 FULL SCRAPING COMPLETED! Processed {total_companies} companies!")
            
            print(f"⏱️  Total time spent: {total_minutes_spent:.1f} minutes ({total_hours_spent:.2f} hours)")

if __name__ == "__main__":
    GlassdoorScraperNew().main()
