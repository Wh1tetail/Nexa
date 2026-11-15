import { useQuery } from "@tanstack/react-query";
import { CreditCard, Lock, MessageSquare } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { PageSkeleton } from "@/components/common";
import { SubscriptionBadge } from "@/components/common/StatusBadges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { authApi, meApi } from "@/services/api";

/** Fresh access flag for students (re-checked when the tab regains focus), so a
 *  renewed subscription opens the sections without signing in again. */
export function useStudentAccess() {
  const { user, setUser } = useAuth();
  const q = useQuery({
    queryKey: ["me", "access"],
    queryFn: async () => {
      const me = await authApi.me();
      setUser(me);
      return me.access_active;
    },
    enabled: user?.role === "student",
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  return { access: q.data ?? user?.access_active ?? true, loading: q.isLoading };
}

/** Closed-section screen: why, and where to go next. */
export function LockedSection() {
  const { t } = useI18n();
  const sub = useQuery({ queryKey: ["me", "subscription"], queryFn: meApi.subscription });
  return (
    <Card className="mx-auto max-w-xl p-6 text-center sm:p-10">
      <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-warning-soft text-[hsl(32_95%_36%)]">
        <Lock className="size-7" />
      </div>
      <h1 className="mt-5 text-xl font-semibold text-primary">{t.access.title}</h1>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{t.access.text}</p>
      <div className="mt-4 flex justify-center">
        {sub.data ? <SubscriptionBadge status={sub.data.status} /> : sub.isSuccess && <span className="text-sm font-medium text-primary">{t.access.noSubscription}</span>}
      </div>
      <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
        <Button asChild>
          <Link to="/student/subscription"><CreditCard />{t.access.mySubscription}</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/student/messages"><MessageSquare />{t.access.writeTeacher}</Link>
        </Button>
      </div>
    </Card>
  );
}

/** Lessons, homework and tests: only with an active subscription. */
export function RequireAccess({ children }: { children: ReactNode }) {
  const { access, loading } = useStudentAccess();
  if (loading) return <PageSkeleton />;
  return access ? <>{children}</> : <LockedSection />;
}
