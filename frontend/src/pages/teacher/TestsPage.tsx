import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, CalendarClock, HelpCircle, Plus, Timer, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { testsApi } from "@/services/api";
import { fmtDateTime } from "@/utils/format";

export default function TestsPage() {
  const { t, locale } = useI18n();
  const q = useQuery({ queryKey: ["tests"], queryFn: testsApi.list });

  return (
    <div>
      <PageHeader
        title={t.tests.title}
        subtitle={t.tests.teacherSubtitle}
        actions={
          <Button asChild>
            <Link to="/teacher/tests/new"><Plus />{t.tests.create}</Link>
          </Button>
        }
      />
      {q.isLoading ? (
        <CardListSkeleton />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data?.length ? (
        <Card>
          <EmptyState icon={BookOpenCheck} title={t.tests.empty} text={t.tests.emptyTeacher}
            action={<Button asChild><Link to="/teacher/tests/new"><Plus />{t.tests.create}</Link></Button>} />
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {q.data.map((test) => (
            <Link key={test.id} to={`/teacher/tests/${test.id}`} className="block rounded-2xl">
              <Card className="flex h-full flex-col p-5 transition-shadow hover:shadow-lift">
                <div className="flex items-start justify-between gap-2">
                  <span className="flex size-10 items-center justify-center rounded-xl bg-accent-soft text-accent">
                    <BookOpenCheck className="size-5" />
                  </span>
                  {test.pending_review_count > 0 && <Badge variant="primary">{t.tests.pendingReview}: {test.pending_review_count}</Badge>}
                </div>
                <h3 className="mt-4 font-semibold">{test.title}</h3>
                {test.description && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{test.description}</p>}
                <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><HelpCircle className="size-3.5" />{t.common.questions(test.questions_count)}</span>
                  <span className="inline-flex items-center gap-1"><Timer className="size-3.5" />{test.time_limit_minutes ? t.common.minutes(test.time_limit_minutes) : t.tests.noLimit}</span>
                  {test.due_at && <span className="inline-flex items-center gap-1"><CalendarClock className="size-3.5" />{fmtDateTime(test.due_at, locale)}</span>}
                </div>
                <div className="mt-5 flex-1" />
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><Users className="size-3.5" />{t.tests.completed}: {test.completed_count}/{test.assigned_count}</span>
                </div>
                <Progress value={(test.completed_count * 100) / Math.max(test.assigned_count, 1)} className="mt-2 h-1.5" />
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
