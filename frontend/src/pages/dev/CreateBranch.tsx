export function CreateBranch(props: { projectId: number; lang: string; onBack: () => void; onCreated: (version: string) => void }) {
  return <div>CreateBranch — coming next <button onClick={props.onBack}>Back</button></div>;
}
