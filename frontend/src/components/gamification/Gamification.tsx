import { BookOpen, ClipboardCheck, Flame, GraduationCap, Info, Lock, Star, Trophy, Zap, type LucideIcon } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import type { Dict } from "@/i18n/ru";
import { cn } from "@/lib/utils";
import type { AchievementCode, Awards, Gamification } from "@/types/api";
import { fmtDate, fmtRelative } from "@/utils/format";

export const ACHIEVEMENT_ICONS: Record<AchievementCode, LucideIcon> = {
  first_lesson: BookOpen,
  first_test: ClipboardCheck,
  perfect_score: Star,
  streak_7: Flame,
  lessons_10: Trophy,
  level_completed: GraduationCap,
};

/** Toast for XP an action has just earned. New achievements arrive as live
 *  notifications (they have their own toast), so they are not repeated here. */
export function showAwards(awards: Awards | null | undefined, t: Dict) {
  if (awards && awards.xp > 0) toast.success(t.gamification.gained(awards.xp), { icon: <Zap className="size-4 text-warning-strong" /> });
}

/** XP, level and streak in one card. */
export function XPCard({ g, compact }: { g: Gamification; compact?: boolean }) {
  const { t } = useI18n();
  const span = g.next_level_xp - g.level_xp;
  const pct = span ? Math.round((100 * (g.xp_total - g.level_xp)) / span) : 100;
  return (
    <Card className={cn("grid gap-4 p-5 sm:p-6", !compact && "sm:grid-cols-[1fr_auto]")}>
      <div className="flex min-w-0 items-center gap-4">
        <span className="flex size-14 shrink-0 flex-col items-center justify-center rounded-2xl bg-accent text-accent-foreground shadow-sm">
          <span className="text-[10px] font-medium uppercase leading-none opacity-80">lvl</span>
          <span className="text-xl font-bold leading-tight">{g.level}</span>
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-2xl font-bold tabular text-primary">{t.gamification.xpTotal(g.xp_total)}</span>
            <span className="text-sm text-muted-foreground">{t.gamification.level(g.level)}</span>
          </p>
          <Progress value={pct} className="mt-2 h-2.5" />
          <p className="mt-1 text-xs text-muted-foreground">{t.gamification.toNext(g.next_level_xp - g.xp_total)}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-xl bg-warning-soft px-4 py-3">
        <Flame className={cn("size-7 shrink-0", g.streak_days ? "text-warning-strong" : "text-muted-foreground")} />
        <div>
          <p className="text-xl font-bold tabular text-primary">{g.streak_days}</p>
          <p className="text-xs text-muted-foreground">{t.gamification.streak}</p>
        </div>
      </div>
    </Card>
  );
}

export function AchievementsGrid({ g }: { g: Gamification }) {
  const { t, locale } = useI18n();
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {g.achievements.map((a) => {
        const Icon = ACHIEVEMENT_ICONS[a.code];
        const b = t.gamification.badge[a.code];
        const earned = !!a.earned_at;
        return (
          <Card key={a.code} className={cn("flex gap-3 p-4", earned ? "border-warning/40" : "opacity-80")}>
            <span
              className={cn(
                "flex size-12 shrink-0 items-center justify-center rounded-2xl",
                earned ? "bg-warning-soft text-warning-strong" : "bg-secondary text-muted-foreground",
              )}
            >
              {earned ? <Icon className="size-6" /> : <Lock className="size-5" />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-primary">{b.title}</p>
              <p className="text-sm text-muted-foreground">{earned ? b.text : b.condition}</p>
              {earned ? (
                <p className="mt-1 text-xs text-success-strong">{t.gamification.earnedOn(fmtDate(a.earned_at, locale))}</p>
              ) : a.target ? (
                <div className="mt-2">
                  <Progress value={(100 * (a.progress ?? 0)) / a.target} className="h-1.5" />
                  <p className="mt-1 text-xs text-muted-foreground">{t.gamification.progress(a.progress ?? 0, a.target)}</p>
                </div>
              ) : (
                <p className="mt-1 text-xs text-muted-foreground">{t.gamification.locked}</p>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export function XPRules({ g }: { g: Gamification }) {
  const { t } = useI18n();
  const s = g.settings;
  const r = t.gamification.rule;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Info className="size-4 text-accent" />{t.gamification.rules}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="grid gap-1.5 text-sm text-primary">
          <li>{r.lesson(s.lesson)}</li>
          <li>{r.test(s.test)}</li>
          <li>{r.bonus(s.test_bonus, s.bonus_threshold)}</li>
          <li>{r.module(s.module)}</li>
          <li>{r.level(s.level)}</li>
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">{t.gamification.rulesNote}</p>
      </CardContent>
    </Card>
  );
}

export function XPHistory({ g }: { g: Gamification }) {
  const { t, locale } = useI18n();
  return (
    <Card>
      <CardHeader><CardTitle>{t.gamification.history}</CardTitle></CardHeader>
      <CardContent>
        {g.recent.length ? (
          <ul className="divide-y">
            {g.recent.map((e, i) => (
              <li key={i} className="flex items-center gap-3 py-2.5">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                  <Zap className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="break-words text-sm font-medium text-primary">{e.title}</p>
                  <p className="text-xs text-muted-foreground">{t.gamification.reason[e.reason]} · {fmtRelative(e.created_at, locale)}</p>
                </div>
                <span className="tabular shrink-0 text-sm font-semibold text-success-strong">{t.gamification.gained(e.points)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t.gamification.noHistory}</p>
        )}
      </CardContent>
    </Card>
  );
}
