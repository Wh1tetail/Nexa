import { useQuery } from "@tanstack/react-query";

import { ProgressView } from "@/components/analytics/ProgressView";
import { ErrorState, PageHeader, StatsSkeleton } from "@/components/common";
import { CourseProgressView } from "@/components/courses/CourseProgressView";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/contexts/I18nContext";
import { lessonHref } from "@/pages/student/StudentCoursesPage";
import { analyticsApi, myCoursesApi } from "@/services/api";

export default function StudentProgressPage() {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["analytics", "me"], queryFn: analyticsApi.me });
  // needs an active subscription; without one the course part is simply not shown
  const courses = useQuery({ queryKey: ["my-course-progress"], queryFn: myCoursesApi.progress, retry: false });
  return (
    <div className="grid gap-8">
      <div>
        <PageHeader title={t.analytics.myTitle} subtitle={t.analytics.mySubtitle} />
        {courses.data && (
          <section className="grid gap-3">
            <h2 className="text-base font-semibold text-primary">{t.myCourses.progressTitle}</h2>
            <CourseProgressView data={courses.data} lessonHref={lessonHref} />
          </section>
        )}
      </div>
      <section className="grid gap-3">
        {courses.data && <h2 className="text-base font-semibold text-primary">{t.nav.tests} · {t.nav.homework} · {t.nav.attendance}</h2>}
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
      </section>
    </div>
  );
}
