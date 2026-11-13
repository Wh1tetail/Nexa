import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, PenLine } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState, PageSkeleton } from "@/components/common";
import { AttemptBadge } from "@/components/common/StatusBadges";
import { QuestionView } from "@/components/tests/QuestionView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { testsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { fmtDateTime } from "@/utils/format";

export default function GradeAttemptPage() {
  const { testId, attemptId } = useParams();
  const id = Number(attemptId);
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["tests", "attempt", id], queryFn: () => testsApi.attempt(id) });
  const [grades, setGrades] = useState<Record<number, { points: string; comment: string }>>({});

  useEffect(() => {
    if (q.data) {
      setGrades(
        Object.fromEntries(
          q.data.answers.map((a) => [a.id, { points: a.points_awarded?.toString() ?? "", comment: a.teacher_comment ?? "" }]),
        ),
      );
    }
  }, [q.data]);

  const save = useMutation({
    mutationFn: () =>
      testsApi.grade(
        id,
        q.data!.answers
          .filter((a) => {
            const qq = q.data!.questions.find((x) => x.id === a.question_id)!;
            return qq.type === "short_answer" || a.points_awarded === null;
          })
          .map((a) => ({
            answer_id: a.id,
            points_awarded: Number(grades[a.id]?.points || 0),
            teacher_comment: grades[a.id]?.comment.trim() || null,
          })),
      ),
    onSuccess: (data) => {
      qc.setQueryData(["tests", "attempt", id], data);
      qc.invalidateQueries({ queryKey: ["tests"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(t.tests.graded);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const a = q.data;
  const byQ = Object.fromEntries(a.answers.map((x) => [x.question_id, x]));

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to={`/teacher/tests/${testId}`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {a.test_title}
      </Link>
      <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-lg font-semibold text-primary">{a.student_name}</p>
          <p className="text-sm text-muted-foreground">{fmtDateTime(a.submitted_at, locale)}</p>
        </div>
        <div className="flex items-center gap-2">
          <AttemptBadge status={a.status} />
          {a.score !== null && (
            <Badge variant="neutral" className="tabular text-sm">
              {a.score}/{a.max_score}
              {a.percent !== null && ` · ${a.percent}%`}
            </Badge>
          )}
        </div>
      </Card>

      <div className="grid gap-4">
        {a.questions.map((qq, i) => {
          const ans = byQ[qq.id];
          const manual = qq.type === "short_answer";
          return (
            <QuestionView
              key={qq.id}
              index={i}
              question={qq}
              value={ans?.answer ?? []}
              result={ans && ans.points_awarded !== null ? ans : undefined}
              footer={
                ans && manual ? (
                  <div className="mt-4 grid gap-2 rounded-xl border border-dashed p-3 sm:grid-cols-[120px_1fr]">
                    <label className="grid gap-1 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><PenLine className="size-3" />{t.tests.points} (0–{qq.points})</span>
                      <Input
                        type="number"
                        min={0}
                        max={qq.points}
                        step={0.5}
                        value={grades[ans.id]?.points ?? ""}
                        onChange={(e) => setGrades((g) => ({ ...g, [ans.id]: { ...g[ans.id], points: e.target.value } }))}
                        className="h-9"
                      />
                    </label>
                    <label className="grid gap-1 text-xs text-muted-foreground">
                      {t.common.comment}
                      <Input
                        value={grades[ans.id]?.comment ?? ""}
                        onChange={(e) => setGrades((g) => ({ ...g, [ans.id]: { ...g[ans.id], comment: e.target.value } }))}
                        className="h-9"
                      />
                    </label>
                  </div>
                ) : null
              }
            />
          );
        })}
      </div>

      <div className="sticky bottom-0 -mx-4 border-t bg-background/90 px-4 py-3 backdrop-blur sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0">
        <Button size="lg" className="w-full" loading={save.isPending} onClick={() => save.mutate()}>
          {t.tests.saveGrade}
        </Button>
      </div>
    </div>
  );
}
