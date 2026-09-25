"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BRIDGE_URL, toWebSocketUrl } from "@/lib/bridge";
import { backoffDelay, initialLoginState, loginReducer, parseStatusMessage } from "@/lib/loginState";

const HEALTH_POLL_MS = 2000;

/**
 * Container logic for /login: keeps the bridge status WebSocket open (with backoff),
 * polls /health while it is down, and trades the one-time grant for a session cookie.
 */
export function useCameraStatus() {
  const router = useRouter();
  const [state, dispatch] = useReducer(loginReducer, initialLoginState);
  const [attemptKey, setAttemptKey] = useState(0); // bump to open a fresh socket (new recognition run)
  const redeeming = useRef(false);

  const redeem = useCallback(
    async (grant: string) => {
      if (redeeming.current) return;
      redeeming.current = true;
      dispatch({ type: "redeem_start" });
      try {
        const response = await fetch("/api/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ grant }),
        });
        if (!response.ok) {
          const detail = (await response.json().catch(() => null))?.error;
          throw new Error(detail ?? `Server answered ${response.status}`);
        }
        dispatch({ type: "redeem_ok" });
        router.replace("/control");
      } catch (error) {
        dispatch({ type: "redeem_failed", error: error instanceof Error ? error.message : "Unknown error" });
      }
    },
    [router],
  );

  // Status WebSocket with reconnect backoff.
  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      dispatch({ type: "connecting" });
      socket = new WebSocket(`${toWebSocketUrl(BRIDGE_URL)}/camera/status`);
      socket.onopen = () => {
        attempt = 0;
        dispatch({ type: "open" });
      };
      socket.onmessage = (event) => {
        const message = parseStatusMessage(event.data);
        if (!message) return;
        dispatch({ type: "message", message });
        if (message.grant) void redeem(message.grant);
      };
      socket.onclose = () => {
        if (disposed) return;
        dispatch({ type: "closed" });
        if (redeeming.current) return; // the grant already arrived: do not start another run
        timer = setTimeout(connect, backoffDelay(attempt++));
      };
    };

    redeeming.current = false;
    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [attemptKey, redeem]);

  // Health polling while the socket is down, to tell "bridge offline" from "connecting".
  const socketDown = state.connection !== "open";
  useEffect(() => {
    if (!socketDown) return;
    let disposed = false;
    const check = async () => {
      try {
        const response = await fetch(`${BRIDGE_URL}/health`, { cache: "no-store" });
        if (!disposed) dispatch({ type: "health", online: response.ok });
      } catch {
        if (!disposed) dispatch({ type: "health", online: false });
      }
    };
    void check();
    const interval = setInterval(check, HEALTH_POLL_MS);
    return () => {
      disposed = true;
      clearInterval(interval);
    };
  }, [socketDown]);

  const retry = useCallback(() => {
    dispatch({ type: "retry" });
    setAttemptKey((key) => key + 1);
  }, []);

  return { state, retry };
}
