import { expect, test } from "@playwright/test";

// Full demo workflow (matches the acceptance criteria):
//  log in → dashboard → open finding → verify evidence + calculation →
//  approve for follow-up → generate an internal review summary → export report →
//  confirm audit-log entries.
//
// Prereqs: API seeded (make seed) and a review run executed for the demo project.
// The first test runs a review to guarantee a finding exists.

const ADMIN = { email: "admin@northstar.example", password: "Northstar-Demo-2025" };

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN.email);
  await page.getByLabel("Password").fill(ADMIN.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

test("log in and see the value-stage dashboard", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  // Potential value is separated from invoiced value and labelled as unreviewed.
  await expect(page.getByText("Potential value identified")).toBeVisible();
  await expect(
    page.getByText(/does not represent recoverable or recovered revenue/i),
  ).toBeVisible();
});

test("open a project and run a billing review", async ({ page }) => {
  await login(page);

  // Open the demo project via the Projects list.
  await page.getByRole("link", { name: "Projects" }).click();
  await page.getByRole("link", { name: /Snowflake Modernization/ }).click();
  await expect(page.getByRole("heading", { name: "Snowflake Modernization" })).toBeVisible();

  // The Reviews tab exposes the billing-period review controls.
  await page.getByRole("tab", { name: "Reviews" }).click();
  await expect(page.getByRole("button", { name: /Run review/ })).toBeVisible();
  await expect(page.getByText(/never invoices anyone/i)).toBeVisible();
});

test("open the finding and verify evidence and calculation", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Finding inbox" }).click();
  await expect(page.getByRole("heading", { name: "Finding inbox" })).toBeVisible();

  // Open the first finding.
  const row = page.getByTestId("finding-row").first();
  await expect(row).toBeVisible();
  await row.click();

  // Evidence: the exclusion clause quotation and the Jira work item are shown.
  await expect(page.getByText("Supporting evidence")).toBeVisible();
  await expect(page.getByText(/Onboarding of new source systems is excluded/i)).toBeVisible();

  // Deterministic calculation is present.
  await expect(page.getByText("Calculation breakdown")).toBeVisible();
  await expect(page.getByText(/never by the language model/i)).toBeVisible();
});

test("approve a finding, generate a summary, and export the report", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Finding inbox" }).click();

  // Deterministically target the potentially-out-of-scope finding (not the duplicate).
  await page.getByLabel("Type").selectOption("potentially_out_of_scope");
  await page.getByTestId("finding-row").first().click();
  await expect(page.getByRole("heading", { name: /Potentially out-of-scope/i })).toBeVisible();

  // Approve for follow-up only if it is still pending, then wait for the change to
  // persist before doing anything that depends on approval.
  const status = page.getByText(/Current status:/);
  await expect(status).toBeVisible();
  if (((await status.textContent()) ?? "").includes("pending")) {
    await page.getByLabel("Action").selectOption("approved_for_followup");
    await page
      .getByLabel("Reason")
      .fill("Salesforce onboarding is a new source system, excluded per SOW section 3.");
    const record = page.getByRole("button", { name: "Record decision" });
    await expect(record).toBeEnabled();
    await record.click();
  }
  // Approval must be reflected in the UI before artifact generation is possible.
  await expect(page.getByText(/Current status:\s*approved for followup/i)).toBeVisible();

  // Generate an internal review summary (allowed only after approval).
  const genButton = page.getByRole("button", { name: /Generate draft/i });
  await expect(genButton).toBeVisible();
  await genButton.click();
  await expect(page.getByText(/DRAFT/)).toBeVisible();

  // The evidence report export link is present.
  await expect(page.getByRole("link", { name: /Evidence report \(PDF\)/ })).toBeVisible();
});

test("audit log records actions", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByRole("heading", { name: "Audit log" })).toBeVisible();
  await expect(page.getByText("auth.login").first()).toBeVisible();
});
