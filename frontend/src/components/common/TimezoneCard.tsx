import { Globe, LocateFixed } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { authApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { browserTimeZone, fmtDateTime } from "@/utils/format";

/** Russian zones first: most users of the school are there. */
const POPULAR = [
  "Europe/Kaliningrad",
  "Europe/Moscow",
  "Europe/Samara",
  "Asia/Yekaterinburg",
  "Asia/Omsk",
  "Asia/Novosibirsk",
  "Asia/Krasnoyarsk",
  "Asia/Irkutsk",
  "Asia/Yakutsk",
  "Asia/Vladivostok",
  "Asia/Magadan",
  "Asia/Kamchatka",
];

function allZones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  try {
    const zones = intl.supportedValuesOf?.("timeZone");
    if (zones?.length) return zones;
  } catch {
    /* old browser */
  }
  return [...POPULAR, "UTC"];
}

function offsetLabel(zone: string): string {
  try {
    const part = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "shortOffset" })
      .formatToParts(new Date())
      .find((p) => p.type === "timeZoneName")?.value;
    return part === "GMT" ? "UTC" : (part ?? "").replace("GMT", "UTC");
  } catch {
    return "";
  }
}

export function TimezoneCard() {
  const { t, locale } = useI18n();
  const { user, setUser } = useAuth();
  const [saving, setSaving] = useState(false);
  const current = user?.timezone ?? browserTimeZone();
  const detected = browserTimeZone();

  const { popular, others } = useMemo(() => {
    const zones = allZones();
    const set = new Set(zones);
    const top = POPULAR.filter((z) => set.has(z));
    return { popular: top, others: zones.filter((z) => !top.includes(z)) };
  }, []);

  async function save(zone: string) {
    if (zone === user?.timezone) return;
    setSaving(true);
    try {
      setUser(await authApi.updateMe({ timezone: zone }));
      toast.success(t.settings.timezoneSaved, { description: `${zone} · ${offsetLabel(zone)}` });
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  const option = (z: string) => (
    <option key={z} value={z}>
      {z.replace(/_/g, " ")} ({offsetLabel(z)})
    </option>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Globe className="size-4 text-accent" />
          {t.settings.timezone}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t.settings.timezoneHint}</p>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <NativeSelect
            value={current}
            disabled={saving}
            onChange={(e) => save(e.target.value)}
            aria-label={t.settings.timezone}
            className="sm:flex-1"
          >
            {!popular.includes(current) && !others.includes(current) && option(current)}
            <optgroup label={t.settings.timezonePopular}>{popular.map(option)}</optgroup>
            <optgroup label={t.settings.timezoneAll}>{others.map(option)}</optgroup>
          </NativeSelect>
          {detected !== current && (
            <Button variant="outline" onClick={() => save(detected)} loading={saving}>
              <LocateFixed />
              {t.settings.timezoneDetect}
            </Button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {t.settings.timezoneNow}: {fmtDateTime(new Date().toISOString(), locale)}
        </p>
      </CardContent>
    </Card>
  );
}
