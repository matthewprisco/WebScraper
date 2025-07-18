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
import time,json,requests,os.path , re

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

		# {
		# 		"Company": "Yotpo",
		# 		"CompanyId": "1515446",
		# 		"CityCountryToScrap" : [
		# 			"United States;US EEs"
		# 			"San Francisco;US EEs"
		# 			"Los Angeles;Other US Cities",
		# 			"Berlin;Other Countries",
		# 			"Tel Aviv;Other Countries"
		# 		]
		# 	}

		self.social_info = None

	def update_crm(self,json_update_data,record_data):
		json_update_data = json.dumps(json_update_data)
		r = requests.patch("https://api.airtable.com/v0/"+self.INPUT_BASE_ID+"/"+self.Prospectus_Table+"/"+ record_data,data = json_update_data, headers=self.Post_Header)
		return r.text,r.status_code


	def load_companies_from_csv(self, csv_file_path):
		df = pd.read_csv(csv_file_path)
		for idx, row in df.iterrows():
			social_links = str(row.get("Social Media Links", ""))
			linkedin_links = [link.strip() for link in social_links.split(",") if "linkedin.com/company" in link]
			print(" ~ linkedin_links ======:", linkedin_links)

			if not linkedin_links:
				print(f" No LinkedIn URL found for: {row.get('Organization Name', 'N/A')}")
				continue

			linkedin_url = linkedin_links[0].rstrip("/")

			self.AllRecordIds.append({
				"Company": row.get("Organization Name", "N/A"),
				"LinkedInURL": linkedin_url,
				"CityCountryToScrap": []  # you can extend this from CSV later if needed
			})

		print(f" Loaded {len(self.AllRecordIds)} companies from CSV.")

	def getInputCompanyTable(self):
		processed_count = 0
		offset = ''
		while 1:
			CompanyTableURL = 'https://api.airtable.com/v0/'+self.INPUT_BASE_ID +'/'+ self.Prospectus_Table
			if len(self.VIEW_NAME) > 1:
				OutputTable = requests.get(CompanyTableURL, headers=self.headers,params={'offset': offset,'view':self.VIEW_NAME}).json()
			else:
				OutputTable = requests.get(CompanyTableURL, headers=self.headers,params={'offset': offset}).json()
			for Records in OutputTable["records"]:

				for recordsKey,recordsValue in Records.items():
					if recordsKey == "fields":
						# print(" ~ recordsValue:", recordsValue)
						SingleRecord = {}
						CityCountry = []
						try:
							SingleRecord["Company"] = recordsValue["Company Name"]
						except:
							continue

						try:
							linked_record_ids = recordsValue.get("Link to Company", [])
							print(" ~ linked_record_ids:", linked_record_ids)
							if linked_record_ids:
								linked_record_id = linked_record_ids[0]
								linked_url = f'https://api.airtable.com/v0/{self.INPUT_BASE_ID}/{self.Prospectus_Table}/{linked_record_id}'
								linked_record_response = requests.get(linked_url, headers=self.headers).json()
								linked_fields = linked_record_response.get("fields", {})

								website = linked_fields.get("Website", "N/A")
								linkedin_id = linked_fields.get("LinkedIn ID", "N/A")

								print(f"     LinkedIn ID =======================: {linkedin_id}")
						except Exception as e:
							print(f"     Error fetching linked company details: {e}")

						try:
							if linkedin_id != "N/A":
								try:
									int(linkedin_id)
									SingleRecord["CompanyId"] = linkedin_id
								except:
									print(" "*4, SingleRecord["Company"] + "[Not Found]")
									continue
							else:
								print(" "*4, SingleRecord["Company"] + "[Not Found]")
								continue
						except:
							print(" "*4,recordsValue["Company Name"]+"[Not Found]")
							continue

						print("    " + recordsValue["Company Name"] + f"[{SingleRecord['CompanyId']}]")

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
						processed_count += 1

						if processed_count >= 10:
							print(" Processed first 5 companies only.")
							return
			try:
				nextOffset = OutputTable["offset"]
				offset = nextOffset
			except:
				break

		# print(f"Total companies to scrape:", self.AllRecordIds)
		print(f"Total companies to scrape:================= {len(self.AllRecordIds)}", self.AllRecordIds)

	# def GeoLocationIds(self):
	# 	offset = ""
	# 	while 1:
	# 		geoTableUrl = 'https://api.airtable.com/v0/' + self.INPUT_BASE_ID + "/" + self.GeoCitiesTable
	# 		r = requests.get(geoTableUrl, headers=self.headers,params={'offset': offset}).json()
	# 		for Records in r["records"]:
	# 			try:
	# 				Records["fields"]["geoUrn"]
	# 				locationName = Records["fields"]["Name"].replace("\n","").strip() +"|"+ Records["id"].replace("\n","").strip()
	# 				print(" "*4,Records["fields"]["Name"].replace("\n","").strip()+"["+Records["fields"]["geoUrn"].replace("\n","").strip()+"]")
	# 				locationGeoId = Records["fields"]["geoUrn"].replace("\n","").strip()
	# 				self.geoTableIds[locationName] = locationGeoId
	# 			except:
	# 				try:
	# 					locationName = Records["fields"]["Name"] +"|"+ Records["id"]
	# 					self.geoTableIds[locationName] = "NULL"
	# 					print(" "*4,Records["fields"]["Name"]+"[Not Found]")
	# 				except:
	# 					()
	# 		try:
	# 			nextOffset = r["offset"]
	# 			offset = nextOffset
	# 		except:
	# 			break



	def GeoLocationIds(self):
		if all(os.path.exists(f) for f in ["all_locations.json", "countries.json", "usa_cities.json"]):
			print(" JSON files already exist. Skipping GeoLocationIds scraping.")
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

		print(" Saved JSON files: all_locations.json, countries.json, usa_cities.json")


	def Get_ChromeDriver(self):
		print("Starting Chrome Driver Instance...")
		from selenium import webdriver
		from selenium.webdriver.chrome.service import Service
		from webdriver_manager.chrome import ChromeDriverManager

		chrome_options = webdriver.ChromeOptions()
		chrome_options.add_argument("--start-maximized")
		# Uncomment below line if you are on a server or want headless
		chrome_options.add_argument('--headless=new')
