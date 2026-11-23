import { FileText, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Field } from "@/components/common";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { BOOK_LANGUAGES, ENGLISH_LEVELS, type BookLanguage, type BookMeta, type BookStatus, type EnglishLevel } from "@/types/api";
import { fmtSize } from "@/utils/format";

/** Hints only; the server enforces BOOK_MAX_UPLOAD_MB / BOOK_MAX_PAGES. */
export const BOOK_MAX_MB = 200;
export const BOOK_MAX_PAGES = 500;

const STATUS_VARIANT: Record<BookStatus, BadgeVariant> = {
  uploaded: "neutral",
  processing: "default",
  ready: "success",
  failed: "danger",
};

export function BookStatusBadge({ status }: { status: BookStatus }) {
  const { t } = useI18n();
  return <Badge variant={STATUS_VARIANT[status]}>{t.books.status[status]}</Badge>;
}

/** Title, author, language and level: used by the upload and the edit dialogs. */
export function BookMetaFields({ value, onChange }: { value: BookMeta; onChange: (v: BookMeta) => void }) {
  const { t } = useI18n();
  return (
    <>
      <Field label={t.books.bookTitle}>
        <Input value={value.title} maxLength={200} onChange={(e) => onChange({ ...value, title: e.target.value })} />
      </Field>
      <Field label={t.books.author} optional>
        <Input value={value.author ?? ""} maxLength={200} onChange={(e) => onChange({ ...value, author: e.target.value || null })} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t.books.language}>
          <NativeSelect value={value.language} onChange={(e) => onChange({ ...value, language: e.target.value as BookLanguage })}>
            {BOOK_LANGUAGES.map((l) => (
              <option key={l} value={l}>{t.books.lang[l]}</option>
            ))}
          </NativeSelect>
        </Field>
        <Field label={t.books.level}>
          <NativeSelect
            value={value.level ?? ""}
            onChange={(e) => onChange({ ...value, level: (e.target.value || null) as EnglishLevel | null })}
          >
            <option value="">{t.books.noLevel}</option>
            {ENGLISH_LEVELS.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </NativeSelect>
        </Field>
      </div>
    </>
  );
}

/** One PDF picker (a button that opens the file dialog, then the chosen file). */
export function PdfPicker({ file, onChange }: { file: File | null; onChange: (f: File) => void }) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files[0];
        if (f) onChange(f);
      }}
      className={`flex flex-col gap-3 rounded-xl border border-dashed p-4 sm:flex-row sm:items-center ${over ? "border-accent bg-accent-soft/40" : ""}`}
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
        <FileText className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        {file ? (
          <>
            <p className="truncate text-sm font-medium text-primary">{file.name}</p>
            <p className="text-xs text-muted-foreground">{fmtSize(file.size)}</p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">{t.books.fileHint(BOOK_MAX_MB, BOOK_MAX_PAGES)}</p>
        )}
      </div>
      <Button type="button" variant="outline" onClick={() => input.current?.click()}>
        <Upload />
        {t.books.chooseFile}
      </Button>
      <input
        ref={input}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onChange(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}
