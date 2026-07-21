import { SignIn } from "@clerk/nextjs";
import { clerkAppearance } from "@/lib/auth-config";

/** Centered card on the plain desk background (SAAS_DESIGN §4) — one job,
 * no split-screen marketing layout, theme-aware like every other page. */
export default function SignInPage() {
  return (
    <div className="flex justify-center pt-10">
      <SignIn appearance={clerkAppearance} />
    </div>
  );
}
