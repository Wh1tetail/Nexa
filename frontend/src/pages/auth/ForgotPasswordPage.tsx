import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, MailCheck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { authApi } from "@/services/api";
import { errorMessage } from "@/services/http";

export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const [sent, setSent] = useState<{ detail: string; dev_reset_url: string | null } | null>(null);
  const schema = z.object({ email: z.string().trim().email(t.auth.invalidEmail) });
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { email: "" } });

  async function onSubmit(v: z.infer<typeof schema>) {
    try {
      setSent(await authApi.forgot(v.email));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <div>
      <Link to="/login" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.auth.backToLogin}
      </Link>
      <h1 className="text-2xl font-semibold">{t.auth.forgotTitle}</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">{t.auth.forgotSubtitle}</p>

      {sent ? (
        <div className="mt-8 animate-fade-in rounded-2xl border bg-secondary/50 p-5">
          <MailCheck className="size-8 text-success" />
          <p className="mt-3 text-sm text-primary">{sent.detail}</p>
          {sent.dev_reset_url && (
            <div className="mt-4 rounded-xl border border-dashed border-warning/60 bg-warning-soft p-3 text-xs">
              <p className="text-warning-strong">{t.auth.devLink}:</p>
              <a href={sent.dev_reset_url} className="mt-1 block break-all font-medium text-accent hover:underline">
                {sent.dev_reset_url}
              </a>
            </div>
          )}
        </div>
      ) : (
        <form onSubmit={form.handleSubmit(onSubmit)} className="mt-8 grid gap-4" noValidate>
          <Field label={t.auth.email} htmlFor="email" error={form.formState.errors.email?.message}>
            <Input id="email" type="email" autoComplete="email" aria-invalid={!!form.formState.errors.email} {...form.register("email")} />
          </Field>
          <Button type="submit" size="lg" loading={form.formState.isSubmitting}>
            {t.auth.sendLink}
          </Button>
        </form>
      )}
    </div>
  );
}
