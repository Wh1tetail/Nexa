import { useId, useState, type ReactNode } from "react";

import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import type { AttendanceMonth, ScorePoint } from "@/types/api";
import { fmtDate, fmtShortDate } from "@/utils/format";

/* Hand-written SVG charts (no chart library): one series each, so color only
 * carries "this is the data" (accent) — identity never depends on color.
 * Thin marks, recessive grid, hover tooltip, and a table view for every chart. */

const W = 600;
const PAD = { top: 16, right: 16, bottom: 28, left: 36 };

/** Above the plot, horizontally at the hovered mark (x in viewBox units -> %, so it
 *  follows the responsive SVG); it never covers the data. */
function Tooltip({ x, children }: { x: number; children: ReactNode }) {
  const left = (x / W) * 100;
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute -top-2 z-10 w-max max-w-[220px] -translate-x-1/2 -translate-y-full rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-lift"
      style={{ left: `${Math.min(85, Math.max(15, left))}%` }}
    >
      {children}
    </div>
  );
}

function TableView({ title, head, rows }: { title: string; head: string[]; rows: ReactNode[][] }) {
  const { t } = useI18n();
  return (
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer select-none text-muted-foreground hover:text-primary">{t.analytics.showTable}</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[280px] text-left">
          <caption className="sr-only">{title}</caption>
          <thead className="text-muted-foreground">
            <tr>{head.map((h) => <th key={h} className="py-1 pr-3 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody className="tabular">
            {rows.map((r, i) => (
              <tr key={i} className="border-t">{r.map((c, j) => <td key={j} className="py-1 pr-3">{c}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function Grid({ height }: { height: number }) {
  const plotH = height - PAD.top - PAD.bottom;
  return (
    <g aria-hidden="true">
      {[0, 50, 100].map((v) => {
        const y = PAD.top + plotH - (v / 100) * plotH;
        return (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} className="stroke-border" strokeWidth={1} />
            <text x={PAD.left - 8} y={y + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{v}%</text>
          </g>
        );
      })}
    </g>
  );
}

/** Percent over time (graded tests or reviewed homework), oldest first. */
export function ScoreChart({ title, points, empty }: { title: string; points: ScorePoint[]; empty: string }) {
  const { t, locale } = useI18n();
  const [hover, setHover] = useState<number | null>(null);
  const H = 200;
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const xs = points.map((_, i) => PAD.left + (points.length === 1 ? plotW / 2 : (i * plotW) / (points.length - 1)));
  const ys = points.map((p) => PAD.top + plotH - (Math.max(0, Math.min(100, p.percent)) / 100) * plotH);
  const id = useId();

  if (!points.length) {
    return <p className="flex h-[140px] items-center justify-center rounded-xl bg-secondary/50 text-sm text-muted-foreground">{empty}</p>;
  }
  const line = points.map((_, i) => `${i ? "L" : "M"}${xs[i].toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const p = hover !== null ? points[hover] : null;

  return (
    <figure aria-labelledby={id}>
      <figcaption id={id} className="sr-only">{title}</figcaption>
      <div className="relative" onMouseLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full overflow-visible" role="img" aria-label={title}>
          <Grid height={H} />
          <path d={line} fill="none" className="stroke-accent" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {points.map((pt, i) => (
            <g key={i}>
              <circle cx={xs[i]} cy={ys[i]} r={hover === i ? 5.5 : 4} className="fill-accent stroke-background" strokeWidth={2} />
              {/* hit target larger than the mark */}
              <rect
                x={xs[i] - Math.max(10, plotW / Math.max(1, points.length) / 2)}
                y={PAD.top}
                width={Math.max(20, plotW / Math.max(1, points.length))}
                height={plotH}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                tabIndex={0}
                aria-label={`${pt.title}: ${pt.percent}%`}
              />
            </g>
          ))}
          <text x={xs[0]} y={H - 6} textAnchor={points.length === 1 ? "middle" : "start"} className="fill-muted-foreground text-[11px]">
            {fmtShortDate(points[0].date, locale)}
          </text>
          {points.length > 1 && (
            <text x={xs[xs.length - 1]} y={H - 6} textAnchor="end" className="fill-muted-foreground text-[11px]">
              {fmtShortDate(points[points.length - 1].date, locale)}
            </text>
          )}
        </svg>
        {p && hover !== null && (
          <Tooltip x={xs[hover]}>
            <p className="font-medium text-primary">{p.title}</p>
            <p className="text-muted-foreground">{fmtShortDate(p.date, locale)}</p>
            <p className="tabular mt-0.5 font-semibold text-primary">
              {p.percent}%
              {p.passed !== null && <span className={cn("ml-1.5 font-normal", p.passed ? "text-success" : "text-danger")}>· {p.passed ? t.tests.passed : t.tests.notPassed}</span>}
            </p>
          </Tooltip>
        )}
      </div>
      <TableView
        title={title}
        head={[t.common.date, t.analytics.item, "%"]}
        rows={points.map((pt) => [fmtShortDate(pt.date, locale), pt.title, `${pt.percent}%`])}
      />
    </figure>
  );
}

/** Attendance rate per calendar month (the breakdown is in the tooltip and table). */
export function AttendanceChart({ title, months }: { title: string; months: AttendanceMonth[] }) {
  const { t, locale } = useI18n();
  const [hover, setHover] = useState<number | null>(null);
  const H = 180;
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const slot = plotW / Math.max(1, months.length);
  const barW = Math.min(44, slot * 0.6);
  const id = useId();
  const monthLabel = (m: string) => fmtDate(m, locale, { month: "short" });
  const m = hover !== null ? months[hover] : null;
  const base = PAD.top + plotH;

  return (
    <figure aria-labelledby={id}>
      <figcaption id={id} className="sr-only">{title}</figcaption>
      <div className="relative" onMouseLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full overflow-visible" role="img" aria-label={title}>
          <Grid height={H} />
          {months.map((mo, i) => {
            const cx = PAD.left + slot * i + slot / 2;
            const h = mo.rate === null ? 0 : Math.max(2, (mo.rate / 100) * plotH);
            const x = cx - barW / 2;
            const r = Math.min(4, h / 2, barW / 2);
            // rounded data end (top), square at the baseline
            const d = `M${x},${base} V${base - h + r} Q${x},${base - h} ${x + r},${base - h} H${x + barW - r} Q${x + barW},${base - h} ${x + barW},${base - h + r} V${base} Z`;
            return (
              <g key={mo.month}>
                {mo.rate === null ? (
                  <text x={cx} y={base - 6} textAnchor="middle" className="fill-muted-foreground text-[11px]">—</text>
                ) : (
                  <path d={d} className={cn("fill-accent transition-opacity", hover !== null && hover !== i && "opacity-40")} />
                )}
                {(hover === i || i === months.length - 1) && mo.rate !== null && (
                  <text x={cx} y={base - h - 6} textAnchor="middle" className="tabular fill-primary text-[11px] font-semibold">{mo.rate}%</text>
                )}
                <text x={cx} y={H - 6} textAnchor="middle" className="fill-muted-foreground text-[11px]">{monthLabel(mo.month)}</text>
                <rect
                  x={cx - slot / 2}
                  y={PAD.top}
                  width={slot}
                  height={plotH}
                  fill="transparent"
                  tabIndex={0}
                  onMouseEnter={() => setHover(i)}
                  onFocus={() => setHover(i)}
                  onBlur={() => setHover(null)}
                  aria-label={`${monthLabel(mo.month)}: ${mo.rate === null ? t.analytics.noMarks : `${mo.rate}%`}`}
                />
              </g>
            );
          })}
        </svg>
        {m && hover !== null && (
          <Tooltip x={PAD.left + slot * hover + slot / 2}>
            <p className="font-medium capitalize text-primary">{fmtDate(m.month, locale, { month: "long", year: "numeric" })}</p>
            {m.rate === null ? (
              <p className="text-muted-foreground">{t.analytics.noMarks}</p>
            ) : (
              <>
                <p className="tabular font-semibold text-primary">{m.rate}%</p>
                <p className="tabular text-muted-foreground">
                  {t.status.attendanceShort.present}: {m.present} · {t.status.attendanceShort.late}: {m.late} · {t.status.attendanceShort.absent}: {m.absent} · {t.status.attendanceShort.excused}: {m.excused}
                </p>
              </>
            )}
          </Tooltip>
        )}
      </div>
      <TableView
        title={title}
        head={[t.analytics.month, "%", t.status.attendanceShort.present, t.status.attendanceShort.late, t.status.attendanceShort.absent, t.status.attendanceShort.excused]}
        rows={months.map((mo) => [monthLabel(mo.month), mo.rate === null ? "—" : `${mo.rate}%`, mo.present, mo.late, mo.absent, mo.excused])}
      />
    </figure>
  );
}
