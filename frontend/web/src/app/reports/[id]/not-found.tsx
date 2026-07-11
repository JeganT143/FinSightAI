import Link from "next/link";

export default function ReportNotFound() {
  return (
    <div className="rounded-md border border-border bg-surface px-6 py-12 text-center">
      <p className="text-text">No report with that ID.</p>
      <p className="mt-1 text-[13px] text-text-muted">
        Find past runs in the{" "}
        <Link href="/reports" className="underline hover:text-text">
          Ledger
        </Link>
        .
      </p>
    </div>
  );
}
