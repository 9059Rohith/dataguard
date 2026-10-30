// Optional visual evidence: requires Playwright in NODE_PATH (not a service dependency).
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless: true});
  const checks = [];
  for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
    const page = await browser.newPage({viewport});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
    await page.goto('http://127.0.0.1:8003/');
    await page.locator('#health').filter({hasText:'SQL CONNECTED'}).waitFor();
    assert.match(await page.title(), /DataGuard/);
    assert.equal(await page.locator('h1').textContent(), 'Trust the published data.');
    const before = await page.locator('#published').textContent();
    await page.getByRole('button', {name:'Refresh state'}).click();
    await page.locator('#health').filter({hasText:'SQL CONNECTED'}).waitFor();
    assert.equal(await page.locator('#published').textContent(), before);
    assert.equal(await page.locator('#error').textContent(), '');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
    const file = `evidence/dashboard-${viewport.width}.png`;
    await page.screenshot({path:file, fullPage:true});
    checks.push({viewport, title:await page.title(), no_runtime_errors:true, no_horizontal_overflow:true,
                 live_sql_state:true, refresh_preserves_current_state:true, screenshot:file});
    await page.close();
  }
  await browser.close();
  fs.writeFileSync('evidence/dashboard-check.json', JSON.stringify({browser:'Chromium via Playwright 1.62.1',
      browser_plugin:'unavailable', flow:'Load dashboard → live SQL state → Refresh state → consistent displayed result', checks},null,2));
  console.log(JSON.stringify(checks,null,2));
})().catch(error => {console.error(error); process.exitCode = 1;});
