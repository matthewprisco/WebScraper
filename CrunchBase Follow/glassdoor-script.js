// glassdoor-script.js
// Node.js script using Puppeteer and Axios to replicate Glassdoor-Main-both-NEW.PY

import fs from "fs";
import csv from "csv-parser";
import axios from "axios";
import puppeteer from "puppeteer";
import { parse } from "node-html-parser";
import path from "path";
import { fileURLToPath } from "url";
import fetch from "node-fetch";

// __dirname replacement for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// You need to define these constants (they were missing in the previous version)
const GLASSDOOR_LOGIN_EMAIL = "czgojueycxqdjnvzjr@tmmbt.net";
const GLASSDOOR_PASSWORD = "czgojueycxqdjnvzjr@tmmbt.net";
const CRM_BASE_ID = "appjvhsxUUz6o0dzo";
const CRM_TABLE = "tblf4Ed9PaDo76QHH";
const API_KEY =
  "patQIAmVOLuXelY42.df469e641a30f1e69d29195be1c1b1362c9416fffc0ac17fd3e1a0b49be8b961";
const AIRTABLE_URL = `https://api.airtable.com/v0/${CRM_BASE_ID}/${CRM_TABLE}`;
const HEADERS = { Authorization: `Bearer ${API_KEY}` };
const POST_HEADERS = { ...HEADERS, "Content-Type": "application/json" };

// CAPTCHA config
const CAPMONSTER_API_KEY = "96bbcafeaf0ccb14cf7c2f0d813fb476";
const TARGET_URL = "https://www.glassdoor.com/index.htm";

function filterDomain(url) {
  try {
    let domain = new URL(url).hostname.replace(/^www\./, "");
    return domain;
  } catch {
    return "";
  }
}

async function loadCompaniesFromCSV(csvPath) {
  return new Promise((resolve, reject) => {
    const companies = [];
    fs.createReadStream(csvPath)
      .pipe(csv())
      .on("data", (row) => {
        const companyName = (row["Organization Name"] || "").trim();
        const website = (row["Website URL"] || "").trim();
        if (companyName) {
          companies.push({ "Company Name": companyName, Website: website });
        }
      })
      .on("end", () => {
        resolve(companies);
      })
      .on("error", reject);
  });
}

