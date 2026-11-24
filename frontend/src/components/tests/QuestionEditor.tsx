import { ArrowDown, ArrowUp, BookOpen, Headphones, Paperclip, Plus, Trash2, X } from "lucide-react";

import { Field } from "@/components/common";
import { BlockEditor, GapsEditor, MatchingEditor, blankTask } from "@/components/tests/TaskEditors";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox, RadioGroup, RadioGroupItem } from "@/components/ui/checkbox";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { QuestionSourceNote } from "@/components/tests/QuestionSourceNote";
import { cn } from "@/lib/utils";
import { CONTENT_TYPES, type Attachment, type QuestionInput, type QuestionType } from "@/types/api";

/** Question types a teacher can pick in the editor (content blocks are added separately). */
export const SCORED_TYPES: QuestionType[] = ["single_choice", "multiple_choice", "true_false", "short_answer", "fill_gaps", "matching"];

const LETTERS = "abcdefghijklmnopqrstuvwxyz";

export function blankQuestion(type: QuestionType = "single_choice"): QuestionInput {
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

export function QuestionEditor({
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
  types = SCORED_TYPES,
}: {
  q: QuestionInput;
  index: number;
  /** number among real questions (blocks have none); none for a single question */
  number?: number;
  total: number;
  locked: boolean;
  files: Attachment[];
  onChange: (q: QuestionInput) => void;
  /** without onRemove / onMove the editor shows no delete and move buttons (one question alone) */
  onRemove?: () => void;
  onMove?: (dir: -1 | 1) => void;
  error?: string;
  /** types the editor may switch between (one type: no switch) */
  types?: QuestionType[];
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
            {number !== undefined && (
              <span className="flex size-7 items-center justify-center rounded-lg bg-accent-soft text-xs font-semibold text-accent">{number}</span>
            )}
            {types.length > 1 ? (
              <NativeSelect value={q.type} disabled={locked} onChange={(e) => setType(e.target.value as QuestionType)} className="h-9 w-auto min-w-[170px] flex-1 sm:flex-none">
                {types.map((type) => (
                  <option key={type} value={type}>{t.status.questionType[type]}</option>
                ))}
              </NativeSelect>
            ) : (
              <span className="text-sm font-medium text-primary">{t.status.questionType[q.type]}</span>
            )}
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
        {(onMove || onRemove) && (
          <div className="ml-auto flex gap-1">
            {onMove && (
              <>
                <Button variant="ghost" size="icon-sm" disabled={locked || index === 0} onClick={() => onMove(-1)} aria-label="Up"><ArrowUp /></Button>
                <Button variant="ghost" size="icon-sm" disabled={locked || index === total - 1} onClick={() => onMove(1)} aria-label="Down"><ArrowDown /></Button>
              </>
            )}
            {onRemove && (
              <Button variant="ghost" size="icon-sm" disabled={locked} onClick={onRemove} className="hover:text-danger" aria-label={t.common.delete}><Trash2 /></Button>
            )}
          </div>
        )}
      </div>
      {q.source && <div className="mt-3"><QuestionSourceNote source={q.source} /></div>}

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

export function Toggle({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
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
