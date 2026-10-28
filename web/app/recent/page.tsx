import type { Metadata } from "next";
import { RecentList } from "@/components/recent-list";

export const metadata: Metadata = { title: "Recent reviews" };

export default function Recent() {
  return (
    <div className="col">
      <h1 className="title">recent</h1>
      <p className="lede">The last ten reviews anyone started here, newest first.</p>
      <RecentList />
    </div>
  );
}
