import { useQuery } from "@tanstack/react-query";

import { ProgressView } from "@/components/analytics/ProgressView";
import { ErrorState, PageHeader, StatsSkeleton } from "@/components/common";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/contexts/I18nContext";
import { analyticsApi } from "@/services/api";

export default function StudentProgressPage() {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["analytics", "me"], queryFn: analyticsApi.me });
  return (
    <div>
      <PageHeader title={t.analytics.myTitle} subtitle={t.analytics.mySubtitle} />
      {q.isLoading ? (
        <div className="grid gap-6">
          <StatsSkeleton />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : q.isError || !q.data ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : (
        <ProgressView data={q.data} />
      )}
    </div>
  );
}
