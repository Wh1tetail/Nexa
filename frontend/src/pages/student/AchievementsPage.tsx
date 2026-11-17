import { useQuery } from "@tanstack/react-query";

import { ErrorState, PageHeader, StatsSkeleton } from "@/components/common";
import { AchievementsGrid, XPCard, XPHistory, XPRules } from "@/components/gamification/Gamification";
import { useI18n } from "@/contexts/I18nContext";
import { gamificationApi } from "@/services/api";

/** Student: XP, level, streak, achievements and how XP is earned. */
export default function AchievementsPage() {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["gamification", "me"], queryFn: gamificationApi.me });
  return (
    <div className="grid gap-6">
      <PageHeader title={t.gamification.title} subtitle={t.gamification.subtitle} />
      {q.isLoading ? (
        <StatsSkeleton />
      ) : q.isError || !q.data ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : (
        <>
          <XPCard g={q.data} />
          <section className="grid gap-3">
            <h2 className="text-base font-semibold text-primary">{t.gamification.achievements}</h2>
            <AchievementsGrid g={q.data} />
          </section>
          <div className="grid gap-6 lg:grid-cols-[1fr_340px] lg:items-start">
            <XPHistory g={q.data} />
            <XPRules g={q.data} />
          </div>
        </>
      )}
    </div>
  );
}