async function solveCaptcha(page) {
  console.log("🔍 Checking for CAPTCHA...");

  try {
    // Navigate to the target URL
    await page.goto(TARGET_URL, { waitUntil: "networkidle2" });
    await page.screenshot({ path: "glassdoor_page.png" });

    // Check if CAPTCHA is present by looking for common indicators
    const captchaIndicators = await page.evaluate(() => {
      const indicators = [];

      // Check for Turnstile widget
      if (document.querySelector("[data-sitekey]")) {
        indicators.push("turnstile_widget");
      }

      // Check for CAPTCHA-related text
      const captchaTexts = [
        "Help Us Protect Glassdoor",
        "Verify you are human",
        "Cloudflare",
        "Turnstile",
        "Please complete the security check",
      ];

      captchaTexts.forEach((text) => {
        if (document.body.innerText.includes(text)) {
          indicators.push(`text_${text}`);
        }
      });

      // Check for CAPTCHA iframe
      if (
        document.querySelector('iframe[src*="cloudflare"]') ||
        document.querySelector('iframe[src*="turnstile"]')
      ) {
        indicators.push("captcha_iframe");
      }

      return indicators;
    });

    console.log("🔍 CAPTCHA indicators found:", captchaIndicators);

    // If no CAPTCHA indicators found, return true (no CAPTCHA to solve)
    if (captchaIndicators.length === 0) {
      console.log("✅ No CAPTCHA detected, proceeding to login...");
      return true;
    }

    console.log("🔒 CAPTCHA detected, attempting to solve...");

    // Inject CAPTCHA detection and parameter extraction
    await page.evaluateOnNewDocument(`
      const waitForTurnstile = () => {
        return new Promise((resolve) => {
          const check = () => {
            if (window.turnstile && typeof window.turnstile === 'object') {
              resolve();
            } else {
              setTimeout(check, 100);
            }
          };
          check();
        });
      };

      waitForTurnstile().then(() => {
        window.turnstile = new Proxy(window.turnstile, {
          get(target, prop) {
            if (prop === 'render') {
              return function(a, b) {
                let p = {
                  type: "TurnstileTask",
                  websiteKey: b.sitekey,
                  websiteURL: window.location.href,
                  data: b.cData,
                  pageData: b.chlPageData,
                  pageAction: b.action,
                  userAgent: navigator.userAgent,
                  cloudflareTaskType: "token"
                };
                window.params = p;
                window.turnstileCallback = b.callback;
                return target.render.apply(this, arguments);
              }
            }
            return target[prop];
          }
        });
      });
    `);

    // Refresh the page to trigger CAPTCHA with our injected code
    await page.reload({ waitUntil: "networkidle2" });

    // Wait for CAPTCHA parameters to be extracted
    let params = null;
    for (let i = 0; i < 30; i++) {
      params = await page.evaluate(() => window.params || null);
      if (params) break;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    if (!params) {
      console.log("❌ Could not extract CAPTCHA parameters");
      return false;
    }

    console.log("✅ CAPTCHA Params extracted:", params);

    // Create CAPTCHA solving task
    const taskPayload = {
      clientKey: CAPMONSTER_API_KEY,
      task: {
        type: "TurnstileTask",
        websiteURL: params.websiteURL,
        websiteKey: params.websiteKey,
        cloudflareTaskType: "token",
        userAgent: params.userAgent,
        pageAction: params.pageAction,
        pageData: params.pageData,
        data: params.data,
      },
    };

    const createTaskRes = await fetch(
      "https://api.capmonster.cloud/createTask",
      {
        method: "POST",
        body: JSON.stringify(taskPayload),
        headers: { "Content-Type": "application/json" },
      }
    );

    const taskJson = await createTaskRes.json();
    console.log("🎯 Task Created:", taskJson);

    if (!taskJson.taskId) {
      throw new Error("❌ Failed to create task: " + JSON.stringify(taskJson));
    }

    // Poll for CAPTCHA solution
    const pollResult = async () => {
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 5000));

        const res = await fetch("https://api.capmonster.cloud/getTaskResult", {
          method: "POST",
          body: JSON.stringify({
            clientKey: CAPMONSTER_API_KEY,
            taskId: taskJson.taskId,
          }),
          headers: { "Content-Type": "application/json" },
        });

        const json = await res.json();
        console.log(`⏳ Polling (${i + 1}/40):`, json.status);

        if (json.status === "ready") return json.solution.token;
        if (json.errorId) throw new Error("❌ Error: " + JSON.stringify(json));
      }
      throw new Error("❌ Timed out waiting for CAPTCHA solve");
    };

    const token = await pollResult();
    console.log("✅ CAPTCHA Solved. Token:", token);

    // Inject the token
    await page.evaluate((token) => {
      if (window.turnstileCallback) {
        window.turnstileCallback(token);
      }
      
      // Also try to find and fill any hidden input fields
      const hiddenInputs = document.querySelectorAll('input[type="hidden"]');
      hiddenInputs.forEach(input => {
        if (input.name && (input.name.includes('captcha') || input.name.includes('token') || input.name.includes('turnstile'))) {
          input.value = token;
        }
      });
      
      // Try to trigger any form submission if present
      const forms = document.querySelectorAll('form');
      forms.forEach(form => {
        const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitButton) {
          submitButton.click();
        }
      });
    }, token);

    console.log("✅ Token injected into page!");
    
    // Wait longer for the token to be processed
    await new Promise((resolve) => setTimeout(resolve, 5000));
    
    // Check if CAPTCHA is still present after token injection
    const stillHasCaptcha = await page.evaluate(() => {
      const indicators = [];
      if (document.querySelector("[data-sitekey]")) indicators.push("turnstile_widget");
      const captchaTexts = [
        "Help Us Protect Glassdoor",
        "Verify you are human",
        "Cloudflare",
        "Turnstile",
        "Please complete the security check",
      ];
      captchaTexts.forEach((text) => {
        if (document.body.innerText.includes(text)) indicators.push(`text_${text}`);
      });
      return indicators.length > 0;
    });
    
    if (stillHasCaptcha) {
      console.log("⚠️ CAPTCHA still present after token injection, waiting longer...");
      await new Promise((resolve) => setTimeout(resolve, 80000));
      
      // Check again
      const stillHasCaptcha2 = await page.evaluate(() => {
        const indicators = [];
        if (document.querySelector("[data-sitekey]")) indicators.push("turnstile_widget");
        const captchaTexts = [
          "Help Us Protect Glassdoor",
          "Verify you are human",
          "Cloudflare",
          "Turnstile",
          "Please complete the security check",
        ];
        captchaTexts.forEach((text) => {
          if (document.body.innerText.includes(text)) indicators.push(`text_${text}`);
        });
        return indicators.length > 0;
      });
      
      if (stillHasCaptcha2) {
        console.log("❌ CAPTCHA still present after extended wait, token may be invalid");
        return { success: false, newPage: null };
      }
    }

    console.log("✅ CAPTCHA successfully solved and verified!");

    // After CAPTCHA solving, try to continue with current page first
    const currentUrl = page.url();
    console.log("🔄 Checking if current page is ready after CAPTCHA solving...");

    // Wait a bit more to ensure the page is fully loaded
    await new Promise((resolve) => setTimeout(resolve, 3000));
    
    // Check if the current page is working properly
    const pageIsReady = await page.evaluate(() => {
      const captchaTexts = [
        "Help Us Protect Glassdoor",
        "Verify you are human",
        "Cloudflare",
        "Turnstile",
        "Please complete the security check",
      ];
      
      const hasCaptchaText = captchaTexts.some(text => 
        document.body.innerText.includes(text)
      );
      
      return !hasCaptchaText && !document.querySelector('[data-sitekey]');
    });
    
    if (pageIsReady) {
      console.log("✅ Current page is ready, continuing with it");
      return { success: true, newPage: page };
    } else {
      console.log("⚠️ Current page still has issues, opening fresh tab...");
      
      // Create new tab as fallback
      const newPage = await page.browser().newPage();

      // Apply the same stealth settings to new page
      await newPage.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
      );
      await newPage.setViewport({ width: 1280, height: 800 });

      // Hide automation detection in new page
      await newPage.evaluateOnNewDocument(() => {
        Object.defineProperty(navigator, "webdriver", {
          get: () => undefined,
        });
        delete navigator.__proto__.webdriver;
        Object.defineProperty(navigator, "plugins", {
          get: () => [1, 2, 3, 4, 5],
        });
        Object.defineProperty(navigator, "languages", {
          get: () => ["en-US", "en"],
        });
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
          parameters.name === "notifications"
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);

        // Additional stealth measures
        Object.defineProperty(navigator, 'hardwareConcurrency', {
          get: () => 8,
        });

        Object.defineProperty(navigator, 'deviceMemory', {
          get: () => 8,
        });

        Object.defineProperty(navigator, 'platform', {
          get: () => 'Win32',
        });

        // Remove automation indicators
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

        // Override chrome runtime
        if (window.chrome) {
          Object.defineProperty(window.chrome, 'runtime', {
            get: () => undefined,
          });
        }

        // Override permissions
        const originalGetUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia;
        if (originalGetUserMedia) {
          navigator.getUserMedia = originalGetUserMedia.bind(navigator);
        }
      });

      // Navigate to the same URL in new tab
      await newPage.goto(currentUrl, { waitUntil: "networkidle2" });

      // Close the old tab
      await page.close();

      // Return the new page reference
      return { success: true, newPage };
    }
  } catch (error) {
    console.error("❌ CAPTCHA solving failed:", error);
    return { success: false, newPage: null };
  }
}

