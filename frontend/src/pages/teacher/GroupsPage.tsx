import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { MoreHorizontal, Pencil, Plus, Trash2, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { CardListSkeleton, EmptyState, ErrorState, Field, PageHeader } from "@/components/common";
import { RecipientPicker } from "@/components/common/RecipientPicker";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/checkbox";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { groupsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { cn } from "@/lib/utils";
import { localInputToIso } from "@/utils/format";
import { ENGLISH_LEVELS, type EnglishLevel, type Group } from "@/types/api";

function GroupDialog({ open, onOpenChange, group }: { open: boolean; onOpenChange: (o: boolean) => void; group?: Group }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [level, setLevel] = useState<EnglishLevel | "">("");
  const [description, setDescription] = useState("");
  const [studentIds, setStudentIds] = useState<number[]>([]);
  const [error, setError] = useState<string>();
  // what new members get from the group's upcoming lessons
  const [lessonsMode, setLessonsMode] = useState<"all" | "from" | "none">("all");
  const [lessonsFrom, setLessonsFrom] = useState("");
  const before = new Set(group?.students.map((s) => s.id) ?? []);
  const joining = studentIds.filter((id) => !before.has(id));
  const leaving = [...before].filter((id) => !studentIds.includes(id));

  useEffect(() => {
    if (open) {
      setName(group?.name ?? "");
      setLevel(group?.level ?? "");
      setDescription(group?.description ?? "");
      setStudentIds(group?.students.map((s) => s.id) ?? []);
      setError(undefined);
      setLessonsMode("all");
      setLessonsFrom("");
    }
  }, [open, group]);

  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), level: level || null, description: description.trim() || null, student_ids: studentIds };
      if (!group) return groupsApi.create(body);
      return groupsApi.update(group.id, {
        ...body,
        assign_lessons: lessonsMode !== "none",
        lessons_from: lessonsMode === "from" && lessonsFrom ? localInputToIso(`${lessonsFrom}T00:00`) : null,
      });
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["groups"] });
      qc.invalidateQueries({ queryKey: ["students"] });
      qc.invalidateQueries({ queryKey: ["lessons"] });
      const detail = t.participants.groupSaved(res.lessons_assigned ?? 0, res.lessons_released ?? 0);
      toast.success(group ? (detail ? `${t.common.saved}: ${detail}` : t.common.saved) : t.groups.created);
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{group ? t.groups.editTitle : t.groups.createTitle}</DialogTitle>
        </DialogHeader>
        <DialogBody className="grid gap-4 sm:grid-cols-2">
          <Field label={t.groups.name} error={error}>
            <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus aria-invalid={!!error} maxLength={120} />
          </Field>
          <Field label={t.groups.level}>
            <NativeSelect value={level} onChange={(e) => setLevel(e.target.value as EnglishLevel | "")}>
              <option value="">{t.groups.noLevel}</option>
              {ENGLISH_LEVELS.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field label={t.groups.description} optional className="sm:col-span-2">
            <Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label={`${t.groups.members} · ${studentIds.length}`} className="sm:col-span-2">
            <RecipientPicker showGroups={false} studentIds={studentIds} groupIds={[]} onChange={(v) => setStudentIds(v.studentIds)} />
          </Field>
          {group && joining.length > 0 && group.upcoming_lessons > 0 && (
            <Field label={t.participants.lessonsTitle} className="sm:col-span-2">
              <RadioGroup value={lessonsMode} onValueChange={(v) => setLessonsMode(v as typeof lessonsMode)} className="gap-2">
                {(["all", "from", "none"] as const).map((m) => (
                  <label
                    key={m}
                    className={cn(
                      "flex min-h-11 cursor-pointer flex-wrap items-center gap-3 rounded-xl border px-3 py-2 text-sm transition-colors",
                      lessonsMode === m ? "border-accent bg-accent-soft/60" : "hover:bg-secondary/60",
                    )}
                  >
                    <RadioGroupItem value={m} />
                    {m === "all" ? t.participants.lessonsAll(group.upcoming_lessons) : m === "from" ? t.participants.lessonsFrom : t.participants.lessonsNone}
                    {m === "from" && lessonsMode === "from" && (
                      <Input type="date" value={lessonsFrom} onChange={(e) => setLessonsFrom(e.target.value)} className="h-9 w-auto" />
                    )}
                  </label>
                ))}
              </RadioGroup>
            </Field>
          )}
          {group && leaving.length > 0 && (
            <p className="rounded-xl bg-warning-soft px-3 py-2.5 text-sm text-warning-strong sm:col-span-2">
              {t.participants.leavingNote(leaving.length)}
            </p>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button
            loading={save.isPending}
            onClick={() => {
              if (!name.trim()) return setError(t.common.required);
              if (lessonsMode === "from" && joining.length && !lessonsFrom) return toast.error(t.participants.lessonsFrom);
              save.mutate();
            }}
          >
            {group ? t.common.save : t.common.create}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function GroupsPage() {
  const { t } = useI18n();
  const isAdmin = useAuth().user?.role === "admin"; // only admins create and delete groups
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["groups"], queryFn: groupsApi.list });
  const [dialog, setDialog] = useState<{ open: boolean; group?: Group }>({ open: false });
  const [toDelete, setToDelete] = useState<Group | null>(null);
  const remove = useMutation({
    mutationFn: (id: number) => groupsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["groups"] });
      setToDelete(null);
      toast.success(t.common.deleted);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div>
      <PageHeader
        title={t.groups.title}
        subtitle={t.groups.subtitle}
        actions={isAdmin && <Button onClick={() => setDialog({ open: true })}><Plus />{t.groups.create}</Button>}
      />
      {q.isLoading ? (
        <CardListSkeleton />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data?.length ? (
        <Card>
          <EmptyState icon={UsersRound} title={t.groups.empty} text={t.groups.emptyHint}
            action={isAdmin ? <Button onClick={() => setDialog({ open: true })}><Plus />{t.groups.create}</Button> : undefined} />
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {q.data.map((g) => (
            <Card key={g.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-2">
                <span className="flex size-10 items-center justify-center rounded-xl bg-accent-soft text-accent">
                  <UsersRound className="size-5" />
                </span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon-sm" aria-label={t.common.actions}><MoreHorizontal /></Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => setDialog({ open: true, group: g })}><Pencil />{t.common.edit}</DropdownMenuItem>
                    {isAdmin && <DropdownMenuItem destructive onSelect={() => setToDelete(g)}><Trash2 />{t.common.delete}</DropdownMenuItem>}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <h3 className="truncate font-semibold">{g.name}</h3>
                {g.level && <Badge variant="neutral">{g.level}</Badge>}
              </div>
              {g.description && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{g.description}</p>}
              <div className="mt-5 flex-1" />
              <div className="flex items-center justify-between">
                <div className="flex -space-x-2">
                  {g.students.slice(0, 5).map((s) => (
                    <Avatar key={s.id} name={s.full_name} className="size-8 text-[10px] ring-2 ring-background" />
                  ))}
                </div>
                <span className="text-sm text-muted-foreground">{t.common.studentsCount(g.students.length)}</span>
              </div>
            </Card>
          ))}
        </div>
      )}
      <GroupDialog open={dialog.open} group={dialog.group} onOpenChange={(open) => setDialog((d) => ({ ...d, open }))} />
      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title={t.groups.deleteTitle}
        description={t.groups.deleteText}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => toDelete && remove.mutate(toDelete.id)}
      />
    </div>
  );
}
