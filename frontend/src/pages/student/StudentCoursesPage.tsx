import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarClock, GraduationCap, Lock, Play } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader, PageSkeleton } from "@/components/common";
import { CourseMap, LessonStatusIcon } from "@/components/courses/CourseProgressView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { myCoursesApi } from "@/services/api";
import type { LessonState, StudentCourseItem } from "@/types/api";
import { fmtDateTime } from "@/utils/format";

export const lessonHref = (id: number) => `/student/course-lessons/${id}`;

function Deadline({ c }: { c: StudentCourseItem }) {
  const { t, locale } = useI18n();
  if (!c.started) {
    return (
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        <Lock className="size-3.5" />
        {t.myCourses.startsOn(fmtDateTime(c.starts_at, locale))}
      </span>
    );
  }
  if (!c.due_at) return null;
  return (
    <span className={cn("inline-flex items-center gap-1", c.overdue ? "text-danger" : "text-muted-foreground")}>
      <CalendarClock className="size-3.5" />
      {c.overdue ? t.myCourses.overdue : t.myCourses.dueBy(fmtDateTime(c.due_at, locale))}
    </span>
  );
}

function ContinueButton({ c, size }: { c: StudentCourseItem; size?: "sm" }) {
  const { t } = useI18n();
  if (!c.started || !c.next_lesson_id) return null;
  return (
    <Button asChild size={size}>
      <Link to={lessonHref(c.next_lesson_id)}>
        <Play />
        {c.lessons_completed ? t.myCourses.continue : t.myCourses.start}
      </Link>
    </Button>
  );
}

function CourseHeader({ c }: { c: StudentCourseItem }) {
  const { t } = useI18n();
  return (
    <>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {c.course_title} · {c.level}
      </p>
      <h3 className="break-words text-lg font-semibold text-primary">{c.scope_title}</h3>
      {c.teacher_name && <p className="text-xs text-muted-foreground">{t.myCourses.teacher}: {c.teacher_name}</p>}
      <div className="mt-3">
        <div className="mb-1 flex justify-between text-xs text-muted-foreground">
          <span>{t.myCourses.completedOf(c.lessons_completed, c.lessons_total)}</span>
          <span className="tabular font-medium text-primary">{c.percent}%</span>
        </div>
        <Progress value={c.percent} indicatorClassName={c.percent === 100 ? "bg-success" : undefined} />
      </div>
    </>
  );
}

/** "My courses": what the teacher assigned, with progress. */
export default function StudentCoursesPage() {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["my-courses"], queryFn: myCoursesApi.list });
  return (
    <div>
      <PageHeader title={t.myCourses.title} subtitle={t.myCourses.subtitle} />
      {q.isLoading ? (
        <CardListSkeleton rows={2} />
      ) : q.isError || !q.data ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data.length ? (
        <Card><EmptyState icon={GraduationCap} title={t.myCourses.empty} text={t.myCourses.emptyHint} /></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {q.data.map((c) => (
            <Card key={c.assignment_id} className={cn("flex flex-col p-5", !c.started && "opacity-80")}>
              <Link to={`/student/courses/${c.assignment_id}`} className="group">
                <div className="group-hover:[&_h3]:text-accent"><CourseHeader c={c} /></div>
              </Link>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs">
                <Deadline c={c} />
                <ContinueButton c={c} size="sm" />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

/** One assigned course: progress and the course map. */
export function StudentCoursePage() {
  const { assignmentId } = useParams();
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["my-courses", Number(assignmentId)], queryFn: () => myCoursesApi.get(Number(assignmentId)) });
  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const c = q.data;
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Link to="/student/courses" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.myCourses.backToCourses}
      </Link>
      <Card className="p-5 sm:p-6">
        <CourseHeader c={c} />
        {c.course_description && <p className="mt-3 whitespace-pre-wrap text-sm text-muted-foreground">{c.course_description}</p>}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm">
          <Deadline c={c} />
          <ContinueButton c={c} />
        </div>
      </Card>
      <section>
        <h2 className="mb-3 text-base font-semibold text-primary">{t.myCourses.map}</h2>
        <CourseMap modules={c.modules} lessonHref={c.started ? lessonHref : undefined} />
      </section>
    </div>
  );
}

type Filter = "all" | LessonState;

/** "My lessons": every lesson of the started courses, with a status filter. */
export function StudentLessonsPage() {
  const { t } = useI18n();
  const [filter, setFilter] = useState<Filter>("all");
  const q = useQuery({ queryKey: ["my-courses", "lessons"], queryFn: myCoursesApi.lessons });
  const rows = (q.data ?? []).filter((r) => filter === "all" || r.status === filter);
  return (
    <div>
      <PageHeader title={t.myCourses.lessonsTitle} subtitle={t.myCourses.lessonsSubtitle} />
      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)} className="mb-4">
        <TabsList>
          <TabsTrigger value="all">{t.myCourses.filterAll}</TabsTrigger>
          <TabsTrigger value="in_progress">{t.myCourses.filterActive}</TabsTrigger>
          <TabsTrigger value="not_started">{t.myCourses.filterNew}</TabsTrigger>
          <TabsTrigger value="completed">{t.myCourses.filterDone}</TabsTrigger>
        </TabsList>
      </Tabs>
      {q.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !rows.length ? (
        <Card><EmptyState icon={GraduationCap} title={t.myCourses.noLessons} /></Card>
      ) : (
        <Card className="divide-y">
          {rows.map((r) => (
            <Link key={r.id} to={lessonHref(r.id)} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-secondary/50 sm:px-5">
              <LessonStatusIcon status={r.status} className="shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="break-words font-medium text-primary">{r.title}</p>
                <p className="truncate text-xs text-muted-foreground">{r.course_title} · {r.level} · {r.module_title}</p>
              </div>
              {r.score_percent !== null && <Badge variant="neutral" className="tabular">{r.score_percent}%</Badge>}
              <span className="hidden text-xs text-muted-foreground sm:inline">{t.myCourses.status[r.status]}</span>
            </Link>
          ))}
        </Card>
      )}
    </div>
  );
}
