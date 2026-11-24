import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Library, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { CardListSkeleton, EmptyState, ErrorState } from "@/components/common";
import { QuestionSourceNote } from "@/components/tests/QuestionSourceNote";
import { taskConfigFromSaved } from "@/components/tests/TaskEditors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { libraryApi } from "@/services/api";
import type { Question, QuestionInput, QuestionType } from "@/types/api";

/** A library question as an independent copy for the lesson (the source goes with it). */
export function libraryQuestionInput(q: Question): QuestionInput {
  return {
    type: q.type,
    text: q.text,
    options: q.type === "true_false" ? [] : q.options,
    correct_answer: q.correct_answer ?? [],
    points: q.points,
    explanation: q.explanation ?? "",
    attachment_ids: [],
    config: taskConfigFromSaved(q),
    source: q.source ?? null,
  };
}

/** Pick questions of a library test to copy into an exercise block. */
export function LibraryQuestionsDialog({
  open,
  onClose,
  types,
  room,
  onInsert,
}: {
  open: boolean;
  onClose: () => void;
  /** question kinds the block takes */
  types: QuestionType[];
  /** how many more questions the block can take */
  room: number;
  onInsert: (qs: QuestionInput[]) => void;
}) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [testId, setTestId] = useState<number | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  useEffect(() => {
    if (!open) {
      setTestId(null);
      setPicked(new Set());
    }
  }, [open]);

  const tests = useQuery({
    queryKey: ["library", "tests", { search }],
    queryFn: () => libraryApi.tests({ search: search.trim() || undefined }),
    enabled: open && testId === null,
  });
  const test = useQuery({ queryKey: ["library", "tests", testId], queryFn: () => libraryApi.get(testId!), enabled: open && testId !== null });
  const usable = (q: Question) => types.includes(q.type) && (q.attachment_ids ?? []).length === 0;
  const insert = () => {
    const qs = (test.data?.questions ?? []).filter((q) => picked.has(q.id)).map(libraryQuestionInput);
    onInsert(qs);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="lg">
        <DialogHeader><DialogTitle>{t.courses.libraryPickTitle}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-3">
          <p className="text-sm text-muted-foreground">{t.courses.libraryPickHint}</p>
          {testId === null ? (
            <>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="pl-9" value={search} placeholder={t.courses.librarySearch} onChange={(e) => setSearch(e.target.value)} />
              </div>
              {tests.isLoading ? (
                <CardListSkeleton rows={3} />
              ) : tests.isError ? (
                <ErrorState onRetry={() => tests.refetch()} />
              ) : !tests.data?.length ? (
                <EmptyState icon={Library} title={t.courses.libraryNoTests} />
              ) : (
                <ul className="grid gap-2">
                  {tests.data.map((x) => (
                    <li key={x.id}>
                      <button
                        type="button"
                        onClick={() => setTestId(x.id)}
                        className="flex w-full min-w-0 flex-wrap items-center gap-2 rounded-xl border bg-card p-3 text-left transition-colors hover:border-accent/50 hover:bg-accent-soft/40"
                      >
                        <span className="min-w-0 flex-1 break-words text-sm font-medium text-primary">{x.title}</span>
                        {x.level && <Badge variant="neutral">{x.level}</Badge>}
                        {!x.published && <Badge variant="warning">{t.courses.libraryDraft}</Badge>}
                        <span className="text-xs text-muted-foreground">{t.courses.libraryCount(x.questions_count)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" className="justify-self-start" onClick={() => (setTestId(null), setPicked(new Set()))}>
                <ArrowLeft />{t.courses.libraryBack}
              </Button>
              {test.isLoading ? (
                <CardListSkeleton rows={3} />
              ) : test.isError || !test.data ? (
                <ErrorState onRetry={() => test.refetch()} />
              ) : (
                <ul className="grid gap-2">
                  {test.data.questions.map((q, i) => {
                    const ok = usable(q);
                    const checked = picked.has(q.id);
                    const can = ok && (checked || picked.size < room);
                    const toggle = (v: boolean) =>
                      setPicked((s) => {
                        const n = new Set(s);
                        if (v) n.add(q.id);
                        else n.delete(q.id);
                        return n;
                      });
                    return (
                      <li key={q.id}>
                        {/* a div, not a label: a label around the checkbox button toggles it twice */}
                        <div
                          className={`flex items-start gap-3 rounded-xl border p-3 ${can ? "cursor-pointer" : ""} ${ok ? "" : "opacity-60"}`}
                          onClick={() => can && toggle(!checked)}
                        >
                          <Checkbox
                            className="mt-0.5"
                            aria-label={`${i + 1}`}
                            disabled={!can}
                            checked={checked}
                            onClick={(e) => e.stopPropagation()}
                            onCheckedChange={(v) => toggle(v === true)}
                          />
                          <span className="grid min-w-0 flex-1 gap-1.5">
                            <span className="break-words text-sm text-primary">{i + 1}. {q.text}</span>
                            <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                              <Badge variant="neutral">{t.status.questionType[q.type]}</Badge>
                              {!types.includes(q.type) ? t.courses.libraryWrongType : (q.attachment_ids ?? []).length > 0 && t.courses.libraryWithFile}
                            </span>
                            {q.source && <QuestionSourceNote source={q.source} />}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </DialogBody>
        <DialogFooter>
          {testId !== null && <span className="mr-auto self-center text-xs text-muted-foreground">{t.courses.libraryRoom(room)}</span>}
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={picked.size === 0} onClick={insert}>{t.courses.libraryInsert(picked.size)}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
