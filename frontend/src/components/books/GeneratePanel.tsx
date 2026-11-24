import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { DraftList } from "@/components/books/DraftList";
import { JobProgress, isActiveJob } from "@/components/books/JobProgress";
import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, NativeSelect } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { booksApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { ENGLISH_LEVELS, type Book, type BookJob, type EnglishLevel, type GenerateInput, type GeneratableType } from "@/types/api";

/** Hints only; the server enforces AI_MAX_QUESTIONS_PER_JOB / AI_MAX_PAGES_PER_JOB. */
const MAX_QUESTIONS = 50;
const MAX_PAGES = 30;
const TYPES: GeneratableType[] = ["single_choice", "multiple_choice", "true_false"];

function GenerationResult({ job }: { job: BookJob }) {
  const { t } = useI18n();
  const result = job.settings.result;
  const usage = job.usage;
  if (job.status !== "done" || !result) return null;
  return (
    <div className="mt-3 grid gap-1 text-sm">
      <p className="font-medium text-primary">{t.books.generationResult(result.drafts)}</p>
      {result.shortfall > 0 && <p className="text-muted-foreground">{t.books.generationShortfall(result.shortfall)}</p>}
      {usage && (
        <p className="text-xs text-muted-foreground">
          {t.books.generationCost(usage.input_tokens + usage.output_tokens, usage.estimated_cost_usd?.toFixed(3) ?? "—")}
        </p>
      )}
    </div>
  );
}

export function GeneratePanel({ book }: { book: Book }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const chapters = useQuery({ queryKey: ["books", book.id, "chapters"], queryFn: () => booksApi.chapters(book.id) });

  const schema = z
    .object({
      mode: z.enum(["chapter", "pages"]),
      chapter_id: z.string(),
      page_start: z.coerce.number().int().min(1).max(book.page_count),
      page_end: z.coerce.number().int().min(1).max(book.page_count),
      question_count: z.coerce.number().int().min(1).max(MAX_QUESTIONS),
      types: z.array(z.enum(["single_choice", "multiple_choice", "true_false"])).min(1, t.books.questionTypes),
      difficulty: z.enum(["mixed", "easy", "medium", "hard"]),
      question_language: z.enum(["en", "ru"]),
      level: z.string(),
    })
    .refine((v) => v.mode === "pages" || v.chapter_id !== "", { path: ["chapter_id"], message: t.books.chooseChapter })
    .refine((v) => v.mode === "chapter" || (v.page_end >= v.page_start && v.page_end - v.page_start < MAX_PAGES), {
      path: ["page_end"],
      message: t.books.limitHint(MAX_QUESTIONS, MAX_PAGES),
    });
  type Values = z.infer<typeof schema>;
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      mode: "chapter",
      chapter_id: "",
      page_start: 1,
      page_end: Math.min(book.page_count, 10),
      question_count: 10,
      types: ["single_choice"],
      difficulty: "mixed",
      question_language: "en",
      level: book.level ?? "",
    },
  });
  const errors = form.formState.errors;
  const mode = form.watch("mode");
  const types = form.watch("types");

  const toInput = (v: Values): GenerateInput => ({
    ...(v.mode === "chapter" ? { chapter_id: Number(v.chapter_id) } : { page_start: v.page_start, page_end: v.page_end }),
    question_count: v.question_count,
    types: v.types,
    difficulty: v.difficulty === "mixed" ? null : v.difficulty,
    question_language: v.question_language,
    level: (v.level || null) as EnglishLevel | null,
  });
  const fromJob = (j: BookJob): GenerateInput => ({
    ...(j.settings.chapter_id ? { chapter_id: j.settings.chapter_id } : { page_start: j.settings.page_start, page_end: j.settings.page_end }),
    question_count: j.settings.question_count ?? 10,
    types: (j.settings.types ?? ["single_choice"]) as GeneratableType[],
    difficulty: j.settings.difficulty && j.settings.difficulty !== "mixed" ? j.settings.difficulty : null,
    question_language: j.settings.question_language ?? "en",
    level: j.settings.level ?? null,
  });
  const start = useMutation({
    mutationFn: (input: GenerateInput) => booksApi.generate(book.id, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["books", book.id] });
      toast.success(t.books.generationStarted);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const cancel = useMutation({
    mutationFn: (jobId: number) => booksApi.cancelJob(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["books", book.id] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const job = book.generation;
  const busy = isActiveJob(job);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Sparkles className="size-4 text-accent" />{t.books.generateTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">{t.books.generateHint}</p>
          <form className="grid gap-4" onSubmit={form.handleSubmit((v) => start.mutate(toInput(v)))}>
            <Field label={t.books.source}>
              <div className="flex flex-wrap gap-2">
                {(["chapter", "pages"] as const).map((m) => (
                  <label key={m} className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border px-3 text-sm hover:bg-secondary">
                    <input type="radio" value={m} className="accent-accent" {...form.register("mode")} />
                    {m === "chapter" ? t.books.sourceChapter : t.books.sourcePages}
                  </label>
                ))}
              </div>
            </Field>
            {mode === "chapter" ? (
              <Field label={t.books.sourceChapter} error={errors.chapter_id?.message}>
                <NativeSelect {...form.register("chapter_id")}>
                  <option value="">{t.books.chooseChapter}</option>
                  {(chapters.data ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {"  ".repeat(c.depth - 1)}{c.title} ({t.books.pageRange(c.start_page, c.end_page)})
                    </option>
                  ))}
                </NativeSelect>
              </Field>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <Field label={t.books.startPage} error={errors.page_start?.message}>
                  <Input type="number" inputMode="numeric" min={1} max={book.page_count} {...form.register("page_start")} />
                </Field>
                <Field label={t.books.endPage} error={errors.page_end?.message}>
                  <Input type="number" inputMode="numeric" min={1} max={book.page_count} {...form.register("page_end")} />
                </Field>
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t.books.questionCount} hint={t.books.limitHint(MAX_QUESTIONS, MAX_PAGES)} error={errors.question_count?.message}>
                <Input type="number" inputMode="numeric" min={1} max={MAX_QUESTIONS} {...form.register("question_count")} />
              </Field>
              <Field label={t.books.difficulty}>
                <NativeSelect {...form.register("difficulty")}>
                  {(["mixed", "easy", "medium", "hard"] as const).map((d) => (
                    <option key={d} value={d}>{t.books.difficultyLevels[d]}</option>
                  ))}
                </NativeSelect>
              </Field>
              <Field label={t.books.questionLanguage}>
                <NativeSelect {...form.register("question_language")}>
                  <option value="en">{t.books.lang.en}</option>
                  <option value="ru">{t.books.lang.ru}</option>
                </NativeSelect>
              </Field>
              <Field label={t.books.studentLevel}>
                <NativeSelect {...form.register("level")}>
                  <option value="">{t.books.noLevel}</option>
                  {ENGLISH_LEVELS.map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </NativeSelect>
              </Field>
            </div>
            <Field label={t.books.questionTypes} error={errors.types?.message}>
              <div className="flex flex-wrap gap-2">
                {TYPES.map((ty) => (
                  <label key={ty} className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border px-3 text-sm hover:bg-secondary">
                    <Checkbox
                      checked={types.includes(ty)}
                      onCheckedChange={(v) =>
                        form.setValue("types", v ? [...types, ty] : types.filter((x) => x !== ty), { shouldValidate: true })
                      }
                    />
                    {t.status.questionType[ty]}
                  </label>
                ))}
              </div>
            </Field>
            <div>
              <Button type="submit" disabled={busy} loading={start.isPending}>
                <Sparkles />
                {t.books.generate}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {job && (
        <div>
          <JobProgress
            title={t.books.generation}
            job={job}
            onCancel={() => cancel.mutate(job.id)}
            cancelling={cancel.isPending}
            onRestart={() => start.mutate(fromJob(job))}
            restarting={start.isPending}
            generation
          />
          <GenerationResult job={job} />
        </div>
      )}

      <DraftList book={book} />
    </div>
  );
}
