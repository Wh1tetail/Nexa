import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { ErrorState, Field, PageHeader, PageSkeleton } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { gamificationApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { XPSettings } from "@/types/api";

const FIELDS: { key: keyof XPSettings; min: number; max: number }[] = [
  { key: "lesson", min: 0, max: 1000 },
  { key: "module", min: 0, max: 5000 },
  { key: "level", min: 0, max: 10000 },
  { key: "test", min: 0, max: 1000 },
  { key: "test_bonus", min: 0, max: 1000 },
  { key: "bonus_threshold", min: 50, max: 100 },
];

/** Admin: how much XP each action gives. */
export default function GamificationSettingsPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["gamification", "settings"], queryFn: gamificationApi.settings });
  const [form, setForm] = useState<Record<keyof XPSettings, string> | null>(null);
  useEffect(() => {
    if (q.data) setForm(Object.fromEntries(Object.entries(q.data).map(([k, v]) => [k, String(v)])) as Record<keyof XPSettings, string>);
  }, [q.data]);
  const save = useMutation({
    mutationFn: () => gamificationApi.saveSettings(Object.fromEntries(Object.entries(form!).map(([k, v]) => [k, Number(v)])) as unknown as XPSettings),
    onSuccess: (d) => {
      qc.setQueryData(["gamification", "settings"], d);
      toast.success(t.common.saved);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading || (q.data && !form)) return <PageSkeleton />;
  if (q.isError || !form) return <ErrorState onRetry={() => q.refetch()} />;
  const invalid = FIELDS.some(({ key, min, max }) => form[key] === "" || Number(form[key]) < min || Number(form[key]) > max);
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title={t.gamification.settingsTitle} subtitle={t.gamification.settingsSubtitle} />
      <Card>
        <CardContent className="grid gap-4 pt-6 sm:grid-cols-2">
          {FIELDS.map(({ key, min, max }) => (
            <Field key={key} label={t.gamification.field[key]}>
              <Input
                type="number"
                min={min}
                max={max}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            </Field>
          ))}
          <p className="text-xs text-muted-foreground sm:col-span-2">{t.gamification.settingsNote}</p>
          <div className="sm:col-span-2">
            <Button loading={save.isPending} disabled={invalid} onClick={() => save.mutate()}><Save />{t.common.save}</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