# 		chrome_options.binary_location = '/home/Betafits/bin/google-chrome'
		chrome_options.add_argument("--no-sandbox")
		chrome_options.add_argument('--log-level=3')
		chrome_options.add_argument("--disable-notifications")
		chrome_options.add_argument('--ignore-certificate-errors-spki-list')
		chrome_options.add_argument('--ignore-ssl-errors')
		chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
		chrome_options.add_experimental_option('useAutomationExtension', False)

		prefs = {
			"credentials_enable_service": False,
			"profile.password_manager_enabled": False,
			"profile.default_content_setting_values.geolocation": 2,
		}
		chrome_options.add_experimental_option("prefs", prefs)

		service = Service(executable_path='/home/Betafits/bin/chromedriver')
		driver = webdriver.Chrome(service=service, options=chrome_options)

# 		driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
		print(" Chrome Driver Started Successfully")
		print(" Current URL:", driver.current_url)
		return driver

	def Login_LinkedIn(self, driver):
		print("Loading LinkedIn cookies...")

		# Load cookies
		with open("/home/Betafits/AllScript/linkdin_cookies_file_qualityteam231.json", "r") as co:
			cookies = json.load(co)

		driver.get("https://www.linkedin.com/feed/")

		# Add cookies to driver
		for cookie in cookies:
			cookie.pop("sameSite", None)
			driver.add_cookie(cookie)

		# Refresh after all cookies are added
		driver.refresh()
		time.sleep(5)
		print(f"driver.current_url ====== ", driver.current_url)
		driver.save_screenshot("linkedin_login_error_1.png")

		# Check if we're logged in
		if "linkedin.com%2Ffeed%2F" in driver.current_url:
			try:
				BUTTON_Profile = WebDriverWait(driver, 5).until(
					EC.presence_of_element_located((By.CLASS_NAME, "member-profile__details"))
				)
				print("🚀 ~ BUTTON_Profile found:", BUTTON_Profile)
				BUTTON_Profile.click()
				time.sleep(5)
			except:
			    driver.save_screenshot("linkedin_login_error_2.png")
			    print("Profile button not found. Attempting manual login...")

			if "linkedin.com%2Ffeed%2F" in driver.current_url:
			    driver.save_screenshot("linkedin_login_error_3.png")
			    try:
				    email_input = WebDriverWait(driver, 10).until(
						EC.presence_of_element_located((By.ID, "username"))
					)
				    password_input = WebDriverWait(driver, 10).until(
						EC.presence_of_element_located((By.ID, "password"))
					)

				    email_input.send_keys("qualityteam231@gmail.com")
				    password_input.send_keys("Linkdin@1234")
				    driver.save_screenshot("linkedin_login_error_4.png")

				    BUTTON = driver.find_element(By.XPATH, "//button[@type='submit' and @aria-label='Sign in']")
				    print(f"button sign up ===== ",BUTTON )
				    BUTTON.click()


				    WebDriverWait(driver, 10).until(EC.url_contains("feed"))
				    driver.save_screenshot("linkedin_login_error_5.png")
				    print("Manual login successful, consider updating cookies.")
			    except Exception as e:
			        driver.save_screenshot("linkedin_Manual login_error_6.png")
			        print("Manual login failed:", e)
			else:
				print("Logged in after profile button click.")
		else:
			print("Logged in using cookies.")

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
		print(f"Total companies to scrape: ========================== {(self.AllRecordIds)}")

		for Records in self.AllRecordIds:
			print(f"Scraping data for: {Records.get('Company')} [{Records.get('CompanyId')}]")

			#------------------------------------------------- Only Company Scrap --------------------------------------------------------------------
			this_LinkedInURL = Records["LinkedInURL"]
			this_CompanyName = str(Records["Company"]).replace('"','')

			# driver.get("https://www.linkedin.com/search/results/people/?currentCompany=["+this_CompanyId+"]&origin=COMPANY_PAGE_CANNED_SEARCH&sid=ZJJ")
			# try:
			# 	WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "search-results-container")))
			# except:
			# 	continue

			TotalResults = "0"
			# TotalResults = driver.find_element(By.CLASS_NAME,"search-results-container").find_element(By.TAG_NAME,"h2").text.split("result")[0]
			# print("\n"+Records["Company"]+"["+this_CompanyId+"]")
			# print(" "*3,"Total Employees: ",TotalResults,"Results")
			# if "No" in TotalResults:
			# 		TotalResults = "0"
			# try:
			# 	int(TotalResults)
			# except:
			# 	TotalResults = "0"

			#-------------------------------------------------------------------------------------------------------------------------------------------------
			TotalEEs = 0
			USEEs = 0
			HQEEs = 0
			OtherUSCities = ""
			OtherCountries = ""

			TotalEEs = int(TotalResults)
			#print(this_CompanyId)
			driver,openJobCount,linkedinURL,companyDetailsfromFunction = self.scrapOpenJobPage(driver,this_LinkedInURL)
			#print("_"*30)
			openJobCount = int(openJobCount)

			print(" "*3,"Open Jobs: ",openJobCount)
			print(" "*3,"Followers: ",companyDetailsfromFunction["Followers"])
			print(" "*3,"Website: ",companyDetailsfromFunction["companyWebsite"])
			print(" "*3,"Department: ",companyDetailsfromFunction["Department"])
			print(" "*3,"HQ: ",companyDetailsfromFunction["headQuarter"])

			ee_counts, total_number = self.scrape_location_ee_counts(driver, this_LinkedInURL)
			print(" ~ ee_counts:================", ee_counts)
			print(" ~ total_number:================", total_number)



			# print(" CityCountryToScrap:", Records["CityCountryToScrap"])

			if not ee_counts or not total_number:
				print(f" Skipping company because employee data or total number is missing.")
				continue  # Or continue if you're in a loop



			categorized = self.categorize_employee_counts(ee_counts,total_number, companyDetailsfromFunction["headQuarter"], Records.get("CityCountryToScrap", []))
			print(" ~ categorized: =============", categorized)


			HQEEs = categorized.get("HQ EEs (Scraped)", 0)
			print(" ~ HQEEs:", HQEEs)
			USEEs = categorized.get("US EEs (Scraped)", 0)
			print(" ~ USEEs:", USEEs)
			OtherUSCities = categorized.get("Other US Cities (Scraped)", "")
			print(" ~ OtherUSCities:", OtherUSCities)
			OtherCountries = categorized.get("Other Countries (Scraped)", "")
			print(" ~ OtherCountries:", OtherCountries)


			# for CityCountry in Records["CityCountryToScrap"]:
			# 	this_ProspectGeo = CityCountry.split(";")[1].replace('"',"")
			# 	CityCountry = CityCountry.split(";")[0]
			# 	#----------------------------------------------------------------------------------------
			# 	LocationFound = False
			# 	toPrintLocation = ""
			# 	for location,GeoId_ in self.geoTableIds.items():
			# 		if location.split('|')[0] == CityCountry or location.split('|')[1] == CityCountry:
			# 			this_CompanyLocationID = GeoId_.replace('"','')
			# 			this_CompanyLocationName = location.split('|')[0]
			# 			if GeoId_ == "NULL":
			# 				toPrintLocation = this_CompanyLocationName
			# 				break
			# 			LocationFound = True
			# 			break
			# 	if LocationFound == False:
			# 		print(" "*3,"*GeoId for",toPrintLocation+"["+CityCountry+"] Not Found")
			# 		continue
			# 	#-----------------------------------------------------------------------------------------
			# 	driver.get("https://www.linkedin.com/search/results/people/?currentCompany=["+this_CompanyId+"]&geoUrn=["+this_CompanyLocationID+"]&origin=FACETED_SEARCH&sid=9vr")
			# 	try:
			# 		WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "search-results-container")))
			# 	except:
			# 		continue
			# 	# TotalResults = driver.find_element(By.CLASS_NAME,"search-results-container").find_element(By.TAG_NAME,"h2").text.split("result")[0]
			# 	TotalResults = "No"
			# 	if "No" in TotalResults:
			# 		TotalResults = "0"
			# 	try:
			# 		int(TotalResults)
			# 	except:
			# 		TotalResults = "0"
			# 	print(" "*3,this_CompanyLocationName,"["+this_CompanyLocationID+"] :",str(TotalResults),"Results")
			# 	time.sleep(1)

			# 	if this_ProspectGeo == "HQ EEs":
			# 		HQEEs = int(TotalResults)
			# 	if this_ProspectGeo == "US EEs":
			# 		USEEs = int(TotalResults)
			# 	if this_ProspectGeo == "Other US Cities":
			# 		OtherUSCities = OtherUSCities + f"{this_CompanyLocationName} ({str(TotalResults).strip()}),"

			# 	if this_ProspectGeo == "Other Countries":
			# 		OtherCountries = OtherCountries + " " + this_CompanyLocationName + " (" + str(TotalResults) + "),"

			# OtherUSCities = sorted(OtherUSCities.split(","),reverse=True)
			# OtherUSCities = ', '.join(OtherUSCities)
			# OtherCountries = sorted(OtherCountries.split(","),reverse=True)
			# OtherCountries = ', '.join(OtherCountries)
			RecordIdURL = "https://api.airtable.com/v0/"+self.INPUT_BASE_ID+"/"+self.Prospectus_Table+"?filterByFormula={Company Name}='"+str(this_CompanyName)+"'"
			time.sleep(1)
			try:
				RecordIDToUpdateData = requests.get(RecordIdURL, headers=self.headers).json()["records"][0]["id"]
				print(" ~ RecordIDToUpdateData: ============ ", RecordIDToUpdateData)
			except:
				print(" "*5,"-->Id Not Found in Prospects Table")
				continue

			crm_update_data = {
									"fields": {
										"Total EEs (Scraped)" : int(total_number),
										"US EEs (Scraped)":USEEs,
										"HQ EEs (Scraped)":HQEEs,
										"Other US Cities (Scraped)":OtherUSCities.strip().strip(',').strip(),
										"Other Countries (Scraped)":OtherCountries.strip().strip(',').strip(),
										"Open Jobs (Scraped)":openJobCount,
										# "Website (Delete)" : companyDetailsfromFunction["companyWebsite"],
										"LinkedIn Description (Scraped)":companyDetailsfromFunction["Short Description"],
										"Industry (Scraped)":companyDetailsfromFunction["Department"],
										"LinkedIn Followers (Scraped)":self.convalue(companyDetailsfromFunction["Followers"]),
										"Year Founded (Scraped)":int(companyDetailsfromFunction["yearFounded"])
										# "Logo (From Companies": [{"url":companyDetailsfromFunction["Company Logo"],"filename":this_CompanyId+"_Logo_.jpg"}]
										#"Create a Field for HeadQuarter":companyDetailsfromFunction["headQuarter"]
									}
								}
			print(self.update_crm(crm_update_data,record_data=RecordIDToUpdateData))
		return driver


	def scrapOpenJobPage(self,driver,this_LinkedInURL):
		companyDetails = {}
		companyDetails["Department"] = ""
		companyDetails["headQuarter"] = ""
		companyDetails["Followers"] = "0"
		companyDetails["Company Logo"] = ""
		companyDetails["Short Description"] = ""
		companyDetails["companyWebsite"] = ""
		companyDetails["yearFounded"] = "0"
		companyDetails["linkedinUrl"] = ""

		driver.get(this_LinkedInURL + "/jobs/")
		print(driver.current_url)
		companyDetails["linkedinUrl"] = driver.current_url

		try:
			jobOpeningtag = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CLASS_NAME, "org-jobs-job-search-form-module__headline"))).text
			# jobOpeningtag = driver.find_element(By.CLASS_NAME,"org-jobs-job-search-form-module__headline").text
			jobOpeningCount = jobOpeningtag.split("has ")[1].split(" ")[0].replace(",","").strip()
		except:
			jobOpeningCount = "0"
		linkedinURL = str(driver.current_url).replace("/jobs/","")

		#Section Company Top Details
		print(" "*3, "Trying to get job jobOpeningCount section...")

		try:
			WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CLASS_NAME, "org-top-card-summary-info-list__info-item")))
		except:
			return driver,jobOpeningCount,linkedinURL,companyDetails

		try:
			shortDescription = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'org-top-card-summary__tagline'))).text
		except:
			shortDescription = ""

		print(" "*3, "Trying to get job detail section...")

		try:
			CompaDetaillist = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "org-top-card-summary-info-list__info-item")))
			# print(" "*3, 'detail =================== ', CompaDetaillist)
			tempCompa = {}
			for index,detail in enumerate(CompaDetaillist):
				# print(" "*3, 'detail =================== ', detail)
				tempCompa["Department"] = 0
				tempCompa["headQuarter"] = 1
				tempCompa["Followers"] = 2
				if "followers" in detail.text:
					companyDetails["Followers"] = detail.text.split(" followers")[0]
				if "employees" in detail.text:
					if companyDetails["Followers"] == "0" or companyDetails["Followers"] ==2:
						companyDetails[list(tempCompa.keys())[list(tempCompa.values()).index(index)]] = ""
				if "followers" not in detail.text and "employees" not in detail.text and index==0:
					companyDetails[list(tempCompa.keys())[list(tempCompa.values()).index(index)]] = detail.text.split(",")[0]
		except Exception as e:
			print(f"error when scrape company detail: ",e)
		driver.get(this_LinkedInURL + "/about/")
		try:
			companyWebsite = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//dt[h3[text()="Website"]]'))).find_element(By.XPATH, 'following-sibling::dd[@class="mb4 t-black--light text-body-medium"]').text
			if "bit.ly" not in companyWebsite:
				companyWebsite = companyWebsite.split("?")[0].replace("//","|").split("/")[0].replace("|","//")
		except Exception as e:
			print(e)
			companyWebsite = ""
		try:
			companyLogoImageUrl = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'evi-image.lazy-image.ember-view.org-top-card-primary-content__logo'))).get_attribute("src")
		except:
			companyLogoImageUrl = ""
		try:
			year_founded = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//dt[h3[text()="Founded"]]'))).find_element(By.XPATH, 'following-sibling::dd[@class="mb4 t-black--light text-body-medium"]').text.strip()
		except Exception as e:
			print(e)
			year_founded = "0"

		try:
			HQ = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//dt[h3[text()="Headquarters"]]'))).find_element(By.XPATH, 'following-sibling::dd[@class="mb4 t-black--light text-body-medium"]').text
		except Exception as e:
			print(e)
			HQ = ""

		print("data website: ",companyWebsite)
		print("data logo: ",companyLogoImageUrl)
		print("year founded: ",year_founded)
		companyDetails["Company Logo"] = companyLogoImageUrl
		companyDetails["Short Description"] = shortDescription
		companyDetails["companyWebsite"] = companyWebsite
		companyDetails["yearFounded"] = year_founded
		companyDetails["headQuarter"] = HQ

		return driver,jobOpeningCount,linkedinURL,companyDetails

	def extract_geo_id_from_url(self,url):
		"""
		Extracts the facetGeoRegion ID from a LinkedIn people page URL.
		Returns the geo ID as a string, or None if not found.
		"""
		match = re.search(r"facetGeoRegion=(\d+)", url)
		if match:
			return match.group(1)
		return None

	def scrape_location_ee_counts(self, driver, this_LinkedInURL):
		"""
		Scrapes the 'Where they live' section on LinkedIn's People tab and
		returns a dictionary {location: employee_count}.
		Skips the company if total number is not found.
		"""

		from selenium.webdriver.common.by import By
		from selenium.webdriver.support.ui import WebDriverWait
		from selenium.webdriver.support import expected_conditions as EC


		driver.get(this_LinkedInURL + "/people/")

		ee_counts = {}
		total_number = None

		try:
			# Try to get total members text (e.g., "966 associated members")
			total_members_elem = WebDriverWait(driver, 10).until(
				EC.presence_of_element_located((By.CLASS_NAME, "org-people__header-spacing-carousel"))
			)
			text = total_members_elem.text.strip()
			if not text:
				print(f" No total members text found for company . Skipping.")
				return None, None

			total_number = text.split()[0].replace(",", "")
			if not total_number.isdigit():
				print(f" Total number is not a digit for company . Skipping.")
				return None, None

			print(f"Total Members: {total_number}")

			# Wait for the geo-region section
			geo_section = WebDriverWait(driver, 10).until(
				EC.presence_of_element_located((By.CLASS_NAME, "org-people-bar-graph-module__geo-region"))
			)

			# Try to click "Show more" if it exists
			try:
				showmore_button = driver.find_element(By.CLASS_NAME, "org-people__show-more-button")
				showmore_button.click()
			except:
				pass  # "Show more" might not always be there

			# Extract location + count
			buttons = geo_section.find_elements(By.CLASS_NAME, "org-people-bar-graph-element")

			for i in range(len(buttons)):
				try:
					buttons = driver.find_elements(By.CLASS_NAME, "org-people-bar-graph-element")
					btn = buttons[i]

					count_elem = btn.find_element(By.TAG_NAME, "strong")
					location_elem = btn.find_element(By.CLASS_NAME, "org-people-bar-graph-element__category")
					count = int(count_elem.text.strip().replace(",", ""))
					location = location_elem.text.strip()

					location_elem.click()

					# Wait until the geoID appears in the URL
					WebDriverWait(driver, 10).until(lambda d: "facetGeoRegion=" in d.current_url)
					current_url = driver.current_url
					geoID = current_url.split("facetGeoRegion=")[-1].split("&")[0]

					ee_counts[location] = {geoID: count}

					print(f"{location} => {geoID} : {count}")

					# Back to main page
					driver.back()

					# Wait for URL to not have facetGeoRegion
					WebDriverWait(driver, 10).until(lambda d: "facetGeoRegion=" not in d.current_url)
					time.sleep(1)  # safety pause

				except Exception as e:
					print(f"Error on index {i}: {e}")
					continue


		except Exception as e:
			print(f" Failed to scrape for company: {e}")
			return None, None


		return ee_counts, total_number

	def categorize_employee_counts(self, ee_counts, total_number, HQ, CityCountryToScrap):
		print(" ~ total_number: ============ ", total_number)
		print(" ~ HQ ============================== :", HQ)

		with open("all_locations.json") as f:
			location_data = json.load(f)

		# Map geo_id → (location name, type)
		geo_id_map = {}
		for key, val in location_data.items():
			location_name, record_id = key.split("|")
			geo_id = val.get("geo_id")
			geo_type = val.get("type")
			geo_id_map[geo_id] = (location_name, geo_type)

		# Map record_id → location name
		record_id_to_name = {
			key.split('|')[1]: key.split('|')[0]
			for key in location_data.keys()
		}

		hq_ee_count = 0
		us_ee_count = 0
		other_us_cities = []
		other_countries = []

		threshold = max(1, int(total_number) * 0.05)
		print(" ~ threshold:", threshold)

		# record_id → tag (e.g. us_city, HQ EEs)
		record_id_tag_map = {}
		for entry in CityCountryToScrap:
			try:
				record_id, tag = entry.split(";")
				record_id_tag_map[record_id.strip()] = tag.strip()
			except:
				continue

		for location_name, geo_data in ee_counts.items():
			for geo_id, count in geo_data.items():
				if count < threshold:
					continue  # skip small counts

				loc_info = geo_id_map.get(geo_id)
				# print(" ----------------- ~ loc_info:", loc_info)
				if not loc_info:
					continue

				loc_name_from_json, loc_type = loc_info
				loc_name_lower = loc_name_from_json.lower()
				# print(" ----------------- ~ loc_name_from_json:", loc_name_from_json)
				matched_tag = None

				# === 1. Check HQ ===
				if loc_name_lower in HQ.lower():
					hq_ee_count += count
					continue

				# === 2. Check if this geo_id maps to a record_id tagged as "us_city" ===
				is_us_city = False
				print(" ----------------- ~ record_id_tag_map:", record_id_tag_map.items())

				for rec_id, tag in record_id_tag_map.items():
					print(" ----------------- ~ rec_id:", rec_id, "tag:", tag)
					if tag != "us_city":
						continue  # skip non-us_city tags

					expected_name = record_id_to_name.get(rec_id, "").lower()
					if expected_name and expected_name in loc_name_lower:
						is_us_city = True
						break  # once matched, no need to check other rec_ids

				# If matched to a us_city, count this location's EEs
				if is_us_city:
					us_ee_count += count
					continue

				if loc_type == "us_city":
					us_ee_count += count
					continue

				print(" ----------------- ~ us_ee_count:", us_ee_count)
				# === 3. Other US Cities (Scraped): type == city, not HQ, not us_city ===
				if loc_type == "city":
					other_us_cities.append(f"{loc_name_from_json} ({count})")
					continue

				# === 4. Other Countries (Scraped): type == country, not HQ, not us_city ===
				if loc_type == "country":
					other_countries.append(f"{loc_name_from_json} ({count})")

		print(" ~ hq_ee_count:", hq_ee_count)
		print(" ~ us_ee_count:", us_ee_count)
		return {
			"HQ EEs (Scraped)": hq_ee_count,
			"US EEs (Scraped)": us_ee_count,
			"Other US Cities (Scraped)": ', '.join(sorted(other_us_cities, reverse=True)),
			"Other Countries (Scraped)": ', '.join(sorted(other_countries, reverse=True))
		}


if __name__ == "__main__":
	linkedin = Linkedin()
	print("Getting Companies to be Scraped:")
	linkedin.load_companies_from_csv("unmatched_companies.csv")
	# linkedin.getInputCompanyTable()
	print("Scrapping GeoLocations:")
	linkedin.GeoLocationIds()
	print("Start Chrome Driver Instance")
	driver = linkedin.Get_ChromeDriver()
	print(f"Login to LinkedIn" , driver)
	driver = linkedin.Login_LinkedIn(driver)
	print("Scrapping Employee Count")
	driver = linkedin.scrapData(driver)
# 	winsound.Beep(1500, 50)
	driver.quit()
