import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, HelpCircle, Pencil, RotateCcw, Timer, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageSkeleton, StatCard } from "@/components/common";
import { AttemptBadge } from "@/components/common/StatusBadges";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/contexts/I18nContext";
import { testsApi } from "@/services/api";
import type { AttemptSummary } from "@/types/api";
import { errorMessage } from "@/services/http";
import { fmtDateTime } from "@/utils/format";
import { scoreVariant } from "@/utils/status";

export default function TestResultsPage() {
  const { testId } = useParams();
  const id = Number(testId);
  const { t, locale } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [deleting, setDeleting] = useState(false);
  const [resetting, setResetting] = useState<AttemptSummary | null>(null);
  const test = useQuery({ queryKey: ["tests", id], queryFn: () => testsApi.get(id) });
  const attempts = useQuery({ queryKey: ["tests", id, "attempts"], queryFn: () => testsApi.attempts(id) });

  const remove = useMutation({
    mutationFn: () => testsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tests"] });
      toast.success(t.common.deleted);
      navigate("/teacher/tests", { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const reset = useMutation({
    mutationFn: (a: AttemptSummary) => testsApi.resetAttempt(a.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tests"] });
      toast.success(t.tests.retakeAllowed);
      setResetting(null);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (test.isLoading) return <PageSkeleton />;
  if (test.isError || !test.data) return <ErrorState onRetry={() => test.refetch()} />;
  const d = test.data;
  const done = (attempts.data ?? []).filter((a) => a.status !== "in_progress");
  const graded = done.filter((a) => a.percent !== null);
  const avg = graded.length ? Math.round(graded.reduce((s, a) => s + (a.percent ?? 0), 0) / graded.length) : null;

  return (
    <div className="space-y-6">
      <Link to="/teacher/tests" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.tests.title}
      </Link>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="page-title break-words">{d.title}</h1>
          {d.description && <p className="page-subtitle">{d.description}</p>}
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5"><HelpCircle className="size-4" />{t.common.questions(d.questions.length)}</span>
            <span className="inline-flex items-center gap-1.5"><Timer className="size-4" />{d.time_limit_minutes ? t.common.minutes(d.time_limit_minutes) : t.tests.noLimit}</span>
            {d.due_at && <span>{t.common.due}: {fmtDateTime(d.due_at, locale)}</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link to={`/teacher/tests/${id}/edit`}><Pencil />{t.common.edit}</Link>
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setDeleting(true)} aria-label={t.common.delete} className="hover:text-danger">
            <Trash2 />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard icon={Users} label={t.tests.assigned} value={d.student_ids.length} />
        <StatCard icon={Users} tone="success" label={t.tests.completed} value={done.length} />
        <StatCard icon={Users} tone="warning" label={t.tests.pendingReview} value={done.filter((a) => a.status === "pending_review").length} />
        <StatCard icon={Users} tone="primary" label={t.tests.score} value={avg !== null ? `${avg}%` : "—"} />
      </div>

      <Card className="overflow-hidden">
        <CardHeader><CardTitle>{t.tests.results}</CardTitle></CardHeader>
        {attempts.data?.length ? (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>{t.common.student}</TableHead>
                <TableHead>{t.common.date}</TableHead>
                <TableHead>{t.common.status}</TableHead>
                <TableHead className="text-right">{t.tests.score}</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {attempts.data.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>
                    <div className="flex items-center gap-3 whitespace-nowrap">
                      <Avatar name={a.student_name} className="size-8 text-[10px]" />
                      <span className="font-medium text-primary">{a.student_name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(a.submitted_at ?? a.started_at, locale)}</TableCell>
                  <TableCell><AttemptBadge status={a.status} /></TableCell>
                  <TableCell className="text-right">
                    {a.percent !== null ? <Badge variant={scoreVariant(a.percent)} className="tabular">{a.score}/{a.max_score} · {a.percent}%</Badge> : "—"}
                    {a.passed !== null && (
                      <span className={a.passed ? "ml-2 text-xs text-success" : "ml-2 text-xs text-danger"}>
                        {a.passed ? t.tests.passed : t.tests.notPassed}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-right">
                    <Button size="icon-sm" variant="ghost" onClick={() => setResetting(a)} aria-label={t.tests.allowRetake} title={t.tests.allowRetake}>
                      <RotateCcw />
                    </Button>
                    {a.status !== "in_progress" && (
                      <Button size="sm" variant={a.status === "pending_review" ? "default" : "ghost"} asChild>
                        <Link to={`/teacher/tests/${id}/attempts/${a.id}`}>{a.status === "pending_review" ? t.tests.grade : t.common.open}</Link>
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState title={t.tests.attemptsEmpty} />
        )}
      </Card>

      <ConfirmDialog
        open={!!resetting}
        onOpenChange={(o) => !o && setResetting(null)}
        title={t.tests.allowRetake}
        description={resetting ? t.tests.retakeText(resetting.student_name) : ""}
        confirmLabel={t.tests.allowRetake}
        cancelLabel={t.common.cancel}
        destructive
        loading={reset.isPending}
        onConfirm={() => resetting && reset.mutate(resetting)}
      />

      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t.tests.deleteTitle}
        description={t.tests.deleteText}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}
