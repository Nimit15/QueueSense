const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1080 },
  });

  const consoleLogs = [];
  const consoleErrors = [];

  page.on('console', msg => {
    consoleLogs.push(`${msg.type()}: ${msg.text()}`);
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('pageerror', err => {
    consoleErrors.push(err.message);
  });

  console.log('Navigating to dashboard...');
  try {
    await page.goto('http://localhost:8000', { waitUntil: 'networkidle', timeout: 30000 });
    console.log('Page loaded successfully');

    // Wait for Three.js to initialize
    await page.waitForTimeout(5000);

    // Check console logs
    console.log('\n=== CONSOLE LOGS ===');
    consoleLogs.forEach(log => console.log(' ', log));

    // Check for canvas
    const canvas = await page.$('#scene-container canvas');
    if (canvas) {
      console.log('\nThree.js canvas found');
    } else {
      console.log('\nWARNING: Three.js canvas NOT found');
      const container = await page.$('#scene-container');
      if (container) {
        const html = await container.innerHTML();
        console.log('Container innerHTML:', html.substring(0, 500));
      }
    }

    // Take screenshot
    const screenshotPath = path.join(__dirname, 'results', 'dashboard_verify.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`\nScreenshot saved to: ${screenshotPath}`);

    const viewportPath = path.join(__dirname, 'results', 'dashboard_viewport.png');
    await page.screenshot({ path: viewportPath });
    console.log(`Viewport screenshot saved to: ${viewportPath}`);

    if (consoleErrors.length > 0) {
      console.log('\nConsole errors:');
      consoleErrors.forEach(e => console.log('  -', e));
    } else {
      console.log('\nNo console errors detected');
    }

    await browser.close();
    console.log('\nVerification complete');
  } catch (err) {
    console.error('Error during verification:', err.message);
    await browser.close();
    process.exit(1);
  }
})();