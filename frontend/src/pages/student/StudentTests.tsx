import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, CalendarClock, HelpCircle, Timer } from "lucide-react";
import { Link } from "react-router-dom";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader, SectionTitle } from "@/components/common";
import { AttemptBadge } from "@/components/common/StatusBadges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/contexts/I18nContext";
import { meApi } from "@/services/api";
import type { StudentTestItem } from "@/types/api";
import { fmtDate, fmtDateTime } from "@/utils/format";
import { scoreVariant } from "@/utils/status";

function TestCard({ item }: { item: StudentTestItem }) {
  const { t, locale } = useI18n();
  const canStart = !item.attempt_id && !item.is_overdue && item.is_available;
  const notYet = !item.attempt_id && !item.is_available;
  const inProgress = item.attempt_status === "in_progress";
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
          <BookOpenCheck className="size-5" />
        </span>
        <div className="flex flex-wrap justify-end gap-1.5">
          {item.passed !== null && (
            <Badge variant={item.passed ? "success" : "danger"}>{item.passed ? t.tests.passed : t.tests.notPassed}</Badge>
          )}
          {item.is_overdue ? <Badge variant="danger">{t.tests.overdueClosed}</Badge> : <AttemptBadge status={item.attempt_status} />}
        </div>
      </div>
      <h3 className="mt-4 font-semibold">{item.title}</h3>
      {item.description && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{item.description}</p>}
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <HelpCircle className="size-3.5" />
          {t.common.questions(item.questions_count)}
        </span>
        <span className="inline-flex items-center gap-1">
          <Timer className="size-3.5" />
          {item.time_limit_minutes ? t.common.minutes(item.time_limit_minutes) : t.tests.noLimit}
        </span>
        {item.due_at && (
          <span className="inline-flex items-center gap-1">
            <CalendarClock className="size-3.5" />
            {fmtDateTime(item.due_at, locale)}
          </span>
        )}
      </div>
      <div className="mt-5 flex-1" />
      {canStart || inProgress ? (
        <Button asChild className="w-full">
          <Link to={`/student/tests/${item.test_id}/take`}>{inProgress ? t.tests.continue : t.tests.start}</Link>
        </Button>
      ) : item.attempt_id ? (
        <Button variant="outline" asChild className="w-full">
          <Link to={`/student/tests/attempts/${item.attempt_id}`}>
            {t.tests.viewResult}
            {item.percent !== null && <span className="tabular ml-1 font-semibold">· {item.percent}%</span>}
          </Link>
        </Button>
      ) : notYet ? (
        <Button variant="outline" disabled className="w-full">
          {t.tests.opensAt(fmtDateTime(item.available_from, locale))}
        </Button>
      ) : (
        <Button variant="outline" disabled className="w-full">
          {t.tests.overdueClosed}
        </Button>
      )}
    </Card>
  );
}

export default function StudentTests() {
  const { t, locale } = useI18n();
  const q = useQuery({ queryKey: ["me", "tests"], queryFn: meApi.tests });
  const history = (q.data ?? []).filter((i) => i.submitted_at).sort((a, b) => (b.submitted_at! > a.submitted_at! ? 1 : -1));

  return (
    <div>
      <PageHeader title={t.tests.title} subtitle={t.tests.studentSubtitle} />
      {q.isLoading ? (
        <CardListSkeleton />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data?.length ? (
        <Card>
          <EmptyState icon={BookOpenCheck} title={t.tests.emptyStudent} />
        </Card>
      ) : (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {q.data.map((i) => (
              <TestCard key={i.test_id} item={i} />
            ))}
          </div>
          {history.length > 0 && (
            <div>
              <SectionTitle>{t.tests.history}</SectionTitle>
              <Card className="overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead>{t.tests.name}</TableHead>
                      <TableHead>{t.common.date}</TableHead>
                      <TableHead>{t.common.status}</TableHead>
                      <TableHead className="text-right">{t.tests.score}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {history.map((h) => (
                      <TableRow key={h.test_id}>
                        <TableCell className="max-w-[220px] truncate font-medium text-primary">
                          <Link to={`/student/tests/attempts/${h.attempt_id}`} className="hover:text-accent">
                            {h.title}
                          </Link>
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDate(h.submitted_at, locale)}</TableCell>
                        <TableCell>
                          <AttemptBadge status={h.attempt_status} />
                        </TableCell>
                        <TableCell className="text-right">
                          {h.percent !== null ? (
                            <Badge variant={scoreVariant(h.percent)} className="tabular">
                              {h.score}/{h.max_score} · {h.percent}%
                            </Badge>
                          ) : (
                            "—"
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
