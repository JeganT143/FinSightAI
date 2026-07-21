import { redirect } from "next/navigation";

/** Profile management is Clerk-hosted (UserButton -> Manage account); the
 * one first-party account surface is billing. */
export default function AccountPage() {
  redirect("/account/billing");
}
