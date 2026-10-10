#!/usr/bin/env python3
"""Tester store — aligned with the design document (architecture.md).

Project-scoped documents; machine records (JSONL) inside, human documents
(Markdown) outside. This script is the contract enforcer for machine records;
the agent owns everything judgment-shaped.

Layout (under the configured external store root):
  projects/<project>/
    index.md                          directory listing (OKF index, no frontmatter)
    setup.md                          launch + setup notes (OKF concept)
    runs/<run-id>/run.jsonl           append-only events (machine record)
    runs/<run-id>/flow.md             selected human-readable test flow (OKF concept, generated)
    runs/<run-id>/report.md           compatibility copy of the generated flow report
    runs/<run-id>/artifacts/          screenshots, bound to their events
    findings.jsonl                    machine record behind findings.md
    findings.md                       unreviewed findings document (OKF concept, generated)
    bugs/index.md + issues/index.md   categorized finding documents
    knowledge/index.md + <topic>.md  project KB (topics are OKF concepts)
    data.json                         approved relative context directories
    runbooks/<runbook-id>.md          test plans (OKF concepts)

Markdown documents follow the Open Knowledge Format (OKF v0.2): every
concept file carries YAML frontmatter with a `type` (plus title,
description, tags, generated provenance); `index.md` files are plain
directory listings without frontmatter; links express relationships."""
from __future__ import annotations
import argparse, datetime as dt, fcntl, hashlib, json, os, re, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = Path("/home/abs-bot-01/dev/gd-math-config/testing")
DATA = Path(os.environ.get("PI_TESTER_DATA_ROOT", str(DEFAULT_DATA_ROOT))).expanduser()
PROJECTS = DATA / "projects"
GLOBAL_KB = DATA / "global-knowledge.md"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,100}$")
RESULTS = ("passed", "failed", "blocked", "skipped")
RUN_STATUSES = ("passed", "failed", "partial", "blocked")
MODES = ("explore", "continue", "runbook")
FINDING_STATUSES = ("new", "needs-retest", "confirmed", "not-a-bug", "suppressed", "fixed")
KB_TOPICS = ("app-rules", "known-non-issues", "focus-areas", "environment", "decisions")
FINDING_CATEGORIES = ("bug", "issue")
UNCLASSIFIED_CATEGORY = "finding"

def slug(value): return value if NAME_RE.fullmatch(value or "") else None

