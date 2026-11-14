import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ChevronRight, ClipboardList, Plus, Search } from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { CardListSkeleton, EmptyState, ErrorState, Field, PageHeader } from "@/components/common";
import { RecipientPicker } from "@/components/common/RecipientPicker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { homeworkApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { fmtDateTime, localInputToIso, wallClockInput } from "@/utils/format";

function CreateHomeworkDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");
  const [maxGrade, setMaxGrade] = useState(10);
  const [recipients, setRecipients] = useState({ studentIds: [] as number[], groupIds: [] as number[] });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setTitle("");
      setDescription("");
      setDue(wallClockInput(7, 23, 59)); // in a week, 23:59 on the user's clock
      setMaxGrade(10);
      setRecipients({ studentIds: [], groupIds: [] });
      setErrors({});
    }
  }, [open]);

  const create = useMutation({
    mutationFn: () =>
      homeworkApi.create({
        title: title.trim(),
        description: description.trim() || null,
        due_at: localInputToIso(due),
        max_grade: maxGrade,
        student_ids: recipients.studentIds,
        group_ids: recipients.groupIds,
      }),
    onSuccess: (hw) => {
      qc.invalidateQueries({ queryKey: ["homework"] });
      toast.success(t.homework.created);
      onOpenChange(false);
      navigate(`/teacher/homework/${hw.id}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  function submit() {
    const e: Record<string, string> = {};
    if (!title.trim()) e.title = t.common.required;
    if (!recipients.studentIds.length && !recipients.groupIds.length) e.recipients = t.homework.selectRecipients;
    if (maxGrade < 1 || maxGrade > 100) e.maxGrade = "1–100";
    setErrors(e);
    if (!Object.keys(e).length) create.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{t.homework.createTitle}</DialogTitle>
        </DialogHeader>
        <DialogBody className="grid gap-4 sm:grid-cols-2">
          <Field label={t.homework.name} error={errors.title} className="sm:col-span-2">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus maxLength={200} aria-invalid={!!errors.title} />
          </Field>
          <Field label={t.homework.description} optional className="sm:col-span-2">
            <Textarea rows={5} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={20000} />
          </Field>
          <Field label={t.homework.dueAt} optional>
            <Input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
          <Field label={t.homework.maxGrade} error={errors.maxGrade}>
            <Input type="number" min={1} max={100} value={maxGrade} onChange={(e) => setMaxGrade(Number(e.target.value))} />
          </Field>
          <Field label={t.homework.assignTo} error={errors.recipients} className="sm:col-span-2">
            <RecipientPicker studentIds={recipients.studentIds} groupIds={recipients.groupIds} onChange={setRecipients} />
          </Field>
          <p className="text-xs text-muted-foreground sm:col-span-2">{t.homework.attachFiles}: {t.homework.allowed}</p>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button loading={create.isPending} onClick={submit}>{t.common.create}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function HomeworkPage() {
  const { t, locale } = useI18n();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const deferred = useDeferredValue(search);
  const q = useQuery({ queryKey: ["homework", deferred], queryFn: () => homeworkApi.list(deferred), placeholderData: (p) => p });

  return (
    <div>
      <PageHeader
        title={t.homework.title}
        subtitle={t.homework.teacherSubtitle}
        actions={<Button onClick={() => setCreating(true)}><Plus />{t.homework.create}</Button>}
      />
      <div className="relative mb-4 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t.common.search} className="pl-9" />
      </div>
      {q.isLoading ? (
        <CardListSkeleton />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data?.length ? (
        <Card>
          <EmptyState icon={ClipboardList} title={t.homework.empty} text={t.homework.emptyTeacher}
            action={<Button onClick={() => setCreating(true)}><Plus />{t.homework.create}</Button>} />
        </Card>
      ) : (
        <Card className="divide-y overflow-hidden">
          {q.data.map((h) => {
            const done = h.counts.submitted + h.counts.reviewed;
            const overdue = h.due_at && new Date(h.due_at) < new Date();
            return (
              <Link key={h.id} to={`/teacher/homework/${h.id}`} className="group flex items-center gap-4 p-4 hover:bg-secondary/50 sm:p-5">
                <span className="hidden size-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent sm:flex">
                  <ClipboardList className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-primary">{h.title}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <CalendarClock className="size-3.5" />
                      {h.due_at ? fmtDateTime(h.due_at, locale) : t.common.noDeadline}
                    </span>
                    <span className="inline-flex items-center gap-2">
                      {t.homework.progress(done, h.counts.total)}
                      <Progress value={(done * 100) / Math.max(h.counts.total, 1)} className="h-1 w-16" />
                    </span>
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1.5 sm:flex-row sm:items-center">
                  {h.counts.submitted > 0 && <Badge variant="primary">{t.homework.review}: {h.counts.submitted}</Badge>}
                  {overdue && <Badge variant="neutral">{t.common.overdue}</Badge>}
                </div>
                <ChevronRight className="hidden size-4 text-muted-foreground group-hover:translate-x-0.5 sm:block" />
              </Link>
            );
          })}
        </Card>
      )}
      <CreateHomeworkDialog open={creating} onOpenChange={setCreating} />
    </div>
  );
}
