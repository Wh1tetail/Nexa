import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, ChevronLeft, ChevronRight, Clock, Flag } from "lucide-react";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageSkeleton } from "@/components/common";
import { LessonBlockView, LessonRunnerProvider, type LessonRunner } from "@/components/courses/LessonBlockView";
import { LessonStatusIcon } from "@/components/courses/CourseProgressView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { lessonHref } from "@/pages/student/StudentCoursesPage";
import { myCoursesApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { StudentLessonView } from "@/types/api";

/** A course lesson for the student: work is saved, listens counted, the lesson is finished once all exercises are checked. */
export default function StudentCourseLessonPage() {
  const { lessonId } = useParams();
  const id = Number(lessonId);
  const { t } = useI18n();
  const qc = useQueryClient();
  const key = ["my-courses", "lesson", id];
  const q = useQuery({ queryKey: key, queryFn: () => myCoursesApi.lesson(id) });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: key });
    qc.invalidateQueries({ queryKey: ["my-courses"], exact: true });
  };
  const runner = useMemo<LessonRunner | null>(() => {
    if (!q.data) return null;
    const d = q.data;
    return {
      check: (blockId, answers) => myCoursesApi.check(id, blockId, answers),
      saved: Object.fromEntries(d.blocks.map((b) => [b.block_id, b])),
      plays: Object.fromEntries(Object.entries(d.plays).map(([k, v]) => [Number(k), v])),
      countPlay: (blockId) => myCoursesApi.play(id, blockId).then((r) => r.plays),
      onChecked: refresh,
    };
    // the saved state is read once per lesson; later refetches only update the counters
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data?.lesson.id]);

  const complete = useMutation({
    mutationFn: () => myCoursesApi.complete(id),
    onSuccess: (d: StudentLessonView) => {
      qc.setQueryData(key, d);
      qc.invalidateQueries({ queryKey: ["my-courses"] });
      qc.invalidateQueries({ queryKey: ["my-course-progress"] });
      toast.success(t.myCourses.finishedToast);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading || (q.data && !runner)) return <PageSkeleton />;
  if (q.isError || !q.data || !runner) return <ErrorState onRetry={() => q.refetch()} />;
  const d = q.data;
  const les = d.lesson;
  const ready = d.exercises_done >= d.exercises_total;
  const wide = les.blocks.some((b) => b.type === "reading");

  return (
    <div className={cn("mx-auto space-y-5", wide ? "max-w-6xl" : "max-w-3xl")}>
      <Link to={`/student/courses/${d.assignment_id}`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {les.path.course_title}
      </Link>

      <Card className="p-5 sm:p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {les.path.level_title} · {les.path.module_title}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="page-title break-words">{les.title}</h1>
          <Badge variant={d.status === "completed" ? "success" : d.status === "in_progress" ? "default" : "neutral"} className="gap-1">
            <LessonStatusIcon status={d.status} className="size-3.5 text-current" />
            {t.myCourses.status[d.status]}
          </Badge>
        </div>
        {les.description && <p className="page-subtitle whitespace-pre-wrap">{les.description}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          {les.duration_minutes && (
            <span className="inline-flex items-center gap-1.5"><Clock className="size-4" />{t.common.minutes(les.duration_minutes)}</span>
          )}
          {d.exercises_total > 0 && <span>{t.myCourses.exercises(d.exercises_done, d.exercises_total)}</span>}
          {d.score_percent !== null && <span>{t.myCourses.result(d.score_percent)}</span>}
        </div>
        {d.exercises_total > 0 && <Progress value={(100 * d.exercises_done) / d.exercises_total} className="mt-3" />}
      </Card>

      <LessonRunnerProvider runner={runner}>
        {les.blocks.length ? (
          les.blocks.map((b) => <LessonBlockView key={b.id} lessonId={les.id} block={b} files={les.files} />)
        ) : (
          <Card><EmptyState title={t.courses.noBlocks} /></Card>
        )}
      </LessonRunnerProvider>

      <Card className={cn("flex flex-col items-center gap-3 p-5 text-center sm:p-6", d.status === "completed" && "border-success/40 bg-success-soft/40")}>
        {d.status === "completed" ? (
          <p className="flex items-center gap-2 font-semibold text-success-strong">
            <CheckCircle2 className="size-5" />
            {t.myCourses.finished}
          </p>
        ) : (
          <>
            {!ready && <p className="text-sm text-muted-foreground">{t.myCourses.finishHint}</p>}
            <Button size="lg" disabled={!ready} loading={complete.isPending} onClick={() => complete.mutate()}>
              <Flag />
              {t.myCourses.finish}
            </Button>
          </>
        )}
      </Card>

      <nav className="flex flex-wrap justify-between gap-2">
        {les.path.prev_id ? (
          <Button variant="outline" asChild>
            <Link to={lessonHref(les.path.prev_id)}><ChevronLeft />{t.courses.prev}</Link>
          </Button>
        ) : (
          <span />
        )}
        {les.path.next_id && (
          <Button asChild variant={d.status === "completed" ? "default" : "outline"}>
            <Link to={lessonHref(les.path.next_id)}>{t.courses.next}<ChevronRight /></Link>
          </Button>
        )}
      </nav>
    </div>
  );
}
