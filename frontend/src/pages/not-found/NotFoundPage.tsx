import { Link } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { EmptyState, Panel, buttonClassName } from "@/shared/ui/primitives";

export function NotFoundPage() {
  const shell = useAppShell();
  return (
    <Panel
      kicker="Route Missing"
      title="This `/app` route no longer exists"
      description="The new frontend keeps six stable destinations only: Overview, Intake, Branch Ops, Runs, Variants, and Project."
    >
      <EmptyState
        title="Unknown route"
        body="The old page split has been removed. Use the new navigation or jump back to the project-first overview."
        action={
          <Link className={buttonClassName("primary")} to={shell.buildHref("/app/overview")}>
            Go to Overview
          </Link>
        }
      />
    </Panel>
  );
}
