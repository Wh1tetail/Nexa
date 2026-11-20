import { Menu } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Logo } from "@/components/common";
import { BrandMark } from "@/components/common/BrandMark";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { Button } from "@/components/ui/button";
import { homePath, useAuth } from "@/contexts/AuthContext";
import { LOCALES, useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";

import "./landing.css";

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
          type="button"
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

/** A real screenshot of the student account, in the light and the dark theme (the page shows the one that matches). */
const LEVELS = ["A1", "A2", "B1", "B2", "C1"];

const SIZES: Record<string, [number, number]> = { cabinet: [2880, 1800], lesson: [1800, 900], achievements: [2260, 1412] };

function Screen({ name, alt, eager }: { name: string; alt: string; eager?: boolean }) {
  const [width, height] = SIZES[name];
  const common = { width, height, alt, decoding: "async" as const };
  return (
    <div className="l-frame" data-slot={name} data-kind="product" data-alt={alt}>
      <img
        className="shot--light"
        src={`/landing/${name}-light.webp`}
        {...common}
        {...(eager ? { fetchPriority: "high" as const } : { loading: "lazy" as const })}
      />
      <img className="shot--dark" src={`/landing/${name}-dark.webp`} loading="lazy" {...common} />
    </div>
  );
}

export default function LandingPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [menu, setMenu] = useState(false);
  const cabinet = user ? homePath(user.role) : "/login";
  const l = t.landing;

  const nav = [
    ["#features", l.navSteps],
    ["#format", l.navFormat],
    ["#contacts", l.navContacts],
  ];
  const formats = [
    [l.fmt1Title, l.fmt1Text],
    [l.fmt2Title, l.fmt2Text],
    [l.fmt3Title, l.fmt3Text],
  ];

  return (
    <div className="landing">
      <div className="l-banner">
        <p className="l-wrap">
          <span>{l.banner}</span>
          <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer">{l.bannerLink}</a>
        </p>
      </div>

      <header className="l-nav">
        <div className="l-wrap l-nav__bar">
          <Logo />
          <nav className="l-nav__links" aria-label={l.stepsLabel}>
            {nav.map(([href, label]) => (
              <a key={href} href={href}>{label}</a>
            ))}
          </nav>
          <div className="l-nav__end">
            <LanguageToggle />
            <ThemeToggle />
            <Link to={cabinet} className="l-btn l-btn--quiet l-btn--sm l-hide-md">
              {user ? user.full_name.split(" ")[0] : l.login}
            </Link>
            <a href="#cta" className="l-btn l-btn--sm l-hide-md">{l.startLearning}</a>
            <Button variant="ghost" size="icon" className="l-show-md" onClick={() => setMenu((v) => !v)} aria-label={t.nav.menu} aria-expanded={menu}>
              <Menu className="!size-5" />
            </Button>
          </div>
        </div>
        {menu && (
          <div className="l-wrap l-nav__menu l-show-md">
            <nav>
              {nav.map(([href, label]) => (
                <a key={href} href={href} onClick={() => setMenu(false)} className="l-menu-link">{label}</a>
              ))}
            </nav>
            <div className="l-nav__menu-actions">
              <Link to={cabinet} className="l-btn l-btn--quiet">{l.login}</Link>
              <a href="#cta" onClick={() => setMenu(false)} className="l-btn">{l.startLearning}</a>
            </div>
          </div>
        )}
      </header>

      <main>
        <section className="l-hero">
          <div className="l-wrap l-grid">
            <div className="l-hero__text">
              <h1>{l.heroTitle}</h1>
              <p className="l-lead">{l.heroText}</p>
              <div className="l-hero__actions">
                <a href="#cta" className="l-btn">{l.startLearning}</a>
                <Link to={cabinet} className="l-btn l-btn--quiet">{l.login}</Link>
              </div>
            </div>
            <figure className="l-hero__shot">
              <Screen name="cabinet" alt={l.heroCaption} eager />
              <figcaption className="l-caption">{l.heroCaption}</figcaption>
            </figure>
          </div>
        </section>

        <ol className="l-steps" id="features" aria-label={l.stepsLabel}>
          <li className="l-step">
            <div className="l-wrap l-grid">
              <div className="l-step__head">
                <h2>{l.s1Title}</h2>
                <p className="l-body">{l.s1Text}</p>
                <p>
                  <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="l-link">{l.s1Link}</a>
                </p>
              </div>
              <figure className="l-levels">
                <ol>
                  {LEVELS.map((lv) => (
                    <li key={lv}>{lv}</li>
                  ))}
                </ol>
                <figcaption className="l-caption">{l.s1Levels}</figcaption>
              </figure>
            </div>
          </li>

          <li className="l-step" id="format">
            <div className="l-wrap l-grid">
              <div className="l-split-head">
                <h2>{l.s2Title}</h2>
                <p className="l-body">{l.s2Text}</p>
              </div>
              <div className="l-rows-wrap">
                <ul className="l-rows l-grid">
                  {formats.map(([title, text]) => (
                    <li key={title}>
                      <h3>{title}</h3>
                      <p>{text}</p>
                    </li>
                  ))}
                </ul>
                <p className="l-note">{l.s2Note}</p>
              </div>
            </div>
          </li>

          <li className="l-step">
            <div className="l-wrap l-grid">
              <div className="l-step__head l-step__head--wide">
                <h2>{l.s3Title}</h2>
                <p className="l-body">{l.s3Text}</p>
              </div>
              <figure className="l-showcase">
                <Screen name="lesson" alt={l.s3Caption} />
                <figcaption className="l-caption">{l.s3Caption}</figcaption>
              </figure>
            </div>
          </li>

          <li className="l-step">
            <div className="l-wrap l-grid">
              <div className="l-pair-text">
                <h2>{l.s4Title}</h2>
                <p className="l-body">{l.s4Text}</p>
              </div>
              <figure className="l-pair-shot">
                <Screen name="achievements" alt={l.s4Caption} />
                <figcaption className="l-caption">{l.s4Caption}</figcaption>
              </figure>
            </div>
          </li>
        </ol>

        <section className="l-close" id="cta">
          <div className="l-wrap l-grid">
            <div className="l-close__text">
              <h2>{l.ctaTitle}</h2>
              <p className="l-lead">{l.ctaText}</p>
              <div className="l-hero__actions">
                <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="l-btn">{l.ctaButton}</a>
                <Link to={cabinet} className="l-btn l-btn--quiet">{l.login}</Link>
              </div>
            </div>
            <div className="l-close__contacts" id="contacts">
              <h3>{l.contactsTitle}</h3>
              <dl>
                <div>
                  <dt>{l.hoursLabel}</dt>
                  <dd>{l.hours}</dd>
                </div>
                <div>
                  <dt>{l.phoneLabel}</dt>
                  <dd><a href={`tel:${CONTACT_PHONE.replace(/\s/g, "")}`} className="l-link">{CONTACT_PHONE}</a></dd>
                </div>
                <div>
                  <dt>{l.emailLabel}</dt>
                  <dd><a href={`mailto:${CONTACT_EMAIL}`} className="l-link">{CONTACT_EMAIL}</a></dd>
                </div>
              </dl>
            </div>
          </div>
        </section>
      </main>

      <footer className="l-footer">
        <div className="l-wrap">
          <Link to="/" className="l-mast" aria-label={t.appName}>
            <BrandMark className="l-mast__mark" />
            <span className="l-mast__word">{t.appName}</span>
          </Link>
          <div className="l-footer__row">
            <p>{t.appTagline}. © {new Date().getFullYear()} {t.appName}</p>
            <nav className="l-footer__links" aria-label={t.appName}>
              <a href="#features">{l.navSteps}</a>
              <a href="#format">{l.navFormat}</a>
              <Link to="/login">{l.login}</Link>
            </nav>
          </div>
        </div>
      </footer>
    </div>
  );
}
