import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowLeft, ArrowUp, BookOpen, Headphones, Lock, Paperclip, Plus, Settings2, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ErrorState, Field, PageSkeleton } from "@/components/common";
import { FileDropzone, FileList } from "@/components/common/Files";
import { RecipientPicker } from "@/components/common/RecipientPicker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox, RadioGroup, RadioGroupItem } from "@/components/ui/checkbox";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { testsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { CONTENT_TYPES, type Attachment, type QuestionInput, type QuestionType } from "@/types/api";
import { BlockEditor, GapsEditor, MatchingEditor, blankTask, cfgOf, taskConfigFromSaved, taskError } from "@/components/tests/TaskEditors";
import { localInputToIso, toDateTimeInput } from "@/utils/format";

const LETTERS = "abcdefghijklmnopqrstuvwxyz";

function blankQuestion(type: QuestionType = "single_choice"): QuestionInput {
  const task = blankTask(type);
  if (task) return task;
  if (type === "true_false") return { type, text: "", options: [], correct_answer: ["true"], points: 1 };
  if (type === "short_answer") return { type, text: "", options: [], correct_answer: [], points: 1 };
  return {
    type,
    text: "",
    options: [
      { id: "a", text: "" },
      { id: "b", text: "" },
    ],
    correct_answer: [],
    points: 1,
  };
}