async function checkAndSolveCaptcha(page) {
  // Check for CAPTCHA indicators
  const captchaIndicators = await page.evaluate(() => {
    const indicators = [];
    if (document.querySelector("[data-sitekey]"))
      indicators.push("turnstile_widget");
    const captchaTexts = [
      "Help Us Protect Glassdoor",
      "Verify you are human",
      "Cloudflare",
      "Turnstile",
      "Please complete the security check",
    ];
    captchaTexts.forEach((text) => {
      if (document.body.innerText.includes(text))
        indicators.push(`text_${text}`);
    });
    if (
      document.querySelector('iframe[src*="cloudflare"]') ||
      document.querySelector('iframe[src*="turnstile"]')
    )
      indicators.push("captcha_iframe");
    return indicators;
  });

  if (captchaIndicators.length === 0) {
    return { success: true, newPage: page }; // No CAPTCHA
  }

  console.log("🔒 CAPTCHA detected, attempting to solve...");
  
  // Try to solve CAPTCHA up to 3 times
  for (let attempt = 1; attempt <= 3; attempt++) {
    console.log(`🔄 CAPTCHA solving attempt ${attempt}/3`);
    
    const result = await solveCaptcha(page);
    if (result.success) {
      console.log(`✅ CAPTCHA solved successfully on attempt ${attempt}`);
      return result;
    } else {
      console.log(`❌ CAPTCHA solving failed on attempt ${attempt}`);
      if (attempt < 3) {
        console.log("⏳ Waiting 5 seconds before retry...");
        await new Promise(resolve => setTimeout(resolve, 5000));
      }
    }
  }
  
  console.log("❌ All CAPTCHA solving attempts failed");
  return { success: false, newPage: null };
}

