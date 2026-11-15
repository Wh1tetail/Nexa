import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Clock, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/common";
import { RecipientPicker } from "@/components/common/RecipientPicker";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Checkbox, RadioGroup, RadioGroupItem } from "@/components/ui/checkbox";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { groupsApi, lessonsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { AttendanceStatus, Lesson } from "@/types/api";
import { fmtDateTime, localInputToIso, toDateTimeInput, wallClockInput } from "@/utils/format";

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["lessons"] });
    qc.invalidateQueries({ queryKey: ["attendance"] });
    qc.invalidateQueries({ queryKey: ["subscriptions"] });
    qc.invalidateQueries({ queryKey: ["students"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
}

export function LessonFormDialog({ open, onOpenChange, lesson }: { open: boolean; onOpenChange: (o: boolean) => void; lesson?: Lesson }) {
  const { t } = useI18n();
  // teachers change only the topic and add students; the rest belongs to the administrator
  const limited = useAuth().user?.role === "teacher" && !!lesson;
  const invalidate = useInvalidate();
  const groups = useQuery({ queryKey: ["groups"], queryFn: groupsApi.list, enabled: open });
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [duration, setDuration] = useState(60);
  const [url, setUrl] = useState("");
  const [groupId, setGroupId] = useState<number | "">("");
  const [studentIds, setStudentIds] = useState<number[]>([]);
  const [repeat, setRepeat] = useState(false);
  const [scope, setScope] = useState<"one" | "following">("one");
  const [repeatWeeks, setRepeatWeeks] = useState(7);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    setTitle(lesson?.title ?? "");
    setTopic(lesson?.topic ?? "");
    // default: tomorrow 18:00 on the user's (profile) clock
    setStartsAt(lesson ? toDateTimeInput(new Date(lesson.starts_at)) : wallClockInput(1, 18));
    setDuration(lesson?.duration_minutes ?? 60);
    setUrl(lesson?.meeting_url ?? "");
    setGroupId(lesson?.group_id ?? "");
    setStudentIds(lesson?.attendance.map((a) => a.student_id) ?? []);
    setRepeat(false);
    setRepeatWeeks(7);
    setScope("one");
    setErrors({});
  }, [open, lesson]);

  const save = useMutation({
    mutationFn: () => {
      const body = {
        title: title.trim(),
        topic: topic.trim() || null,
        starts_at: localInputToIso(startsAt)!,
        duration_minutes: duration,
        meeting_url: url.trim() || null,
        student_ids: studentIds,
      };
      if (!lesson) {
        return lessonsApi.create({ ...body, group_id: groupId || null, repeat_weeks: repeat ? repeatWeeks : 0 });
      }
      // send only what changed, so "this and following" doesn't overwrite untouched fields
      const before = {
        title: lesson.title,
        topic: lesson.topic,
        starts_at: new Date(lesson.starts_at).toISOString(),
        duration_minutes: lesson.duration_minutes,
        meeting_url: lesson.meeting_url,
      };
      const changed: Partial<typeof body> = {};
      (Object.keys(before) as (keyof typeof before)[]).forEach((k) => {
        if (body[k] !== before[k]) Object.assign(changed, { [k]: body[k] });
      });
      const prevIds = lesson.attendance.map((a) => a.student_id).sort().join(",");
      if ([...studentIds].sort().join(",") !== prevIds) changed.student_ids = studentIds;
      return lessonsApi.update(lesson.id, changed, scope);
    },
    onSuccess: () => {
      invalidate();
      toast.success(lesson ? t.common.saved : t.lessons.created);
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  function submit() {
    const e: Record<string, string> = {};
    if (!title.trim()) e.title = t.common.required;
    if (!startsAt) e.startsAt = t.common.required;
    if (url && !/^https?:\/\//i.test(url.trim())) e.url = "https://…";
    if (!lesson && !groupId && !studentIds.length) e.students = t.lessons.selectStudents;
    if (repeat && (repeatWeeks < 1 || repeatWeeks > 52)) e.repeat = "1–52";
    setErrors(e);
    if (!Object.keys(e).length) save.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{lesson ? t.lessons.editTitle : t.lessons.createTitle}</DialogTitle>
        </DialogHeader>
        <DialogBody className="grid gap-4 sm:grid-cols-2">
          {limited && (
            <p className="rounded-xl bg-secondary px-3 py-2.5 text-sm text-muted-foreground sm:col-span-2">{t.lessons.teacherLimited}</p>
          )}
          <Field label={t.lessons.name} error={errors.title}>
            <Input
              disabled={limited}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              aria-invalid={!!errors.title}
              maxLength={200}
              placeholder="Intermediate Evening"
            />
          </Field>
          <Field label={t.lessons.topic} optional>
            <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Present Perfect" />
          </Field>
          <Field label={t.lessons.startsAt} error={errors.startsAt}>
            <Input type="datetime-local" disabled={limited} value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
          </Field>
          <Field label={t.lessons.duration}>
            <Input type="number" min={15} max={600} step={15} disabled={limited} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
          </Field>
          <Field label={t.lessons.meetingUrl} optional error={errors.url} className="sm:col-span-2">
            <Input type="url" disabled={limited} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://meet.google.com/…" />
          </Field>
          {!lesson && (
            <div className="grid gap-3 rounded-xl border bg-secondary/40 p-3 sm:col-span-2">
              <label className="flex cursor-pointer items-center gap-3">
                <Checkbox checked={repeat} onCheckedChange={(c) => setRepeat(c === true)} />
                <span className="text-sm font-medium text-primary">{t.lessons.repeat}</span>
              </label>
              {repeat && (
                <Field label={t.lessons.repeatWeeks} error={errors.repeat} hint={t.lessons.repeatHint(repeatWeeks + 1)}>
                  <Input type="number" min={1} max={52} value={repeatWeeks} onChange={(e) => setRepeatWeeks(Number(e.target.value))} className="sm:w-32" />
                </Field>
              )}
            </div>
          )}
          {!lesson && (
            <Field label={t.lessons.chooseGroup} className="sm:col-span-2">
              <NativeSelect
                value={groupId}
                onChange={(e) => {
                  const id = e.target.value ? Number(e.target.value) : "";
                  setGroupId(id);
                  const g = groups.data?.find((x) => x.id === id);
                  if (g && !title) setTitle(g.name);
                }}
              >
                <option value="">{t.lessons.noGroup}</option>
                {groups.data?.map((g) => (
                  <option key={g.id} value={g.id}>{g.name} · {g.students.length}</option>
                ))}
              </NativeSelect>
            </Field>
          )}
          <Field label={t.lessons.participants} error={errors.students} className="sm:col-span-2">
            <RecipientPicker
              showGroups={false}
              studentIds={studentIds}
              groupIds={[]}
              disabledStudentIds={
                limited
                  ? lesson!.attendance.map((a) => a.student_id) // can add, not remove
                  : groupId
                    ? groups.data?.find((g) => g.id === groupId)?.students.map((s) => s.id)
                    : []
              }
              onChange={(v) => setStudentIds(v.studentIds)}
            />
          </Field>
          {lesson?.series_id && lesson.series_position && lesson.series_total && (
            <Field label={t.lessons.applyTo} hint={t.lessons.scopeHint} className="sm:col-span-2">
              <RadioGroup value={scope} onValueChange={(v) => setScope(v as "one" | "following")} className="sm:grid-cols-2">
                {(["one", "following"] as const).map((v) => (
                  <label
                    key={v}
                    className={cn(
                      "flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-sm transition-colors",
                      scope === v ? "border-accent bg-accent-soft/60" : "hover:bg-secondary/60",
                    )}
                  >
                    <RadioGroupItem value={v} />
                    {v === "one" ? t.lessons.scopeOne : t.lessons.scopeFollowing(lesson.series_total! - lesson.series_position! + 1)}
                  </label>
                ))}
              </RadioGroup>
            </Field>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button loading={save.isPending} onClick={submit}>{lesson ? t.common.save : t.common.create}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const STATUS_BUTTONS: { status: AttendanceStatus; icon: typeof Check; active: string }[] = [
  { status: "present", icon: Check, active: "border-success bg-success text-white" },
  { status: "late", icon: Clock, active: "border-warning bg-warning text-white" },
  { status: "absent", icon: X, active: "border-danger bg-danger text-white" },
  { status: "excused", icon: ShieldCheck, active: "border-primary bg-primary text-primary-foreground" },
];

export function AttendanceDialog({ open, onOpenChange, lesson }: { open: boolean; onOpenChange: (o: boolean) => void; lesson: Lesson | null }) {
  const { t, locale } = useI18n();
  const invalidate = useInvalidate();
  const [marks, setMarks] = useState<Record<number, { status: AttendanceStatus | null; comment: string }>>({});

  useEffect(() => {
    if (open && lesson) {
      setMarks(Object.fromEntries(lesson.attendance.map((a) => [a.student_id, { status: a.status, comment: a.comment ?? "" }])));
    }
  }, [open, lesson]);

  const save = useMutation({
    mutationFn: () =>
      lessonsApi.mark(
        lesson!.id,
        Object.entries(marks).map(([sid, m]) => ({ student_id: Number(sid), status: m.status, comment: m.comment.trim() || null })),
      ),
    onSuccess: () => {
      invalidate();
      toast.success(t.lessons.attendanceSaved);
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!lesson) return null;
  const set = (sid: number, patch: Partial<{ status: AttendanceStatus | null; comment: string }>) =>
    setMarks((m) => ({ ...m, [sid]: { ...m[sid], ...patch } }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{t.lessons.markAttendance}</DialogTitle>
          <DialogDescription>
            {lesson.title} · {fmtDateTime(lesson.starts_at, locale)}
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="grid gap-3">
          <div className="flex justify-end">
            <Button
              variant="soft"
              size="sm"
              onClick={() => setMarks((m) => Object.fromEntries(Object.entries(m).map(([k, v]) => [k, { ...v, status: "present" as const }])))}
            >
              <Check />
              {t.lessons.markAll}: {t.status.attendance.present}
            </Button>
          </div>
          {lesson.attendance.map((a) => {
            const m = marks[a.student_id] ?? { status: null, comment: "" };
            return (
              <div key={a.student_id} className="rounded-xl border p-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <Avatar name={a.student_name} className="size-8 text-[10px]" />
                    <span className="truncate text-sm font-medium text-primary">{a.student_name}</span>
                  </div>
                  <div className="grid grid-cols-4 gap-1.5" role="radiogroup" aria-label={a.student_name}>
                    {STATUS_BUTTONS.map(({ status, icon: Icon, active }) => (
                      <button
                        key={status}
                        type="button"
                        role="radio"
                        aria-checked={m.status === status}
                        title={t.status.attendance[status]}
                        onClick={() => set(a.student_id, { status: m.status === status ? null : status })}
                        className={cn(
                          "flex h-10 items-center justify-center gap-1 rounded-lg border px-2 text-xs font-medium transition-colors sm:w-[72px]",
                          m.status === status ? active : "text-muted-foreground hover:bg-secondary",
                        )}
                      >
                        <Icon className="size-3.5" />
                        <span className="truncate">{t.status.attendanceShort[status]}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <Input
                  value={m.comment}
                  onChange={(e) => set(a.student_id, { comment: e.target.value })}
                  placeholder={t.lessons.commentPlaceholder}
                  className="mt-2 h-9"
                  maxLength={1000}
                />
              </div>
            );
          })}
          <p className="text-xs text-muted-foreground">{t.subscriptions.autoCharge}</p>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button loading={save.isPending} onClick={() => save.mutate()}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ExtendSeriesDialog({ lesson, onClose }: { lesson: Lesson | null; onClose: () => void }) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const [weeks, setWeeks] = useState(4);
  useEffect(() => {
    if (lesson) setWeeks(4);
  }, [lesson]);
  const save = useMutation({
    mutationFn: () => lessonsApi.extendSeries(lesson!.id, weeks),
    onSuccess: () => {
      invalidate();
      toast.success(t.lessons.seriesExtended(weeks));
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const valid = Number.isInteger(weeks) && weeks >= 1 && weeks <= 52;
  return (
    <Dialog open={!!lesson} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{lesson?.series_id ? t.lessons.extendSeriesTitle : t.lessons.makeRecurring}</DialogTitle>
          <DialogDescription>{t.lessons.extendSeriesHint}</DialogDescription>
        </DialogHeader>
        <DialogBody>
          <Field label={t.lessons.addWeeks} error={valid ? undefined : "1–52"}>
            <Input type="number" min={1} max={52} value={weeks} onChange={(e) => setWeeks(Number(e.target.value))} />
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button loading={save.isPending} disabled={!valid} onClick={() => save.mutate()}>{t.lessons.extendSeries}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
