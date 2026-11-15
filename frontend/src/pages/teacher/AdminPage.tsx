import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarCheck,
  CreditCard,
  GraduationCap,
  KeyRound,
  MoreHorizontal,
  Pencil,
  Plus,
  Power,
  Presentation,
  RefreshCw,
  Search,
  Trash2,
  UserX,
  Users,
  UserRoundCog,
} from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";
import { toast } from "sonner";

import { CardListSkeleton, EmptyState, ErrorState, Field, PageHeader, StatCard, StatsSkeleton } from "@/components/common";
import { showInviteToast } from "@/components/common/InviteToast";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input, NativeSelect } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { adminApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { ENGLISH_LEVELS, type AdminUser, type EnglishLevel, type Role } from "@/types/api";
import { fmtDate, fmtRelative, generatePassword } from "@/utils/format";
import { passwordSchema } from "@/utils/validation";

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["admin"] });
}

function CreateUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const teachers = useQuery({ queryKey: ["admin", "teachers"], queryFn: adminApi.teachers, enabled: open });
  const [role, setRole] = useState<"student" | "teacher">("student");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [level, setLevel] = useState<EnglishLevel>("A1");
  const [invite, setInvite] = useState(true);
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setFullName("");
      setEmail("");
      setPhone("");
      setTeacherId("");
      setLevel("A1");
      setInvite(true);
      setPassword(generatePassword());
      setErrors({});
    }
  }, [open]);

  const create = useMutation({
    mutationFn: async () => {
      const base = { email: email.trim(), full_name: fullName.trim(), phone: phone.trim() || null, password: invite ? null : password, send_invite: invite };
      if (role === "teacher") {
        await adminApi.createTeacher(base);
        return null;
      }
      const s = await adminApi.createStudent({ ...base, english_level: level, group_ids: [], teacher_id: teacherId ? Number(teacherId) : null });
      return s.dev_invite_url ?? null;
    },
    onSuccess: (devUrl) => {
      invalidate();
      if (invite) showInviteToast(t.students.inviteSent, email, devUrl, t.students.devLink);
      else toast.success(t.admin.created, { description: `${email} / ${password}`, duration: 15000 });
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  function submit() {
    const e: Record<string, string> = {};
    if (fullName.trim().length < 2) e.fullName = t.students.fullNameMin;
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) e.email = t.auth.invalidEmail;
    if (!invite) {
      const r = passwordSchema(t).safeParse(password);
      if (!r.success) e.password = r.error.issues[0].message;
    }
    setErrors(e);
    if (!Object.keys(e).length) create.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{t.admin.createUser}</DialogTitle>
        </DialogHeader>
        <DialogBody className="grid gap-4 sm:grid-cols-2">
          <Tabs value={role} onValueChange={(v) => setRole(v as "student" | "teacher")} className="sm:col-span-2">
            <TabsList className="w-full">
              <TabsTrigger value="student" className="flex-1"><GraduationCap className="size-4" />{t.admin.role.student}</TabsTrigger>
              <TabsTrigger value="teacher" className="flex-1"><Presentation className="size-4" />{t.admin.role.teacher}</TabsTrigger>
            </TabsList>
          </Tabs>
          <Field label={t.students.fullName} error={errors.fullName} className="sm:col-span-2">
            <Input value={fullName} onChange={(e) => setFullName(e.target.value)} aria-invalid={!!errors.fullName} maxLength={200} />
          </Field>
          <Field label={t.students.email} error={errors.email}>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} aria-invalid={!!errors.email} />
          </Field>
          <Field label={t.students.phone} optional>
            <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </Field>
          {role === "student" && (
            <>
              <Field label={t.dashboard.teacher}>
                <NativeSelect value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
                  <option value="">{t.admin.noTeacher}</option>
                  {teachers.data?.map((x) => <option key={x.id} value={x.id}>{x.full_name}</option>)}
                </NativeSelect>
              </Field>
              <Field label={t.students.level}>
                <NativeSelect value={level} onChange={(e) => setLevel(e.target.value as EnglishLevel)}>
                  {ENGLISH_LEVELS.map((l) => <option key={l}>{l}</option>)}
                </NativeSelect>
              </Field>
            </>
          )}
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border bg-secondary/40 p-3 sm:col-span-2">
            <Checkbox className="mt-0.5" checked={invite} onCheckedChange={(c) => setInvite(c === true)} />
            <span>
              <span className="block text-sm font-medium text-primary">{t.students.sendInvite}</span>
              <span className="block text-xs text-muted-foreground">{t.students.sendInviteHint}</span>
            </span>
          </label>
          {!invite && (
            <Field label={t.students.tempPassword} error={errors.password} hint={t.auth.passwordRules} className="sm:col-span-2">
              <div className="flex gap-2">
                <Input className="font-mono" value={password} onChange={(e) => setPassword(e.target.value)} />
                <Button type="button" variant="outline" size="icon" aria-label={t.students.generate} onClick={() => setPassword(generatePassword())}>
                  <RefreshCw />
                </Button>
              </div>
            </Field>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button loading={create.isPending} onClick={submit}>{t.common.create}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditUserDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [level, setLevel] = useState<EnglishLevel>("A1");
  useEffect(() => {
    if (user) {
      setFullName(user.full_name);
      setEmail(user.email);
      setPhone(user.phone ?? "");
      setLevel(user.english_level ?? "A1");
    }
  }, [user]);
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const save = useMutation({
    mutationFn: () =>
      adminApi.updateUser(user!.id, {
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
        ...(user!.role === "student" ? { english_level: level } : {}),
      }),
    onSuccess: () => {
      invalidate();
      toast.success(t.common.saved);
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={!!user} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t.common.edit}</DialogTitle>
          <DialogDescription>{user?.email}</DialogDescription>
        </DialogHeader>
        <DialogBody className="grid gap-4">
          <Field label={t.students.fullName}><Input value={fullName} onChange={(e) => setFullName(e.target.value)} /></Field>
          <Field
            label={t.students.email}
            hint={email.trim().toLowerCase() !== user?.email.toLowerCase() ? t.admin.emailChangeHint : undefined}
            error={email && !emailOk ? t.admin.emailInvalid : undefined}
          >
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} aria-invalid={!!email && !emailOk} />
          </Field>
          <Field label={t.students.phone} optional><Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
          {user?.role === "student" && (
            <Field label={t.students.level}>
              <NativeSelect value={level} onChange={(e) => setLevel(e.target.value as EnglishLevel)}>
                {ENGLISH_LEVELS.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </NativeSelect>
            </Field>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button loading={save.isPending} disabled={fullName.trim().length < 2 || !emailOk} onClick={() => save.mutate()}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteUserDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const isTeacher = user?.role === "teacher";
  const needsTransfer = isTeacher && (user?.students_count ?? 0) > 0;
  const teachers = useQuery({ queryKey: ["admin", "teachers"], queryFn: adminApi.teachers, enabled: !!user && isTeacher });
  const others = (teachers.data ?? []).filter((x) => x.id !== user?.teacher_profile_id);
  const [transferTo, setTransferTo] = useState("");
  const [sure, setSure] = useState(false);
  useEffect(() => {
    setTransferTo("");
    setSure(false);
  }, [user]);
  const remove = useMutation({
    mutationFn: () => adminApi.deleteUser(user!.id, transferTo ? Number(transferTo) : undefined),
    onSuccess: () => {
      invalidate();
      toast.success(t.admin.userDeleted);
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!user) return null;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{isTeacher ? t.admin.deleteTeacherTitle : t.admin.deleteStudentTitle}</DialogTitle>
          <DialogDescription>{user.full_name} · {user.email}</DialogDescription>
        </DialogHeader>
        <DialogBody className="grid gap-4">
          <p className="text-sm text-muted-foreground">{isTeacher ? t.admin.deleteTeacherText : t.admin.deleteStudentText}</p>
          {needsTransfer && (
            <Field label={t.admin.transferTo} hint={t.admin.transferHint(user.students_count ?? 0)}>
              <NativeSelect value={transferTo} onChange={(e) => setTransferTo(e.target.value)}>
                <option value="">{t.actAs.choose}</option>
                {others.map((x) => (
                  <option key={x.id} value={x.id}>{x.full_name} · {t.common.studentsCount(x.students_count)}</option>
                ))}
              </NativeSelect>
            </Field>
          )}
          <p className="rounded-lg bg-secondary/60 p-3 text-xs text-muted-foreground">{t.admin.deactivateInstead}</p>
          <label className="flex items-start gap-2 text-sm">
            <Checkbox checked={sure} onCheckedChange={(v) => setSure(v === true)} className="mt-0.5" />
            <span>{t.admin.deleteConfirm}</span>
          </label>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button
            variant="destructive"
            loading={remove.isPending}
            disabled={!sure || (needsTransfer && !transferTo)}
            onClick={() => remove.mutate()}
          >
            <Trash2 />
            {t.common.delete}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PasswordDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const { t } = useI18n();
  const [mode, setMode] = useState<"link" | "set">("link");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  useEffect(() => {
    if (user) {
      setMode("link");
      setPassword(generatePassword());
      setError(undefined);
    }
  }, [user]);
  const save = useMutation({
    mutationFn: () => adminApi.setPassword(user!.id, mode === "set" ? { password } : { send_link: true }),
    onSuccess: (r) => {
      if (mode === "link") showInviteToast(r.detail, user!.email, r.dev_invite_url, t.students.devLink);
      else toast.success(t.admin.passwordSet, { description: `${user!.email} / ${password}`, duration: 15000 });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  function submit() {
    if (mode === "set") {
      const r = passwordSchema(t).safeParse(password);
      if (!r.success) return setError(r.error.issues[0].message);
    }
    save.mutate();
  }
  return (
    <Dialog open={!!user} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t.admin.passwordTitle}</DialogTitle>
          <DialogDescription>{user?.full_name} · {user?.email}</DialogDescription>
        </DialogHeader>
        <DialogBody className="grid gap-4">
          <Tabs value={mode} onValueChange={(v) => setMode(v as "link" | "set")}>
            <TabsList className="w-full">
              <TabsTrigger value="link" className="flex-1">{t.admin.sendLink}</TabsTrigger>
              <TabsTrigger value="set" className="flex-1">{t.admin.setPassword}</TabsTrigger>
            </TabsList>
          </Tabs>
          {mode === "set" && (
            <Field label={t.settings.newPassword} error={error} hint={t.auth.passwordRules}>
              <div className="flex gap-2">
                <Input className="font-mono" value={password} onChange={(e) => setPassword(e.target.value)} />
                <Button type="button" variant="outline" size="icon" aria-label={t.students.generate} onClick={() => setPassword(generatePassword())}>
                  <RefreshCw />
                </Button>
              </div>
            </Field>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button loading={save.isPending} onClick={submit}>{mode === "set" ? t.common.save : t.admin.sendLink}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReassignDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const teachers = useQuery({ queryKey: ["admin", "teachers"], queryFn: adminApi.teachers, enabled: !!user });
  const [teacherId, setTeacherId] = useState("");
  useEffect(() => {
    if (user) setTeacherId(user.teacher_id?.toString() ?? "");
  }, [user]);
  const save = useMutation({
    mutationFn: () => adminApi.reassign(user!.student_id!, Number(teacherId)),
    onSuccess: () => {
      invalidate();
      toast.success(t.admin.teacherChanged);
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={!!user} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t.admin.changeTeacher}</DialogTitle>
          <DialogDescription>{user?.full_name}</DialogDescription>
        </DialogHeader>
        <DialogBody className="grid gap-3">
          <NativeSelect value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
            <option value="" disabled>—</option>
            {teachers.data?.map((x) => <option key={x.id} value={x.id}>{x.full_name} · {t.common.studentsCount(x.students_count)}</option>)}
          </NativeSelect>
          <p className="text-xs text-muted-foreground">{t.admin.changeTeacherHint}</p>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button loading={save.isPending} disabled={!teacherId || Number(teacherId) === user?.teacher_id} onClick={() => save.mutate()}>
            {t.common.save}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Administrator console: school stats and user management. */
export default function AdminPage() {
  const { t, locale } = useI18n();
  const { user: me } = useAuth();
  const invalidate = useInvalidate();
  const [role, setRole] = useState<Role | "">("");
  const [search, setSearch] = useState("");
  const deferred = useDeferredValue(search);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [pwUser, setPwUser] = useState<AdminUser | null>(null);
  const [reassigning, setReassigning] = useState<AdminUser | null>(null);
  const [deletingUser, setDeletingUser] = useState<AdminUser | null>(null);

  const stats = useQuery({ queryKey: ["admin", "stats"], queryFn: adminApi.stats });
  const filters = { role, search: deferred };
  const users = useQuery({ queryKey: ["admin", "users", filters], queryFn: () => adminApi.users(filters), placeholderData: (p) => p });

  const toggle = useMutation({
    mutationFn: (u: AdminUser) => adminApi.updateUser(u.id, { is_active: !u.is_active }),
    onSuccess: (u) => {
      invalidate();
      toast.success(u.is_active ? t.admin.activated : t.admin.deactivated);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const roleVariant = { admin: "primary", teacher: "default", student: "neutral" } as const;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t.admin.title}
        subtitle={t.admin.subtitle}
        actions={<Button onClick={() => setCreating(true)}><Plus />{t.admin.createUser}</Button>}
      />

      {stats.isLoading ? (
        <StatsSkeleton />
      ) : stats.data ? (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <StatCard icon={Presentation} label={t.admin.teachers} value={stats.data.teachers} />
          <StatCard icon={Users} tone="success" label={t.admin.activeStudents} value={stats.data.active_students} hint={`${t.admin.students}: ${stats.data.students}`} />
          <StatCard icon={UserX} tone={stats.data.unassigned_students ? "warning" : "primary"} label={t.admin.unassigned} value={stats.data.unassigned_students} />
          <StatCard icon={CreditCard} tone="primary" label={t.admin.activeSubscriptions} value={stats.data.active_subscriptions}
            hint={<span className="inline-flex items-center gap-1"><CalendarCheck className="size-3" />{t.admin.lessonsMonth}: {stats.data.lessons_this_month}</span>} />
        </div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={role} onValueChange={(v) => setRole(v as Role | "")}>
          <TabsList>
            <TabsTrigger value="">{t.admin.allRoles}</TabsTrigger>
            <TabsTrigger value="teacher">{t.admin.teachers}</TabsTrigger>
            <TabsTrigger value="student">{t.admin.students}</TabsTrigger>
            <TabsTrigger value="admin">{t.admin.role.admin}</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t.common.search} className="pl-9" />
        </div>
      </div>

      {users.isLoading ? (
        <CardListSkeleton rows={6} />
      ) : users.isError ? (
        <ErrorState onRetry={() => users.refetch()} />
      ) : !users.data?.length ? (
        <Card><EmptyState icon={Users} title={t.admin.empty} /></Card>
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>{t.admin.users}</TableHead>
                <TableHead>{t.common.status}</TableHead>
                <TableHead className="hidden md:table-cell">{t.dashboard.teacher} / {t.admin.students}</TableHead>
                <TableHead className="hidden lg:table-cell">{t.admin.lastLogin}</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.data.map((u) => (
                <TableRow key={u.id} className={u.is_active ? "" : "opacity-60"}>
                  <TableCell>
                    <div className="flex min-w-0 items-center gap-3">
                      <Avatar name={u.full_name} />
                      <div className="min-w-0">
                        <p className="truncate font-medium text-primary">
                          {u.full_name}
                          {u.id === me?.id && <span className="ml-2 text-xs font-normal text-muted-foreground">({t.admin.you})</span>}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">{u.email}</p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col items-start gap-1">
                      <Badge variant={roleVariant[u.role]}>{t.admin.role[u.role]}{u.english_level ? ` · ${u.english_level}` : ""}</Badge>
                      {!u.is_active && <Badge variant="danger">{t.students.inactive}</Badge>}
                    </div>
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground md:table-cell">
                    {u.role === "student" ? (u.teacher_name ?? <span className="text-warning">{t.admin.noTeacher}</span>) : u.role === "teacher" ? t.common.studentsCount(u.students_count ?? 0) : "—"}
                  </TableCell>
                  <TableCell className="hidden whitespace-nowrap text-muted-foreground lg:table-cell">
                    {u.last_login_at ? fmtRelative(u.last_login_at, locale) : t.admin.never}
                    <span className="block text-xs">{fmtDate(u.created_at, locale)}</span>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm" aria-label={t.common.actions}><MoreHorizontal /></Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setEditing(u)}><Pencil />{t.common.edit}</DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => setPwUser(u)}><KeyRound />{t.admin.passwordTitle}</DropdownMenuItem>
                        {u.role === "student" && (
                          <DropdownMenuItem onSelect={() => setReassigning(u)}><UserRoundCog />{t.admin.changeTeacher}</DropdownMenuItem>
                        )}
                        {u.id !== me?.id && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem destructive={u.is_active} onSelect={() => toggle.mutate(u)}>
                              <Power />
                              {u.is_active ? t.admin.deactivate : t.admin.activate}
                            </DropdownMenuItem>
                            {u.role !== "admin" && (
                              <DropdownMenuItem destructive onSelect={() => setDeletingUser(u)}>
                                <Trash2 />
                                {t.common.delete}
                              </DropdownMenuItem>
                            )}
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <CreateUserDialog open={creating} onOpenChange={setCreating} />
      <EditUserDialog user={editing} onClose={() => setEditing(null)} />
      <PasswordDialog user={pwUser} onClose={() => setPwUser(null)} />
      <ReassignDialog user={reassigning} onClose={() => setReassigning(null)} />
      <DeleteUserDialog user={deletingUser} onClose={() => setDeletingUser(null)} />
    </div>
  );
}
