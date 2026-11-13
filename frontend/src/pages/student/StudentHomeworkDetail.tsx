import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CalendarClock, Lock, MessageSquareText, Send, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState, PageSkeleton } from "@/components/common";
import { FileDropzone, FileList } from "@/components/common/Files";
import { SubmissionBadge } from "@/components/common/StatusBadges";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { meApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Attachment } from "@/types/api";
import { fmtDateTime } from "@/utils/format";

const EDITABLE = ["new", "in_progress", "needs_revision"];

export default function StudentHomeworkDetail() {
  const { submissionId } = useParams();
  const id = Number(submissionId);
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const key = ["me", "homework", id];
  const q = useQuery({ queryKey: key, queryFn: () => meApi.homeworkItem(id) });
  const [comment, setComment] = useState("");
  const [toDelete, setToDelete] = useState<Attachment | null>(null);

  useEffect(() => {
    if (q.data) setComment(q.data.student_comment ?? "");
  }, [q.data?.submission_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["me", "homework"] });
    qc.invalidateQueries({ queryKey: ["dashboard", "student"] });
  };

  const submit = useMutation({
    mutationFn: () => meApi.submitHomework(id, comment.trim() || null),
    onSuccess: (data) => {
      qc.setQueryData(key, data);
      refresh();
      toast.success(t.homework.submitted);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const removeFile = useMutation({
    mutationFn: (f: Attachment) => meApi.removeFile(id, f.id),
    onSuccess: () => {
      setToDelete(null);
      q.refetch();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const h = q.data;
  const editable = EDITABLE.includes(h.status);

  return (
    <div className="space-y-6">
      <Link to="/student/homework" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.homework.title}
      </Link>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="page-title break-words">{h.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <UserRound className="size-4" />
              {h.teacher_name}
            </span>
            <span className={`inline-flex items-center gap-1.5 ${h.is_overdue ? "font-medium text-danger" : ""}`}>
              <CalendarClock className="size-4" />
              {h.due_at ? `${t.common.due}: ${fmtDateTime(h.due_at, locale)}` : t.common.noDeadline}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {h.is_overdue && <Badge variant="danger">{t.common.overdue}</Badge>}
          <SubmissionBadge status={h.status} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t.homework.description}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-primary/90">{h.description || "—"}</p>
              {h.attachments.length > 0 && (
                <div>
                  <p className="mb-2 text-sm font-medium text-primary">{t.homework.attachments}</p>
                  <FileList files={h.attachments} />
                </div>
              )}
            </CardContent>
          </Card>

          {(h.teacher_comment || h.grade !== null) && (
            <Card className={h.status === "needs_revision" ? "border-danger/30" : "border-success/30"}>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="flex items-center gap-2">
                  <MessageSquareText className="size-4 text-accent" />
                  {t.homework.teacherFeedback}
                </CardTitle>
                {h.grade !== null && (
                  <span className="tabular rounded-xl bg-success-soft px-3 py-1 text-lg font-semibold text-[hsl(142_72%_29%)]">
                    {h.grade}
                    <span className="text-sm font-normal opacity-70">/{h.max_grade}</span>
                  </span>
                )}
              </CardHeader>
              {h.teacher_comment && (
                <CardContent>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{h.teacher_comment}</p>
                </CardContent>
              )}
            </Card>
          )}
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>{t.homework.yourWork}</CardTitle>
            {h.submitted_at && (
              <p className="text-xs text-muted-foreground">
                {t.homework.sentAt}: {fmtDateTime(h.submitted_at, locale)}
              </p>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            <FileList files={h.files} onRemove={editable ? setToDelete : undefined} />
            {editable ? (
              <>
                <FileDropzone
                  compact
                  onUpload={async (files, onProgress) => {
                    await meApi.uploadFiles(id, files, onProgress);
                    await q.refetch();
                    refresh();
                  }}
                />
                <div className="grid gap-1.5">
                  <Label htmlFor="comment">{t.homework.yourAnswer}</Label>
                  <Textarea
                    id="comment"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder={t.homework.answerPlaceholder}
                    maxLength={5000}
                  />
                </div>
                <Button
                  className="w-full"
                  size="lg"
                  loading={submit.isPending}
                  onClick={() => {
                    if (!h.files.length && !comment.trim()) {
                      toast.error(t.homework.needFileOrText);
                      return;
                    }
                    submit.mutate();
                  }}
                >
                  <Send />
                  {t.homework.submit}
                </Button>
              </>
            ) : (
              <>
                {h.student_comment && (
                  <p className="whitespace-pre-wrap rounded-xl bg-secondary p-3 text-sm">{h.student_comment}</p>
                )}
                <p className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Lock className="mt-0.5 size-3.5 shrink-0" />
                  {t.homework.lockedHint}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title={`${t.common.delete} «${toDelete?.original_name}»?`}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={removeFile.isPending}
        onConfirm={() => toDelete && removeFile.mutate(toDelete)}
      />
    </div>
  );
}
