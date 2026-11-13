import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Send, Timer } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState, PageSkeleton } from "@/components/common";
import { QuestionView } from "@/components/tests/QuestionView";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { meApi, type AnswerMap } from "@/services/api";
import { errorMessage } from "@/services/http";

function useCountdown(deadline: string | null) {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    if (!deadline) return;
    const end = new Date(deadline).getTime();
    const tick = () => setLeft(Math.max(0, Math.floor((end - Date.now()) / 1000)));
    tick();
    const h = setInterval(tick, 1000);
    return () => clearInterval(h);
  }, [deadline]);
  return left;
}

export default function TakeTestPage() {
  const { testId } = useParams();
  const { t } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [confirm, setConfirm] = useState(false);
  const dirty = useRef(false);
  const submittedRef = useRef(false);

  // Starting is idempotent on the server: returns the existing attempt if any.
  const start = useQuery({
    queryKey: ["me", "tests", "attempt-start", testId],
    queryFn: () => meApi.startTest(Number(testId)),
    staleTime: Infinity,
    gcTime: 0,
  });
  const attempt = start.data;

  useEffect(() => {
    if (attempt) {
      setAnswers(Object.fromEntries(attempt.answers.map((a) => [a.question_id, a.answer])));
    }
  }, [attempt]);

  const submit = useMutation({
    mutationFn: () => meApi.submitTest(attempt!.id, answers),
    onSuccess: (res) => {
      submittedRef.current = true;
      qc.invalidateQueries({ queryKey: ["me", "tests"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "student"] });
      toast.success(t.tests.submitted);
      navigate(`/student/tests/attempts/${res.id}`, { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  // Autosave every few seconds while answering.
  const save = useCallback(async () => {
    if (!attempt || !dirty.current || submittedRef.current) return;
    dirty.current = false;
    try {
      await meApi.saveProgress(attempt.id, answers);
    } catch {
      dirty.current = true;
    }
  }, [attempt, answers]);

  useEffect(() => {
    const h = setTimeout(save, 2500);
    return () => clearTimeout(h);
  }, [save]);

  const left = useCountdown(attempt?.deadline_at ?? null);
  useEffect(() => {
    if (left === 0 && attempt && !submittedRef.current && !submit.isPending) {
      toast.warning(t.tests.autoSubmitted);
      submit.mutate();
    }
  }, [left]); // eslint-disable-line react-hooks/exhaustive-deps

  // Warn before leaving the page with unsent answers.
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => {
      if (!submittedRef.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, []);

  if (start.isLoading) return <PageSkeleton />;
  if (start.isError || !attempt) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-danger">{errorMessage(start.error)}</p>
        <ErrorState onRetry={() => start.refetch()} />
      </div>
    );
  }
  if (attempt.status !== "in_progress") return <Navigate to={`/student/tests/attempts/${attempt.id}`} replace />;

  const total = attempt.questions.length;
  const answered = attempt.questions.filter((q) => (answers[q.id] ?? []).length > 0).length;
  const mm = left !== null ? String(Math.floor(left / 60)).padStart(2, "0") : "";
  const ss = left !== null ? String(left % 60).padStart(2, "0") : "";

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/student/tests" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.tests.title}
      </Link>
      <h1 className="page-title">{attempt.test_title}</h1>

      <div className="sticky top-16 z-10 -mx-4 mt-4 border-b bg-secondary/90 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-2xl sm:border sm:bg-background/90 sm:px-5">
        <div className="flex items-center gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted-foreground">{t.tests.answered(answered, total)}</p>
            <Progress value={(answered * 100) / total} className="mt-1.5 h-1.5" />
          </div>
          {left !== null && (
            <div
              className={cn(
                "tabular flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-semibold",
                left < 60 ? "bg-danger-soft text-danger" : left < 300 ? "bg-warning-soft text-[hsl(32_95%_36%)]" : "bg-secondary text-primary",
              )}
              aria-label={t.tests.timeLeft}
            >
              <Timer className="size-4" />
              {mm}:{ss}
            </div>
          )}
          <Button size="sm" onClick={() => setConfirm(true)} loading={submit.isPending}>
            <Send />
            <span className="hidden sm:inline">{t.tests.finish}</span>
          </Button>
        </div>
      </div>

      <div className="mt-6 grid gap-4">
        {attempt.questions.map((q, i) => (
          <QuestionView
            key={q.id}
            index={i}
            question={q}
            value={answers[q.id] ?? []}
            onChange={(v) => {
              dirty.current = true;
              setAnswers((prev) => ({ ...prev, [q.id]: v }));
            }}
          />
        ))}
      </div>

      <Button size="lg" className="mt-6 w-full" onClick={() => setConfirm(true)} loading={submit.isPending}>
        <Send />
        {t.tests.finish}
      </Button>

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t.tests.finishConfirm}
        description={t.tests.finishText(answered, total)}
        confirmLabel={t.tests.finish}
        cancelLabel={t.common.cancel}
        loading={submit.isPending}
        onConfirm={() => submit.mutate()}
      />
    </div>
  );
}
