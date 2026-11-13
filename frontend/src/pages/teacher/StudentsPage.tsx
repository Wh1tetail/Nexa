import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Plus, Search, Users } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { SubscriptionBadge } from "@/components/common/StatusBadges";
import { StudentFormDialog } from "@/components/students/StudentFormDialog";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/contexts/I18nContext";
import { groupsApi, studentsApi, type StudentFilters } from "@/services/api";
import { ENGLISH_LEVELS, type EnglishLevel, type SubscriptionStatus } from "@/types/api";
import { fmtDate } from "@/utils/format";

export default function StudentsPage() {
  const { t, locale } = useI18n();
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState<EnglishLevel | "">("");
  const [groupId, setGroupId] = useState<number | "">("");
  const [subStatus, setSubStatus] = useState<SubscriptionStatus | "">("");
  const [creating, setCreating] = useState(false);
  const deferredSearch = useDeferredValue(search);

  const filters: StudentFilters = { search: deferredSearch, level, group_id: groupId, subscription_status: subStatus };
  const q = useQuery({ queryKey: ["students", filters], queryFn: () => studentsApi.list(filters), placeholderData: (p) => p });
  const groups = useQuery({ queryKey: ["groups"], queryFn: groupsApi.list });
  const hasFilters = !!(search || level || groupId || subStatus);

  return (
    <div>
      <PageHeader
        title={t.students.title}
        subtitle={q.data ? t.common.studentsCount(q.data.length) : t.students.subtitle}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus />
            {t.students.add}
          </Button>
        }
      />

      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-[1fr_auto_auto_auto]">
        <div className="relative sm:col-span-2 lg:col-span-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t.students.searchPlaceholder} className="pl-9" />
        </div>
        <NativeSelect value={level} onChange={(e) => setLevel(e.target.value as EnglishLevel | "")} className="lg:w-36">
          <option value="">{t.students.allLevels}</option>
          {ENGLISH_LEVELS.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </NativeSelect>
        <NativeSelect value={groupId} onChange={(e) => setGroupId(e.target.value ? Number(e.target.value) : "")} className="lg:w-44">
          <option value="">{t.students.allGroups}</option>
          {groups.data?.map((g) => (
            <option key={g.id} value={g.id}>{g.name}</option>
          ))}
        </NativeSelect>
        <NativeSelect value={subStatus} onChange={(e) => setSubStatus(e.target.value as SubscriptionStatus | "")} className="sm:col-span-2 lg:col-span-1 lg:w-48">
          <option value="">{t.students.allStatuses}</option>
          {(["active", "expiring_soon", "expired", "frozen"] as const).map((s) => (
            <option key={s} value={s}>{t.status.subscription[s]}</option>
          ))}
        </NativeSelect>
      </div>

      {q.isLoading ? (
        <CardListSkeleton rows={6} />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data?.length ? (
        <Card>
          <EmptyState
            icon={Users}
            title={t.students.empty}
            text={t.students.emptyHint}
            action={
              hasFilters ? (
                <Button variant="outline" onClick={() => { setSearch(""); setLevel(""); setGroupId(""); setSubStatus(""); }}>
                  {t.common.resetFilters}
                </Button>
              ) : (
                <Button onClick={() => setCreating(true)}><Plus />{t.students.add}</Button>
              )
            }
          />
        </Card>
      ) : (
        <>
          {/* Mobile: cards */}
          <Card className="divide-y md:hidden">
            {q.data.map((s) => (
              <Link key={s.id} to={`/teacher/students/${s.id}`} className="flex items-center gap-3 p-4 hover:bg-secondary/50">
                <Avatar name={s.full_name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-primary">{s.full_name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {s.english_level}
                    {s.lessons_left !== null && ` · ${t.students.lessonsLeft}: ${s.lessons_left}`}
                  </p>
                </div>
                <SubscriptionBadge status={s.subscription_status} />
              </Link>
            ))}
          </Card>
          {/* Desktop: table */}
          <Card className="hidden overflow-hidden md:block">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t.common.student}</TableHead>
                  <TableHead>{t.students.level}</TableHead>
                  <TableHead>{t.common.groups}</TableHead>
                  <TableHead>{t.subscription.title}</TableHead>
                  <TableHead className="text-right">{t.students.lessonsLeft}</TableHead>
                  <TableHead className="w-8" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((s) => (
                  <TableRow key={s.id} className="group cursor-pointer">
                    <TableCell>
                      <Link to={`/teacher/students/${s.id}`} className="flex items-center gap-3">
                        <Avatar name={s.full_name} />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-primary">
                            {s.full_name}
                            {!s.is_active && <Badge variant="neutral" className="ml-2">{t.students.inactive}</Badge>}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">{s.email}</p>
                        </div>
                      </Link>
                    </TableCell>
                    <TableCell><Badge variant="neutral">{s.english_level}</Badge></TableCell>
                    <TableCell className="max-w-[180px] truncate text-muted-foreground">
                      {s.groups.map((g) => g.name).join(", ") || "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col items-start gap-1">
                        <SubscriptionBadge status={s.subscription_status} />
                        {s.subscription_end && (
                          <span className="text-xs text-muted-foreground">{t.common.to} {fmtDate(s.subscription_end, locale)}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="tabular text-right font-medium text-primary">{s.lessons_left ?? "—"}</TableCell>
                    <TableCell>
                      <Link to={`/teacher/students/${s.id}`} aria-label={t.common.open}>
                        <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      <StudentFormDialog open={creating} onOpenChange={setCreating} />
    </div>
  );
}
