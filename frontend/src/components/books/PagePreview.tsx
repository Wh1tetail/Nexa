import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ScanLine } from "lucide-react";
import { useEffect, useState } from "react";

import { CardListSkeleton, ErrorState } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { booksApi } from "@/services/api";
import type { Book } from "@/types/api";

const STEP = 5;

/** The extracted text, a few pages at a time (what the AI will read later). */
export function PagePreview({ book, range }: { book: Book; range: { from: number; to: number } | null }) {
  const { t } = useI18n();
  const total = book.page_count;
  const [from, setFrom] = useState(1);
  const [jump, setJump] = useState("1");
  useEffect(() => {
    if (range) {
      setFrom(range.from);
      setJump(String(range.from));
    }
  }, [range]);
  const to = Math.min(total, from + STEP - 1);
  const q = useQuery({
    queryKey: ["books", book.id, "pages", from, to],
    queryFn: () => booksApi.pages(book.id, from, to),
    placeholderData: keepPreviousData,
  });
  const go = (page: number) => {
    const p = Math.max(1, Math.min(total, page));
    setFrom(p);
    setJump(String(p));
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">{t.books.pagesShown(from, to, total)}</p>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-sm" aria-label={t.books.prevPages} disabled={from <= 1} onClick={() => go(from - STEP)}>
            <ChevronLeft />
          </Button>
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              go(Number(jump) || 1);
            }}
          >
            <Input
              aria-label={t.books.goToPage}
              type="number"
              inputMode="numeric"
              min={1}
              max={total}
              value={jump}
              onChange={(e) => setJump(e.target.value)}
              className="h-9 w-20"
            />
          </form>
          <Button variant="outline" size="icon-sm" aria-label={t.books.nextPages} disabled={to >= total} onClick={() => go(from + STEP)}>
            <ChevronRight />
          </Button>
        </div>
      </div>
      {q.isLoading ? (
        <CardListSkeleton rows={2} />
      ) : q.isError || !q.data ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : (
        q.data.map((p) => (
          <Card key={p.page_number} className="p-4 sm:p-5">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-primary">{t.books.pageN(p.page_number)}</p>
              {p.needs_ocr ? (
                <Badge variant="warning" className="gap-1"><ScanLine className="size-3" />{t.books.needsOcr}</Badge>
              ) : p.source === "ocr" ? (
                <Badge variant="default" className="gap-1"><ScanLine className="size-3" />{t.books.ocrDone}</Badge>
              ) : !p.text ? (
                <Badge variant="neutral">{t.books.noText}</Badge>
              ) : null}
            </div>
            {p.text && <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-primary">{p.text}</p>}
          </Card>
        ))
      )}
    </div>
  );
}
