import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CalendarCheck, CalendarDays, CalendarX2, Mail, MessageSquare, Pencil, Percent, Phone, Plus, Power, Send } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ProgressView } from "@/components/analytics/ProgressView";
import { CourseProgressView } from "@/components/courses/CourseProgressView";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageSkeleton, StatCard, StatsSkeleton } from "@/components/common";
import { showInviteToast } from "@/components/common/InviteToast";
import { AttemptBadge, AttendanceBadge, SubmissionBadge, SubscriptionBadge } from "@/components/common/StatusBadges";
import { StudentFormDialog } from "@/components/students/StudentFormDialog";
import { SubscriptionActions, SubscriptionFormDialog, useCanManageSubscriptions } from "@/components/subscriptions/SubscriptionDialogs";
import { SubscriptionWidget } from "@/components/subscriptions/SubscriptionWidget";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { analyticsApi, courseAssignmentsApi, lessonsApi, studentsApi, testsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { fmtDate, fmtDateTime, toDateInput } from "@/utils/format";
import { scoreVariant } from "@/utils/status";

export default function StudentProfilePage() {
  const { studentId } = useParams();
  const id = Number(studentId);
  const { t, locale } = useI18n();
  const canManageSubs = useCanManageSubscriptions();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [newSub, setNewSub] = useState(false);

  const student = useQuery({ queryKey: ["students", id], queryFn: () => studentsApi.get(id) });
  const subs = useQuery({ queryKey: ["subscriptions", "student", id], queryFn: () => studentsApi.subscriptions(id) });
  const hw = useQuery({ queryKey: ["students", id, "homework"], queryFn: () => studentsApi.homeworkHistory(id) });
  const tests = useQuery({ queryKey: ["students", id, "tests"], queryFn: () => testsApi.allAttempts({ student_id: id }) });
  const att = useQuery({ queryKey: ["students", id, "attendance"], queryFn: () => lessonsApi.records({ student_id: id }) });
  const stats = useQuery({ queryKey: ["students", id, "attendance-stats"], queryFn: () => lessonsApi.stats({ student_id: id }) });

  const invite = useMutation({
    mutationFn: () => studentsApi.invite(id),
    onSuccess: (r) => showInviteToast(t.students.inviteSent, student.data!.email, r.dev_invite_url, t.students.devLink),
    onError: (e) => toast.error(errorMessage(e)),
  });

  const toggleActive = useMutation({
    mutationFn: () => studentsApi.update(id, { is_active: !student.data!.is_active }),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success(s.is_active ? t.students.activated : t.students.deactivated);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (student.isLoading) return <PageSkeleton />;
  if (student.isError || !student.data) return <ErrorState onRetry={() => student.refetch()} />;
  const s = student.data;
  // same rule as the backend: latest subscription that has already started, else the next upcoming one
  const today = toDateInput(new Date());
  const allSubs = subs.data ?? [];
  const current = allSubs.find((x) => x.start_date <= today) ?? allSubs[allSubs.length - 1] ?? null;
  const st = stats.data?.[0];

  return (
    <div className="space-y-6">
      <Link to="/teacher/students" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.students.title}
      </Link>

      <Card className="p-5 sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <Avatar name={s.full_name} className="size-16 text-lg" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold sm:text-2xl">{s.full_name}</h1>
              <Badge>{s.english_level}</Badge>
              {!s.is_active && <Badge variant="neutral">{t.students.inactive}</Badge>}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-muted-foreground">
              <a href={`mailto:${s.email}`} className="inline-flex min-w-0 items-center gap-1.5 hover:text-accent">
                <Mail className="size-4 shrink-0" />
                <span className="truncate">{s.email}</span>
              </a>
              {s.phone && (
                <a href={`tel:${s.phone}`} className="inline-flex items-center gap-1.5 hover:text-accent">
                  <Phone className="size-4" />
                  {s.phone}
                </a>
              )}
              <span className="inline-flex items-center gap-1.5">
                <CalendarDays className="size-4" />
                {t.students.registered}: {fmtDate(s.created_at, locale)}
              </span>
            </div>
            {s.groups.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {s.groups.map((g) => (
                  <Badge key={g.id} variant="neutral">{g.name}</Badge>
                ))}
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="icon" asChild>
              <Link to={`/teacher/messages/${s.id}`} aria-label={t.messages.write} title={t.messages.write}>
                <MessageSquare />
              </Link>
            </Button>
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil />
              {t.common.edit}
            </Button>
            <Button variant="outline" size="icon" onClick={() => invite.mutate()} loading={invite.isPending}
              aria-label={t.students.resendInvite} title={t.students.resendInvite} disabled={!s.is_active}>
              {!invite.isPending && <Send />}
            </Button>
            <Button variant="ghost" size="icon" onClick={() => toggleActive.mutate()} loading={toggleActive.isPending}
              aria-label={s.is_active ? t.students.deactivate : t.students.activate} title={s.is_active ? t.students.deactivate : t.students.activate}>
              {!toggleActive.isPending && <Power className={s.is_active ? "text-muted-foreground" : "text-success"} />}
            </Button>
          </div>
        </div>
        {s.notes && <p className="mt-4 whitespace-pre-wrap rounded-xl bg-secondary p-3 text-sm text-primary/80">{s.notes}</p>}
      </Card>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">{t.students.overview}</TabsTrigger>
          <TabsTrigger value="progress">{t.analytics.progressTab}</TabsTrigger>
          <TabsTrigger value="courses">{t.myCourses.progressTitle}</TabsTrigger>
          <TabsTrigger value="homework">{t.nav.homework}</TabsTrigger>
          <TabsTrigger value="tests">{t.nav.tests}</TabsTrigger>
          <TabsTrigger value="attendance">{t.nav.attendance}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_1fr]">
            <SubscriptionWidget
              sub={current}
              title={t.students.currentSubscription}
              actions={
                current ? (
                  <SubscriptionActions sub={current} />
                ) : canManageSubs ? (
                  <Button onClick={() => setNewSub(true)}>
                    <Plus />
                    {t.subscriptions.create}
                  </Button>
                ) : undefined
              }
            />
            <div className="grid content-start gap-4">
              <div className="grid grid-cols-2 gap-3">
                <StatCard icon={Percent} tone="primary" label={t.attendance.rate} value={st ? `${st.attendance_rate}%` : "—"} />
                <StatCard icon={CalendarCheck} tone="success" label={t.attendance.visited} value={st ? st.present + st.late : "—"} />
                <StatCard icon={CalendarX2} tone="danger" label={t.attendance.missed} value={st ? st.absent + st.excused : "—"} />
                <StatCard icon={CalendarDays} label={t.attendance.upcoming} value={st?.upcoming ?? "—"} />
              </div>
              <Card>
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle>{t.subscription.history}</CardTitle>
                  {canManageSubs && (
                    <Button size="sm" variant="soft" onClick={() => setNewSub(true)}>
                      <Plus />
                      {t.common.create}
                    </Button>
                  )}
                </CardHeader>
                <CardContent>
                  {subs.data?.length ? (
                    <ul className="divide-y">
                      {subs.data.map((x) => (
                        <li key={x.id} className="flex items-center justify-between gap-2 py-2.5">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-primary">{x.title ?? t.subscription.title}</p>
                            <p className="tabular text-xs text-muted-foreground">
                              {fmtDate(x.start_date, locale)} — {fmtDate(x.end_date, locale)} · {x.used_lessons}/{x.total_lessons}
                            </p>
                          </div>
                          <div className="flex items-center gap-1">
                            <SubscriptionBadge status={x.status} />
                            <SubscriptionActions sub={x} compact />
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">{t.subscriptions.empty}</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="progress">
          <StudentProgressTab studentId={id} />
        </TabsContent>

        <TabsContent value="courses">
          <StudentCoursesTab studentId={id} />
        </TabsContent>

        <TabsContent value="homework">
          <Card className="overflow-hidden">
            {hw.data?.length ? (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>{t.homework.name}</TableHead>
                    <TableHead>{t.homework.dueAt}</TableHead>
                    <TableHead>{t.common.status}</TableHead>
                    <TableHead className="text-right">{t.homework.grade}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {hw.data.map((h) => (
                    <TableRow key={h.submission_id}>
                      <TableCell className="max-w-[260px] truncate font-medium text-primary">
                        <Link to={`/teacher/homework/${h.homework_id}?submission=${h.submission_id}`} className="hover:text-accent">{h.title}</Link>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">{h.due_at ? fmtDateTime(h.due_at, locale) : "—"}</TableCell>
                      <TableCell><SubmissionBadge status={h.status} /></TableCell>
                      <TableCell className="tabular text-right font-medium">{h.grade !== null ? `${h.grade}/${h.max_grade}` : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState title={t.homework.empty} />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="tests">
          <Card className="overflow-hidden">
            {tests.data?.length ? (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>{t.tests.name}</TableHead>
                    <TableHead>{t.common.date}</TableHead>
                    <TableHead>{t.common.status}</TableHead>
                    <TableHead className="text-right">{t.tests.score}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tests.data.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="max-w-[260px] truncate font-medium text-primary">
                        <Link to={`/teacher/tests/${a.test_id}/attempts/${a.id}`} className="hover:text-accent">{a.test_title}</Link>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDate(a.submitted_at ?? a.started_at, locale)}</TableCell>
                      <TableCell><AttemptBadge status={a.status} /></TableCell>
                      <TableCell className="text-right">
                        {a.percent !== null ? <Badge variant={scoreVariant(a.percent)} className="tabular">{a.percent}%</Badge> : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState title={t.tests.attemptsEmpty} />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="attendance">
          <Card className="overflow-hidden">
            {att.data?.length ? (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>{t.common.date}</TableHead>
                    <TableHead>{t.lessons.name}</TableHead>
                    <TableHead>{t.common.status}</TableHead>
                    <TableHead>{t.common.comment}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {att.data.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="whitespace-nowrap">{fmtDateTime(r.starts_at, locale)}</TableCell>
                      <TableCell className="max-w-[220px] truncate">{r.lesson_title}</TableCell>
                      <TableCell><AttendanceBadge status={r.status} /></TableCell>
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
      </Tabs>

      <StudentFormDialog open={editing} onOpenChange={setEditing} student={s} />
      <SubscriptionFormDialog open={newSub} onOpenChange={setNewSub} studentId={id} />
    </div>
  );
}

function StudentProgressTab({ studentId }: { studentId: number }) {
  const q = useQuery({ queryKey: ["analytics", "student", studentId], queryFn: () => analyticsApi.student(studentId) });
  if (q.isLoading) return <StatsSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  return <ProgressView data={q.data} />;
}

function StudentCoursesTab({ studentId }: { studentId: number }) {
  const q = useQuery({ queryKey: ["course-assignments", "student", studentId], queryFn: () => courseAssignmentsApi.studentProgress(studentId) });
  if (q.isLoading) return <StatsSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  return <CourseProgressView data={q.data} />;
}