async function updateCRM(company, gdurl) {
  const encodedFormula = encodeURIComponent(`{Company Name}='${company}'`);
  const url = `${AIRTABLE_URL}?filterByFormula=${encodedFormula}`;
  const response = await axios.get(url, { headers: HEADERS });
  if (response.data.records && response.data.records.length > 0) {
    const recordId = response.data.records[0].id;
    const data = { fields: { "Glassdoor URL": gdurl } };
    const patchUrl = `${AIRTABLE_URL}/${recordId}`;
    await axios.patch(patchUrl, data, { headers: POST_HEADERS });
    console.log(`Updated Airtable for ${company}`);
  } else {
    const data = {
      fields: { "Company Name": company, "Glassdoor URL": gdurl },
    };
    await axios.post(AIRTABLE_URL, data, { headers: POST_HEADERS });
    console.log(`Created new record in Airtable for ${company}`);
  }
}

async function searchGlassdoorUrl(page, company, website) {
  try {
    await page.goto("https://www.glassdoor.com/Reviews/index.htm", {
      waitUntil: "networkidle2",
    });

    // Check for CAPTCHA after navigation to search page
    const captchaResult1 = await checkAndSolveCaptcha(page);
    if (!captchaResult1.success) {
      console.log(
        `❌ CAPTCHA solving failed for ${company} search. Skipping...`
      );
      return null;
    }
    // Use new page if CAPTCHA solving created one
    if (captchaResult1.newPage !== page) {
      page = captchaResult1.newPage;
    }

    const domain = filterDomain(website);
    await page.waitForSelector('input[name="typedKeyword"]', {
      timeout: 10000,
    });
    await page.type('input[name="typedKeyword"]', domain, { delay: 100 });
    await new Promise((resolve) => setTimeout(resolve, 3000));

    // Check for CAPTCHA after typing search term
    const captchaResult2 = await checkAndSolveCaptcha(page);
    if (!captchaResult2.success) {
      console.log(
        `❌ CAPTCHA solving failed after search input for ${company}. Skipping...`
      );
      return null;
    }
    // Use new page if CAPTCHA solving created one
    if (captchaResult2.newPage !== page) {
      page = captchaResult2.newPage;
    }

    await page.waitForSelector("#employer-autocomplete-search-suggestions li", {
      timeout: 10000,
    });
    await page.click("#employer-autocomplete-search-suggestions li");
    await new Promise((resolve) => setTimeout(resolve, 3000));

    // Check for CAPTCHA after clicking search suggestion
    const captchaResult3 = await checkAndSolveCaptcha(page);
    if (!captchaResult3.success) {
      console.log(
        `❌ CAPTCHA solving failed after search selection for ${company}. Skipping...`
      );
      return null;
    }
    // Use new page if CAPTCHA solving created one
    if (captchaResult3.newPage !== page) {
      page = captchaResult3.newPage;
    }

    const fullUrl = page.url();
    console.log(`Autocomplete Glassdoor URL: ${fullUrl}`);
    return fullUrl;
  } catch (e) {
    console.log(`Glassdoor search failed for ${company}: ${e}`);
    return null;
  }
}

function xpathText(tree, selector) {
  const el = tree.querySelector(selector);
  return el ? el.text.trim() : null;
}

