import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { CardListSkeleton, EmptyState, ErrorState, Field, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { BOOK_MAX_MB, BookMetaFields, BookStatusBadge, PdfPicker } from "@/pages/books/shared";
import { booksApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Book, BookMeta } from "@/types/api";
import { fmtDate } from "@/utils/format";

const EMPTY_META: BookMeta = { title: "", author: null, language: "en", level: null };

function UploadDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState<BookMeta>(EMPTY_META);
  const [progress, setProgress] = useState<number | null>(null);

  const reset = () => {
    setFile(null);
    setMeta(EMPTY_META);
    setProgress(null);
  };
  const upload = useMutation({
    mutationFn: () => booksApi.upload(file!, { ...meta, title: meta.title.trim() }, setProgress),
    onSuccess: (b) => {
      qc.invalidateQueries({ queryKey: ["books"] });
      toast.success(t.books.uploaded);
      reset();
      onClose();
      navigate(`/methodist/books/${b.id}`);
    },
    onError: (e) => {
      setProgress(null);
      toast.error(errorMessage(e));
    },
  });
  const pick = (f: File) => {
    if (!f.name.toLowerCase().endsWith(".pdf")) return toast.error(t.books.onlyPdf);
    if (f.size > BOOK_MAX_MB * 1024 * 1024) return toast.error(t.files.tooBig(f.name, BOOK_MAX_MB));
    setFile(f);
    if (!meta.title.trim()) setMeta((m) => ({ ...m, title: f.name.replace(/\.pdf$/i, "").slice(0, 200) }));
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !upload.isPending && (reset(), onClose())}>
      <DialogContent>
        <DialogHeader><DialogTitle>{t.books.uploadTitle}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4">
          <Field label={t.books.file}>
            <PdfPicker file={file} onChange={pick} />
          </Field>
          <BookMetaFields value={meta} onChange={setMeta} />
          {progress !== null && (
            <div className="grid gap-1.5">
              <Progress value={progress} />
              <p className="text-xs text-muted-foreground">{t.books.uploading(progress)}</p>
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" disabled={upload.isPending} onClick={() => (reset(), onClose())}>{t.common.cancel}</Button>
          <Button disabled={!file || !meta.title.trim()} loading={upload.isPending} onClick={() => upload.mutate()}>
            {t.books.upload}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BookRow({ b }: { b: Book }) {
  const { t, locale } = useI18n();
  return (
    <Link to={`/methodist/books/${b.id}`} className="group block focus-visible:outline-none">
      <Card className="flex flex-col gap-3 p-4 transition-shadow group-hover:shadow-lift group-focus-visible:ring-2 group-focus-visible:ring-ring sm:flex-row sm:items-center sm:gap-4">
        <span className="hidden size-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent sm:flex">
          <BookOpen className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="break-words font-semibold text-primary">{b.title}</p>
          <p className="text-sm text-muted-foreground">
            {[b.author, t.books.lang[b.language], t.books.pages(b.page_count)].filter(Boolean).join(", ")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          {b.level && <Badge variant="neutral">{b.level}</Badge>}
          <BookStatusBadge status={b.status} />
          <span className="text-xs text-muted-foreground">{fmtDate(b.created_at, locale)}</span>
        </div>
      </Card>
    </Link>
  );
}

export default function BooksPage() {
  const { t } = useI18n();
  const [uploading, setUploading] = useState(false);
  const q = useQuery({ queryKey: ["books"], queryFn: booksApi.list });

  return (
    <div>
      <PageHeader
        title={t.books.title}
        subtitle={t.books.subtitle}
        actions={<Button onClick={() => setUploading(true)}><Plus />{t.books.upload}</Button>}
      />
      {q.isLoading ? (
        <CardListSkeleton rows={3} />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data?.length ? (
        <Card>
          <EmptyState
            icon={BookOpen}
            title={t.books.empty}
            text={t.books.emptyText}
            action={<Button onClick={() => setUploading(true)}><Plus />{t.books.upload}</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-3">
          {q.data.map((b) => (
            <BookRow key={b.id} b={b} />
          ))}
        </div>
      )}
      <UploadDialog open={uploading} onClose={() => setUploading(false)} />
    </div>
  );
}
