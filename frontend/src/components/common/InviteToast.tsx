import { toast } from "sonner";

/** Success toast after an invitation / reset e-mail. In development the backend
 *  also returns the link (no mail server), which is shown and can be copied. */
export function showInviteToast(title: string, email: string, devUrl: string | null | undefined, devLabel: string) {
  toast.success(title, {
    description: devUrl ? (
      <span className="block">
        {email}
        <span className="mt-1 block text-xs opacity-80">{devLabel}:</span>
        <a href={devUrl} target="_blank" rel="noreferrer" className="block break-all text-xs font-medium underline">
          {devUrl}
        </a>
      </span>
    ) : (
      email
    ),
    duration: devUrl ? 30000 : 6000,
    action: devUrl ? { label: "Copy", onClick: () => navigator.clipboard?.writeText(devUrl) } : undefined,
  });
}
