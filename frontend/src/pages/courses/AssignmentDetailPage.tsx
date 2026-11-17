import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CalendarClock, UserMinus, UserPlus, Users, UsersRound, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { EmptyState, ErrorState, Field, PageSkeleton, StatCard } from "@/components/common";
import { RecipientPicker } from "@/components/common/RecipientPicker";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { AssignmentDates } from "@/pages/courses/AssignmentsPage";
import { courseAssignmentsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { CourseAssignmentDetail } from "@/types/api";
import { fmtRelative, localInputToIso, toDateTimeInput } from "@/utils/format";

function DatesDialog({ a, open, onClose }: { a: CourseAssignmentDetail; open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [starts, setStarts] = useState("");
  const [due, setDue] = useState("");
  useEffect(() => {
    setStarts(toDateTimeInput(new Date(a.starts_at)));
    setDue(a.due_at ? toDateTimeInput(new Date(a.due_at)) : "");
  }, [open, a]);
  const save = useMutation({
    mutationFn: () => courseAssignmentsApi.update(a.id, { starts_at: localInputToIso(starts), due_at: localInputToIso(due), clear_due: !due }),
    onSuccess: (d) => {
      qc.setQueryData(["course-assignments", a.id], d);
      qc.invalidateQueries({ queryKey: ["course-assignments", "list"] });
      toast.success(t.common.saved);
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader><DialogTitle>{t.courseAssign.editDates}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-3">
          <Field label={t.courseAssign.startsAt} hint={t.courseAssign.startsHint}>
            <Input type="datetime-local" value={starts} onChange={(e) => setStarts(e.target.value)} />
          </Field>
          <Field label={t.courseAssign.dueAt} optional>
            <Input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={!starts} loading={save.isPending} onClick={() => save.mutate()}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AddStudentsDialog({ a, open, onClose }: { a: CourseAssignmentDetail; open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [ids, setIds] = useState<number[]>([]);
  useEffect(() => setIds([]), [open]);
  const active = a.students.filter((s) => !s.removed_at).map((s) => s.student_id);
  const add = useMutation({
    mutationFn: () => courseAssignmentsApi.addStudents(a.id, ids),
    onSuccess: (d) => {
      qc.setQueryData(["course-assignments", a.id], d);
      qc.invalidateQueries({ queryKey: ["course-assignments", "list"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="lg">
        <DialogHeader><DialogTitle>{t.courseAssign.addStudents}</DialogTitle></DialogHeader>
        <DialogBody>
          <RecipientPicker
            studentIds={ids}
            groupIds={[]}
            showGroups={false}
            disabledStudentIds={active}
            onChange={(v) => setIds(v.studentIds.filter((x) => !active.includes(x)))}
          />
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={!ids.length} loading={add.isPending} onClick={() => add.mutate()}>{t.courseAssign.addStudents}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function AssignmentDetailPage() {
  const { assignmentId } = useParams();
  const id = Number(assignmentId);
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["course-assignments", id], queryFn: () => courseAssignmentsApi.get(id) });
  const [dialog, setDialog] = useState<"dates" | "add" | "cancel" | null>(null);
  const [removing, setRemoving] = useState<number | null>(null);

  const cancel = useMutation({
    mutationFn: () => courseAssignmentsApi.cancel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["course-assignments"] });
      setDialog(null);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (studentId: number) => courseAssignmentsApi.removeStudent(id, studentId),
    onSuccess: (d) => {
      qc.setQueryData(["course-assignments", id], d);
      qc.invalidateQueries({ queryKey: ["course-assignments", "list"] });
      setRemoving(null);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const a = q.data;
  const live = !a.removed_at;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link to="/teacher/course-assignments" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.courseAssign.title}
      </Link>

      <Card className="p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Link to={`/teacher/courses/${a.course_id}`} className="hover:text-accent">{a.course_title}</Link>
              {" · "}
              {a.scope === "level" ? t.courseAssign.level : `${a.level} · ${t.courseAssign.module}`}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <h1 className="page-title break-words">{a.scope_title}</h1>
              {!live && <Badge variant="neutral">{t.courseAssign.cancelled}</Badge>}
            </div>
            <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                {a.group_name ? <UsersRound className="size-4" /> : <Users className="size-4" />}
                {a.group_name ? t.courseAssign.group(a.group_name) : t.courseAssign.individual}
              </span>
              <AssignmentDates a={a} />
            </p>
          </div>
          {live && (
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button variant="outline" onClick={() => setDialog("dates")}><CalendarClock />{t.courseAssign.editDates}</Button>
              <Button variant="ghost" className="hover:text-danger" onClick={() => setDialog("cancel")}><XCircle />{t.courseAssign.cancel}</Button>
            </div>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard icon={Users} label={t.common.students} value={a.students_count} hint={t.courseAssign.lessonsLabel + ": " + a.lessons_total} />
        <StatCard icon={CalendarClock} tone="accent" label={t.courseAssign.avgProgress} value={`${a.avg_percent ?? 0}%`} />
        <StatCard icon={UsersRound} tone="success" label={t.courseAssign.finishedLabel} value={a.completed_count} />
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-primary">{t.courseAssign.progress}</h2>
          {live && <Button size="sm" variant="soft" onClick={() => setDialog("add")}><UserPlus />{t.courseAssign.addStudents}</Button>}
        </div>
        {a.students.length ? (
          <Card className="divide-y">
            {a.students.map((s) => (
              <div key={s.student_id} className={cn("flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-4 sm:px-5", s.removed_at && "opacity-60")}>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium text-primary">
                    <Link to={`/teacher/students/${s.student_id}`} className="hover:text-accent">{s.full_name}</Link>
                    {s.removed_at && <Badge variant="neutral">{t.courseAssign.removed}</Badge>}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t.courseAssign.lastActivity}: {s.last_activity ? fmtRelative(s.last_activity, locale) : t.courseAssign.never}
                    {s.avg_score !== null && <> · {t.courseAssign.avgScore}: {s.avg_score}%</>}
                  </p>
                </div>
                <div className="flex w-full items-center gap-3 sm:w-64">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                      <span>{t.courseAssign.lessonsDone(s.lessons_completed, s.lessons_total)}</span>
                      <span className="tabular font-medium text-primary">{s.percent}%</span>
                    </div>
                    <Progress value={s.percent} indicatorClassName={s.percent === 100 ? "bg-success" : undefined} />
                  </div>
                  {live && !s.removed_at && (
                    <Button variant="ghost" size="icon-sm" className="shrink-0 hover:text-danger" aria-label={t.courseAssign.removeStudent} onClick={() => setRemoving(s.student_id)}>
                      <UserMinus />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </Card>
        ) : (
          <Card><EmptyState icon={Users} title={t.courseAssign.noStudents} /></Card>
        )}
      </section>

      <DatesDialog a={a} open={dialog === "dates"} onClose={() => setDialog(null)} />
      <AddStudentsDialog a={a} open={dialog === "add"} onClose={() => setDialog(null)} />
      <ConfirmDialog
        open={dialog === "cancel"}
        onOpenChange={(o) => !o && setDialog(null)}
        title={t.courseAssign.cancel}
        description={t.courseAssign.cancelText}
        confirmLabel={t.courseAssign.cancel}
        cancelLabel={t.common.cancel}
        destructive
        loading={cancel.isPending}
        onConfirm={() => cancel.mutate()}
      />
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={t.courseAssign.removeStudent}
        description={t.courseAssign.removeStudentText}
        confirmLabel={t.courseAssign.removeStudent}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => removing !== null && remove.mutate(removing)}
      />
    </div>
  );
}
