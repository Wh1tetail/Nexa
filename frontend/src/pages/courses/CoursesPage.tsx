import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Layers, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { CardListSkeleton, EmptyState, ErrorState, Field, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { useCoursesBase } from "@/pages/courses/shared";
import { coursesApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { ENGLISH_LEVELS, type CourseItem, type EnglishLevel } from "@/types/api";

function CreateCourseDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { base } = useCoursesBase();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [levels, setLevels] = useState<EnglishLevel[]>(["A1"]);
  const create = useMutation({
    mutationFn: () => coursesApi.create({ title, description: description || null, levels }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["courses"] });
      toast.success(t.courses.created);
      onClose();
      navigate(`${base}/${c.id}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader><DialogTitle>{t.courses.newCourse}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4">
          <Field label={t.courses.courseTitle}>
            <Input value={title} maxLength={200} autoFocus placeholder="General English" onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label={t.courses.description} optional>
            <Textarea rows={3} value={description} maxLength={5000} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label={t.courses.levels} hint={t.courses.levelsHint}>
            <div className="flex flex-wrap gap-2">
              {ENGLISH_LEVELS.map((l) => (
                <label key={l} className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border px-3 text-sm hover:bg-secondary">
                  <Checkbox
                    checked={levels.includes(l)}
                    onCheckedChange={(v) => setLevels((x) => (v ? [...x, l] : x.filter((y) => y !== l)))}
                  />
                  {l}
                </label>
              ))}
            </div>
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={!title.trim()} loading={create.isPending} onClick={() => create.mutate()}>{t.common.create}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CourseCard({ c }: { c: CourseItem }) {
  const { t } = useI18n();
  const { base, editor } = useCoursesBase();
  return (
    <Link to={`${base}/${c.id}`} className="group block focus-visible:outline-none">
      <Card className="flex h-full flex-col p-5 transition-all group-hover:-translate-y-0.5 group-hover:shadow-lift group-focus-visible:ring-2 group-focus-visible:ring-ring">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <GraduationCap className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="break-words text-base font-semibold text-primary">{c.title}</h3>
            {c.author_name && <p className="text-xs text-muted-foreground">{t.courses.author}: {c.author_name}</p>}
          </div>
          {editor && <Badge variant={c.published ? "success" : "warning"}>{c.published ? t.courses.published : t.courses.draft}</Badge>}
        </div>
        {c.description && <p className="mt-3 line-clamp-3 text-sm text-muted-foreground">{c.description}</p>}
        <div className="mt-auto pt-4">
          {c.level_codes.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1">
              {c.level_codes.map((l) => (
                <Badge key={l} variant="neutral">{l}</Badge>
              ))}
            </div>
          )}
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1"><Layers className="size-3.5" />{t.courses.modulesCount(c.modules_count)}</span>
            <span>{t.courses.lessonsCount(c.lessons_count)}</span>
            {editor && c.draft_lessons_count > 0 && <span>{t.courses.draftsCount(c.draft_lessons_count)}</span>}
          </p>
        </div>
      </Card>
    </Link>
  );
}

export default function CoursesPage() {
  const { t } = useI18n();
  const { editor } = useCoursesBase();
  const [creating, setCreating] = useState(false);
  const q = useQuery({ queryKey: ["courses"], queryFn: coursesApi.list });

  return (
    <div>
      <PageHeader
        title={t.courses.title}
        subtitle={editor ? t.courses.editorSubtitle : t.courses.subtitle}
        actions={editor && <Button onClick={() => setCreating(true)}><Plus />{t.courses.newCourse}</Button>}
      />
      {q.isLoading ? (
        <CardListSkeleton rows={3} />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data?.length ? (
        <Card>
          <EmptyState
            icon={GraduationCap}
            title={t.courses.empty}
            text={editor ? t.courses.emptyEditor : t.courses.emptyTeacher}
            action={editor && <Button onClick={() => setCreating(true)}><Plus />{t.courses.newCourse}</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {q.data.map((c) => (
            <CourseCard key={c.id} c={c} />
          ))}
        </div>
      )}
      {editor && <CreateCourseDialog open={creating} onClose={() => setCreating(false)} />}
    </div>
  );
}
