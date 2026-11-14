import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Field, PageHeader } from "@/components/common";
import { TimezoneCard } from "@/components/common/TimezoneCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n, type Locale } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { authApi } from "@/services/api";
import { errorMessage, tokenStore } from "@/services/http";
import { passwordSchema } from "@/utils/validation";

export default function SettingsPage() {
  const { t, locale, setLocale } = useI18n();
  const { user, setUser } = useAuth();

  const profileSchema = z.object({
    full_name: z.string().trim().min(2, t.students.fullNameMin).max(200),
    phone: z.string().trim().max(32),
  });
  const profile = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: user?.full_name ?? "", phone: user?.phone ?? "" },
  });

  const pwSchema = z.object({ current: z.string().min(1, t.auth.passwordRequired), next: passwordSchema(t) });
  const pw = useForm<z.infer<typeof pwSchema>>({ resolver: zodResolver(pwSchema), defaultValues: { current: "", next: "" } });

  async function changeLocale(l: Locale) {
    setLocale(l);
    try {
      setUser(await authApi.updateMe({ locale: l }));
    } catch {
      /* local preference still applied */
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title={t.settings.title} subtitle={t.settings.subtitle} />

      <Card>
        <CardHeader>
          <CardTitle>{t.settings.profile}</CardTitle>
          <p className="text-sm text-muted-foreground">{user?.email}</p>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4"
            onSubmit={profile.handleSubmit(async (v) => {
              try {
                setUser(await authApi.updateMe({ full_name: v.full_name, phone: v.phone || null }));
                toast.success(t.common.saved);
              } catch (e) {
                toast.error(errorMessage(e));
              }
            })}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t.settings.fullName} error={profile.formState.errors.full_name?.message}>
                <Input {...profile.register("full_name")} />
              </Field>
              <Field label={t.settings.phone} optional>
                <Input type="tel" {...profile.register("phone")} />
              </Field>
            </div>
            <div>
              <Button type="submit" loading={profile.formState.isSubmitting}>{t.common.save}</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t.common.language}</CardTitle>
          <p className="text-sm text-muted-foreground">{t.settings.languageHint}</p>
        </CardHeader>
        <CardContent>
          <div className="inline-flex rounded-xl bg-secondary p-1">
            {([
              ["ru", "Русский"],
              ["en", "English"],
            ] as const).map(([code, label]) => (
              <button
                key={code}
                onClick={() => changeLocale(code)}
                className={cn(
                  "rounded-lg px-4 py-2 text-sm font-medium transition-all",
                  locale === code ? "bg-background text-primary shadow-sm" : "text-muted-foreground hover:text-primary",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <TimezoneCard />

      <Card>
        <CardHeader>
          <CardTitle>{t.settings.security}</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4"
            onSubmit={pw.handleSubmit(async (v) => {
              try {
                tokenStore.set(await authApi.changePassword(v.current, v.next));
                pw.reset();
                toast.success(t.settings.passwordChanged);
              } catch (e) {
                pw.setError("current", { message: errorMessage(e) });
              }
            })}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t.settings.currentPassword} error={pw.formState.errors.current?.message}>
                <Input type="password" autoComplete="current-password" {...pw.register("current")} />
              </Field>
              <Field label={t.settings.newPassword} error={pw.formState.errors.next?.message} hint={t.auth.passwordRules}>
                <Input type="password" autoComplete="new-password" {...pw.register("next")} />
              </Field>
            </div>
            <div>
              <Button type="submit" variant="primary" loading={pw.formState.isSubmitting}>{t.settings.changePassword}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
