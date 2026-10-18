import { expect, test, type Page } from "@playwright/test";

const SHOTS = process.env.E2E_SHOTS || "e2e-screenshots";
const OPERATOR_USER = process.env.E2E_OPERATOR_USER || "coordinator";
const OPERATOR_PASSWORD = process.env.E2E_OPERATOR_PASSWORD || "";

async function onboard(page: Page, name: string, email: string, place: string) {
  await page.goto("/onboarding");
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Email").fill(email);
  const addr = page.getByRole("textbox", { name: "Address or neighbourhood" });
  await addr.fill(place);
  await addr.press("Enter");
  await page.locator("ul li button").filter({ hasText: /Delhi/ }).first().click();
  await expect(page.getByText("Neighbourhood", { exact: true })).toBeVisible();
  await expect(page.locator("button.rounded-full").first()).toBeVisible();
  await page.getByRole("button", { name: /Continue as a resident/ }).last().click();
  await page.waitForURL((u) => !u.pathname.startsWith("/onboarding"));
}

test("two residents, a report, corroboration, coordinator approval and persistent memory", async ({ browser }) => {
  const a = await (await browser.newContext()).newPage();
  const b = await (await browser.newContext()).newPage();
  const stamp = Date.now().toString().slice(-5);
  const title = `E2E test report ${stamp}: waterlogging at Barakhamba crossing`;

  // Resident A onboards and reports
  await onboard(a, "E2E Resident A", `e2e-a-${stamp}@example.com`, "Barakhamba Road, New Delhi");
  await a.screenshot({ path: `${SHOTS}/01-home-resident.png`, fullPage: true });
  await a.goto("/report");
  await a.waitForLoadState("networkidle");
  await a.getByRole("button", { name: "Waterlogging" }).click();
  const loc = a.getByRole("textbox", { name: "Location" });
  await loc.fill("Barakhamba Road, New Delhi");
  await loc.press("Enter");
  await a.locator("ul li button").filter({ hasText: /Delhi/ }).first().click();
  await a.getByLabel("Title").fill(title);
  await a.getByLabel("What's happening?").fill("Clearly identified automated test submission — not a real-world incident. Used to verify the graph workflow.");
  await a.screenshot({ path: `${SHOTS}/02-report-form.png`, fullPage: true });
  await a.getByRole("button", { name: /Submit to CityPulse community/ }).click();
  await a.waitForURL(/\/issues\/iss_/);
  await expect(a.getByText("Submitted to the CityPulse community.").first()).toBeVisible();
  await expect(a.getByRole("heading", { name: "Related reports" })).toBeVisible();
  const issueUrl = a.url().split("?")[0];
  await a.screenshot({ path: `${SHOTS}/03-issue-detail.png`, fullPage: true });

  // Resident B, nearby, discovers it within the radius and corroborates
  await onboard(b, "E2E Resident B", `e2e-b-${stamp}@example.com`, "Connaught Place, New Delhi");
  await b.goto("/around-you");
  await b.waitForLoadState("networkidle");
  await b.getByRole("radio", { name: "3 km" }).click();
  const card = b.locator("div").filter({ has: b.getByRole("link", { name: title }) }).last();
  await expect(b.getByRole("link", { name: title })).toBeVisible();
  await b.screenshot({ path: `${SHOTS}/04-around-you.png`, fullPage: true });
  await card.getByRole("button", { name: /I'm affected too/ }).click();
  await expect(card.getByRole("button", { name: /You're affected/ })).toBeVisible();

  // Graph explorer shows resident -> issue -> neighbourhood/road links (resident anonymised)
  await b.goto(`/connections?focus=${issueUrl.split("/").pop()}`);
  await expect(b.getByText(/nodes ·/)).toBeVisible();
  await b.waitForTimeout(1500);
  await b.screenshot({ path: `${SHOTS}/05-connections.png`, fullPage: true });

  // Coordinator: analyse, approve, record outcome
  test.skip(!OPERATOR_PASSWORD, "E2E_OPERATOR_PASSWORD not set");
  const op = await (await browser.newContext()).newPage();
  await op.goto("/command");
  await op.getByLabel("Username").fill(OPERATOR_USER);
  await op.getByLabel("Password").fill(OPERATOR_PASSWORD);
  await op.getByRole("button", { name: "Sign in" }).click();
  await expect(op.getByRole("heading", { name: "Overview" })).toBeVisible();
  await op.screenshot({ path: `${SHOTS}/06-command-overview.png`, fullPage: true });
  await op.goto(`/command/incidents/${issueUrl.split("/").pop()}`);
  await op.getByRole("button", { name: "Run agents" }).click();
  await expect(op.getByText(/Explanation paths/)).toBeVisible();
  await op.screenshot({ path: `${SHOTS}/07-agent-analysis.png`, fullPage: true });
  await op.getByRole("button", { name: /Approve & execute/ }).first().click();
  await expect(op.getByPlaceholder("What actually happened?")).toBeVisible();
  await op.getByPlaceholder("What actually happened?").fill("Test outcome: residents confirmed via in-app request.");
  await op.getByRole("button", { name: "Worked" }).click();
  await expect(op.getByText(/Memory Agent wrote/)).toBeVisible();

  // Reload: memory persists in FalkorDB
  await op.goto("/command/memory");
  await op.reload();
  await expect(op.getByText(/Test outcome: residents confirmed/).first()).toBeVisible();
  await op.screenshot({ path: `${SHOTS}/08-city-memory.png`, fullPage: true });
});
