import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  FileSearch,
  FileText,
  FolderKanban,
  Gauge,
  Globe2,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  UploadCloud,
  UserRound,
  XCircle,
} from "lucide-react";

const API = "/api/v1";
const tokenKey = "auth_token";
const refreshKey = "refresh_token";
let refreshPromise = null;

function renewAccessToken() {
  if (!refreshPromise) {
    const refreshToken = localStorage.getItem(refreshKey);
    if (!refreshToken) return Promise.reject(new Error("Your session has expired. Sign in again."));
    refreshPromise = fetch(`${API}/auth/refresh`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: jsonBody({ refresh_token: refreshToken }),
    }).then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.access_token) throw new Error("Your session has expired. Sign in again.");
      localStorage.setItem(tokenKey, data.access_token);
      return data.access_token;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

async function apiFetch(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  const token = localStorage.getItem(tokenKey);
  if (token) headers.Authorization = `Bearer ${token}`;
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body !== undefined && !isForm && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let response = await fetch(`${API}${path}`, { ...options, headers });
  if (response.status === 401 && !path.includes("/auth/login") && !path.includes("/auth/refresh") && localStorage.getItem(refreshKey)) {
    try {
      headers.Authorization = `Bearer ${await renewAccessToken()}`;
      response = await fetch(`${API}${path}`, { ...options, headers });
    } catch (error) {
      localStorage.removeItem(tokenKey);
      localStorage.removeItem(refreshKey);
      throw error;
    }
  }
  if (options.responseType === "blob" && response.ok) return response.blob();
  const raw = await response.text();
  let data = null;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = { detail: raw };
    }
  }
  if (!response.ok) {
    const detail = data?.detail || data?.message || data?.error;
    throw new Error(typeof detail === "string" ? detail : `${response.status} ${response.statusText}`);
  }
  return data;
}

const jsonBody = (value) => JSON.stringify(value);

const navigation = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "upload", label: "Document upload", icon: UploadCloud },
  { id: "analysis", label: "Analysis", icon: FileSearch },
  { id: "recommendations", label: "Recommendations", icon: ListChecks },
  { id: "standards", label: "Standards explorer", icon: BookOpen },
  { id: "certification", label: "Certification", icon: ShieldCheck },
  { id: "review", label: "Review", icon: ClipboardList },
  { id: "audit", label: "Audit", icon: Activity },
  { id: "settings", label: "Settings", icon: Settings },
];

function ErrorMessage({ children }) {
  if (!children) return null;
  return <div className="notice notice-error" role="alert">{children}</div>;
}

function EmptyState({ icon: Icon = FileText, title, children }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon size={22} aria-hidden="true" /></span>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}

function PageHeading({ eyebrow, title, description, action }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}

function StatusPill({ children, tone = "neutral" }) {
  return <span className={`status-pill status-${tone}`}>{children}</span>;
}

function Busy({ label = "Loading" }) {
  return <div className="busy" role="status"><span className="spinner" />{label}</div>;
}

function LoginPanel({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await apiFetch("/auth/login", {
        method: "POST",
        body: jsonBody({ email: email.trim(), password }),
      });
      localStorage.setItem(tokenKey, data.access_token);
      if (data.refresh_token) localStorage.setItem(refreshKey, data.refresh_token);
      const profile = await apiFetch("/auth/me");
      onLogin(profile);
    } catch (err) {
      setError(err.message || "Sign in failed. Check your credentials and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand-mark"><ShieldCheck size={25} aria-hidden="true" /></div>
        <div className="eyebrow">Indian Standards · Compliance Workspace</div>
        <h1 id="login-title">Sign in to IS Platform</h1>
        <p className="muted">Use your organization account to continue.</p>
        <ErrorMessage>{error}</ErrorMessage>
        <form onSubmit={submit} className="form-stack">
          <label htmlFor="login-email">Work email</label>
          <input id="login-email" type="email" autoComplete="username" value={email}
            onChange={(e) => setEmail(e.target.value)} required />
          <label htmlFor="login-password">Password</label>
          <input id="login-password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
          <button className="button button-primary button-full" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}<ArrowRight size={16} aria-hidden="true" />
          </button>
        </form>
        <div className="login-footnote">Access is controlled by your assigned platform role.</div>
      </section>
      <div className="login-aside" aria-hidden="true">
        <div className="login-aside-copy">
          <span className="aside-kicker">Procurement assurance</span>
          <h2>Make every requirement easier to trace.</h2>
          <p>Bring tender documents, standards, and review work into one clear workspace.</p>
        </div>
        <div className="aside-orbit orbit-one" /><div className="aside-orbit orbit-two" />
      </div>
    </main>
  );
}

