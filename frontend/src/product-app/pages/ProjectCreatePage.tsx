export function ProjectCreatePage(props: {
  createProjectName: string;
  createTranslationColumns: string;
  createRemarkColumns: string;
  isBusy: boolean;
  hasProjects: boolean;
  onProjectNameChange: (value: string) => void;
  onTranslationColumnsChange: (value: string) => void;
  onRemarkColumnsChange: (value: string) => void;
  onCreateProject: () => void;
  onBackToOverview: () => void;
}) {
  return (
    <section className="panel panel-wide" data-testid="project-create-page">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Project Setup</p>
          <h3>Create Project</h3>
        </div>
      </div>
      <p className="muted">
        Define the fixed template once. Translation and remark column names are
        fixed after project creation and are used by import, compare, queue,
        fill, and master query.
      </p>
      <div className="stack form-stack">
        <label className="field">
          <span>Project Name</span>
          <input
            value={props.createProjectName}
            onChange={(event) => props.onProjectNameChange(event.target.value)}
            data-testid="project-name-input"
          />
        </label>
        <label className="field">
          <span>Translation Columns</span>
          <input
            value={props.createTranslationColumns}
            onChange={(event) =>
              props.onTranslationColumnsChange(event.target.value)
            }
            placeholder="fr, en"
            data-testid="project-translation-columns"
          />
        </label>
        <label className="field">
          <span>Remark Columns</span>
          <input
            value={props.createRemarkColumns}
            onChange={(event) => props.onRemarkColumnsChange(event.target.value)}
            placeholder="context"
            data-testid="project-remark-columns"
          />
        </label>
        <div className="toolbar">
          <button
            className="button accent"
            onClick={props.onCreateProject}
            disabled={props.isBusy}
            data-testid="project-create-button"
          >
            Create Project
          </button>
          {props.hasProjects ? (
            <button className="button subtle" onClick={props.onBackToOverview}>
              Back to Overview
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}
