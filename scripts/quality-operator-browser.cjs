const fs = require("fs");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
(async () => {
  const b = await chromium.launch({ headless: true });
  try {
    const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    p.on("pageerror", (e) => errors.push(e.message));
    await p.goto(process.env.QUALITY_BASE_URL || "http://127.0.0.1:8013");
    await p.locator(".page-heading h1").waitFor();
    await p
      .getByRole("button", { name: "Connect operator", exact: false })
      .click();
    await p
      .getByLabel("Operator token", { exact: true })
      .fill("quality-local-verification-operator-0000000000");
    await p.getByRole("button", { name: "Connect securely" }).click();
    await p
      .locator("#profile-label")
      .filter({ hasText: "Connected operator" })
      .waitFor();
    await p.getByRole("link", { name: "Capture history", exact: true }).click();
    const records = JSON.parse(
      fs.readFileSync("dataguard/source_capture.json", "utf8"),
    ).records;
    await p
      .getByLabel("Capture name", { exact: true })
      .fill("Browser verification · actual GitHub source records");
    await p
      .getByLabel("Or paste your JSON records")
      .fill(JSON.stringify(records));
    await p.getByRole("button", { name: "Import & evaluate" }).click();
    await p.getByRole("heading", { name: "Know what flows in." }).waitFor();
    await p.getByRole("link", { name: "Contracts", exact: true }).click();
    await p.getByRole("button", { name: "Save contract" }).click();
    await p.getByRole("status").filter({ hasText: "Contract saved" }).waitFor();
    await p.getByRole("link", { name: "Quality checks", exact: true }).click();
    await p.getByRole("button", { name: "Re-evaluate capture" }).click();
    await p
      .getByRole("status")
      .filter({ hasText: "New evaluation created" })
      .waitFor();
    if ((await p.locator(".check-row").count()) !== 6)
      throw Error("Expected six quality results");
    await p.getByRole("link", { name: "Incidents", exact: true }).click();
    await p
      .getByLabel("Finding or follow-up")
      .fill(
        "Browser verification inspected actual GitHub source records and passed the stored quality checks.",
      );
    await p.getByRole("button", { name: "Save private note" }).click();
    await p
      .getByRole("status")
      .filter({ hasText: "Private investigation note saved" })
      .waitFor();
    await p.getByRole("link", { name: "Recovery", exact: true }).click();
    await p.getByRole("button", { name: "Validate & select" }).first().click();
    await p
      .getByRole("status")
      .filter({ hasText: "Recovery reference validated" })
      .waitFor();
    await p.getByRole("link", { name: "AI investigator", exact: true }).click();
    await p
      .getByLabel("Your investigation")
      .fill("Explain the freshness evidence in the actual captures.");
    await p.getByRole("button", { name: "Investigate", exact: true }).click();
    await p
      .locator("#agent-error")
      .filter({ hasText: "AI provider is not configured" })
      .waitFor();
    await p
      .getByRole("button", { name: "Disconnect operator", exact: false })
      .click();
    await p
      .locator("#profile-label")
      .filter({ hasText: "Public observer" })
      .waitFor();
    await p.goto(
      (process.env.QUALITY_BASE_URL || "http://127.0.0.1:8013") +
        "/console/incidents",
    );
    await p
      .getByRole("heading", { name: "Give issues a paper trail." })
      .waitFor();
    if (
      await p
        .getByText(
          "Browser verification inspected actual GitHub source records and passed the stored quality checks.",
          { exact: true },
        )
        .count()
    )
      throw Error("Private note leaked");
    if (errors.length) throw Error(errors.join("; "));
    console.log(
      JSON.stringify({
        operatorConnection: "passed",
        realSourceUpload: "passed",
        contractSave: "passed",
        recheck: "passed",
        privateNote: "passed",
        validatedRecovery: "passed",
        providerUnavailable: "explicit",
        disconnectAndPrivacy: "passed",
        errors,
      }),
    );
  } finally {
    await b.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
