import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, GraduationCap, Presentation } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { homePath, useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { errorMessage } from "@/services/http";

const DEMO_PASSWORD = "Demo12345";

export default function LoginPage() {
  const { t } = useI18n();
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [show, setShow] = useState(false);

  const schema = z.object({
    email: z.string().trim().email(t.auth.invalidEmail),
    password: z.string().min(1, t.auth.passwordRequired),
  });
  type Values = z.infer<typeof schema>;

  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  async function onSubmit(v: Values) {
    try {
      const me = await login(v.email, v.password);
      toast.success(t.auth.welcomeBack);
      const from = (location.state as { from?: string } | null)?.from;
      const home = homePath(me.role);
      navigate(from && from.startsWith(home) ? from : home, { replace: true });
    } catch (e) {
      form.setError("password", { message: errorMessage(e) });
    }
  }

  const fillDemo = (email: string) => {
    form.setValue("email", email);
    form.setValue("password", DEMO_PASSWORD);
    form.handleSubmit(onSubmit)();
  };

  const { errors, isSubmitting } = form.formState;

  return (
    <div>
      <h1 className="text-2xl font-semibold">{t.auth.loginTitle}</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">{t.auth.loginSubtitle}</p>

      <form onSubmit={form.handleSubmit(onSubmit)} className="mt-8 grid gap-4" noValidate>
        <Field label={t.auth.email} htmlFor="email" error={errors.email?.message}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            placeholder="you@example.com"
            aria-invalid={!!errors.email}
            {...form.register("email")}
          />
        </Field>
        <Field
          label={
            <span className="flex w-full items-center justify-between">
              {t.auth.password}
              <Link to="/forgot-password" className="text-xs font-normal text-accent hover:underline">
                {t.auth.forgot}
              </Link>
            </span>
          }
          htmlFor="password"
          error={errors.password?.message}
        >
          <div className="relative">
            <Input
              id="password"
              type={show ? "text" : "password"}
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              className="pr-10"
              {...form.register("password")}
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="absolute right-1 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-primary"
              aria-label={show ? "Hide password" : "Show password"}
            >
              {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </Field>
        <Button type="submit" size="lg" className="mt-2" loading={isSubmitting}>
          {t.auth.submit}
        </Button>
      </form>

      {import.meta.env.DEV && (
        <div className="mt-8 rounded-xl border border-dashed p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t.auth.demoTitle}</p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button variant="outline" size="sm" onClick={() => fillDemo("teacher@lingua.school")} disabled={isSubmitting}>
              <Presentation />
              {t.auth.demoTeacher}
            </Button>
            <Button variant="outline" size="sm" onClick={() => fillDemo("anna@lingua.school")} disabled={isSubmitting}>
              <GraduationCap />
              {t.auth.demoStudent}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
