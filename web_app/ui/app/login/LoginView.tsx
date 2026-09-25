"use client";

import { REQUIRED_STREAK } from "@/lib/bridge";
import { CameraFeed } from "./CameraFeed";
import { StatusPanel } from "./StatusPanel";
import { useCameraStatus } from "./useCameraStatus";

/** Container: wires the camera status hook to the presentational pieces. */
export function LoginView() {
  const { state, retry } = useCameraStatus();
  return (
    <>
      <CameraFeed />
      <StatusPanel state={state} requiredStreak={REQUIRED_STREAK} onRetry={retry} />
    </>
  );
}
