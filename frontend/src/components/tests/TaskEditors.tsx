import { BookOpen, Headphones, Plus, X } from "lucide-react";

import { Field } from "@/components/common";
import { Markdown } from "@/components/tests/Markdown";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import type { Attachment, FillMode, Question, QuestionInput, QuestionType } from "@/types/api";

/** What the editor keeps in QuestionInput.config (the API's input format). */
export interface EditorConfig {
  template?: string;
  gap_points?: number[];
  mode?: FillMode;
  case_sensitive?: boolean;
  distractors?: string[];
  pairs?: { left: string; right: string }[];
  attachment_id?: number | null;
  max_plays?: number | null;
  body?: string;
  image_id?: number | null;
}

export const cfgOf = (q: QuestionInput) => (q.config ?? {}) as EditorConfig;

const GAP = /\{([^{}]+)\}/g;

/** Gaps of a template as the server parses them: accepted answers and hint. */
export function parseGaps(template: string) {
  return [...template.matchAll(GAP)].map((m) => {
    const [body, hint] = m[1].split("::");
    return { answers: body.split("|").map((a) => a.trim()).filter(Boolean), hint: hint?.trim() || null };
  });
}

export function blankTask(type: QuestionType): QuestionInput | null {
  const base = { type, options: [], correct_answer: [], explanation: null, attachment_ids: [] };
  if (type === "fill_gaps")
    return { ...base, text: "", points: 1, config: { template: "", gap_points: [], mode: "input", case_sensitive: false, distractors: [] } };
  if (type === "matching")
    return {
      ...base,
      text: "",
      points: 2,
      config: { pairs: [{ left: "", right: "" }, { left: "", right: "" }], distractors: [] },
    };
  if (type === "audio") return { ...base, text: "", points: 0, config: { attachment_id: null, max_plays: null, body: "" } };
  if (type === "reading") return { ...base, text: "", points: 0, config: { body: "", image_id: null } };
  return null;
}

/** Saved question (teacher view, answers revealed) -> editor input. */
export function taskConfigFromSaved(q: Question): Record<string, unknown> | undefined {
  const c = q.config;
  if (q.type === "fill_gaps")
    return {
      template: c.template ?? "",
      gap_points: (c.gaps ?? []).map((g) => g.points),
      mode: c.mode ?? "input",
      case_sensitive: !!c.case_sensitive,
      distractors: c.distractors ?? [],
    };
  if (q.type === "matching") return { pairs: c.pairs ?? [], distractors: c.distractors ?? [] };
  if (q.type === "audio") return { attachment_id: c.attachment_id ?? null, max_plays: c.max_plays ?? null, body: c.body ?? "" };
  if (q.type === "reading") return { body: c.body ?? "", image_id: c.image_id ?? null };
  return undefined;
}

/** First problem of a new-type question, for the editor's validation. */
export function taskError(q: QuestionInput, t: ReturnType<typeof useI18n>["t"]): string | undefined {
  const c = cfgOf(q);
  if (q.type === "fill_gaps" && !parseGaps(c.template ?? "").some((g) => g.answers.length)) return t.tasks.gapsNeeded;
  if (q.type === "matching" && (c.pairs ?? []).filter((p) => p.left.trim() && p.right.trim()).length < 2) return t.tasks.pairsNeeded;
  if (q.type === "audio" && !c.attachment_id) return t.tasks.audioNeeded;
  if (q.type === "reading" && !(c.body ?? "").trim()) return t.tasks.readingNeeded;
  return undefined;
}

const words = (s: string) => s.split(",").map((w) => w.trim()).filter(Boolean);

// ---------- fill in the gaps ----------

