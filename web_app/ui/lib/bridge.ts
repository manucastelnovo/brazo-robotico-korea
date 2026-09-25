/** Bridge URLs. The browser must use "localhost" so the session cookie reaches the bridge WebSocket. */
export const BRIDGE_URL = (process.env.NEXT_PUBLIC_BRIDGE_URL ?? "http://localhost:8765").replace(/\/$/, "");

/** Server-to-server URL, used only by route handlers. */
export const BRIDGE_INTERNAL_URL = (process.env.BRIDGE_INTERNAL_URL ?? "http://127.0.0.1:8765").replace(/\/$/, "");

/** Frames the bridge needs to see in a row (HUENIT_FACE_STREAK on the bridge). */
export const REQUIRED_STREAK = Number(process.env.NEXT_PUBLIC_REQUIRED_STREAK ?? 3);

export function toWebSocketUrl(httpUrl: string): string {
  return httpUrl.replace(/^http/, "ws");
}
