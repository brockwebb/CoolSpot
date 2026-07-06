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
  await expect(page.locator("#legend .legend-title")).toContainText("CRE-Heat");
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
  await page.selectOption("#layer-select", "no_ac");
  await expect(page.locator("#legend .legend-title")).toContainText("without air conditioning");
  const layerSwitchMs = Date.now() - switchStart;

  console.log(`[perf] load-to-legend: ${loadToLegendMs}ms, layer-switch: ${layerSwitchMs}ms`);

  expect(loadToLegendMs).toBeLessThan(15000);
  expect(layerSwitchMs).toBeLessThan(5000);
});

test("percent/count toggle flips legend to separator counts", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-title")).toContainText("% with 3+", { timeout: 15000 });
  await page.locator('#show-as input[value="count"]').click();
  await expect(page.locator("#legend .legend-title")).toContainText("People with 3+");
  await expect(page.locator("#legend .legend-row").nth(3)).toContainText("1,000"); // separator, round stop
});

test("distance layer disables the mode toggle", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-row").first()).toBeVisible({ timeout: 15000 });
  await page.selectOption("#layer-select", "distance");
  await expect(page.locator('#show-as input[value="count"]')).toBeDisabled();
  await expect(page.locator("#show-as")).toHaveClass(/dimmed/);
  await page.selectOption("#layer-select", "heat");
  await expect(page.locator('#show-as input[value="count"]')).toBeEnabled();
});

test("underserved highlight and help disclosure", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-row").first()).toBeVisible({ timeout: 15000 });
  await page.locator("#underserved-help summary").click();
  await expect(page.locator("#underserved-help-text")).toContainText("8 km");
  await expect(page.locator("#underserved-help-text")).toContainText("1,500 people");
  await page.locator("#only-gaps").click();
  // at 8km + 1500 affected, 155 tracts qualify; blue outline weight=2 stroke color #1d4ed8
  await expect(page.locator('#map path[stroke="#1d4ed8"]').first()).toBeAttached();
});

test("segmented nav on both pages with correct active side", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('.seg-nav a[aria-current="page"]')).toHaveText("Find cooling centers");
  await page.goto("/analysis.html");
  await expect(page.locator('.seg-nav a[aria-current="page"]')).toHaveText("Heat vulnerability map");
});

test("legend renders as a horizontal bar above the map", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-title")).toBeVisible({ timeout: 15000 });
  const order = await page.evaluate(() => {
    const legend = document.getElementById("legend");
    const map = document.getElementById("map");
    return !!(legend.compareDocumentPosition(map) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(order).toBe(true); // legend precedes map in DOM
});

test("tract click opens popup and fills slim bar with county name", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-title")).toBeVisible({ timeout: 15000 });
  // Hide cooling-center markers first — they share the overlay pane with tract polygons and
  // can sit visually on top of a tiny/sliver tract path, stealing the click.
  await page.locator("#show-centers").uncheck();
  await page.locator("#map path.leaflet-interactive").first().click({ force: true });
  await expect(page.locator(".leaflet-popup-content h3").first()).toContainText(/Census Tract|Tract/);
  await expect(page.locator("#tract-info h3")).toContainText(/County|city|District of Columbia/);
});
