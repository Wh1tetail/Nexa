import { cn } from "@/lib/utils";

/** NEXA monogram: a geometric «N» whose accent diagonal is the "next step",
 *  plus a small accent spark. `inverted` is for dark backgrounds. */
export function BrandMark({
  className,
  inverted = false,
  spark = true,
}: {
  className?: string;
  inverted?: boolean;
  spark?: boolean;
}) {
  // the regular mark flips in the dark theme so it stays visible on navy
  const tile = inverted ? "fill-white" : "fill-[#14213D] dark:fill-white";
  const stem = inverted ? "stroke-[#14213D]" : "stroke-white dark:stroke-[#14213D]";
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8 shrink-0", className)} aria-hidden focusable="false">
      <rect width="32" height="32" rx="9" className={tile} />
      <path d="M10 23V9" className={stem} strokeWidth="3.2" strokeLinecap="round" />
      <path d="M22 23V9" className={stem} strokeWidth="3.2" strokeLinecap="round" />
      <path d="M10.6 9.8 21.4 22.2" stroke="#3563F5" strokeWidth="3.2" strokeLinecap="round" />
      {spark && <circle cx="25.5" cy="6.5" r="2.2" fill="#3563F5" />}
    </svg>
  );
}
