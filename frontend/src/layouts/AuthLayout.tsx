import { Outlet } from "react-router-dom";

import { Logo } from "@/components/common";
import { useI18n } from "@/contexts/I18nContext";

export function AuthLayout() {
  const { t } = useI18n();
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="flex flex-col px-4 py-6 sm:px-10">
        <Logo />
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-sm animate-fade-in">
            <Outlet />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">© {new Date().getFullYear()} {t.appName}</p>
      </div>
      <div className="relative hidden overflow-hidden bg-primary lg:block">
        <div className="absolute -right-24 -top-24 size-[420px] rounded-full bg-accent/40 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 size-[360px] rounded-full bg-accent/25 blur-3xl" />
        <div className="relative flex h-full flex-col justify-end p-12 text-white">
          <p className="max-w-md text-3xl font-semibold leading-tight tracking-tight">
            “The limits of my language mean the limits of my world.”
          </p>
          <p className="mt-4 text-sm text-white/60">Ludwig Wittgenstein</p>
        </div>
      </div>
    </div>
  );
}