export function GapsEditor({ q, locked, onChange }: { q: QuestionInput; locked: boolean; onChange: (q: QuestionInput) => void }) {
  const { t } = useI18n();
  const c = cfgOf(q);
  const gaps = parseGaps(c.template ?? "");
  const points = gaps.map((_, i) => c.gap_points?.[i] ?? 1);
  const set = (patch: Partial<EditorConfig>) => {
    const next = { ...c, ...patch };
    const total = parseGaps(next.template ?? "").reduce((s, _, i) => s + (next.gap_points?.[i] ?? 1), 0);
    onChange({ ...q, config: next as Record<string, unknown>, points: Math.max(total, 1) });
  };
  return (
    <div className="mt-3 grid gap-3">
      <Field label={t.tasks.template} hint={t.tasks.templateHint}>
        <Textarea
          rows={4}
          value={c.template ?? ""}
          disabled={locked}
          maxLength={20000}
          placeholder="Tom usually {goes::go} to school. He {likes|loves} English."
          onChange={(e) => set({ template: e.target.value })}
        />
      </Field>
      {gaps.length > 0 && (
        <div className="grid gap-2 rounded-xl border bg-secondary/40 p-3">
          <p className="text-xs font-medium text-muted-foreground">
            {t.tasks.gapsFound(gaps.length)} · {t.tasks.gapPoints}
          </p>
          <div className="flex flex-wrap gap-2">
            {gaps.map((g, i) => (
              <label
                key={i}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg border bg-card px-2 py-1 text-xs",
                  !g.answers.length && "border-danger/50",
                )}
              >
                <span className="max-w-[160px] truncate font-medium text-primary">{g.answers.join(" / ") || "?"}</span>
                <Input
                  type="number"
                  min={1}
                  max={20}
                  disabled={locked}
                  value={points[i]}
                  aria-label={`${t.tasks.gapPoints} ${i + 1}`}
                  onChange={(e) =>
                    set({ gap_points: points.map((p, j) => (j === i ? Math.min(20, Math.max(1, Number(e.target.value) || 1)) : p)) })
                  }
                  className="h-7 w-14 px-2"
                />
              </label>
            ))}
          </div>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t.tasks.mode}>
          <NativeSelect value={c.mode ?? "input"} disabled={locked} onChange={(e) => set({ mode: e.target.value as FillMode })}>
            <option value="input">{t.tasks.modeInput}</option>
            <option value="dropdown">{t.tasks.modeDropdown}</option>
            <option value="drag">{t.tasks.modeDrag}</option>
          </NativeSelect>
        </Field>
        {c.mode && c.mode !== "input" && (
          <Field label={t.tasks.distractors} optional>
            <Input
              defaultValue={(c.distractors ?? []).join(", ")}
              disabled={locked}
              placeholder="go, went"
              onBlur={(e) => set({ distractors: words(e.target.value) })}
            />
          </Field>
        )}
      </div>
      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <Checkbox checked={!!c.case_sensitive} disabled={locked} onCheckedChange={(v) => set({ case_sensitive: v === true })} />
        {t.tasks.caseSensitive}
      </label>
    </div>
  );
}

// ---------- matching ----------

export function MatchingEditor({ q, locked, onChange }: { q: QuestionInput; locked: boolean; onChange: (q: QuestionInput) => void }) {
  const { t } = useI18n();
  const c = cfgOf(q);
  const pairs = c.pairs ?? [];
  const set = (patch: Partial<EditorConfig>) => onChange({ ...q, config: { ...c, ...patch } as Record<string, unknown> });
  const setPair = (i: number, side: "left" | "right", v: string) =>
    set({ pairs: pairs.map((p, j) => (j === i ? { ...p, [side]: v } : p)) });
  return (
    <div className="mt-3 grid gap-2">
      <p className="text-xs text-muted-foreground">{t.tasks.pairs}</p>
      {pairs.map((p, i) => (
        <div key={i} className="grid grid-cols-[1fr_auto_1fr_auto] items-center gap-2">
          <Input value={p.left} disabled={locked} placeholder={t.tasks.left} maxLength={300} onChange={(e) => setPair(i, "left", e.target.value)} className="h-9" />
          <span className="text-muted-foreground">→</span>
          <Input value={p.right} disabled={locked} placeholder={t.tasks.right} maxLength={300} onChange={(e) => setPair(i, "right", e.target.value)} className="h-9" />
          <Button
            variant="ghost"
            size="icon-sm"
            disabled={locked || pairs.length <= 2}
            aria-label={t.common.delete}
            onClick={() => set({ pairs: pairs.filter((_, j) => j !== i) })}
          >
            <X />
          </Button>
        </div>
      ))}
      {!locked && pairs.length < 20 && (
        <Button variant="ghost" size="sm" className="justify-self-start" onClick={() => set({ pairs: [...pairs, { left: "", right: "" }] })}>
          <Plus />
          {t.tasks.addPair}
        </Button>
      )}
      <Field label={t.tasks.distractors} optional>
        <Input
          defaultValue={(c.distractors ?? []).join(", ")}
          disabled={locked}
          placeholder="кот, мышь"
          onBlur={(e) => set({ distractors: words(e.target.value) })}
        />
      </Field>
    </div>
  );
}

