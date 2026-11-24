import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Library,
  RefreshCw,
  RotateCcw,
  Save,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ExportDialog } from "@/components/books/ExportDialog";
import { CardListSkeleton, EmptyState, ErrorState, Field, PageSkeleton } from "@/components/common";
import { QuestionEditor } from "@/components/tests/QuestionEditor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { NativeSelect, Textarea } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { booksApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Difficulty, DraftStatus, QuestionDraft, QuestionInput, QuestionType, ReviewAction } from "@/types/api";

type Filter = DraftStatus | "all";
const FILTERS: Filter[] = ["draft", "approved", "rejected", "exported", "all"];
const EDIT_TYPES: QuestionType[] = ["single_choice", "multiple_choice", "true_false"];
const STATUS_VARIANT = { draft: "warning", approved: "success", rejected: "danger", exported: "default" } as const;

/** The page text with the quote marked, so the methodist sees what the answer rests on. */
function SourceText({ text, excerpt }: { text: string; excerpt: string }) {
  const at = excerpt.trim() ? text.toLowerCase().indexOf(excerpt.trim().toLowerCase()) : -1;
  if (at < 0) return <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-primary">{text}</p>;
  const end = at + excerpt.trim().length;
  return (
    <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-primary">
      {text.slice(0, at)}
      <mark className="rounded bg-warning-soft px-0.5 text-primary">{text.slice(at, end)}</mark>
      {text.slice(end)}
    </p>
  );
}

