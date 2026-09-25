// T069: the create-next-app placeholder homepage is retired now that
// there's a real shell to land on.
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/memory");
}
