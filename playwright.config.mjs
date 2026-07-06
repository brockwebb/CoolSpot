import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests-e2e",
  webServer: { command: "python3 -m http.server 8080 -d site", port: 8080, reuseExistingServer: true },
  use: { baseURL: "http://localhost:8080" },
});
