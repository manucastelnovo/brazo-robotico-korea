import type { Metadata } from "next";
import { SecurityNotice } from "@/app/SecurityNotice";
import { LoginView } from "./LoginView";
import styles from "./login.module.css";

export const metadata: Metadata = { title: "Face login | HUENIT" };

export default function LoginPage() {
  return (
    <main className={styles.page}>
      <h1>HUENIT face login</h1>
      <p className={styles.lead}>Look at the camera. You get in when it recognizes face ID 1.</p>
      <SecurityNotice />
      <div className={styles.layout}>
        <LoginView />
      </div>
    </main>
  );
}