function DashboardPage({ user, onNavigate }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      apiFetch("/health/ready"),
      apiFetch("/projects?limit=100"),
      apiFetch("/standards?limit=1"),
    ]).then(([health, projects, standards]) => {
      if (!active) return;
      const projectData = projects.status === "fulfilled" ? projects.value : { projects: [], total: 0 };
      const standardData = standards.status === "fulfilled" ? standards.value : { total: 0 };
      setSummary({
        healthy: health.status === "fulfilled" && health.value?.status === "READY",
        projects: projectData.total || 0,
        documents: (projectData.projects || []).reduce((total, item) => total + (item.document_count || 0), 0),
        standards: standardData.total || 0,
      });
      if (projects.status === "rejected") setError(projects.reason.message);
      setBusy(false);
    });
    return () => { active = false; };
  }, []);

  return (
    <>
      <PageHeading eyebrow="Workspace overview" title={`Good to see you${user.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}`}
        description="A clear view of your projects, documents, and standards work." />
      {error && <ErrorMessage>{error}</ErrorMessage>}
      {busy ? <Busy label="Loading workspace summary" /> : (
        <div className="stat-grid">
          <StatCard icon={FolderKanban} label="Projects" value={summary?.projects ?? "—"} detail="Active workspace records" />
          <StatCard icon={FileText} label="Documents" value={summary?.documents ?? "—"} detail="Uploaded to your projects" />
          <StatCard icon={BookOpen} label="Standards" value={summary?.standards ?? "—"} detail="In the current catalogue" />
          <StatCard icon={Gauge} label="API status" value={summary?.healthy ? "Ready" : "Unavailable"}
            detail="Backend and database readiness" tone={summary?.healthy ? "green" : "amber"} />
        </div>
      )}
      <section className="section-block">
        <div className="section-title-row"><div><div className="eyebrow">Get started</div><h3>Choose your next step</h3></div></div>
        <div className="quick-grid">
          <QuickAction icon={Plus} title="Create a project" text="Set up a tender workspace." onClick={() => onNavigate("projects")} />
          <QuickAction icon={UploadCloud} title="Upload a document" text="Add a PDF, DOCX, XLSX, or TXT file." onClick={() => onNavigate("upload")} />
          <QuickAction icon={Search} title="Explore standards" text="Search codes, versions, and relationships." onClick={() => onNavigate("standards")} />
        </div>
      </section>
      <div className="notice notice-info"><CheckCircle2 size={18} aria-hidden="true" /> AI analysis is evidence-led. Results need human review before procurement decisions.</div>
    </>
  );
}

function StatCard({ icon: Icon, label, value, detail, tone = "blue" }) {
  return <div className="stat-card"><span className={`stat-icon tone-${tone}`}><Icon size={19} aria-hidden="true" /></span>
    <div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-detail">{detail}</div></div>;
}

function QuickAction({ icon: Icon, title, text, onClick }) {
  return <button className="quick-action" onClick={onClick}><span className="quick-icon"><Icon size={19} aria-hidden="true" /></span>
    <span><strong>{title}</strong><small>{text}</small></span><ArrowRight size={16} className="quick-arrow" aria-hidden="true" /></button>;
}

function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({ code: "", title: "", description: "" });

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const data = await apiFetch("/projects?limit=100");
      setProjects(data.projects || []);
      setTotal(data.total || 0);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = async (event) => {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      await apiFetch("/projects", { method: "POST", body: jsonBody(form) });
      setForm({ code: "", title: "", description: "" });
      setNotice("Project created.");
      await load();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  return <>
    <PageHeading eyebrow="Tender workspaces" title="Projects" description="Create and organize the project spaces used for tender analysis." />
    <ErrorMessage>{error}</ErrorMessage>
    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    <div className="split-layout">
      <section className="panel">
        <div className="panel-heading"><div><h3>New project</h3><p>Use a unique project code for tracking.</p></div></div>
        <form className="form-stack" onSubmit={create}>
          <label htmlFor="project-code">Project code</label>
          <input id="project-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} maxLength={100} required />
          <label htmlFor="project-title">Project title</label>
          <input id="project-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={255} required />
          <label htmlFor="project-description">Description <span className="optional">Optional</span></label>
          <textarea id="project-description" rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={5000} />
          <button className="button button-primary" disabled={saving}><Plus size={16} aria-hidden="true" />{saving ? "Creating…" : "Create project"}</button>
        </form>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h3>Your projects</h3><p>{total} project{total === 1 ? "" : "s"}</p></div><button className="button button-quiet" onClick={load} disabled={busy}>Refresh</button></div>
        {busy ? <Busy label="Loading projects" /> : projects.length ? <div className="project-list">
          {projects.map((project) => <article className="project-row" key={project.id}>
            <span className="project-avatar"><FolderKanban size={19} aria-hidden="true" /></span>
            <div className="project-main"><div className="project-row-top"><strong>{project.title}</strong><StatusPill tone={project.status === "draft" ? "neutral" : "blue"}>{project.status}</StatusPill></div>
              <div className="project-meta"><span>{project.code}</span><span>{project.document_count} documents</span></div>
              {project.description && <p>{project.description}</p>}
            </div>
          </article>)}
        </div> : <EmptyState icon={FolderKanban} title="No projects yet">Create a project to start organizing tender documents.</EmptyState>}
      </section>
    </div>
  </>;
}

function UploadPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [documents, setDocuments] = useState([]);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const fileInput = useRef(null);

  const loadProjects = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const data = await apiFetch("/projects?limit=100");
      const rows = data.projects || [];
      setProjects(rows);
      setProjectId((current) => rows.some((p) => p.id === current) ? current : (rows[0]?.id || ""));
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadProjects(); }, [loadProjects]);
  useEffect(() => {
    if (!projectId) { setDocuments([]); return; }
    let active = true;
    apiFetch(`/documents?project_id=${encodeURIComponent(projectId)}`)
      .then((rows) => { if (active) setDocuments(rows || []); })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [projectId]);

  const upload = async (event) => {
    event.preventDefault();
    if (!file || !projectId) return;
    setBusy(true); setError(""); setNotice("");
    const body = new FormData();
    body.append("file", file);
    body.append("project_id", projectId);
    try {
      const saved = await apiFetch("/documents/upload", { method: "POST", body });
      setNotice(`${saved.filename} uploaded and processed.`);
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setDocuments((rows) => [saved, ...rows]);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return <>
    <PageHeading eyebrow="Project files" title="Document upload" description="Add tender files for extraction and evidence-grounded analysis." />
    <ErrorMessage>{error}</ErrorMessage>
    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    {loading ? <Busy label="Loading projects" /> : !projects.length ? <EmptyState icon={FolderKanban} title="Create a project first">Documents are stored inside a project. Create one before uploading.</EmptyState> : (
      <div className="split-layout upload-layout">
        <section className="panel">
          <div className="panel-heading"><div><h3>Add a document</h3><p>Files up to 50 MB are accepted.</p></div></div>
          <form className="form-stack" onSubmit={upload}>
            <label htmlFor="upload-project">Project</label>
            <select id="upload-project" value={projectId} onChange={(e) => setProjectId(e.target.value)} required>
              {projects.map((project) => <option key={project.id} value={project.id}>{project.code} · {project.title}</option>)}
            </select>
            <label htmlFor="upload-file">Choose a file</label>
            <input ref={fileInput} id="upload-file" type="file" accept=".pdf,.docx,.xlsx,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} required />
            <div className="upload-hint"><UploadCloud size={18} aria-hidden="true" /> PDF, DOCX, XLSX, and TXT</div>
            <button className="button button-primary" type="submit" disabled={busy || !file}><UploadCloud size={16} aria-hidden="true" />{busy ? "Uploading and processing…" : "Upload document"}</button>
          </form>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><h3>Project documents</h3><p>Processing status and file details.</p></div></div>
          {documents.length ? <div className="document-list">{documents.map((doc) => <div className="document-row" key={doc.id}>
            <span className="document-icon"><FileText size={18} aria-hidden="true" /></span>
            <div className="document-main"><strong>{doc.filename}</strong><small>{doc.file_type?.toUpperCase()} · {formatBytes(doc.file_size_bytes)} · {doc.total_pages} page{doc.total_pages === 1 ? "" : "s"}</small>
              {doc.error_message && <small className="text-danger">{doc.error_message}</small>}</div>
            <StatusPill tone={doc.processing_status === "completed" ? "green" : doc.processing_status === "failed" ? "red" : "amber"}>{doc.processing_status}</StatusPill>
          </div>)}</div> : <EmptyState icon={FileText} title="No documents in this project">Uploaded files will appear here.</EmptyState>}
        </section>
      </div>
    )}
  </>;
}

function formatBytes(value = 0) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function AnalysisPage({ onAnalysis }) {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState("text");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch("/projects?limit=100").then((data) => {
      const rows = data.projects || [];
      setProjects(rows);
      setProjectId(rows[0]?.id || "");
    }).catch((err) => setError(err.message));
  }, []);
  useEffect(() => {
    if (!projectId) { setDocuments([]); setDocumentId(""); return; }
    apiFetch(`/documents?project_id=${encodeURIComponent(projectId)}`).then((rows) => {
      setDocuments(rows || []);
      setDocumentId(rows?.[0]?.id || "");
    }).catch((err) => setError(err.message));
  }, [projectId]);

  const runAnalysis = async (event) => {
    event.preventDefault();
    if ((mode === "text" && !text.trim()) || (mode === "document" && !documentId)) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const extraction = await apiFetch("/analysis/extract-specifications", {
        method: "POST",
        body: jsonBody(mode === "text" ? { custom_text: text } : { document_id: documentId }),
      });
      let sourceText = text;
      if (mode === "document") {
        const document = await apiFetch(`/documents/${encodeURIComponent(documentId)}`);
        sourceText = document.extracted_text_preview || "";
      }
      const entities = extraction.entities || {};
      const cited = entities.standards_cited || [];
      const categories = entities.categories || [];
      const searchQuery = (sourceText || cited.join(" ")).trim().slice(0, 10000);
      const checks = await Promise.allSettled([
        apiFetch("/analysis/detect-gaps", { method: "POST", body: jsonBody({ text: sourceText, cited_standards: cited, categories }) }),
        sourceText.trim() ? apiFetch("/analysis/detect-conflicts", { method: "POST", body: jsonBody({ text: sourceText, cited_references: cited }) }) : Promise.resolve(null),
        searchQuery.length >= 2 ? apiFetch("/standards/search", { method: "POST", body: jsonBody({ query: searchQuery, search_type: "hybrid", top_k: 5 }) }) : Promise.resolve({ results: [], total_results: 0 }),
      ]);
      const output = {
        extraction,
        gaps: checks[0].status === "fulfilled" ? checks[0].value : null,
        conflicts: checks[1].status === "fulfilled" ? checks[1].value : null,
        search: checks[2].status === "fulfilled" ? checks[2].value : null,
        secondaryErrors: checks.filter((item) => item.status === "rejected").map((item) => item.reason.message),
      };
      setResult(output);
      onAnalysis({ candidates: output.search?.results || [], extraction, sourceText, projectId: mode === "document" ? projectId : null, documentId: mode === "document" ? documentId : null });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return <>
    <PageHeading eyebrow="Tender review" title="Analysis" description="Extract specification entities, check for potential gaps, and flag contradictions for review." />
    <ErrorMessage>{error}</ErrorMessage>
    <section className="panel analysis-panel">
      <div className="segmented" role="tablist" aria-label="Analysis source">
        <button type="button" role="tab" aria-selected={mode === "text"} className={mode === "text" ? "selected" : ""} onClick={() => setMode("text")}>Paste text</button>
        <button type="button" role="tab" aria-selected={mode === "document"} className={mode === "document" ? "selected" : ""} onClick={() => setMode("document")}>Use project document</button>
      </div>
      <form className="form-stack" onSubmit={runAnalysis}>
        {mode === "text" ? <><label htmlFor="analysis-text">Tender or specification text</label>
        <textarea id="analysis-text" rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste a tender clause or technical specification…" required /></> : <>
          <label htmlFor="analysis-project">Project</label><select id="analysis-project" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            {projects.map((project) => <option value={project.id} key={project.id}>{project.code} · {project.title}</option>)}
          </select>
          <label htmlFor="analysis-document">Processed document</label><select id="analysis-document" value={documentId} onChange={(e) => setDocumentId(e.target.value)} disabled={!documents.length}>
            {documents.map((doc) => <option value={doc.id} key={doc.id}>{doc.filename} · {doc.processing_status}</option>)}
          </select>
          {!documents.length && <p className="field-hint">Upload a document to this project first.</p>}
        </>}
        <button className="button button-primary" disabled={busy || (mode === "document" && !documentId) || (mode === "text" && !text.trim())} type="submit">
          <FileSearch size={16} aria-hidden="true" />{busy ? "Analyzing…" : "Analyze specification"}
        </button>
      </form>
    </section>
    {busy && <Busy label="Extracting entities and checking the tender" />}
    {result && <AnalysisResult result={result} />}
  </>;
}

function AnalysisResult({ result }) {
  const entities = result.extraction?.entities || {};
  const entityGroups = [
    ["Products", entities.products], ["Categories", entities.categories], ["Materials", entities.materials],
    ["Standards cited", entities.standards_cited], ["Performance", entities.performance],
    ["Safety", entities.safety], ["Testing", entities.testing], ["Certification hints", entities.certification_hints],
  ].filter(([, items]) => items?.length);
  const gaps = result.gaps?.total_gaps_found || 0;
  const conflicts = result.conflicts ? (result.conflicts.total_conflicts || 0) : "—";
  return <section className="section-block">
    <div className="section-title-row"><div><div className="eyebrow">Analysis results</div><h3>Review these findings</h3></div>
      <StatusPill tone="amber">Potential findings · human verification required</StatusPill></div>
    {result.secondaryErrors.map((message, index) => <ErrorMessage key={index}>{message}</ErrorMessage>)}
    <div className="summary-strip">
      <SummaryMetric label="Entities found" value={result.extraction?.total_entities_found ?? 0} />
      <SummaryMetric label="Potential gaps" value={gaps} tone={gaps ? "amber" : "green"} />
      <SummaryMetric label={result.conflicts ? "Potential conflicts" : "Conflict check"} value={conflicts} tone={result.conflicts && conflicts ? "red" : "green"} />
      <SummaryMetric label="Standards to inspect" value={result.search?.total_results ?? 0} />
    </div>
    {entityGroups.length ? <div className="panel entity-panel"><h4>Extracted details</h4><div className="entity-grid">
      {entityGroups.map(([label, values]) => <div className="entity-group" key={label}><span>{label}</span><div>{values.map((value, i) => <StatusPill key={`${label}-${i}`} tone="blue">{String(value)}</StatusPill>)}</div></div>)}
    </div></div> : <div className="notice notice-info">No structured entities were identified in this text.</div>}
    {result.gaps?.missing_mandatory_standards?.length > 0 && <FindingList title="Potential gaps" rows={result.gaps.missing_mandatory_standards.map((row) => ({ title: `${row.standard_code} · ${row.title}`, detail: row.reason, severity: row.severity }))} />}
    {result.gaps?.missing_normative_references?.length > 0 && <FindingList title="Missing normative references" rows={result.gaps.missing_normative_references.map((row) => ({ title: `${row.missing_normative} · referenced by ${row.source_standard}`, detail: row.reason, severity: row.severity }))} />}
    {result.conflicts?.conflicts?.length > 0 && <FindingList title="Potential conflicts" rows={result.conflicts.conflicts.map((row) => ({ title: row.conflict_type.replaceAll("_", " "), detail: row.description, severity: row.severity }))} />}
    {result.search?.results?.length > 0 && <div className="panel candidate-panel"><h4>Standards to inspect</h4><p className="muted">Search candidates are not compliance recommendations. Confirm the source and current version.</p>
      {result.search.results.slice(0, 5).map((item) => <div className="candidate-row" key={item.standard_id}><div><strong>{item.standard_code}</strong><span>{item.title}</span></div><StatusPill tone="neutral">{item.match_type}</StatusPill></div>)}
    </div>}
  </section>;
}

function SummaryMetric({ label, value, tone = "blue" }) {
  return <div className="summary-metric"><span>{label}</span><strong className={`metric-${tone}`}>{value}</strong></div>;
}

function FindingList({ title, rows }) {
  return <div className="finding-panel"><h4><AlertTriangle size={17} aria-hidden="true" />{title}</h4>
    {rows.map((row, i) => <div className="finding-row" key={`${row.title}-${i}`}><div><strong>{row.title}</strong><p>{row.detail}</p></div><StatusPill tone={row.severity === "CRITICAL" ? "red" : row.severity === "HIGH" ? "amber" : "neutral"}>{row.severity || "Review"}</StatusPill></div>)}
  </div>;
}

function RecommendationsPage({ analysis }) {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [creatingId, setCreatingId] = useState("");
  const [createdIds, setCreatedIds] = useState([]);
  const [notice, setNotice] = useState("");
  const [reportBusy, setReportBusy] = useState(false);
  const ask = async (event) => {
    event.preventDefault();
    setBusy(true); setError(""); setAnswer(null);
    try { setAnswer(await apiFetch("/analysis/rag-explain", { method: "POST", body: jsonBody({ query }) })); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const createForReview = async (standardId) => {
    if (!analysis?.projectId || !analysis?.documentId) return;
    setCreatingId(standardId); setError(""); setNotice("");
    try {
      await apiFetch("/reviews/recommendations", {
        method: "POST",
        body: jsonBody({ project_id: analysis.projectId, document_id: analysis.documentId, standard_id: standardId, source_excerpt: analysis.sourceText }),
      });
      setCreatedIds((ids) => [...ids, standardId]);
      setNotice("Recommendation saved as pending review. A reviewer must verify its evidence and current standard text.");
    } catch (err) { setError(err.message); }
    finally { setCreatingId(""); }
  };
  const downloadReport = async () => {
    if (!analysis?.projectId) return;
    setReportBusy(true); setError("");
    try {
      const blob = await apiFetch(`/projects/${encodeURIComponent(analysis.projectId)}/report.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = "project-review-report.pdf"; anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) { setError(err.message); }
    finally { setReportBusy(false); }
  };
  const candidates = analysis?.candidates || [];
  return <>
    <PageHeading eyebrow="Evidence and rationale" title="Recommendations" description="Review search candidates and ask a question that must be supported by retrieved evidence."
      action={analysis?.projectId && <button className="button button-secondary" type="button" onClick={downloadReport} disabled={reportBusy}>{reportBusy ? "Preparing report…" : "Download project report"}<FileText size={16} aria-hidden="true" /></button>} />
    <ErrorMessage>{error}</ErrorMessage>
    {notice && <div className="notice notice-info" role="status">{notice}</div>}
    <div className="split-layout recommendation-layout">
      <section className="panel"><div className="panel-heading"><div><h3>Evidence-grounded question</h3><p>If the evidence is missing, the system will say so.</p></div></div>
        <form className="form-stack" onSubmit={ask}><label htmlFor="rag-question">Question</label><textarea id="rag-question" rows={4} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask about a requirement or standard…" required minLength={3} />
          <button className="button button-primary" type="submit" disabled={busy || query.trim().length < 3}>{busy ? "Checking evidence…" : "Ask from evidence"}<ArrowRight size={16} aria-hidden="true" /></button></form>
        {answer && <div className={`answer-card ${answer.is_verified ? "answer-verified" : "answer-unverified"}`}>
          <div className="answer-heading">{answer.is_verified ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}<strong>{answer.is_verified ? "Evidence found" : "Insufficient verified evidence"}</strong></div>
          <p>{answer.explanation}</p>
          {answer.evidence?.length > 0 && <div className="evidence-list"><h4>Retrieved evidence</h4>{answer.evidence.map((item, i) => <blockquote key={`${item.source}-${i}`}><p>“{item.snippet}”</p><footer>{item.source}{item.clause ? ` · ${item.clause}` : ""} · Evidence {Math.round((item.confidence || 0) * 100)}%</footer></blockquote>)}</div>}
        </div>}
      </section>
      <section className="panel"><div className="panel-heading"><div><h3>From your latest analysis</h3><p>Search matches to inspect further.</p></div></div>
        {candidates.length ? <div className="candidate-list">{candidates.map((item) => <article className="recommendation-card" key={item.standard_id}>
          <div className="recommendation-top"><strong>{item.standard_code}</strong><StatusPill tone="neutral">{item.match_type}</StatusPill></div>
          <h4>{item.title}</h4><p>{item.explanation}</p><div className="recommendation-meta"><span>{item.category}</span>{item.current_version && <span>{item.current_version}</span>}</div>
          {analysis?.projectId && analysis?.documentId && <button className="button button-secondary" type="button" onClick={() => createForReview(item.standard_id)} disabled={creatingId === item.standard_id || createdIds.includes(item.standard_id)}>
            {createdIds.includes(item.standard_id) ? "Saved for review" : creatingId === item.standard_id ? "Saving…" : "Create for review"}
          </button>}
        </article>)}</div> : <EmptyState icon={Search} title="No analysis candidates yet">Run an analysis to carry search matches into this view.</EmptyState>}
        <p className="caveat">Matches are search results, not approved recommendations. Verify scope, version, and evidence.</p>
      </section>
    </div>
  </>;
}

function StandardsPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [standards, setStandards] = useState([]);
  const [results, setResults] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  const load = useCallback(async () => {
    setBusy(true); setError(""); setResults(null);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (category) params.set("category", category);
      const data = await apiFetch(`/standards?${params}`);
      setStandards(data.standards || []);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }, [category]);
  useEffect(() => { load(); }, [load]);

  const search = async (event) => {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const data = await apiFetch("/standards/search", { method: "POST", body: jsonBody({ query, search_type: "hybrid", category_filter: category || null, top_k: 20 }) });
      setResults(data.results || []);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const open = async (id) => {
    setError("");
    try { setSelected(await apiFetch(`/standards/${encodeURIComponent(id)}`)); }
    catch (err) { setError(err.message); }
  };

  const visible = results || standards;
  return <>
    <PageHeading eyebrow="BIS catalogue" title="Standards explorer" description="Search standards and inspect versions, amendments, relationships, and certification details." />
    <ErrorMessage>{error}</ErrorMessage>
    <section className="panel explorer-tools"><form onSubmit={search} className="search-form">
      <label className="sr-only" htmlFor="standards-query">Search standards</label><Search size={18} aria-hidden="true" />
      <input id="standards-query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by code, title, or topic" minLength={2} />
      <label className="sr-only" htmlFor="standards-category">Filter category</label><select id="standards-category" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All categories</option><option>Civil</option><option>Electrical</option><option>Mechanical</option><option>Metallurgy</option></select>
      <button className="button button-primary" type="submit" disabled={busy || query.trim().length < 2}>Search</button>
      {results && <button className="button button-quiet" type="button" onClick={load}>Clear search</button>}
    </form></section>
    <div className="explorer-layout">
      <section className="panel standards-list"><div className="panel-heading"><div><h3>{results ? "Search results" : "Catalogue"}</h3><p>{results ? `${results.length} matching standards` : `${visible.length} standards shown`}</p></div></div>
        {busy ? <Busy label="Loading standards" /> : visible.length ? visible.map((item) => <button className={`standard-row ${selected?.id === (item.id || item.standard_id) ? "active" : ""}`} key={item.id || item.standard_id} onClick={() => open(item.id || item.standard_id)}>
          <span><strong>{item.standard_code}</strong><small>{item.title}</small></span><ArrowRight size={16} aria-hidden="true" /></button>) : <EmptyState icon={BookOpen} title="No standards found">Try a broader search or another category.</EmptyState>}
      </section>
      <section className="panel standard-detail">{selected ? <>
        <div className="detail-title"><div><div className="eyebrow">{selected.category}</div><h3>{selected.standard_code}</h3><p>{selected.title}</p></div><StatusPill tone={selected.status === "active" ? "green" : "amber"}>{selected.status}</StatusPill></div>
        {selected.scope && <div className="detail-section"><h4>Scope</h4><p>{selected.scope}</p></div>}
        <DetailCollection title="Versions and amendments" rows={(selected.versions || []).map((version) => ({ title: version.version_label, detail: `${version.is_current ? "Current version" : "Previous version"}${version.changelog ? ` · ${version.changelog}` : ""}`, extra: version.amendments?.length ? `${version.amendments.length} amendment(s)` : "" }))} />
        <DetailCollection title="Normative and related references" rows={(selected.normative_references || []).map((ref) => ({ title: `${ref.target_standard_code} · ${ref.target_title}`, detail: `${ref.relationship_type}${ref.clause_reference ? ` · ${ref.clause_reference}` : ""}`, extra: ref.description }))} />
        <DetailCollection title="Referenced by" rows={(selected.referenced_by || []).map((ref) => ({ title: `${ref.source_standard_code} · ${ref.source_title}`, detail: `${ref.relationship_type}${ref.clause_reference ? ` · ${ref.clause_reference}` : ""}`, extra: ref.description }))} />
        <DetailCollection title="Certification information" rows={(selected.certifications || []).map((cert) => ({ title: cert.certification_type, detail: `${cert.is_mandatory ? "Mandatory" : "Not marked mandatory"}${cert.qco_order_number ? ` · ${cert.qco_order_number}` : ""}`, extra: cert.details }))} />
        {selected.bis_url && <a className="text-link" href={selected.bis_url} target="_blank" rel="noreferrer">Open BIS source <ArrowRight size={14} aria-hidden="true" /></a>}
      </> : <EmptyState icon={BookOpen} title="Select a standard">Choose a code to view its version history and relationships.</EmptyState>}</section>
    </div>
  </>;
}

function DetailCollection({ title, rows }) {
  if (!rows.length) return null;
  return <div className="detail-section"><h4>{title}</h4><div className="detail-list">{rows.map((row, i) => <div className="detail-row" key={`${row.title}-${i}`}><strong>{row.title}</strong>{row.detail && <p>{row.detail}</p>}{row.extra && <small>{row.extra}</small>}</div>)}</div></div>;
}

function CertificationPage() {
  const [codes, setCodes] = useState("");
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (event) => {
    event.preventDefault();
    const standards = codes.split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
    if (!standards.length) return;
    setBusy(true); setError(""); setResult(null);
    try { setResult(await apiFetch("/analysis/certification-check", { method: "POST", body: jsonBody({ standards, tender_clause_text: text || null }) })); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <>
    <PageHeading eyebrow="Rule-based checks" title="Certification" description="Check cited standards against the certification rules available in the catalogue." />
    <ErrorMessage>{error}</ErrorMessage>
    <div className="split-layout certification-layout">
      <section className="panel"><div className="panel-heading"><div><h3>Run a certification check</h3><p>Results reflect the current local rules dataset.</p></div></div>
        <form className="form-stack" onSubmit={run}><label htmlFor="cert-codes">Standard codes <span className="optional">One per line or comma separated</span></label>
          <textarea id="cert-codes" rows={5} value={codes} onChange={(e) => setCodes(e.target.value)} placeholder="IS 1786&#10;IS 694" required />
          <label htmlFor="cert-text">Tender clause <span className="optional">Optional</span></label><textarea id="cert-text" rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste an applicable certification clause…" />
          <button className="button button-primary" type="submit" disabled={busy || !codes.trim()}><ShieldCheck size={16} aria-hidden="true" />{busy ? "Checking…" : "Check certification"}</button>
        </form>
      </section>
      <section className="panel"><div className="panel-heading"><div><h3>Check result</h3><p>Each item should be verified against authoritative sources.</p></div></div>
        {busy ? <Busy label="Checking certification rules" /> : result ? <>
          <div className="cert-summary"><span className={`cert-icon ${result.overall_status === "COMPLIANT" ? "cert-good" : "cert-review"}`}>{result.overall_status === "COMPLIANT" ? <CheckCircle2 size={21} /> : <AlertTriangle size={21} />}</span>
            <div><strong>{result.overall_status || "Manual verification required"}</strong><small>{result.standards_evaluated ?? result.checks?.length ?? 0} standards evaluated</small></div></div>
          {(result.checks || []).map((check, index) => <div className="cert-row" key={`${check.standard_code}-${index}`}><div><strong>{check.standard_code}</strong><p>{check.recommendation || check.alert || "Manual verification required."}</p>{check.alert && <small>{check.alert}</small>}</div>
            <StatusPill tone={String(check.compliance_status).includes("COMPLIANT") ? "green" : "amber"}>{check.compliance_status || "Review"}</StatusPill></div>)}
        </> : <EmptyState icon={ShieldCheck} title="No check run yet">Enter standards and run a check to see the rule-based results.</EmptyState>}
      </section>
    </div>
  </>;
}

function ReviewPage({ user }) {
  const [recommendations, setRecommendations] = useState([]);
  const [filter, setFilter] = useState("pending_review");
  const [comments, setComments] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const canSubmit = user.permissions?.includes("review:submit") || user.role === "admin";
  const canApprove = user.permissions?.includes("review:approve") || user.role === "admin";

  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (filter) params.set("status", filter);
      const data = await apiFetch(`/reviews/recommendations?${params}`);
      setRecommendations(data.recommendations || []);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const act = async (recommendationId, action) => {
    const comment = comments[recommendationId] || "";
    if (["reject", "flag", "comment", "request_review"].includes(action) && !comment.trim()) return;
    setSavingId(recommendationId); setError(""); setNotice("");
    try {
      await apiFetch(`/reviews/recommendations/${encodeURIComponent(recommendationId)}/actions`, {
        method: "POST",
        body: jsonBody({ action, comments: comment.trim() || null }),
      });
      setNotice("Review action saved. Tender approval remains a separate decision.");
      setComments((previous) => ({ ...previous, [recommendationId]: "" }));
      await load();
    } catch (err) { setError(err.message); }
    finally { setSavingId(null); }
  };

  return <>
    <PageHeading eyebrow="Human decision workflow" title="Review" description="Inspect the stored evidence and record accountable reviewer decisions." />
    <ErrorMessage>{error}</ErrorMessage>
    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    <div className="review-toolbar">
      <div className="review-safety"><ShieldCheck size={16} aria-hidden="true" /> Accepting a recommendation does not approve a tender.</div>
      <label htmlFor="review-status">Show</label>
      <select id="review-status" value={filter} onChange={(e) => setFilter(e.target.value)}>
        <option value="pending_review">Pending review</option><option value="review_requested">Review requested</option>
        <option value="flagged">Flagged</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option><option value="">All statuses</option>
      </select>
      <button className="button button-quiet" onClick={load} disabled={busy}>Refresh</button>
    </div>
    {!canSubmit && <div className="notice notice-error">Your role does not have permission to review recommendations.</div>}
    {busy ? <Busy label="Loading review queue" /> : recommendations.length ? <div className="review-queue">
      {recommendations.map((item) => <article className="review-card" key={item.id}>
        <div className="review-card-top"><div><div className="eyebrow">{item.project_code} · {item.project_title}</div>
          <h3><span>{item.standard_code}</span>{item.standard_title && <small>{item.standard_title}</small>}</h3></div>
          <StatusPill tone={item.status === "accepted" ? "green" : item.status === "rejected" ? "red" : item.status === "flagged" ? "amber" : "blue"}>{item.status.replaceAll("_", " ")}</StatusPill>
        </div>
        <div className="review-meta"><span>Confidence: {item.confidence_level}</span><span>Match: {Math.round((item.match_score || 0) * 100)}%</span>
          {item.version && <span>{item.version}</span>}<span>Certification: {item.certification_status}</span></div>
        <div className="review-rationale"><strong>Why this match</strong><p>{item.why_justification}</p>
          {item.relationship_summary && <p>{item.relationship_summary}</p>}{item.limitations && <p className="review-limitation">Limitations: {item.limitations}</p>}</div>
        <div className="review-evidence"><strong>Evidence ({item.evidence?.length || 0})</strong>
          {item.evidence?.length ? item.evidence.map((evidence) => <blockquote key={evidence.id}><p>“{evidence.source_text_snippet}”</p><footer>
            {evidence.document_name || evidence.standard_code || evidence.evidence_type}{evidence.clause_number ? ` · ${evidence.clause_number}` : ""}{evidence.page_number ? ` · page ${evidence.page_number}` : ""} · {Math.round((evidence.confidence_score || 0) * 100)}% confidence
          </footer></blockquote>) : <p className="field-hint">No evidence is attached. Resolve this data gap before treating the match as verified.</p>}
        </div>
        {canSubmit && <div className="review-actions">
          <label htmlFor={`review-comment-${item.id}`}>Reviewer comment <span className="optional">Required for reject, flag, comment, or request review</span></label>
          <textarea id={`review-comment-${item.id}`} rows={2} maxLength={5000} value={comments[item.id] || ""} onChange={(e) => setComments((previous) => ({ ...previous, [item.id]: e.target.value }))} placeholder="Add context or a reason for your decision…" />
          <div className="review-action-buttons">
            {canApprove && !["accepted", "rejected"].includes(item.status) && <>
              <button className="button button-primary" onClick={() => act(item.id, "accept")} disabled={savingId === item.id}><CheckCircle2 size={15} aria-hidden="true" />Accept</button>
              <button className="button button-danger" onClick={() => act(item.id, "reject")} disabled={savingId === item.id || !(comments[item.id] || "").trim()}>Reject</button>
            </>}
            <button className="button button-secondary" onClick={() => act(item.id, "flag")} disabled={savingId === item.id || !(comments[item.id] || "").trim()}>Flag</button>
            <button className="button button-secondary" onClick={() => act(item.id, "comment")} disabled={savingId === item.id || !(comments[item.id] || "").trim()}>Comment</button>
            <button className="button button-secondary" onClick={() => act(item.id, "request_review")} disabled={savingId === item.id || !(comments[item.id] || "").trim()}>Request review</button>
          </div>
        </div>}
        {item.review_history?.length > 0 && <div className="review-history"><strong>Decision history</strong>{item.review_history.map((event) => <div key={event.id}>
          <span>{event.reviewer_name} · {event.action.replaceAll("_", " ")}</span><small>{formatDate(event.created_at)}</small>{event.comments && <p>{event.comments}</p>}
        </div>)}</div>}
      </article>)}
    </div> : <EmptyState icon={ClipboardList} title="No recommendations in this queue">Persisted, evidence-linked recommendations appear here for human review.</EmptyState>}
  </>;
}

function AuditPage() {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [filter, setFilter] = useState("");
  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (filter.trim()) params.set("action", filter.trim());
      const data = await apiFetch(`/audit?${params}`);
      setEvents(data.events || []); setTotal(data.total || 0);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }, [filter]);
  useEffect(() => { load(); }, [load]);
  return <>
    <PageHeading eyebrow="Traceability" title="Audit" description="Read recent system events. Audit records are not editable from this workspace." />
    <ErrorMessage>{error}</ErrorMessage>
    <section className="panel audit-panel"><div className="panel-heading"><div><h3>Recent events</h3><p>{total} matching event{total === 1 ? "" : "s"}</p></div><button className="button button-quiet" onClick={load} disabled={busy}>Refresh</button></div>
      <form className="audit-filter" onSubmit={(e) => { e.preventDefault(); load(); }}><label htmlFor="audit-filter">Filter by action</label><input id="audit-filter" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="e.g. auth.login" /><button className="button button-secondary" type="submit">Apply filter</button></form>
      {busy ? <Busy label="Loading audit events" /> : events.length ? <div className="table-wrap"><table><thead><tr><th>Event</th><th>User</th><th>Entity</th><th>Time</th><th>Details</th></tr></thead><tbody>
        {events.map((event) => <tr key={event.id}><td><strong>{event.action}</strong><small>{event.ip_address || ""}</small></td><td>{event.user_email || "System"}</td><td>{event.entity_type}{event.entity_id ? <small>{event.entity_id}</small> : null}</td><td>{formatDate(event.timestamp)}</td><td className="audit-details">{event.details || "—"}</td></tr>)}
      </tbody></table></div> : <EmptyState icon={Activity} title="No audit events">Events will appear here as people use the workspace.</EmptyState>}
    </section>
  </>;
}

function SettingsPage({ user }) {
  const [language, setLanguage] = useState(() => localStorage.getItem("preferred_language") || "en");
  const [notice, setNotice] = useState("");
  const saveLanguage = (value) => {
    setLanguage(value); localStorage.setItem("preferred_language", value);
    setNotice("Display preference saved on this device.");
  };
  return <>
    <PageHeading eyebrow="Account and preferences" title="Settings" description="View your account role and manage local display preferences." />
    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    <div className="settings-grid">
      <section className="panel account-panel"><div className="panel-heading"><div><h3>Signed-in account</h3><p>Role and access come from the platform.</p></div></div>
        <div className="account-row"><span className="account-avatar"><UserRound size={22} aria-hidden="true" /></span><div><strong>{user.full_name || user.email}</strong><small>{user.email}</small></div></div>
        <div className="settings-pair"><span>Role</span><strong>{user.role || "—"}</strong></div>
        <div className="settings-pair"><span>Department</span><strong>{user.department || "—"}</strong></div>
        <div className="settings-pair"><span>Account status</span><StatusPill tone={user.is_active === false ? "red" : "green"}>{user.is_active === false ? "Inactive" : "Active"}</StatusPill></div>
      </section>
      <section className="panel"><div className="panel-heading"><div><h3>Language preference</h3><p>Saved in this browser for future translated labels.</p></div><Globe2 size={19} aria-hidden="true" /></div>
        <label htmlFor="preferred-language">Preferred language</label><select id="preferred-language" value={language} onChange={(e) => saveLanguage(e.target.value)}><option value="en">English</option><option value="hi">हिन्दी (Hindi)</option></select>
        <div className="settings-note">Hindi term translations are available in the analysis API. Most workspace labels currently display in English.</div>
      </section>
    </div>
  </>;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [activePage, setActivePage] = useState("dashboard");
  const [analysis, setAnalysis] = useState(null);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem(tokenKey);
    if (!token) { setAuthLoading(false); return; }
    apiFetch("/auth/me").then(setUser).catch(() => { localStorage.removeItem(tokenKey); localStorage.removeItem(refreshKey); }).finally(() => setAuthLoading(false));
  }, []);

  const current = useMemo(() => navigation.find((item) => item.id === activePage) || navigation[0], [activePage]);
  const logout = async () => {
    setLogoutError("");
    try { await apiFetch("/auth/logout", { method: "POST" }); }
    catch (err) { setLogoutError(err.message); }
    finally { localStorage.removeItem(tokenKey); localStorage.removeItem(refreshKey); setUser(null); setAnalysis(null); }
  };

  if (authLoading) return <main className="auth-loading"><Busy label="Checking your session" /></main>;
  if (!user) return <LoginPanel onLogin={setUser} />;

  const PageIcon = current.icon;
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar">
      <div className="sidebar-brand"><span className="brand-mark"><ShieldCheck size={22} aria-hidden="true" /></span><span><strong>IS Platform</strong><small>Compliance workspace</small></span></div>
      <div className="nav-caption">WORKSPACE</div>
      <nav className="side-nav" aria-label="Main navigation">{navigation.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${activePage === id ? "active" : ""}`} onClick={() => setActivePage(id)} aria-label={label} title={label} aria-current={activePage === id ? "page" : undefined}>
        <Icon size={18} aria-hidden="true" /><span>{label}</span>{activePage === id && <span className="nav-active-dot" />}
      </button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheck size={16} aria-hidden="true" /><span>Evidence first.<br />Human review always.</span></div>
        <div className="sidebar-user"><span className="user-avatar">{(user.full_name || user.email || "U").slice(0, 1).toUpperCase()}</span><span className="user-label"><strong>{user.full_name || user.email}</strong><small>{user.role || "Platform user"}</small></span><button className="icon-button" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button></div>
      </div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><PageIcon size={15} aria-hidden="true" /><strong>{current.label}</strong></div>
        <div className="topbar-right"><span className="topbar-role"><span className="online-dot" />Signed in as {user.role || "user"}</span><button className="mobile-signout" onClick={logout} aria-label="Sign out"><LogOut size={16} /></button></div>
      </header>
      {logoutError && <div className="logout-error"><ErrorMessage>{logoutError}</ErrorMessage></div>}
      <main id="main-content" className="page-content">
        {activePage === "dashboard" && <DashboardPage user={user} onNavigate={setActivePage} />}
        {activePage === "projects" && <ProjectsPage />}
        {activePage === "upload" && <UploadPage />}
        {activePage === "analysis" && <AnalysisPage onAnalysis={setAnalysis} />}
        {activePage === "recommendations" && <RecommendationsPage analysis={analysis} />}
        {activePage === "standards" && <StandardsPage />}
        {activePage === "certification" && <CertificationPage />}
        {activePage === "review" && <ReviewPage user={user} />}
        {activePage === "audit" && <AuditPage />}
        {activePage === "settings" && <SettingsPage user={user} />}
      </main>
      <footer className="app-footer"><span>IS Platform</span><span>Standards and evidence require human verification before use.</span></footer>
    </div>
  </div>;
}