// ---------- audio / reading blocks ----------

export function BlockEditor({
  q,
  locked,
  files,
  onChange,
}: {
  q: QuestionInput;
  locked: boolean;
  files: Attachment[];
  onChange: (q: QuestionInput) => void;
}) {
  const { t } = useI18n();
  const c = cfgOf(q);
  const set = (patch: Partial<EditorConfig>) => onChange({ ...q, config: { ...c, ...patch } as Record<string, unknown> });
  const audio = files.filter((f) => f.mime_type.startsWith("audio/"));
  const images = files.filter((f) => f.mime_type.startsWith("image/"));
  return (
    <div className="mt-3 grid gap-3">
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        {q.type === "audio" ? <Headphones className="size-4 text-accent" /> : <BookOpen className="size-4 text-accent" />}
        {t.tasks.blockNote}
      </p>
      <Field label={t.tasks.blockTitle}>
        <Input
          value={q.text}
          disabled={locked}
          maxLength={300}
          placeholder={q.type === "audio" ? "Dialogue 1" : "A day in the park"}
          onChange={(e) => onChange({ ...q, text: e.target.value })}
        />
      </Field>
      {q.type === "audio" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t.tasks.audioFile} hint={audio.length ? undefined : t.tasks.noAudioFiles}>
              <NativeSelect
                value={c.attachment_id ?? ""}
                disabled={locked || !audio.length}
                onChange={(e) => set({ attachment_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">{t.tasks.chooseAudio}</option>
                {audio.map((f) => (
                  <option key={f.id} value={f.id}>{f.original_name}</option>
                ))}
              </NativeSelect>
            </Field>
            <Field label={t.tasks.maxPlays}>
              <NativeSelect
                value={c.max_plays ?? ""}
                disabled={locked}
                onChange={(e) => set({ max_plays: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">{t.tasks.unlimited}</option>
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </NativeSelect>
            </Field>
          </div>
          <Field label={t.tasks.instructions} optional>
            <Textarea rows={2} value={c.body ?? ""} disabled={locked} maxLength={5000} onChange={(e) => set({ body: e.target.value })} />
          </Field>
        </>
      ) : (
        <>
          <Field label={t.tasks.readingText} hint={t.tasks.readingHint}>
            <Textarea rows={8} value={c.body ?? ""} disabled={locked} maxLength={30000} onChange={(e) => set({ body: e.target.value })} />
          </Field>
          <Field label={t.tasks.readingImage} optional>
            <NativeSelect value={c.image_id ?? ""} disabled={locked} onChange={(e) => set({ image_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">{t.tasks.noImage}</option>
              {images.map((f) => (
                <option key={f.id} value={f.id}>{f.original_name}</option>
              ))}
            </NativeSelect>
          </Field>
          {(c.body ?? "").trim() && (
            <div className="rounded-xl border bg-secondary/30 p-4">
              <Markdown text={c.body ?? ""} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
