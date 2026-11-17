import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpenCheck, Copy, Eye, FolderTree, Pencil, Tag, Timer, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState, PageSkeleton } from "@/components/common";
import { QuestionView } from "@/components/tests/QuestionView";
import { TestBody, hasReading } from "@/components/tests/TestBody";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { useCopyToMine, useLibraryBase } from "@/pages/library/shared";
import { libraryApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Question } from "@/types/api";

/** The right answer as if a student gave it, so the preview shows everything as correct. */
function correctValue(q: Question): string[] {
  if (q.type === "fill_gaps") return ((q.config.answers as string[][] | undefined) ?? []).map((a) => a[0] ?? "");
  if (q.type === "matching") return (q.config.answers as string[] | undefined) ?? [];
  if (q.type === "short_answer") return (q.correct_answer ?? []).slice(0, 1);
  return q.correct_answer ?? [];
}

/** Preview of a library test as students see it (with the correct answers). */
export default function LibraryTestPage() {
  const { testId } = useParams();
  const id = Number(testId);
  const { t } = useI18n();
  const { base, editor } = useLibraryBase();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const copy = useCopyToMine();
  const [deleting, setDeleting] = useState(false);
  const q = useQuery({ queryKey: ["library", "test", id], queryFn: () => libraryApi.get(id) });
  const duplicate = useMutation({
    mutationFn: () => libraryApi.duplicate(id),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success(t.library.duplicated);
      navigate(`${base}/tests/${d.id}/edit`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => libraryApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success(t.common.deleted);
      navigate(base, { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const d = q.data;

  return (
    <div className={cn("mx-auto space-y-6", hasReading(d.questions) ? "max-w-6xl" : "max-w-3xl")}>
      <Link to={base} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.library.title}
      </Link>

      <Card className="p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              {d.level && <Badge variant="neutral">{d.level}</Badge>}
              {editor && <Badge variant={d.published ? "success" : "warning"}>{d.published ? t.library.published : t.library.draft}</Badge>}
            </div>
            <h1 className="page-title mt-2 break-words">{d.title}</h1>
            {d.description && <p className="page-subtitle">{d.description}</p>}
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1.5"><BookOpenCheck className="size-4" />{t.common.questions(d.questions_count)}</span>
              <span className="inline-flex items-center gap-1.5"><Timer className="size-4" />{d.time_limit_minutes ? t.common.minutes(d.time_limit_minutes) : t.tests.noLimit}</span>
              {d.sections.length > 0 && (
                <span className="inline-flex items-center gap-1.5"><FolderTree className="size-4" />{d.sections.map((s) => s.name).join(", ")}</span>
              )}
              {d.author_name && <span>{t.library.author}: {d.author_name}</span>}
            </div>
            {d.tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {d.tags.map((g) => (
                  <span key={g} className="inline-flex items-center gap-1 rounded-md bg-secondary px-1.5 py-0.5 text-xs text-muted-foreground">
                    <Tag className="size-3" />{g}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {editor ? (
              <>
                <Button variant="outline" asChild><Link to={`${base}/tests/${id}/edit`}><Pencil />{t.common.edit}</Link></Button>
                <Button variant="outline" loading={duplicate.isPending} onClick={() => duplicate.mutate()}><Copy />{t.library.duplicate}</Button>
                <Button variant="ghost" size="icon" onClick={() => setDeleting(true)} aria-label={t.common.delete} className="hover:text-danger"><Trash2 /></Button>
              </>
            ) : (
              <Button loading={copy.isPending} onClick={() => copy.mutate(id)}><Copy />{t.library.copyToMine}</Button>
            )}
          </div>
        </div>
      </Card>

      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Eye className="size-4" />
        {t.library.preview}: {t.library.previewHint}
      </p>
      <TestBody
        questions={d.questions}
        files={d.files}
        renderQuestion={(qq, i) => <QuestionView index={i} question={qq} files={d.files} value={correctValue(qq)} />}
      />

      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t.library.deleteTitle}
        description={t.library.deleteText}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}
