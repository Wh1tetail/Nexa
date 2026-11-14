import { Mail } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { authApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { EMAIL_CATEGORIES, type EmailCategory } from "@/types/api";

/** Which events also arrive by e-mail (only if still unread in the app after a few minutes). */
export function EmailPrefsCard() {
  const { user, setUser } = useAuth();
  const { t } = useI18n();
  const [saving, setSaving] = useState<EmailCategory | null>(null);
  if (!user || user.role === "admin") return null;

  async function toggle(category: EmailCategory, on: boolean) {
    setSaving(category);
    try {
      setUser(await authApi.updateMe({ email_prefs: { [category]: on } }));
      toast.success(t.settings.emailSaved);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="size-4 text-accent" />
          {t.settings.emailTitle}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t.settings.emailHint(user.email)}</p>
      </CardHeader>
      <CardContent className="grid gap-1">
        {EMAIL_CATEGORIES.map((c) => {
          const id = `email-pref-${c}`;
          return (
            <label
              key={c}
              htmlFor={id}
              className="flex cursor-pointer items-start gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-secondary"
            >
              <Checkbox
                id={id}
                checked={user.email_prefs?.[c] ?? true}
                disabled={saving !== null}
                onCheckedChange={(v) => toggle(c, v === true)}
                className="mt-0.5"
              />
              <span className="min-w-0">
                <span className="block text-sm font-medium text-primary">{t.settings.emailCategories[c].title}</span>
                <span className="block text-xs text-muted-foreground">{t.settings.emailCategories[c].text}</span>
              </span>
            </label>
          );
        })}
      </CardContent>
    </Card>
  );
}
