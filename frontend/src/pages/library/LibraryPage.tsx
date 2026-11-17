import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpenCheck,
  Copy,
  FolderPlus,
  FolderTree,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Tag,
  Timer,
  Trash2,
  X,
} from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { CardListSkeleton, EmptyState, ErrorState, Field, PageHeader } from "@/components/common";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input, NativeSelect } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { flattenSections, useCopyToMine, useLibraryBase } from "@/pages/library/shared";
import { libraryApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { ENGLISH_LEVELS, type EnglishLevel, type LibraryItem, type LibrarySection, type QuestionType } from "@/types/api";

const TASK_TYPES: QuestionType[] = [
  "single_choice", "multiple_choice", "true_false", "short_answer", "fill_gaps", "matching", "audio", "reading",
];

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["library"] });
}

// ---------- sections ----------

function SectionDialog({
  state,
  onClose,
}: {
  state: { mode: "create"; parent: LibrarySection | null } | { mode: "rename"; section: LibrarySection } | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const [name, setName] = useState("");
  useEffect(() => setName(state?.mode === "rename" ? state.section.name : ""), [state]);
  const save = useMutation({
    mutationFn: () =>
      state!.mode === "rename"
        ? libraryApi.updateSection(state!.section.id, { name: name.trim() })
        : libraryApi.createSection(name.trim(), state!.mode === "create" ? state!.parent?.id ?? null : null),
    onSuccess: () => {
      invalidate();
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const title =
    state?.mode === "rename" ? t.library.renameSection : state?.parent ? `${t.library.addSubsection} · ${state.parent.name}` : t.library.addSection;
  return (
    <Dialog open={!!state} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <DialogBody>
          <Field label={t.library.sectionName}>
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus
              onKeyDown={(e) => e.key === "Enter" && name.trim() && save.mutate()} />
          </Field>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button loading={save.isPending} disabled={!name.trim()} onClick={() => save.mutate()}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SectionTree({
  sections,
  selected,
  onSelect,
  editor,
}: {
  sections: LibrarySection[];
  selected: number | "";
  onSelect: (id: number | "") => void;
  editor: boolean;
}) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const [dialog, setDialog] = useState<Parameters<typeof SectionDialog>[0]["state"]>(null);
  const [deleting, setDeleting] = useState<LibrarySection | null>(null);
  const remove = useMutation({
    mutationFn: (id: number) => libraryApi.removeSection(id),
    onSuccess: (_, id) => {
      if (selected === id) onSelect("");
      setDeleting(null);
      invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const flat = flattenSections(sections);
  const total = sections.filter((s) => s.parent_id === null).reduce((n, s) => n + s.tests_count, 0);
  return (
    <Card className="p-2">
      <div className="flex items-center justify-between px-2 py-1.5">
        <p className="flex items-center gap-2 text-sm font-semibold text-primary">
          <FolderTree className="size-4 text-accent" />
          {t.library.sections}
        </p>
        {editor && (
          <Button size="icon-sm" variant="ghost" aria-label={t.library.addSection} title={t.library.addSection}
            onClick={() => setDialog({ mode: "create", parent: null })}>
            <FolderPlus />
          </Button>
        )}
      </div>
      <ul className="grid gap-0.5">
        <li>
          <button
            onClick={() => onSelect("")}
            className={cn("flex w-full items-center rounded-lg px-2 py-1.5 text-left text-sm transition-colors",
              selected === "" ? "bg-accent-soft font-medium text-accent" : "text-muted-foreground hover:bg-secondary")}
          >
            <span className="flex-1">{t.library.allSections}</span>
            <span className="tabular text-xs opacity-70">{total}</span>
          </button>
        </li>
        {flat.map((s) => (
          <li key={s.id} className="group flex items-center">
            <button
              onClick={() => onSelect(s.id)}
              style={{ paddingLeft: 8 + s.depth * 14 }}
              className={cn("flex min-w-0 flex-1 items-center gap-2 rounded-lg py-1.5 pr-2 text-left text-sm transition-colors",
                selected === s.id ? "bg-accent-soft font-medium text-accent" : "text-primary hover:bg-secondary",
                s.depth === 0 && "font-medium")}
            >
              <span className="min-w-0 flex-1 truncate">{s.name}</span>
              <span className="tabular text-xs text-muted-foreground">{s.tests_count}</span>
            </button>
            {editor && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="icon-sm" variant="ghost" className="shrink-0 opacity-60 group-hover:opacity-100" aria-label={t.common.actions}>
                    <MoreHorizontal />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => setDialog({ mode: "create", parent: s })}><FolderPlus />{t.library.addSubsection}</DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => setDialog({ mode: "rename", section: s })}><Pencil />{t.library.renameSection}</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem destructive onSelect={() => setDeleting(s)}><Trash2 />{t.library.deleteSection}</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </li>
        ))}
      </ul>
      <SectionDialog state={dialog} onClose={() => setDialog(null)} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`${t.library.deleteSection} «${deleting?.name}»?`}
        description={t.library.deleteSectionText}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
      />
    </Card>
  );
}

// ---------- tests ----------

function TestCard({
  item,
  editor,
  base,
  selected,
  onSelect,
  onDelete,
}: {
  item: LibraryItem;
  editor: boolean;
  base: string;
  selected: boolean;
  onSelect: (v: boolean) => void;
  onDelete: () => void;
}) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const navigate = useNavigate();
  const copy = useCopyToMine();
  const duplicate = useMutation({
    mutationFn: () => libraryApi.duplicate(item.id),
    onSuccess: (d) => {
      invalidate();
      toast.success(t.library.duplicated);
      navigate(`${base}/tests/${d.id}/edit`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const kinds = item.question_types.filter((q) => !["single_choice", "multiple_choice", "true_false", "short_answer"].includes(q));
  return (
    <Card className={cn("flex gap-3 p-4 transition-colors sm:p-5", selected && "border-accent/60 bg-accent-soft/30")}>
      {editor && <Checkbox checked={selected} onCheckedChange={(v) => onSelect(v === true)} className="mt-1" aria-label={item.title} />}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          {item.level && <Badge variant="neutral">{item.level}</Badge>}
          {editor && !item.published && <Badge variant="warning">{t.library.draft}</Badge>}
          {kinds.map((k) => (
            <Badge key={k} variant="default">{t.status.questionType[k]}</Badge>
          ))}
        </div>
        <Link to={`${base}/tests/${item.id}`} className="mt-2 block font-semibold text-primary hover:text-accent">
          {item.title}
        </Link>
        {item.description && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{item.description}</p>}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1"><BookOpenCheck className="size-3.5" />{t.common.questions(item.questions_count)}</span>
          {item.time_limit_minutes && <span className="inline-flex items-center gap-1"><Timer className="size-3.5" />{t.common.minutes(item.time_limit_minutes)}</span>}
          {item.sections.length > 0 && <span className="inline-flex items-center gap-1"><FolderTree className="size-3.5" />{item.sections.map((s) => s.name).join(", ")}</span>}
          {item.author_name && <span>{t.library.author}: {item.author_name}</span>}
          {editor && item.copies > 0 && <span>{t.library.copies(item.copies)}</span>}
        </div>
        {item.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {item.tags.map((g) => (
              <span key={g} className="inline-flex items-center gap-1 rounded-md bg-secondary px-1.5 py-0.5 text-[11px] text-muted-foreground">
                <Tag className="size-3" />{g}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-2">
        {editor ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon-sm" variant="ghost" aria-label={t.common.actions}><MoreHorizontal /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => navigate(`${base}/tests/${item.id}/edit`)}><Pencil />{t.common.edit}</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => duplicate.mutate()}><Copy />{t.library.duplicate}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={onDelete}><Trash2 />{t.common.delete}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Button size="sm" variant="outline" loading={copy.isPending} onClick={() => copy.mutate(item.id)}>
            <Copy />
            <span className="hidden sm:inline">{t.library.copyToMine}</span>
          </Button>
        )}
      </div>
    </Card>
  );
}

function MoveDialog({
  ids,
  sections,
  fromSection,
  onClose,
}: {
  ids: number[] | null;
  sections: LibrarySection[];
  fromSection: LibrarySection | null;
  onClose: (done: boolean) => void;
}) {
  const { t } = useI18n();
  const invalidate = useInvalidate();
  const [target, setTarget] = useState("");
  const [leave, setLeave] = useState(false);
  useEffect(() => {
    setTarget("");
    setLeave(false);
  }, [ids]);
  const move = useMutation({
    mutationFn: () => libraryApi.move(ids!, Number(target), leave && fromSection ? fromSection.id : undefined),
    onSuccess: () => {
      invalidate();
      toast.success(t.library.moved);
      onClose(true);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={!!ids} onOpenChange={(o) => !o && onClose(false)}>
      <DialogContent size="sm">
        <DialogHeader><DialogTitle>{t.library.moveTitle(ids?.length ?? 0)}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-3">
          <NativeSelect value={target} onChange={(e) => setTarget(e.target.value)} aria-label={t.library.move}>
            <option value="">{t.library.move}…</option>
            {flattenSections(sections).map((s) => (
              <option key={s.id} value={s.id}>{"  ".repeat(s.depth)}{s.name}</option>
            ))}
          </NativeSelect>
          {fromSection && (
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <Checkbox checked={leave} onCheckedChange={(v) => setLeave(v === true)} />
              {t.library.moveFrom(fromSection.name)}
            </label>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onClose(false)}>{t.common.cancel}</Button>
          <Button disabled={!target || Number(target) === fromSection?.id} loading={move.isPending} onClick={() => move.mutate()}>{t.library.move}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function LibraryPage() {
  const { t } = useI18n();
  const { base, editor } = useLibraryBase();
  const invalidate = useInvalidate();
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState<EnglishLevel | "">("");
  const [sectionId, setSectionId] = useState<number | "">("");
  const [questionType, setQuestionType] = useState<QuestionType | "">("");
  const [authorId, setAuthorId] = useState<number | "">("");
  const [tag, setTag] = useState("");
  const [status, setStatus] = useState<"" | "published" | "draft">("");
  const [selected, setSelected] = useState<number[]>([]);
  const [moving, setMoving] = useState<number[] | null>(null);
  const [deleting, setDeleting] = useState<LibraryItem | null>(null);
  const q = useDeferredValue(search);

  const filters = {
    search: q, level, section_id: sectionId, question_type: questionType, author_id: authorId, tag,
    published: status === "" ? ("" as const) : status === "published",
  };
  const sections = useQuery({ queryKey: ["library", "sections"], queryFn: libraryApi.sections });
  const tags = useQuery({ queryKey: ["library", "tags"], queryFn: libraryApi.tags });
  const tests = useQuery({ queryKey: ["library", "tests", filters], queryFn: () => libraryApi.tests(filters), placeholderData: (p) => p });
  // authors come from an unfiltered list, so choosing one does not hide the others
  const all = useQuery({ queryKey: ["library", "tests", "all"], queryFn: () => libraryApi.tests() });
  const authors = [...new Map((all.data ?? []).filter((i) => i.author_id).map((i) => [i.author_id!, i.author_name ?? "—"])).entries()];
  const currentSection = sections.data?.find((s) => s.id === sectionId) ?? null;
  const hasFilters = !!(search || level || sectionId || questionType || authorId || tag || status);

  const remove = useMutation({
    mutationFn: (id: number) => libraryApi.remove(id),
    onSuccess: () => {
      invalidate();
      setDeleting(null);
      toast.success(t.common.deleted);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div>
      <PageHeader
        title={t.library.title}
        subtitle={editor ? t.library.editorSubtitle : t.library.subtitle}
        actions={
          editor && (
            <Button asChild>
              <Link to={`${base}/tests/new`}><Plus />{t.library.newTest}</Link>
            </Button>
          )
        }
      />
      <div className="grid gap-4 lg:grid-cols-[260px_1fr] lg:items-start">
        <div className="hidden lg:sticky lg:top-20 lg:block">
          {sections.data && <SectionTree sections={sections.data} selected={sectionId} onSelect={setSectionId} editor={editor} />}
        </div>
        <div className="grid min-w-0 gap-3">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-[1fr_auto_auto_auto]">
            <div className="relative sm:col-span-2 xl:col-span-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t.library.search} className="pl-9" />
            </div>
            {/* phones: sections as a list */}
            <NativeSelect value={sectionId} onChange={(e) => setSectionId(e.target.value ? Number(e.target.value) : "")} className="lg:hidden" aria-label={t.library.sections}>
              <option value="">{t.library.allSections}</option>
              {flattenSections(sections.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>{"  ".repeat(s.depth)}{s.name} ({s.tests_count})</option>
              ))}
            </NativeSelect>
            <NativeSelect value={level} onChange={(e) => setLevel(e.target.value as EnglishLevel | "")} className="xl:w-32" aria-label={t.library.level}>
              <option value="">{t.library.allLevels}</option>
              {ENGLISH_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </NativeSelect>
            <NativeSelect value={questionType} onChange={(e) => setQuestionType(e.target.value as QuestionType | "")} className="xl:w-48" aria-label={t.library.allTypes}>
              <option value="">{t.library.allTypes}</option>
              {TASK_TYPES.map((k) => <option key={k} value={k}>{t.status.questionType[k]}</option>)}
            </NativeSelect>
            <NativeSelect value={authorId} onChange={(e) => setAuthorId(e.target.value ? Number(e.target.value) : "")} className="xl:w-44" aria-label={t.library.author}>
              <option value="">{t.library.allAuthors}</option>
              {authors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            </NativeSelect>
            {editor && (
              <NativeSelect value={status} onChange={(e) => setStatus(e.target.value as typeof status)} className="xl:w-40" aria-label={t.library.drafts}>
                <option value="">{t.library.allStatuses}</option>
                <option value="published">{t.library.published}</option>
                <option value="draft">{t.library.drafts}</option>
              </NativeSelect>
            )}
          </div>
          {(tags.data?.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-1.5" aria-label={t.library.tags}>
              {tags.data!.map((g) => (
                <button key={g.id} onClick={() => setTag((v) => (v === g.name ? "" : g.name))} aria-pressed={tag === g.name}
                  className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors",
                    tag === g.name ? "border-accent bg-accent-soft text-accent" : "text-muted-foreground hover:bg-secondary")}>
                  <Tag className="size-3" />{g.name}<span className="tabular opacity-60">{g.tests_count}</span>
                </button>
              ))}
            </div>
          )}

          {editor && selected.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-accent/30 bg-accent-soft/40 px-3 py-2 text-sm">
              <span className="font-medium text-primary">{t.library.selected(selected.length)}</span>
              <Button size="sm" onClick={() => setMoving(selected)}><FolderTree />{t.library.move}</Button>
              <Button size="sm" variant="ghost" onClick={() => setSelected([])}><X />{t.library.clearSelection}</Button>
            </div>
          )}

          {tests.isLoading ? (
            <CardListSkeleton rows={4} />
          ) : tests.isError ? (
            <ErrorState onRetry={() => tests.refetch()} />
          ) : !tests.data?.length ? (
            <Card>
              <EmptyState icon={BookOpenCheck} title={t.library.empty} text={t.library.emptyHint}
                action={hasFilters ? (
                  <Button variant="outline" onClick={() => { setSearch(""); setLevel(""); setSectionId(""); setQuestionType(""); setAuthorId(""); setTag(""); setStatus(""); }}>
                    {t.common.resetFilters}
                  </Button>
                ) : undefined} />
            </Card>
          ) : (
            tests.data.map((i) => (
              <TestCard key={i.id} item={i} editor={editor} base={base}
                selected={selected.includes(i.id)}
                onSelect={(v) => setSelected((s) => (v ? [...s, i.id] : s.filter((x) => x !== i.id)))}
                onDelete={() => setDeleting(i)} />
            ))
          )}
        </div>
      </div>

      <MoveDialog ids={moving} sections={sections.data ?? []} fromSection={currentSection}
        onClose={(done) => { setMoving(null); if (done) setSelected([]); }} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t.library.deleteTitle}
        description={`«${deleting?.title}». ${t.library.deleteText}`}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
      />
    </div>
  );
}
