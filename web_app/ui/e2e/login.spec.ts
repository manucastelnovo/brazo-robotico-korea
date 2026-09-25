import { expect, test } from "@playwright/test";

const BRIDGE_WS = (process.env.NEXT_PUBLIC_BRIDGE_URL ?? "http://localhost:8765").replace(/^http/, "ws");

test("face login flow with the mock camera", async ({ page, context }) => {
  // /control is protected before login.
  await page.goto("/control");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "HUENIT face login" })).toBeVisible();
  await expect(page.getByText("Local demo only.")).toBeVisible();

  // The MJPEG feed renders real pixels.
  const feed = page.getByAltText("Live view from the HUENIT AI Camera");
  await expect.poll(() => feed.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  await page.screenshot({ path: "test-results/login.png" });

  // The mock recognizes ID 1 and the page moves on by itself.
  await page.waitForURL(/\/control$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Robot control" })).toBeVisible();
  await page.screenshot({ path: "test-results/control.png" });

  const session = (await context.cookies()).find((c) => c.name === "huenit_session");
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Strict");

  // The httpOnly cookie set on localhost:3000 must reach the bridge WS on localhost:8765.
  const jog = await page.evaluate(
    (url) =>
      new Promise<{ opened: boolean; closeCode: number | null; gotState: boolean }>((resolve) => {
        const result = { opened: false, closeCode: null as number | null, gotState: false };
        const ws = new WebSocket(url);
        ws.onopen = () => {
          result.opened = true;
          ws.send(JSON.stringify({ type: "ping" }));
        };
        ws.onmessage = (event) => {
          if (JSON.parse(event.data).type === "state") result.gotState = true;
        };
        ws.onclose = (event) => {
          result.closeCode = event.code;
          resolve(result);
        };
        setTimeout(() => {
          ws.close();
          resolve(result);
        }, 1500);
      }),
    `${BRIDGE_WS}/arm/jog`,
  );
  expect(jog.opened).toBe(true);
  expect(jog.closeCode).not.toBe(4401);
  expect(jog.gotState).toBe(true);

  // Logout goes back to /login and /control is protected again.
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/control");
  await expect(page).toHaveURL(/\/login$/);
});
