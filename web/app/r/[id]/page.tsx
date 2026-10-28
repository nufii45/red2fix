import type { Metadata } from "next";
import { Suspense } from "react";
import { RunView } from "@/components/run-view";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `Review ${id}` };
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="col">
      <Suspense>
        <RunView id={id} />
      </Suspense>
    </div>
  );
}
