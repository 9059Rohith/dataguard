"use strict";

// Run against a local or hosted console with an installed Playwright package.
const assert = require("node:assert/strict");
const { writeFileSync } = require("node:fs");
const { chromium } = require(
  process.env.DATAGUARD_PLAYWRIGHT_MODULE || "playwright",
);
const manifest = require("../dataguard/archive-manifest.json");

const base = process.env.DATAGUARD_BROWSER_URL || "http://127.0.0.1:55466";
const widths = [320, 390, 820, 1366, 1920];
const routes = manifest
  .filter((entry) => entry.placement === "hero")
  .map((entry) => entry.route);

async function verify() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.DATAGUARD_CHROME_PATH || undefined,
  });
  const page = await browser.newPage({ reducedMotion: "reduce" });
  const failures = [];
  const checked = [];
  const assets = new Set();
  page.on("pageerror", (error) => failures.push(error.message));
  page.on("requestfailed", (request) =>
    failures.push(request.url() + " " + request.failure()?.errorText),
  );
  page.on("response", (response) => {
    if (response.status() >= 400)
      failures.push(`${response.status()} ${response.url()}`);
  });

  try {
    for (const width of widths) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of routes) {
        await page.goto(`${base}/console/${route}`, {
          waitUntil: "domcontentloaded",
        });
        await page.locator(".archive-hero h1").waitFor();
        const frames = page.locator("[data-archive-art]");
        const expected = manifest.filter((entry) => entry.route === route);
        assert.equal(await frames.count(), expected.length, route);
        for (const entry of expected) {
          const frame = page.locator(`[data-archive-art="${entry.file}"]`);
          await frame.scrollIntoViewIfNeeded();
          const image = frame.locator("img");
          await image.evaluate((element) => element.decode());
          assert.equal(await image.getAttribute("alt"), "");
          assert.equal(
            await image.getAttribute("loading"),
            entry.placement === "hero" ? "eager" : "lazy",
          );
          assert.ok(await frame.isVisible());
          assets.add(entry.file);
        }
        const dimensions = await page.evaluate(() => ({
          client: document.documentElement.clientWidth,
          scroll: document.documentElement.scrollWidth,
        }));
        assert.equal(
          dimensions.client,
          dimensions.scroll,
          `${route} overflows at ${width}px`,
        );
        checked.push({ route, width, ...dimensions });
      }
    }
    assert.equal(assets.size, manifest.length);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${base}/console/overview`);
    const menu = page.getByRole("button", { name: "Open navigation" });
    await menu.click();
    assert.equal(await menu.getAttribute("aria-expanded"), "true");
    await page.keyboard.press("Escape");
    assert.equal(await menu.getAttribute("aria-expanded"), "false");
    assert.ok(
      await menu.evaluate((element) => document.activeElement === element),
    );

    await page.setViewportSize({ width: 1366, height: 900 });
    await page.goto(`${base}/console/checks`);
    const replay = page.getByRole("button", { name: "Replay source checks" });
    await replay.click();
    await page
      .getByRole("heading", { name: "Baseline replay · published" })
      .waitFor();
    await page.locator("#quality-benchmark-form select").selectOption("strict");
    await replay.click();
    await page
      .getByRole("heading", { name: "Strict replay · quarantined" })
      .waitFor();
    assert.ok(await page.getByText(/96 of 500 failed/).isVisible());
    assert.ok(await page.getByText(/177 of 500 failed/).isVisible());

    await page.goto(`${base}/console/impact`);
    await page.getByRole("button", { name: "Compare contracts" }).click();
    await page.locator(".impact-report").waitFor();
    await page.getByRole("link", { name: "Datasets", exact: true }).click();
    await page
      .getByRole("heading", { name: "Source register.", exact: true })
      .waitFor();
    await page.goBack();
    await page.getByRole("heading", { name: /Change the rule/ }).waitFor();

    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.goto(`${base}/console/overview`, {
      waitUntil: "domcontentloaded",
    });
    await page.locator(".archive-hero h1").waitFor();
    assert.ok(
      await page.evaluate(
        () =>
          document
            .querySelector(".archive-hero")
            .getAnimations({ subtree: true }).length > 0,
      ),
    );
    const scrollLinked = await page.evaluate(() =>
      CSS.supports("animation-timeline: scroll()"),
    );
    if (scrollLinked) {
      const start = await page
        .locator(".archive-scroll-rule")
        .evaluate((element) => getComputedStyle(element).transform);
      await page.evaluate(() =>
        window.scrollTo({ top: 420, behavior: "instant" }),
      );
      await page.waitForFunction(
        (initial) =>
          getComputedStyle(document.querySelector(".archive-scroll-rule"))
            .transform !== initial,
        start,
      );
    }
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.waitForFunction(
      () =>
        document.querySelector(".archive-hero").getAnimations({ subtree: true })
          .length === 0,
    );
    assert.equal(
      await page
        .locator("html")
        .evaluate((element) => getComputedStyle(element).scrollBehavior),
      "auto",
    );
    assert.ok(await page.locator(".archive-hero h1").isVisible());
    assert.deepEqual(failures, []);

    const evidence = {
      base,
      checked,
      distinctVisibleArtwork: assets.size,
      desktopPublicWorkflows: [
        "baseline/strict benchmark",
        "contract comparison",
        "route history",
      ],
      mobileKeyboardMenu: true,
      reducedMotion: true,
      scrollLinked,
      errors: failures,
    };
    if (process.env.DATAGUARD_BROWSER_EVIDENCE)
      writeFileSync(
        process.env.DATAGUARD_BROWSER_EVIDENCE,
        JSON.stringify(evidence, null, 2) + "\n",
      );
    if (process.env.DATAGUARD_BROWSER_SCREENSHOT) {
      await page.evaluate(() =>
        window.scrollTo({ top: 0, behavior: "instant" }),
      );
      await page
        .locator(".archive-plate img")
        .evaluate((image) => image.decode());
      await page.screenshot({
        path: process.env.DATAGUARD_BROWSER_SCREENSHOT,
        type: "jpeg",
        quality: 88,
      });
    }
    console.log(
      `${checked.length} viewport/route checks, ${assets.size} visible artworks, browser workflows and motion passed`,
    );
  } finally {
    await browser.close();
  }
}

verify().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