async function scrapeDataAndUpdate(
  page,
  company,
  gdurl,
  alreadyOnPage = false
) {
  if (!alreadyOnPage) {
    await page.goto(gdurl, { waitUntil: "networkidle2" });
    
    // Check for CAPTCHA after navigating to company page
    const captchaResult = await checkAndSolveCaptcha(page);
    if (!captchaResult.success) {
      console.log(`❌ CAPTCHA solving failed for ${company} page. Skipping...`);
      return;
    }
    // Use new page if CAPTCHA solving created one
    if (captchaResult.newPage !== page) {
      page = captchaResult.newPage;
    }
  }
  
  await new Promise((resolve) => setTimeout(resolve, 10000));
  const pageSource = await page.content();
  const tree = parse(pageSource);

  // These selectors may need adjustment based on actual HTML
  const totalReviews = xpathText(tree, ".review-overview_reviewCount__hQpzR");
  const companyRating = xpathText(
    tree,
    ".rating-headline-average_rating__J5rIy"
  );
  const engagedStatus = xpathText(
    "#__next > div > div:nth-child(1) > div > main > div > div:nth-child(1) > div:nth-child(3) > div:nth-child(2) > div > span > p"
  );
  const engagedEmployer =
    engagedStatus && engagedStatus.includes("Engaged") ? "Yes" : "No";
  let gd_id = "";
  if (gdurl.includes("EI_IE")) {
    try {
      gd_id = gdurl.split("EI_IE")[1].split(".")[0];
    } catch {}
  }
  let totalReviewsNum = 0;
  if (totalReviews) {
    const match = totalReviews.match(/\((\d+)\)/);
    if (match) totalReviewsNum = parseInt(match[1], 10);
  }
  const data = {
    fields: {
      "Glassdoor URL": gdurl,
      "Glassdoor ID": gd_id,
      "GD Overall Review": companyRating ? parseFloat(companyRating) : null,
      "GD # of Reviews (Overall)": totalReviewsNum,
      "Glassdoor Engaged": engagedEmployer,
    },
  };
  const encodedFormula = encodeURIComponent(`{Company Name}='${company}'`);
  const res = await axios.get(
    `${AIRTABLE_URL}?filterByFormula=${encodedFormula}`,
    { headers: HEADERS }
  );
  if (res.data.records && res.data.records.length > 0) {
    const recordId = res.data.records[0].id;
    const patchUrl = `${AIRTABLE_URL}/${recordId}`;
    await axios.patch(patchUrl, data, { headers: POST_HEADERS });
    console.log(`Airtable updated for ${company}`);
  } else {
    data.fields["Company Name"] = company;
    await axios.post(AIRTABLE_URL, data, { headers: POST_HEADERS });
    console.log(`Airtable record created for ${company}`);
  }
}

async function loadAndApplyCookies(page) {
  try {
    const cookiesPath = path.join(__dirname, "glassdoor_cookies.json");
    if (!fs.existsSync(cookiesPath)) {
      console.log("❌ Cookies file not found");
      return false;
    }

    const cookiesData = JSON.parse(fs.readFileSync(cookiesPath, "utf8"));
    await page.setCookie(...cookiesData);
    console.log("✅ Cookies loaded and applied");
    return true;
  } catch (error) {
    console.log("❌ Error loading cookies:", error);
    return false;
  }
}

async function checkIfLoggedIn(page) {
  try {
    // Check for common logged-in indicators
    const loggedInIndicators = await page.evaluate(() => {
      const indicators = [];

      // Check for user avatar/profile elements
      if (
        document.querySelector('[data-test="user-avatar"]') ||
        document.querySelector(".user-avatar") ||
        document.querySelector('[data-test="profile-dropdown"]')
      ) {
        indicators.push("user_avatar");
      }

      // Check for logout button
      if (
        document.querySelector('[data-test="logout-button"]') ||
        document.querySelector('a[href*="logout"]')
      ) {
        indicators.push("logout_button");
      }

      // Check for user menu
      if (
        document.querySelector('[data-test="user-menu"]') ||
        document.querySelector(".user-menu")
      ) {
        indicators.push("user_menu");
      }

      // Check if login form is NOT present (indicates logged in)
      if (
        !document.querySelector("#inlineUserEmail") &&
        !document.querySelector('input[type="password"]')
      ) {
        indicators.push("no_login_form");
      }

      return indicators;
    });

    console.log("🔍 Login status indicators:", loggedInIndicators);
    return loggedInIndicators.length > 0;
  } catch (error) {
    console.log("❌ Error checking login status:", error);
    return false;
  }
}