def now(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def lines(path):
    if not path.exists(): return []
    out=[]
    for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        try: out.append(json.loads(line))
        except json.JSONDecodeError as e: raise SystemExit(f"invalid JSONL {path}:{n}: {e}")
    return out

def append(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
        f.flush(); os.fsync(f.fileno()); fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f: f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def project_dir(name):
    s=slug(name) or die("invalid project name")
    p=PROJECTS/s
    if not p.is_dir(): die(f"project does not exist: {s} (project-create first)")
    return p


def checked_context_paths(project, values):
    """Validate project context entries as existing, relative directories.

    Context is deliberately constrained to the tester data root.  Resolving
    before the boundary check also prevents a symlink from escaping that
    boundary.  The returned values preserve the project-relative spelling
    stored in data.json.
    """
    if not isinstance(values, list):
        die("data.json: context_paths must be an array")
    root = DATA.resolve()
    seen = set()
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            die("data.json: every context_paths entry must be a non-empty relative directory path")
        raw = value.strip()
        candidate = Path(raw)
        if candidate.is_absolute():
            die(f"data.json: context path must be relative to the project directory: {raw}")
        resolved = (project / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            die(f"data.json: context path escapes the tester data root: {raw}")
        if not resolved.is_dir():
            die(f"data.json: context path is not an existing directory: {raw}")
        if raw in seen:
            die(f"data.json: duplicate context path: {raw}")
        seen.add(raw)
        result.append(raw)
    return result


def read_project_config(project):
    """Read and validate the project's durable context configuration."""
    config = project / "data.json"
    if not config.is_file():
        die(f"project is missing data.json: {project.name}")
    try:
        value = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"invalid project data.json: {exc}")
    if not isinstance(value, dict) or set(value) != {"context_paths"}:
        die("data.json must contain only the context_paths array")
    return {"context_paths": checked_context_paths(project, value["context_paths"])}


def write_project_config(project, context_paths=()):
    values = checked_context_paths(project, list(context_paths))
    atomic_write(project / "data.json", json.dumps({"context_paths": values}, indent=2) + "\n")


def run_dir(project, rid):
    d=project_dir(project)/"runs"/(slug(rid) or die("invalid run id"))
    return d

def run_events(d):
    return lines(d/"run.jsonl")

def active_run(project, rid):
    jp=project_dir(project)/"runs"/(slug(rid) or die("invalid run id"))/"run.jsonl"
    ev=lines(jp)
    if not ev: die("run does not exist; run start first")
    if ev[-1].get("event")=="run_completed": die("run already completed")
    return ev

def die(msg): raise SystemExit(msg)

def parse_json(value, default):
    if value is None: return default
    try: return json.loads(value)
    except json.JSONDecodeError: return default

def rel_project_path(path, pname):
    """Normalize an image path so it resolves relative to project-root markdown files."""
    p = str(path).strip()
    for pref in (f"projects/{pname}/", "projects/"):
        if p.startswith(pref): return p[len(pref):]
    return p

def split_pairs(value, sep=";"):
    return [x.strip() for x in (value or "").split(sep) if x.strip()]

# ---------- OKF helpers ----------

OKF_VERSION = "0.2"
ACTOR = "tester/1.0"

def yq(v): return json.dumps(str(v), ensure_ascii=False)

def fm(typ, title, description="", resource="", tags=(), extra=()):
    """OKF front matter for a generated concept document."""
    out=[f"type: {typ}", f"title: {yq(title)}"]
    if description: out.append(f"description: {yq(description)}")
    if resource: out.append(f"resource: {resource}")
    if tags: out.append("tags: [" + ", ".join(tags) + "]")
    out += list(extra)
    out.append(f"generated: {{ by: {ACTOR}, at: {now()} }}")
    return "---\n" + "\n".join(out) + "\n---\n\n"

def fm_field(text, key):
    """Read one scalar field from a document's YAML front matter."""
    m=re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m: return ""
    mm=re.search(rf"(?m)^{key}:\s*(.+)$", m.group(1))
    return mm.group(1).strip().strip('"') if mm else ""

def image_grid(items):
    """Render evidence images as tables: chunks of 4, one row per image + Notes cell."""
    out=[]
    for i in range(0,len(items),4):
        out.append("| Evidence | Notes |\n|---|-------|\n")
        for rp,cap in items[i:i+4]:
            out.append(f"| ![{Path(rp).stem}]({rp}) | {cap} |\n")
        out.append("\n")
    return "".join(out)

# ---------- projects ----------

def rebuild_project_index(p):
    """Project index.md is an OKF directory listing (no frontmatter)."""
    out=[f"# Project index — {p.name}\n\n"]
    out.append("# Setup\n\n* [Setup](setup.md) - how to launch and configure the app under test\n\n")
    out.append("# Runs\n\n")
    runs=sorted((p/"runs").glob("*/run.jsonl"))
    if runs:
        for jp in runs:
            rid=jp.parent.name
            flow=jp.parent/"flow.md"
            report=jp.parent/"report.md"
            doc=flow if flow.exists() else report
            desc=fm_field(doc.read_text(encoding="utf-8"),"description") if doc.exists() else ""
            target=f"runs/{rid}/{doc.name}" if doc.exists() else f"runs/{rid}/run.jsonl"
            out.append(f"* [Run {rid}]({target}) - {desc or 'exploration/test run'}\n")
    else:
        out.append("No runs yet.\n")
    out.append("\n# Findings\n\n")
    finding_rows=lines(p/"findings.jsonl") if (p/"findings.jsonl").exists() else []
    pending_count=sum(finding_category(row)==UNCLASSIFIED_CATEGORY for row in finding_rows)
    if (p/"findings.md").exists():
        out.append(f"* [Findings](findings.md) - {pending_count} awaiting human review\n")
    for category in FINDING_CATEGORIES:
        count=sum(finding_category(row)==category for row in finding_rows)
        if count:
            label=category.title() + " findings"
            out.append(f"* [{label}]({finding_document(category)}) - {count} classified finding(s)\n")
    if not finding_rows:
        out.append("No findings yet.\n")
    out.append("\n# Knowledge\n\n* [Knowledge index](knowledge/index.md) - reviewed project knowledge\n\n")
    out.append("# Runbooks\n\n")
    rbs=sorted((p/"runbooks").glob("*.md"))
    if rbs:
        for rb in rbs:
            d=fm_field(rb.read_text(encoding="utf-8"),"description") or "test plan"
            out.append(f"* [{rb.stem}](runbooks/{rb.name}) - {d}\n")
    else:
        out.append("No runbooks yet.\n")
    atomic_write(p/"index.md", "".join(out))

def rebuild_root_index():
    """Bundle-root index; per OKF it may carry okf_version."""
    # A valid store always has the cross-project KB, even before the first
    # entry is added.  Otherwise the documented project-create -> validate
    # workflow leaves a freshly-created store invalid.
    if not GLOBAL_KB.exists():
        atomic_write(GLOBAL_KB, fm(
            "Knowledge",
            "Global knowledge",
            "Cross-project knowledge: standing decisions, environment facts, and rules that apply beyond a single project.",
            tags=["knowledge", "global"],
        ) + "# Global knowledge\n\nNo entries yet.\n")
    out=[f"---\nokf_version: {OKF_VERSION}\n---\n\n# Tester knowledge bundle\n\n"]
    out.append("# Projects\n\n")
    projs=[q for q in sorted(PROJECTS.glob("*")) if q.is_dir()] if PROJECTS.exists() else []
    out += [f"* [{q.name}](projects/{q.name}/) - test project bundle\n" for q in projs] or ["No projects yet.\n"]
    out.append("\n# Global knowledge\n\n* [Global knowledge](global-knowledge.md) - cross-project decisions and rules\n")
    atomic_write(DATA/"index.md", "".join(out))

def cmd_project_create(a):
    s=slug(a.name) or die("invalid project name")
    p=PROJECTS/s
    if p.exists(): die(f"project already exists: {s}")
    for sub in ("runs","knowledge","runbooks","bugs","issues"): (p/sub).mkdir(parents=True, exist_ok=True)
    write_project_config(p, a.context_path)
    atomic_write(p/"setup.md", fm("App Setup", s, f"How to launch and configure {s} under test.", tags=["setup"])
        + f"# Setup — {s}\n\n- **application:** (name)\n- **executable:** (path to the supplied binary)\n- **launch:** approved `bin/pi-tester-launch <executable>`\n- **environment:** Linux desktop on disposable Xvfb display :1042 (1280x720)\n- **setup notes:** profiles, save data, window sizing\n")
    for topic in KB_TOPICS:
        tf=p/"knowledge"/f"{topic}.md"
        if not tf.exists():
            atomic_write(tf, fm("Knowledge", f"{topic} — {s}", topic.replace("-"," ") + f" for project {s}.", tags=["knowledge", topic])
                + f"# {topic.replace('-',' ').title()}\n\nNo entries yet.\n")
    rebuild_kb_index(p/"knowledge", s)
    rebuild_findings_documents(p, [])
    rebuild_project_index(p)
    rebuild_root_index()
    print(json.dumps({"project":s,"root":str(p.relative_to(DATA))}))

def cmd_project_list(a):
    out=[]
    for p in sorted(PROJECTS.glob("*")) if PROJECTS.exists() else []:
        if not p.is_dir(): continue
        out.append({"project":p.name,"runs":len(list((p/'runs').glob('*/run.jsonl'))),"findings":len(lines(p/'findings.jsonl')) if (p/'findings.jsonl').exists() else 0,"runbooks":len(list((p/'runbooks').glob('*.md')))})
    print(json.dumps({"projects":out},ensure_ascii=False))

# ---------- run ----------

def cmd_start(a):
    p=project_dir(a.project); read_project_config(p)
    rid=slug(a.run_id) or die("invalid run id")
    rd=p/"runs"/rid
    if (rd/"run.jsonl").exists() and lines(rd/"run.jsonl"): die(f"run already exists: {rid}")
    (rd/"artifacts").mkdir(parents=True, exist_ok=True)
    header={"event":"run_started","run_id":rid,"project":a.project,"target":a.target,"purpose":a.purpose,
            "boundary":a.boundary,"environment":a.environment,"mode":a.mode,"status":"open","timestamp":now()}
    if a.mode=="runbook":
        if not a.runbook_id: die("runbook mode requires --runbook-id")
        runbook_id=slug(a.runbook_id) or die("invalid runbook id")
        runbook=p/"runbooks"/f"{runbook_id}.md"
        if not runbook.is_file(): die(f"runbook does not exist: {runbook_id}")
        status=re.search(r"(?m)^status:\s*(\S+)\s*$", runbook.read_text(encoding="utf-8"))
        if not status or status.group(1)!="active": die(f"runbook is not active: {runbook_id}")
        header["runbook_id"]=runbook_id
    append(rd/"run.jsonl", header)
    print(json.dumps({"run_id":rid,"run_dir":str(rd.relative_to(DATA)),"artifacts":str((rd/'artifacts').relative_to(DATA))}))

def cmd_action(a):
    ev=active_run(a.project, a.run_id); rd=project_dir(a.project)/"runs"/slug(a.run_id)
    artifacts=[]
    for name in split_pairs(a.artifacts, ","):
        f=rd/"artifacts"/name
        if not f.is_file(): die(f"artifact does not exist in run artifacts dir: {name}")
        artifacts.append("artifacts/"+name)
    obj={"seq":max((x.get("seq",0) for x in ev if isinstance(x.get("seq"),int)),default=0)+1,
         "event":"action","timestamp":now(),"action":a.action,"result":a.result}
    if artifacts: obj["artifacts"]=artifacts
    for key,val in (("target",a.target),("test",a.test),("expected",a.expected),("observed",a.observed),("notes",a.notes)):
        if val not in (None,""): obj[key]=val
    append(rd/"run.jsonl", obj); print(json.dumps(obj,ensure_ascii=False))

def cmd_complete(a):
    ev=active_run(a.project, a.run_id); rd=project_dir(a.project)/"runs"/slug(a.run_id)
    obj={"event":"run_completed","run_id":a.run_id,"project":a.project,"status":a.status,"summary":a.summary,"timestamp":now()}
    append(rd/"run.jsonl", obj); print(json.dumps(obj,ensure_ascii=False))

def cmd_report(a):
    p=project_dir(a.project); rd=p/"runs"/slug(a.run_id); ev=run_events(rd)
    if not ev or ev[0].get("event")!="run_started": die("run has no header event")
    head=ev[0]; acts=[e for e in ev if e.get("event")=="action"]
    last=ev[-1]; done=last.get("event")=="run_completed"
    purpose=head.get("purpose","") or a.run_id
    extra=[f'result: {last.get("status") if done else "open"}']
    if head.get("runbook_id"): extra.append(f'source_runbook: {head["runbook_id"]}')
    out=[fm("Run", f"Run {a.run_id}", purpose, f"runs/{a.run_id}/run.jsonl", ["run", head.get("mode","explore")], extra),
         f"# Run {a.run_id} — {purpose}\n\n",
         f"- **project:** [{head.get('project')}](../../index.md)\n- **target:** `{head.get('target')}`\n- **mode:** {head.get('mode')}"
         + (f" — runbook: [{head['runbook_id']}](../../runbooks/{head['runbook_id']}.md)" if head.get("runbook_id") else "") + "\n",
         f"- **boundary:** {head.get('boundary')}\n- **environment:** {head.get('environment')}\n- **started:** {head.get('timestamp')}\n"]
    if done: out.append(f"- **status:** {last.get('status')} — {last.get('summary','')}\n")
    out.append("\n## Contents\n\n- [Coverage](#coverage)\n- [Blocked work](#blocked-work)\n- [Summary](#summary)\n- [Evidence](#evidence)\n\n")
    if acts: out.append("Step anchors: " + " · ".join(f"[{e['seq']}](#seq-{e['seq']})" for e in acts) + "\n\n")
    out.append("## Coverage\n\n")
    for e in acts:
        out.append(f'<a id="seq-{e["seq"]}"></a>\n\n### {e["seq"]} — {e["action"]} (`{e["result"]}`)\n\n')
        for k in ("test","expected","observed","notes"):
            if e.get(k): out.append(f"**{k}:** {e[k]}\n\n")
        imgs=e.get("artifacts",[])
        if len(imgs)==1:
            stem=Path(imgs[0]).stem
            out.append(f"![{stem}]({imgs[0]})\n\n*{stem} — {e.get('action','')}*\n\n")
        elif imgs:
            out.append(image_grid([(rp, f"seq {e['seq']}: {e.get('action','evidence')}") for rp in imgs]))
    blocked=[e for e in acts if e.get("result")=="blocked"]
    out.append("## Blocked work\n\n" + ("\n".join(f"- seq {e['seq']}: {e['action']}" for e in blocked)+"\n" if blocked else "None.\n"))
    out.append("\n## Summary\n\n" + ((last.get("summary","")+"\n") if done else "(run still open)\n"))
    arts=[art for e in acts for art in e.get("artifacts",[])]
    if arts:
        out.append("\n## Evidence\n\n")
        out+= "".join(f"- [{Path(x).name}]({x})\n" for x in arts)
    # flow.md is the canonical selected flow. Keep report.md as a generated
    # compatibility copy for existing links and consumers.
    content="".join(out)
    atomic_write(rd/"flow.md", content)
    atomic_write(rd/"report.md", content)
    rebuild_project_index(p)
    print(json.dumps({"flow":str((rd/'flow.md').relative_to(DATA)),
                      "report":str((rd/'report.md').relative_to(DATA)),
                      "events":len(ev)}))

# ---------- findings ----------

def findings_path(project): return project_dir(project)/"findings.jsonl"

def img_list(value):
    out=[]
    for pair in split_pairs(value):
        # tolerate multiple paths comma-joined in one pair (no caption marker)
        items=[x.strip() for x in pair.split(",")] if ("|" not in pair and "," in pair) else [pair]
        for x in items:
            path,_,cap=x.partition("|")
            if not path: die(f"bad image spec: {x}")
            out.append({"path":path.strip(),"caption":cap.strip()})
    return out

def cmd_finding(a):
    p=project_dir(a.project); rows=lines(p/"findings.jsonl")
    fp=a.fingerprint or hashlib.sha1(re.sub(r"\W+"," ",a.title.lower()).encode()).hexdigest()[:16]
    matches=[i for i,x in enumerate(rows) if x.get("fingerprint")==fp or (not a.fingerprint and x.get("title"," ").casefold()==a.title.casefold())]
    new_imgs=img_list(a.images)
    category = finding_category(rows[matches[0]]) if matches else UNCLASSIFIED_CATEGORY
    proposal = a.proposed_for_kb.strip()
    base={"finding_id":a.finding_id or f"finding-{a.run_id}-{len(rows)+1:03d}","fingerprint":fp,"run_id":a.run_id,
          "title":a.title,"category":category,"severity":a.severity,"confidence":a.confidence,"status":a.status,
          "description":a.description,"steps":parse_json(a.steps,[]),"expected":a.expected,"observed":a.observed,
          "images":new_imgs,"references":split_pairs(a.references),"proposed_for_kb":proposal,
          "proposal_state":"pending" if proposal else "","recurrence":{},"updated_at":now()}
    if matches:
        old=rows[matches[0]]
        rec=old.get("recurrence",{})
        if isinstance(rec,str): rec={"occurrences":1,"note":rec}
        occ=rec.get("occurrences",1)+1
        rec.update(occurrences=occ, last_seen_run=a.run_id, last_seen_at=now())
        rec.setdefault("first_seen_run", old.get("run_id", a.run_id))
        # Human classification is durable; a recurrence must not return a
        # classified bug/issue to the unclassified intake document.
        updates={k:v for k,v in base.items() if v not in (None,"",[])}
        updates["category"]=finding_category(old)
        merged={**old, **updates}
        merged["images"]=old.get("images",[])+[im for im in new_imgs if im not in old.get("images",[])]
        merged["references"]=sorted(set(old.get("references",[]))|set(base["references"]))
        merged["recurrence"]=rec; merged["updated_at"]=now()
        rows[matches[0]]=merged; verb="updated"
    else:
        base["recurrence"]={"occurrences":1,"first_seen_run":a.run_id,"first_seen_at":now(),"last_seen_run":a.run_id,"last_seen_at":now()}
        rows.append(base); verb="created"
    atomic_write(p/"findings.jsonl", "".join(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n" for x in rows))
    rebuild_findings_documents(p, rows)
    rebuild_project_index(p)
    print(json.dumps({"result":verb,"finding":rows[matches[0]] if matches else base},ensure_ascii=False))

def cmd_finding_status(a):
    p=project_dir(a.project); rows=lines(p/"findings.jsonl")
    reason=a.reason.strip()
    if not reason:
        die("finding-status requires --reason so the human decision is durable")
    idx=next((i for i,x in enumerate(rows) if x.get("finding_id")==a.finding_id), None)
    if idx is None: die(f"finding not found: {a.finding_id}")
    row=rows[idx]
    log={"from":row.get("status"),"status":a.status,"reason":reason,"by":"human","at":now()}
    if a.category:
        log["category_from"]=finding_category(row); log["category_to"]=a.category
        row["category"]=a.category
    row.setdefault("status_log",[]).append(log)
    row["status"]=a.status; row["updated_at"]=now()
    atomic_write(p/"findings.jsonl", "".join(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n" for x in rows))
    rebuild_findings_documents(p, rows)
    rebuild_project_index(p)
    print(json.dumps(row,ensure_ascii=False))

def finding_category(row):
    category=row.get("category", UNCLASSIFIED_CATEGORY)
    return category if category in (*FINDING_CATEGORIES, UNCLASSIFIED_CATEGORY) else UNCLASSIFIED_CATEGORY


def finding_document(category):
    """Return the category index inside its findings directory."""
    return f"{category}s/index.md"


def migrate_legacy_category_documents(project):
    """Move legacy flat category documents into their category directories."""
    for category in FINDING_CATEGORIES:
        legacy = project / f"{category}s.md"
        current = project / finding_document(category)
        if legacy.is_file() and not current.exists():
            current.parent.mkdir(parents=True, exist_ok=True)
            os.replace(legacy, current)


def render_findings_document(project, entries, category=None):
    """Render the root findings index or one categorized findings document."""
    p=project
    prefix=""
    label=category.title() + " findings" if category else "Findings"
    resource="findings.jsonl"
    extra=[f"category: {category}"] if category else []
    out=[fm("Findings", f"{label} — {p.name}", f"Human-readable {label.casefold()} for project {p.name}.", resource, ["findings"] + ([category] if category else []), extra),
         f"# {label} — {p.name}\n\n",
         "| # | Finding | Description | Severity | Status |\n|---|---------|-------------|----------|--------|\n"]
    if not entries:
        out.append("| — | No findings | No findings in this category yet. | — | — |\n\n")
    for i,x in entries:
        desc=(x.get("description") or x.get("observed") or "").replace("|","\\|")
        if len(desc)>110: desc=desc[:107]+"…"
        out.append(f'| {i} | [F{i}](#f{i}) | {desc} | {x.get("severity")} | {x.get("status")} |\n')
    out.append("\n")
    for i,x in entries:
        out.append(f'<a id="f{i}"></a>\n\n## F{i} — {x.get("title")}\n\n')
        out.append(f'**category:** {finding_category(x)}\n\n')
        out.append(f'**run:** [{x.get("run_id")}]({prefix}runs/{x.get("run_id")}/flow.md)\n\n')
        if x.get("description"): out.append(f"**description:** {x['description']}\n\n")
        if x.get("steps"):
            out.append("**steps:**\n"); out+= "".join(f"{n}. {s}\n" for n,s in enumerate(x["steps"],1)); out.append("\n")
        if x.get("expected"): out.append(f"**expected:** {x['expected']}\n\n")
        if x.get("observed"): out.append(f"**observed:** {x['observed']}\n\n")
        imgs=x.get("images") or []
        if len(imgs)==1:
            rp=prefix + rel_project_path(imgs[0]["path"], p.name)
            cap=imgs[0].get("caption") or Path(imgs[0]["path"]).name
            out.append(f"![{Path(rp).stem}]({rp})\n\n*{cap}*\n\n")
        elif imgs:
            out.append(image_grid([(prefix + rel_project_path(im["path"], p.name), im.get("caption") or Path(im["path"]).name) for im in imgs]))
        if x.get("references"): out.append("**references:** " + ", ".join(f"`{r}`" for r in x["references"]) + "\n\n")
        rec=x.get("recurrence",{})
        if isinstance(rec,str): out.append(f"**seen in:** {rec}\n\n")
        else: out.append(f"**seen in:** {rec.get('occurrences',1)} run(s) (first: {rec.get('first_seen_run')}, latest: {rec.get('last_seen_run')})\n\n")
        if x.get("proposal_state")=="pending" and x.get("proposed_for_kb"):
            out.append(f"**proposed for KB:** {x['proposed_for_kb']} *(awaiting human confirmation)*\n\n")
    return "".join(out)


def rebuild_findings_documents(project, rows):
    """Write findings.md and category indexes under bugs/ and issues/."""
    p=project
    migrate_legacy_category_documents(p)
    entries=list(enumerate(rows,1))
    pending=[entry for entry in entries if finding_category(entry[1])==UNCLASSIFIED_CATEGORY]
    atomic_write(p/"findings.md", render_findings_document(p, pending))
    for category in FINDING_CATEGORIES:
        category_entries=[entry for entry in entries if finding_category(entry[1])==category]
        atomic_write(p/finding_document(category), render_findings_document(p, category_entries, category))


def cmd_findings_report(a):
    p=project_dir(a.project); rows=lines(p/"findings.jsonl")
    rebuild_findings_documents(p, rows)
    rebuild_project_index(p)
    print(json.dumps({"report":str((p/'findings.md').relative_to(DATA)),
                      "documents":[str((p/finding_document(category)).relative_to(DATA)) for category in FINDING_CATEGORIES],
                      "findings":len(rows)}))

# ---------- knowledge ----------

def kb_entry(title, content, source, reviewed_by=None):
    review=reviewed_by or "human"
    return f"- **{title}** — {content}\n  (Source: {source}; review: {now()[:10]} by {review})\n"

def rebuild_kb_index(kb_dir, title):
    items=[]
    for f in sorted(kb_dir.glob("*.md")):
        if f.name=="index.md": continue
        d=fm_field(f.read_text(encoding="utf-8"),"description") or f.stem
        items.append(f"* [{f.stem}]({f.name}) - {d}\n")
    text=f"# Knowledge index — {title}\n\n" + ("".join(items) or "No entries yet.\n")
    atomic_write(kb_dir/"index.md", text)

def cmd_kb_add(a):
    entry=kb_entry(a.title, a.content, a.source, a.reviewed_by)
    if a.global_:
        if not GLOBAL_KB.exists():
            atomic_write(GLOBAL_KB, fm("Knowledge", "Global knowledge", "Cross-project knowledge: standing decisions, environment facts, and rules that apply beyond a single project.", tags=["knowledge","global"]))
        with GLOBAL_KB.open("a",encoding="utf-8") as f: f.write("\n" + entry)
        print(json.dumps({"saved":str(GLOBAL_KB.relative_to(DATA)),"scope":"global"}))
        return
    kb=project_dir(a.project)/"knowledge"
    topic=slug(a.topic) or die("invalid topic slug")
    if a.topic not in KB_TOPICS: die(f"topic must be one of {KB_TOPICS}")
    with (kb/f"{topic}.md").open("a",encoding="utf-8") as f: f.write("\n"+entry)
    rebuild_kb_index(kb, a.project)
    print(json.dumps({"saved":str((kb/f'{topic}.md').relative_to(DATA)),"topic":topic}))

def cmd_kb_propose(a):
    p=project_dir(a.project); rows=lines(p/"findings.jsonl")
    idx=next((i for i,x in enumerate(rows) if x.get("finding_id")==a.finding_id), None)
    if idx is None: die("finding does not exist")
    rows[idx]["proposed_for_kb"]=a.note or rows[idx].get("proposed_for_kb") or f"{rows[idx].get('title')} — {rows[idx].get('observed','')}"
    rows[idx]["proposal_state"]="pending"; rows[idx]["updated_at"]=now()
    atomic_write(p/"findings.jsonl", "".join(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n" for x in rows))
    rebuild_findings_documents(p, rows)
    rebuild_project_index(p)
    print(json.dumps({"finding_id":a.finding_id,"proposal_state":"pending"}))

def cmd_kb_accept(a):
    p=project_dir(a.project); rows=lines(p/"findings.jsonl")
    idx=next((i for i,x in enumerate(rows) if x.get("finding_id")==a.finding_id), None)
    if idx is None: die("finding does not exist")
    text=rows[idx].get("proposed_for_kb") or die("nothing proposed for this finding")
    topic=slug(a.topic) or die("invalid topic slug")
    if a.topic not in KB_TOPICS: die(f"topic must be one of {KB_TOPICS}")
    kb=p/"knowledge"
    with (kb/f"{topic}.md").open("a",encoding="utf-8") as f:
        f.write("\n"+kb_entry(rows[idx].get("title",""), text, f"finding {a.finding_id}; accepted by human", a.confirmed_by))
    rows[idx]["proposal_state"]="accepted"; rows[idx]["updated_at"]=now()
    atomic_write(p/"findings.jsonl", "".join(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n" for x in rows))
    rebuild_kb_index(kb, p.name)
    rebuild_findings_documents(p, rows)
    rebuild_project_index(p)
    print(json.dumps({"finding_id":a.finding_id,"proposal_state":"accepted","topic":topic}))

def cmd_kb_reject(a):
    p=project_dir(a.project); rows=lines(p/"findings.jsonl")
    idx=next((i for i,x in enumerate(rows) if x.get("finding_id")==a.finding_id), None)
    if idx is None: die("finding does not exist")
    rows[idx]["proposal_state"]="rejected"; rows[idx]["updated_at"]=now()
    atomic_write(p/"findings.jsonl", "".join(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n" for x in rows))
    rebuild_findings_documents(p, rows)
    rebuild_project_index(p)
    print(json.dumps({"finding_id":a.finding_id,"proposal_state":"rejected"}))

# ---------- runbooks ----------

def runbook_path(project, rid): return project_dir(project)/"runbooks"/f"{slug(rid)}.md"

def cmd_runbook_create(a):
    p=project_dir(a.project); rb=p/"runbooks"/f"{slug(a.runbook_id)}.md"
    if rb.exists(): die("runbook already exists")
    if a.file:
        src=Path(a.file)
        if not src.is_file(): die("source file does not exist")
        atomic_write(rb, src.read_text(encoding="utf-8"))
    else:
        fmtext=fm("Runbook", a.title, "Test plan for the app under test.", tags=["runbook"],
            extra=[f"status: {'active' if a.active else 'draft'}", "version: 1",
                   f"created_by: {'human' if a.human else ACTOR}"])
        atomic_write(rb, fmtext + f"# Runbook — {a.title}\n\n## Setup\n\n(preconditions)\n\n## Tests\n\n### T1 — (title)\n\n- **objective:**\n- **steps:** 1.\n- **expected:**\n- **evidence:**\n")
    rebuild_project_index(p)
    print(json.dumps({"runbook":str(rb.relative_to(DATA)),"status":"created"}))

def cmd_runbook_freeze(a):
    p=project_dir(a.project); rd=p/"runs"/slug(a.run_id); ev=run_events(rd)
    acts=[e for e in ev if e.get("event")=="action" and (not a.seqs or e.get("seq") in {int(s) for s in split_pairs(a.seqs,",")})]
    if not acts: die("no action events to freeze")
    want={int(s) for s in split_pairs(a.seqs,",")} if a.seqs else None
    head=ev[0]; rb=p/"runbooks"/f"{slug(a.runbook_id)}.md"
    if rb.exists(): die("runbook already exists")
    purpose=head.get("purpose","")
    fmtext=fm("Runbook", a.runbook_id, f"Test plan frozen from run {a.run_id}" + (f" — {purpose}" if purpose else ".") + ".", tags=["runbook"],
        extra=["status: draft", "version: 1",
               "sources:", f"  - id: run-{a.run_id}", f"    resource: runs/{a.run_id}/run.jsonl", f"    title: source run {a.run_id}"])
    out=[fmtext, f"# Runbook — {a.runbook_id}\n\n",
         f"**source run:** [{a.run_id}](../runs/{a.run_id}/flow.md) — purpose: {purpose}\n\n",
         "## Setup\n\n- preconditions, test data, and window sizing (fill in from the source run)\n\n## Tests\n\n"]
    n=0
    for e in ev:
        if e.get("event")!="action" or (want and e.get("seq") not in want): continue
        n+=1
        out.append(f"### T{n} — {e.get('action')}\n\n- **objective:** {e.get('observed') or e.get('action')}\n")
        steps=e.get("observed") or e.get("target") or e.get("action")
        out.append(f"- **steps:** 1. {steps}\n- **expected:** (fill in)\n")
        if e.get("artifacts"):
            ev_links=", ".join(f"[{Path(x).name}](../runs/{a.run_id}/{x})" for x in e["artifacts"])
            out.append(f"- **evidence:** {ev_links}\n")
        out.append("\n")
    atomic_write(rb, "".join(out))
    rebuild_project_index(p)
    print(json.dumps({"runbook":str(rb.relative_to(DATA)),"tests":n,"status":"draft"}))

def cmd_runbook_validate(a):
    targets=[(a.runbook_id,)] if a.runbook_id else [(p.name,) for p in sorted((project_dir(a.project)/'runbooks').glob('*.md'))]
    problems=[]
    for t in targets:
        rid=t[0].removesuffix(".md") if t[0].endswith(".md") else t[0]
        rb=project_dir(a.project)/"runbooks"/f"{rid}.md"
        text=rb.read_text(encoding="utf-8")
        if not fm_field(text,"type"): problems.append(f"{rid}: missing OKF frontmatter")
        status=re.search(r"(?m)^status:\s*(\S+)\s*$", text)
        if not status or status.group(1) not in ("draft","active","retired"): problems.append(f"{rid}: missing/invalid status")
        tests=re.findall(r"^### (T\d+) — ", text, re.M)
        if len(tests)!=len(set(tests)): problems.append(f"{rid}: duplicate test ids")
        for m in re.finditer(r"^### (T\d+) — (.*?)(?=\n### |\Z)", text, re.S|re.M):
            sec=m.group(0)
            for key in ("objective","steps","expected"):
                if f"**{key}:**" not in sec: problems.append(f"{rid}: test {m.group(1)} missing **{key}:**")
    print(json.dumps({"valid":not problems,"runbooks":len(targets),"problems":problems}))
    if problems: sys.exit(1)

# ---------- history & validation ----------

def cmd_history(a):
    q=a.query.casefold(); hits=[]
    for f in DATA.rglob("*"):
        if f.is_file() and f.suffix in (".jsonl",".md") and q in f.read_text(encoding="utf-8",errors="replace").casefold():
            hits.append(str(f.relative_to(DATA)))
    print(json.dumps({"query":a.query,"matches":sorted(set(hits))},ensure_ascii=False))

def cmd_validate(a):
    problems=[]; checked=[]
    if not GLOBAL_KB.exists(): problems.append("missing global-knowledge.md")
    elif not fm_field(GLOBAL_KB.read_text(encoding="utf-8"),"type"): problems.append("global-knowledge.md: missing OKF frontmatter/type")
    if (DATA/"index.md").exists():
        checked.append("index.md (bundle root)")
    for p in sorted(PROJECTS.glob("*")):
        if not p.is_dir(): continue
        for sub,why in (("index.md","project index.md"),("knowledge/index.md","knowledge index"),("setup.md","setup.md"),("data.json","data.json"),("findings.md","findings.md")):
            if not (p/sub).exists(): problems.append(f"{p.name}: missing {why}")
        for category in FINDING_CATEGORIES:
            category_index = p/finding_document(category)
            if not category_index.is_file():
                problems.append(f"{p.name}: missing {finding_document(category)}")
        if (p/"data.json").is_file():
            try:
                config=json.loads((p/"data.json").read_text(encoding="utf-8"))
                if not isinstance(config,dict) or set(config) != {"context_paths"}:
                    problems.append(f"{p.name}/data.json: must contain only the context_paths array")
                else:
                    try:
                        checked_context_paths(p, config["context_paths"])
                    except SystemExit as exc:
                        problems.append(f"{p.name}/data.json: {exc}")
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"{p.name}/data.json: invalid JSON ({exc})")
        for md in sorted(p.rglob("*.md")):
            if md.name in ("index.md","log.md"): continue
            if not fm_field(md.read_text(encoding="utf-8"),"type"):
                problems.append(f"{p.name}/{md.relative_to(p)}: missing OKF frontmatter/type")
        fp=p/"findings.jsonl"
        if fp.exists():
            for row in lines(fp):
                for im in row.get("images",[]):
                    if not (p/rel_project_path(im.get("path",""), p.name)).is_file():
                        problems.append(f"{p.name}: finding {row.get('finding_id')} image not found: {im.get('path')}")
        for rb in (p/"runbooks").glob("*.md"):
            text=rb.read_text(encoding="utf-8")
            st=re.search(r"(?m)^status:\s*(\S+)\s*$", text)
            if not st or st.group(1) not in ("draft","active","retired"): problems.append(f"{p.name}/{rb.name}: missing/invalid status")
        for jp in sorted((p/"runs").glob("*/run.jsonl")):
            rdir=jp.parent; ev=lines(jp)
            last_seq=0
            for i,e in enumerate(ev):
                if i==0 and e.get("event")!="run_started": problems.append(f"{rdir.name}: first line is not run_started")
                if e.get("event")=="action":
                    sq=e.get("seq",0)
                    if sq<=last_seq: problems.append(f"{rdir.name}: seq not increasing at line {i+1}")
                    last_seq=sq
                    for art in e.get("artifacts",[]):
                        if not (rdir/art).is_file(): problems.append(f"{rdir.name}: missing artifact {art}")
                if e.get("event")=="run_completed" and i!=len(ev)-1: problems.append(f"{rdir.name}: run_completed is not last")
            if ev and ev[-1].get("event")=="run_completed" and not (rdir/"flow.md").is_file():
                problems.append(f"{rdir.name}: completed run has no flow.md (run-report)")
            checked.append(str(jp))
    print(json.dumps({"valid":not problems,"problems":problems},ensure_ascii=False))
    if problems: sys.exit(1)

def parser():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True)
    x=s.add_parser("project-create"); x.add_argument("--name",required=True)
    x.add_argument("--context-path",action="append",default=[], metavar="RELATIVE_DIRECTORY",
                   help="approved existing directory relative to the project directory (repeatable)")
    x.set_defaults(fn=cmd_project_create)
    x=s.add_parser("project-list"); x.set_defaults(fn=cmd_project_list)
    x=s.add_parser("run-start"); x.add_argument("--project",required=True); x.add_argument("--run-id",required=True)
    x.add_argument("--target",required=True); x.add_argument("--purpose",required=True)
    x.add_argument("--boundary",default="User-facing interface only; no source access; no irreversible actions")
    x.add_argument("--environment",default="Linux desktop on disposable Xvfb display :1042")
    x.add_argument("--mode",default="explore",choices=MODES); x.add_argument("--runbook-id"); x.set_defaults(fn=cmd_start)
    x=s.add_parser("action"); x.add_argument("--project",required=True); x.add_argument("--run-id",required=True)
    x.add_argument("--action",required=True); x.add_argument("--result",required=True,choices=RESULTS)
    x.add_argument("--target"); x.add_argument("--test"); x.add_argument("--expected"); x.add_argument("--observed")
    x.add_argument("--artifacts"); x.add_argument("--notes"); x.set_defaults(fn=cmd_action)
    x=s.add_parser("run-complete"); x.add_argument("--project",required=True); x.add_argument("--run-id",required=True)
    x.add_argument("--status",required=True,choices=RUN_STATUSES); x.add_argument("--summary",required=True); x.set_defaults(fn=cmd_complete)
    x=s.add_parser("run-report"); x.add_argument("--project",required=True); x.add_argument("--run-id",required=True); x.set_defaults(fn=cmd_report)
    x=s.add_parser("finding"); x.add_argument("--project",required=True); x.add_argument("--run-id",required=True)
    x.add_argument("--title",required=True); x.add_argument("--finding-id"); x.add_argument("--fingerprint")
    x.add_argument("--description",default=""); x.add_argument("--severity",default="medium",choices=["low","medium","high"])
    x.add_argument("--confidence",default="medium",choices=["low","medium","high"]); x.add_argument("--status",default="new",choices=FINDING_STATUSES)
    x.add_argument("--steps"); x.add_argument("--expected",default=""); x.add_argument("--observed",default="")
    x.add_argument("--images"); x.add_argument("--references"); x.add_argument("--proposed-for-kb",default=""); x.set_defaults(fn=cmd_finding)
    x=s.add_parser("finding-status"); x.add_argument("--project",required=True); x.add_argument("--finding-id",required=True)
    x.add_argument("--status",required=True,choices=FINDING_STATUSES); x.add_argument("--category",choices=FINDING_CATEGORIES,help="human classification: bug or issue"); x.add_argument("--reason",default=""); x.set_defaults(fn=cmd_finding_status)
    x=s.add_parser("findings-report"); x.add_argument("--project",required=True); x.set_defaults(fn=cmd_findings_report)
    x=s.add_parser("kb-add"); x.add_argument("--project"); x.add_argument("--global",dest="global_",action="store_true")
    x.add_argument("--topic",default="app-rules"); x.add_argument("--title",required=True); x.add_argument("--content",required=True)
    x.add_argument("--source",required=True); x.add_argument("--reviewed-by",default="human"); x.set_defaults(fn=cmd_kb_add)
    x=s.add_parser("kb-propose"); x.add_argument("--project",required=True); x.add_argument("--finding-id",required=True)
    x.add_argument("--note",default=""); x.set_defaults(fn=cmd_kb_propose)
    x=s.add_parser("kb-accept"); x.add_argument("--project",required=True); x.add_argument("--finding-id",required=True)
    x.add_argument("--topic",required=True); x.add_argument("--confirmed-by",required=True); x.set_defaults(fn=cmd_kb_accept)
    x=s.add_parser("kb-reject"); x.add_argument("--project",required=True); x.add_argument("--finding-id",required=True); x.set_defaults(fn=cmd_kb_reject)
    x=s.add_parser("runbook-create"); x.add_argument("--project",required=True); x.add_argument("--runbook-id",required=True)
    x.add_argument("--title",default="Runbook"); x.add_argument("--file"); x.add_argument("--active",action="store_true")
    x.add_argument("--human",action="store_true"); x.set_defaults(fn=cmd_runbook_create)
    x=s.add_parser("runbook-freeze"); x.add_argument("--project",required=True); x.add_argument("--run-id",required=True)
    x.add_argument("--runbook-id",required=True); x.add_argument("--seqs"); x.set_defaults(fn=cmd_runbook_freeze)
    x=s.add_parser("runbook-validate"); x.add_argument("--project",required=True); x.add_argument("--runbook-id"); x.set_defaults(fn=cmd_runbook_validate)
    x=s.add_parser("history"); x.add_argument("query"); x.set_defaults(fn=cmd_history)
    x=s.add_parser("validate"); x.set_defaults(fn=cmd_validate)
    return p

if __name__=="__main__":
    a=parser().parse_args(); a.fn(a)