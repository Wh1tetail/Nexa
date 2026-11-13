import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { authApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { passwordSchema } from "@/utils/validation";

export default function ResetPasswordPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token");

  const schema = z
    .object({ password: passwordSchema(t), repeat: z.string() })
    .refine((v) => v.password === v.repeat, { message: t.auth.passwordsMismatch, path: ["repeat"] });
  type Values = z.infer<typeof schema>;
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { password: "", repeat: "" } });

  async function onSubmit(v: Values) {
    try {
      await authApi.reset(token!, v.password);
      toast.success(t.auth.resetDone);
      navigate("/login", { replace: true });
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  if (!token) {
    return (
      <div>
        <h1 className="text-2xl font-semibold">{t.auth.noToken}</h1>
        <Button asChild className="mt-6">
          <Link to="/forgot-password">{t.auth.forgotTitle}</Link>
        </Button>
      </div>
    );
  }

  const { errors, isSubmitting } = form.formState;
  return (
    <div>
      <h1 className="text-2xl font-semibold">{t.auth.resetTitle}</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">{t.auth.resetSubtitle}</p>
      <form onSubmit={form.handleSubmit(onSubmit)} className="mt-8 grid gap-4" noValidate>
        <Field label={t.auth.newPassword} htmlFor="password" error={errors.password?.message} hint={t.auth.passwordRules}>
          <Input id="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...form.register("password")} />
        </Field>
        <Field label={t.auth.repeatPassword} htmlFor="repeat" error={errors.repeat?.message}>
          <Input id="repeat" type="password" autoComplete="new-password" aria-invalid={!!errors.repeat} {...form.register("repeat")} />
        </Field>
        <Button type="submit" size="lg" loading={isSubmitting}>
          {t.auth.resetSubmit}
        </Button>
      </form>
    </div>
  );
}
