/** Pure state machine for the /login page. The WebSocket and fetch side effects live in useCameraStatus. */

export type CameraStatus = "off" | "starting" | "streaming" | "error";

/** One message from the bridge WS /camera/status. */
export type StatusMessage = {
  state: "searching" | "recognized";
  streak: number;
  idx: string | null;
  percent: number | null;
  camera_status: CameraStatus;
  camera_error: string | null;
  grant?: string;
};

export type LoginState = {
  connection: "connecting" | "open" | "closed";
  bridgeOnline: boolean | null; // null = not checked yet
  cameraStatus: CameraStatus | null;
  cameraError: string | null;
  streak: number;
  idx: string | null;
  percent: number | null;
  recognized: boolean;
  phase: "waiting" | "redeeming" | "done" | "failed";
  error: string | null;
};

export type LoginEvent =
  | { type: "connecting" }
  | { type: "open" }
  | { type: "closed" }
  | { type: "health"; online: boolean }
  | { type: "message"; message: StatusMessage }
  | { type: "redeem_start" }
  | { type: "redeem_ok" }
  | { type: "redeem_failed"; error: string }
  | { type: "retry" };

export const initialLoginState: LoginState = {
  connection: "connecting",
  bridgeOnline: null,
  cameraStatus: null,
  cameraError: null,
  streak: 0,
  idx: null,
  percent: null,
  recognized: false,
  phase: "waiting",
  error: null,
};

export function loginReducer(state: LoginState, event: LoginEvent): LoginState {
  switch (event.type) {
    case "connecting":
      return { ...state, connection: "connecting" };
    case "open":
      return { ...state, connection: "open", bridgeOnline: true };
    case "closed":
      return { ...state, connection: "closed", streak: 0, recognized: false };
    case "health":
      return { ...state, bridgeOnline: event.online };
    case "message": {
      const m = event.message;
      return {
        ...state,
        cameraStatus: m.camera_status,
        cameraError: m.camera_error,
        streak: m.streak,
        idx: m.idx,
        percent: m.percent,
        recognized: m.state === "recognized",
      };
    }
    case "redeem_start":
      return { ...state, phase: "redeeming", error: null };
    case "redeem_ok":
      return { ...state, phase: "done" };
    case "redeem_failed":
      return { ...state, phase: "failed", error: event.error };
    case "retry":
      return { ...initialLoginState, bridgeOnline: state.bridgeOnline };
  }
}

/** Parses a raw WS payload; returns null for anything that is not a status message. */
export function parseStatusMessage(raw: unknown): StatusMessage | null {
  if (typeof raw !== "string") return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null) return null;
  const m = data as Record<string, unknown>;
  if (m.state !== "searching" && m.state !== "recognized") return null;
  if (typeof m.streak !== "number") return null;
  return {
    state: m.state,
    streak: m.streak,
    idx: typeof m.idx === "string" ? m.idx : null,
    percent: typeof m.percent === "number" ? m.percent : null,
    camera_status: isCameraStatus(m.camera_status) ? m.camera_status : "off",
    camera_error: typeof m.camera_error === "string" ? m.camera_error : null,
    grant: typeof m.grant === "string" && m.grant ? m.grant : undefined,
  };
}

function isCameraStatus(value: unknown): value is CameraStatus {
  return value === "off" || value === "starting" || value === "streaming" || value === "error";
}

/** Short human-readable status line (never color-only). */
export function describeStatus(state: LoginState): string {
  if (state.phase === "done") return "Recognized. Opening the control page...";
  if (state.phase === "redeeming") return "Recognized. Signing you in...";
  if (state.phase === "failed") return `Login failed: ${state.error}`;
  if (state.connection !== "open") {
    return state.bridgeOnline === false
      ? "Bridge offline: run `python -m web_app.bridge`"
      : "Connecting to the bridge...";
  }
  switch (state.cameraStatus) {
    case "starting":
      return "Starting camera (a real camera can take up to 25 seconds)...";
    case "error":
      return `Camera error: ${state.cameraError ?? "unknown error"}`;
    case "off":
    case null:
      return "Camera off.";
    case "streaming":
      return state.idx
        ? `Face ${state.idx} seen (${state.percent ?? "?"}%). Hold still...`
        : "Looking for a face...";
  }
}

/** Reconnect delay: 0.5 s doubling up to 5 s. */
export function backoffDelay(attempt: number): number {
  return Math.min(5000, 500 * 2 ** attempt);
}
