import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, ClipboardCheck, Download, Repeat, MoreHorizontal, Pencil, Plus, RotateCcw, Trash2, Users, Video, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { AttendanceBadge, LessonBadge } from "@/components/common/StatusBadges";
import { currentMonday, shiftDays, WeekCalendar, type CalendarEvent } from "@/components/calendar/WeekCalendar";
import { AttendanceDialog, ExtendSeriesDialog, LessonFormDialog } from "@/components/attendance/LessonDialogs";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input, NativeSelect } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { lessonsApi, studentsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Lesson } from "@/types/api";
import { addDays, fmtDate, fmtDateTime, fmtTime, fmtWeekday, toDateInput } from "@/utils/format";

function LessonCard({
  lesson,
  onMark,
  onEdit,
  onDelete,
  onExtend,
}: {
  lesson: Lesson;
  onMark: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onExtend: () => void;
}) {
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const marked = lesson.attendance.filter((a) => a.status).length;
  const total = lesson.attendance.length;
  const isPast = new Date(lesson.starts_at).getTime() < Date.now();
  const toggleCancel = useMutation({
    mutationFn: (scope: "one" | "following") =>
      lessonsApi.update(lesson.id, { status: lesson.status === "cancelled" ? "scheduled" : "cancelled" }, scope),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lessons"] });
      qc.invalidateQueries({ queryKey: ["attendance"] });
      toast.success(lesson.status === "cancelled" ? t.common.saved : t.lessons.cancelled);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Card className={cn("p-4 sm:p-5", lesson.status === "cancelled" && "opacity-60")}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4 sm:w-44 sm:shrink-0">
          <div className={cn("flex w-16 shrink-0 flex-col items-center rounded-xl py-2", isPast ? "bg-secondary text-primary" : "bg-accent-soft text-accent")}>
            <span className="text-[11px] font-medium">{fmtWeekday(lesson.starts_at, locale).split(",")[0]}</span>
            <span className="text-sm font-semibold">{fmtDate(lesson.starts_at, locale, { day: "numeric", month: "short" })}</span>
          </div>
          <div className="text-sm">
            <p className="tabular font-semibold text-primary">{fmtTime(lesson.starts_at, locale)}</p>
            <p className="text-xs text-muted-foreground">{t.common.minutes(lesson.duration_minutes)}</p>
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate font-medium text-primary">{lesson.title}</p>
            <LessonBadge status={lesson.status} />
            {lesson.series_id && (
              <span title={t.lessons.series} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Repeat className="size-3.5" />
                <span className="sr-only">{t.lessons.series}</span>
                {lesson.series_position && lesson.series_total && t.lessons.seriesOf(lesson.series_position, lesson.series_total)}
              </span>
            )}
          </div>
          <p className="mt-0.5 truncate text-sm text-muted-foreground">
            {lesson.topic ?? "—"}
          </p>
          <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Users className="size-3.5" />
              {t.common.studentsCount(total)}
            </span>
            {lesson.status !== "cancelled" && isPast && (
              <span className="inline-flex items-center gap-2">
                {t.lessons.marked}: {marked}/{total}
                <Progress value={(marked * 100) / Math.max(total, 1)} className="h-1 w-16" />
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {lesson.meeting_url && lesson.status === "scheduled" && (
            <Button variant="ghost" size="icon-sm" asChild>
              <a href={lesson.meeting_url} target="_blank" rel="noreferrer noopener" aria-label={t.lessons.meetingUrl}>
                <Video />
              </a>
            </Button>
          )}
          {lesson.status !== "cancelled" && (
            <Button size="sm" variant={isPast && marked < total ? "default" : "outline"} onClick={onMark} className="flex-1 sm:flex-none">
              <ClipboardCheck />
              {t.lessons.markAttendance}
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={t.common.actions}><MoreHorizontal /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={onEdit}><Pencil />{t.common.edit}</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => toggleCancel.mutate("one")}>
                {lesson.status === "cancelled" ? <><RotateCcw />{t.lessons.restoreLesson}</> : <><XCircle />{t.lessons.cancelLesson}</>}
              </DropdownMenuItem>
              {lesson.series_id && lesson.status === "scheduled" && lesson.series_position !== lesson.series_total && (
                <DropdownMenuItem onSelect={() => toggleCancel.mutate("following")}>
                  <XCircle />
                  {t.lessons.cancelFollowing}
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onSelect={onExtend}>
                <Repeat />
                {lesson.series_id ? t.lessons.extendSeries : t.lessons.makeRecurring}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={onDelete}><Trash2 />{t.common.delete}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </Card>
  );
}

export default function LessonsPage() {
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const today = new Date();
  const [from, setFrom] = useState(toDateInput(addDays(today, -30)));
  const [to, setTo] = useState(toDateInput(addDays(today, 30)));
  const [studentId, setStudentId] = useState<number | "">("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Lesson | undefined>();
  const [marking, setMarking] = useState<Lesson | null>(null);
  const [deleting, setDeleting] = useState<Lesson | null>(null);
  const [extending, setExtending] = useState<Lesson | null>(null);

  const filter = { date_from: from, date_to: to, student_id: studentId };
  const lessons = useQuery({ queryKey: ["lessons", filter], queryFn: () => lessonsApi.list(filter), placeholderData: (p) => p });
  // Calendar tab: its own week window (one extra day each side covers time zone edges)
  const [week, setWeek] = useState(currentMonday());
  const weekFilter = { date_from: shiftDays(week, -1), date_to: shiftDays(week, 7), student_id: studentId };
  const weekLessons = useQuery({
    queryKey: ["lessons", "week", weekFilter],
    queryFn: () => lessonsApi.list(weekFilter),
    placeholderData: (p) => p,
  });
  const weekEvents: CalendarEvent[] = (weekLessons.data ?? []).map((l) => ({
    id: l.id,
    title: l.title,
    subtitle: [l.topic, t.common.studentsCount(l.attendance.length)].filter(Boolean).join(" · "),
    startsAt: l.starts_at,
    durationMinutes: l.duration_minutes,
    tone: l.status,
    meetingUrl: l.meeting_url,
  }));
  const openFromCalendar = (id: number) => {
    const l = weekLessons.data?.find((x) => x.id === id);
    if (!l) return;
    if (l.status !== "cancelled" && new Date(l.starts_at).getTime() <= Date.now()) setMarking(l);
    else {
      setEditing(l);
      setCreating(true);
    }
  };
  const records = useQuery({ queryKey: ["attendance", "records", filter], queryFn: () => lessonsApi.records(filter), placeholderData: (p) => p });
  const stats = useQuery({ queryKey: ["attendance", "stats", filter], queryFn: () => lessonsApi.stats(filter), placeholderData: (p) => p });
  const students = useQuery({ queryKey: ["students", "picker"], queryFn: () => studentsApi.list({ active: true }) });

  const remove = useMutation({
    mutationFn: ({ id, scope }: { id: number; scope: "one" | "following" }) => lessonsApi.remove(id, scope),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lessons"] });
      qc.invalidateQueries({ queryKey: ["attendance"] });
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      setDeleting(null);
      toast.success(t.common.deleted);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const [exporting, setExporting] = useState(false);
  async function exportCsv() {
    setExporting(true);
    try {
      await lessonsApi.exportCsv(filter);
      toast.success(t.lessons.exported);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setExporting(false);
    }
  }

  const { upcoming, past } = useMemo(() => {
    const now = Date.now();
    const all = lessons.data ?? [];
    return {
      upcoming: all.filter((l) => new Date(l.starts_at).getTime() >= now),
      past: all.filter((l) => new Date(l.starts_at).getTime() < now).reverse(),
    };
  }, [lessons.data]);

  const setPreset = (days: number) => {
    setFrom(toDateInput(addDays(new Date(), -days)));
    setTo(toDateInput(addDays(new Date(), days)));
  };

  return (
    <div>
      <PageHeader
        title={t.lessons.title}
        subtitle={t.lessons.subtitle}
        actions={
          <>
            <Button variant="outline" loading={exporting} onClick={exportCsv}>
              <Download />
              {t.lessons.exportCsv}
            </Button>
            <Button onClick={() => { setEditing(undefined); setCreating(true); }}><Plus />{t.lessons.create}</Button>
          </>
        }
      />

      <Card className="mb-5 p-3 sm:p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[auto_auto_1fr_auto]">
          <label className="grid gap-1 text-xs text-muted-foreground">
            {t.common.from}
            <Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="grid gap-1 text-xs text-muted-foreground">
            {t.common.to}
            <Input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} />
          </label>
          <label className="grid gap-1 text-xs text-muted-foreground">
            {t.common.student}
            <NativeSelect value={studentId} onChange={(e) => setStudentId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">{t.lessons.allStudents}</option>
              {students.data?.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
            </NativeSelect>
          </label>
          <div className="flex items-end gap-1">
            <Button variant="secondary" size="sm" className="h-10" onClick={() => setPreset(7)}>{t.lessons.week}</Button>
            <Button variant="secondary" size="sm" className="h-10" onClick={() => setPreset(30)}>{t.lessons.month}</Button>
          </div>
        </div>
      </Card>

      <Tabs defaultValue="lessons">
        <TabsList>
          <TabsTrigger value="lessons">{t.lessons.tabLessons}</TabsTrigger>
          <TabsTrigger value="calendar">{t.lessons.tabCalendar}</TabsTrigger>
          <TabsTrigger value="table">{t.lessons.tabTable}</TabsTrigger>
          <TabsTrigger value="stats">{t.lessons.tabStats}</TabsTrigger>
        </TabsList>

        <TabsContent value="calendar">
          <WeekCalendar
            weekStart={week}
            onWeekChange={setWeek}
            events={weekEvents}
            loading={weekLessons.isLoading}
            onEventClick={openFromCalendar}
          />
        </TabsContent>

        <TabsContent value="lessons" className="space-y-6">
          {lessons.isLoading ? (
            <CardListSkeleton />
          ) : lessons.isError ? (
            <ErrorState onRetry={() => lessons.refetch()} />
          ) : !lessons.data?.length ? (
            <Card><EmptyState icon={CalendarCheck} title={t.lessons.emptyLessons} /></Card>
          ) : (
            <>
              {upcoming.length > 0 && (
                <section className="grid gap-3">
                  <h2 className="text-sm font-semibold text-muted-foreground">{t.lessons.upcoming} · {upcoming.length}</h2>
                  {upcoming.map((l) => (
                    <LessonCard key={l.id} lesson={l} onMark={() => setMarking(l)} onEdit={() => { setEditing(l); setCreating(true); }} onDelete={() => setDeleting(l)} onExtend={() => setExtending(l)} />
                  ))}
                </section>
              )}
              {past.length > 0 && (
                <section className="grid gap-3">
                  <h2 className="text-sm font-semibold text-muted-foreground">{t.lessons.past} · {past.length}</h2>
                  {past.map((l) => (
                    <LessonCard key={l.id} lesson={l} onMark={() => setMarking(l)} onEdit={() => { setEditing(l); setCreating(true); }} onDelete={() => setDeleting(l)} onExtend={() => setExtending(l)} />
                  ))}
                </section>
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="table">
          <Card className="overflow-hidden">
            {records.isLoading ? (
              <CardListSkeleton />
            ) : records.data?.length ? (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>{t.common.date}</TableHead>
                    <TableHead>{t.common.student}</TableHead>
                    <TableHead>{t.lessons.name}</TableHead>
                    <TableHead>{t.common.status}</TableHead>
                    <TableHead>{t.common.comment}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {records.data.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="whitespace-nowrap">{fmtDateTime(r.starts_at, locale)}</TableCell>
                      <TableCell className="whitespace-nowrap font-medium text-primary">{r.student_name}</TableCell>
                      <TableCell className="max-w-[200px] truncate text-muted-foreground">{r.lesson_title}</TableCell>
                      <TableCell>{r.lesson_status === "cancelled" ? <LessonBadge status="cancelled" /> : <AttendanceBadge status={r.status} />}</TableCell>
                      <TableCell className="max-w-[220px] truncate text-muted-foreground">{r.comment ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState title={t.lessons.emptyRecords} />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="stats">
          <Card className="overflow-hidden">
            {stats.isLoading ? (
              <CardListSkeleton />
            ) : stats.data?.length ? (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>{t.common.student}</TableHead>
                    <TableHead className="text-center">{t.lessons.present}</TableHead>
                    <TableHead className="text-center">{t.lessons.late}</TableHead>
                    <TableHead className="text-center">{t.lessons.absent}</TableHead>
                    <TableHead className="text-center">{t.lessons.excused}</TableHead>
                    <TableHead className="min-w-[160px]">{t.lessons.rate}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {stats.data.map((s) => (
                    <TableRow key={s.student_id}>
                      <TableCell className="whitespace-nowrap font-medium text-primary">{s.student_name}</TableCell>
                      <TableCell className="tabular text-center">{s.present}</TableCell>
                      <TableCell className="tabular text-center">{s.late}</TableCell>
                      <TableCell className="tabular text-center">{s.absent}</TableCell>
                      <TableCell className="tabular text-center">{s.excused}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress
                            value={s.attendance_rate}
                            className="h-1.5 flex-1"
                            indicatorClassName={s.attendance_rate >= 80 ? "bg-success" : s.attendance_rate >= 50 ? "bg-warning" : "bg-danger"}
                          />
                          <Badge variant="neutral" className="tabular w-12 justify-center">{s.total_marked ? `${s.attendance_rate}%` : "—"}</Badge>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState title={t.lessons.emptyRecords} />
            )}
          </Card>
        </TabsContent>
      </Tabs>

      <LessonFormDialog open={creating} onOpenChange={setCreating} lesson={editing} />
      <ExtendSeriesDialog lesson={extending} onClose={() => setExtending(null)} />
      <AttendanceDialog open={!!marking} onOpenChange={(o) => !o && setMarking(null)} lesson={marking} />
      <ConfirmDialog
        open={!!deleting && !deleting.series_id}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t.lessons.deleteTitle}
        description={t.lessons.deleteText}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate({ id: deleting.id, scope: "one" })}
      />
      <Dialog open={!!deleting?.series_id} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle>{t.lessons.deleteScopeTitle}</DialogTitle>
            <DialogDescription>{t.lessons.deleteSeriesText}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)}>{t.common.cancel}</Button>
            <Button variant="outline" className="text-danger" loading={remove.isPending && remove.variables?.scope === "one"}
              onClick={() => deleting && remove.mutate({ id: deleting.id, scope: "one" })}>
              {t.lessons.deleteOnlyThis}
            </Button>
            <Button variant="destructive" loading={remove.isPending && remove.variables?.scope === "following"}
              onClick={() => deleting && remove.mutate({ id: deleting.id, scope: "following" })}>
              {t.lessons.deleteFollowing}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
