import { useQuery } from "@tanstack/react-query";
import { CalendarClock, ChevronRight, ClipboardList, Paperclip } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { SubmissionBadge } from "@/components/common/StatusBadges";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { meApi } from "@/services/api";
import type { StudentHomework } from "@/types/api";
import { fmtDateTime } from "@/utils/format";

const ACTIVE = ["new", "in_progress", "needs_revision"];

export function HomeworkRow({ h }: { h: StudentHomework }) {
  const { t, locale } = useI18n();
  return (
    <Link
      to={`/student/homework/${h.submission_id}`}
      className="group flex items-center gap-4 p-4 transition-colors hover:bg-secondary/50 sm:p-5"
    >
      <span
        className={cn(
          "hidden size-10 shrink-0 items-center justify-center rounded-xl sm:flex",
          h.status === "needs_revision" ? "bg-danger-soft text-danger" : "bg-accent-soft text-accent",
        )}
      >
        <ClipboardList className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-primary">{h.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className={cn("inline-flex items-center gap-1", h.is_overdue && "font-medium text-danger")}>
            <CalendarClock className="size-3.5" />
            {h.due_at ? fmtDateTime(h.due_at, locale) : t.common.noDeadline}
          </span>
          {h.attachments.length > 0 && (
            <span className="inline-flex items-center gap-1">
              <Paperclip className="size-3.5" />
              {h.attachments.length}
            </span>
          )}
          {h.grade !== null && (
            <span className="font-medium text-primary">
              {t.homework.grade}: {h.grade}/{h.max_grade}
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5 sm:flex-row sm:items-center">
        {h.is_overdue && <Badge variant="danger">{t.common.overdue}</Badge>}
        <SubmissionBadge status={h.status} />
      </div>
      <ChevronRight className="hidden size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 sm:block" />
    </Link>
  );
}

export default function StudentHomeworkList() {
  const { t } = useI18n();
  const [tab, setTab] = useState("active");
  const q = useQuery({ queryKey: ["me", "homework"], queryFn: meApi.homework });

  const items = useMemo(() => {
    const all = q.data ?? [];
    if (tab === "active") return all.filter((h) => ACTIVE.includes(h.status));
    if (tab === "done") return all.filter((h) => !ACTIVE.includes(h.status));
    return all;
  }, [q.data, tab]);

  const activeCount = (q.data ?? []).filter((h) => ACTIVE.includes(h.status)).length;

  return (
    <div>
      <PageHeader title={t.homework.title} subtitle={t.homework.studentSubtitle} />
      <Tabs value={tab} onValueChange={setTab} className="mb-4">
        <TabsList>
          <TabsTrigger value="active">
            {t.homework.filterActive}
            {activeCount > 0 && <span className="tabular rounded-full bg-accent px-1.5 text-[11px] text-accent-foreground">{activeCount}</span>}
          </TabsTrigger>
          <TabsTrigger value="done">{t.homework.filterDone}</TabsTrigger>
          <TabsTrigger value="all">{t.common.all}</TabsTrigger>
        </TabsList>
      </Tabs>
      {q.isLoading ? (
        <CardListSkeleton />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : items.length ? (
        <Card className="divide-y overflow-hidden">
          {items.map((h) => (
            <HomeworkRow key={h.submission_id} h={h} />
          ))}
        </Card>
      ) : (
        <Card>
          <EmptyState icon={ClipboardList} title={tab === "active" ? t.homework.emptyStudent : t.homework.empty} />
        </Card>
      )}
    </div>
  );
}
