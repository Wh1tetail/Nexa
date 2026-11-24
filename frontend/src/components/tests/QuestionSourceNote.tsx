import { BookOpen } from "lucide-react";

import { useI18n } from "@/contexts/I18nContext";
import type { QuestionSource } from "@/types/api";

/** "From the book ..., p. N" under a question - editors only (students never get a source). */
export function QuestionSourceNote({ source }: { source: QuestionSource }) {
  const { t } = useI18n();
  return (
    <div className="grid gap-1 rounded-lg bg-secondary px-3 py-2 text-xs text-muted-foreground">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <BookOpen className="size-3.5 shrink-0" />
        <span className="break-words">{t.tests.fromBook(source.book_title, source.page_start, source.page_end)}</span>
        {source.difficulty && <span>· {t.books.difficultyOne[source.difficulty]}</span>}
      </p>
      {source.excerpt && <p className="break-words italic">«{source.excerpt}»</p>}
    </div>
  );
}
