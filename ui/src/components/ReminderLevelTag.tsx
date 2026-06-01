// Pastille du niveau de relance suggéré (none / first / second / formal).

import type { ReminderLevel } from "../api-client";
import { LEVEL_LABEL } from "./format";

export function ReminderLevelTag({ level }: { level: ReminderLevel }) {
  return (
    <span className={`tag lvl-${level}`}>
      <span className="tag__dot" />
      {LEVEL_LABEL[level]}
    </span>
  );
}
