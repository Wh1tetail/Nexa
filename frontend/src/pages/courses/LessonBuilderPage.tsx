import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { ArrowDown, ArrowLeft, ArrowUp, Eye, Paperclip, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState, Field, PageSkeleton } from "@/components/common";
import { FileDropzone, FileList } from "@/components/common/Files";
import { Markdown } from "@/components/tests/Markdown";
import { QuestionEditor, SCORED_TYPES, Toggle, blankQuestion } from "@/components/tests/QuestionEditor";
import { blankTask } from "@/components/tests/TaskEditors";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { BLOCK_ICONS, useCoursesBase } from "@/pages/courses/shared";
import { coursesApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import {
  EXERCISE_BLOCKS,
  LESSON_BLOCK_TYPES,
  type Attachment,
  type CourseLessonDetail,
  type LessonBlockContent,
  type LessonBlockType,
  type QuestionInput,
  type QuestionType,
  type VocabularyWord,
} from "@/types/api";

interface Draft {
  key: string;
  id?: number;
  type: LessonBlockType;
  title: string;
  content: LessonBlockContent;
  questions: QuestionInput[];
}

/** Blocks made of exactly one question, and the kinds it may be. */
const SINGLE: Partial<Record<LessonBlockType, QuestionType[]>> = {
  fill_gaps: ["fill_gaps"],
  multiple_choice: ["single_choice", "multiple_choice", "true_false"],
  matching: ["matching"],
};

let seq = 0;
const newKey = () => `n${++seq}`;
const emptyWord = (): VocabularyWord => ({ word: "", translation: "", transcription: "", example: "" });

function blankBlock(type: LessonBlockType): Draft {
  const base = { key: newKey(), type, title: "" };
  switch (type) {
    case "text":
      return { ...base, content: { body: "" }, questions: [] };
    case "grammar":
      return { ...base, content: { body: "", examples: [] }, questions: [] };
    case "vocabulary":
      return { ...base, content: { words: [emptyWord(), emptyWord()] }, questions: [] };
    case "image":
      return { ...base, content: { attachment_id: null, caption: "" }, questions: [] };
    case "audio":
      return { ...base, content: { attachment_id: null, body: "", transcript: "" }, questions: [] };
    case "video":
      return { ...base, content: { url: "", caption: "" }, questions: [] };
    case "reading":
      return { ...base, content: { body: "", image_id: null }, questions: [blankQuestion()] };
    case "listening":
      return { ...base, content: { attachment_id: null, max_plays: null, body: "", transcript: "" }, questions: [blankQuestion()] };
    case "quiz":
      return { ...base, content: { body: "" }, questions: [blankQuestion(), blankQuestion("true_false")] };
    case "fill_gaps":
      return { ...base, content: {}, questions: [blankTask("fill_gaps")!] };
    case "matching":
      return { ...base, content: {}, questions: [blankTask("matching")!] };
    default:
      return { ...base, content: {}, questions: [blankQuestion()] };
  }
}

/** Saved question -> editor input (fill_gaps keeps per-gap points as `gap_points` in the editor). */
function editable(q: QuestionInput): QuestionInput {
  if (q.type !== "fill_gaps") return q;
  const c = (q.config ?? {}) as { gaps?: { points: number }[] } & Record<string, unknown>;
  const { gaps, ...rest } = c;
  return { ...q, config: { ...rest, gap_points: (gaps ?? []).map((g) => g.points) } };
}

function videoUrl(c: LessonBlockContent): string {
  if (c.url !== undefined) return c.url;
  if (c.provider === "youtube" && c.video_id) return `https://youtu.be/${c.video_id}`;
  if (c.provider === "vimeo" && c.video_id) return `https://vimeo.com/${c.video_id}`;
  return "";
}

function toDrafts(d: CourseLessonDetail): Draft[] {
  return d.blocks.map((b) => ({
    key: `b${b.id}`,
    id: b.id,
    type: b.type,
    title: b.title ?? "",
    content: b.type === "video" && !b.content.attachment_id ? { url: videoUrl(b.content), caption: b.content.caption ?? "" } : b.content,
    questions: b.questions.map(editable),
  }));
}

/** What goes to the server: empty vocabulary rows and an unused video source are dropped. */
function toInput(b: Draft) {
  let content: LessonBlockContent = b.content;
  if (b.type === "vocabulary") content = { words: (content.words ?? []).filter((w) => w.word.trim()) };
  if (b.type === "grammar") content = { ...content, examples: (content.examples ?? []).filter((e) => e.trim()) };
  if (b.type === "video")
    content = content.attachment_id !== undefined ? { attachment_id: content.attachment_id, caption: content.caption } : { url: content.url ?? "", caption: content.caption };
  return { id: b.id ?? null, type: b.type, title: b.title.trim() || null, content, questions: b.questions };
}

function FileSelect({
  files,
  kind,
  value,
  placeholder,
  empty,
  onChange,
}: {
  files: Attachment[];
  kind: "image" | "audio" | "video";
  value: number | null | undefined;
  placeholder: string;
  empty: string;
  onChange: (id: number | null) => void;
}) {
  const list = files.filter((f) => f.mime_type.startsWith(`${kind}/`));
  return (
    <div className="grid gap-1">
      <NativeSelect value={value ?? ""} disabled={!list.length} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{placeholder}</option>
        {list.map((f) => (
          <option key={f.id} value={f.id}>{f.original_name}</option>
        ))}
      </NativeSelect>
      {!list.length && <p className="text-xs text-muted-foreground">{empty}</p>}
    </div>
  );
}

function BodyField({ value, onChange, label, rows = 6, optional }: { value: string; onChange: (v: string) => void; label: string; rows?: number; optional?: boolean }) {
  const { t } = useI18n();
  return (
    <>
      <Field label={label} hint={t.courses.bodyHint} optional={optional}>
        <Textarea rows={rows} value={value} maxLength={30000} onChange={(e) => onChange(e.target.value)} />
      </Field>
      {value.trim() && (
        <div className="rounded-xl border bg-secondary/30 p-4">
          <Markdown text={value} />
        </div>
      )}
    </>
  );
}

function QuestionsEditor({ block, files, onChange }: { block: Draft; files: Attachment[]; onChange: (q: QuestionInput[]) => void }) {
  const { t } = useI18n();
  const single = SINGLE[block.type];
  const qs = block.questions;
  const set = (i: number, q: QuestionInput) => onChange(qs.map((x, k) => (k === i ? q : x)));
  const move = (i: number, dir: -1 | 1) => {
    const next = [...qs];
    [next[i], next[i + dir]] = [next[i + dir], next[i]];
    onChange(next);
  };
  return (
    <div className="grid gap-3">
      {!single && <p className="text-sm font-medium text-primary">{t.courses.questions}</p>}
      {qs.map((q, i) => (
        <QuestionEditor
          key={i}
          q={q}
          index={i}
          number={i + 1}
          total={single ? 1 : qs.length}
          locked={false}
          files={files}
          types={single ?? SCORED_TYPES}
          onChange={(nq) => set(i, nq)}
          onRemove={() => (single || qs.length === 1 ? undefined : onChange(qs.filter((_, k) => k !== i)))}
          onMove={(dir) => move(i, dir)}
        />
      ))}
      {!single && qs.length < 30 && (
        <Button variant="soft" size="sm" className="justify-self-start" onClick={() => onChange([...qs, blankQuestion()])}>
          <Plus />
          {t.courses.addQuestion}
        </Button>
      )}
    </div>
  );
}

function BlockFields({ block, files, onChange }: { block: Draft; files: Attachment[]; onChange: (b: Draft) => void }) {
  const { t } = useI18n();
  const c = block.content;
  const set = (patch: Partial<LessonBlockContent>) => onChange({ ...block, content: { ...c, ...patch } });
  const questions = EXERCISE_BLOCKS.includes(block.type) && (
    <QuestionsEditor block={block} files={files} onChange={(questions) => onChange({ ...block, questions })} />
  );

  switch (block.type) {
    case "text":
      return <BodyField label={t.courses.body} value={c.body ?? ""} onChange={(body) => set({ body })} />;
    case "grammar":
      return (
        <>
          <BodyField label={t.courses.rule} value={c.body ?? ""} onChange={(body) => set({ body })} />
          <Field label={t.courses.examples} hint={t.courses.examplesHint} optional>
            <Textarea rows={3} value={(c.examples ?? []).join("\n")} onChange={(e) => set({ examples: e.target.value.split("\n") })} />
          </Field>
        </>
      );
    case "vocabulary": {
      const words = c.words ?? [];
      const setWord = (i: number, patch: Partial<VocabularyWord>) => set({ words: words.map((w, k) => (k === i ? { ...w, ...patch } : w)) });
      return (
        <div className="grid gap-2">
          <p className="text-xs text-muted-foreground">{t.courses.wordsHint}</p>
          {words.map((w, i) => (
            <div key={i} className="grid gap-2 rounded-xl border p-2 sm:grid-cols-[1fr_1fr_0.8fr_1.4fr_auto] sm:border-0 sm:p-0">
              <Input value={w.word} maxLength={200} placeholder={t.courses.word} aria-label={t.courses.word} onChange={(e) => setWord(i, { word: e.target.value })} />
              <Input value={w.translation ?? ""} maxLength={300} placeholder={t.courses.translation} aria-label={t.courses.translation} onChange={(e) => setWord(i, { translation: e.target.value })} />
              <Input value={w.transcription ?? ""} maxLength={100} placeholder={t.courses.transcription} aria-label={t.courses.transcription} onChange={(e) => setWord(i, { transcription: e.target.value })} />
              <Input value={w.example ?? ""} maxLength={500} placeholder={t.courses.example} aria-label={t.courses.example} onChange={(e) => setWord(i, { example: e.target.value })} />
              <Button variant="ghost" size="icon" className="justify-self-end" aria-label={t.common.delete} onClick={() => set({ words: words.filter((_, k) => k !== i) })}>
                <X />
              </Button>
            </div>
          ))}
          {words.length < 200 && (
            <Button variant="soft" size="sm" className="justify-self-start" onClick={() => set({ words: [...words, emptyWord()] })}>
              <Plus />{t.courses.addWord}
            </Button>
          )}
        </div>
      );
    }
    case "image":
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t.courses.image}>
            <FileSelect files={files} kind="image" value={c.attachment_id} placeholder={t.courses.chooseImage} empty={t.courses.noImages} onChange={(attachment_id) => set({ attachment_id })} />
          </Field>
          <Field label={t.courses.caption} optional>
            <Input value={c.caption ?? ""} maxLength={500} onChange={(e) => set({ caption: e.target.value })} />
          </Field>
        </div>
      );
    case "audio":
    case "listening":
      return (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t.tasks.audioFile}>
              <FileSelect files={files} kind="audio" value={c.attachment_id} placeholder={t.tasks.chooseAudio} empty={t.tasks.noAudioFiles} onChange={(attachment_id) => set({ attachment_id })} />
            </Field>
            {block.type === "listening" && (
              <Field label={t.tasks.maxPlays}>
                <NativeSelect value={c.max_plays ?? ""} onChange={(e) => set({ max_plays: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">{t.tasks.unlimited}</option>
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </NativeSelect>
              </Field>
            )}
          </div>
          <Field label={t.tasks.instructions} optional>
            <Textarea rows={2} value={c.body ?? ""} maxLength={5000} onChange={(e) => set({ body: e.target.value })} />
          </Field>
          <Field label={t.courses.transcript} hint={t.courses.transcriptHint} optional>
            <Textarea rows={3} value={c.transcript ?? ""} maxLength={20000} onChange={(e) => set({ transcript: e.target.value })} />
          </Field>
          {questions}
        </>
      );
    case "video": {
      const byFile = c.attachment_id !== undefined;
      return (
        <>
          <div className="inline-flex w-fit rounded-xl bg-secondary p-1 text-sm">
            {[false, true].map((file) => (
              <button
                key={String(file)}
                type="button"
                aria-pressed={byFile === file}
                onClick={() => set(file ? { attachment_id: c.attachment_id ?? null, url: undefined } : { url: videoUrl(c), attachment_id: undefined })}
                className={cn("rounded-lg px-3 py-1.5 font-medium transition-colors", byFile === file ? "bg-background text-primary shadow-sm" : "text-muted-foreground hover:text-primary")}
              >
                {file ? t.courses.videoFile : t.courses.videoLink}
              </button>
            ))}
          </div>
          {byFile ? (
            <FileSelect files={files} kind="video" value={c.attachment_id} placeholder={t.courses.chooseVideo} empty={t.courses.noVideos} onChange={(attachment_id) => set({ attachment_id })} />
          ) : (
            <Input value={c.url ?? ""} maxLength={500} placeholder="https://www.youtube.com/watch?v=…" aria-label={t.courses.videoLink} onChange={(e) => set({ url: e.target.value })} />
          )}
          <Field label={t.courses.caption} optional>
            <Input value={c.caption ?? ""} maxLength={500} onChange={(e) => set({ caption: e.target.value })} />
          </Field>
        </>
      );
    }
    case "reading":
      return (
        <>
          <BodyField label={t.tasks.readingText} rows={8} value={c.body ?? ""} onChange={(body) => set({ body })} />
          <Field label={t.tasks.readingImage} optional>
            <FileSelect files={files} kind="image" value={c.image_id} placeholder={t.tasks.noImage} empty={t.courses.noImages} onChange={(image_id) => set({ image_id })} />
          </Field>
          {questions}
        </>
      );
    default:
      return (
        <>
          <Field label={t.tasks.instructions} optional>
            <Textarea rows={2} value={c.body ?? ""} maxLength={5000} onChange={(e) => set({ body: e.target.value })} />
          </Field>
          {questions}
        </>
      );
  }
}

function BlockCard({
  block,
  index,
  total,
  files,
  error,
  onChange,
  onMove,
  onRemove,
}: {
  block: Draft;
  index: number;
  total: number;
  files: Attachment[];
  error: boolean;
  onChange: (b: Draft) => void;
  onMove: (dir: -1 | 1) => void;
  onRemove: () => void;
}) {
  const { t } = useI18n();
  const Icon = BLOCK_ICONS[block.type];
  return (
    <Card id={`block-${block.key}`} className={cn("scroll-mt-20 p-4 sm:p-5", error && "border-danger/60")}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex h-9 items-center gap-2 rounded-lg bg-accent-soft px-3 text-sm font-medium text-accent">
          <Icon className="size-4" />
          {t.courses.block[block.type]}
        </span>
        <div className="ml-auto flex gap-1">
          <Button variant="ghost" size="icon-sm" disabled={index === 0} onClick={() => onMove(-1)} aria-label={t.courses.moveUp}><ArrowUp /></Button>
          <Button variant="ghost" size="icon-sm" disabled={index === total - 1} onClick={() => onMove(1)} aria-label={t.courses.moveDown}><ArrowDown /></Button>
          <Button variant="ghost" size="icon-sm" onClick={onRemove} className="hover:text-danger" aria-label={t.common.delete}><Trash2 /></Button>
        </div>
      </div>
      <div className="mt-3 grid gap-3">
        <Field label={t.courses.blockTitle} optional>
          <Input value={block.title} maxLength={200} onChange={(e) => onChange({ ...block, title: e.target.value })} />
        </Field>
        <BlockFields block={block} files={files} onChange={onChange} />
      </div>
    </Card>
  );
}

export default function LessonBuilderPage() {
  const { lessonId } = useParams();
  const id = Number(lessonId);
  const { t } = useI18n();
  const { base } = useCoursesBase();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["courses", "lesson", id], queryFn: () => coursesApi.lesson(id) });

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [duration, setDuration] = useState("");
  const [published, setPublished] = useState(false);
  const [blocks, setBlocks] = useState<Draft[]>([]);
  const [dirty, setDirty] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const loadedFor = useRef<number | null>(null);

  const load = (d: CourseLessonDetail) => {
    setTitle(d.title);
    setDescription(d.description ?? "");
    setDuration(d.duration_minutes ? String(d.duration_minutes) : "");
    setPublished(d.published);
    setBlocks(toDrafts(d));
    setDirty(false);
    setErrorKey(null);
  };
  // content is loaded once per lesson; later refetches (files) must not wipe unsaved edits
  useEffect(() => {
    if (q.data && loadedFor.current !== q.data.id) {
      loadedFor.current = q.data.id;
      load(q.data);
    }
  }, [q.data]);

  useEffect(() => {
    if (!dirty) return;
    const h = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);

  const touch = <A,>(fn: (a: A) => void) => (a: A) => {
    fn(a);
    setDirty(true);
  };
  const setBlock = (key: string, b: Draft) => {
    setBlocks((xs) => xs.map((x) => (x.key === key ? b : x)));
    setDirty(true);
  };
  const moveBlock = (i: number, dir: -1 | 1) => {
    setBlocks((xs) => {
      const next = [...xs];
      [next[i], next[i + dir]] = [next[i + dir], next[i]];
      return next;
    });
    setDirty(true);
  };
  const addBlock = (type: LessonBlockType) => {
    const b = blankBlock(type);
    setBlocks((xs) => [...xs, b]);
    setDirty(true);
    setTimeout(() => document.getElementById(`block-${b.key}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };

  const save = useMutation({
    mutationFn: () =>
      coursesApi.saveLesson(id, {
        title: title.trim(),
        description: description.trim() || null,
        duration_minutes: duration ? Number(duration) : null,
        published,
        blocks: blocks.map(toInput),
      }),
    onSuccess: (d) => {
      qc.setQueryData(["courses", "lesson", id], d);
      qc.invalidateQueries({ queryKey: ["courses"] });
      load(d);
      toast.success(t.courses.saved);
    },
    onError: (e) => {
      const field = axios.isAxiosError(e) ? (e.response?.data as { field?: string } | undefined)?.field : undefined;
      const m = field?.match(/^blocks\.(\d+)/);
      const bad = m ? blocks[Number(m[1])] : undefined;
      // say which block the problem is in
      toast.error(bad ? `${Number(m![1]) + 1}. ${t.courses.block[bad.type]}: ${errorMessage(e)}` : errorMessage(e));
      setErrorKey(bad?.key ?? null);
      if (bad) document.getElementById(`block-${bad.key}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
  });

  const refreshFiles = () => qc.invalidateQueries({ queryKey: ["courses", "lesson", id] });
  const removeFile = useMutation({
    mutationFn: (f: Attachment) => coursesApi.deleteFile(id, f.id),
    onSuccess: (_, f) => {
      // the server already cleared saved references; clear them in the unsaved draft too
      setBlocks((xs) =>
        xs.map((b) => {
          const c = { ...b.content };
          if (c.attachment_id === f.id) c.attachment_id = null;
          if (c.image_id === f.id) c.image_id = null;
          return { ...b, content: c, questions: b.questions.map((qq) => ({ ...qq, attachment_ids: (qq.attachment_ids ?? []).filter((x) => x !== f.id) })) };
        }),
      );
      refreshFiles();
      toast.success(t.common.deleted);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  // until the lesson is in the form (avoids a frame of empty fields)
  if (!q.data || loadedFor.current !== q.data.id) return <PageSkeleton />;
  const d = q.data;
  const files = d.files;

  const preview = () => {
    if (!dirty) return navigate(`${base}/lessons/${id}`);
    save.mutate(undefined, { onSuccess: () => navigate(`${base}/lessons/${id}`) });
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link to={`${base}/${d.path.course_id}`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {d.path.course_title}
      </Link>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {d.path.level_title} · {d.path.module_title}
          </p>
          <h1 className="page-title">{t.courses.builder}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={preview} disabled={save.isPending}><Eye />{t.courses.preview}</Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!title.trim()}><Save />{t.common.save}</Button>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle>{t.courses.lessonSettings}</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-[1fr_180px]">
          <Field label={t.courses.lessonTitle}>
            <Input value={title} maxLength={200} onChange={(e) => touch(setTitle)(e.target.value)} />
          </Field>
          <Field label={t.courses.duration} optional>
            <Input type="number" min={1} max={600} value={duration} onChange={(e) => touch(setDuration)(e.target.value)} />
          </Field>
          <Field label={t.courses.description} optional className="sm:col-span-2">
            <Textarea rows={2} value={description} maxLength={5000} onChange={(e) => touch(setDescription)(e.target.value)} />
          </Field>
          <div className="sm:col-span-2">
            <Toggle label={t.courses.publishLesson} hint={t.courses.publishLessonHint} checked={published} onChange={touch(setPublished)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Paperclip className="size-4 text-accent" />{t.courses.materials}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <FileDropzone
            compact
            extraTypes={["mp4", "webm"]}
            hint={t.courses.materialsHint}
            onUpload={(list, onProgress) => coursesApi.uploadFiles(id, list, onProgress).then(refreshFiles)}
          />
          <FileList files={files} onRemove={(f) => removeFile.mutate(f)} />
        </CardContent>
      </Card>

      {blocks.length ? (
        blocks.map((b, i) => (
          <BlockCard
            key={b.key}
            block={b}
            index={i}
            total={blocks.length}
            files={files}
            error={errorKey === b.key}
            onChange={(nb) => setBlock(b.key, nb)}
            onMove={(dir) => moveBlock(i, dir)}
            onRemove={() => {
              setBlocks((xs) => xs.filter((x) => x.key !== b.key));
              setDirty(true);
            }}
          />
        ))
      ) : (
        <p className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">{t.courses.noBlocks}</p>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold text-primary">{t.courses.addBlock}</h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {LESSON_BLOCK_TYPES.map((type) => {
            const Icon = BLOCK_ICONS[type];
            return (
              <button
                key={type}
                type="button"
                onClick={() => addBlock(type)}
                className="flex min-w-0 items-start gap-2.5 rounded-xl border bg-card p-3 text-left transition-colors hover:border-accent/50 hover:bg-accent-soft/40"
              >
                <Icon className="mt-0.5 size-4 shrink-0 text-accent" />
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-primary">{t.courses.block[type]}</span>
                  <span className="block text-xs text-muted-foreground">{t.courses.blockHint[type]}</span>
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {dirty && (
        <div className="sticky bottom-4 z-30 flex items-center justify-between gap-3 rounded-xl border bg-background/95 px-4 py-3 shadow-lift backdrop-blur">
          <span className="text-sm text-muted-foreground">{t.courses.unsaved}</span>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!title.trim()}><Save />{t.common.save}</Button>
        </div>
      )}
    </div>
  );
}
