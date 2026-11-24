import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { booksApi, libraryApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { ENGLISH_LEVELS, type Book, type EnglishLevel, type LibrarySection } from "@/types/api";

/** Sections as a flat list, children under their parent ("— " per level). */
function flatSections(all: LibrarySection[]): { id: number; label: string }[] {
  const out: { id: number; label: string }[] = [];
  const walk = (parent: number | null, depth: number) => {
    for (const s of all.filter((x) => x.parent_id === parent).sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))) {
      out.push({ id: s.id, label: `${"— ".repeat(depth)}${s.name}` });
      walk(s.id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}

/** Approved questions into a new unpublished library test or the end of an unpublished one. */
export function ExportDialog({ book, ids, open, onClose }: { book: Book; ids: number[]; open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [title, setTitle] = useState(book.title);
  const [level, setLevel] = useState<EnglishLevel | "">(book.level ?? "");
  const [sectionId, setSectionId] = useState("");
  const [tags, setTags] = useState("");
  const [testId, setTestId] = useState("");
  useEffect(() => {
    if (open) {
      setTitle(book.title.slice(0, 200));
      setLevel(book.level ?? "");
    }
  }, [open, book]);

  const sections = useQuery({ queryKey: ["library", "sections"], queryFn: libraryApi.sections, enabled: open });
  const drafts = useQuery({
    queryKey: ["library", "tests", { published: false }],
    queryFn: () => libraryApi.tests({ published: false }),
    enabled: open && mode === "existing",
  });
  const options = useMemo(() => flatSections(sections.data ?? []), [sections.data]);

  const send = useMutation({
    mutationFn: () =>
      booksApi.exportDrafts(
        book.id,
        mode === "existing"
          ? { draft_ids: ids, test_id: Number(testId) }
          : {
              draft_ids: ids,
              title: title.trim(),
              level: level || null,
              section_ids: sectionId ? [Number(sectionId)] : [],
              tags: tags.split(",").map((x) => x.trim()).filter(Boolean),
            },
      ),
    onSuccess: (test) => {
      qc.invalidateQueries({ queryKey: ["books", book.id] });
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success(t.books.exportDone(ids.length), {
        action: { label: t.books.openTest, onClick: () => navigate(`/methodist/library/tests/${test.id}`) },
      });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const ready = mode === "new" ? title.trim().length > 0 : testId !== "";

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !send.isPending && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>{t.books.exportTitle}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4">
          <p className="text-sm text-muted-foreground">{t.books.exportHint}</p>
          <Tabs value={mode} onValueChange={(v) => setMode(v as "new" | "existing")}>
            <TabsList className="w-full">
              <TabsTrigger value="new" className="flex-1">{t.books.exportNew}</TabsTrigger>
              <TabsTrigger value="existing" className="flex-1">{t.books.exportExisting}</TabsTrigger>
            </TabsList>
          </Tabs>
          {mode === "new" ? (
            <>
              <Field label={t.books.exportTestTitle}>
                <Input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t.books.exportLevel}>
                  <NativeSelect value={level} onChange={(e) => setLevel(e.target.value as EnglishLevel | "")}>
                    <option value="">{t.books.exportNoLevel}</option>
                    {ENGLISH_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
                  </NativeSelect>
                </Field>
                <Field label={t.books.exportSection}>
                  <NativeSelect value={sectionId} onChange={(e) => setSectionId(e.target.value)}>
                    <option value="">{t.books.exportNoSection}</option>
                    {options.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                  </NativeSelect>
                </Field>
              </div>
              <Field label={t.books.exportTags} hint={t.books.exportTagsHint}>
                <Input value={tags} maxLength={300} onChange={(e) => setTags(e.target.value)} />
              </Field>
            </>
          ) : (
            <Field label={t.books.exportPickTest}>
              {drafts.data && drafts.data.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t.books.exportNoTests}</p>
              ) : (
                <NativeSelect value={testId} disabled={drafts.isLoading} onChange={(e) => setTestId(e.target.value)}>
                  <option value="">—</option>
                  {(drafts.data ?? []).map((x) => (
                    <option key={x.id} value={x.id}>{x.title} ({x.questions_count})</option>
                  ))}
                </NativeSelect>
              )}
            </Field>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" disabled={send.isPending} onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={!ready} loading={send.isPending} onClick={() => send.mutate()}>{t.books.exportSubmit(ids.length)}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
