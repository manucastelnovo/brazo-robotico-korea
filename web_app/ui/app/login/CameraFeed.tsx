"use client";

import { useEffect, useState } from "react";
import { BRIDGE_URL } from "@/lib/bridge";
import styles from "./login.module.css";

const RETRY_MS = 2000;

/** Live MJPEG video from the bridge. Reloads with a cache-busting query when the stream breaks. */
export function CameraFeed() {
  const [bust, setBust] = useState(0);
  const [broken, setBroken] = useState(false);

  useEffect(() => {
    if (!broken) return;
    const timer = setTimeout(() => {
      setBroken(false);
      setBust(Date.now());
    }, RETRY_MS);
    return () => clearTimeout(timer);
  }, [broken]);

  return (
    <div className={styles.feed}>
      {/* next/image cannot render an endless MJPEG stream, so a plain img is used. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        key={bust}
        src={`${BRIDGE_URL}/camera/stream${bust ? `?t=${bust}` : ""}`}
        alt="Live view from the HUENIT AI Camera"
        width={320}
        height={240}
        onError={() => setBroken(true)}
      />
      {broken && <p className={styles.feedOverlay}>Video unavailable, retrying...</p>}
    </div>
  );
}
