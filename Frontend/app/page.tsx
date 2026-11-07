/**
 * Home page ("/").
 *
 * A Server Component that just arranges sections:
 *   Hero (static intro) + AssessmentWorkspace (interactive form → report)
 */

import { AssessmentWorkspace } from "@/components/assessment/AssessmentWorkspace";
import { Hero } from "@/components/layout/Hero";

export default function Home() {
  return (
    <>
      <Hero />
      <AssessmentWorkspace />
    </>
  );
}
