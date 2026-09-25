import { describeStatus, type LoginState } from "@/lib/loginState";
import styles from "./login.module.css";

type Props = {
  state: LoginState;
  requiredStreak: number;
  onRetry: () => void;
};

/** Presentational status block. Text carries the meaning; color only reinforces it. */
export function StatusPanel({ state, requiredStreak, onRetry }: Props) {
  const streak = Math.min(state.streak, requiredStreak);
  const tone = state.phase === "failed" || state.cameraStatus === "error" ? "bad" : state.recognized ? "good" : "neutral";

  return (
    <section className={styles.panel} data-tone={tone} aria-labelledby="status-title">
      <h2 id="status-title" className={styles.panelTitle}>
        Recognition status
      </h2>
      <p role="status" aria-live="polite" className={styles.statusLine}>
        {describeStatus(state)}
      </p>

      <div className={styles.progressRow}>
        <label htmlFor="streak">
          Matching frames: {streak} / {requiredStreak}
        </label>
        <progress id="streak" max={requiredStreak} value={streak} />
      </div>

      <dl className={styles.facts}>
        <dt>Camera</dt>
        <dd>{state.cameraStatus ?? "unknown"}</dd>
        <dt>Face ID</dt>
        <dd>{state.idx ?? "none"}</dd>
        <dt>Confidence</dt>
        <dd>{state.percent === null ? "-" : `${state.percent}%`}</dd>
      </dl>

      {state.phase === "failed" && (
        <button type="button" className={styles.button} onClick={onRetry}>
          Try again
        </button>
      )}
    </section>
  );
}
