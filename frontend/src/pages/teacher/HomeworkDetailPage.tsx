import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CalendarClock, MoreHorizontal, Pencil, Trash2, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState, Field, PageSkeleton } from "@/components/common";
import { FileDropzone, FileList } from "@/components/common/Files";
import { ParticipantList } from "@/components/common/ParticipantList";
import { RecipientPicker } from "@/components/common/RecipientPicker";
import { SubmissionBadge } from "@/components/common/StatusBadges";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { homeworkApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Attachment, HomeworkDetail, Submission, SubmissionStatus } from "@/types/api";
import { fmtDateTime, localInputToIso, toDateTimeInput } from "@/utils/format";

function ReviewDialog({ sub, hw, onClose }: { sub: Submission | null; hw: HomeworkDetail; onClose: () => void }) {
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const [grade, setGrade] = useState<string>("");
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<SubmissionStatus>("reviewed");

  useEffect(() => {
    if (sub) {
      setGrade(sub.grade?.toString() ?? "");
      setComment(sub.teacher_comment ?? "");
      setStatus(sub.status === "needs_revision" ? "needs_revision" : "reviewed");
    }
  }, [sub]);

  const save = useMutation({
    mutationFn: (s: SubmissionStatus) =>
      homeworkApi.review(sub!.id, { status: s, grade: grade === "" ? null : Number(grade), teacher_comment: comment.trim() || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["homework"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(t.homework.reviewed);
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Dialog open={!!sub} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="lg">
        {sub && (
          <>
            <DialogHeader>
              <DialogTitle>{t.homework.reviewTitle}</DialogTitle>
              <DialogDescription>
                {sub.student_name} · {hw.title}
              </DialogDescription>
            </DialogHeader>
            <DialogBody className="grid gap-5">
              <div className="grid gap-2">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-primary">{t.homework.yourWork}</p>
                  <SubmissionBadge status={sub.status} />
                </div>
                {sub.submitted_at && <p className="text-xs text-muted-foreground">{t.homework.sentAt}: {fmtDateTime(sub.submitted_at, locale)}</p>}
                <FileList files={sub.files} emptyText={t.homework.noFiles} />
                {sub.student_comment && <p className="whitespace-pre-wrap rounded-xl bg-secondary p-3 text-sm">{sub.student_comment}</p>}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={`${t.homework.grade} (0–${hw.max_grade})`}>
                  <Input type="number" min={0} max={hw.max_grade} value={grade} onChange={(e) => setGrade(e.target.value)} />
                </Field>
                <Field label={t.homework.setStatus}>
                  <NativeSelect value={status} onChange={(e) => setStatus(e.target.value as SubmissionStatus)}>
                    {(["reviewed", "needs_revision", "submitted", "in_progress", "new"] as const).map((s) => (
                      <option key={s} value={s}>{t.status.submission[s]}</option>
                    ))}
                  </NativeSelect>
                </Field>
                <Field label={t.common.comment} className="sm:col-span-2">
                  <Textarea rows={4} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={5000} />
                </Field>
              </div>
            </DialogBody>
            <DialogFooter>
              <Button variant="outline" onClick={() => save.mutate("needs_revision")} loading={save.isPending && save.variables === "needs_revision"}>
                {t.homework.sendToRevision}
              </Button>
              <Button onClick={() => save.mutate(status)} loading={save.isPending && save.variables !== "needs_revision"}>
                {t.common.save}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function EditDialog({ hw, open, onOpenChange }: { hw: HomeworkDetail; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [title, setTitle] = useState(hw.title);
  const [description, setDescription] = useState(hw.description ?? "");
  const [due, setDue] = useState(hw.due_at ? toDateTimeInput(new Date(hw.due_at)) : "");
  const [maxGrade, setMaxGrade] = useState(hw.max_grade);

  useEffect(() => {
    if (open) {
      setTitle(hw.title);
      setDescription(hw.description ?? "");
      setDue(hw.due_at ? toDateTimeInput(new Date(hw.due_at)) : "");
      setMaxGrade(hw.max_grade);
    }
  }, [open, hw]);

  const save = useMutation({
    mutationFn: () =>
      homeworkApi.update(hw.id, { title: title.trim(), description: description.trim() || null, due_at: localInputToIso(due), max_grade: maxGrade }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["homework"] });
      toast.success(t.common.saved);
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader><DialogTitle>{t.homework.editTitle}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4 sm:grid-cols-2">
          <Field label={t.homework.name} className="sm:col-span-2">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          </Field>
          <Field label={t.homework.description} className="sm:col-span-2">
            <Textarea rows={6} value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label={t.homework.dueAt}>
            <Input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
          <Field label={t.homework.maxGrade}>
            <Input type="number" min={1} max={100} value={maxGrade} onChange={(e) => setMaxGrade(Number(e.target.value))} />
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button loading={save.isPending} disabled={!title.trim()} onClick={() => save.mutate()}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AddStudentsDialog({ hw, open, onOpenChange }: { hw: HomeworkDetail; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [r, setR] = useState({ studentIds: [] as number[], groupIds: [] as number[] });
  useEffect(() => {
    if (open) setR({ studentIds: [], groupIds: [] });
  }, [open]);
  const save = useMutation({
    mutationFn: () => homeworkApi.update(hw.id, { add_student_ids: r.studentIds, add_group_ids: r.groupIds }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["homework"] });
      toast.success(t.common.saved);
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>{t.homework.addStudents}</DialogTitle></DialogHeader>
        <DialogBody>
          <RecipientPicker studentIds={r.studentIds} groupIds={r.groupIds} onChange={setR} disabledStudentIds={hw.submissions.filter((s) => !s.removed_at).map((s) => s.student_id)} />
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button loading={save.isPending} disabled={!r.studentIds.length && !r.groupIds.length} onClick={() => save.mutate()}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function HomeworkDetailPage() {
  const { homeworkId } = useParams();
  const id = Number(homeworkId);
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = useQuery({ queryKey: ["homework", "detail", id], queryFn: () => homeworkApi.get(id) });
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [fileToDelete, setFileToDelete] = useState<Attachment | null>(null);

  const reviewId = Number(params.get("submission")) || null;
  const reviewing = q.data?.submissions.find((s) => s.id === reviewId) ?? null;

  const remove = useMutation({
    mutationFn: () => homeworkApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["homework"] });
      toast.success(t.common.deleted);
      navigate("/teacher/homework", { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const unassign = useMutation({
    mutationFn: (ids: number[]) => homeworkApi.unassign(id, ids),
    onSuccess: (_, ids) => {
      qc.invalidateQueries({ queryKey: ["homework"] });
      toast.success(t.participants.removedToast(ids.length));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const restore = useMutation({
    mutationFn: (studentId: number) => homeworkApi.update(id, { add_student_ids: [studentId] }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["homework"] });
      toast.success(t.participants.restoredToast);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const removeFile = useMutation({
    mutationFn: (f: Attachment) => homeworkApi.removeAttachment(id, f.id),
    onSuccess: () => {
      setFileToDelete(null);
      q.refetch();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const hw = q.data;

  return (
    <div className="space-y-6">
      <Link to="/teacher/homework" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.homework.title}
      </Link>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="page-title break-words">{hw.title}</h1>
          <p className="mt-2 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
            <CalendarClock className="size-4" />
            {hw.due_at ? `${t.common.due}: ${fmtDateTime(hw.due_at, locale)}` : t.common.noDeadline} · {t.homework.maxGrade}: {hw.max_grade}
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon" aria-label={t.common.actions}><MoreHorizontal /></Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setEditing(true)}><Pencil />{t.common.edit}</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setAdding(true)}><UserPlus />{t.homework.addStudents}</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => setDeleting(true)}><Trash2 />{t.common.delete}</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.3fr]">
        <Card className="h-fit">
          <CardHeader><CardTitle>{t.homework.description}</CardTitle></CardHeader>
          <CardContent className="space-y-5">
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{hw.description || "—"}</p>
            <div className="space-y-3">
              <p className="text-sm font-medium text-primary">{t.homework.attachments}</p>
              <FileList files={hw.attachments} onRemove={setFileToDelete} />
              <FileDropzone
                compact
                onUpload={async (files, onProgress) => {
                  await homeworkApi.uploadAttachments(id, files, onProgress);
                  await q.refetch();
                }}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>{t.homework.submissions}</CardTitle>
            <span className="text-sm text-muted-foreground">
              {t.homework.progress(
                hw.submissions.filter((s) => !s.removed_at && ["submitted", "reviewed"].includes(s.status)).length,
                hw.submissions.filter((s) => !s.removed_at).length,
              )}
            </span>
          </CardHeader>
          <CardContent className="px-3 sm:px-4">
            <ParticipantList
              rows={hw.submissions.map((s) => ({
                studentId: s.student_id,
                name: s.student_name,
                removedAt: s.removed_at,
                meta: (
                  <>
                    {s.submitted_at ? `${t.homework.sentAt}: ${fmtDateTime(s.submitted_at, locale)}` : t.homework.notSubmittedYet}
                    {s.files.length > 0 && ` · 📎 ${s.files.length}`}
                  </>
                ),
                aside: (
                  <div className="flex shrink-0 items-center gap-2">
                    {s.grade !== null && <span className="tabular text-sm font-semibold text-primary">{s.grade}/{hw.max_grade}</span>}
                    {!s.removed_at && <SubmissionBadge status={s.status} />}
                    <Button size="sm" variant="ghost" onClick={() => setParams({ submission: String(s.id) })}>
                      {t.common.open}
                    </Button>
                  </div>
                ),
              }))}
              confirmTitle={t.participants.removeHwTitle}
              confirmText={t.participants.removeHwText}
              onRemove={(ids) => unassign.mutateAsync(ids)}
              onRestore={(sid) => restore.mutateAsync(sid)}
              busy={unassign.isPending || restore.isPending}
            />
          </CardContent>
        </Card>
      </div>

      <ReviewDialog sub={reviewing} hw={hw} onClose={() => setParams({})} />
      <EditDialog hw={hw} open={editing} onOpenChange={setEditing} />
      <AddStudentsDialog hw={hw} open={adding} onOpenChange={setAdding} />
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t.homework.deleteTitle}
        description={t.homework.deleteText}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
      <ConfirmDialog
        open={!!fileToDelete}
        onOpenChange={(o) => !o && setFileToDelete(null)}
        title={`${t.common.delete} «${fileToDelete?.original_name}»?`}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={removeFile.isPending}
        onConfirm={() => fileToDelete && removeFile.mutate(fileToDelete)}
      />
    </div>
  );
}
