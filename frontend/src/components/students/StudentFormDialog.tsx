import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { groupsApi, studentsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { ENGLISH_LEVELS, type EnglishLevel, type StudentProfile } from "@/types/api";
import { generatePassword } from "@/utils/format";
import { showInviteToast } from "@/components/common/InviteToast";
import { passwordSchema } from "@/utils/validation";

interface Props {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  student?: StudentProfile; // edit mode
}

export function StudentFormDialog({ open, onOpenChange, student }: Props) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const edit = !!student;
  const groups = useQuery({ queryKey: ["groups"], queryFn: groupsApi.list, enabled: open });

  const schema = z
    .object({
      full_name: z.string().trim().min(2, t.students.fullNameMin).max(200),
      email: z.string().trim().email(t.auth.invalidEmail),
      phone: z.string().trim().max(32).optional(),
      english_level: z.enum(ENGLISH_LEVELS as [EnglishLevel, ...EnglishLevel[]]),
      password: z.string().optional(),
      send_invite: z.boolean(),
      notes: z.string().max(5000).optional(),
      group_ids: z.array(z.number()),
    })
    .superRefine((v, ctx) => {
      if (edit) return;
      if (!v.password && !v.send_invite) {
        ctx.addIssue({ code: "custom", path: ["password"], message: t.students.passwordOrInvite });
      } else if (v.password) {
        const r = passwordSchema(t).safeParse(v.password);
        if (!r.success) ctx.addIssue({ code: "custom", path: ["password"], message: r.error.issues[0].message });
      }
    });
  type Values = z.infer<typeof schema>;

  const form = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) {
      form.reset({
        full_name: student?.full_name ?? "",
        email: student?.email ?? "",
        phone: student?.phone ?? "",
        english_level: student?.english_level ?? "A1",
        password: edit ? undefined : generatePassword(),
        send_invite: false,
        notes: student?.notes ?? "",
        group_ids: student?.groups.map((g) => g.id) ?? [],
      });
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const mutation = useMutation({
    mutationFn: (v: Values) =>
      edit
        ? studentsApi.update(student!.id, {
            full_name: v.full_name,
            phone: v.phone || null,
            english_level: v.english_level,
            notes: v.notes || null,
            group_ids: v.group_ids,
          })
        : studentsApi.create({
            full_name: v.full_name,
            email: v.email,
            phone: v.phone || null,
            english_level: v.english_level,
            password: v.password || null,
            send_invite: v.send_invite,
            notes: v.notes || null,
            group_ids: v.group_ids,
          }),
    onSuccess: (created, v) => {
      qc.invalidateQueries({ queryKey: ["students"] });
      qc.invalidateQueries({ queryKey: ["groups"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      if (edit) {
        toast.success(t.common.saved);
      } else if (v.send_invite && !v.password) {
        showInviteToast(t.students.inviteSent, v.email, created.dev_invite_url, t.students.devLink);
      } else {
        const creds = `${v.email} / ${v.password}`;
        toast.success(t.students.created, {
          description: creds,
          duration: 15000,
          action: { label: t.students.copyCredentials, onClick: () => navigator.clipboard?.writeText(creds) },
        });
      }
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const { errors } = form.formState;
  const groupIds = form.watch("group_ids") ?? [];
  const sendInvite = form.watch("send_invite");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{edit ? t.students.editTitle : t.students.addTitle}</DialogTitle>
          {!edit && <DialogDescription>{t.students.addHint}</DialogDescription>}
        </DialogHeader>
        <form onSubmit={form.handleSubmit((v) => mutation.mutate(v))} className="flex min-h-0 flex-1 flex-col" noValidate>
          <DialogBody className="grid gap-4 sm:grid-cols-2">
            <Field label={t.students.fullName} error={errors.full_name?.message} className="sm:col-span-2">
              <Input autoFocus aria-invalid={!!errors.full_name} {...form.register("full_name")} />
            </Field>
            <Field label={t.students.email} error={errors.email?.message}>
              <Input type="email" disabled={edit} aria-invalid={!!errors.email} {...form.register("email")} />
            </Field>
            <Field label={t.students.phone} optional>
              <Input type="tel" placeholder="+7 900 000-00-00" {...form.register("phone")} />
            </Field>
            <Field label={t.students.level}>
              <NativeSelect {...form.register("english_level")}>
                {ENGLISH_LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            {!edit && !sendInvite && (
              <Field label={t.students.tempPassword} error={errors.password?.message} hint={t.auth.passwordRules}>
                <div className="flex gap-2">
                  <Input className="font-mono" aria-invalid={!!errors.password} {...form.register("password")} />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    aria-label={t.students.generate}
                    onClick={() => form.setValue("password", generatePassword(), { shouldValidate: true })}
                  >
                    <RefreshCw />
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    aria-label={t.students.copyCredentials}
                    onClick={() => {
                      navigator.clipboard?.writeText(form.getValues("password") ?? "");
                      toast.success(t.students.copied);
                    }}
                  >
                    <Copy />
                  </Button>
                </div>
              </Field>
            )}
            {!edit && (
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border bg-secondary/40 p-3 sm:col-span-2">
                <Checkbox
                  className="mt-0.5"
                  checked={sendInvite}
                  onCheckedChange={(c) => {
                    form.setValue("send_invite", c === true);
                    if (c === true) form.setValue("password", "");
                    else form.setValue("password", generatePassword());
                  }}
                />
                <span>
                  <span className="block text-sm font-medium text-primary">{t.students.sendInvite}</span>
                  <span className="block text-xs text-muted-foreground">{t.students.sendInviteHint}</span>
                </span>
              </label>
            )}
            {(groups.data?.length ?? 0) > 0 && (
              <Field label={t.common.groups} className="sm:col-span-2">
                <div className="flex flex-wrap gap-2">
                  {groups.data!.map((g) => (
                    <label key={g.id} className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-secondary/60">
                      <Checkbox
                        checked={groupIds.includes(g.id)}
                        onCheckedChange={(c) =>
                          form.setValue("group_ids", c ? [...groupIds, g.id] : groupIds.filter((x) => x !== g.id))
                        }
                      />
                      {g.name}
                    </label>
                  ))}
                </div>
              </Field>
            )}
            <Field label={t.students.notes} optional className="sm:col-span-2">
              <Textarea rows={3} {...form.register("notes")} />
            </Field>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t.common.cancel}
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              {edit ? t.common.save : t.common.create}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
