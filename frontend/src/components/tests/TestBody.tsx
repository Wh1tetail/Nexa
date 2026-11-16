import { Fragment, type ReactNode } from "react";

import { BlockView } from "@/components/tests/TaskViews";
import { cn } from "@/lib/utils";
import { CONTENT_TYPES, type Attachment, type Question } from "@/types/api";

interface Section {
  block: Question | null;
  items: { q: Question; number: number }[];
}

/** Questions grouped by the audio / reading block they follow; only real
 *  questions are numbered. */
export function sections(questions: Question[]): Section[] {
  const out: Section[] = [{ block: null, items: [] }];
  let n = 0;
  for (const q of questions) {
    if (CONTENT_TYPES.includes(q.type)) out.push({ block: q, items: [] });
    else out[out.length - 1].items.push({ q, number: ++n });
  }
  return out.filter((s) => s.block || s.items.length);
}

export const hasReading = (questions: Question[]) => questions.some((q) => q.type === "reading");

/** The body of a test: blocks with their questions. A reading text sits next to
 *  its questions on wide screens (and stays in view while scrolling), above
 *  them on phones; audio is shown above its questions. */
export function TestBody({
  questions,
  files,
  renderQuestion,
  attemptId,
  plays,
  live = false,
}: {
  questions: Question[];
  files: Attachment[];
  /** index is 0-based among real questions */
  renderQuestion: (q: Question, index: number) => ReactNode;
  attemptId?: number;
  plays?: Record<string, number>;
  live?: boolean;
}) {
  return (
    <div className="grid gap-6">
      {sections(questions).map((s, i) => {
        const list = (
          <div className="grid content-start gap-4">
            {s.items.map(({ q, number }) => (
              <Fragment key={q.id}>{renderQuestion(q, number - 1)}</Fragment>
            ))}
          </div>
        );
        if (!s.block) return <Fragment key={`s${i}`}>{list}</Fragment>;
        const block = <BlockView q={s.block} files={files} attemptId={attemptId} plays={plays} live={live} />;
        const reading = s.block.type === "reading" && s.items.length > 0;
        return (
          <section key={s.block.id} className={cn("grid gap-4", reading && "lg:grid-cols-2 lg:items-start")}>
            <div className={cn(reading && "lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto")}>{block}</div>
            {list}
          </section>
        );
      })}
    </div>
  );
}

/** Files shown by questions or blocks (the rest are general test materials). */
export const usedFileIds = (questions: Question[]) =>
  questions.flatMap((q) => [
    ...q.attachment_ids,
    ...(q.config.attachment_id ? [q.config.attachment_id] : []),
    ...(q.config.image_id ? [q.config.image_id] : []),
  ]);
