import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Headphones, Library, Lock, Paperclip, Plus, Settings2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState, Field, PageSkeleton } from "@/components/common";
import { FileDropzone, FileList } from "@/components/common/Files";
import { RecipientPicker } from "@/components/common/RecipientPicker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { flattenSections, useLibraryBase } from "@/pages/library/shared";
import { libraryApi, testsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import {
  CONTENT_TYPES,
  ENGLISH_LEVELS,
  type Attachment,
  type EnglishLevel,
  type LibraryTestDetail,
  type QuestionInput,
  type TestDetail,
} from "@/types/api";

import { QuestionEditor, Toggle, blankQuestion } from "@/components/tests/QuestionEditor";
import { cfgOf, taskConfigFromSaved, taskError } from "@/components/tests/TaskEditors";
import { localInputToIso, toDateTimeInput } from "@/utils/format";

/** A teacher's test or a library test, as the editor reads them. */
type Loaded = Omit<TestDetail, "student_ids" | "has_attempts" | "due_at"> &
  Partial<Pick<TestDetail, "student_ids" | "has_attempts" | "due_at">> &
  Partial<Pick<LibraryTestDetail, "level" | "sections" | "tags" | "published">>;

/** Editor for a teacher's own test, or (library) a shared library test of a methodist / admin. */
export default function TestEditorPage({ library = false }: { library?: boolean }) {
  const { testId } = useParams();
  const editId = testId ? Number(testId) : null;
  const { t } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { base: libBase } = useLibraryBase();
  const testKey = library ? ["library", "test", editId] : ["tests", editId];
  const existing = useQuery({
    queryKey: testKey,
    // both shapes share the editable fields; the extra ones are optional here
    queryFn: async () => (library ? await libraryApi.get(editId!) : await testsApi.get(editId!)) as Loaded,
    enabled: !!editId,
  });
  const sectionsQ = useQuery({ queryKey: ["library", "sections"], queryFn: libraryApi.sections, enabled: library });
  const [level, setLevel] = useState<EnglishLevel | "">("");
  const [sectionIds, setSectionIds] = useState<number[]>([]);
  const [tags, setTags] = useState("");
  const [published, setPublished] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [limit, setLimit] = useState<string>("");
  const [due, setDue] = useState("");
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [questions, setQuestions] = useState<QuestionInput[]>([blankQuestion()]);
  const [availableFrom, setAvailableFrom] = useState("");
  const [passing, setPassing] = useState("");
  const [shuffleQuestions, setShuffleQuestions] = useState(false);
  const [shuffleOptions, setShuffleOptions] = useState(false);
  const [showAnswers, setShowAnswers] = useState(true);
  const [recipients, setRecipients] = useState({ studentIds: [] as number[], groupIds: [] as number[] });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const d = existing.data;
    if (!d) return;
    setTitle(d.title);
    setDescription(d.description ?? "");
    setLimit(d.time_limit_minutes?.toString() ?? "");
    setDue(d.due_at ? toDateTimeInput(new Date(d.due_at)) : "");
    setQuestions(
      d.questions.map((q) => ({
        type: q.type,
        text: q.text,
        options: q.type === "true_false" ? [] : q.options,
        correct_answer: q.correct_answer ?? [],
        points: q.points,
        explanation: q.explanation ?? "",
        attachment_ids: q.attachment_ids,
        config: taskConfigFromSaved(q),
        source: q.source ?? null, // the book it came from: kept on save
      })),
    );
    setAvailableFrom(d.available_from ? toDateTimeInput(new Date(d.available_from)) : "");
    setPassing(d.passing_percent?.toString() ?? "");
    setMaxAttempts(d.max_attempts);
    setShuffleQuestions(d.shuffle_questions);
    setShuffleOptions(d.shuffle_options);
    setShowAnswers(d.show_correct_answers);
    setRecipients({ studentIds: d.student_ids ?? [], groupIds: [] });
    setLevel(d.level ?? "");
    setSectionIds((d.sections ?? []).map((x) => x.id));
    setTags((d.tags ?? []).join(", "));
    setPublished(!!d.published);
  }, [existing.data]);

  const locked = !library && !!existing.data?.has_attempts;
  const files = existing.data?.files ?? [];

  const uploadFiles = (list: File[], onProgress: (p: number) => void) =>
    (library ? libraryApi.uploadFiles(editId!, list, onProgress) : testsApi.uploadFiles(editId!, list, onProgress)).then(() =>
      qc.invalidateQueries({ queryKey: testKey }),
    );
  const removeFile = useMutation({
    mutationFn: (f: Attachment) => (library ? libraryApi.deleteFile(editId!, f.id) : testsApi.deleteFile(editId!, f.id)),
    onSuccess: (_, f) => {
      // questions stop referring to it (the server does the same)
      setQuestions((qs) =>
        qs.map((q) => {
          const c = cfgOf(q);
          const config = q.config && (c.attachment_id === f.id || c.image_id === f.id)
            ? { ...q.config, ...(c.attachment_id === f.id ? { attachment_id: null } : {}), ...(c.image_id === f.id ? { image_id: null } : {}) }
            : q.config;
          return { ...q, config, attachment_ids: (q.attachment_ids ?? []).filter((x) => x !== f.id) };
        }),
      );
      qc.invalidateQueries({ queryKey: testKey });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const save = useMutation({
    mutationFn: async (): Promise<{ id: number }> => {
      const body = {
        title: title.trim(),
        description: description.trim() || null,
        time_limit_minutes: limit ? Number(limit) : null,
        due_at: localInputToIso(due),
        available_from: localInputToIso(availableFrom),
        passing_percent: passing ? Number(passing) : null,
        max_attempts: maxAttempts,
        shuffle_questions: shuffleQuestions,
        shuffle_options: shuffleOptions,
        show_correct_answers: showAnswers,
        questions: questions.map((q) => ({
          ...q,
          text: q.text.trim(),
          explanation: q.explanation?.trim() || null,
          options: q.type === "true_false" ? [{ id: "true", text: "True" }, { id: "false", text: "False" }] : q.options.map((o) => ({ ...o, text: o.text.trim() })),
          correct_answer: q.correct_answer.map((c) => c.trim()).filter(Boolean),
        })),
        student_ids: recipients.studentIds,
        group_ids: recipients.groupIds,
      };
      if (library) {
        const { due_at: _due, student_ids: _s, group_ids: _g, ...rest } = body;
        const lib = {
          ...rest,
          level: level || null,
          section_ids: sectionIds,
          tags: tags.split(",").map((x) => x.trim()).filter(Boolean),
          published,
        };
        return editId ? libraryApi.update(editId, lib) : libraryApi.create(lib);
      }
      return editId ? testsApi.update(editId, body) : testsApi.create(body);
    },
    onSuccess: (test) => {
      qc.invalidateQueries({ queryKey: library ? ["library"] : ["tests"] });
      toast.success(editId ? t.tests.saved : library ? t.library.created : t.tests.created);
      navigate(library ? `${libBase}/tests/${test.id}` : `/teacher/tests/${test.id}`, { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  function validate() {
    const e: Record<string, string> = {};
    if (!title.trim()) e.title = t.common.required;
    if (!questions.length) e.questions = t.tests.minOneQuestion;
    const p = Number(passing);
    if (passing && (!Number.isInteger(p) || p < 1 || p > 100)) e.passing = t.tests.passingRange;
    if (availableFrom && due && availableFrom >= due) e.availableFrom = t.tests.openBeforeDue;
    if (!questions.some((q) => !CONTENT_TYPES.includes(q.type))) e.questions = t.tests.minOneQuestion;
    questions.forEach((q, i) => {
      const block = CONTENT_TYPES.includes(q.type);
      const task = taskError(q, t);
      if (!q.text.trim()) e[`q${i}`] = block ? t.tasks.titleNeeded : t.tests.questionText + ": " + t.common.required.toLowerCase();
      else if (task) e[`q${i}`] = task;
      else if (block || q.type === "fill_gaps" || q.type === "matching") return;
      else if ((q.type === "single_choice" || q.type === "multiple_choice") && q.options.some((o) => !o.text.trim())) e[`q${i}`] = t.tests.fillOptions;
      else if (q.type !== "short_answer" && !q.correct_answer.length) e[`q${i}`] = t.tests.markCorrect;
    });
    setErrors(e);
    if (Object.keys(e).length) {
      toast.error(Object.values(e)[0]);
      return false;
    }
    return true;
  }

  if (editId && existing.isLoading) return <PageSkeleton />;
  if (editId && existing.isError) return <ErrorState onRetry={() => existing.refetch()} />;

  const update = (i: number, q: QuestionInput) => setQuestions((qs) => qs.map((x, j) => (j === i ? q : x)));
  const move = (i: number, dir: -1 | 1) =>
    setQuestions((qs) => {
      const copy = [...qs];
      [copy[i], copy[i + dir]] = [copy[i + dir], copy[i]];
      return copy;
    });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to={library ? (editId ? `${libBase}/tests/${editId}` : libBase) : editId ? `/teacher/tests/${editId}` : "/teacher/tests"}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary"
      >
        <ArrowLeft className="size-4" />
        {library ? t.library.title : t.tests.title}
      </Link>
      <h1 className="page-title">{editId ? t.tests.editTitle : library ? t.library.newTest : t.tests.createTitle}</h1>

      {locked && (
        <div className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning-soft p-3 text-sm text-warning-strong">
          <Lock className="mt-0.5 size-4 shrink-0" />
          {t.tests.lockedQuestions}
        </div>
      )}

      <Card>
        <CardContent className="grid gap-4 pt-5 sm:grid-cols-2 sm:pt-6">
          <Field label={t.tests.name} error={errors.title} className="sm:col-span-2">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} aria-invalid={!!errors.title} />
          </Field>
          <Field label={t.tests.description} optional className="sm:col-span-2">
            <Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label={t.tests.timeLimit} optional>
            <Input type="number" min={1} max={600} placeholder={t.tests.noLimit} value={limit} onChange={(e) => setLimit(e.target.value)} />
          </Field>
          {!library && (
            <Field label={t.tests.dueAt} optional>
              <Input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
            </Field>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="size-4 text-accent" />
            {t.tests.settings}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label={t.tests.availableFrom} hint={t.tests.availableFromHint} error={errors.availableFrom} optional>
            <Input type="datetime-local" value={availableFrom} onChange={(e) => setAvailableFrom(e.target.value)} aria-invalid={!!errors.availableFrom} />
          </Field>
          <Field label={t.tests.passingPercent} hint={t.tests.passingHint} error={errors.passing} optional>
            <Input type="number" min={1} max={100} placeholder="70" value={passing} onChange={(e) => setPassing(e.target.value)} aria-invalid={!!errors.passing} />
          </Field>
          <Field label={t.tests.maxAttempts} hint={t.tests.maxAttemptsHint}>
            <NativeSelect value={maxAttempts} onChange={(e) => setMaxAttempts(Number(e.target.value))}>
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </NativeSelect>
          </Field>
          <div className="grid gap-1 sm:col-span-2">
            <Toggle label={t.tests.shuffleQuestions} hint={t.tests.shuffleQuestionsHint} checked={shuffleQuestions} onChange={setShuffleQuestions} />
            <Toggle label={t.tests.shuffleOptions} hint={t.tests.shuffleOptionsHint} checked={shuffleOptions} onChange={setShuffleOptions} />
            <Toggle label={t.tests.showAnswers} hint={t.tests.showAnswersHint} checked={showAnswers} onChange={setShowAnswers} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Paperclip className="size-4 text-accent" />
            {t.tests.materials}
          </CardTitle>
          <p className="text-sm text-muted-foreground">{t.tests.materialsHint}</p>
        </CardHeader>
        <CardContent className="grid gap-3">
          {!editId ? (
            <p className="rounded-lg bg-secondary px-3 py-2.5 text-sm text-muted-foreground">{t.tests.materialsSaveFirst}</p>
          ) : (
            <>
              <FileList files={files} onRemove={locked ? undefined : (f) => removeFile.mutate(f)} emptyText={t.tests.noMaterials} />
              {!locked && <FileDropzone compact onUpload={uploadFiles} />}
            </>
          )}
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h2 className="text-base font-semibold">{t.tests.questions} · {questions.filter((q) => !CONTENT_TYPES.includes(q.type)).length}</h2>
        {questions.map((q, i) => (
          <QuestionEditor
            key={i}
            q={q}
            index={i}
            number={questions.slice(0, i + 1).filter((x) => !CONTENT_TYPES.includes(x.type)).length}
            total={questions.length}
            locked={locked}
            files={files}
            error={errors[`q${i}`]}
            onChange={(nq) => update(i, nq)}
            onRemove={() => setQuestions((qs) => qs.filter((_, j) => j !== i))}
            onMove={(d) => move(i, d)}
          />
        ))}
        {!locked && (
          <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
            <Button
              variant="outline"
              className="w-full border-dashed"
              onClick={() =>
                setQuestions((qs) => {
                  const last = [...qs].reverse().find((x) => !CONTENT_TYPES.includes(x.type));
                  return [...qs, blankQuestion(last?.type)];
                })
              }
            >
              <Plus />
              {t.tests.addQuestion}
            </Button>
            <Button variant="outline" className="border-dashed" onClick={() => setQuestions((qs) => [...qs, blankQuestion("audio")])}>
              <Headphones />
              {t.tasks.addAudio}
            </Button>
            <Button variant="outline" className="border-dashed" onClick={() => setQuestions((qs) => [...qs, blankQuestion("reading")])}>
              <BookOpen />
              {t.tasks.addReading}
            </Button>
          </div>
        )}
      </div>

      {library ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Library className="size-4 text-accent" />
              {t.library.meta}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field label={t.library.level}>
              <NativeSelect value={level} onChange={(e) => setLevel(e.target.value as EnglishLevel | "")}>
                <option value="">{t.library.noLevel}</option>
                {ENGLISH_LEVELS.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </NativeSelect>
            </Field>
            <Field label={t.library.tags} hint={t.library.tagsHint} optional>
              <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="present simple, routine" />
            </Field>
            <Field label={t.library.sections} hint={t.library.sectionsHint} className="sm:col-span-2">
              <div className="grid max-h-64 gap-0.5 overflow-y-auto rounded-xl border p-2 sm:grid-cols-2">
                {flattenSections(sectionsQ.data ?? []).map((sec) => (
                  <label key={sec.id} style={{ paddingLeft: 6 + sec.depth * 14 }}
                    className={cn("flex cursor-pointer items-center gap-2 rounded-lg py-1 pr-2 text-sm hover:bg-secondary", sec.depth === 0 && "font-medium")}>
                    <Checkbox
                      checked={sectionIds.includes(sec.id)}
                      onCheckedChange={(v) => setSectionIds((ids) => (v ? [...ids, sec.id] : ids.filter((x) => x !== sec.id)))}
                    />
                    <span className="truncate">{sec.name}</span>
                  </label>
                ))}
              </div>
            </Field>
            <div className="sm:col-span-2">
              <Toggle label={t.library.publish} hint={t.library.publishHint} checked={published} onChange={setPublished} />
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader><CardTitle>{t.tests.assign}</CardTitle></CardHeader>
          <CardContent>
            <RecipientPicker
              studentIds={recipients.studentIds}
              groupIds={recipients.groupIds}
              onChange={setRecipients}
              disabledStudentIds={editId ? existing.data?.student_ids : []}
            />
          </CardContent>
        </Card>
      )}

      <div className="sticky bottom-0 -mx-4 flex gap-2 border-t bg-background/90 px-4 py-3 backdrop-blur sm:static sm:mx-0 sm:justify-end sm:border-0 sm:bg-transparent sm:p-0">
        <Button variant="outline" className="flex-1 sm:flex-none" onClick={() => navigate(-1)}>{t.common.cancel}</Button>
        <Button className="flex-1 sm:flex-none" loading={save.isPending} onClick={() => validate() && save.mutate()}>
          {t.common.save}
        </Button>
      </div>
    </div>
  );
}
