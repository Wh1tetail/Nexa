import {
  BookOpenCheck,
  CalendarCheck,
  CalendarDays,
  ClipboardList,
  CreditCard,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  Users,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Logo } from "@/components/common";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Dialog, DialogTitle, SheetContent } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { homePath, useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { useRealtimeNotifications } from "@/hooks/useNotifications";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

function useNav(): NavItem[] {
  const { user } = useAuth();
  const { t } = useI18n();
  if (user?.role === "admin") {
    return [{ to: "/admin", label: t.nav.dashboard, icon: LayoutDashboard, end: true }];
  }
  if (user?.role === "student") {
    return [
      { to: "/student", label: t.nav.dashboard, icon: LayoutDashboard, end: true },
      { to: "/student/homework", label: t.nav.homework, icon: ClipboardList },
      { to: "/student/tests", label: t.nav.tests, icon: BookOpenCheck },
      { to: "/student/schedule", label: t.nav.schedule, icon: CalendarDays },
      { to: "/student/attendance", label: t.nav.attendance, icon: CalendarCheck },
      { to: "/student/subscription", label: t.nav.subscription, icon: CreditCard },
    ];
  }
  return [
    { to: "/teacher", label: t.nav.dashboard, icon: LayoutDashboard, end: true },
    { to: "/teacher/students", label: t.nav.students, icon: Users },
    { to: "/teacher/groups", label: t.nav.groups, icon: UsersRound },
    { to: "/teacher/lessons", label: t.nav.lessons, icon: CalendarCheck },
    { to: "/teacher/homework", label: t.nav.homework, icon: ClipboardList },
    { to: "/teacher/tests", label: t.nav.tests, icon: BookOpenCheck },
    { to: "/teacher/subscriptions", label: t.nav.subscriptions, icon: CreditCard },
  ];
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const items = useNav();
  return (
    <nav className="grid gap-1">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-primary",
              isActive && "bg-accent-soft text-accent hover:bg-accent-soft hover:text-accent",
            )
          }
        >
          <Icon className="size-[18px] shrink-0" />
          <span className="truncate">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function SidebarFooter({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const base = homePath(user?.role ?? "teacher");
  return (
    <div className="grid gap-1 border-t pt-4">
      <NavLink
        to={`${base}/settings`}
        onClick={onNavigate}
        className={({ isActive }) =>
          cn(
            "flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-primary",
            isActive && "bg-accent-soft text-accent",
          )
        }
      >
        <Settings className="size-[18px]" />
        {t.nav.settings}
      </NavLink>
    </div>
  );
}

export function DashboardLayout() {
  const { user, logout } = useAuth();
  useRealtimeNotifications();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const base = homePath(user?.role ?? "teacher");

  async function handleLogout() {
    await logout();
    toast.success(t.auth.loggedOut);
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-dvh bg-secondary/60">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r bg-background px-4 py-5 lg:flex">
        <Logo to={base} className="px-2" />
        <p className="mt-1 px-2 text-xs text-muted-foreground">
          {user?.role === "student" ? t.nav.studentArea : user?.role === "admin" ? "Admin" : t.nav.teacherArea}
        </p>
        <div className="mt-8 flex-1 overflow-y-auto">
          <SidebarNav />
        </div>
        <SidebarFooter />
      </aside>

      {/* Mobile drawer */}
      <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent aria-describedby={undefined}>
          <DialogTitle className="sr-only">{t.nav.menu}</DialogTitle>
          <div className="flex h-full flex-col px-4 py-5">
            <Logo to={base} className="px-2" />
            <div className="mt-8 flex-1 overflow-y-auto">
              <SidebarNav onNavigate={() => setMobileOpen(false)} />
            </div>
            <SidebarFooter onNavigate={() => setMobileOpen(false)} />
          </div>
        </SheetContent>
      </Dialog>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-2 border-b bg-background/85 px-4 backdrop-blur-md sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="-ml-2 lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label={t.nav.menu}
          >
            <Menu className="!size-5" />
          </Button>
          <Logo to={base} className="lg:hidden" />
          <div className="flex-1" />
          <NotificationBell />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2.5 rounded-full p-1 pr-1 transition-colors hover:bg-secondary sm:pr-3">
                <Avatar name={user?.full_name ?? ""} className="size-8" />
                <span className="hidden max-w-[160px] truncate text-sm font-medium text-primary sm:block">
                  {user?.full_name}
                </span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>
                <span className="block truncate font-medium text-primary">{user?.full_name}</span>
                <span className="block truncate">{user?.email}</span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => navigate(`${base}/settings`)}>
                <Settings />
                {t.nav.settings}
              </DropdownMenuItem>
              <DropdownMenuItem destructive onSelect={handleLogout}>
                <LogOut />
                {t.nav.logout}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>
        <main key={location.pathname + "|" + (user?.timezone ?? "")} className="mx-auto w-full max-w-6xl animate-fade-in px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
