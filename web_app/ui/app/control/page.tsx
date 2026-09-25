import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SecurityNotice } from "@/app/SecurityNotice";
import { isValidSession, SESSION_COOKIE } from "@/lib/session";
import styles from "@/app/shared.module.css";
import { LogoutButton } from "./LogoutButton";

export const metadata: Metadata = { title: "Control | HUENIT" };

// Placeholder until step 3 (gamepad control).
export default async function ControlPage() {
  // The proxy already guards this route; check again so the page never renders without a session.
  if (!isValidSession((await cookies()).get(SESSION_COOKIE)?.value)) redirect("/login");

  return (
    <main className={styles.page}>
      <h1>Robot control</h1>
      <p>Logged in. Gamepad control arrives in step 3.</p>
      <SecurityNotice />
      <LogoutButton />
    </main>
  );
}
