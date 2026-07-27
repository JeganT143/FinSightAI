import { SignIn } from "@clerk/nextjs";
import { DemoCredentials } from "@/components/DemoCredentials";
import { clerkAppearance } from "@/lib/auth-config";

/** Centered card on the plain desk background (SAAS_DESIGN §4) — one job,
 * no split-screen marketing layout, theme-aware like every other page. */
export default function SignInPage() {
  return (
    <div className="flex flex-col items-center gap-6 pt-10">
      <DemoCredentials />
      <SignIn appearance={clerkAppearance} />
    </div>
  );
}
