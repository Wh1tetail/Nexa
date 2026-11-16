import { RotateCcw, UserMinus } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { EmptyState } from "@/components/common";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import type { ParticipantState } from "@/types/api";
import { fmtDate } from "@/utils/format";

export interface ParticipantRow {
  studentId: number;
  name: string;
  /** Set for excluded students (their history is kept). */
  removedAt: string | null;
  /** Extra line under the name (status, attempts, files...). */
  meta?: ReactNode;
  /** Right side (badge, score...). */
  aside?: ReactNode;
}

/** Students of a lesson / test / homework with the "active / excluded / all"
 *  filter, removal of one or several (with confirmation) and restoring. */
export function ParticipantList({
  rows,
  confirmTitle,
  confirmText,
  onRemove,
  onRestore,
  busy,
  defaultState = "active",
}: {
  rows: ParticipantRow[];
  confirmTitle: (n: number) => string;
  confirmText: string;
  onRemove: (studentIds: number[]) => Promise<unknown>;
  onRestore?: (studentId: number) => Promise<unknown>;
  busy?: boolean;
  defaultState?: ParticipantState;
}) {
  const { t, locale } = useI18n();
  const [state, setState] = useState<ParticipantState>(defaultState);
  const [selected, setSelected] = useState<number[]>([]);
  const [confirm, setConfirm] = useState<number[] | null>(null);

  const counts = useMemo(
    () => ({ active: rows.filter((r) => !r.removedAt).length, removed: rows.filter((r) => r.removedAt).length, all: rows.length }),
    [rows],
  );
  const shown = rows.filter((r) => state === "all" || (state === "active") === !r.removedAt);
  const selectable = shown.filter((r) => !r.removedAt).map((r) => r.studentId);
  // a student who was excluded or left the list can't stay selected
  useEffect(() => setSelected((s) => s.filter((id) => selectable.includes(id))), [selectable.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const allSelected = selectable.length > 0 && selectable.every((id) => selected.includes(id));

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Tabs value={state} onValueChange={(v) => setState(v as ParticipantState)}>
          <TabsList>
            {(["active", "removed", "all"] as const).map((s) => (
              <TabsTrigger key={s} value={s}>
                {t.participants[s]}
                <span className="tabular text-xs opacity-60">{counts[s]}</span>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        {selected.length > 0 && (
          <Button size="sm" variant="outline" className="text-danger-strong" onClick={() => setConfirm(selected)}>
            <UserMinus />
            {t.participants.removeSelected(selected.length)}
          </Button>
        )}
      </div>

      {shown.length ? (
        <ul className="grid gap-1">
          {selectable.length > 1 && (
            <li>
              <label className="flex cursor-pointer items-center gap-3 px-2.5 py-1.5 text-xs text-muted-foreground">
                <Checkbox
                  checked={allSelected}
                  onCheckedChange={(c) => setSelected(c === true ? selectable : [])}
                  aria-label={t.participants.selectAll}
                />
                {t.participants.selectAll}
              </label>
            </li>
          )}
          {shown.map((r) => (
            <li
              key={r.studentId}
              className={cn("flex items-center gap-3 rounded-xl p-2.5", r.removedAt ? "bg-secondary/50" : "hover:bg-secondary/60")}
            >
              {!r.removedAt ? (
                <Checkbox
                  checked={selected.includes(r.studentId)}
                  onCheckedChange={() => toggle(r.studentId)}
                  aria-label={r.name}
                />
              ) : (
                <span className="size-5 shrink-0" />
              )}
              <Avatar name={r.name} className={cn(r.removedAt && "opacity-60")} />
              <div className="min-w-0 flex-1">
                <p className={cn("truncate text-sm font-medium", r.removedAt ? "text-muted-foreground" : "text-primary")}>{r.name}</p>
                <div className="truncate text-xs text-muted-foreground">
                  {r.removedAt ? t.participants.removedOn(fmtDate(r.removedAt, locale)) : r.meta}
                  {r.removedAt && r.meta ? <> · {r.meta}</> : null}
                </div>
              </div>
              {r.aside}
              {r.removedAt ? (
                <>
                  <Badge variant="neutral" className="hidden sm:inline-flex">{t.participants.removedBadge}</Badge>
                  {onRestore && (
                    <Button size="sm" variant="ghost" disabled={busy} onClick={() => onRestore(r.studentId)}>
                      <RotateCcw />
                      <span className="hidden sm:inline">{t.participants.restore}</span>
                    </Button>
                  )}
                </>
              ) : (
                <Button
                  size="icon-sm"
                  variant="ghost"
                  className="hover:text-danger"
                  aria-label={`${t.participants.remove}: ${r.name}`}
                  title={t.participants.remove}
                  onClick={() => setConfirm([r.studentId])}
                >
                  <UserMinus />
                </Button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title={t.participants.empty} />
      )}

      <ConfirmDialog
        open={!!confirm}
        onOpenChange={(o) => !o && setConfirm(null)}
        title={confirm ? confirmTitle(confirm.length) : ""}
        description={
          confirm
            ? `${rows.filter((r) => confirm.includes(r.studentId)).map((r) => r.name).join(", ")}. ${confirmText}`
            : ""
        }
        confirmLabel={t.participants.remove}
        cancelLabel={t.common.cancel}
        destructive
        loading={busy}
        onConfirm={async () => {
          if (!confirm) return;
          try {
            await onRemove(confirm);
          } catch {
            return; // the caller shows the error; the dialog stays open
          }
          setSelected((s) => s.filter((id) => !confirm.includes(id)));
          setConfirm(null);
        }}
      />
    </div>
  );
}
