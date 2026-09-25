"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import styles from "@/app/shared.module.css";

export function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const logout = async () => {
    setBusy(true);
    await fetch("/api/logout", { method: "POST" }).catch(() => null);
    router.replace("/login");
    router.refresh();
  };

  return (
    <button type="button" className={styles.button} onClick={logout} disabled={busy}>
      {busy ? "Logging out..." : "Log out"}
    </button>
  );
}
