# CrunchBase Follow - Advanced Data Pipeline 🚀

A comprehensive data pipeline system for scraping, matching, and processing company data from CrunchBase, LinkedIn, and Glassdoor platforms with automated CAPTCHA solving and Airtable integration.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [File Structure](#file-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Detailed File Descriptions](#detailed-file-descriptions)
- [Configuration](#configuration)
- [API Integration](#api-integration)
- [CAPTCHA Handling](#captcha-handling)
- [Data Flow](#data-flow)
- [Error Handling](#error-handling)
- [Contributing](#contributing)

## 🎯 Overview

CrunchBase Follow is an advanced data pipeline system that automates the collection, processing, and synchronization of company data across multiple platforms. The system specializes in:

- **CrunchBase Investment Data Scraping**: Automated extraction of Vista Equity Partners' investment portfolio
- **Company Data Matching**: Intelligent matching between CrunchBase data and existing Airtable records
- **LinkedIn Employee Analytics**: Comprehensive employee count analysis by geographic location
- **Glassdoor Reviews Integration**: Automated collection of company ratings and review data
- **Multi-Platform Data Synchronization**: Seamless integration with Airtable CRM system

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CrunchBase    │    │    LinkedIn     │    │   Glassdoor     │
│    Scraper      │    │    Scraper      │    │    Scraper      │
│  (JavaScript)   │    │   (Python)      │    │  (JavaScript)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Processing Layer                        │
│              (Matching & Normalization)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Airtable CRM                              │
│                 (Central Data Storage)                         │
└─────────────────────────────────────────────────────────────────┘
```

## ✨ Features

### 🔍 Data Scraping

- **CrunchBase Investment Tracking**: Real-time scraping of Vista Equity Partners' portfolio
- **LinkedIn Employee Analytics**: Geographic distribution analysis of company employees
- **Glassdoor Company Reviews**: Automated extraction of ratings and engagement metrics
- **Anti-Detection Mechanisms**: Advanced CAPTCHA solving and session management

### 🎯 Data Processing

- **Intelligent Matching**: Fuzzy string matching for company name normalization
- **Geographic Categorization**: Automated classification of employee locations
- **Data Validation**: Comprehensive validation and error handling
- **Duplicate Detection**: Advanced algorithms to prevent data duplication

### 🔄 Integration

- **Airtable Synchronization**: Real-time data updates and record management
- **Multi-Platform Support**: Seamless integration across CrunchBase, LinkedIn, and Glassdoor
- **Automated Workflows**: Sequential execution of data pipeline stages
- **Error Recovery**: Robust error handling and retry mechanisms

## 📁 File Structure

```
CrunchBase Follow/
├── 📜 Main_Runner.py              # Pipeline orchestrator and workflow manager
├── 🔍 crunchbase-main_cap.js      # CrunchBase scraper with CAPTCHA solving
├── 📊 crunchbase_matching.py      # Company data matching and normalization
├── 💼 Linkedin-Main.py            # LinkedIn employee analytics scraper
├── ⭐ glassdoor-script.js          # Glassdoor reviews and ratings scraper
├── 🍪 glassdoor_cookies.json      # Glassdoor session management
├── 📋 requirements.txt            # Python dependencies
└── 📖 README.md                   # This documentation file
```

## 🛠️ Installation

### Prerequisites

- **Python 3.8+**
- **Node.js 16+**
- **Chrome Browser**
- **ChromeDriver** (automatically managed)

### Python Dependencies

```bash
pip install -r requirements.txt
```

### Node.js Dependencies

```bash
npm install puppeteer axios node-html-parser csv-parser json2csv selenium-webdriver node-fetch
```

### Environment Setup

1. **Configure API Keys**:

   - Airtable API Key
   - CapMonster API Key (for CAPTCHA solving)
   - Platform credentials

2. **Set up Chrome Driver**:
   ```bash
   # Automatically handled by webdriver-manager
   ```

## 🚀 Usage

### Full Pipeline Execution

```bash
python Main_Runner.py
```

### Individual Component Execution

#### CrunchBase Data Scraping

```bash
node crunchbase-main_cap.js
```

#### Company Matching

```bash
python crunchbase_matching.py
```

#### LinkedIn Employee Analytics

```bash
python Linkedin-Main.py
```

#### Glassdoor Reviews

```bash
node glassdoor-script.js
```

## 📄 Detailed File Descriptions

### 🎛️ Main_Runner.py - Pipeline Orchestrator

**Purpose**: Coordinates the entire data pipeline workflow
**Key Features**:

- Sequential script execution
- File dependency management
- Error handling and logging
- Process monitoring

**Workflow**:

1. Execute CrunchBase scraper
2. Wait for `vista_extended_funding_data.csv`
3. Run company matching algorithm
4. Wait for `unmatched_companies.csv`
5. Execute Glassdoor scraper
6. Run LinkedIn employee analytics

```python
# Example usage
def run_script(script_name):
    result = subprocess.run(["python", script_name], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error running {script_name}: {result.stderr}")
        exit(1)
```

### 🔍 crunchbase-main_cap.js - CrunchBase Investment Scraper

**Purpose**: Scrapes Vista Equity Partners' investment portfolio from CrunchBase
**Key Features**:

- **Advanced CAPTCHA Solving**: Integration with CapMonster Cloud
- **Investment Data Extraction**: Announced dates, funding rounds, money raised
- **Company Profile Scraping**: Website URLs, social media links
- **Anti-Detection**: Sophisticated browser automation

**Data Fields Extracted**:

- Announced Date
- Organization Name
- Organization URL
- Website URL
- Social Media Links
- Lead Investor
- Funding Round
- Money Raised

**CAPTCHA Handling**:

```javascript
const taskPayload = {
  clientKey: "96bbcafeaf0ccb14cf7c2f0d813fb476",
  task: {
    type: "TurnstileTask",
    websiteURL: params.websiteURL,
    websiteKey: params.websiteKey,
    cloudflareTaskType: "token",
  },
};
```

### 📊 crunchbase_matching.py - Company Data Matching Engine

**Purpose**: Matches CrunchBase data with existing Airtable records
**Key Features**:

- **Fuzzy String Matching**: Advanced normalization algorithms
- **Duplicate Detection**: Prevents data duplication
- **Batch Processing**: Handles large datasets efficiently
- **Unmatched Record Identification**: Outputs new companies for processing

**Normalization Process**:

```python
def normalize_string(value):
    """Normalizes company names for accurate matching"""
    if not value:
        return ""
    value = unidecode(value)  # Remove accents
    value = re.sub(r'[^a-zA-Z0-9\s]', ' ', value)  # Remove special chars
    value = re.sub(r'\s+', ' ', value).strip()  # Normalize spaces
    value = value.replace(' ', '')  # Remove all spaces
    return value.lower()
```

**Matching Algorithm**:

- Loads existing Airtable company records
- Normalizes company names using advanced algorithms
- Identifies new companies not in the database
- Outputs unmatched records for further processing

### 💼 Linkedin-Main.py - LinkedIn Employee Analytics Engine

**Purpose**: Comprehensive LinkedIn employee data analysis and geographic distribution
**Key Features**:

- **Employee Count Analysis**: Total and geographic distribution
- **Location-Based Categorization**: HQ, US cities, international locations
- **Company Profile Scraping**: Logo, description, website, founding year
- **Job Opening Tracking**: Active job postings analysis
- **Airtable Integration**: Real-time CRM updates

**Geographic Analysis Categories**:

- **HQ Employees**: Headquarters-based staff
- **US Employees**: Total US-based workforce
- **Other US Cities**: Non-HQ US locations
- **Other Countries**: International workforce

**Employee Categorization Logic**:

```python
def categorize_employee_counts(self, ee_counts, total_number, HQ, CityCountryToScrap):
    """Categorizes employees by geographic location"""
    # 1. Headquarters matching
    if loc_name_lower in HQ.lower():
        hq_ee_count += count

    # 2. US city identification
    if tag == "us_city":
        us_ee_count += count

    # 3. Other categorization
    if loc_type == "city":
        other_us_cities.append(f"{loc_name_from_json} ({count})")
```

**Data Fields Processed**:

- Total Employee Count
- Geographic Distribution
- Company Logo URL
- LinkedIn Description
- Industry Classification
- Year Founded
- Headquarters Location
- LinkedIn Followers
- Open Job Positions

### ⭐ glassdoor-script.js - Glassdoor Reviews Scraper

**Purpose**: Automated extraction of company ratings and review data from Glassdoor
**Key Features**:

- **Review Metrics Extraction**: Overall ratings, review counts
- **Engagement Status**: Employer engagement indicators
- **Company URL Matching**: Intelligent company identification
- **CAPTCHA Handling**: Automated CAPTCHA solving
- **Session Management**: Cookie-based authentication

**Data Fields Extracted**:

- Glassdoor URL
- Glassdoor ID
- Overall Review Rating
- Total Number of Reviews
- Engaged Employer Status

**Search and Matching Process**:

```javascript
async function searchGlassdoorUrl(page, company, website) {
  // Intelligent search using company name and website
  // Returns Glassdoor URL for data extraction
}
```

**CAPTCHA Integration**:

- Detects CAPTCHA challenges
- Automatically solves using CapMonster Cloud
- Maintains session continuity
- Handles multiple CAPTCHA types

### 🍪 glassdoor_cookies.json - Session Management

**Purpose**: Stores Glassdoor session cookies for authentication
**Features**:

- Persistent login sessions
- Authentication token management
- Session restoration capabilities

## ⚙️ Configuration

### 🔑 API Configuration

```python
# Airtable Configuration
AIRTABLE_BASE_ID = "appjvhsxUUz6o0dzo"
AIRTABLE_API_KEY = "your_api_key_here"
AIRTABLE_TABLE_NAME = "Company"

# CAPTCHA Service
CAPMONSTER_API_KEY = "96bbcafeaf0ccb14cf7c2f0d813fb476"

# LinkedIn Configuration
VIEW_NAME = "Matt View"
INPUT_BASE_ID = "appjvhsxUUz6o0dzo"
OUTPUT_BASE_ID = "appQfs70fHCsFgeUe"
```

### 🗂️ Database Schema

**Airtable Fields**:

- Company Name
- Website URL
- LinkedIn ID
- Total EEs (Scraped)
- US EEs (Scraped)
- HQ EEs (Scraped)
- Other US Cities (Scraped)
- Other Countries (Scraped)
- Glassdoor URL
- Glassdoor ID
- GD Overall Review
- GD # of Reviews (Overall)
- Glassdoor Engaged

## 🔄 Data Flow

### 📊 Complete Pipeline Flow

1. **CrunchBase Scraping**:

   - Access Vista Equity Partners' investment page
   - Solve CAPTCHA challenges
   - Extract investment data
   - Generate `vista_extended_funding_data.csv`

2. **Company Matching**:

   - Load existing Airtable records
   - Compare with CrunchBase data
   - Identify unmatched companies
   - Generate `unmatched_companies.csv`

3. **Glassdoor Integration**:

   - Process unmatched companies
   - Search for Glassdoor profiles
   - Extract review data
   - Update Airtable records

4. **LinkedIn Analytics**:
   - Process company LinkedIn profiles
   - Extract employee geographic data
   - Categorize by location
   - Update comprehensive company profiles

### 🔄 Data Synchronization

- **Real-time Updates**: Immediate Airtable synchronization
- **Batch Processing**: Efficient handling of large datasets
- **Error Recovery**: Automatic retry mechanisms
- **Data Validation**: Comprehensive validation checks

## 🛡️ Error Handling

### 🚨 Exception Management

- **Network Errors**: Automatic retry with exponential backoff
- **CAPTCHA Failures**: Multiple solving attempts
- **Data Validation**: Comprehensive error checking
- **Session Management**: Automatic session restoration

### 📝 Logging

- **Detailed Logging**: Comprehensive operation logs
- **Error Tracking**: Detailed error reporting
- **Performance Monitoring**: Execution time tracking
- **Debug Information**: Detailed debugging data

## 📊 Dependencies

### 🐍 Python Dependencies

```txt
requests==2.31.0           # HTTP requests
beautifulsoup4==4.12.2     # HTML parsing
selenium==4.15.2           # Browser automation
pandas==2.1.3              # Data manipulation
openpyxl==3.1.2            # Excel operations
webdriver-manager==4.0.1   # Chrome driver management
python-dotenv==1.0.0       # Environment variables
unidecode==1.3.7           # Unicode normalization
```

### 📦 Node.js Dependencies

```json
{
  "puppeteer": "^21.5.0",
  "axios": "^1.6.0",
  "node-html-parser": "^6.1.0",
  "csv-parser": "^3.0.0",
  "json2csv": "^7.0.0",
  "selenium-webdriver": "^4.15.0",
  "node-fetch": "^3.3.0"
}
```
