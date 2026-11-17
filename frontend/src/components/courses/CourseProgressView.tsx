import { BookCheck, CheckCircle2, Circle, CircleDot, GraduationCap, Layers, ListChecks, Target } from "lucide-react";
import { Link } from "react-router-dom";

import { StatCard } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import type { CourseProgress, LessonState, StudentCourseModule } from "@/types/api";

export function LessonStatusIcon({ status, className }: { status: LessonState; className?: string }) {
  const { t } = useI18n();
  const label = t.myCourses.status[status];
  if (status === "completed") return <CheckCircle2 className={cn("size-4 text-success", className)} aria-label={label} />;
  if (status === "in_progress") return <CircleDot className={cn("size-4 text-accent", className)} aria-label={label} />;
  return <Circle className={cn("size-4 text-muted-foreground/60", className)} aria-label={label} />;
}

/** Modules and their lessons with statuses; lessons are links when `lessonHref` is given. */
export function CourseMap({ modules, lessonHref }: { modules: StudentCourseModule[]; lessonHref?: (id: number) => string }) {
  const { t } = useI18n();
  return (
    <ol className="grid gap-3">
      {modules.map((m, i) => (
        <li key={m.id} className="rounded-xl border p-3 sm:p-4">
          <div className="flex items-start gap-2">
            <span
              className={cn(
                "flex size-7 shrink-0 items-center justify-center rounded-lg text-xs font-semibold",
                m.completed ? "bg-success-soft text-success-strong" : "bg-secondary text-muted-foreground",
              )}
            >
              {m.completed ? <CheckCircle2 className="size-4" /> : i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="break-words font-medium text-primary">{m.title}</p>
              {m.completed && <p className="text-xs text-success-strong">{t.myCourses.moduleDone}</p>}
            </div>
          </div>
          <ul className="mt-2 grid gap-0.5 sm:pl-9">
            {m.lessons.map((les) => {
              const body = (
                <>
                  <LessonStatusIcon status={les.status} className="shrink-0" />
                  <span className="min-w-0 flex-1 break-words">{les.title}</span>
                  {les.score_percent !== null && <span className="tabular text-xs text-muted-foreground">{les.score_percent}%</span>}
                </>
              );
              return (
                <li key={les.id}>
                  {lessonHref ? (
                    <Link to={lessonHref(les.id)} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-primary transition-colors hover:bg-secondary">
                      {body}
                    </Link>
                  ) : (
                    <div className="flex items-center gap-2 px-2 py-1.5 text-sm text-primary">{body}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ol>
  );
}

/** Course part of "My progress" (also shown to the teacher on a student's page). */
export function CourseProgressView({ data, lessonHref }: { data: CourseProgress; lessonHref?: (id: number) => string }) {
  const { t } = useI18n();
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard icon={GraduationCap} tone="accent" label={t.myCourses.currentLevel} value={data.english_level} />
        <StatCard icon={BookCheck} tone="success" label={t.myCourses.lessonsCompleted} value={data.lessons_completed} />
        <StatCard icon={Target} label={t.myCourses.lessonsRemaining} value={data.lessons_remaining} />
        <StatCard icon={Layers} tone="primary" label={t.myCourses.modulesCompleted} value={data.modules_completed} />
        <StatCard icon={ListChecks} tone="warning" label={t.myCourses.exercisesDone} value={data.exercises_done} />
        <StatCard icon={CheckCircle2} tone="success" label={t.myCourses.avgScore} value={data.avg_score === null ? "—" : `${data.avg_score}%`} />
      </div>
      {data.items.length ? (
        data.items.map((it) => (
          <Card key={`${it.course_id}-${it.level}`} className="p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{it.course_title}</p>
                <h3 className="text-lg font-semibold text-primary">{it.level_title}</h3>
              </div>
              <Badge variant={it.percent === 100 ? "success" : "neutral"} className="tabular">{t.myCourses.levelProgress(it.percent)}</Badge>
            </div>
            <Progress value={it.percent} className="mt-3 h-3" indicatorClassName={it.percent === 100 ? "bg-success" : undefined} />
            <p className="mt-2 flex flex-wrap gap-x-3 text-sm text-muted-foreground">
              <span>{t.myCourses.completedOf(it.lessons_completed, it.lessons_total)}</span>
              <span>{t.myCourses.modulesCompleted}: {it.modules_completed}/{it.modules_total}</span>
              {it.avg_score !== null && <span>{t.myCourses.avgScore}: {it.avg_score}%</span>}
            </p>
            <h4 className="mb-2 mt-4 text-sm font-semibold text-primary">{t.myCourses.map}</h4>
            <CourseMap modules={it.modules} lessonHref={lessonHref} />
          </Card>
        ))
      ) : (
        <Card className="p-6 text-center text-sm text-muted-foreground">{t.myCourses.noProgress}</Card>
      )}
    </div>
  );
}
