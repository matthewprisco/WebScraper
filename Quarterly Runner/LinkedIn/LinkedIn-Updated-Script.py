# Overview
# The main objective of this code is to update records in an Airtable database with data that is retrieved, most likely
# through web scraping, regarding companies' information such as employee counts, open job positions, LinkedIn URL, etc.

# This script automates the task of updating company data in an Airtable database. It retrieves the necessary data,
# constructs requests to modify records, handles potential errors gracefully, and ensures proper resource management
# by terminating the web driver session after operations are completed. The script effectively links collected data
# with Cloud-based storage, improving efficiency in data management tasks.


from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import time,json,requests,os.path

import pandas as pd
from openpyxl import load_workbook
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest


class Linkedin:
	def __init__(self):
		# credential
		self.VIEW_NAME = "Matt View"
		self.INPUT_BASE_ID = 'appjvhsxUUz6o0dzo'
		self.OUTPUT_BASE_ID = 'appQfs70fHCsFgeUe'
		self.API_KEY = 'patQIAmVOLuXelY42.df469e641a30f1e69d29195be1c1b1362c9416fffc0ac17fd3e1a0b49be8b961'
		self.CompanyTable = 'tbl6d9xMvwRKcTlfY'
		self.Prospectus_Table = 'tblf4Ed9PaDo76QHH'
		self.GeoCitiesTable = 'tbl4PsNMGFGC4BRyE'
		self.OUTPUT_Table = 'tbli5Waff0LBrM5jU'
		self.WebscraperBase_OpenJob = "tblFx6SBmtNRCeOgm"
		self.headers = {'Authorization': 'Bearer '+ self.API_KEY}
		self.Post_Header = {'Authorization': 'Bearer '+ self.API_KEY,'Content-Type': 'application/json'}
		self.geoTableIds = {}
		self.AllRecordIds = []
		self.update_log = []  # Track all updates
		self.log_filename = None  # Will be set when log file is created

		self.social_info = None

	def create_log_file(self):
		"""
		Create or load the log file at the start of the process
		"""
		self.log_filename = "linkedin_scraping_log.json"
		
		# Check if log file already exists
		if os.path.exists(self.log_filename):
			try:
				with open(self.log_filename, "r") as f:
					existing_log = json.load(f)
				print(f"📝 Loaded existing log file: {self.log_filename} with {len(existing_log)} entries")
			except Exception as e:
				print(f"⚠️ Error reading existing log file, creating new one: {e}")
				existing_log = []
		else:
			existing_log = []
			print(f"📝 Created new log file: {self.log_filename}")
		
		# Store existing log entries in the update_log list
		self.update_log = existing_log

	def log_update(self, company_name, linkedin_id, record_id, condition, status="Success"):
		"""
		Log an update to the tracking file and append to existing log
		"""
		update_entry = {
			"Company_Name": company_name,
			"LinkedIn_ID": linkedin_id,
			"Record_ID": record_id,
			"Airtable_URL": f"https://airtable.com/{self.INPUT_BASE_ID}/{self.Prospectus_Table}/{record_id}",
			"Condition": condition,
			"Status": status,
			"Timestamp": datetime.now().isoformat()
		}
		self.update_log.append(update_entry)
		
		# Write the entire updated log to file immediately
		if self.log_filename:
			try:
				with open(self.log_filename, "w") as f:
					json.dump(self.update_log, f, indent=4)
			except Exception as e:
				print(f"⚠️ Error writing to log file: {e}")
		
		print(f"📝 LOGGED UPDATE: {company_name} - {condition}")

	def save_update_log(self):
		"""
		Save the final update log summary
		"""
		if self.update_log:
			print(f"💾 Update log saved to: {self.log_filename}")
			print(f"📊 Total updates in log file: {len(self.update_log)}")
			
			# Show summary of this run
			initial_count = len(self.update_log) - len([u for u in self.update_log if u.get("Timestamp", "").startswith(datetime.now().strftime("%Y-%m-%d"))])
			this_run_count = len(self.update_log) - initial_count
			
			print(f"📈 This run added: {this_run_count} new entries")
			print(f"📊 Total entries in log file: {len(self.update_log)}")
			
			# Show overall summary
			success_count = len([u for u in self.update_log if u["Status"] == "Success"])
			error_count = len([u for u in self.update_log if u["Status"] != "Success"])
			print(f"✅ Total successful updates: {success_count}")
			print(f"❌ Total failed updates: {error_count}")

	def navigate_to_section(self, driver, company_id, section_name):
		"""
		Navigate to a specific section using the navigation bar instead of direct URLs
		"""
		print(f"    🧭 navigate_to_section: Navigating to {section_name} section")
		
		# Check current URL to see if we're already on the right company page
		current_url = driver.current_url
		if not current_url.startswith(f"https://www.linkedin.com/company/{company_id}"):
			# Only navigate to main company page if we're not already there
			main_url = f"https://www.linkedin.com/company/{company_id}/"
			driver.get(main_url)
			time.sleep(3)
			
			# Check if we're on a valid company page
			current_url = driver.current_url
			if "unavailable" in current_url:
				print(f"    ❌ navigate_to_section: Company page unavailable")
				return False, "unavailable"
			elif "showcase" in current_url:
				print(f"    ⚠️ navigate_to_section: Showcase page detected")
				return False, "showcase"
		else:
			print(f"    ℹ️ navigate_to_section: Already on company page, checking current section")
		
		try:
			# Wait for navigation bar to load
			WebDriverWait(driver, 10).until(
				EC.presence_of_element_located((By.CLASS_NAME, "org-page-navigation"))
			)
			
			# Find the navigation item for the requested section
			nav_items = driver.find_elements(By.CLASS_NAME, "org-page-navigation__item-anchor")
			
			section_found = False
			for nav_item in nav_items:
				nav_text = nav_item.text.strip().lower()
				nav_href = nav_item.get_attribute("href")
				
				if section_name.lower() in nav_text or section_name.lower() in nav_href:
					print(f"    ✅ navigate_to_section: Found {section_name} navigation item")
					nav_item.click()
					time.sleep(3)
					section_found = True
					break
			
			if not section_found:
				print(f"    ❌ navigate_to_section: {section_name} section not found in navigation")
				return False, "section_not_found"
			
			# Verify we're on the correct page
			current_url = driver.current_url
			print(f"    📍 navigate_to_section: Current URL after navigation: {current_url}")
			
			return True, current_url
			
		except Exception as e:
			print(f"    ❌ navigate_to_section: Error navigating to {section_name}: {e}")
			return False, str(e)

	def update_crm(self,json_update_data,record_data):
		json_update_data = json.dumps(json_update_data)
		r = requests.patch("https://api.airtable.com/v0/"+self.INPUT_BASE_ID+"/"+self.Prospectus_Table+"/"+ record_data,data = json_update_data, headers=self.Post_Header)
		return r.text,r.status_code

	def getInputCompanyTable(self):
		# Check if JSON file already exists
		if os.path.exists("companies_to_scrape.json"):
			print("✅ JSON file already exists. Loading companies from companies_to_scrape.json")
			with open("companies_to_scrape.json", "r") as f:
				self.AllRecordIds = json.load(f)
			print(f"📊 Loaded {len(self.AllRecordIds)} companies from JSON file")
			return

		processed_count = 0
		offset = ''
		serial_number = 0
		all_companies_data = []
		
		print("🔍 SEARCHING COMPANIES IN PROSPECTS TABLE:")
		print("=" * 60)
		print(f"📋 Table: {self.Prospectus_Table}")
		print(f"🔗 Base ID: {self.INPUT_BASE_ID}")
		print(f"👁️ View: {self.VIEW_NAME}")
		print("=" * 60)
		
		while 1:
			CompanyTableURL = 'https://api.airtable.com/v0/'+self.INPUT_BASE_ID +'/'+ self.Prospectus_Table
			if len(self.VIEW_NAME) > 1:
				OutputTable = requests.get(CompanyTableURL, headers=self.headers,params={'offset': offset,'view':self.VIEW_NAME}).json()
			else:
				OutputTable = requests.get(CompanyTableURL, headers=self.headers,params={'offset': offset}).json()
			for Records in OutputTable["records"]:
				serial_number += 1
				
				for recordsKey,recordsValue in Records.items():
					if recordsKey == "fields":
						SingleRecord = {}
						CityCountry = []
						try:
							company_name = recordsValue["Company Name"]
							SingleRecord["Company"] = company_name
						except:
							continue

						# Initialize company data for CSV
						company_data = {
							"Serial_Number": serial_number,
							"Company_Name": company_name,
							"Record_ID": recordsValue.get("Record ID", ""),
							"LinkedIn_ID": "N/A",
							"Status": "Not Found",
							"Reason": "",
							"Website": "N/A",
							"HQ_Scrape": "",
							"US_Scrape": "",
							"Other_US_Cities": "",
							"Countries_to_Scrape": "",
							"Airtable_URL": f"https://airtable.com/{self.INPUT_BASE_ID}/{self.Prospectus_Table}/{Records.get('id', '')}"
						}

						try:
							linked_record_ids = recordsValue.get("Link to Company", [])
							print(f"#{serial_number:3d} 🔍 {company_name}")
							print(f"    🔗 linked_record_ids: {linked_record_ids}")
							
							if linked_record_ids:
								linked_record_id = linked_record_ids[0] 
								linked_url = f'https://api.airtable.com/v0/{self.INPUT_BASE_ID}/{self.Prospectus_Table}/{linked_record_id}'
								linked_record_response = requests.get(linked_url, headers=self.headers).json()
								linked_fields = linked_record_response.get("fields", {})
								
								website = linked_fields.get("Website", "N/A")
								linkedin_id = linked_fields.get("LinkedIn ID", "N/A")
								
								# Update company data
								company_data["Website"] = website
								company_data["LinkedIn_ID"] = linkedin_id
								
								print(f"    🔗 LinkedIn ID: {linkedin_id}")
								
								# From Prospects table
								record_id = recordsValue.get("Record ID", "")
								SingleRecord["RecordIDToUpdate"] = record_id
								print(f"    🔗 Record ID to Update: {record_id}")
								
								# Check if LinkedIn ID is valid
								if linkedin_id != "N/A":
									try:
										int(linkedin_id)
										SingleRecord["CompanyId"] = linkedin_id
										company_data["Status"] = "Found"
										print(f"    ✅ FOUND - LinkedIn ID: {linkedin_id}")
									except:
										company_data["Status"] = "Not Found"
										company_data["Reason"] = "LinkedIn ID not numeric"
										print(f"    ❌ NOT FOUND - LinkedIn ID not numeric: {linkedin_id}")
										all_companies_data.append(company_data)
										continue
								else:
									company_data["Status"] = "Not Found"
									company_data["Reason"] = "LinkedIn ID is N/A"
									print(f"    ❌ NOT FOUND - LinkedIn ID is N/A")
									all_companies_data.append(company_data)
									continue
							else:
								company_data["Status"] = "Not Found"
								company_data["Reason"] = "No Link to Company"
								print(f"    ❌ NOT FOUND - No Link to Company")
								all_companies_data.append(company_data)
								continue
						except Exception as e:
							company_data["Status"] = "Error"
							company_data["Reason"] = f"Error: {str(e)}"
							print(f"    ❌ ERROR fetching linked company details: {e}")
							all_companies_data.append(company_data)
							continue

						# Add location data to CSV
						try:
							hq_scrape = recordsValue.get('HQ Scrape', [])
							company_data["HQ_Scrape"] = "; ".join(hq_scrape) if hq_scrape else ""
						except:
							pass
						try:
							us_scrape = recordsValue.get('US Scrape', [])
							company_data["US_Scrape"] = "; ".join(us_scrape) if us_scrape else ""
						except:
							pass
						try:
							other_us = recordsValue.get('Other US Cities To Scrape', [])
							company_data["Other_US_Cities"] = "; ".join(other_us) if other_us else ""
						except:
							pass
						try:
							countries = recordsValue.get('Countries to Scape', [])
							company_data["Countries_to_Scrape"] = "; ".join(countries) if countries else ""
						except:
							pass

						print(f"    📊 {company_name} [{SingleRecord.get('CompanyId', 'N/A')}]")

						try:
							for citytoScrap in recordsValue['HQ Scrape']:
								CityCountry.append(citytoScrap+";HQ EEs")
						except:
							()
						try:
							for citytoScrap in recordsValue['US Scrape']:
								CityCountry.append(citytoScrap+";US EEs")
						except:
							()
						try:
							for citytoScrap in recordsValue['Other US Cities To Scrape']:
								CityCountry.append(citytoScrap+";Other US Cities")
						except:
							()
						try:
							for citytoScrap in recordsValue['Countries to Scape']:
								CityCountry.append(citytoScrap+";Other Countries")
						except:
							()
						SingleRecord["CityCountryToScrap"] = CityCountry
						self.AllRecordIds.append(SingleRecord)
						all_companies_data.append(company_data)
						processed_count += 1

						if processed_count >= 10:
							print(f"\n✅ Processed first 10 companies only.")
							break
			try:
				nextOffset = OutputTable["offset"]
				offset = nextOffset
			except:
				break

		# Save to JSON file
		with open("companies_to_scrape.json", "w") as f:
			json.dump(self.AllRecordIds, f, indent=4)
		print(f"💾 Saved {len(self.AllRecordIds)} companies to companies_to_scrape.json")

		# Generate CSV file
		if all_companies_data:
			df = pd.DataFrame(all_companies_data)
			df.to_csv("companies_data.csv", index=False)
			print(f"📊 Generated companies_data.csv with {len(all_companies_data)} companies")
			
			# Show summary
			found_count = len([c for c in all_companies_data if c["Status"] == "Found"])
			not_found_count = len([c for c in all_companies_data if c["Status"] == "Not Found"])
			error_count = len([c for c in all_companies_data if c["Status"] == "Error"])
			
			print(f"\n📈 SUMMARY:")
			print(f"✅ Found: {found_count}")
			print(f"❌ Not Found: {not_found_count}")
			print(f"⚠️ Errors: {error_count}")
			print(f"📁 Files generated:")
			print(f"   - companies_to_scrape.json (for scraping)")
			print(f"   - companies_data.csv (for review)")

		print(f"✅ Total companies processed: {len(self.AllRecordIds)}")
		print("Summary of companies:")
		for record in self.AllRecordIds:
			print(f"  - {record.get('Company')} (LinkedIn ID: {record.get('CompanyId')})")

	def GeoLocationIds(self):
		if all(os.path.exists(f) for f in ["all_locations.json", "countries.json", "usa_cities.json"]):
			print("✅ JSON files already exist. Skipping GeoLocationIds scraping.")
			return

		offset = ""
		all_locations = {}
		countries = {}
		usa_cities = {}

		while True:
			geoTableUrl = f'https://api.airtable.com/v0/{self.INPUT_BASE_ID}/{self.GeoCitiesTable}'
			response = requests.get(geoTableUrl, headers=self.headers, params={'offset': offset})
			r = response.json()

			for record in r.get("records", []):
				fields = record.get("fields", {})
				name = fields.get("Name", "").replace("\n", "").strip()
				record_id = record.get("id", "").strip()
				location_key = f"{name}|{record_id}"

				geo_id = fields.get("geoUrn", "NULL").replace("\n", "").strip()
				if geo_id == "NULL":
					print("    " + f"{name} [Not Found]")
				else:
					print("    " + f"{name} [{geo_id}]")

				# Determine classification type
				is_country = bool(fields.get("Country"))
				is_us_city = bool(fields.get("US State") or fields.get("US Major Metro"))

				location_type = []
				if is_country:
					location_type.append("country")
				if is_us_city:
					location_type.append("us_city")

				entry = {
					"geo_id": geo_id,
					"type": ", ".join(location_type) if location_type else "city"
				}

				# Add to main and filtered dictionaries
				all_locations[location_key] = entry
				if is_country:
					countries[location_key] = entry
				if is_us_city:
					usa_cities[location_key] = entry

			offset = r.get("offset", "")
			if not offset:
				break

		# Save to JSON files
		with open("all_locations.json", "w") as f:
			json.dump(all_locations, f, indent=4)
		with open("countries.json", "w") as f:
			json.dump(countries, f, indent=4)
		with open("usa_cities.json", "w") as f:
			json.dump(usa_cities, f, indent=4)

		print("✅ Saved JSON files: all_locations.json, countries.json, usa_cities.json")


	def Get_ChromeDriver(self):
		chrome_options = webdriver.ChromeOptions()
		chrome_options.add_argument("--start-maximized")
		chrome_options.add_argument("--no-sandbox")
		chrome_options.add_argument('--log-level=3')
		chrome_options.add_argument("--disable-notifications")
		chrome_options.add_argument('--ignore-certificate-errors-spki-list')
		chrome_options.add_argument('--ignore-ssl-errors')
		chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
		chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
		chrome_options.add_experimental_option('useAutomationExtension', False)

		prefs = {
					"credentials_enable_service": False,
					"profile.password_manager_enabled": False ,
					"profile.default_content_setting_values.geolocation": 2,
				}
		chrome_options.add_experimental_option("prefs", prefs)
		
		driver = webdriver.Chrome(options=chrome_options)
		return driver



	def Login_LinkedIn(self,driver):
		print("🔐 Loading LinkedIn cookies...")
		
		# Find the most recent cookie file
		cookie_files = [f for f in os.listdir('.') if f.startswith('linkedin_cookies_Mhuzaifasaeed_') and f.endswith('.json')]
		
		if not cookie_files:
			print("❌ No cookie files found. Please run save_cookies.py first to create a cookie file.")
			print("📝 Falling back to manual login...")
			driver.get("https://www.linkedin.com/feed/")
			time.sleep(120)
			WebDriverWait(driver, 10).until(EC.url_contains("feed"))
			print("Manual login successful, consider updating cookies.")
			return driver
		
		# Use the most recent cookie file
		latest_cookie_file = max(cookie_files, key=os.path.getctime)
		print(f"🍪 Using cookie file: {latest_cookie_file}")
		
		try:
			# Load cookies from file
			with open(latest_cookie_file, 'r') as f:
				cookies = json.load(f)
			
			# Navigate to LinkedIn first (cookies can only be added when on the domain)
			driver.get("https://www.linkedin.com")
			time.sleep(2)
			
			# Add all cookies
			for cookie in cookies:
				try:
					driver.add_cookie(cookie)
				except Exception as e:
					print(f"⚠️ Could not add cookie {cookie.get('name', 'unknown')}: {e}")
			
			print(f"✅ Added {len(cookies)} cookies")
			
			# Navigate to feed to verify login
			driver.get("https://www.linkedin.com/feed/")
			time.sleep(3)
			
			# Check if login was successful
			current_url = driver.current_url
			if "feed" in current_url or "mynetwork" in current_url or "messaging" in current_url:
				print("✅ Cookie login successful!")
				return driver
			else:
				print("❌ Cookie login failed, falling back to manual login...")
				driver.get("https://www.linkedin.com/feed/")
				time.sleep(120)
				WebDriverWait(driver, 10).until(EC.url_contains("feed"))
				print("Manual login successful, consider updating cookies.")
				return driver
				
		except Exception as e:
			print(f"❌ Error loading cookies: {e}")
			print("📝 Falling back to manual login...")
			driver.get("https://www.linkedin.com/feed/")
			time.sleep(120)
			WebDriverWait(driver, 10).until(EC.url_contains("feed"))
			print("Manual login successful, consider updating cookies.")
			return driver



	

	def convalue(self,val):
		if 'k' in val.lower():
			return int(float(val.lower().replace('k', '')) * 1_000)
		elif 'm' in val.lower():
			return int(float(val.lower().replace('m', '')) * 1_000_000)
		else:
			if val.isdigit():
				return int(val)
			else:
				return 0
	def scrapData(self,driver):
		print(f"Total companies to scrape: {len(self.AllRecordIds)}")
		print("Companies to scrape:")
		for i, record in enumerate(self.AllRecordIds, 1):
			print(f"  {i}. {record.get('Company')} [{record.get('CompanyId')}] - Record ID: {record.get('RecordIDToUpdate')}")

		for Records in self.AllRecordIds:
			print(f"\n{'='*60}")
			print(f"🔍 PROCESSING: {Records.get('Company')} [{Records.get('CompanyId')}]")
			print(f"{'='*60}")

			this_CompanyId = str(Records["CompanyId"]).replace('"','')
			this_CompanyName = str(Records["Company"]).replace('"','')

			# Show the LinkedIn URL being accessed
			linkedin_jobs_url = f"https://www.linkedin.com/company/{this_CompanyId}/jobs/"
			print(f"🌐 Accessing LinkedIn Jobs URL: {linkedin_jobs_url}")
			
			driver.get(linkedin_jobs_url)
			print(f"📍 Current URL after navigation: {driver.current_url}")
			
			# Check if we were redirected to a showcase page or unavailable page
			current_url = driver.current_url
			if "showcase" in current_url:
				print("⚠️ Redirected to showcase page - will try to scrape available data")
			elif "unavailable" in current_url:
				print("❌ LinkedIn page is unavailable - will mark as unavailable")
			else:
				print("✅ Standard company page loaded")
			
			# Try to find jobs section, but don't fail if not found
			jobs_section_found = False
			try:
				WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "search-results-container")))
				print("✅ Jobs page loaded successfully")
				jobs_section_found = True
			except:
				print("⚠️ Jobs section not found - will continue with available data")

			TotalResults = "0"

			TotalEEs = 0
			USEEs = 0
			HQEEs = 0
			OtherUSCities = ""
			OtherCountries = ""

			TotalEEs = int(TotalResults)
			print("🔧 Calling scrapOpenJobPage function...")
			driver,openJobCount,linkedinURL,companyDetailsfromFunction = self.scrapOpenJobPage(driver,this_CompanyId)
			openJobCount = int(openJobCount)

			# Check if LinkedIn page is unavailable
			if companyDetailsfromFunction.get("linkedinAvailable") == "unavailable":
				print("🚫 CONDITION 1: LinkedIn page is completely unavailable")
				print(" "*3, "LinkedIn page unavailable - updating only LinkedIn Profile field")
				
				# Use the stored Record ID instead of searching by company name
				RecordIDToUpdateData = Records.get("RecordIDToUpdate")
				if RecordIDToUpdateData:
					print("🚀 ~ RecordIDToUpdateData: ============ ", RecordIDToUpdateData)
				else:
					print(" "*5,"["+str(this_CompanyId)+"]-->Record ID not found")
					continue

				# Only update LinkedIn Profile field when unavailable
				crm_update_data = {
					"fields": {
						"LinkedIn Profile": "unavailable"
					}
				}
				print("📤 Updating Airtable with 'unavailable' status...")
				update_result = self.update_crm(crm_update_data,record_data=RecordIDToUpdateData)
				print(update_result)
				
				# Log the update
				self.log_update(
					company_name=this_CompanyName,
					linkedin_id=this_CompanyId,
					record_id=RecordIDToUpdateData,
					condition="Condition 1: LinkedIn page completely unavailable"
				)
				continue

			# Check for missing sections (only if LinkedIn page is available)
			missing_sections = companyDetailsfromFunction.get("missingSections", [])
			print(f"🔍 Missing sections detected: {missing_sections}")
			
			# Only try to scrape people section if it's not already marked as missing
			people_section_available = True
			if "people" not in missing_sections:
				print("🔧 Calling scrape_location_ee_counts function...")
				ee_counts, total_number, people_section_available = self.scrape_location_ee_counts(driver, this_CompanyId)
				
				if not people_section_available:
					missing_sections.append("people")
					print("❌ People section is not available")
				else:
					print("✅ People section is available")
			else:
				print("ℹ️ People section already marked as missing, skipping scrape_location_ee_counts")
				ee_counts, total_number = None, None
			
			print(" "*3,"Open Jobs: ",openJobCount)
			print(" "*3,"Followers: ",companyDetailsfromFunction["Followers"])
			print(" "*3,"Website: ",companyDetailsfromFunction["companyWebsite"])
			print(" "*3,"Department: ",companyDetailsfromFunction["Department"])

			print("🚀 ~ ee_counts:================", ee_counts)
			print("🚀 ~ total_number:================", total_number)
			
			print("📌 CityCountryToScrap:", Records["CityCountryToScrap"])

			# Prepare LinkedIn Profile field value
			linkedin_profile_value = "available"
			if missing_sections:
				linkedin_profile_value = "unavailable(" + ", ".join(missing_sections) + ")"
				print("🚫 CONDITION 2: LinkedIn page available but some sections are missing")
				print(" "*3, f"Missing sections: {missing_sections}")
			else:
				print("✅ CONDITION 3: LinkedIn page fully available - all sections accessible")

			# Initialize variables for employee counts
			HQEEs = 0
			USEEs = 0
			OtherUSCities = ""
			OtherCountries = ""
			total_ees_scraped = 0

			# Only process employee data if people section is available
			if people_section_available and ee_counts and total_number:
				print("🔧 Processing employee data...")
				categorized = self.categorize_employee_counts(ee_counts, total_number, Records.get("CityCountryToScrap", []))
				print("🚀 ~ categorized: =============", categorized)

				HQEEs = categorized.get("HQ EEs (Scraped)", 0)
				print("🚀 ~ HQEEs:", HQEEs)
				USEEs = categorized.get("US EEs (Scraped)", 0)
				print("🚀 ~ USEEs:", USEEs)
				OtherUSCities = categorized.get("Other US Cities (Scraped)", "")
				print("🚀 ~ OtherUSCities:", OtherUSCities)
				OtherCountries = categorized.get("Other Countries (Scraped)", "")
				print("🚀 ~ OtherCountries:", OtherCountries)
				total_ees_scraped = int(total_number)
			else:
				print(" "*3, "Skipping employee data processing due to missing people section")

			# Use the stored Record ID instead of searching by company name
			RecordIDToUpdateData = Records.get("RecordIDToUpdate")
			if RecordIDToUpdateData:
				print("🚀 ~ RecordIDToUpdateData: ============ ", RecordIDToUpdateData)
			else:
				print(" "*5,"["+str(this_CompanyId)+"]-->Record ID not found")
				continue

			# Build CRM update data with all available information
			crm_update_data = {
				"fields": {
					"LinkedIn Profile": linkedin_profile_value,
					"Open Jobs (Scraped)": openJobCount,
					"LinkedIn Description (Scraped)": companyDetailsfromFunction["Short Description"],
					"Industry (Scraped)": companyDetailsfromFunction["Department"],
					"LinkedIn Followers (Scraped)": self.convalue(companyDetailsfromFunction["Followers"]),
					"Year Founded (Scraped)": int(companyDetailsfromFunction["yearFounded"])
				}
			}

			# Add job details if available
			if companyDetailsfromFunction.get("jobAboutText"):
				crm_update_data["fields"]["Job About Text"] = companyDetailsfromFunction["jobAboutText"]
				print(" "*3,"Job About Text: Added to update")

			# Add employee data only if available
			if people_section_available and total_ees_scraped > 0:
				crm_update_data["fields"]["Total EEs (Scraped)"] = total_ees_scraped
				crm_update_data["fields"]["US EEs (Scraped)"] = USEEs
				crm_update_data["fields"]["HQ EEs (Scraped)"] = HQEEs
				crm_update_data["fields"]["Other US Cities (Scraped)"] = OtherUSCities.strip().strip(',').strip()
				crm_update_data["fields"]["Other Countries (Scraped)"] = OtherCountries.strip().strip(',').strip()
				
				# Add link fields for location records
				if categorized.get("HQ Scrape"):
					crm_update_data["fields"]["HQ Scrape"] = categorized["HQ Scrape"]
					print(" "*3,"HQ Scrape: Added to update")
				if categorized.get("Other US Cities To Scrape"):
					crm_update_data["fields"]["Other US Cities To Scrape"] = categorized["Other US Cities To Scrape"]
					print(" "*3,"Other US Cities To Scrape: Added to update")
				if categorized.get("Countries to Scape"):
					crm_update_data["fields"]["Countries to Scape"] = categorized["Countries to Scape"]
					print(" "*3,"Countries to Scape: Added to update")

			print("📤 Updating Airtable with scraped data...")
			update_result = self.update_crm(crm_update_data,record_data=RecordIDToUpdateData)
			print(update_result)
			
			# Log the update based on condition
			if missing_sections:
				condition_desc = f"Condition 2: LinkedIn page available but missing sections ({', '.join(missing_sections)})"
			else:
				condition_desc = "Condition 3: LinkedIn page fully available - all sections accessible"
			
			self.log_update(
				company_name=this_CompanyName,
				linkedin_id=this_CompanyId,
				record_id=RecordIDToUpdateData,
				condition=condition_desc
			)
		return driver

	def scrape_job_details(self, driver, company_id):
		"""
		Scrapes job details from the first available job opening
		"""
		print(f"  🔧 scrape_job_details: Starting job details scraping for company {company_id}")
		
		try:
			# Navigate to Jobs section
			jobs_success, jobs_result = self.navigate_to_section(driver, company_id, "Jobs")
			if not jobs_success:
				print(f"  ❌ scrape_job_details: Could not navigate to Jobs section: {jobs_result}")
				return ""
			
			# Wait for job listings to load
			print("  🔧 scrape_job_details: Waiting for job listings to load...")
			time.sleep(5)  # Give more time for carousel to load
			
			# Try different selectors for job listings in carousel structure
			job_listings = []
			selectors_to_try = [
				"artdeco-carousel__item",  # Carousel items
				"job-card-container",      # Job card containers
				"job-card-square__link",   # Job card links
				"jobs-search__results-list",
				"jobs-search-results__list",
				"jobs-search-results-list",
				"job-search-results__list",
				"job-search-results-list"
			]
			
			for selector in selectors_to_try:
				try:
					job_listings = driver.find_elements(By.CLASS_NAME, selector)
					if job_listings:
						print(f"  ✅ scrape_job_details: Found {len(job_listings)} job listings using selector: {selector}")
						break
				except:
					continue
			
			if not job_listings:
				# Try finding by job cards or job items with CSS selectors
				try:
					job_listings = driver.find_elements(By.CSS_SELECTOR, "[data-job-id]")
					if job_listings:
						print(f"  ✅ scrape_job_details: Found {len(job_listings)} job listings using data-job-id selector")
				except:
					pass
			
			if not job_listings:
				# Try finding job card links specifically
				try:
					job_listings = driver.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/search/']")
					if job_listings:
						print(f"  ✅ scrape_job_details: Found {len(job_listings)} job links using href selector")
				except:
					pass
			
			if not job_listings:
				print("  ❌ scrape_job_details: No job listings found")
				return ""
			
			# Get the first job listing
			first_job = job_listings[0]
			print("  ✅ scrape_job_details: Found first job listing")
			
			# Get the job URL before clicking
			job_url = None
			try:
				
				job_link = first_job.find_element(By.CLASS_NAME, "job-card-square__main")
				job_url = job_link.get_attribute("href")
				
				
				if job_url:
					print(f"  🔗 scrape_job_details: Job URL: {job_url}")
					# Navigate directly to the job URL
					driver.get(job_url)
					time.sleep(5)  # Wait for job details page to load
				else:
					# Fallback to clicking
					print("  🔧 scrape_job_details: Clicking on first job...")
					first_job.click()
					time.sleep(5)
			except Exception as e:
				print(f"  ⚠️ scrape_job_details: Error getting job URL, trying click: {e}")
				first_job.click()
				time.sleep(5)
			
			# Wait for job details to load - try multiple selectors
			print("  🔧 scrape_job_details: Waiting for job details to load...")
			job_details_elem = None
			
			detail_selectors = [
				"jobs-box__html-content",
				"jobs-description-content__text",
				"jobs-description__content",
				"job-description__content",
				"job-description-content__text",
				"jobs-description-content__text--stretch"
			]
			
			for selector in detail_selectors:
				try:
					job_details_elem = WebDriverWait(driver, 5).until(
						EC.presence_of_element_located((By.CLASS_NAME, selector))
					)
					print(f"  ✅ scrape_job_details: Found job details using selector: {selector}")
					break
				except:
					continue
			
			# If still not found, try by ID
			if not job_details_elem:
				try:
					job_details_elem = WebDriverWait(driver, 20).until(
						EC.presence_of_element_located((By.ID, "job-details"))
					)
					print("  ✅ scrape_job_details: Found job details using ID: job-details")
				except:
					pass
			
			# If still not found, try by CSS selector with partial class match
			if not job_details_elem:
				try:
					job_details_elem = driver.find_element(By.CSS_SELECTOR, "[class*='jobs-box__html-content']")
					print("  ✅ scrape_job_details: Found job details using partial class match")
				except:
					pass
			
			# If still not found, try by CSS selector with jobs-description
			if not job_details_elem:
				try:
					job_details_elem = driver.find_element(By.CSS_SELECTOR, "[class*='jobs-description']")
					print("  ✅ scrape_job_details: Found job details using jobs-description partial match")
				except:
					pass
			
			if not job_details_elem:
				print("  ❌ scrape_job_details: Could not find job details element")
				print(f"  🔍 Current URL: {driver.current_url}")
				return ""
			
			# Extract job details text
			job_details_text = job_details_elem.text.strip()
			
			if job_details_text:
				# Truncate if too long (Airtable has limits)
				if len(job_details_text) > 100000:  # Airtable text field limit
					job_details_text = job_details_text[:100000] + "..."
				
				print(f"  ✅ scrape_job_details: Successfully scraped job details ({len(job_details_text)} characters)")
				print(f"  📝 Job details preview: {job_details_text[:200]}...")
				return job_details_text
			else:
				print("  ❌ scrape_job_details: No job details text found")
				return ""
				
		except Exception as e:
			print(f"  ❌ scrape_job_details: Error scraping job details: {e}")
			# Print current URL for debugging
			try:
				print(f"  🔍 Current URL: {driver.current_url}")
			except:
				pass
			return ""

	def scrapOpenJobPage(self,driver,this_CompanyId):
		companyDetails = {}
		companyDetails["Department"] = ""
		companyDetails["headQuarter"] = ""
		companyDetails["Followers"] = "0"
		companyDetails["Company Logo"] = ""
		companyDetails["Short Description"] = ""
		companyDetails["companyWebsite"] = ""
		companyDetails["yearFounded"] = "0"
		companyDetails["linkedinUrl"] = ""
		companyDetails["linkedinAvailable"] = ""
		companyDetails["missingSections"] = []
		companyDetails["jobAboutText"] = ""  # New field for job details

		print(f"  🌐 scrapOpenJobPage: Starting scraping for company {this_CompanyId}")
		
		# Navigate to main company page first
		main_success, main_result = self.navigate_to_section(driver, this_CompanyId, "Home")
		if not main_success:
			if main_result == "unavailable":
				companyDetails["linkedinAvailable"] = "unavailable"
				print("  🚫 scrapOpenJobPage: LinkedIn page is unavailable for this company.")
				return driver, "0", "", companyDetails
			elif main_result == "showcase":
				print("  ⚠️ scrapOpenJobPage: Showcase page detected - limited data available")
				companyDetails["missingSections"].append("jobs")
				companyDetails["missingSections"].append("people")
			else:
				print(f"  ❌ scrapOpenJobPage: Failed to access main page: {main_result}")
				return driver, "0", "", companyDetails

		companyDetails["linkedinUrl"] = driver.current_url

		# Try to navigate to Jobs section
		jobs_success, jobs_result = self.navigate_to_section(driver, this_CompanyId, "Jobs")
		if jobs_success:
			try:
				jobOpeningtag = WebDriverWait(driver, 5).until(
					EC.presence_of_element_located((By.CLASS_NAME, "org-jobs-job-search-form-module__headline"))
				).text
				jobOpeningCount = jobOpeningtag.split("has ")[1].split(" ")[0].replace(",","").strip()
				print(f"  ✅ scrapOpenJobPage: Jobs section found - {jobOpeningCount} jobs")
				
				# If jobs are available, scrape job details
				if int(jobOpeningCount) > 0:
					print("  🔧 scrapOpenJobPage: Jobs available, scraping job details...")
					job_details = self.scrape_job_details(driver, this_CompanyId)
					companyDetails["jobAboutText"] = job_details
				else:
					print("  ℹ️ scrapOpenJobPage: No jobs available, skipping job details")
					
			except:
				jobOpeningCount = "0"
				companyDetails["missingSections"].append("jobs")
				print("  ❌ scrapOpenJobPage: Jobs section not found")
		else:
			jobOpeningCount = "0"
			companyDetails["missingSections"].append("jobs")
			print("  ❌ scrapOpenJobPage: Could not navigate to Jobs section")

		# Navigate back to main page for company details
		main_success, _ = self.navigate_to_section(driver, this_CompanyId, "Home")
		if not main_success:
			print("  ⚠️ scrapOpenJobPage: Could not navigate back to main page")

		print("  🔧 scrapOpenJobPage: Trying to get company details section...")

		try:
			WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CLASS_NAME, "org-top-card-summary-info-list__info-item")))
			print("  ✅ scrapOpenJobPage: Company details section found")
		except:
			print("  ❌ scrapOpenJobPage: Company details section not found")
			return driver,jobOpeningCount,driver.current_url,companyDetails

		try:
			shortDescription = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'org-top-card-summary__tagline'))).text
			print(f"  ✅ scrapOpenJobPage: Short description found: {shortDescription[:50]}...")
		except:
			shortDescription = ""
			print("  ❌ scrapOpenJobPage: Short description not found")
		
		print("  🔧 scrapOpenJobPage: Trying to get company detail section...")

		# Try to get followers using the new HTML structure first
		followers_found = False
		try:
			# Look for the new followers structure
			followers_elem = WebDriverWait(driver, 5).until(
				EC.presence_of_element_located((By.CLASS_NAME, "update-components-actor__description"))
			)
			followers_text = followers_elem.text.strip()
			if "followers" in followers_text.lower():
				# Extract the number before "followers"
				import re
				followers_match = re.search(r'([\d,]+)\s*followers', followers_text, re.IGNORECASE)
				if followers_match:
					companyDetails["Followers"] = followers_match.group(1).replace(",", "")
					print(f"  ✅ scrapOpenJobPage: Followers found (new structure): {companyDetails['Followers']}")
					followers_found = True
		except Exception as e:
			print(f"  ℹ️ scrapOpenJobPage: New followers structure not found: {e}")

		# If new structure didn't work, try the old method
		if not followers_found:
			try:
				CompaDetaillist = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "org-top-card-summary-info-list__info-item")))
				tempCompa = {}
				for index,detail in enumerate(CompaDetaillist):
					tempCompa["Department"] = 0
					tempCompa["headQuarter"] = 1
					tempCompa["Followers"] = 2
					if "followers" in detail.text:
						companyDetails["Followers"] = detail.text.split(" followers")[0]
						print(f"  ✅ scrapOpenJobPage: Followers found (old structure): {companyDetails['Followers']}")
					if "employees" in detail.text:
						if companyDetails["Followers"] == "0" or companyDetails["Followers"] ==2:
							companyDetails[list(tempCompa.keys())[list(tempCompa.values()).index(index)]] = ""
					if "followers" not in detail.text and "employees" not in detail.text and index==0:
						companyDetails[list(tempCompa.keys())[list(tempCompa.values()).index(index)]] = detail.text.split(",")[0]
				print("  ✅ scrapOpenJobPage: Company details processed successfully")
			except Exception as e:
				print(f"  ❌ scrapOpenJobPage: Error when scraping company details: {e}")
		
		# Navigate to About section for additional details
		about_success, _ = self.navigate_to_section(driver, this_CompanyId, "About")
		if about_success:
			try:
				companyWebsite = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//dt[h3[text()="Website"]]'))).find_element(By.XPATH, 'following-sibling::dd[@class="mb4 t-black--light text-body-medium"]').text
				if "bit.ly" not in companyWebsite:
					companyWebsite = companyWebsite.split("?")[0].replace("//","|").split("/")[0].replace("|","//")
				print(f"  ✅ scrapOpenJobPage: Website found: {companyWebsite}")
			except Exception as e:
				print(f"  ❌ scrapOpenJobPage: Website not found: {e}")
				companyWebsite = ""
			try:
				companyLogoImageUrl = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'evi-image.lazy-image.ember-view.org-top-card-primary-content__logo'))).get_attribute("src")
				print(f"  ✅ scrapOpenJobPage: Company logo found")
			except:
				print("  ❌ scrapOpenJobPage: Company logo not found")
				companyLogoImageUrl = ""
			try:
				year_founded = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//dt[h3[text()="Founded"]]'))).find_element(By.XPATH, 'following-sibling::dd[@class="mb4 t-black--light text-body-medium"]').text.strip()
				print(f"  ✅ scrapOpenJobPage: Year founded found: {year_founded}")
			except Exception as e:
				print(f"  ❌ scrapOpenJobPage: Year founded not found: {e}")
				year_founded = "0"

			try:
				HQ = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//dt[h3[text()="Headquarters"]]'))).find_element(By.XPATH, 'following-sibling::dd[@class="mb4 t-black--light text-body-medium"]').text
				print(f"  ✅ scrapOpenJobPage: Headquarters found: {HQ}")
			except Exception as e:
				print(f"  ❌ scrapOpenJobPage: Headquarters not found: {e}")
				HQ = ""
		else:
			print("  ℹ️ scrapOpenJobPage: Could not navigate to About section")
			companyWebsite = ""
			companyLogoImageUrl = ""
			year_founded = "0"
			HQ = ""

		print(f"  📊 scrapOpenJobPage: Final data - Website: {companyWebsite}, Logo: {'Yes' if companyLogoImageUrl else 'No'}, Year: {year_founded}, HQ: {HQ}")
		print(f"  📝 Job About Text: {'Yes' if companyDetails['jobAboutText'] else 'No'}")
		companyDetails["Company Logo"] = companyLogoImageUrl
		companyDetails["Short Description"] = shortDescription
		companyDetails["companyWebsite"] = companyWebsite
		companyDetails["yearFounded"] = year_founded
		companyDetails["headQuarter"] = HQ

		return driver,jobOpeningCount,driver.current_url,companyDetails

	def scrape_location_ee_counts(self, driver, company_id):
		"""
		Scrapes the 'Where they live' section on LinkedIn's People tab and
		returns a dictionary {location_name: employee_count} with location details.
		Also gets total employee count.
		"""

		from selenium.webdriver.common.by import By
		from selenium.webdriver.support.ui import WebDriverWait
		from selenium.webdriver.support import expected_conditions as EC

		print(f"    🌐 scrape_location_ee_counts: Starting people scraping for company {company_id}")
		
		# Navigate to People section using navigation
		people_success, people_result = self.navigate_to_section(driver, company_id, "People")
		if not people_success:
			print(f"    ❌ scrape_location_ee_counts: Could not navigate to People section: {people_result}")
			return None, None, False

		ee_counts = {}  # Will store {location_name: {"count": count}}
		total_number = None
		people_section_available = True

		try:
			# Try to get total members text (e.g., "966 associated members")
			print("    🔧 scrape_location_ee_counts: Looking for total members count...")
			total_members_elem = WebDriverWait(driver, 10).until(
				EC.presence_of_element_located((By.CLASS_NAME, "org-people__header-spacing-carousel"))
			)
			text = total_members_elem.text.strip()
			if not text:
				print(f"    ❌ scrape_location_ee_counts: No total members text found for company {company_id}. People section may be unavailable.")
				people_section_available = False
				return None, None, people_section_available

			total_number = text.split()[0].replace(",", "")
			if not total_number.isdigit():
				print(f"    ❌ scrape_location_ee_counts: Total number is not a digit for company {company_id}. People section may be unavailable.")
				people_section_available = False
				return None, None, people_section_available

			print(f"    ✅ scrape_location_ee_counts: Total Members found: {total_number}")

			# Wait for the geo-region section
			print("    🔧 scrape_location_ee_counts: Looking for geo-region section...")
			geo_section = WebDriverWait(driver, 10).until(
				EC.presence_of_element_located((By.CLASS_NAME, "org-people-bar-graph-module__geo-region"))
			)
			print("    ✅ scrape_location_ee_counts: Geo-region section found")

			# Function to click "Show more" button
			def click_show_more():
				try:
					showmore_button = driver.find_element(By.CLASS_NAME, "org-people__show-more-button")
					if "Show more" in showmore_button.text:
						showmore_button.click()
						print("    ✅ Clicked 'Show more' button")
						time.sleep(2)
						return True
					else:
						print("    ℹ️ 'Show more' button already expanded")
						return True
				except Exception as e:
					print(f"    ℹ️ 'Show more' button not found or not clickable: {e}")
					return False

			# Click "Show more" to expand all locations
			click_show_more()

			# Calculate threshold (5% of total)
			threshold = max(1, int(total_number) * 0.05)
			print(f"    📊 Threshold for location filtering: {threshold} employees (5% of {total_number})")

			# Get all location buttons after expanding
			print("    🔧 scrape_location_ee_counts: Getting all location buttons...")
			buttons = geo_section.find_elements(By.CLASS_NAME, "org-people-bar-graph-element")
			print(f"    📊 Found {len(buttons)} location buttons")

			# Process each button (no clicking on individual locations needed)
			for i, btn in enumerate(buttons):
				try:
					# Get location info directly from the button
					count_elem = btn.find_element(By.TAG_NAME, "strong")
					location_elem = btn.find_element(By.CLASS_NAME, "org-people-bar-graph-element__category")

					count_text = count_elem.text.strip().replace(",", "")
					if not count_text:
						print(f"        ⚠️ Empty count for button {i+1}, skipping")
						continue
						
					count = int(count_text)
					location_name = location_elem.text.strip()
					
					if not location_name:
						print(f"        ⚠️ Empty location name for button {i+1}, skipping")
						continue
					
					# Skip if below threshold
					if count < threshold:
						print(f"        ⏭️ Skipping {location_name} ({count} employees) - below threshold")
						continue

					print(f"        ✅ Processing {location_name}: {count} employees")
					
					# Store the data using location name as key
					ee_counts[location_name] = {
						"count": count
					}
					print(f"        📍 Stored: {location_name} ({count})")

				except Exception as e:
					print(f"        ❌ Error processing button {i+1}: {e}")
					continue

			print(f"    ✅ scrape_location_ee_counts: Successfully extracted {len(ee_counts)} locations")

		except Exception as e:
			print(f"    ❌ scrape_location_ee_counts: Failed to scrape for company {company_id}: {e}")
			people_section_available = False
			return None, None, people_section_available

		return ee_counts, total_number, people_section_available

	def categorize_employee_counts(self, ee_counts, total_number, CityCountryToScrap=None): 
		print("🚀 ~ total_number: ============ ", total_number)
		"""
		Categorizes LinkedIn employee counts into Airtable fields by matching location names:
		HQ EEs, US EEs, Other US Cities, Other Countries.
		Also returns link fields for HQ Scrape, Other US Cities To Scrape, Countries to Scape.

		:param ee_counts: dict of {location_name: {"count": count}}
		:param total_number: total number of associated members (int)
		:param CityCountryToScrap: list like "recXXX123;HQ EEs" for HQ identification
		:return: dict with Airtable field keys and values
		"""

		# Load location data from all_locations.json
		with open("all_locations.json") as f:
			location_data = json.load(f)

		# Create mappings for name matching
		name_to_record_id = {}
		name_to_type = {}
		name_to_geo_id = {}
		
		for key, value in location_data.items():
			location_name, record_id = key.split('|')
			geo_id = value.get("geo_id")
			location_type = value.get("type", "")
			
			if geo_id and geo_id != "NULL":
				name_to_record_id[location_name] = record_id
				name_to_type[location_name] = location_type
				name_to_geo_id[location_name] = geo_id

		print("🔍 LOCATION MAPPING DEBUG:")
		print(f"📊 Total locations in all_locations.json: {len(location_data)}")
		print(f"📊 Name to record ID mappings: {len(name_to_record_id)}")
		
		# Show some example mappings
		example_mappings = list(name_to_record_id.items())[:3]
		for location_name, record_id in example_mappings:
			location_type = name_to_type.get(location_name, "N/A")
			geo_id = name_to_geo_id.get(location_name, "N/A")
			print(f"    {location_name} → {record_id} (type: {location_type}, geo_id: {geo_id})")

		# Initialize result containers
		hq_ee_count = 0
		us_ee_count = 0
		other_us_cities = []
		other_countries = []
		
		# Initialize link field containers
		hq_scrape_record_ids = []
		other_us_cities_record_ids = []
		countries_record_ids = []

		# Create HQ mapping from CityCountryToScrap
		hq_record_ids = set()
		if CityCountryToScrap:
			for entry in CityCountryToScrap:
				try:
					record_id, tag = entry.split(";")
					if tag.strip() == "HQ EEs":
						hq_record_ids.add(record_id.strip())
				except:
					continue

		print("🔍 PROCESSING LINKEDIN LOCATIONS:")
		print(f"🌍 LinkedIn scraped locations: {list(ee_counts.keys())}")
		print(f"🏢 HQ Record IDs from config: {list(hq_record_ids)}")

		# Process each LinkedIn scraped location
		for location_name, location_info in ee_counts.items():
			linkedin_count = location_info["count"]
			
			print(f"    🔍 Processing LinkedIn location: {location_name} - {linkedin_count} employees")
			
			# Try to find match in our location data with multiple strategies
			matched_record_id = None
			matched_type = None
			match_strategy = "none"
			
			# Strategy 1: Exact match
			if location_name in name_to_record_id:
				matched_record_id = name_to_record_id[location_name]
				matched_type = name_to_type[location_name]
				match_strategy = "exact"
				print(f"        ✅ EXACT MATCH: {location_name} → {matched_record_id} (type: {matched_type})")
			else:
				# Strategy 2: Remove common suffixes and try again
				location_name_clean = location_name.replace(", United States", "").replace(", US", "").strip()
				if location_name_clean in name_to_record_id:
					matched_record_id = name_to_record_id[location_name_clean]
					matched_type = name_to_type[location_name_clean]
					match_strategy = "suffix_removal"
					print(f"        ✅ SUFFIX REMOVAL MATCH: {location_name} → {location_name_clean} → {matched_record_id} (type: {matched_type})")
				else:
					# Strategy 3: Extract city name (before first comma) and try
					city_part = location_name.split(',')[0].strip()
					if city_part in name_to_record_id:
						matched_record_id = name_to_record_id[city_part]
						matched_type = name_to_type[city_part]
						match_strategy = "city_extraction"
						print(f"        ✅ CITY EXTRACTION MATCH: {location_name} → {city_part} → {matched_record_id} (type: {matched_type})")
					else:
						# Strategy 4: Try partial matching for metropolitan areas
						# Remove "Metropolitan Area", "Metro", etc.
						metro_clean = location_name.replace(" Metropolitan Area", "").replace(" Metro", "").replace(" Metropolitan", "").strip()
						if metro_clean in name_to_record_id:
							matched_record_id = name_to_record_id[metro_clean]
							matched_type = name_to_type[metro_clean]
							match_strategy = "metro_cleanup"
							print(f"        ✅ METRO CLEANUP MATCH: {location_name} → {metro_clean} → {matched_record_id} (type: {matched_type})")
						else:
							# Strategy 5: Try state name extraction for "State, United States" format
							if ", United States" in location_name:
								state_part = location_name.split(',')[0].strip()
								if state_part in name_to_record_id:
									matched_record_id = name_to_record_id[state_part]
									matched_type = name_to_type[state_part]
									match_strategy = "state_extraction"
									print(f"        ✅ STATE EXTRACTION MATCH: {location_name} → {state_part} → {matched_record_id} (type: {matched_type})")
								else:
									print(f"        ❌ NO MATCH: {location_name} not found in all_locations.json")
									continue
							else:
								print(f"        ❌ NO MATCH: {location_name} not found in all_locations.json")
								continue
			
			# Check if this is an HQ location first
			is_hq_location = matched_record_id in hq_record_ids
			
			# Categorize based on type and add to appropriate containers
			if is_hq_location:
				hq_ee_count += linkedin_count
				hq_scrape_record_ids.append(matched_record_id)
				print(f"        🏢 Added to HQ EEs: {linkedin_count}")
			elif location_name == "United States" or (match_strategy == "suffix_removal" and location_name_clean == "United States"):
				# Special case: United States should be counted as US EEs, not Other Countries
				us_ee_count += linkedin_count
				print(f"        🇺🇸 Added to US EEs (United States): {linkedin_count}")
			elif matched_type == "us_city":
				us_ee_count += linkedin_count
				# Extract just the city name (before comma)
				city_name = location_name.split(',')[0].strip()
				other_us_cities.append((city_name, linkedin_count))
				other_us_cities_record_ids.append(matched_record_id)
				print(f"        📍 Added to US EEs: {linkedin_count}")
				print(f"        📍 Added to Other US Cities: {city_name} ({linkedin_count})")
			elif matched_type == "country":
				# Skip United States from Other Countries
				if location_name == "United States" or (match_strategy == "suffix_removal" and location_name_clean == "United States"):
					us_ee_count += linkedin_count
					print(f"        🇺🇸 Added to US EEs (United States country): {linkedin_count}")
				else:
					other_countries.append((location_name, linkedin_count))
					countries_record_ids.append(matched_record_id)
					print(f"        📍 Added to Other Countries: {location_name} ({linkedin_count})")
			elif matched_type == "city":
				# For regular cities, we need to determine if it's HQ or other
				# For now, we'll add to other countries unless it's a major US city
				if "United States" in location_name or any(state in location_name for state in ["CA", "TX", "NY", "FL", "WA", "IL", "PA", "OH", "GA", "NC", "MI", "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "CO", "OR", "WI", "MN", "SC", "AL", "LA", "KY", "UT", "IA", "NV", "AR", "MS", "CT", "KS", "NE", "ID", "HI", "NH", "ME", "RI", "MT", "DE", "SD", "ND", "AK", "DC", "VT", "WY", "WV"]):
					us_ee_count += linkedin_count
					# Extract just the city name (before comma)
					city_name = location_name.split(',')[0].strip()
					other_us_cities.append((city_name, linkedin_count))
					other_us_cities_record_ids.append(matched_record_id)
					print(f"        📍 Added to US EEs (city): {linkedin_count}")
				else:
					other_countries.append((location_name, linkedin_count))
					countries_record_ids.append(matched_record_id)
					print(f"        📍 Added to Other Countries (city): {linkedin_count}")

		# Sort cities and countries by count (descending) and format
		other_us_cities_sorted = sorted(other_us_cities, key=lambda x: x[1], reverse=True)
		other_countries_sorted = sorted(other_countries, key=lambda x: x[1], reverse=True)
		
		other_us_cities_formatted = [f"{name} ({count})" for name, count in other_us_cities_sorted]
		other_countries_formatted = [f"{name} ({count})" for name, count in other_countries_sorted]

		# Remove duplicates from record ID lists
		hq_scrape_record_ids = list(set(hq_scrape_record_ids))
		other_us_cities_record_ids = list(set(other_us_cities_record_ids))
		countries_record_ids = list(set(countries_record_ids))

		print("📊 CATEGORIZATION RESULTS:")
		print(f"    HQ EEs: {hq_ee_count}")
		print(f"    US EEs: {us_ee_count}")
		print(f"    Other US Cities: {other_us_cities_formatted}")
		print(f"    Other Countries: {other_countries_formatted}")
		print(f"    Other US Cities Record IDs: {other_us_cities_record_ids}")
		print(f"    Countries Record IDs: {countries_record_ids}")

		return {
			"HQ EEs (Scraped)": hq_ee_count,
			"US EEs (Scraped)": us_ee_count,
			"Other US Cities (Scraped)": ', '.join(other_us_cities_formatted),
			"Other Countries (Scraped)": ', '.join(other_countries_formatted),
			"HQ Scrape": hq_scrape_record_ids,
			"Other US Cities To Scrape": other_us_cities_record_ids,
			"Countries to Scape": countries_record_ids
		}

	def generateCompanyDataFiles(self):
		"""
		Generate CSV and JSON files with company data before scraping
		"""
		# Check if JSON file already exists
		if os.path.exists("companies_to_scrape.json"):
			print("✅ JSON file already exists. Loading companies from companies_to_scrape.json")
			with open("companies_to_scrape.json", "r") as f:
				self.AllRecordIds = json.load(f)
			print(f"📊 Loaded {len(self.AllRecordIds)} companies from JSON file")
			return

		processed_count = 0
		offset = ''
		serial_number = 0
		all_companies_data = []
		
		print("🔍 SEARCHING COMPANIES IN PROSPECTS TABLE:")
		print("=" * 60)
		print(f"📋 Table: {self.Prospectus_Table}")
		print(f"🔗 Base ID: {self.INPUT_BASE_ID}")
		print(f"👁️ View: {self.VIEW_NAME}")
		print("=" * 60)
		
		while 1:
			CompanyTableURL = 'https://api.airtable.com/v0/'+self.INPUT_BASE_ID +'/'+ self.Prospectus_Table
			if len(self.VIEW_NAME) > 1:
				OutputTable = requests.get(CompanyTableURL, headers=self.headers,params={'offset': offset,'view':self.VIEW_NAME}).json()
			else:
				OutputTable = requests.get(CompanyTableURL, headers=self.headers,params={'offset': offset}).json()
			for Records in OutputTable["records"]:
				serial_number += 1
				
				for recordsKey,recordsValue in Records.items():
					if recordsKey == "fields":
						SingleRecord = {}
						CityCountry = []
						try:
							company_name = recordsValue["Company Name"]
							SingleRecord["Company"] = company_name
						except:
							continue

						# Initialize company data for CSV
						company_data = {
							"Serial_Number": serial_number,
							"Company_Name": company_name,
							"Record_ID": recordsValue.get("Record ID", ""),
							"LinkedIn_ID": "N/A",
							"Status": "Not Found",
							"Reason": "",
							"Website": "N/A",
							"HQ_Scrape": "",
							"US_Scrape": "",
							"Other_US_Cities": "",
							"Countries_to_Scrape": "",
							"Airtable_URL": f"https://airtable.com/{self.INPUT_BASE_ID}/{self.Prospectus_Table}/{Records.get('id', '')}"
						}

						try:
							linked_record_ids = recordsValue.get("Link to Company", [])
							print(f"#{serial_number:3d} 🔍 {company_name}")
							print(f"    🔗 linked_record_ids: {linked_record_ids}")
							
							if linked_record_ids:
								linked_record_id = linked_record_ids[0] 
								linked_url = f'https://api.airtable.com/v0/{self.INPUT_BASE_ID}/{self.Prospectus_Table}/{linked_record_id}'
								linked_record_response = requests.get(linked_url, headers=self.headers).json()
								linked_fields = linked_record_response.get("fields", {})
								
								website = linked_fields.get("Website", "N/A")
								linkedin_id = linked_fields.get("LinkedIn ID", "N/A")
								
								# Update company data
								company_data["Website"] = website
								company_data["LinkedIn_ID"] = linkedin_id
								
								print(f"    🔗 LinkedIn ID: {linkedin_id}")
								
								# From Prospects table
								record_id = recordsValue.get("Record ID", "")
								SingleRecord["RecordIDToUpdate"] = record_id
								print(f"    🔗 Record ID to Update: {record_id}")
								
								# Check if LinkedIn ID is valid
								if linkedin_id != "N/A":
									try:
										int(linkedin_id)
										SingleRecord["CompanyId"] = linkedin_id
										company_data["Status"] = "Found"
										print(f"    ✅ FOUND - LinkedIn ID: {linkedin_id}")
									except:
										company_data["Status"] = "Not Found"
										company_data["Reason"] = "LinkedIn ID not numeric"
										print(f"    ❌ NOT FOUND - LinkedIn ID not numeric: {linkedin_id}")
										all_companies_data.append(company_data)
										continue
								else:
									company_data["Status"] = "Not Found"
									company_data["Reason"] = "LinkedIn ID is N/A"
									print(f"    ❌ NOT FOUND - LinkedIn ID is N/A")
									all_companies_data.append(company_data)
									continue
							else:
								company_data["Status"] = "Not Found"
								company_data["Reason"] = "No Link to Company"
								print(f"    ❌ NOT FOUND - No Link to Company")
								all_companies_data.append(company_data)
								continue
						except Exception as e:
							company_data["Status"] = "Error"
							company_data["Reason"] = f"Error: {str(e)}"
							print(f"    ❌ ERROR fetching linked company details: {e}")
							all_companies_data.append(company_data)
							continue

						# Add location data to CSV
						try:
							hq_scrape = recordsValue.get('HQ Scrape', [])
							company_data["HQ_Scrape"] = "; ".join(hq_scrape) if hq_scrape else ""
						except:
							pass
						try:
							us_scrape = recordsValue.get('US Scrape', [])
							company_data["US_Scrape"] = "; ".join(us_scrape) if us_scrape else ""
						except:
							pass
						try:
							other_us = recordsValue.get('Other US Cities To Scrape', [])
							company_data["Other_US_Cities"] = "; ".join(other_us) if other_us else ""
						except:
							pass
						try:
							countries = recordsValue.get('Countries to Scape', [])
							company_data["Countries_to_Scrape"] = "; ".join(countries) if countries else ""
						except:
							pass

						print(f"    📊 {company_name} [{SingleRecord.get('CompanyId', 'N/A')}]")

						try:
							for citytoScrap in recordsValue['HQ Scrape']:
								CityCountry.append(citytoScrap+";HQ EEs")
						except:
							()
						try:
							for citytoScrap in recordsValue['US Scrape']:
								CityCountry.append(citytoScrap+";US EEs")
						except:
							()
						try:
							for citytoScrap in recordsValue['Other US Cities To Scrape']:
								CityCountry.append(citytoScrap+";Other US Cities")
						except:
							()
						try:
							for citytoScrap in recordsValue['Countries to Scape']:
								CityCountry.append(citytoScrap+";Other Countries")
						except:
							()
						SingleRecord["CityCountryToScrap"] = CityCountry
						self.AllRecordIds.append(SingleRecord)
						all_companies_data.append(company_data)
						processed_count += 1

						if processed_count >= 10:
							print(f"\n✅ Processed first 10 companies only.")
							break
			try:
				nextOffset = OutputTable["offset"]
				offset = nextOffset
			except:
				break

		# Save to JSON file
		with open("companies_to_scrape.json", "w") as f:
			json.dump(self.AllRecordIds, f, indent=4)
		print(f"💾 Saved {len(self.AllRecordIds)} companies to companies_to_scrape.json")

		# Generate CSV file
		if all_companies_data:
			df = pd.DataFrame(all_companies_data)
			df.to_csv("companies_data.csv", index=False)
			print(f"📊 Generated companies_data.csv with {len(all_companies_data)} companies")
			
			# Show summary
			found_count = len([c for c in all_companies_data if c["Status"] == "Found"])
			not_found_count = len([c for c in all_companies_data if c["Status"] == "Not Found"])
			error_count = len([c for c in all_companies_data if c["Status"] == "Error"])
			
			print(f"\n📈 SUMMARY:")
			print(f"✅ Found: {found_count}")
			print(f"❌ Not Found: {not_found_count}")
			print(f"⚠️ Errors: {error_count}")
			print(f"📁 Files generated:")
			print(f"   - companies_to_scrape.json (for scraping)")
			print(f"   - companies_data.csv (for review)")

		print(f"✅ Total companies processed: {len(self.AllRecordIds)}")
		print("Summary of companies:")
		for record in self.AllRecordIds:
			print(f"  - {record.get('Company')} (LinkedIn ID: {record.get('CompanyId')})")

	def test_location_mapping(self):
		"""
		Test function to demonstrate how location mapping works with location names
		"""
		print("🧪 TESTING LOCATION MAPPING WITH LOCATION NAMES")
		print("=" * 60)
		
		# Load location data
		with open("all_locations.json") as f:
			location_data = json.load(f)

		# Create mappings for name matching
		name_to_record_id = {}
		name_to_type = {}
		name_to_geo_id = {}
		
		for key, value in location_data.items():
			location_name, record_id = key.split('|')
			geo_id = value.get("geo_id")
			location_type = value.get("type", "")
			
			if geo_id and geo_id != "NULL":
				name_to_record_id[location_name] = record_id
				name_to_type[location_name] = location_type
				name_to_geo_id[location_name] = geo_id

		# Simulate LinkedIn scraped data with location names (including the problematic ones from the debug output)
		simulated_ee_counts = {
			"United States": {"count": 5},
			"Tennessee, United States": {"count": 3},
			"Nashville, TN": {"count": 3},
			"Nashville Metropolitan Area": {"count": 3},
			"United Kingdom": {"count": 1},
			"Japan": {"count": 1},
			"Yamato": {"count": 1},
			"California, United States": {"count": 1},
			"England, United Kingdom": {"count": 1},
			"Redondo Beach, CA": {"count": 1},
			"India": {"count": 1},
			"New York, United States": {"count": 1},
			"Kanagawa, Japan": {"count": 1},
			"Maharashtra, India": {"count": 1},
			"Pune": {"count": 1}
		}

		print("🌍 SIMULATED LINKEDIN DATA WITH LOCATION NAMES:")
		for location_name, info in simulated_ee_counts.items():
			print(f"    {location_name}: {info['count']} employees")

		print("\n🔍 IMPROVED MATCHING PROCESS:")
		
		# Initialize result containers
		hq_ee_count = 0
		us_ee_count = 0
		other_us_cities = []
		other_countries = []
		
		# Initialize link field containers
		hq_scrape_record_ids = []
		other_us_cities_record_ids = []
		countries_record_ids = []

		# Simulate HQ configuration (Nashville is HQ)
		hq_record_ids = {"recyhZ4APMgCkKfJa"}  # Nashville record ID

		for location_name, info in simulated_ee_counts.items():
			linkedin_count = info["count"]
			
			print(f"\n    🔍 Processing LinkedIn location: {location_name} ({linkedin_count} employees)")
			
			# Try to find match in our location data with multiple strategies
			matched_record_id = None
			matched_type = None
			match_strategy = "none"
			
			# Strategy 1: Exact match
			if location_name in name_to_record_id:
				matched_record_id = name_to_record_id[location_name]
				matched_type = name_to_type[location_name]
				match_strategy = "exact"
				print(f"        ✅ EXACT MATCH: {location_name} → {matched_record_id} (type: {matched_type})")
			else:
				# Strategy 2: Remove common suffixes and try again
				location_name_clean = location_name.replace(", United States", "").replace(", US", "").strip()
				if location_name_clean in name_to_record_id:
					matched_record_id = name_to_record_id[location_name_clean]
					matched_type = name_to_type[location_name_clean]
					match_strategy = "suffix_removal"
					print(f"        ✅ SUFFIX REMOVAL MATCH: {location_name} → {location_name_clean} → {matched_record_id} (type: {matched_type})")
				else:
					# Strategy 3: Extract city name (before first comma) and try
					city_part = location_name.split(',')[0].strip()
					if city_part in name_to_record_id:
						matched_record_id = name_to_record_id[city_part]
						matched_type = name_to_type[city_part]
						match_strategy = "city_extraction"
						print(f"        ✅ CITY EXTRACTION MATCH: {location_name} → {city_part} → {matched_record_id} (type: {matched_type})")
					else:
						# Strategy 4: Try partial matching for metropolitan areas
						# Remove "Metropolitan Area", "Metro", etc.
						metro_clean = location_name.replace(" Metropolitan Area", "").replace(" Metro", "").replace(" Metropolitan", "").strip()
						if metro_clean in name_to_record_id:
							matched_record_id = name_to_record_id[metro_clean]
							matched_type = name_to_type[metro_clean]
							match_strategy = "metro_cleanup"
							print(f"        ✅ METRO CLEANUP MATCH: {location_name} → {metro_clean} → {matched_record_id} (type: {matched_type})")
						else:
							# Strategy 5: Try state name extraction for "State, United States" format
							if ", United States" in location_name:
								state_part = location_name.split(',')[0].strip()
								if state_part in name_to_record_id:
									matched_record_id = name_to_record_id[state_part]
									matched_type = name_to_type[state_part]
									match_strategy = "state_extraction"
									print(f"        ✅ STATE EXTRACTION MATCH: {location_name} → {state_part} → {matched_record_id} (type: {matched_type})")
								else:
									print(f"        ❌ NO MATCH: {location_name} not found in all_locations.json")
									continue
							else:
								print(f"        ❌ NO MATCH: {location_name} not found in all_locations.json")
								continue
			
			# Check if this is an HQ location first
			is_hq_location = matched_record_id in hq_record_ids
			
			# Categorize based on type and add to appropriate containers
			if is_hq_location:
				hq_ee_count += linkedin_count
				hq_scrape_record_ids.append(matched_record_id)
				print(f"        🏢 Added to HQ EEs: {linkedin_count}")
			elif location_name == "United States" or (match_strategy == "suffix_removal" and location_name_clean == "United States"):
				# Special case: United States should be counted as US EEs, not Other Countries
				us_ee_count += linkedin_count
				print(f"        🇺🇸 Added to US EEs (United States): {linkedin_count}")
			elif matched_type == "us_city":
				us_ee_count += linkedin_count
				# Extract just the city name (before comma)
				city_name = location_name.split(',')[0].strip()
				other_us_cities.append((city_name, linkedin_count))
				other_us_cities_record_ids.append(matched_record_id)
				print(f"        📍 Added to US EEs: {linkedin_count}")
				print(f"        📍 Added to Other US Cities: {city_name} ({linkedin_count})")
			elif matched_type == "country":
				# Skip United States from Other Countries
				if location_name == "United States" or (match_strategy == "suffix_removal" and location_name_clean == "United States"):
					us_ee_count += linkedin_count
					print(f"        🇺🇸 Added to US EEs (United States country): {linkedin_count}")
				else:
					other_countries.append((location_name, linkedin_count))
					countries_record_ids.append(matched_record_id)
					print(f"        📍 Added to Other Countries: {location_name} ({linkedin_count})")
			elif matched_type == "city":
				# For regular cities, we need to determine if it's HQ or other
				# For now, we'll add to other countries unless it's a major US city
				if "United States" in location_name or any(state in location_name for state in ["CA", "TX", "NY", "FL", "WA", "IL", "PA", "OH", "GA", "NC", "MI", "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "CO", "OR", "WI", "MN", "SC", "AL", "LA", "KY", "UT", "IA", "NV", "AR", "MS", "CT", "KS", "NE", "ID", "HI", "NH", "ME", "RI", "MT", "DE", "SD", "ND", "AK", "DC", "VT", "WY", "WV"]):
					us_ee_count += linkedin_count
					# Extract just the city name (before comma)
					city_name = location_name.split(',')[0].strip()
					other_us_cities.append((city_name, linkedin_count))
					other_us_cities_record_ids.append(matched_record_id)
					print(f"        📍 Added to US EEs (city): {linkedin_count}")
				else:
					other_countries.append((location_name, linkedin_count))
					countries_record_ids.append(matched_record_id)
					print(f"        📍 Added to Other Countries (city): {linkedin_count}")

		# Sort cities and countries by count (descending) and format
		other_us_cities_sorted = sorted(other_us_cities, key=lambda x: x[1], reverse=True)
		other_countries_sorted = sorted(other_countries, key=lambda x: x[1], reverse=True)
		
		other_us_cities_formatted = [f"{name} ({count})" for name, count in other_us_cities_sorted]
		other_countries_formatted = [f"{name} ({count})" for name, count in other_countries_sorted]

		# Remove duplicates from record ID lists
		hq_scrape_record_ids = list(set(hq_scrape_record_ids))
		other_us_cities_record_ids = list(set(other_us_cities_record_ids))
		countries_record_ids = list(set(countries_record_ids))

		print(f"\n📊 FINAL RESULTS:")
		print(f"    HQ EEs: {hq_ee_count}")
		print(f"    US EEs: {us_ee_count}")
		print(f"    Other US Cities: {', '.join(other_us_cities_formatted)}")
		print(f"    Other Countries: {', '.join(other_countries_formatted)}")
		print(f"    HQ Scrape Record IDs: {hq_scrape_record_ids}")
		print(f"    Other US Cities Record IDs: {other_us_cities_record_ids}")
		print(f"    Countries Record IDs: {countries_record_ids}")

		print("\n" + "=" * 60)


if __name__ == "__main__":
	linkedin = Linkedin()
	
	# Create or load log file at the start
	print("📝 SETTING UP LOG FILE")
	print("=" * 50)
	linkedin.create_log_file()
	
	# Test location mapping functionality
	print("\n🧪 TESTING LOCATION MAPPING FUNCTIONALITY")
	linkedin.test_location_mapping()
	
	# Show table information
	print("📋 AIRTABLE CONFIGURATION:")
	print("=" * 50)
	print(f"📊 Prospects Table: {linkedin.Prospectus_Table}")
	print(f"🔗 Base ID: {linkedin.INPUT_BASE_ID}")
	print(f"👁️ View: {linkedin.VIEW_NAME}")
	print(f"🔗 Direct Airtable Link: https://airtable.com/{linkedin.INPUT_BASE_ID}/{linkedin.Prospectus_Table}")
	print("=" * 50)
	
	# Generate CSV and JSON files with company data
	print("Generating company data files:")
	linkedin.generateCompanyDataFiles()
	
	print("Scrapping GeoLocations:")
	linkedin.GeoLocationIds()
	print("Start Chrome Driver Instance")
	driver = linkedin.Get_ChromeDriver()
	print("Login to LinkedIn")
	driver = linkedin.Login_LinkedIn(driver)
	print("Scrapping Employee Count")
	driver = linkedin.scrapData(driver)
	
	# Save the update log
	print("\n" + "="*60)
	print("💾 SAVING UPDATE LOG")
	print("="*60)
	linkedin.save_update_log()
