import { Monitor, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/contexts/I18nContext";
import { useTheme, type ThemeChoice } from "@/contexts/ThemeContext";
import { cn } from "@/lib/utils";

/** Header button: switches between light and dark (an explicit choice). */
export function ThemeToggle({ className }: { className?: string }) {
  const { t } = useI18n();
  const { resolved, setTheme } = useTheme();
  const next = resolved === "dark" ? "light" : "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      className={className}
      onClick={() => setTheme(next)}
      aria-label={next === "dark" ? t.theme.toDark : t.theme.toLight}
      title={next === "dark" ? t.theme.toDark : t.theme.toLight}
    >
      {resolved === "dark" ? <Sun className="!size-5" /> : <Moon className="!size-5" />}
    </Button>
  );
}

const OPTIONS: { value: ThemeChoice; icon: typeof Sun }[] = [
  { value: "light", icon: Sun },
  { value: "dark", icon: Moon },
  { value: "system", icon: Monitor },
];

/** Settings: light / dark / follow the device. */
export function ThemePicker() {
  const { t } = useI18n();
  const { theme, setTheme } = useTheme();
  return (
    <div role="radiogroup" aria-label={t.theme.title} className="inline-flex flex-wrap rounded-xl bg-secondary p-1">
      {OPTIONS.map(({ value, icon: Icon }) => (
        <button
          key={value}
          role="radio"
          aria-checked={theme === value}
          onClick={() => setTheme(value)}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all",
            theme === value ? "bg-background text-primary shadow-sm" : "text-muted-foreground hover:text-primary",
          )}
        >
          <Icon className="size-4" />
          {t.theme[value]}
        </button>
      ))}
    </div>
  );
}
