import { useQuery } from "@tanstack/react-query";
import { CalendarClock, GraduationCap, Layers, Users, UsersRound } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { courseAssignmentsApi } from "@/services/api";
import type { CourseAssignmentItem } from "@/types/api";
import { fmtDate, fmtRelative } from "@/utils/format";

function Dates({ a }: { a: Pick<CourseAssignmentItem, "starts_at" | "due_at"> }) {
  const { t, locale } = useI18n();
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2">
      <CalendarClock className="size-3.5" />
      {t.courseAssign.starts(fmtDate(a.starts_at, locale))}
      {a.due_at && <span>· {t.courseAssign.due(fmtDate(a.due_at, locale))}</span>}
    </span>
  );
}

function AssignmentCard({ a }: { a: CourseAssignmentItem }) {
  const { t } = useI18n();
  return (
    <Link to={`/teacher/course-assignments/${a.id}`} className="group block focus-visible:outline-none">
      <Card className={cn("p-4 transition-all group-hover:shadow-lift sm:p-5", a.removed_at && "opacity-70")}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            {a.scope === "level" ? <GraduationCap className="size-5" /> : <Layers className="size-5" />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {a.course_title} · {a.scope === "level" ? t.courseAssign.level : `${a.level} · ${t.courseAssign.module}`}
            </p>
            <p className="break-words font-semibold text-primary group-hover:text-accent">{a.scope_title}</p>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                {a.group_name ? <UsersRound className="size-3.5" /> : <Users className="size-3.5" />}
                {a.group_name ? t.courseAssign.group(a.group_name) : t.courseAssign.individual}
                {" · "}
                {t.courseAssign.studentsCount(a.students_count)}
              </span>
              <span>{t.courseAssign.lessonsTotal(a.lessons_total)}</span>
              <Dates a={a} />
            </p>
          </div>
          <div className="w-full shrink-0 sm:w-44">
            {a.removed_at ? (
              <Badge variant="neutral">{t.courseAssign.cancelled}</Badge>
            ) : (
              <>
                <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>{t.courseAssign.avgProgress}</span>
                  <span className="tabular font-medium text-primary">{a.avg_percent ?? 0}%</span>
                </div>
                <Progress value={a.avg_percent ?? 0} />
                {a.completed_count > 0 && <p className="mt-1 text-xs text-success-strong">{t.courseAssign.finished(a.completed_count)}</p>}
              </>
            )}
          </div>
        </div>
      </Card>
    </Link>
  );
}

function StudentsTab() {
  const { t, locale } = useI18n();
  const q = useQuery({ queryKey: ["course-assignments", "students"], queryFn: courseAssignmentsApi.students });
  if (q.isLoading) return <CardListSkeleton rows={3} />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data.length) return <Card><EmptyState icon={Users} title={t.courseAssign.noStudents} /></Card>;
  return (
    <Card className="divide-y">
      {q.data.map((r) => (
        <Link
          key={r.student_id}
          to={`/teacher/students/${r.student_id}`}
          className="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-secondary/50 sm:flex-row sm:items-center sm:gap-4 sm:px-5"
        >
          <div className="min-w-0 flex-1">
            <p className="flex flex-wrap items-center gap-2 font-medium text-primary">
              {r.full_name}
              <Badge variant="neutral">{r.english_level}</Badge>
            </p>
            <p className="text-xs text-muted-foreground">
              {t.courseAssign.assignments(r.assignments)} · {t.courseAssign.lastActivity}:{" "}
              {r.last_activity ? fmtRelative(r.last_activity, locale) : t.courseAssign.never}
              {r.avg_score !== null && <> · {t.courseAssign.avgScore}: {r.avg_score}%</>}
            </p>
          </div>
          <div className="w-full sm:w-52">
            <div className="mb-1 flex justify-between text-xs text-muted-foreground">
              <span>{t.courseAssign.lessonsDone(r.lessons_completed, r.lessons_total)}</span>
              <span className="tabular font-medium text-primary">{r.percent}%</span>
            </div>
            <Progress value={r.percent} />
          </div>
        </Link>
      ))}
    </Card>
  );
}

/** Teacher: what was assigned to whom, and students' progress in courses. */
export default function AssignmentsPage() {
  const { t } = useI18n();
  const [showCancelled, setShowCancelled] = useState(false);
  const q = useQuery({ queryKey: ["course-assignments", "list", showCancelled], queryFn: () => courseAssignmentsApi.list(showCancelled) });

  return (
    <div>
      <PageHeader title={t.courseAssign.title} subtitle={t.courseAssign.subtitle} />
      <Tabs defaultValue="assignments">
        <TabsList>
          <TabsTrigger value="assignments">{t.courseAssign.tabAssignments}</TabsTrigger>
          <TabsTrigger value="students">{t.courseAssign.tabStudents}</TabsTrigger>
        </TabsList>
        <TabsContent value="assignments" className="space-y-3">
          <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-muted-foreground">
            <Checkbox checked={showCancelled} onCheckedChange={(v) => setShowCancelled(v === true)} />
            {t.courseAssign.showCancelled}
          </label>
          {q.isLoading ? (
            <CardListSkeleton rows={3} />
          ) : q.isError || !q.data ? (
            <ErrorState onRetry={() => q.refetch()} />
          ) : !q.data.length ? (
            <Card>
              <EmptyState
                icon={GraduationCap}
                title={t.courseAssign.empty}
                text={t.courseAssign.emptyHint}
                action={<Button asChild variant="outline"><Link to="/teacher/courses">{t.courseAssign.openCourses}</Link></Button>}
              />
            </Card>
          ) : (
            q.data.map((a) => <AssignmentCard key={a.id} a={a} />)
          )}
        </TabsContent>
        <TabsContent value="students">
          <StudentsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export { Dates as AssignmentDates };
