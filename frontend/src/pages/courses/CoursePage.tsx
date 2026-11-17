import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  CircleCheck,
  CircleDashed,
  Clock,
  Copy,
  Eye,
  FolderInput,
  GraduationCap,
  Layers,
  MoreHorizontal,
  Pencil,
  Plus,
  Settings2,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { EmptyState, ErrorState, Field, PageSkeleton } from "@/components/common";
import { Toggle } from "@/components/tests/QuestionEditor";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { useCoursesBase } from "@/pages/courses/shared";
import { coursesApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { ENGLISH_LEVELS, type CourseDetail, type CourseModule, type EnglishLevel, type LessonSummary } from "@/types/api";

type Dlg =
  | { kind: "settings" }
  | { kind: "deleteCourse" }
  | { kind: "renameLevel"; id: number; title: string }
  | { kind: "deleteLevel"; id: number }
  | { kind: "addModule"; levelId: number }
  | { kind: "renameModule"; id: number; title: string; description: string }
  | { kind: "copyModule"; id: number }
  | { kind: "deleteModule"; id: number }
  | { kind: "copyLesson"; id: number }
  | { kind: "moveLesson"; id: number; moduleId: number }
  | { kind: "deleteLesson"; id: number };

/** Applies a structure change that answers with the whole tree. */
function useTreeMutation<A>(courseId: number, fn: (a: A) => Promise<CourseDetail>, done?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (tree) => {
      qc.setQueryData(["courses", courseId], tree);
      qc.invalidateQueries({ queryKey: ["courses"], exact: true });
      if (done) toast.success(done);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

function TextDialog({
  open,
  title,
  label,
  initial = "",
  withDescription,
  initialDescription = "",
  loading,
  onClose,
  onSubmit,
}: {
  open: boolean;
  title: string;
  label: string;
  initial?: string;
  withDescription?: boolean;
  initialDescription?: string;
  loading: boolean;
  onClose: () => void;
  onSubmit: (value: string, description: string) => void;
}) {
  const { t } = useI18n();
  const [value, setValue] = useState(initial);
  const [description, setDescription] = useState(initialDescription);
  useEffect(() => {
    setValue(initial);
    setDescription(initialDescription);
  }, [open, initial, initialDescription]);
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4">
          <Field label={label}>
            <Input
              value={value}
              maxLength={200}
              autoFocus
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && value.trim() && !withDescription && onSubmit(value.trim(), description)}
            />
          </Field>
          {withDescription && (
            <Field label={t.courses.description} optional>
              <Textarea rows={3} value={description} maxLength={5000} onChange={(e) => setDescription(e.target.value)} />
            </Field>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={!value.trim()} loading={loading} onClick={() => onSubmit(value.trim(), description.trim())}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Pick a target (a level for modules, a module for lessons); "" = next to the original. */
function TargetDialog({
  open,
  title,
  hint,
  options,
  allowNear,
  initial = "",
  confirmLabel,
  loading,
  onClose,
  onSubmit,
}: {
  open: boolean;
  title: string;
  hint?: string;
  options: { id: number; label: string }[];
  allowNear: boolean;
  initial?: string;
  confirmLabel: string;
  loading: boolean;
  onClose: () => void;
  onSubmit: (targetId: number | undefined) => void;
}) {
  const { t } = useI18n();
  const [target, setTarget] = useState(initial);
  useEffect(() => setTarget(initial), [open, initial]);
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-2">
          <NativeSelect value={target} onChange={(e) => setTarget(e.target.value)} aria-label={title}>
            {allowNear && <option value="">{t.courses.copyNear}</option>}
            {options.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </NativeSelect>
          {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button
            disabled={!allowNear && !target}
            loading={loading}
            onClick={() => onSubmit(target ? Number(target) : undefined)}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SettingsDialog({ course, open, onClose }: { course: CourseDetail; open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const [title, setTitle] = useState(course.title);
  const [description, setDescription] = useState(course.description ?? "");
  const [published, setPublished] = useState(course.published);
  useEffect(() => {
    setTitle(course.title);
    setDescription(course.description ?? "");
    setPublished(course.published);
  }, [open, course]);
  const save = useTreeMutation(course.id, () => coursesApi.update(course.id, { title, description: description || null, published }), t.common.saved);
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader><DialogTitle>{t.courses.settings}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4">
          <Field label={t.courses.courseTitle}>
            <Input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label={t.courses.description} optional>
            <Textarea rows={4} value={description} maxLength={5000} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Toggle label={t.courses.publishCourse} hint={t.courses.publishCourseHint} checked={published} onChange={setPublished} />
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={!title.trim()} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>
            {t.common.save}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function LessonRow({
  lesson,
  index,
  total,
  onDialog,
  onUpdate,
}: {
  lesson: LessonSummary;
  index: number;
  total: number;
  onDialog: (d: Dlg) => void;
  onUpdate: (data: { published?: boolean; position?: number }) => void;
}) {
  const { t } = useI18n();
  const { base, editor } = useCoursesBase();
  const href = editor ? `${base}/lessons/${lesson.id}/edit` : `${base}/lessons/${lesson.id}`;
  return (
    <li className="group flex items-center gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-secondary/60 sm:px-3">
      <span className="tabular flex size-7 shrink-0 items-center justify-center rounded-lg bg-secondary text-xs font-semibold text-muted-foreground">
        {index + 1}
      </span>
      <Link to={href} className="min-w-0 flex-1">
        <span className="block break-words text-sm font-medium text-primary group-hover:text-accent">{lesson.title}</span>
        <span className="flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
          <span>{t.courses.blocksCount(lesson.blocks_count)}</span>
          {lesson.duration_minutes && (
            <span className="inline-flex items-center gap-1"><Clock className="size-3" />{t.common.minutes(lesson.duration_minutes)}</span>
          )}
        </span>
      </Link>
      {editor && (
        <>
          {lesson.published ? (
            <CircleCheck className="size-4 shrink-0 text-success" aria-label={t.courses.published} />
          ) : (
            <Badge variant="warning" className="shrink-0">{t.courses.draft}</Badge>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon-sm" variant="ghost" className="shrink-0" aria-label={t.common.actions}><MoreHorizontal /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild><Link to={`${base}/lessons/${lesson.id}/edit`}><Pencil />{t.common.edit}</Link></DropdownMenuItem>
              <DropdownMenuItem asChild><Link to={`${base}/lessons/${lesson.id}`}><Eye />{t.courses.preview}</Link></DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onUpdate({ published: !lesson.published })}>
                {lesson.published ? <CircleDashed /> : <CircleCheck />}
                {lesson.published ? t.courses.unpublish : t.courses.publish}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled={index === 0} onSelect={() => onUpdate({ position: index - 1 })}><ArrowUp />{t.courses.moveUp}</DropdownMenuItem>
              <DropdownMenuItem disabled={index === total - 1} onSelect={() => onUpdate({ position: index + 1 })}><ArrowDown />{t.courses.moveDown}</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onDialog({ kind: "moveLesson", id: lesson.id, moduleId: 0 })}><FolderInput />{t.courses.moveLesson}</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onDialog({ kind: "copyLesson", id: lesson.id })}><Copy />{t.courses.copyLesson}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={() => onDialog({ kind: "deleteLesson", id: lesson.id })}><Trash2 />{t.common.delete}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </>
      )}
    </li>
  );
}

function AddLesson({ moduleId }: { moduleId: number }) {
  const { t } = useI18n();
  const { base } = useCoursesBase();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const add = useMutation({
    mutationFn: () => coursesApi.addLesson(moduleId, title.trim()),
    onSuccess: (les) => {
      qc.invalidateQueries({ queryKey: ["courses"] });
      navigate(`${base}/lessons/${les.id}/edit`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <form
      className="mt-2 flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (title.trim()) add.mutate();
      }}
    >
      <Input value={title} maxLength={200} placeholder={t.courses.lessonTitle} onChange={(e) => setTitle(e.target.value)} className="h-9" />
      <Button type="submit" size="sm" variant="soft" disabled={!title.trim()} loading={add.isPending} className="shrink-0">
        <Plus />
        {t.courses.addLesson}
      </Button>
    </form>
  );
}

function ModuleCard({
  module,
  index,
  total,
  onDialog,
  courseId,
}: {
  module: CourseModule;
  index: number;
  total: number;
  onDialog: (d: Dlg) => void;
  courseId: number;
}) {
  const { t } = useI18n();
  const { editor } = useCoursesBase();
  const move = useTreeMutation(courseId, (position: number) => coursesApi.updateModule(module.id, { position }));
  const updateLesson = useTreeMutation(courseId, (a: { id: number; data: { published?: boolean; position?: number } }) =>
    coursesApi.updateLesson(a.id, a.data),
  );
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-accent">{t.courses.modulePrefix(index + 1)}</p>
          <h3 className="mt-0.5 break-words text-base font-semibold text-primary">{module.title}</h3>
          {module.description && <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">{module.description}</p>}
        </div>
        {editor && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon-sm" variant="ghost" aria-label={t.common.actions}><MoreHorizontal /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => onDialog({ kind: "renameModule", id: module.id, title: module.title, description: module.description ?? "" })}>
                <Pencil />{t.courses.renameModule}
              </DropdownMenuItem>
              <DropdownMenuItem disabled={index === 0} onSelect={() => move.mutate(index - 1)}><ArrowUp />{t.courses.moveUp}</DropdownMenuItem>
              <DropdownMenuItem disabled={index === total - 1} onSelect={() => move.mutate(index + 1)}><ArrowDown />{t.courses.moveDown}</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onDialog({ kind: "copyModule", id: module.id })}><Copy />{t.courses.copyModule}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={() => onDialog({ kind: "deleteModule", id: module.id })}><Trash2 />{t.common.delete}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      {module.lessons.length ? (
        <ul className="mt-3 grid gap-0.5">
          {module.lessons.map((l, i) => (
            <LessonRow
              key={l.id}
              lesson={l}
              index={i}
              total={module.lessons.length}
              onDialog={(d) => onDialog(d.kind === "moveLesson" ? { ...d, moduleId: module.id } : d)}
              onUpdate={(data) => updateLesson.mutate({ id: l.id, data })}
            />
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">{t.courses.noLessons}</p>
      )}
      {editor && <AddLesson moduleId={module.id} />}
    </Card>
  );
}

export default function CoursePage() {
  const { courseId } = useParams();
  const id = Number(courseId);
  const { t } = useI18n();
  const { base, editor } = useCoursesBase();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["courses", id], queryFn: () => coursesApi.get(id) });
  const [tab, setTab] = useState<string>("");
  const [dlg, setDlg] = useState<Dlg | null>(null);
  const close = () => setDlg(null);

  const levels = q.data?.levels ?? [];
  useEffect(() => {
    if (levels.length && !levels.some((l) => String(l.id) === tab)) setTab(String(levels[0].id));
  }, [levels, tab]);

  const allModules = useMemo(
    () => levels.flatMap((lv) => lv.modules.map((m) => ({ id: m.id, label: `${lv.level} · ${m.title}` }))),
    [levels],
  );

  const addLevel = useTreeMutation(id, (level: EnglishLevel) => coursesApi.addLevel(id, { level }));
  const renameLevel = useTreeMutation(id, (a: { id: number; title: string }) => coursesApi.updateLevel(a.id, { title: a.title }));
  const removeLevel = useTreeMutation(id, (levelId: number) => coursesApi.removeLevel(levelId), t.common.deleted);
  const addModule = useTreeMutation(id, (a: { levelId: number; title: string; description: string }) =>
    coursesApi.addModule(a.levelId, { title: a.title, description: a.description || null }),
  );
  const renameModule = useTreeMutation(id, (a: { id: number; title: string; description: string }) =>
    coursesApi.updateModule(a.id, { title: a.title, description: a.description || null }),
  );
  const copyModule = useTreeMutation(id, (a: { id: number; target?: number }) => coursesApi.copyModule(a.id, a.target), t.courses.copied);
  const removeModule = useTreeMutation(id, (moduleId: number) => coursesApi.removeModule(moduleId), t.common.deleted);
  const moveLesson = useTreeMutation(id, (a: { id: number; target: number }) => coursesApi.updateLesson(a.id, { module_id: a.target }));
  const removeLesson = useTreeMutation(id, (lessonId: number) => coursesApi.removeLesson(lessonId), t.common.deleted);
  const copyLesson = useMutation({
    mutationFn: (a: { id: number; target?: number }) => coursesApi.copyLesson(a.id, a.target),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["courses"] });
      toast.success(t.courses.copied);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const removeCourse = useMutation({
    mutationFn: () => coursesApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["courses"] });
      toast.success(t.common.deleted);
      navigate(base, { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const c = q.data;
  const missing = ENGLISH_LEVELS.filter((l) => !levels.some((lv) => lv.level === l));

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link to={base} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.courses.title}
      </Link>

      <Card className="p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 gap-3">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
              <GraduationCap className="size-5" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="page-title break-words">{c.title}</h1>
                {editor && <Badge variant={c.published ? "success" : "warning"}>{c.published ? t.courses.published : t.courses.draft}</Badge>}
              </div>
              {c.description && <p className="page-subtitle whitespace-pre-wrap">{c.description}</p>}
              <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                <span className="inline-flex items-center gap-1"><Layers className="size-4" />{t.courses.modulesCount(c.modules_count)}</span>
                <span>{t.courses.lessonsCount(c.lessons_count)}</span>
                {editor && c.draft_lessons_count > 0 && <span>{t.courses.draftsCount(c.draft_lessons_count)}</span>}
                {c.author_name && <span>{t.courses.author}: {c.author_name}</span>}
              </p>
            </div>
          </div>
          {editor && (
            <div className="flex shrink-0 gap-2">
              <Button variant="outline" onClick={() => setDlg({ kind: "settings" })}><Settings2 />{t.courses.settings}</Button>
              <Button variant="ghost" size="icon" className="hover:text-danger" aria-label={t.common.delete} onClick={() => setDlg({ kind: "deleteCourse" })}>
                <Trash2 />
              </Button>
            </div>
          )}
        </div>
        {editor && !c.published && (
          <p className="mt-4 rounded-xl bg-warning-soft px-4 py-2.5 text-sm text-primary">{t.courses.notPublished}</p>
        )}
      </Card>

      {!levels.length ? (
        <Card>
          <EmptyState icon={Layers} title={t.courses.noLevels} />
          {editor && (
            <div className="flex flex-wrap justify-center gap-2 px-6 pb-8">
              {missing.map((l) => (
                <Button key={l} variant="outline" size="sm" loading={addLevel.isPending && addLevel.variables === l} onClick={() => addLevel.mutate(l)}>
                  <Plus />{l}
                </Button>
              ))}
            </div>
          )}
        </Card>
      ) : (
        <Tabs value={tab} onValueChange={setTab}>
          <div className="flex flex-wrap items-center gap-2">
            <TabsList className="max-w-full">
              {levels.map((lv) => (
                <TabsTrigger key={lv.id} value={String(lv.id)}>{lv.title}</TabsTrigger>
              ))}
            </TabsList>
            {editor && missing.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" loading={addLevel.isPending}><Plus />{t.courses.addLevel}</Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start">
                  {missing.map((l) => (
                    <DropdownMenuItem key={l} onSelect={() => addLevel.mutate(l, { onSuccess: (tree) => setTab(String(tree.levels.find((x) => x.level === l)?.id ?? tab)) })}>
                      {l}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
          {levels.map((lv) => (
            <TabsContent key={lv.id} value={String(lv.id)} className="space-y-4">
              {editor && (
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => setDlg({ kind: "renameLevel", id: lv.id, title: lv.title })}>
                      <Pencil />{t.courses.renameLevel}
                    </Button>
                    <Button variant="ghost" size="icon-sm" className="hover:text-danger" aria-label={t.common.delete} onClick={() => setDlg({ kind: "deleteLevel", id: lv.id })}>
                      <Trash2 />
                    </Button>
                  </div>
                  <Button size="sm" onClick={() => setDlg({ kind: "addModule", levelId: lv.id })}><Plus />{t.courses.addModule}</Button>
                </div>
              )}
              {lv.modules.length ? (
                lv.modules.map((m, i) => (
                  <ModuleCard key={m.id} module={m} index={i} total={lv.modules.length} onDialog={setDlg} courseId={id} />
                ))
              ) : (
                <Card><EmptyState icon={Layers} title={t.courses.noModules} /></Card>
              )}
            </TabsContent>
          ))}
        </Tabs>
      )}

      {editor && (
        <>
          <SettingsDialog course={c} open={dlg?.kind === "settings"} onClose={close} />
          <ConfirmDialog
            open={dlg?.kind === "deleteCourse"}
            onOpenChange={(o) => !o && close()}
            title={t.courses.deleteCourse}
            description={t.courses.deleteCourseText}
            confirmLabel={t.common.delete}
            cancelLabel={t.common.cancel}
            destructive
            loading={removeCourse.isPending}
            onConfirm={() => removeCourse.mutate()}
          />
          <TextDialog
            open={dlg?.kind === "renameLevel"}
            title={t.courses.renameLevel}
            label={t.courses.levelTitle}
            initial={dlg?.kind === "renameLevel" ? dlg.title : ""}
            loading={renameLevel.isPending}
            onClose={close}
            onSubmit={(title) => dlg?.kind === "renameLevel" && renameLevel.mutate({ id: dlg.id, title }, { onSuccess: close })}
          />
          <ConfirmDialog
            open={dlg?.kind === "deleteLevel"}
            onOpenChange={(o) => !o && close()}
            title={t.courses.deleteLevel}
            description={t.courses.deleteLevelText}
            confirmLabel={t.common.delete}
            cancelLabel={t.common.cancel}
            destructive
            loading={removeLevel.isPending}
            onConfirm={() => dlg?.kind === "deleteLevel" && removeLevel.mutate(dlg.id, { onSuccess: close })}
          />
          <TextDialog
            open={dlg?.kind === "addModule"}
            title={t.courses.addModule}
            label={t.courses.moduleTitle}
            withDescription
            loading={addModule.isPending}
            onClose={close}
            onSubmit={(title, description) =>
              dlg?.kind === "addModule" && addModule.mutate({ levelId: dlg.levelId, title, description }, { onSuccess: close })
            }
          />
          <TextDialog
            open={dlg?.kind === "renameModule"}
            title={t.courses.renameModule}
            label={t.courses.moduleTitle}
            withDescription
            initial={dlg?.kind === "renameModule" ? dlg.title : ""}
            initialDescription={dlg?.kind === "renameModule" ? dlg.description : ""}
            loading={renameModule.isPending}
            onClose={close}
            onSubmit={(title, description) =>
              dlg?.kind === "renameModule" && renameModule.mutate({ id: dlg.id, title, description }, { onSuccess: close })
            }
          />
          <TargetDialog
            open={dlg?.kind === "copyModule"}
            title={t.courses.copyModule}
            hint={t.courses.copyHint}
            options={levels.map((lv) => ({ id: lv.id, label: lv.title }))}
            allowNear
            confirmLabel={t.courses.copyModule}
            loading={copyModule.isPending}
            onClose={close}
            onSubmit={(target) => dlg?.kind === "copyModule" && copyModule.mutate({ id: dlg.id, target }, { onSuccess: close })}
          />
          <ConfirmDialog
            open={dlg?.kind === "deleteModule"}
            onOpenChange={(o) => !o && close()}
            title={t.courses.deleteModule}
            description={t.courses.deleteModuleText}
            confirmLabel={t.common.delete}
            cancelLabel={t.common.cancel}
            destructive
            loading={removeModule.isPending}
            onConfirm={() => dlg?.kind === "deleteModule" && removeModule.mutate(dlg.id, { onSuccess: close })}
          />
          <TargetDialog
            open={dlg?.kind === "copyLesson"}
            title={t.courses.copyLesson}
            hint={t.courses.copyHint}
            options={allModules}
            allowNear
            confirmLabel={t.courses.copyLesson}
            loading={copyLesson.isPending}
            onClose={close}
            onSubmit={(target) => dlg?.kind === "copyLesson" && copyLesson.mutate({ id: dlg.id, target }, { onSuccess: close })}
          />
          <TargetDialog
            open={dlg?.kind === "moveLesson"}
            title={t.courses.moveTitle}
            options={allModules}
            allowNear={false}
            initial={dlg?.kind === "moveLesson" ? String(dlg.moduleId) : ""}
            confirmLabel={t.courses.move}
            loading={moveLesson.isPending}
            onClose={close}
            onSubmit={(target) => dlg?.kind === "moveLesson" && target && moveLesson.mutate({ id: dlg.id, target }, { onSuccess: close })}
          />
          <ConfirmDialog
            open={dlg?.kind === "deleteLesson"}
            onOpenChange={(o) => !o && close()}
            title={t.courses.deleteLesson}
            description={t.courses.deleteLessonText}
            confirmLabel={t.common.delete}
            cancelLabel={t.common.cancel}
            destructive
            loading={removeLesson.isPending}
            onConfirm={() => dlg?.kind === "deleteLesson" && removeLesson.mutate(dlg.id, { onSuccess: close })}
          />
        </>
      )}
    </div>
  );
}
