import { Suspense } from "react";
import type { Metadata } from "next";
import LoginForm from "./LoginForm";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to the QuantPulse AI trading terminal.",
};

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-[80vh]" />}>
      <LoginForm />
    </Suspense>
  );
}