function DraftEditor({
  bookId,
  bookTitle,
  draft,
  onPrev,
  onNext,
  onRegenerate,
  regenerating,
}: {
  bookId: number;
  bookTitle: string;
  draft: QuestionDraft;
  onPrev?: () => void;
  onNext?: () => void;
  onRegenerate: () => void;
  regenerating: boolean;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [question, setQuestion] = useState<QuestionInput>(draft.question);
  const [difficulty, setDifficulty] = useState<Difficulty>(draft.difficulty);
  const [excerpt, setExcerpt] = useState(draft.excerpt);
  useEffect(() => {
    setQuestion(draft.question);
    setDifficulty(draft.difficulty);
    setExcerpt(draft.excerpt);
  }, [draft]);
  const dirty =
    JSON.stringify(question) !== JSON.stringify(draft.question) || difficulty !== draft.difficulty || excerpt !== draft.excerpt;
  const pages = useQuery({
    queryKey: ["books", bookId, "pages", draft.page_start, draft.page_end],
    queryFn: () => booksApi.pages(bookId, draft.page_start, draft.page_end),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["books", bookId] });
  const save = useMutation({
    mutationFn: () => booksApi.updateDraft(draft.id, { question, difficulty, excerpt }),
    onSuccess: () => {
      refresh();
      toast.success(t.books.draftSaved);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const act = useMutation({
    mutationFn: (action: ReviewAction) => booksApi.review(bookId, [draft.id], action),
    onSuccess: (res) => {
      refresh();
      const r = res[0];
      if (r?.ok) {
        toast.success(t.books.reviewDone(1, 0));
        onNext?.();
      } else if (r) toast.error(t.books.reviewReason[r.reason ?? ""] ?? t.books.reviewDone(0, 1));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const exported = draft.status === "exported";

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
      <div className="grid content-start gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={STATUS_VARIANT[draft.status]}>{t.books.draftStatus[draft.status]}</Badge>
          <span className="text-xs text-muted-foreground">{t.books.sourcePage(draft.page_start, draft.page_end)}</span>
          {exported && draft.exported_test_id && (
            <Button asChild variant="link" size="sm" className="h-auto p-0">
              <Link to={`/methodist/library/tests/${draft.exported_test_id}`}><Library />{t.books.openTest}</Link>
            </Button>
          )}
        </div>
        <QuestionEditor
          q={question}
          index={0}
          total={1}
          locked={exported}
          files={[]}
          types={EDIT_TYPES}
          onChange={setQuestion}
        />
        <Field label={t.books.difficulty}>
          <NativeSelect value={difficulty} disabled={exported} onChange={(e) => setDifficulty(e.target.value as Difficulty)}>
            {(["easy", "medium", "hard"] as const).map((d) => (
              <option key={d} value={d}>{t.books.difficultyOne[d]}</option>
            ))}
          </NativeSelect>
        </Field>
        <div className="flex flex-wrap gap-2">
          {dirty && !exported && (
            <Button loading={save.isPending} onClick={() => save.mutate()}><Save />{t.books.saveDraft}</Button>
          )}
          {!dirty && !exported && draft.status !== "approved" && (
            <Button loading={act.isPending && act.variables === "approve"} onClick={() => act.mutate("approve")}>
              <Check />{t.books.approve}
            </Button>
          )}
          {!exported && draft.status !== "rejected" && (
            <Button variant="outline" disabled={dirty} loading={act.isPending && act.variables === "reject"} onClick={() => act.mutate("reject")}>
              <X />{t.books.reject}
            </Button>
          )}
          {!exported && draft.status !== "draft" && (
            <Button variant="outline" disabled={dirty} onClick={() => act.mutate("reset")}><RotateCcw />{t.books.toReview}</Button>
          )}
          {(draft.status === "draft" || draft.status === "rejected") && (
            <Button variant="outline" disabled={dirty} loading={regenerating} onClick={onRegenerate}>
              {!regenerating && <RefreshCw />}{t.books.regenerate}
            </Button>
          )}
        </div>
        <div className="flex justify-between gap-2">
          <Button variant="ghost" size="sm" disabled={!onPrev} onClick={onPrev}><ChevronLeft />{t.books.prev}</Button>
          <Button variant="ghost" size="sm" disabled={!onNext} onClick={onNext}>{t.books.next}<ChevronRight /></Button>
        </div>
      </div>

      <div className="grid content-start gap-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{bookTitle}</CardTitle>
            <p className="text-sm text-muted-foreground">{t.books.sourcePage(draft.page_start, draft.page_end)}</p>
          </CardHeader>
          <CardContent className="grid gap-4">
            <Field label={t.books.excerpt} hint={t.books.excerptHint}>
              <Textarea rows={3} value={excerpt} maxLength={1000} disabled={exported} onChange={(e) => setExcerpt(e.target.value)} />
            </Field>
            <div className="grid gap-2">
              <p className="text-sm font-medium text-primary">{t.books.checks}</p>
              {draft.warnings.length ? (
                draft.warnings.map((w) => (
                  <p key={w} className="flex items-start gap-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger-strong">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0" />{t.books.warning[w] ?? w}
                  </p>
                ))
              ) : (
                <p className="flex items-start gap-2 rounded-lg bg-success-soft px-3 py-2 text-sm text-success-strong">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0" />{t.books.checksOk}
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <p className="text-sm font-medium text-primary">{t.books.pageText}</p>
              {pages.isLoading ? (
                <CardListSkeleton rows={1} />
              ) : (
                <div className="max-h-80 overflow-y-auto rounded-lg border bg-secondary/40 p-3">
                  <SourceText text={(pages.data ?? []).map((p) => p.text).join("\n\n")} excerpt={draft.excerpt} />
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function ReviewPage() {
  const { bookId } = useParams();
  const id = Number(bookId);
  const { t } = useI18n();
  const qc = useQueryClient();
  const [filter, setFilter] = useState<Filter>("draft");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [regenJob, setRegenJob] = useState<number | null>(null);
  // the ids are fixed when the dialog opens (the list changes once they are sent)
  const [exportFor, setExportFor] = useState<number[]>([]);
  const [exporting, setExporting] = useState(false);
  const book =useQuery({ queryKey: ["books", id], queryFn: () => booksApi.get(id) });
  const all = useQuery({ queryKey: ["books", id, "drafts"], queryFn: () => booksApi.drafts(id) });
  const list = useMemo(
    () => (all.data ?? []).filter((d) => filter === "all" || d.status === filter),
    [all.data, filter],
  );
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: all.data?.length ?? 0 };
    for (const d of all.data ?? []) c[d.status] = (c[d.status] ?? 0) + 1;
    return c;
  }, [all.data]);
  const current = list.find((d) => d.id === currentId) ?? list[0] ?? null;
  const pos = current ? list.indexOf(current) : -1;
  useEffect(() => setSelected(new Set()), [filter]);

  const bulk = useMutation({
    mutationFn: (action: ReviewAction) => booksApi.review(id, [...selected], action),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["books", id] });
      const failed = res.filter((r) => !r.ok);
      const reasons = [...new Set(failed.map((r) => t.books.reviewReason[r.reason ?? ""]).filter(Boolean))];
      (failed.length ? toast.warning : toast.success)(t.books.reviewDone(res.length - failed.length, failed.length), {
        description: reasons.join("; ") || undefined,
      });
      setSelected(new Set(failed.map((r) => r.id)));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  // a replacement question is made by the worker: follow its job, then show the new draft
  const job = useQuery({
    queryKey: ["books", "jobs", regenJob],
    queryFn: () => booksApi.job(regenJob!),
    enabled: regenJob !== null,
    refetchInterval: (q) => (q.state.data && ["done", "failed", "cancelled"].includes(q.state.data.status) ? false : 2000),
  });
  useEffect(() => {
    const j = job.data;
    if (!j || !["done", "failed", "cancelled"].includes(j.status)) return;
    setRegenJob(null);
    qc.invalidateQueries({ queryKey: ["books", id] });
    const newId = j.settings.result && (j.settings.result as { draft_ids?: number[] }).draft_ids?.[0];
    if (j.status === "done" && newId) {
      toast.success(t.books.regenerated);
      setFilter("draft");
      setCurrentId(newId);
    } else if (j.status === "done") toast.warning(t.books.regenerateNone);
    else toast.error((j.error_code && t.books.jobError[j.error_code]) || t.books.jobErrorOther);
  }, [job.data, qc, id, t]);
  const regenerate = useMutation({
    mutationFn: (draftId: number) => booksApi.regenerateDraft(draftId),
    onSuccess: (j) => {
      setRegenJob(j.id);
      toast.message(t.books.regenerating);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (book.isLoading || all.isLoading) return <PageSkeleton />;
  if (book.isError || all.isError || !book.data || !all.data) return <ErrorState onRetry={() => { book.refetch(); all.refetch(); }} />;
  const allSelected = list.length > 0 && list.every((d) => selected.has(d.id));
  const selectable = filter !== "exported"; // exported questions are out of review's reach
  // in "approved": the selected ones, or all of them when nothing is selected
  const exportIds = filter === "approved" ? (selected.size ? [...selected] : list.map((d) => d.id)) : [];

  return (
    <div className="space-y-5">
      <Link to={`/methodist/books/${id}`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {book.data.title}
      </Link>
      <div>
        <h1 className="page-title">{t.books.review}</h1>
        <p className="page-subtitle">{t.books.reviewHint}</p>
      </div>

      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
        <TabsList className="max-w-full overflow-x-auto">
          {FILTERS.map((f) => (
            <TabsTrigger key={f} value={f}>{t.books.filter[f]} ({counts[f] ?? 0})</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {list.length === 0 ? (
        <Card><EmptyState icon={ClipboardCheck} title={t.books.nothingHere} /></Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
          <Card className="h-fit overflow-hidden">
            {selectable && <div className="flex flex-wrap items-center gap-2 border-b p-3">
              <label className="mr-auto flex items-center gap-2 text-sm">
                <Checkbox checked={allSelected} onCheckedChange={(v) => setSelected(new Set(v ? list.map((d) => d.id) : []))} />
                {t.books.selectAll}
              </label>
              {exportIds.length > 0 && (
                <Button size="sm" className="w-full" onClick={() => (setExportFor(exportIds), setExporting(true))}>
                  <Library />
                  {selected.size ? t.books.exportSelected(selected.size) : t.books.exportAll(exportIds.length)}
                </Button>
              )}
              {selected.size > 0 && (
                <>
                  <Button size="sm" loading={bulk.isPending && bulk.variables === "approve"} onClick={() => bulk.mutate("approve")}>
                    {t.books.approveSelected(selected.size)}
                  </Button>
                  <Button size="sm" variant="outline" loading={bulk.isPending && bulk.variables === "reject"} onClick={() => bulk.mutate("reject")}>
                    {t.books.rejectSelected(selected.size)}
                  </Button>
                </>
              )}
            </div>}
            <ul className="max-h-[32rem] divide-y overflow-y-auto">
              {list.map((d, i) => (
                <li key={d.id} className={cn("flex items-start gap-2 p-3", current?.id === d.id && "bg-accent-soft/50")}>
                  {d.status !== "exported" && <Checkbox
                    className="mt-0.5"
                    aria-label={`${i + 1}`}
                    checked={selected.has(d.id)}
                    onCheckedChange={(v) =>
                      setSelected((s) => {
                        const n = new Set(s);
                        if (v) n.add(d.id);
                        else n.delete(d.id);
                        return n;
                      })
                    }
                  />}
                  <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setCurrentId(d.id)}>
                    <p className="line-clamp-2 break-words text-sm text-primary">{i + 1}. {d.question.text}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                      <Badge variant={STATUS_VARIANT[d.status]}>{t.books.draftStatus[d.status]}</Badge>
                      {t.books.sourcePage(d.page_start, d.page_end)}
                      {d.warnings.length > 0 && <AlertTriangle className="size-3.5 text-danger" aria-label={String(d.warnings.length)} />}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          {current ? (
            <DraftEditor
              bookId={id}
              bookTitle={book.data.title}
              draft={current}
              onPrev={pos > 0 ? () => setCurrentId(list[pos - 1].id) : undefined}
              onNext={pos >= 0 && pos < list.length - 1 ? () => setCurrentId(list[pos + 1].id) : undefined}
              onRegenerate={() => regenerate.mutate(current.id)}
              regenerating={regenerate.isPending || regenJob !== null}
            />
          ) : (
            <Card><EmptyState icon={ClipboardCheck} title={t.books.pickDraft} /></Card>
          )}
        </div>
      )}
      <ExportDialog
        book={book.data}
        ids={exportFor}
        open={exporting}
        onClose={() => {
          setExporting(false);
          setSelected(new Set());
        }}
      />
    </div>
  );
}
