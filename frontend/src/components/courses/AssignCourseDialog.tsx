import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/common";
import { RecipientPicker } from "@/components/common/RecipientPicker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { courseAssignmentsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { localInputToIso, toDateTimeInput } from "@/utils/format";

export interface AssignTarget {
  courseId: number;
  levelId?: number;
  moduleId?: number;
  /** what is being assigned, for the title */
  label: string;
}

/** Teacher: give a level or a module to students and/or groups. */
export function AssignCourseDialog({ target, onClose }: { target: AssignTarget | null; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [recipients, setRecipients] = useState({ studentIds: [] as number[], groupIds: [] as number[] });
  const [starts, setStarts] = useState("");
  const [due, setDue] = useState("");
  useEffect(() => {
    setRecipients({ studentIds: [], groupIds: [] });
    setStarts(toDateTimeInput(new Date()));
    setDue("");
  }, [target]);

  const assign = useMutation({
    mutationFn: () =>
      courseAssignmentsApi.assign({
        course_id: target!.courseId,
        level_id: target!.levelId ?? null,
        module_id: target!.moduleId ?? null,
        student_ids: recipients.studentIds,
        group_ids: recipients.groupIds,
        starts_at: localInputToIso(starts),
        due_at: localInputToIso(due),
      }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["course-assignments"] });
      if (r.assigned === 0 && !r.assignment_ids.length) toast.info(t.courseAssign.nobodyNew);
      else toast.success([t.courseAssign.done(r.assigned), r.skipped ? t.courseAssign.skipped(r.skipped) : ""].filter(Boolean).join(" · "));
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const empty = !recipients.studentIds.length && !recipients.groupIds.length;
  return (
    <Dialog open={!!target} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="lg">
        <DialogHeader><DialogTitle className="break-words">{target ? t.courseAssign.assignTitle(target.label) : ""}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4">
          <RecipientPicker studentIds={recipients.studentIds} groupIds={recipients.groupIds} onChange={setRecipients} />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t.courseAssign.startsAt} hint={t.courseAssign.startsHint}>
              <Input type="datetime-local" value={starts} onChange={(e) => setStarts(e.target.value)} />
            </Field>
            <Field label={t.courseAssign.dueAt} optional>
              <Input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
            </Field>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={empty} loading={assign.isPending} onClick={() => assign.mutate()}>{t.courseAssign.assign}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
