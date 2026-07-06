import { test, expect } from "@playwright/test";

test("finder loads with data and map", async ({ page }) => {
  const failures = [];
  page.on("response", (r) => { if (!r.ok() && r.url().includes("/data/")) failures.push(r.url()); });
  await page.goto("/");
  await expect(page.locator("h1")).toHaveText("CoolSpot");
  await expect(page.locator("#map .leaflet-tile-pane")).toBeAttached();
  await expect(page.locator("#freshness")).toContainText("centers", { timeout: 10000 });
  expect(failures).toEqual([]);
});

test("fallback area search renders results", async ({ page }) => {
  await page.goto("/");
  await page.locator("#fallback-picker").evaluate((el) => (el.hidden = false));
  await page.locator("#area-select").selectOption({ label: "Washington, DC" });
  await expect(page.locator(".result-card").first()).toBeVisible();
  await expect(page.locator(".result-card").first().locator("a.btn")).toHaveAttribute("href", /google\.com\/maps\/dir/);
});

test("analysis view renders choropleth and legend", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-row").first()).toBeVisible({ timeout: 15000 });
  await expect(page.locator("#legend h3")).toContainText("CRE-Heat");
  await expect(page.locator("#map path.leaflet-interactive").first()).toBeAttached({ timeout: 15000 });
  await expect(page.locator("#freshness")).toContainText("centers", { timeout: 10000 });
});

test("known-limitations jump button links to a populated section", async ({ page }) => {
  await page.goto("/");
  const btn = page.locator("a.jump-btn");
  await expect(btn).toHaveAttribute("href", "#known-limitations");
  // JS replaces the fallback <li> with the shared caveats list.
  await expect(page.locator("#known-limitations-list li")).toHaveCount(7, { timeout: 10000 });
  await expect(page.locator("#known-limitations")).toContainText("Baltimore County");
  await btn.click();
  await expect(page).toHaveURL(/#known-limitations$/);
  await expect(page.locator("#known-limitations")).toBeInViewport();
});

test("analysis view also shows the known-limitations section", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("a.jump-btn")).toHaveAttribute("href", "#known-limitations");
  await expect(page.locator("#known-limitations-list li")).toHaveCount(7, { timeout: 15000 });
});

test("analysis view layer switch is interactive and performant", async ({ page }) => {
  const loadStart = Date.now();
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-row").first()).toBeVisible({ timeout: 15000 });
  const loadToLegendMs = Date.now() - loadStart;

  const switchStart = Date.now();
  await page.locator('#layer-picker input[value="no_ac"]').click();
  await expect(page.locator("#legend h3")).toContainText("without air conditioning");
  const layerSwitchMs = Date.now() - switchStart;

  console.log(`[perf] load-to-legend: ${loadToLegendMs}ms, layer-switch: ${layerSwitchMs}ms`);

  expect(loadToLegendMs).toBeLessThan(15000);
  expect(layerSwitchMs).toBeLessThan(5000);
});
