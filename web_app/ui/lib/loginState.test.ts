import { describe, expect, it } from "vitest";
import {
  backoffDelay,
  describeStatus,
  initialLoginState,
  loginReducer,
  parseStatusMessage,
  type LoginState,
} from "./loginState";

const streaming = (overrides: Partial<LoginState> = {}): LoginState => ({
  ...initialLoginState,
  connection: "open",
  bridgeOnline: true,
  cameraStatus: "streaming",
  ...overrides,
});

describe("parseStatusMessage", () => {
  it("parses a bridge message with a grant", () => {
    const raw = JSON.stringify({
      state: "recognized",
      streak: 3,
      idx: "1",
      percent: 91,
      camera_status: "streaming",
      camera_error: null,
      grant: "abc",
    });
    expect(parseStatusMessage(raw)).toEqual({
      state: "recognized",
      streak: 3,
      idx: "1",
      percent: 91,
      camera_status: "streaming",
      camera_error: null,
      grant: "abc",
    });
  });

  it("rejects junk", () => {
    expect(parseStatusMessage("not json")).toBeNull();
    expect(parseStatusMessage(JSON.stringify({ state: "other", streak: 1 }))).toBeNull();
    expect(parseStatusMessage(JSON.stringify(null))).toBeNull();
    expect(parseStatusMessage(42)).toBeNull();
  });

  it("drops an empty grant", () => {
    const raw = JSON.stringify({ state: "searching", streak: 0, camera_status: "starting", grant: "" });
    expect(parseStatusMessage(raw)?.grant).toBeUndefined();
  });
});

describe("loginReducer", () => {
  it("tracks messages", () => {
    const next = loginReducer(streaming(), {
      type: "message",
      message: { state: "searching", streak: 2, idx: "1", percent: 88, camera_status: "streaming", camera_error: null },
    });
    expect(next).toMatchObject({ streak: 2, idx: "1", percent: 88, recognized: false });
  });

  it("resets the streak when the socket closes", () => {
    const next = loginReducer(streaming({ streak: 2 }), { type: "closed" });
    expect(next).toMatchObject({ connection: "closed", streak: 0 });
  });

  it("goes through the redeem phases", () => {
    let s = loginReducer(streaming(), { type: "redeem_start" });
    expect(s.phase).toBe("redeeming");
    s = loginReducer(s, { type: "redeem_failed", error: "Grant expired" });
    expect(s).toMatchObject({ phase: "failed", error: "Grant expired" });
    s = loginReducer(s, { type: "retry" });
    expect(s).toMatchObject({ phase: "waiting", error: null, connection: "connecting", bridgeOnline: true });
  });
});

describe("describeStatus", () => {
  it("explains an offline bridge", () => {
    const s = { ...initialLoginState, connection: "closed" as const, bridgeOnline: false };
    expect(describeStatus(s)).toContain("python -m web_app.bridge");
  });

  it("shows the camera start and errors", () => {
    expect(describeStatus(streaming({ cameraStatus: "starting" }))).toContain("Starting camera");
    expect(describeStatus(streaming({ cameraStatus: "error", cameraError: "port busy" }))).toContain("port busy");
  });

  it("shows who is seen", () => {
    expect(describeStatus(streaming({ idx: "1", percent: 91 }))).toContain("Face 1 seen (91%)");
  });
});

describe("backoffDelay", () => {
  it("doubles up to 5 s", () => {
    expect([0, 1, 2, 3, 4, 10].map(backoffDelay)).toEqual([500, 1000, 2000, 4000, 5000, 5000]);
  });
});
