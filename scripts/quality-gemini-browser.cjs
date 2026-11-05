const fs = require("fs");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const base =
  process.env.QUALITY_BASE_URL || "https://rohith-dataguard.vercel.app";
function operatorToken() {
  if (process.env.QUALITY_OPERATOR_TOKEN)
    return process.env.QUALITY_OPERATOR_TOKEN;
  const line = fs
    .readFileSync(".env.quality.local", "utf8")
    .split(/\r?\n/)
    .find((l) => l.startsWith("DATAGUARD_TOKEN="));
  if (!line)
    throw Error(
      "Operator credential is required for this authenticated verification.",
    );
  const value = line.slice(line.indexOf("=") + 1);
  return value.startsWith('"') ? JSON.parse(value) : value;
}
(async () => {
  const token = operatorToken();
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1100 },
    });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + "/console/agent");
    await page
      .getByRole("heading", { name: "Investigate, with evidence." })
      .waitFor();
    await page
      .getByRole("button", { name: "Connect operator", exact: false })
      .click();
    await page.getByLabel("Operator token", { exact: true }).fill(token);
    await page.getByRole("button", { name: "Connect securely" }).click();
    await page
      .locator("#profile-label")
      .filter({ hasText: "Connected operator" })
      .waitFor();
    await page
      .getByText(/^Google Gemini · gemini-3\.(?:5|1)-flash-lite$/)
      .waitFor();
    const question =
      "Inspect actual records in the latest public GitHub capture using inspect_capture. In concise plain text, identify the repository with the most stars and the repository with the most open issues, with exact counts, full capture ID, record count and SHA-256. Cite only observed evidence.";
    await page.getByLabel("Your investigation").fill(question);
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/quality/investigate") &&
        r.request().method() === "POST",
      { timeout: 120000 },
    );
    await page
      .getByRole("button", { name: "Investigate", exact: true })
      .click();
    const response = await pending;
    const result = await response.json();
    if (response.status() !== 200)
      throw Error("Live investigator failed with HTTP " + response.status());
    if (
      result.provider !== "Google Gemini" ||
      !["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"].includes(result.model) ||
      result.public_data_only !== true
    )
      throw Error("Wrong live provider or data scope.");
    if (
      !result.trace.some(
        (t) =>
          t.tool === "inspect_capture" &&
          t.result.visibility === "public" &&
          t.result.row_count === 8,
      )
    )
      throw Error("The model did not inspect the real public source records.");
    const capture = result.trace.find(
      (t) => t.tool === "inspect_capture" && t.result.id,
    ).result;
    if (!result.answer.includes(capture.id))
      throw Error("Final answer does not cite the capture actually inspected.");
    const encoded = JSON.stringify(result);
    if (
      encoded.includes(token) ||
      encoded.includes("thought_signature") ||
      encoded.includes("extra_content") ||
      /AIza[0-9A-Za-z_-]{20,}/.test(encoded)
    )
      throw Error("Sensitive provider material in public result.");
    await page
      .getByRole("heading", { name: "Investigation findings", exact: true })
      .waitFor();
    for (const field of ["stargazers_count", "open_issues_count"]) {
      const highest = capture.records.reduce((a, b) =>
        a[field] >= b[field] ? a : b,
      );
      if (
        !result.answer.includes(highest.full_name) ||
        !(
          result.answer.includes(String(highest[field])) ||
          result.answer.includes(highest[field].toLocaleString("en-US"))
        )
      ) {
        throw Error(
          "The model answer did not match the actual source maximum for " +
            field,
        );
      }
    }
    await page.locator("#toast").waitFor({ state: "hidden", timeout: 12000 });
    await page.screenshot({
      path: "evidence/quality-gemini-browser.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForFunction(
      () =>
        document.querySelector(".sidebar").getBoundingClientRect().right <= 0.5,
    );
    if (
      await page
        .locator("body")
        .evaluate((el) => el.scrollWidth > innerWidth + 1)
    )
      throw Error("Mobile investigator overflow");
    await page.screenshot({
      path: "evidence/quality-gemini-mobile.png",
      fullPage: true,
    });
    if (errors.length) throw Error(errors.join("; "));
    const evidence = {
      verified_at: new Date().toISOString(),
      base_url: base,
      http_status: response.status(),
      workflow:
        "Connect authenticated operator → ask about public GitHub records → actual Gemini evidence tools → cited model answer",
      question,
      result,
      browser_errors: errors,
    };
    fs.writeFileSync(
      "evidence/quality-gemini-browser.json",
      JSON.stringify(evidence, null, 2),
    );
    console.log(
      JSON.stringify({
        http_status: response.status(),
        provider: result.provider,
        model: result.model,
        tools: result.trace.map((t) => t.tool),
        provider_requests: result.provider_requests,
        record_count: capture.row_count,
        capture_id: capture.id,
        answer_chars: result.answer.length,
        errors,
      }),
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