async function main() {
  const companies = await loadCompaniesFromCSV(
    path.join(__dirname, "unmatched_companies.csv")
  );
  console.log(`Loaded ${companies.length} companies from CSV`);

  // Launch browser in headless mode
  const browser = await puppeteer.launch({
    headless: false,
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', // Use system Chrome
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-accelerated-2d-canvas",
      "--no-first-run",
      "--no-zygote",
      "--disable-gpu",
      "--disable-blink-features=AutomationControlled",
      "--disable-web-security",
      "--disable-features=VizDisplayCompositor",
      "--disable-extensions",
      "--disable-plugins",
      "--disable-default-apps",
      "--disable-sync",
      "--disable-translate",
      "--hide-scrollbars",
      "--mute-audio",
      "--no-default-browser-check",
      "--no-experiments",
      "--disable-background-timer-throttling",
      "--disable-backgrounding-occluded-windows",
      "--disable-renderer-backgrounding",
      "--disable-features=TranslateUI",
      "--disable-ipc-flooding-protection",
      "--disable-blink-features=AutomationControlled",
      "--disable-automation",
      "--disable-infobars",
      "--disable-notifications",
      "--disable-popup-blocking",
      "--disable-save-password-bubble",
      "--disable-single-click-autofill",
      "--disable-translate-new-ux",
      "--disable-web-security",
      "--disable-xss-auditor",
      "--no-default-browser-check",
      "--no-first-run",
      "--no-pings",
      "--no-zygote",
      "--password-store=basic",
      "--use-mock-keychain",
    ],
  });

  const page = await browser.newPage();

  // Hide automation detection
  await page.evaluateOnNewDocument(() => {
    // Remove webdriver property
    Object.defineProperty(navigator, "webdriver", {
      get: () => undefined,
    });

    // Remove automation properties
    delete navigator.__proto__.webdriver;

    // Override plugins
    Object.defineProperty(navigator, "plugins", {
      get: () => [1, 2, 3, 4, 5],
    });

    // Override languages
    Object.defineProperty(navigator, "languages", {
      get: () => ["en-US", "en"],
    });

    // Override permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
      parameters.name === "notifications"
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);

    // Additional stealth measures
    Object.defineProperty(navigator, 'hardwareConcurrency', {
      get: () => 8,
    });

    Object.defineProperty(navigator, 'deviceMemory', {
      get: () => 8,
    });

    Object.defineProperty(navigator, 'platform', {
      get: () => 'Win32',
    });

    // Remove automation indicators
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

    // Override chrome runtime
    if (window.chrome) {
      Object.defineProperty(window.chrome, 'runtime', {
        get: () => undefined,
      });
    }

    // Override permissions
    const originalGetUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia;
    if (originalGetUserMedia) {
      navigator.getUserMedia = originalGetUserMedia.bind(navigator);
    }
  });

  // Set user agent and viewport
  await page.setUserAgent(
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
  );
  await page.setViewport({ width: 1280, height: 800 });

  // Step 1: Try cookie-based login first
  console.log("🍪 Attempting cookie-based login...");
  const cookiesLoaded = await loadAndApplyCookies(page);

  if (cookiesLoaded) {
    // Navigate to Glassdoor with cookies
    await page.goto("https://www.glassdoor.com/index.htm", {
      waitUntil: "networkidle2",
    });

    // Check for CAPTCHA after navigation
    const captchaResult = await checkAndSolveCaptcha(page);
    if (!captchaResult.success) {
      console.log("❌ CAPTCHA solving failed. Exiting...");
      await browser.close();
      return;
    }
    // Use new page if CAPTCHA solving created one
    if (captchaResult.newPage !== page) {
      page = captchaResult.newPage;
    }

    // Check if login was successful
    const isLoggedIn = await checkIfLoggedIn(page);

    if (isLoggedIn) {
      console.log("✅ Successfully logged in using cookies!");
      await page.screenshot({
        path: "downloaded_files/glassdoor_logged_in_cookies.png",
      });
    } else {
      console.log("❌ Cookie login failed, trying manual login...");
      await manualLogin(page);
    }
  } else {
    console.log("❌ Could not load cookies, trying manual login...");
    await manualLogin(page);
  }

  // Check for session timeout message
  // const sessionTimeout = await page.$x("//*[contains(text(), 'session has timed out')]");
  // if (sessionTimeout.length > 0) {
  //   console.log('Session timed out. Try again or check for CAPTCHA.');
  //   await page.screenshot({ path: 'session_timeout.png' });
  // }

  for (const record of companies) {
    const company = record["Company Name"];
    const website = record["Website"];
    if (!website) {
      console.log(`No website for ${company}`);
      continue;
    }

    // Check for CAPTCHA before processing each company
    const captchaResult = await checkAndSolveCaptcha(page);
    if (!captchaResult.success) {
      console.log(`❌ CAPTCHA solving failed for ${company}. Skipping...`);
      continue;
    }
    // Use new page if CAPTCHA solving created one
    if (captchaResult.newPage !== page) {
      page = captchaResult.newPage;
    }

    const gdurl = await searchGlassdoorUrl(page, company, website);
    if (gdurl) {
      await scrapeDataAndUpdate(page, company, gdurl, true);
    } else {
      console.log(`Skipping ${company} — Glassdoor URL not found.`);
    }
  }
  await browser.close();
}

