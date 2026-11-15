import { BookOpenCheck, CalendarCheck, ClipboardList, Clock, TrendingDown, TrendingUp } from "lucide-react";

import { AttendanceChart, ScoreChart } from "@/components/analytics/Charts";
import { StatCard } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import type { StudentProgress } from "@/types/api";

const pct = (v: number | null) => (v === null ? "—" : `${v}%`);

/** Progress of one student: summary cards and charts (used by the student and the teacher). */
export function ProgressView({ data }: { data: StudentProgress }) {
  const { t } = useI18n();
  const s = data.summary;
  const trend = s.test_trend;
  return (
    <div className="grid gap-6">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard
          icon={BookOpenCheck}
          label={t.analytics.avgTest}
          value={pct(s.avg_test)}
          tone="accent"
          hint={
            trend !== null ? (
              <span className={trend >= 0 ? "inline-flex items-center gap-1 text-success" : "inline-flex items-center gap-1 text-danger"}>
                {trend >= 0 ? <TrendingUp className="size-3.5" /> : <TrendingDown className="size-3.5" />}
                {t.analytics.trend(trend)}
              </span>
            ) : (
              t.analytics.count(s.tests_count)
            )
          }
        />
        <StatCard icon={ClipboardList} label={t.analytics.avgHomework} value={pct(s.avg_homework)} tone="primary" hint={t.analytics.count(s.homework_count)} />
        <StatCard icon={CalendarCheck} label={t.analytics.attendance} value={pct(s.attendance_rate)} tone="success" />
        <StatCard icon={Clock} label={t.analytics.onTime} value={pct(s.on_time_rate)} tone="warning" hint={t.analytics.onTimeHint} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t.analytics.testsChart}</CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <ScoreChart title={t.analytics.testsChart} points={data.tests} empty={t.analytics.noTests} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t.analytics.homeworkChart}</CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <ScoreChart title={t.analytics.homeworkChart} points={data.homework} empty={t.analytics.noHomework} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t.analytics.attendanceChart}</CardTitle>
          <p className="text-sm text-muted-foreground">{t.analytics.attendanceHint}</p>
        </CardHeader>
        <CardContent className="pt-6">
          <AttendanceChart title={t.analytics.attendanceChart} months={data.attendance} />
        </CardContent>
      </Card>
    </div>
  );
}
