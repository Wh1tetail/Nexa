import {
  ArrowRight,
  BookOpenCheck,
  CalendarCheck,
  Check,
  ClipboardList,
  CreditCard,
  Mail,
  Menu,
  Phone,
  Sparkles,
  UserRound,
  Users,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Logo } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { homePath, useAuth } from "@/contexts/AuthContext";
import { LOCALES, useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";

/** School contacts shown on the landing page. */
const WHATSAPP_URL = "https://wa.me/message/BKGS736WHM6NI1";
const CONTACT_PHONE = "+7 705 654 0935";
const CONTACT_EMAIL = "kadrzhnvdaniyar@gmail.com";

function LanguageToggle() {
  const { locale, setLocale } = useI18n();
  return (
    <div className="flex rounded-lg bg-secondary p-0.5 text-xs font-medium">
      {LOCALES.map((l) => (
        <button
          key={l.code}
          onClick={() => setLocale(l.code)}
          aria-label={l.name}
          title={l.name}
          className={cn(
            "rounded-md px-2 py-1 transition-colors",
            locale === l.code ? "bg-background text-primary shadow-sm" : "text-muted-foreground",
          )}
        >
          {l.short}
        </button>
      ))}
    </div>
  );
}

function HeroMockup() {
  const { t } = useI18n();
  return (
    <div className="relative mx-auto w-full max-w-md lg:max-w-none">
      <div className="absolute -inset-6 -z-10 rounded-[2rem] bg-gradient-to-br from-accent/20 via-accent/5 to-transparent blur-2xl" />
      <Card className="p-5 shadow-lift sm:p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">{t.subscription.title}</p>
            <p className="mt-1 font-semibold text-primary">12 / 16 {t.subscription.left.toLowerCase()}</p>
          </div>
          <span className="rounded-full bg-success-soft px-2.5 py-1 text-xs font-medium text-[hsl(142_72%_29%)]">
            {t.status.subscription.active}
          </span>
        </div>
        <Progress value={68} className="mt-4" indicatorClassName="bg-success" />
        <div className="mt-6 grid grid-cols-3 gap-3 text-center">
          {[
            ["24", t.attendance.visited],
            ["92%", t.attendance.rate],
            ["B1", t.dashboard.level],
          ].map(([v, l]) => (
            <div key={l} className="rounded-xl bg-secondary p-3">
              <p className="text-lg font-semibold text-primary">{v}</p>
              <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{l}</p>
            </div>
          ))}
        </div>
      </Card>
      <Card className="absolute -bottom-8 -left-2 hidden w-60 p-4 shadow-lift sm:block lg:-left-10">
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-xl bg-success-soft text-[hsl(142_72%_32%)]">
            <Check className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-primary">Essay: My last vacation</p>
            <p className="text-xs text-muted-foreground">{t.status.submission.reviewed} · 9/10</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

function Feature({ icon: Icon, title, text }: { icon: LucideIcon; title: string; text: string }) {
  return (
    <Card className="p-6 transition-shadow hover:shadow-lift">
      <span className="flex size-11 items-center justify-center rounded-xl bg-accent-soft text-accent">
        <Icon className="size-5" />
      </span>
      <h3 className="mt-5 font-semibold">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{text}</p>
    </Card>
  );
}

export default function LandingPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [menu, setMenu] = useState(false);
  const cabinet = user ? homePath(user.role) : "/login";
  const l = t.landing;

  const nav = [
    ["#features", l.navFeatures],
    ["#format", l.navFormat],
    ["#contacts", l.navContacts],
  ];

  return (
    <div className="min-h-dvh bg-background">
      <header className="sticky top-0 z-30 border-b border-transparent bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/70">
        <div className="container flex h-16 items-center gap-6">
          <Logo />
          <nav className="hidden flex-1 items-center gap-6 text-sm text-muted-foreground md:flex">
            {nav.map(([href, label]) => (
              <a key={href} href={href} className="transition-colors hover:text-primary">
                {label}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <LanguageToggle />
            <Button variant="ghost" asChild className="hidden sm:inline-flex">
              <Link to={cabinet}>{user ? user.full_name.split(" ")[0] : l.login}</Link>
            </Button>
            <Button asChild className="hidden sm:inline-flex">
              <a href="#cta">{l.startLearning}</a>
            </Button>
            <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMenu((v) => !v)} aria-label={t.nav.menu}>
              <Menu className="!size-5" />
            </Button>
          </div>
        </div>
        {menu && (
          <div className="container animate-fade-in border-t pb-4 md:hidden">
            <nav className="grid py-2">
              {nav.map(([href, label]) => (
                <a key={href} href={href} onClick={() => setMenu(false)} className="rounded-lg px-2 py-3 text-sm font-medium text-primary hover:bg-secondary">
                  {label}
                </a>
              ))}
            </nav>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" asChild>
                <Link to={cabinet}>{l.login}</Link>
              </Button>
              <Button asChild>
                <a href="#cta" onClick={() => setMenu(false)}>{l.startLearning}</a>
              </Button>
            </div>
          </div>
        )}
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 -z-10 h-[520px] bg-gradient-to-b from-secondary to-background" />
        <div className="container grid items-center gap-14 py-14 sm:py-20 lg:grid-cols-[1.1fr_1fr] lg:py-28">
          <div className="animate-fade-in">
            <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-medium text-accent shadow-sm">
              <Sparkles className="size-3.5" />
              {l.heroBadge}
            </span>
            <h1 className="mt-5 text-balance text-4xl font-semibold leading-[1.08] sm:text-5xl lg:text-6xl">
              {l.heroTitle}
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">{l.heroText}</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button size="lg" asChild>
                <a href="#cta">
                  {l.startLearning}
                  <ArrowRight />
                </a>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to={cabinet}>{l.login}</Link>
              </Button>
            </div>
            <dl className="mt-12 grid max-w-md grid-cols-3 gap-6">
              {[
                ["1 200+", l.stat1],
                ["4.9", l.stat2],
                ["6", l.stat3],
              ].map(([v, k]) => (
                <div key={k}>
                  <dt className="text-2xl font-semibold text-primary">{v}</dt>
                  <dd className="mt-1 text-xs leading-snug text-muted-foreground">{k}</dd>
                </div>
              ))}
            </dl>
          </div>
          <HeroMockup />
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-16 py-16 sm:py-24">
        <div className="container">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-semibold sm:text-4xl">{l.featuresTitle}</h2>
            <p className="mt-3 text-muted-foreground">{l.featuresText}</p>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Feature icon={UserRound} title={l.f1Title} text={l.f1Text} />
            <Feature icon={ClipboardList} title={l.f2Title} text={l.f2Text} />
            <Feature icon={BookOpenCheck} title={l.f3Title} text={l.f3Text} />
            <Feature icon={CreditCard} title={l.f4Title} text={l.f4Text} />
          </div>
        </div>
      </section>

      {/* Format */}
      <section id="format" className="scroll-mt-16 bg-secondary py-16 sm:py-24">
        <div className="container">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-semibold sm:text-4xl">{l.formatTitle}</h2>
            <p className="mt-3 text-muted-foreground">{l.formatText}</p>
          </div>
          <div className="mt-10 grid gap-4 lg:grid-cols-3">
            {[
              { icon: UserRound, title: l.fmt1Title, text: l.fmt1Text, featured: false },
              { icon: Users, title: l.fmt2Title, text: l.fmt2Text, featured: true },
              { icon: Zap, title: l.fmt3Title, text: l.fmt3Text, featured: false },
            ].map(({ icon: Icon, title, text, featured }) => (
              <Card key={title} className={cn("flex flex-col p-7", featured && "border-accent/40 ring-1 ring-accent/30")}>
                <Icon className={cn("size-6", featured ? "text-accent" : "text-primary")} />
                <h3 className="mt-5 text-lg font-semibold">{title}</h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{text}</p>
                <ul className="mt-6 grid gap-2.5 text-sm">
                  {[l.fmtPoint1, l.fmtPoint2, l.fmtPoint3].map((p) => (
                    <li key={p} className="flex items-center gap-2 text-primary">
                      <Check className="size-4 text-success" />
                      {p}
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section id="cta" className="scroll-mt-16 py-16 sm:py-24">
        <div className="container">
          <div className="relative overflow-hidden rounded-3xl bg-primary px-6 py-12 text-center sm:px-12 sm:py-16">
            <div className="absolute -right-20 -top-20 size-72 rounded-full bg-accent/40 blur-3xl" />
            <div className="absolute -bottom-24 -left-10 size-72 rounded-full bg-accent/20 blur-3xl" />
            <div className="relative">
              <CalendarCheck className="mx-auto size-10 text-white/80" />
              <h2 className="mt-4 text-3xl font-semibold text-white sm:text-4xl">{l.ctaTitle}</h2>
              <p className="mx-auto mt-3 max-w-lg text-white/70">{l.ctaText}</p>
              <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
                <Button size="lg" asChild>
                  <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer">{l.ctaButton}</a>
                </Button>
                <Button size="lg" variant="outline" className="border-white/20 bg-white/10 text-white hover:bg-white/20" asChild>
                  <Link to={cabinet}>{l.login}</Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer id="contacts" className="border-t bg-background">
        <div className="container grid gap-10 py-12 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <Logo />
            <p className="mt-3 max-w-sm text-sm text-muted-foreground">{t.appTagline}</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-primary">{l.contactsTitle}</p>
            <ul className="mt-4 grid gap-3 text-sm text-muted-foreground">
              <li className="flex items-center gap-2">
                <Phone className="size-4 shrink-0" />
                <a href={`tel:${CONTACT_PHONE.replace(/\s/g, "")}`} className="hover:text-primary">{CONTACT_PHONE}</a>
              </li>
              <li className="flex min-w-0 items-center gap-2">
                <Mail className="size-4 shrink-0" />
                <a href={`mailto:${CONTACT_EMAIL}`} className="min-w-0 break-all hover:text-primary">{CONTACT_EMAIL}</a>
              </li>
            </ul>
          </div>
          <div>
            <p className="text-sm font-semibold text-primary">{l.hours}</p>
            <div className="mt-4 grid gap-2 text-sm">
              <a href="#features" className="text-muted-foreground hover:text-primary">{l.navFeatures}</a>
              <a href="#format" className="text-muted-foreground hover:text-primary">{l.navFormat}</a>
              <Link to="/login" className="text-muted-foreground hover:text-primary">{l.login}</Link>
            </div>
          </div>
        </div>
        <div className="border-t">
          <p className="container py-5 text-xs text-muted-foreground">
            © {new Date().getFullYear()} {t.appName}. {l.rights}
          </p>
        </div>
      </footer>
    </div>
  );
}
