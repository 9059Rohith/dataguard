const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
    deviceScaleFactor: 1,
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  await page.goto(process.env.QUALITY_BASE_URL || "http://127.0.0.1:8013");
  await page
    .getByRole("heading", { name: "Good data. Clear evidence." })
    .waitFor();
  await page.screenshot({
    path: "evidence/quality-desktop.png",
    fullPage: true,
  });
  const routes = [
    "datasets",
    "contracts",
    "checks",
    "batches",
    "quarantine",
    "versions",
    "lineage",
    "incidents",
    "recovery",
    "agent",
    "connections",
    "settings",
  ];
  for (const route of routes) {
    await page.goto(
      (process.env.QUALITY_BASE_URL || "http://127.0.0.1:8013") +
        "/console/" +
        route,
    );
    await page.locator(".page-heading h1").waitFor();
    if (
      /[\u00c2]|\u00e2[\u20ac\u2020]/.test(
        await page.locator("body").innerText(),
      )
    )
      throw Error("Text encoding regression on " + route);
    if (
      await page.locator("body").evaluate((e) => e.scrollWidth > innerWidth + 1)
    )
      throw Error("Desktop overflow: " + route);
  }
  await page.goto(
    (process.env.QUALITY_BASE_URL || "http://127.0.0.1:8013") +
      "/console/datasets",
  );
  await page
    .getByRole("textbox", { name: "Search repository records" })
    .fill("fastapi");
  if ((await page.locator("tbody tr").count()) !== 1)
    throw Error("Search failed");
  await page
    .getByRole("button", { name: "Inspect record 1", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "fastapi/fastapi", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Close details", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Connect operator", exact: false })
    .click();
  await page.getByLabel("Operator token", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["overview", ...routes]) {
    await page.goto(
      (process.env.QUALITY_BASE_URL || "http://127.0.0.1:8013") +
        "/console/" +
        route,
    );
    await page.locator(".page-heading h1").waitFor();
    if (
      /[\u00c2]|\u00e2[\u20ac\u2020]/.test(
        await page.locator("body").innerText(),
      )
    )
      throw Error("Text encoding regression on " + route);
    if (
      await page.locator("body").evaluate((e) => e.scrollWidth > innerWidth + 1)
    )
      throw Error("Mobile overflow: " + route);
    if (route === "overview")
      await page.screenshot({
        path: "evidence/quality-mobile.png",
        fullPage: true,
      });
  }
  if (errors.length) throw Error(errors.join("; "));
  console.log(
    JSON.stringify({
      pages: 13,
      mobilePages: 13,
      search: "passed",
      recordInspection: "passed",
      accessDialog: "passed",
      errors,
    }),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
