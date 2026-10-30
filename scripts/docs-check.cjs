// Real Swagger UI check; requires Playwright in NODE_PATH, not in the service image.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
  const base = process.env.BASE_URL || 'http://127.0.0.1:18083';
  const checks = [];
  for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
    const page = await browser.newPage({viewport});
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      window.cspViolations = [];
      document.addEventListener('securitypolicyviolation', event => window.cspViolations.push({directive:event.effectiveDirective, blocked:event.blockedURI}));
    });
    const response = await page.goto(base + '/docs');
    await page.locator('.swagger-ui .info .title').waitFor({timeout:60000});
    const health = page.locator('.opblock').filter({has:page.locator('[data-path="/health"]')});
    await health.locator('.opblock-summary-control').click();
    await health.getByRole('button',{name:'Try it out'}).click();
    await health.getByRole('button',{name:'Execute',exact:true}).click();
    await health.locator('.response-col_status').filter({hasText:'200'}).first().waitFor();
    await health.locator('.live-responses-table').filter({hasText:'alive'}).waitFor();
    assert.deepEqual(await page.evaluate(() => window.cspViolations), []);
    assert.deepEqual(errors, []);
    const screenshot = `evidence/docs-${viewport.width}.png`;
    await page.screenshot({path:screenshot,fullPage:true});
    checks.push({viewport,title:await page.title(),swagger_rendered:true,health_execute_status:200,
      health_execute_body:'{"status":"alive"}',csp:response.headers()['content-security-policy'],
      csp_violations:[],console_errors:[],screenshot});
    await page.close();
  }
  const redocPage = await browser.newPage();
  const redocErrors = [];
  redocPage.on('console', message => { if(message.type() === 'error') redocErrors.push(message.text()); });
  redocPage.on('pageerror', error => redocErrors.push(error.message));
  await redocPage.goto(base + '/redoc');
  await redocPage.getByRole('heading',{name:/DataGuard/}).first().waitFor({timeout:60000});
  assert.deepEqual(redocErrors, []);
  const redoc = {rendered:true,console_errors:[]};
  await browser.close();
  const evidence = {generated_at:new Date().toISOString(),base,browser:'Chromium via Playwright 1.62.1',
    execution:'reproducible headless browser integration test',flow:'/docs → GET /health → Try it out → Execute → 200 alive',checks,redoc};
  fs.writeFileSync('evidence/docs-check.json',JSON.stringify(evidence,null,2));
  console.log(JSON.stringify(evidence,null,2));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
