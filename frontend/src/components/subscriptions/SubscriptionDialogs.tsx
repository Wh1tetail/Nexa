import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarPlus,
  MinusCircle,
  MoreHorizontal,
  Pencil,
  PlusCircle,
  Snowflake,
  Sun,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Field } from "@/components/common";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { studentsApi, subscriptionsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Subscription } from "@/types/api";
import { addDays, toDateInput } from "@/utils/format";

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["subscriptions"] });
    qc.invalidateQueries({ queryKey: ["students"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
}

export function SubscriptionFormDialog({
  open,
  onOpenChange,
  sub,
  studentId,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  sub?: Subscription;
  studentId?: number;
}) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const edit = !!sub;
  const students = useQuery({
    queryKey: ["students", "picker"],
    queryFn: () => studentsApi.list({ active: true }),
    enabled: open && !edit && !studentId,
  });

  const schema = z
    .object({
      student_id: z.coerce.number().min(1, t.common.required),
      title: z.string().max(200).optional(),
      start_date: z.string().min(1, t.common.required),
      end_date: z.string().min(1, t.common.required),
      total_lessons: z.coerce.number().int().min(1).max(1000),
      used_lessons: z.coerce.number().int().min(0),
      notes: z.string().max(5000).optional(),
    })
    .refine((v) => v.end_date >= v.start_date, { message: t.subscriptions.endBeforeStart, path: ["end_date"] })
    .refine((v) => v.used_lessons <= v.total_lessons, { message: t.subscriptions.usedMoreThanTotal, path: ["used_lessons"] });
  type Values = z.infer<typeof schema>;
  const form = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!open) return;
    const today = new Date();
    form.reset({
      student_id: sub?.student_id ?? studentId ?? 0,
      title: sub?.title ?? "",
      start_date: sub?.start_date ?? toDateInput(today),
      end_date: sub?.end_date ?? toDateInput(addDays(today, 30)),
      total_lessons: sub?.total_lessons ?? 8,
      used_lessons: sub?.used_lessons ?? 0,
      notes: sub?.notes ?? "",
    });
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const mutation = useMutation({
    mutationFn: (v: Values) => {
      const body = { ...v, title: v.title || null, notes: v.notes || null };
      return edit ? subscriptionsApi.update(sub!.id, body) : subscriptionsApi.create(body);
    },
    onSuccess: () => {
      invalidate();
      toast.success(edit ? t.common.saved : t.subscriptions.created);
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const { errors } = form.formState;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{edit ? t.subscriptions.editTitle : t.subscriptions.createTitle}</DialogTitle>
          {sub && <DialogDescription>{sub.student_name}</DialogDescription>}
        </DialogHeader>
        <form onSubmit={form.handleSubmit((v) => mutation.mutate(v))} className="flex min-h-0 flex-1 flex-col" noValidate>
          <DialogBody className="grid gap-4 sm:grid-cols-2">
            {!edit && !studentId && (
              <Field label={t.common.student} error={errors.student_id?.message} className="sm:col-span-2">
                <NativeSelect {...form.register("student_id")}>
                  <option value={0}>—</option>
                  {students.data?.map((s) => (
                    <option key={s.id} value={s.id}>{s.full_name}</option>
                  ))}
                </NativeSelect>
              </Field>
            )}
            <Field label={t.subscriptions.name} optional className="sm:col-span-2">
              <Input placeholder={t.subscriptions.namePlaceholder} {...form.register("title")} />
            </Field>
            <Field label={t.subscriptions.startDate} error={errors.start_date?.message}>
              <Input type="date" {...form.register("start_date")} />
            </Field>
            <Field label={t.subscriptions.endDate} error={errors.end_date?.message}>
              <Input type="date" {...form.register("end_date")} />
            </Field>
            <Field label={t.subscriptions.totalLessons} error={errors.total_lessons?.message}>
              <Input type="number" min={1} inputMode="numeric" {...form.register("total_lessons")} />
            </Field>
            <Field label={t.subscriptions.usedLessons} error={errors.used_lessons?.message}>
              <Input type="number" min={0} inputMode="numeric" {...form.register("used_lessons")} />
            </Field>
            <Field label={t.subscriptions.notes} optional className="sm:col-span-2">
              <Textarea rows={2} {...form.register("notes")} />
            </Field>
            <p className="text-xs text-muted-foreground sm:col-span-2">{t.subscriptions.autoCharge}</p>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
            <Button type="submit" loading={mutation.isPending}>{edit ? t.common.save : t.common.create}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ExtendDialog({ open, onOpenChange, sub }: { open: boolean; onOpenChange: (o: boolean) => void; sub: Subscription }) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const [mode, setMode] = useState<"days" | "date">("days");
  const [days, setDays] = useState(30);
  const [date, setDate] = useState(sub.end_date);
  const [lessons, setLessons] = useState(8);

  useEffect(() => {
    if (open) {
      setMode("days");
      setDays(30);
      setDate(toDateInput(addDays(new Date(sub.end_date), 30)));
      setLessons(8);
    }
  }, [open, sub.end_date]);

  const mutation = useMutation({
    mutationFn: () =>
      subscriptionsApi.extend(sub.id, {
        ...(mode === "days" ? { add_days: days } : { new_end_date: date }),
        add_lessons: lessons,
      }),
    onSuccess: () => {
      invalidate();
      toast.success(t.subscriptions.extended);
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t.subscriptions.extendTitle}</DialogTitle>
          <DialogDescription>{sub.student_name}</DialogDescription>
        </DialogHeader>
        <DialogBody className="grid gap-4">
          <Tabs value={mode} onValueChange={(v) => setMode(v as "days" | "date")}>
            <TabsList className="w-full">
              <TabsTrigger value="days" className="flex-1">{t.subscriptions.byDays}</TabsTrigger>
              <TabsTrigger value="date" className="flex-1">{t.subscriptions.byDate}</TabsTrigger>
            </TabsList>
          </Tabs>
          {mode === "days" ? (
            <Field label={t.subscriptions.addDays}>
              <Input type="number" min={1} value={days} onChange={(e) => setDays(Number(e.target.value))} />
            </Field>
          ) : (
            <Field label={t.subscriptions.newEndDate}>
              <Input type="date" value={date} min={sub.start_date} onChange={(e) => setDate(e.target.value)} />
            </Field>
          )}
          <Field label={t.subscriptions.addLessons}>
            <Input type="number" min={0} value={lessons} onChange={(e) => setLessons(Number(e.target.value))} />
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button onClick={() => mutation.mutate()} loading={mutation.isPending} disabled={mode === "days" ? days < 1 : !date}>
            {t.subscriptions.extend}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Action menu for a subscription: extend, use/return lesson, freeze, edit, delete. */
/** Subscriptions are created and changed only by the administrator; teachers just view them. */
export function useCanManageSubscriptions() {
  return useAuth().user?.role === "admin";
}

export function SubscriptionActions(props: { sub: Subscription; compact?: boolean }) {
  return useCanManageSubscriptions() ? <ManageActions {...props} /> : null;
}

function ManageActions({ sub, compact }: { sub: Subscription; compact?: boolean }) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const [editing, setEditing] = useState(false);
  const [extending, setExtending] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const act = useMutation({
    mutationFn: async (kind: "use" | "return" | "freeze" | "unfreeze") => {
      if (kind === "use") return subscriptionsApi.useLesson(sub.id, 1);
      if (kind === "return") return subscriptionsApi.useLesson(sub.id, -1);
      if (kind === "freeze") return subscriptionsApi.freeze(sub.id);
      return subscriptionsApi.unfreeze(sub.id);
    },
    onSuccess: (_, kind) => {
      invalidate();
      toast.success(
        { use: t.subscriptions.lessonUsed, return: t.subscriptions.lessonReturned, freeze: t.subscriptions.frozen, unfreeze: t.subscriptions.unfrozen }[kind],
      );
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => subscriptionsApi.remove(sub.id),
    onSuccess: () => {
      invalidate();
      setDeleting(false);
      toast.success(t.common.deleted);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <>
      <div className="flex items-center gap-2">
        {!compact && (
          <>
            <Button size="sm" onClick={() => setExtending(true)}>
              <CalendarPlus />
              {t.subscriptions.extend}
            </Button>
            <Button size="sm" variant="outline" onClick={() => act.mutate("use")} disabled={sub.lessons_left <= 0} loading={act.isPending && act.variables === "use"}>
              <MinusCircle />
              {t.subscriptions.useLesson}
            </Button>
          </>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="icon-sm" variant="ghost" aria-label={t.common.actions}>
              <MoreHorizontal />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {compact && (
              <>
                <DropdownMenuItem onSelect={() => setExtending(true)}>
                  <CalendarPlus />
                  {t.subscriptions.extend}
                </DropdownMenuItem>
                <DropdownMenuItem disabled={sub.lessons_left <= 0} onSelect={() => act.mutate("use")}>
                  <MinusCircle />
                  {t.subscriptions.useLesson}
                </DropdownMenuItem>
              </>
            )}
            <DropdownMenuItem disabled={sub.used_lessons <= 0} onSelect={() => act.mutate("return")}>
              <PlusCircle />
              {t.subscriptions.returnLesson}
            </DropdownMenuItem>
            {sub.is_frozen ? (
              <DropdownMenuItem onSelect={() => act.mutate("unfreeze")}>
                <Sun />
                {t.subscriptions.unfreeze}
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem disabled={sub.status === "expired"} onSelect={() => act.mutate("freeze")}>
                <Snowflake />
                {t.subscriptions.freeze}
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={() => setEditing(true)}>
              <Pencil />
              {t.common.edit}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => setDeleting(true)}>
              <Trash2 />
              {t.common.delete}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <SubscriptionFormDialog open={editing} onOpenChange={setEditing} sub={sub} />
      <ExtendDialog open={extending} onOpenChange={setExtending} sub={sub} />
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t.subscriptions.deleteTitle}
        description={t.subscriptions.deleteText}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </>
  );
}