function QuestionEditor({
  q,
  index,
  number,
  total,
  locked,
  onChange,
  onRemove,
  onMove,
  error,
  files,
}: {
  q: QuestionInput;
  index: number;
  /** number among real questions (blocks have none) */
  number: number;
  total: number;
  locked: boolean;
  files: Attachment[];
  onChange: (q: QuestionInput) => void;
  onRemove: () => void;
  onMove: (dir: -1 | 1) => void;
  error?: string;
}) {
  const { t } = useI18n();
  const isChoice = q.type === "single_choice" || q.type === "multiple_choice";
  const isBlock = CONTENT_TYPES.includes(q.type);
  const fixedPoints = isBlock || q.type === "fill_gaps"; // computed: blocks 0, gaps = sum of gap points

  const setType = (type: QuestionType) => {
    const task = blankTask(type);
    if (task) return onChange({ ...task, text: q.text });
    const fresh = blankQuestion(type);
    onChange({ ...fresh, text: q.text, points: q.points, explanation: q.explanation, attachment_ids: q.attachment_ids, options: isChoice && (type === "single_choice" || type === "multiple_choice") ? q.options : fresh.options });
  };

  const nextId = () => LETTERS.split("").find((l) => !q.options.some((o) => o.id === l)) ?? String(Date.now());

  return (
    <Card className={cn("p-4 sm:p-5", error && "border-danger/50")}>
      <div className="flex flex-wrap items-center gap-2">
        {isBlock ? (
          <span className="flex h-9 items-center gap-2 rounded-lg bg-accent-soft px-3 text-sm font-medium text-accent">
            {q.type === "audio" ? <Headphones className="size-4" /> : <BookOpen className="size-4" />}
            {t.status.questionType[q.type]}
          </span>
        ) : (
          <>
            <span className="flex size-7 items-center justify-center rounded-lg bg-accent-soft text-xs font-semibold text-accent">{number}</span>
            <NativeSelect value={q.type} disabled={locked} onChange={(e) => setType(e.target.value as QuestionType)} className="h-9 w-auto min-w-[170px] flex-1 sm:flex-none">
              {(["single_choice", "multiple_choice", "true_false", "short_answer", "fill_gaps", "matching"] as const).map((type) => (
                <option key={type} value={type}>{t.status.questionType[type]}</option>
              ))}
            </NativeSelect>
          </>
        )}
        {!isBlock && (
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            {t.tests.points}
            {fixedPoints ? (
              <span className="tabular flex h-9 items-center px-1 text-sm font-medium text-primary">{q.points}</span>
            ) : (
              <Input type="number" min={1} max={100} disabled={locked} value={q.points} onChange={(e) => onChange({ ...q, points: Math.max(1, Number(e.target.value)) })} className="h-9 w-16" />
            )}
          </label>
        )}
        <div className="ml-auto flex gap-1">
          <Button variant="ghost" size="icon-sm" disabled={locked || index === 0} onClick={() => onMove(-1)} aria-label="Up"><ArrowUp /></Button>
          <Button variant="ghost" size="icon-sm" disabled={locked || index === total - 1} onClick={() => onMove(1)} aria-label="Down"><ArrowDown /></Button>
          <Button variant="ghost" size="icon-sm" disabled={locked} onClick={onRemove} className="hover:text-danger" aria-label={t.common.delete}><Trash2 /></Button>
        </div>
      </div>

      {isBlock ? (
        <BlockEditor q={q} locked={locked} files={files} onChange={onChange} />
      ) : (
        <Textarea
          className="mt-3 min-h-[64px]"
          placeholder={q.type === "fill_gaps" ? "Complete the text using the correct words." : q.type === "matching" ? "Match the words with their translations." : t.tests.questionText}
          value={q.text}
          disabled={locked}
          onChange={(e) => onChange({ ...q, text: e.target.value })}
          maxLength={5000}
        />
      )}
      {q.type === "fill_gaps" && <GapsEditor q={q} locked={locked} onChange={onChange} />}
      {q.type === "matching" && <MatchingEditor q={q} locked={locked} onChange={onChange} />}

      {isChoice && (
        <div className="mt-3 grid gap-2">
          <p className="text-xs text-muted-foreground">{t.tests.options} · {t.tests.markCorrect.toLowerCase()}</p>
          {q.type === "single_choice" ? (
            <RadioGroup value={q.correct_answer[0] ?? ""} onValueChange={(v) => onChange({ ...q, correct_answer: [v] })} disabled={locked}>
              {q.options.map((o, i) => (
                <div key={o.id} className="flex items-center gap-2">
                  <RadioGroupItem value={o.id} aria-label={t.tests.correct} />
                  <Input
                    value={o.text}
                    disabled={locked}
                    placeholder={`${t.tests.option} ${i + 1}`}
                    onChange={(e) => onChange({ ...q, options: q.options.map((x) => (x.id === o.id ? { ...x, text: e.target.value } : x)) })}
                    className="h-9"
                  />
                  <Button variant="ghost" size="icon-sm" disabled={locked || q.options.length <= 2}
                    onClick={() => onChange({ ...q, options: q.options.filter((x) => x.id !== o.id), correct_answer: q.correct_answer.filter((c) => c !== o.id) })}>
                    <X />
                  </Button>
                </div>
              ))}
            </RadioGroup>
          ) : (
            q.options.map((o, i) => (
              <div key={o.id} className="flex items-center gap-2">
                <Checkbox
                  checked={q.correct_answer.includes(o.id)}
                  disabled={locked}
                  aria-label={t.tests.correct}
                  onCheckedChange={(c) =>
                    onChange({ ...q, correct_answer: c ? [...q.correct_answer, o.id] : q.correct_answer.filter((x) => x !== o.id) })
                  }
                />
                <Input
                  value={o.text}
                  disabled={locked}
                  placeholder={`${t.tests.option} ${i + 1}`}
                  onChange={(e) => onChange({ ...q, options: q.options.map((x) => (x.id === o.id ? { ...x, text: e.target.value } : x)) })}
                  className="h-9"
                />
                <Button variant="ghost" size="icon-sm" disabled={locked || q.options.length <= 2}
                  onClick={() => onChange({ ...q, options: q.options.filter((x) => x.id !== o.id), correct_answer: q.correct_answer.filter((c) => c !== o.id) })}>
                  <X />
                </Button>
              </div>
            ))
          )}
          {!locked && q.options.length < 10 && (
            <Button variant="ghost" size="sm" className="justify-self-start" onClick={() => onChange({ ...q, options: [...q.options, { id: nextId(), text: "" }] })}>
              <Plus />
              {t.tests.addOption}
            </Button>
          )}
        </div>
      )}

      {q.type === "true_false" && (
        <RadioGroup value={q.correct_answer[0]} onValueChange={(v) => onChange({ ...q, correct_answer: [v] })} disabled={locked} className="mt-3 grid-cols-2">
          {(["true", "false"] as const).map((v) => (
            <label key={v} className={cn("flex h-11 cursor-pointer items-center gap-3 rounded-xl border px-4 text-sm", q.correct_answer[0] === v && "border-success bg-success-soft")}>
              <RadioGroupItem value={v} />
              {v === "true" ? t.tests.true : t.tests.false}
            </label>
          ))}
        </RadioGroup>
      )}

      {q.type === "short_answer" && (
        <Field label={t.tests.acceptedAnswers} hint={t.tests.acceptedHint} className="mt-3">
          <Input
            value={q.correct_answer.join("; ")}
            disabled={locked}
            placeholder="gone; has gone"
            onChange={(e) => onChange({ ...q, correct_answer: e.target.value.split(";").map((s) => s.trimStart()) })}
          />
        </Field>
      )}
      {!isBlock && files.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs text-muted-foreground">{t.tests.questionFiles}</p>
          <div className="flex flex-wrap gap-1.5">
            {files.map((f) => {
              const on = (q.attachment_ids ?? []).includes(f.id);
              return (
                <button
                  key={f.id}
                  type="button"
                  disabled={locked}
                  aria-pressed={on}
                  onClick={() =>
                    onChange({
                      ...q,
                      attachment_ids: on ? (q.attachment_ids ?? []).filter((x) => x !== f.id) : [...(q.attachment_ids ?? []), f.id],
                    })
                  }
                  className={cn(
                    "flex max-w-full items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition-colors disabled:opacity-60",
                    on ? "border-accent bg-accent-soft text-accent" : "text-muted-foreground hover:bg-secondary",
                  )}
                >
                  <Paperclip className="size-3.5 shrink-0" />
                  <span className="max-w-[200px] truncate">{f.original_name}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {!isBlock && (
        <Field label={t.tests.explanation} hint={t.tests.explanationHint} optional className="mt-3">
          <Textarea
            rows={2}
            value={q.explanation ?? ""}
            disabled={locked}
            maxLength={5000}
            onChange={(e) => onChange({ ...q, explanation: e.target.value })}
          />
        </Field>
      )}
      {error && <p className="mt-3 text-xs text-danger">{error}</p>}
    </Card>
  );
}

function Toggle({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg p-2 transition-colors hover:bg-secondary">
      <Checkbox checked={checked} onCheckedChange={(v) => onChange(v === true)} className="mt-0.5" />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-primary">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
    </label>
  );
}

export default function TestEditorPage() {
  const { testId } = useParams();
  const editId = testId ? Number(testId) : null;
  const { t } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const existing = useQuery({ queryKey: ["tests", editId], queryFn: () => testsApi.get(editId!), enabled: !!editId });

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
      })),
    );
    setAvailableFrom(d.available_from ? toDateTimeInput(new Date(d.available_from)) : "");
    setPassing(d.passing_percent?.toString() ?? "");
    setMaxAttempts(d.max_attempts);
    setShuffleQuestions(d.shuffle_questions);
    setShuffleOptions(d.shuffle_options);
    setShowAnswers(d.show_correct_answers);
    setRecipients({ studentIds: d.student_ids, groupIds: [] });
  }, [existing.data]);

  const locked = !!existing.data?.has_attempts;
  const files = existing.data?.files ?? [];

  const uploadFiles = (list: File[], onProgress: (p: number) => void) =>
    testsApi.uploadFiles(editId!, list, onProgress).then(() => qc.invalidateQueries({ queryKey: ["tests", editId] }));
  const removeFile = useMutation({
    mutationFn: (f: Attachment) => testsApi.deleteFile(editId!, f.id),
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
      qc.invalidateQueries({ queryKey: ["tests", editId] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const save = useMutation({
    mutationFn: () => {
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
      return editId ? testsApi.update(editId, body) : testsApi.create(body);
    },
    onSuccess: (test) => {
      qc.invalidateQueries({ queryKey: ["tests"] });
      toast.success(editId ? t.tests.saved : t.tests.created);
      navigate(`/teacher/tests/${test.id}`, { replace: true });
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
      <Link to={editId ? `/teacher/tests/${editId}` : "/teacher/tests"} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.tests.title}
      </Link>
      <h1 className="page-title">{editId ? t.tests.editTitle : t.tests.createTitle}</h1>

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
          <Field label={t.tests.dueAt} optional>
            <Input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
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

      <div className="sticky bottom-0 -mx-4 flex gap-2 border-t bg-background/90 px-4 py-3 backdrop-blur sm:static sm:mx-0 sm:justify-end sm:border-0 sm:bg-transparent sm:p-0">
        <Button variant="outline" className="flex-1 sm:flex-none" onClick={() => navigate(-1)}>{t.common.cancel}</Button>
        <Button className="flex-1 sm:flex-none" loading={save.isPending} onClick={() => validate() && save.mutate()}>
          {t.common.save}
        </Button>
      </div>
    </div>
  );
}
