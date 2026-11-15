import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BookOpenCheck, CalendarCheck, ClipboardList, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, PageHeader, StatCard, StatsSkeleton } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { analyticsApi, groupsApi } from "@/services/api";
import type { RiskReason, StudentOverviewRow } from "@/types/api";
import { fmtRelative } from "@/utils/format";

const PERIODS = [30, 90, 365] as const;
const pct = (v: number | null) => (v === null ? "—" : `${v}%`);

/** A value with a thin bar behind it (magnitude at a glance, number still readable). */
function Meter({ value, warnBelow }: { value: number | null; warnBelow: number }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  const low = value < warnBelow;
  return (
    <span className="inline-flex items-center gap-2">
      <span className="tabular w-10 text-right font-medium text-primary">{value}%</span>
      <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-secondary sm:block" aria-hidden="true">
        <span className={cn("block h-full rounded-full", low ? "bg-danger" : "bg-accent")} style={{ width: `${value}%` }} />
      </span>
    </span>
  );
}

function Risks({ risks }: { risks: RiskReason[] }) {
  const { t } = useI18n();
  if (!risks.length) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {risks.map((r) => (
        <Badge key={r} variant={r === "inactive" ? "neutral" : "warning"} className="whitespace-nowrap">
          <AlertTriangle />
          {t.analytics.risk[r]}
        </Badge>
      ))}
    </div>
  );
}

function StudentRow({ r }: { r: StudentOverviewRow }) {
  const { t, locale } = useI18n();
  return (
    <TableRow>
      <TableCell className="min-w-[210px]">
        <Link to={`/teacher/students/${r.student_id}`} className="whitespace-nowrap font-medium text-primary hover:text-accent">
          {r.full_name}
        </Link>
        <p className="text-xs text-muted-foreground">{[r.english_level, ...r.groups].join(" · ")}</p>
      </TableCell>
      <TableCell><Meter value={r.avg_test} warnBelow={60} /></TableCell>
      <TableCell><Meter value={r.avg_homework} warnBelow={60} /></TableCell>
      <TableCell><Meter value={r.attendance_rate} warnBelow={70} /></TableCell>
      <TableCell className={cn("tabular text-center", r.overdue_homework > 0 && "font-semibold text-danger")}>{r.overdue_homework}</TableCell>
      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
        {r.last_activity ? fmtRelative(r.last_activity, locale) : t.analytics.never}
      </TableCell>
      <TableCell><Risks risks={r.risks} /></TableCell>
    </TableRow>
  );
}

export default function AnalyticsPage() {
  const { t } = useI18n();
  const [period, setPeriod] = useState<number>(90);
  const [groupId, setGroupId] = useState<number | null>(null);
  const groups = useQuery({ queryKey: ["groups"], queryFn: groupsApi.list });
  const q = useQuery({
    queryKey: ["analytics", "overview", period, groupId],
    queryFn: () => analyticsApi.overview(period, groupId),
    placeholderData: (prev) => prev,
  });
  const d = q.data;

  return (
    <div>
      <PageHeader title={t.analytics.title} subtitle={t.analytics.subtitle} />

      {/* filters: one row above everything they affect */}
      <div className="mb-6 flex flex-col gap-2 sm:flex-row">
        <NativeSelect value={period} onChange={(e) => setPeriod(Number(e.target.value))} aria-label={t.lessons.period} className="sm:w-48">
          {PERIODS.map((p) => (
            <option key={p} value={p}>{t.analytics.period(p)}</option>
          ))}
        </NativeSelect>
        <NativeSelect
          value={groupId ?? ""}
          onChange={(e) => setGroupId(e.target.value ? Number(e.target.value) : null)}
          aria-label={t.common.group}
          className="sm:w-56"
        >
          <option value="">{t.students.allGroups}</option>
          {groups.data?.map((g) => (
            <option key={g.id} value={g.id}>{g.name}</option>
          ))}
        </NativeSelect>
      </div>

      {q.isLoading ? (
        <div className="grid gap-6">
          <StatsSkeleton />
          <Skeleton className="h-72 w-full" />
        </div>
      ) : q.isError || !d ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : (
        <div className={cn("grid gap-6 transition-opacity", q.isFetching && "opacity-60")}>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatCard icon={Users} label={t.analytics.students} value={d.students} tone="primary"
              hint={d.at_risk ? t.analytics.atRisk(d.at_risk) : t.analytics.allGood} />
            <StatCard icon={BookOpenCheck} label={t.analytics.avgTest} value={pct(d.avg_test)} tone="accent" />
            <StatCard icon={ClipboardList} label={t.analytics.avgHomework} value={pct(d.avg_homework)} tone="primary" />
            <StatCard icon={CalendarCheck} label={t.analytics.attendance} value={pct(d.attendance_rate)} tone="success" />
          </div>

          <Card className="overflow-hidden">
            {d.rows.length ? (
              <div className="overflow-x-auto">
                <Table className="min-w-[860px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t.common.student}</TableHead>
                      <TableHead>{t.analytics.colTests}</TableHead>
                      <TableHead>{t.analytics.colHomework}</TableHead>
                      <TableHead>{t.analytics.attendance}</TableHead>
                      <TableHead className="text-center">{t.analytics.colOverdue}</TableHead>
                      <TableHead>{t.analytics.colActivity}</TableHead>
                      <TableHead>{t.analytics.colAttention}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {d.rows.map((r) => <StudentRow key={r.student_id} r={r} />)}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <EmptyState icon={Users} title={t.analytics.empty} />
            )}
          </Card>
          <p className="text-xs text-muted-foreground">{t.analytics.rules}</p>
        </div>
      )}
    </div>
  );
}
