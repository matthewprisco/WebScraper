// solve_turnstile.js
import fetch from "node-fetch";
import chrome from "selenium-webdriver/chrome.js";
import { Builder, By, until } from "selenium-webdriver";
import { Parser } from "json2csv";
import fs from "fs";

(async function () {
  const options = new chrome.Options();
  // options.addArguments("--headless");
  options.addArguments("--disable-blink-features=AutomationControlled");
  options.addArguments("--no-sandbox");
  options.addArguments("--disable-dev-shm-usage");

  const driver = await new Builder()
    .forBrowser("chrome")
    .setChromeOptions(options)
    .build();

  const TARGET_URL =
    "https://www.crunchbase.com/organization/vista-equity-partners/recent_investments/investments";
  let params = null;
  try {
    while (!params) {
      await driver.get(TARGET_URL);

      await driver.executeScript(`
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

      params = await driver.executeAsyncScript(`
        const callback = arguments[arguments.length - 1];
        setTimeout(() => {
          callback(window.params || null);
        }, 5000);
      `);

      if (!params) {
        console.log("🔁 Params not captured, retrying...");
        const image = await driver.takeScreenshot();

        // Save it to a file
        fs.writeFileSync("screenshot.png", image, "base64");

        console.log("📸 Screenshot saved as screenshot.png");
        await driver.sleep(3000);
      }
    }

    console.log("✅ CAPTCHA Params:", params);

    const taskPayload = {
      clientKey: "96bbcafeaf0ccb14cf7c2f0d813fb476",
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

    const taskId = taskJson.taskId;

    const pollResult = async () => {
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 5000));

        const res = await fetch("https://api.capmonster.cloud/getTaskResult", {
          method: "POST",
          body: JSON.stringify({ clientKey: taskPayload.clientKey, taskId }),
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

    await driver.executeScript(`window.turnstileCallback('${token}');`);
    console.log("✅ Token injected into page!");

    // Wait to proceed or scrape as needed
    await driver.sleep(10);

    console.log("✅ CAPTCHA solved. You may now run the Python scraper.");

    await driver.wait(
      until.elementsLocated(By.xpath("//table/tbody/tr")),
      40000
    );
    const rows = await driver.findElements(By.xpath("//table/tbody/tr"));
    console.log(`📊 Found ${rows.length} rows in the data table.`);
    console.log(`📊 Found ${rows} rows in the data table.`);

    const scraped = [];

    for (let i = 0; i < 5; i++) {
      try {
        // Re-locate the row in each iteration to avoid stale reference
        const rowsRefreshed = await driver.findElements(
          By.xpath("//table/tbody/tr")
        );
        const row = rowsRefreshed[i];

        const columns = await row.findElements(By.tagName("td"));
        if (!columns.length) continue;

        const announced_date = await columns[0].getText();
        const org_name = await columns[1].getText();
        const org_link_elem = await columns[1].findElement(By.tagName("a"));
        const org_url = await org_link_elem.getAttribute("href");
        const lead_investor = await columns[2].getText();
        const funding_round = await columns[3].getText();
        const money_raised = await columns[4].getText();

        // Open org page in new tab
        await driver.executeScript("window.open('');");
        const handles = await driver.getAllWindowHandles();
        await driver.switchTo().window(handles[1]);
        await driver.get(org_url);
        await driver.sleep(5000);

        let website_url = "";
        try {
          const website_elem = await driver.findElement(
            By.xpath(
              '//a[contains(@href, "http") and contains(@title, "www.")]'
            )
          );
          website_url = await website_elem.getAttribute("href");
        } catch (e) {}

        const social_links = [];
        try {
          const social_elems = await driver.findElements(
            By.xpath('//span[contains(@class,"social-link-icons")]//a')
          );
          for (const s of social_elems) {
            const href = await s.getAttribute("href");
            if (href) social_links.push(href);
          }
        } catch (e) {}

        // Close tab
        await driver.close();
        await driver.switchTo().window(handles[0]);

        scraped.push({
          "Announced Date": announced_date,
          "Organization Name": org_name,
          "Organization URL": org_url,
          "Website URL": website_url,
          "Social Media Links": social_links.join(", "),
          "Lead Investor": lead_investor,
          "Funding Round": funding_round,
          "Money Raised": money_raised,
        });
      } catch (err) {
        console.error("❌ Error in row:", err.message);
      }
    }
    // Save to CSV
    const parser = new Parser();
    const csv = parser.parse(scraped);
    fs.writeFileSync("vista_extended_funding_data.csv", csv);
    console.log("✅ Data saved to vista_extended_funding_data.csv");
  } catch (err) {
    console.error("❌ Error:", err);
  }
})();
