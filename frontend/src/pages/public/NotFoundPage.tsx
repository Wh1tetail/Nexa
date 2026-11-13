import { Link } from "react-router-dom";

import { Logo } from "@/components/common";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/contexts/I18nContext";

export default function NotFoundPage() {
  const { t } = useI18n();
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 text-center">
      <Logo />
      <p className="mt-10 text-7xl font-semibold tracking-tight text-accent">404</p>
      <h1 className="mt-4 text-2xl font-semibold">{t.auth.notFoundTitle}</h1>
      <p className="mt-2 max-w-sm text-muted-foreground">{t.auth.notFoundText}</p>
      <Button asChild className="mt-8">
        <Link to="/">{t.auth.toHome}</Link>
      </Button>
    </div>
  );
}
