import { CheckCircle2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Checkbox, RadioGroup, RadioGroupItem } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import type { Answer, Question } from "@/types/api";

interface Props {
  index: number;
  question: Question;
  value: string[];
  onChange?: (v: string[]) => void;
  result?: Answer; // when present -> read-only review mode
  footer?: React.ReactNode;
}

export function QuestionView({ index, question: q, value, onChange, result, footer }: Props) {
  const { t } = useI18n();
  const readOnly = !onChange;
  const correct = q.correct_answer ?? [];
  const showCorrect = readOnly && q.correct_answer !== null;

  const optionLabel = (id: string, text: string) =>
    q.type === "true_false" ? (id === "true" ? t.tests.true : t.tests.false) : text;

  const optionState = (id: string) => {
    if (!showCorrect) return "";
    if (correct.includes(id)) return "border-success/50 bg-success-soft";
    if (value.includes(id)) return "border-danger/40 bg-danger-soft";
    return "";
  };

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t.tests.question} {index + 1} · {t.status.questionType[q.type]}
        </p>
        <div className="flex shrink-0 items-center gap-2">
          {result && result.points_awarded !== null && (
            <Badge variant={result.is_correct ? "success" : result.points_awarded > 0 ? "warning" : "danger"} className="tabular">
              {result.is_correct ? <CheckCircle2 /> : <XCircle />}
              {result.points_awarded}/{q.points}
            </Badge>
          )}
          {!result && <Badge variant="neutral">{t.common.points(q.points)}</Badge>}
        </div>
      </div>
      <p className="mt-2 whitespace-pre-wrap break-words text-base font-medium text-primary">{q.text}</p>
      {q.type === "multiple_choice" && !readOnly && (
        <p className="mt-1 text-xs text-muted-foreground">{t.tests.selectMany}</p>
      )}

      <div className="mt-4">
        {(q.type === "single_choice" || q.type === "true_false") && (
          <RadioGroup
            value={value[0] ?? ""}
            onValueChange={(v) => onChange?.([v])}
            disabled={readOnly}
            className={cn(q.type === "true_false" && "sm:grid-cols-2")}
          >
            {q.options.map((o) => (
              <label
                key={o.id}
                className={cn(
                  "flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors",
                  !readOnly && "hover:bg-secondary/60",
                  value.includes(o.id) && !showCorrect && "border-accent bg-accent-soft/60",
                  optionState(o.id),
                  readOnly && "cursor-default",
                )}
              >
                <RadioGroupItem value={o.id} />
                <span className="flex-1 break-words">{optionLabel(o.id, o.text)}</span>
              </label>
            ))}
          </RadioGroup>
        )}

        {q.type === "multiple_choice" && (
          <div className="grid gap-2">
            {q.options.map((o) => {
              const checked = value.includes(o.id);
              return (
                <label
                  key={o.id}
                  className={cn(
                    "flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors",
                    !readOnly && "hover:bg-secondary/60",
                    checked && !showCorrect && "border-accent bg-accent-soft/60",
                    optionState(o.id),
                    readOnly && "cursor-default",
                  )}
                >
                  <Checkbox
                    checked={checked}
                    disabled={readOnly}
                    onCheckedChange={(c) =>
                      onChange?.(c ? [...value, o.id] : value.filter((v) => v !== o.id))
                    }
                  />
                  <span className="flex-1 break-words">{o.text}</span>
                </label>
              );
            })}
          </div>
        )}

        {q.type === "short_answer" &&
          (readOnly ? (
            <div className="grid gap-2 text-sm">
              <div className="rounded-xl border bg-secondary/50 px-4 py-3">
                <span className="text-xs text-muted-foreground">{t.tests.yourAnswer}: </span>
                <span className="font-medium text-primary">{value[0] || t.tests.noAnswer}</span>
              </div>
              {showCorrect && correct.length > 0 && (
                <div className="rounded-xl border border-success/40 bg-success-soft px-4 py-3">
                  <span className="text-xs text-muted-foreground">{t.tests.correctAnswer}: </span>
                  <span className="font-medium text-primary">{correct.join(" / ")}</span>
                </div>
              )}
            </div>
          ) : (
            <Input
              value={value[0] ?? ""}
              onChange={(e) => onChange?.(e.target.value ? [e.target.value] : [])}
              placeholder={t.tests.placeholderAnswer}
              maxLength={2000}
            />
          ))}
      </div>

      {result?.teacher_comment && (
        <p className="mt-4 rounded-xl bg-accent-soft/60 px-4 py-3 text-sm text-primary">💬 {result.teacher_comment}</p>
      )}
      {footer}
    </Card>
  );
}
