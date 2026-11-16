import { Fragment, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Inline: **bold**, *italic*. Plain text otherwise (never HTML). */
function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const token = m[0];
    out.push(
      token.startsWith("**") ? (
        <strong key={`${key}-${i++}`} className="font-semibold text-primary">{token.slice(2, -2)}</strong>
      ) : (
        <em key={`${key}-${i++}`}>{token.slice(1, -1)}</em>
      ),
    );
    last = m.index + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

type Run = { kind: "ul" | "ol" | "p" | "h2" | "h3"; lines: string[] };
const UL = /^\s*[-*]\s+/;
const OL = /^\s*\d+[.)]\s+/;

/** Lines of a paragraph split into text, list and heading runs, so a list may
 *  follow a line of text without a blank line in between. */
function runs(lines: string[]): Run[] {
  const out: Run[] = [];
  for (const line of lines) {
    const kind: Run["kind"] = /^###\s/.test(line) ? "h3" : /^##\s/.test(line) ? "h2" : UL.test(line) ? "ul" : OL.test(line) ? "ol" : "p";
    const last = out[out.length - 1];
    if (last && last.kind === kind && kind !== "h2" && kind !== "h3") last.lines.push(line);
    else out.push({ kind, lines: [line] });
  }
  return out;
}

function renderRun(run: Run, key: string): ReactNode {
  if (run.kind === "h2") return <h3 key={key} className="text-lg font-semibold">{inline(run.lines[0].replace(/^##\s+/, ""), key)}</h3>;
  if (run.kind === "h3") return <h4 key={key} className="text-base font-semibold">{inline(run.lines[0].replace(/^###\s+/, ""), key)}</h4>;
  if (run.kind === "ul" || run.kind === "ol") {
    const List = run.kind === "ul" ? "ul" : "ol";
    const strip = run.kind === "ul" ? UL : OL;
    return (
      <List key={key} className={cn("space-y-1 pl-5", run.kind === "ul" ? "list-disc" : "list-decimal")}>
        {run.lines.map((l, li) => <li key={li}>{inline(l.replace(strip, ""), `${key}-${li}`)}</li>)}
      </List>
    );
  }
  return (
    <p key={key} className="break-words">
      {run.lines.map((l, li) => (
        <Fragment key={li}>
          {li > 0 && <br />}
          {inline(l, `${key}-${li}`)}
        </Fragment>
      ))}
    </p>
  );
}

/** A small, safe subset of Markdown for reading texts: paragraphs (blank line),
 *  line breaks, ## / ### headings, - and 1. lists, **bold**, *italic*. */
export function Markdown({ text }: { text: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  return (
    <div className="grid gap-3 text-[15px] leading-relaxed text-foreground">
      {blocks.flatMap((block, bi) => runs(block.split("\n")).map((run, ri) => renderRun(run, `b${bi}-${ri}`)))}
    </div>
  );
}