async function manualLogin(page) {
  console.log("🔐 Attempting manual login...");

  // Navigate to login page
  await page.goto("https://www.glassdoor.com/index.htm", {
    waitUntil: "networkidle2",
  });

  // Check for CAPTCHA after navigation
  const captchaResult = await checkAndSolveCaptcha(page);
  if (!captchaResult.success) {
    console.log("❌ CAPTCHA solving failed. Exiting...");
    throw new Error("CAPTCHA solving failed");
  }
  // Use new page if CAPTCHA solving created one
  if (captchaResult.newPage !== page) {
    page = captchaResult.newPage;
  }

  await page.screenshot({
    path: "downloaded_files/glassdoor_page_before_login.png",
  });

  // Step 1: Enter email and click continue
  await page.waitForSelector("#inlineUserEmail", { timeout: 10000 });
  await page.type("#inlineUserEmail", GLASSDOOR_LOGIN_EMAIL, { delay: 100 });

  // Click continue button
  try {
    const continueButton =
      (await page.$('button[type="submit"]')) ||
      (await page.$('input[type="submit"]')) ||
      (await page.$('[data-test="email-continue-button"]'));

    if (continueButton) {
      await continueButton.click();
      console.log("✅ Clicked continue button");
    } else {
      await page.keyboard.press("Enter");
      console.log("✅ Pressed Enter to continue");
    }

    await new Promise((resolve) => setTimeout(resolve, 3000));

    // Check for CAPTCHA after email submission
    const captchaResult2 = await checkAndSolveCaptcha(page);
    if (!captchaResult2.success) {
      console.log("❌ CAPTCHA solving failed after email. Exiting...");
      throw new Error("CAPTCHA solving failed after email");
    }
    // Use new page if CAPTCHA solving created one
    if (captchaResult2.newPage !== page) {
      page = captchaResult2.newPage;
    }

    // Step 2: Enter password and sign in
    await page.waitForSelector('input[type="password"]', { timeout: 10000 });
    await page.type('input[type="password"]', GLASSDOOR_PASSWORD, {
      delay: 100,
    });

    const signInButton =
      (await page.$('button[type="submit"]')) ||
      (await page.$('input[type="submit"]')) ||
      (await page.$('[data-test="sign-in-button"]'));

    if (signInButton) {
      await signInButton.click();
      console.log("✅ Clicked sign in button");
    } else {
      await page.keyboard.press("Enter");
      console.log("✅ Pressed Enter to sign in");
    }

    await new Promise((resolve) => setTimeout(resolve, 5000));

    // Check for CAPTCHA after password submission
    const captchaResult3 = await checkAndSolveCaptcha(page);
    if (!captchaResult3.success) {
      console.log("❌ CAPTCHA solving failed after password. Exiting...");
      throw new Error("CAPTCHA solving failed after password");
    }
    // Use new page if CAPTCHA solving created one
    if (captchaResult3.newPage !== page) {
      page = captchaResult3.newPage;
    }
  } catch (error) {
    console.log("❌ Error during manual login process:", error);
    await page.keyboard.press("Enter");
  }

  await page.screenshot({
    path: "downloaded_files/glassdoor_page_after_login.png",
  });

  // Verify login was successful
  const isLoggedIn = await checkIfLoggedIn(page);
  if (!isLoggedIn) {
    throw new Error("Manual login failed");
  }

  console.log("✅ Manual login successful!");
}

main().catch(console.error);
