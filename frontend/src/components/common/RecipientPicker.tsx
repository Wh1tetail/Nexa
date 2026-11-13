import { useQuery } from "@tanstack/react-query";
import { Search, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { groupsApi, studentsApi } from "@/services/api";

interface Props {
  studentIds: number[];
  groupIds: number[];
  onChange: (v: { studentIds: number[]; groupIds: number[] }) => void;
  showGroups?: boolean;
  disabledStudentIds?: number[];
}

/** Pick students and/or groups as recipients for homework, tests and lessons. */
export function RecipientPicker({ studentIds, groupIds, onChange, showGroups = true, disabledStudentIds = [] }: Props) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const students = useQuery({ queryKey: ["students", "picker"], queryFn: () => studentsApi.list({ active: true }) });
  const groups = useQuery({ queryKey: ["groups"], queryFn: groupsApi.list, enabled: showGroups });

  const filtered = useMemo(
    () => (students.data ?? []).filter((s) => s.full_name.toLowerCase().includes(q.trim().toLowerCase())),
    [students.data, q],
  );

  const toggle = (list: number[], id: number) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  return (
    <div className="grid gap-3">
      {showGroups && (groups.data?.length ?? 0) > 0 && (
        <div className="flex flex-wrap gap-2">
          {groups.data!.map((g) => {
            const on = groupIds.includes(g.id);
            return (
              <button
                key={g.id}
                type="button"
                onClick={() => onChange({ studentIds, groupIds: toggle(groupIds, g.id) })}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors",
                  on ? "border-accent bg-accent-soft text-accent" : "hover:bg-secondary",
                )}
              >
                <Users className="size-3.5" />
                {g.name}
                <span className="text-xs opacity-70">{g.students.length}</span>
              </button>
            );
          })}
        </div>
      )}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.common.search} className="pl-9" />
      </div>
      <div className="max-h-56 overflow-y-auto rounded-xl border">
        {students.isLoading ? (
          <div className="space-y-2 p-3">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        ) : (
          filtered.map((s) => {
            const disabled = disabledStudentIds.includes(s.id);
            const checked = disabled || studentIds.includes(s.id);
            return (
              <label
                key={s.id}
                className={cn(
                  "flex cursor-pointer items-center gap-3 border-b px-3 py-2 last:border-0 hover:bg-secondary/60",
                  disabled && "cursor-default opacity-60",
                )}
              >
                <Checkbox
                  checked={checked}
                  disabled={disabled}
                  onCheckedChange={() => onChange({ studentIds: toggle(studentIds, s.id), groupIds })}
                />
                <Avatar name={s.full_name} className="size-7 text-[10px]" />
                <span className="min-w-0 flex-1 truncate text-sm">{s.full_name}</span>
                <span className="text-xs text-muted-foreground">{s.english_level}</span>
              </label>
            );
          })
        )}
        {!students.isLoading && !filtered.length && (
          <p className="p-4 text-center text-sm text-muted-foreground">{t.students.empty}</p>
        )}
      </div>
    </div>
  );
}
