import styles from "./shared.module.css";

export function SecurityNotice() {
  return (
    <p className={styles.notice} role="note">
      <strong>Local demo only.</strong> 2D face recognition can be fooled with a photo. Do not use this as real
      security.
    </p>
  );
}
