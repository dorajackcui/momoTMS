export function BranchDetail(props: { projectId: number; version: string; onBack: () => void }) {
  return <div>BranchDetail for {props.version} — coming next <button onClick={props.onBack}>Back</button></div>;
}
