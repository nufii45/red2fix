import type { Metadata } from "next";
import { Suspense } from "react";
import { RunView } from "@/components/run-view";
import { fake } from "@/lib/config";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `Review ${id}` };
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="col">
      {fake && <div className="alert" role="status" style={{ marginTop: 0, marginBottom: "1.5rem" }}>Replay of a recorded review, not a live run.</div>}
      <Suspense>
        <RunView id={id} />
      </Suspense>
    </div>
  );
}
