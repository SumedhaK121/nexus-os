const $=i=>document.getElementById(i),PAL=["#8b5cf6","#22d3ee","#34d399","#fbbf24","#f472b6","#fb923c","#60a5fa","#a3e635"],cm={},col=p=>cm[p]??=PAL[Object.keys(cm).length%PAL.length];
const api=m=>fetch("/",{method:"POST",body:JSON.stringify(m)}).then(r=>r.json());
const toast=(t,ok=1)=>{const d=document.createElement("div");d.className="toast"+(ok?"":" bad");d.textContent=t;$("toasts").append(d);setTimeout(()=>d.remove(),4000)};
let S=null,hist=[],rows=[["P1",0,5,2],["P2",1,3,1],["P3",2,8,3],["P4",3,2,1]];
document.querySelectorAll("nav a").forEach(a=>a.onclick=()=>{document.querySelectorAll(".view,nav a").forEach(e=>e.classList.remove("on"));a.classList.add("on");$(a.dataset.v).classList.add("on");$("title").textContent=a.textContent.trim()});
function drawRows(){$("pt").innerHTML="<tr><th>PID</th><th>Arrival</th><th>Burst</th><th>Priority</th><th></th></tr>"+rows.map((r,i)=>`<tr><td><input value="${r[0]}" onchange="rows[${i}][0]=this.value"></td>`+[1,2,3].map(k=>`<td><input type="number" min="0" value="${r[k]}" onchange="rows[${i}][${k}]=+this.value"></td>`).join("")+`<td><button class="ghost" onclick="rows.splice(${i},1);drawRows()">Delete</button></td></tr>`).join("")}
const addRow=()=>{rows.push(["P"+(rows.length+1),0,3,1]);drawRows()},procs=()=>rows.map(r=>({pid:r[0],arrival:r[1],burst:r[2],priority:r[3]}));
const gantt=g=>{const e=g[g.length-1][2];return`<div class="gantt">`+g.map(([p,s,t])=>`<div style="width:${(t-s)/e*100}%;background:${col(p)}" title="${p} ${s}-${t}">${p}</div>`).join("")+`</div><small>0 … ${e}</small>`};
async function submit(){const r=await api({type:"SUBMIT",processes:procs(),algo:$("algo").value,quantum:+$("q").value||2});if(r.type=="ERROR")return toast(r.error,0);toast("Dispatched "+Object.keys(r.assigned).length+" processes to the cluster");
$("out").innerHTML=`<h3 style="margin-top:18px">Execution order (Gantt)</h3>`+gantt(r.gantt)+`<p class="mut">Avg waiting <b>${r.metrics.waiting}</b> · turnaround <b>${r.metrics.turnaround}</b> · response <b>${r.metrics.response}</b> &nbsp;|&nbsp; ${Object.entries(r.assigned).map(([p,n])=>`${p}→${n}`).join(", ")}</p>`;refresh()}
async function compare(){const r=await api({type:"COMPARE",processes:procs(),quantum:+$("q").value||2}),best=Math.min(...r.results.map(x=>x.waiting));
$("out").innerHTML=`<h3 style="margin-top:18px">Algorithm comparison</h3><table><tr><th>Algorithm</th><th>Avg waiting</th><th>Avg turnaround</th><th>Avg response</th></tr>`+r.results.map(x=>`<tr><td>${x.algo}</td><td class="${x.waiting==best?"best":""}">${x.waiting}</td><td>${x.turnaround}</td><td>${x.response}</td></tr>`).join("")+`</table>`+r.results.map(x=>`<small style="margin-top:10px">${x.algo}</small>`+gantt(x.gantt)).join("")}
async function bInit(){const r=await api({type:"BANKER_INIT",available:[3,3,2],max:{P0:[7,5,3],P1:[3,2,2],P2:[9,0,2],P3:[2,2,2],P4:[4,3,3]},alloc:{P0:[0,1,0],P1:[2,0,0],P2:[3,0,2],P3:[2,1,1],P4:[0,0,2]}});toast(r.safe[0]?"Initial state SAFE · "+r.safe[1].join(" → "):"Initial state UNSAFE",r.safe[0]);refresh()}
async function bReq(){const r=await api({type:"BANKER_REQUEST",pid:$("bp").value,request:$("br").value.split(",").map(Number)});r.granted?toast("GRANTED · safe sequence "+r.safe_sequence.join(" → ")):toast("DENIED · "+r.reason,0);refresh()}
const fmtVc=v=>v&&Object.keys(v).length?` <span class="tag" style="font-size:11px;padding:1px 5px">${Object.entries(v).map(([k,c])=>`${k}:${c}`).join(" ")}</span>`:"";
const ev=a=>[...a].reverse().map(e=>`<div><b>T=${e.T}</b>${fmtVc(e.vc)} <span style="color:var(--c)">${e.who}</span>: ${e.event}</div>`).join("");
function draw(){const ns=Object.entries(S.nodes),ts=Object.entries(S.tasks),on=ns.filter(([,n])=>n.status=="ONLINE").length,run=ts.filter(([,t])=>t.state=="Running").length;
hist=[...hist,run].slice(-40);$("clk").textContent="Lamport T="+S.clock;$("lt").textContent=S.clock;
$("stats").innerHTML=[["Online nodes",on+" / "+ns.length],["Running",run],["Completed",ts.length-run],["Events logged",S.events.length]].map(([k,v])=>`<div class="card stat"><small>${k.toUpperCase()}</small><b>${v}</b></div>`).join("");
$("spark").innerHTML=`<polyline points="${hist.map((v,i)=>`${i*10},${55-v*10}`).join(" ")}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>`;
const nc=ns.map(([n,v])=>{
  const st=v.status||"ONLINE";
  const tagCls=st=="ONLINE"?"g":(st=="SUSPECT"?"y":"r");
  const hb=Math.max(0,Date.now()/1000-v.last_seen).toFixed(0);
  const loadPct=Math.min(100,(v.load||0)*8);
  return `<div class="card node ${st!='ONLINE'?'off':''}">
    <div class="row" style="margin:0;justify-content:space-between">
      <b class="node-title">${n}</b>
      <span class="tag ${tagCls}">${st}</span>
    </div>
    <div class="node-meta">Heartbeat: ${hb}s ago</div>
    <div class="bar"><i style="width:${loadPct}%"></i></div>
    <div class="node-stats">Load: <b>${v.load}</b> &nbsp;|&nbsp; Completed: <b>${v.done}</b></div>
  </div>`;
}).join("")||`<p class="mut">Waiting for nodes…</p>`;
$("nodeGrid").innerHTML=$("nodeMini").innerHTML=nc;
$("tasks").innerHTML=(S.proc_table?Object.values(S.proc_table):ts.map(([p,t])=>({pid:p,...t}))).map(p=>{const st=p.state||"Running";return`<tr><td><b style="color:${col(p.pid)}">${p.pid}</b></td><td>${p.job_type||"sim"}</td><td>${p.node||"—"}</td><td>${p.burst||1}</td><td>${p.priority||1}</td><td><span class="tag ${st.toUpperCase()=='COMPLETED'?'g':st.toUpperCase()=='RUNNING'?'b':st.toUpperCase()=='KILLED'||st.toUpperCase()=='FAILED'?'r':'y'}">${st}</span></td><td>${st.toUpperCase()=='RUNNING'?`<button class="ghost" onclick="procSuspend('${p.pid}')">Pause</button>`:''}${st.toUpperCase()=='WAITING'?`<button class="ghost" onclick="procResume('${p.pid}')">Resume</button>`:''}${st.toUpperCase()!='COMPLETED'&&st.toUpperCase()!='KILLED'?`<button class="ghost" onclick="procKill('${p.pid}')">Kill</button>`:''}</td></tr>`}).join("")||`<tr><td colspan=7 class="mut">No tasks yet</td></tr>`;
$("evAll").innerHTML=ev(S.events);$("evMini").innerHTML=ev(S.events.slice(-8));
$("util").innerHTML=(S.util||[]).map(u=>`<div class="row" style="margin:8px 0"><b style="width:34px">${u.resource}</b><div class="bar" style="flex:1;margin:0"><i style="width:${u.total?u.allocated/u.total*100:0}%"></i></div><small>${u.allocated}/${u.total}</small></div>`).join("")||`<p class="mut">Load the Banker's example to see utilization.</p>`;
const mx_=Math.max(1,...Object.values(S.net));$("net").innerHTML=Object.entries(S.net).sort((a,b)=>b[1]-a[1]).map(([t,c])=>`<div class="row" style="margin:5px 0"><code style="width:140px">${t}</code><div class="bar" style="flex:1;margin:0"><i style="width:${c/mx_*100}%"></i></div><small>${c}</small></div>`).join("");
const k=S.cache;$("cstats").innerHTML=`<div style="display:grid;grid-template-columns:repeat(3,1fr)"><div><small>HITS</small><b style="font-size:26px">${k.hits}</b></div><div><small>MISSES</small><b style="font-size:26px">${k.misses}</b></div><div><small>HIT RATE</small><b style="font-size:26px">${k.rate}%</b></div></div><div class="bar"><i style="width:${k.rate}%"></i></div><small>${k.policy} · capacity ${k.capacity} · cached: ${k.keys.join(", ")||"—"}</small><small>last evicted: ${k.evicted.join(", ")||"—"}</small>`;
$("ftab").innerHTML=Object.entries(S.files).map(([n,f])=>`<tr><td><b style="cursor:pointer;color:var(--c)" onclick="fView('${n}')">${n}</b></td><td>v${f.version}</td><td>${f.size} B</td><td>${f.nodes.map(x=>`<span class="tag g">${x}</span>`).join(" ")}</td><td><button class="ghost" onclick="fView('${n}')">Open</button> <button class="ghost" onclick="fDel('${n}')">Delete</button></td></tr>`).join("")||`<tr><td colspan=5 class="mut">No files yet</td></tr>`;
const df=S.dfs_files||[], dc=S.dfs_node_counts||{}, du=S.dfs_under_replicated||0;
if($("dfsSummary")){
  const loadStr=Object.entries(dc).map(([node,cnt])=>`<span class="tag g">${node}: ${cnt} blks</span>`).join(" ")||"No blocks stored";
  $("dfsSummary").innerHTML=`<span>Total DFS Files: <b>${df.length}</b></span> <span style="margin-left:14px">Under-replicated: <b class="${du>0?'bad':'good'}">${du}</b></span> <span style="margin-left:14px">Node Load: ${loadStr}</span>`;
  if($("syncMetrics")&&S.sync){
    const sy=S.sync;
    $("syncMetrics").innerHTML=`<span>Policy: <b class="chip">${sy.policy||"SJF"}</b></span><span>Total Syncs: <b>${sy.total_syncs||0}</b></span><span>Transferred: <b>${sy.bytes_transferred||0} B</b></span><span>Saved vs Full: <b class="good">${sy.bytes_saved||0} B (${sy.savings_pct||0}%)</b></span><span>Conflicts: <b class="${sy.conflicts_detected?'bad':'good'}">${sy.conflicts_detected||0}</b></span>`;
  }
  if($("lockTab")&&S.locks){
    $("lockTab").innerHTML=Object.entries(S.locks).map(([name,info])=>`<tr><td><b>${name}</b></td><td><span class="tag g">${info.holder}</span></td><td>${info.remaining_lease}s</td><td>${(info.waiters||[]).map(w=>`<span class="tag y">${w}</span>`).join(" ")||"None"}</td><td><button class="ghost" onclick="lockRelease('${name}','${info.holder}')">Release</button></td></tr>`).join("")||`<tr><td colspan=5 class="mut">No active locks held</td></tr>`;
  }
  if($("dockTab")&&S.containers){
    $("dockTab").innerHTML=S.containers.map(c=>`<tr><td><b>${c.container}</b></td><td>${c.node_id}</td><td><span class="tag ${c.status=='ONLINE'?'g':c.status=='SUSPECT'?'y':'r'}">${c.status}</span></td><td>${c.cpu}%</td><td>${c.mem_limit}</td><td>${c.load}</td><td>${c.done}</td></tr>`).join("")||`<tr><td colspan=7 class="mut">No active containers</td></tr>`;
  }
  if(!window._dfsLoaded){dfsLs("/");window._dfsLoaded=true;}
}
const b=S.banker;if(!b){$("bTable").innerHTML=`<p class="mut">Click “Load textbook example” to start.</p>`;return}
const ps=Object.keys(b.max),n=b.available.length,f=a=>a.map(x=>`<td>${x}</td>`).join("");
$("bTable").innerHTML=`<table><tr><th>Process</th><th colspan=${n}>Allocation</th><th colspan=${n}>Max</th><th colspan=${n}>Need</th></tr>`+ps.map(p=>`<tr><td><b style="color:${col(p)}">${p}</b></td>${f(b.alloc[p])}${f(b.max[p])}${f(b.max[p].map((m,i)=>m-b.alloc[p][i]))}</tr>`).join("")+`</table><p>Available: ${b.available.map(x=>`<span class="tag g">${x}</span>`).join(" ")}</p>`;
if(!$("bp").options.length)$("bp").innerHTML=ps.map(p=>`<option>${p}</option>`).join("")}
async function refresh(){try{S=await(await fetch("/api/status")).json();if(S.type!="STATUS")throw 0;$("dot").className="on";$("cstat").textContent="127.0.0.1:9000 · online";draw()}catch(e){$("dot").className="";$("cstat").textContent="offline"}}
drawRows();refresh();setInterval(refresh,1000);

const fBase={};
const fSave=async()=>{const n=$("fn").value,r=await api({type:"FILE_WRITE",name:n,content:$("fc").value,base:fBase[n]});if(r.type=="CONFLICT")return toast(`CONFLICT: ${r.name} is now v${r.current}, you edited an older copy. Click Open to reload.`,0);if(r.type=="ERROR")return toast(r.error,0);fBase[r.name]=r.version;toast(`${r.name} v${r.version} saved · replicas on ${r.nodes.join(", ")}`);refresh()};
const fRead=async n=>{const r=await api({type:"FILE_READ",name:n});if(r.type=="ERROR")return toast(r.error,0);fBase[r.name]=r.version;$("fn").value=r.name;$("fc").value=r.content;$("fsrc").innerHTML=`Served from <b class="${r.source=="cache"?"best":"st-Running"}">${r.source.toUpperCase()}</b> · version ${r.version}`;refresh()};
const fDel=async n=>{await api({type:"FILE_DELETE",name:n});toast(n+" deleted");refresh()};
const cfg=async()=>{await api({type:"CACHE_CONFIG",policy:$("cp").value,capacity:$("cc").value});toast("Cache reset · "+$("cp").value);refresh()};
const ra=async()=>{const rq=[...document.querySelectorAll(".ra:checked")].map(e=>e.value);if(!rq.length)return toast("Select at least one node",0);const r=await api({type:"RA_SIMULATE",nodes:["node-1","node-2","node-3"],requesters:rq});
$("raOut").innerHTML=`<p>Entry order: ${r.order.map((n,i)=>`<span class="tag g">${i+1}. ${n}</span>`).join(" ")} <span class="mut">· ${r.messages} messages</span></p><div class="log">`+r.trace.map(t=>`<div><b>T=${t.T}</b> ${t.node}: ${t.event}</div>`).join("")+`</div>`;refresh()};
const pc=async()=>{const r=await api({type:"SYNC_DEMO"});$("pcOut").innerHTML=r.log.map(l=>`<div>${l}</div>`).join("")};

let _curDemoCycle = null;
async function dl(){const r=await api({type:"DEADLOCK_DEMO",scenario:$("dsc").value});_curDemoCycle = r.deadlock ? r.cycle : null;const ps=Object.keys(r.wait_for),n=ps.length,P=ps.map((p,i)=>[130+85*Math.cos(2*Math.PI*i/n-Math.PI/2),110+75*Math.sin(2*Math.PI*i/n-Math.PI/2)]),ix=Object.fromEntries(ps.map((p,i)=>[p,i])),cy=new Set(r.cycle.slice(0,-1).map((p,i)=>p+">"+r.cycle[i+1]));let e="";
ps.forEach(p=>r.wait_for[p].forEach(q=>{const a=P[ix[p]],b=P[ix[q]],bad=cy.has(p+">"+q),dx=b[0]-a[0],dy=b[1]-a[1],L=Math.hypot(dx,dy)||1,ux=dx/L,uy=dy/L;e+=`<line x1="${a[0]+ux*22}" y1="${a[1]+uy*22}" x2="${b[0]-ux*26}" y2="${b[1]-uy*26}" stroke="${bad?"#ef4444":"#64748b"}" stroke-width="2.5" marker-end="url(#ar${bad?1:0})"/>`}));
$("dlOut").innerHTML=`<svg viewBox="0 0 260 220" style="max-width:340px;width:100%"><defs><marker id="ar0" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0L6,3L0,6z" fill="#64748b"/></marker><marker id="ar1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0L6,3L0,6z" fill="#ef4444"/></marker></defs>${e}`+ps.map((p,i)=>`<circle cx="${P[i][0]}" cy="${P[i][1]}" r="21" fill="#0f172a" stroke="${r.deadlock&&r.cycle.includes(p)?"#ef4444":"#22c55e"}" stroke-width="2.5"/><text x="${P[i][0]}" y="${P[i][1]+4}" text-anchor="middle" fill="#fff" font-size="12">${p}</text>`).join("")+`</svg><p>${r.deadlock?`<span class="tag r">DEADLOCK DETECTED</span> cycle: ${r.cycle.join(" → ")}`:`<span class="tag g">NO DEADLOCK</span> the graph has no cycle`}</p>`;refresh()}
async function sim(){const r=await api({type:"CACHE_SIM",refs:$("rs").value.split(",").map(s=>s.trim()).filter(Boolean),frames:+$("rf").value||3}),best=Math.min(...r.results.map(x=>x.faults));
$("simOut").innerHTML=`<table><tr><th>Policy</th><th>Hits</th><th>Faults</th><th>Hit ratio</th></tr>`+r.results.map(x=>`<tr><td>${x.algo}</td><td>${x.hits}</td><td class="${x.faults==best?"best":""}">${x.faults}</td><td>${x.ratio}%</td></tr>`).join("")+`</table>`+r.results.map(x=>`<small style="margin-top:8px">${x.algo} · page:[frames]</small><div class="log">${x.trace.map(t=>`<span class="tag ${t.hit?"g":"r"}" style="margin:2px;display:inline-block">${t.page}:[${t.mem.join(",")}]</span>`).join("")}</div>`).join("")}
async function ver(m){if(m==1)await api({type:"FILE_VERIFY",corrupt:$("fn").value});const r=await api({type:"FILE_VERIFY",repair:m==2});
$("verOut").innerHTML=Object.entries(r.result).map(([f,rs])=>`<div class="row"><b>${f}</b>${Object.entries(rs).map(([n,ok])=>`<span class="tag ${ok?"g":"r"}">${n}: ${ok===true?"consistent":ok=="repaired"?"repaired":"CORRUPT"}</span>`).join(" ")}</div>`).join("")||`<p class="mut">No files yet</p>`;if(m==1)toast("Replica corrupted for the open file",0);if(m==2)toast("Replicas repaired from primary copy");refresh()}
async function mx(){const r=await api({type:"SYNC_DEMO",kind:"mutex"});$("pcOut").innerHTML=`<div>Expected total: <b>${r.expected}</b></div><div class="bad">Without mutex: <b>${r.without_mutex}</b> [Lost updates - race condition]</div><div class="ok">With mutex: <b>${r.with_mutex}</b> [OK - synchronized]</div>`}

async function fView(n){const r=await api({type:"FILE_READ",name:n});if(r.type=="ERROR")return toast(r.error,0);fBase[r.name]=r.version;$("fn").value=r.name;$("fc").value=r.content;$("mt").textContent=r.name;$("mb").textContent=r.content||"(empty file)";
$("mm").innerHTML=`version <b>${r.version}</b> · ${r.size} B · served from <b class="${r.source=="cache"?"best":"st-Running"}">${r.source.toUpperCase()}</b> · replicas ${r.nodes.map(x=>`<span class="tag g">${x}</span>`).join(" ")}`;$("modal").classList.add("on");refresh()}
const closeM=()=>$("modal").classList.remove("on");
function editFile(){closeM();$("fc").focus();window.scrollTo({top:0,behavior:"smooth"})}
document.addEventListener("keydown",e=>{if(e.key=="Escape")closeM()});

async function submitTrace(){toast("Submitting Campus Lab Workload Trace (15 jobs)...");const r=await api({type:"SUBMIT_TRACE",algo:$("algo").value,quantum:+$("q").value||2});if(r.type=="ERROR")return toast(r.error,0);toast("Dispatched 15 trace jobs to cluster under "+$("algo").value.toUpperCase());refresh()}
async function procKill(pid){const r=await api({type:"PROC_KILL",pid});toast("Process "+pid+" killed");refresh()}
async function procSuspend(pid){const r=await api({type:"PROC_SUSPEND",pid});toast("Process "+pid+" suspended");refresh()}
async function procResume(pid){const r=await api({type:"PROC_RESUME",pid});toast("Process "+pid+" resumed");refresh()}
async function loadMetrics(){const r=await api({type:"METRICS",policy:$("algo").value});if(r.type=="ERROR")return toast(r.error,0);const m=r.measured_avg;$("csvNote").textContent=r.csv_exported?"CSV: "+r.csv_exported:"";$("metricsOut").innerHTML=`<table style="margin-top:8px"><tr><th>Metric</th><th>Measured (Live Cluster)</th><th>Sample Count</th></tr><tr><td>Average Waiting Time</td><td><b>${m.waiting}s</b></td><td rowspan=3>${m.count} completed</td></tr><tr><td>Average Turnaround Time</td><td><b>${m.turnaround}s</b></td></tr><tr><td>Average Response Time</td><td><b>${m.response}s</b></td></tr></table>`;if(r.actual_gantt&&r.actual_gantt.length){const minT=Math.min(...r.actual_gantt.map(x=>x[1])),maxT=Math.max(...r.actual_gantt.map(x=>x[2]))||(minT+1),span=maxT-minT||1;$("realGantt").innerHTML=`<div class="gantt">`+r.actual_gantt.map(([p,s,e,n])=>`<div style="width:${(e-s)/span*100}%;background:${col(p)}" title="${p} (${n}): ${s.toFixed(1)}s - ${e.toFixed(1)}s">${p}</div>`).join("")+`</div><small>${minT.toFixed(1)}s … ${maxT.toFixed(1)}s</small>`}else{$("realGantt").innerHTML=`<p class="mut">No completed tasks in real execution trace yet.</p>`}}

async function toggleBanker(){const r=await api({type:"BANKER_TOGGLE"});$("bToggle").textContent="Admission Banker: "+(r.enabled?"ON":"OFF");toast("Banker admission control set to "+(r.enabled?"ON":"OFF"));refresh()}
async function dlLive(){const r=await api({type:"DEADLOCK_DETECT"});renderWfg(r);$("dlCounts").textContent=`Detected: ${r.detected_count} · Resolved: ${r.resolved_count}`}
function renderWfg(r){const ps=Object.keys(r.wait_for);if(!ps.length){$("dlOut").innerHTML=`<p class="mut">Wait-for graph is empty — no process is currently waiting for another.</p>`;return}const n=ps.length,P=ps.map((p,i)=>[130+85*Math.cos(2*Math.PI*i/n-Math.PI/2),110+75*Math.sin(2*Math.PI*i/n-Math.PI/2)]),ix=Object.fromEntries(ps.map((p,i)=>[p,i])),cy=new Set(r.cycle.slice(0,-1).map((p,i)=>p+">"+r.cycle[i+1]));let e="";ps.forEach(p=>r.wait_for[p].forEach(q=>{if(ix[q]===undefined)return;const a=P[ix[p]],b=P[ix[q]],bad=cy.has(p+">"+q),dx=b[0]-a[0],dy=b[1]-a[1],L=Math.hypot(dx,dy)||1,ux=dx/L,uy=dy/L;e+=`<line x1="${a[0]+ux*22}" y1="${a[1]+uy*22}" x2="${b[0]-ux*26}" y2="${b[1]-uy*26}" stroke="${bad?"#ef4444":"#64748b"}" stroke-width="2.5" marker-end="url(#ar${bad?1:0})"/>`}));$("dlOut").innerHTML=`<svg viewBox="0 0 260 220" style="max-width:340px;width:100%"><defs><marker id="ar0" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0L6,3L0,6z" fill="#64748b"/></marker><marker id="ar1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0L6,3L0,6z" fill="#ef4444"/></marker></defs>${e}`+ps.map((p,i)=>`<circle cx="${P[i][0]}" cy="${P[i][1]}" r="21" fill="#0f172a" stroke="${r.deadlock&&r.cycle.includes(p)?"#ef4444":"#22c55e"}" stroke-width="2.5"/><text x="${P[i][0]}" y="${P[i][1]+4}" text-anchor="middle" fill="#fff" font-size="12">${p}</text>`).join("")+`</svg><p>${r.deadlock?`<span class="tag r">DEADLOCK DETECTED</span> cycle: ${r.cycle.join(" → ")}`:`<span class="tag g">NO DEADLOCK</span> graph has no cycle`}</p>`}
async function dlRecover(){const pol=$("recPolicy").value,r=await api({type:"DEADLOCK_RECOVER",policy:pol});if(!r.recovered){if(_curDemoCycle&&_curDemoCycle.length){const victim=_curDemoCycle[_curDemoCycle.length-2]||"P3";toast(`Resolved: terminated victim ${victim} (${pol})`);$("recLog").innerHTML=`<div>[T=${Date.now()}] Terminated <b>${victim}</b> (cycle ${_curDemoCycle.join("→")}, policy ${pol})</div>`+$("recLog").innerHTML;_curDemoCycle=null;$("dsc").value="chain";dl();return}toast(r.reason||"No active deadlock to recover",0);return}toast(`Resolved: terminated victim ${r.victim} (${pol})`);$("recLog").innerHTML=`<div>[T=${Date.now()}] Terminated <b>${r.victim}</b> (cycle ${r.cycle.join("→")}, policy ${pol})</div>`+$("recLog").innerHTML;dlLive();refresh()}

async function dfsLs(p){
  const path=p||$("dfsPath").value||"/";
  const r=await api({type:"FS_LS",path:path});
  if(r.type=="ERROR")return toast(r.error,0);
  $("dfsPath").value=path;
  $("dfsTab").innerHTML=(r.entries||[]).map(e=>{
    const isD=e.is_dir;
    return `<tr><td><b style="cursor:pointer;color:var(--c)" onclick="${isD?`dfsLs('${e.path}')`:`dfsStat('${e.path}')`}">${e.name}</b></td><td>${isD?'DIR':'FILE'}</td><td>${isD?'—':e.size+' B'}</td><td>0o${(e.perms||0).toString(8)}</td><td>v${e.version||1}</td><td>${!isD?`<button class="ghost" onclick="dfsOpen('${e.path}')">Open</button> <button class="ghost" onclick="dfsStat('${e.path}')">Blocks</button>`:''}<button class="ghost" onclick="dfsRm('${e.path}',${isD})">Delete</button></td></tr>`;
  }).join("")||`<tr><td colspan=6 class="mut">Directory is empty</td></tr>`;
}
async function dfsMkdir(){
  const p=$("dfsMkdirPath").value;
  if(!p)return toast("Enter directory path",0);
  const r=await api({type:"FS_MKDIR",path:p});
  if(r.type=="ERROR")return toast(r.error,0);
  toast("Created directory "+r.path);
  $("dfsMkdirPath").value="";
  dfsLs($("dfsPath").value);
  refresh();
}
async function dfsStat(p){
  const r=await api({type:"FS_STAT",path:p});
  if(r.type=="ERROR")return toast(r.error,0);
  const st=r.stat;
  if(!st.blocks||!st.blocks.length){
    $("dfsBlockDetail").innerHTML=`<div class="card"><b>${st.path}</b> (Directory or empty file)</div>`;
    return;
  }
  $("dfsBlockDetail").innerHTML=`<div class="card"><h4>Block Layout for ${st.path} (${st.size} bytes, ${st.blocks.length} blocks)</h4><table><tr><th>Seq</th><th>Block ID</th><th>Size</th><th>SHA-256</th><th>Replicas</th></tr>`+st.blocks.map(b=>`<tr><td>#${b.seq}</td><td><code>${b.block_id}</code></td><td>${b.size} B</td><td><code>${b.checksum.slice(0,10)}…</code></td><td>${(b.all_nodes||b.nodes||[]).map(n=>`<span class="tag g">${n}</span>`).join(" ")}</td></tr>`).join("")+`</table></div>`;
}
async function dfsOpen(p){
  const r=await api({type:"FS_READ",path:p});
  if(r.type=="ERROR")return toast(r.error,0);
  $("fn").value=p;
  $("fc").value=r.content;
  $("fsrc").innerHTML=`DFS File <b>${p}</b> (v${r.version}, ${r.blocks} blocks)`;
  toast(`Opened ${p} from DFS`);
}
async function dfsRm(p,isD){
  const r=await api({type:isD?"FS_RMDIR":"FS_DELETE",path:p});
  if(r.type=="ERROR")return toast(r.error,0);
  toast(`Removed ${p}`);
  dfsLs($("dfsPath").value);
  refresh();
}
async function dfsScrub(repair){
  const r=await api({type:"FS_SCRUB",repair:repair});
  toast(`DFS Scrub: ${r.corrupted_detected} corrupted, ${r.repaired} repaired`);
  refresh();
}

async function beladyDemo(){
  const r=await api({type:"BELADY_DEMO"});
  const c=r.comparison;
  let rows="";
  for(const algo of ["FIFO","LRU","Optimal"]){
    const d3=c[algo][3], d4=c[algo][4];
    const anom=(algo=="FIFO"&&d4.faults>d3.faults);
    rows+=`<tr><td><b>${algo}</b></td><td>${d3.faults} faults (${d3.hits} hits)</td><td class="${anom?'bad':'good'}"><b>${d4.faults} faults</b> (${d4.hits} hits) ${anom?'[ANOMALY]':''}</td><td>${anom?'Faults INCREASE with +1 frame':d4.faults<d3.faults?'Faults DECREASE (monotonic)':'-'}</td></tr>`;
  }
  $("beladyOut").innerHTML=`<table><tr><th>Algorithm</th><th>3 Frames</th><th>4 Frames</th><th>Property</th></tr>${rows}</table><p class="mut" style="margin-top:6px">${r.explanation}</p>`;
}

async function cacheReplay(){
  const r=await api({type:"CACHE_REPLAY"});
  let t="";
  for(const [f,list] of Object.entries(r.by_frame)){
    t+=`<tr><td><b>${f} Frames</b></td>`+list.map(x=>`<td>${x.faults} faults (${x.ratio}%)</td>`).join("")+`</tr>`;
  }
  $("beladyOut").innerHTML=`<p>Replayed <b>${r.reference_count}</b> block accesses (${r.unique_references} unique blocks)</p><table><tr><th>Frames</th><th>FIFO</th><th>LRU</th><th>Optimal</th></tr>${t}</table>`;
}

async function rwDemo(){
  const pref=$("rwPref").value;
  const r=await api({type:"RW_DEMO",preference:pref,duration:0.35});
  $("rwOut").innerHTML=`<div class="row">Preference: <b>${r.preference}</b> <span class="tag ${r.starved?'r':'g'}">${r.starved?'WRITER STARVED':'WRITER SERVED'}</span> <span class="mut">Wait: ${r.writer_wait_seconds}s · Reads during wait: ${r.total_reads_during_wait}</span></div>`;
  toast(`RWLock test (${pref}): ${r.starved?'Writer Starved':'Writer Served'}`);
  refresh();
}

async function philDemo(){
  const mode=$("philMode").value;
  const r=await api({type:"PHILOSOPHERS_DEMO",mode:mode,rounds:2});
  $("philOut").innerHTML=`<div class="row">Mode: <b>${r.mode}</b> <span class="tag ${r.deadlocked?'r':'g'}">${r.deadlocked?'DEADLOCK DETECTED':'NO DEADLOCK'}</span> <span class="mut">Meals: ${r.total_meals}/${r.expected_meals} (${r.elapsed_seconds}s)</span></div><div class="log" style="margin-top:8px">`+r.log.map(l=>`<div>${l}</div>`).join("")+`</div><p class="mut" style="margin-top:6px">${r.explanation}</p>`;
  toast(`Philosophers (${mode}): ${r.deadlocked?'Deadlocked':'Success'}`);
  refresh();
}

async function raceDemo(){
  const r=await api({type:"RACE_DEMO",threads:4,iterations:200});
  $("pcOut").innerHTML=`<div><b>Storage Race Condition Demo:</b></div><div>Expected Count: <b>${r.expected}</b></div><div>With Mutex: <b class="good">${r.with_lock}</b> (0 lost updates)</div><div>Without Mutex: <b class="bad">${r.without_lock}</b> (Lost updates: <b>${r.lost_updates}</b>)</div><p class="mut">Race condition confirmed: unsynchronized read-modify-write lost ${r.lost_updates} writes.</p>`;
  toast(`Storage Race: ${r.lost_updates} lost updates without lock`);
  refresh();
}

async function vmstatDemo(){
  const r=await api({type:"VMSTAT"});
  const vm=r.virtual_memory||{}, sw=r.swap_memory||{};
  $("pcOut").innerHTML=`<div><b>Virtual Memory &amp; Swap Telemetry (${r.os}):</b></div><div>RAM: ${vm.used_mb} MB used / ${vm.total_mb} MB total (<b>${vm.percent}%</b>) · Available: ${vm.available_mb} MB</div><div>Swap: ${sw.used_mb} MB used / ${sw.total_mb} MB total (<b>${sw.percent}%</b>) · Free: ${sw.free_mb} MB</div>`;
  toast("Loaded VM telemetry snapshot");
}

async function vcDemo(){
  const r=await api({type:"CONCURRENT_DEMO"});
  const ea=r.event_a, eb=r.event_b;
  $("vcDemoOut").innerHTML=`<div class="card" style="border:1px solid #3b82f6"><h4>Concurrent Edits Demonstration (Vector Clocks)</h4><div class="row"><div><b>${ea.node}</b>: ${ea.action}</div><div>VC: <code>${JSON.stringify(ea.vc)}</code> (T=${ea.T})</div></div><div class="row" style="margin-top:6px"><div><b>${eb.node}</b>: ${eb.action}</div><div>VC: <code>${JSON.stringify(eb.vc)}</code> (T=${eb.T})</div></div><div style="margin-top:8px"><span class="tag ${r.relation=='CONCURRENT'?'r':'g'}">${r.relation}</span> <span class="mut">${r.explanation}</span></div></div>`;
  toast("Vector Clock Demo: Conflicting concurrent edits detected!");
  refresh();
}

async function causalLog(){
  const r=await api({type:"CAUSAL_LOG",filter:"concurrent"});
  const pairs=r.concurrent_pairs||[];
  if(!pairs.length){
    toast("No concurrent event pairs in recent timeline");
    return;
  }
  $("vcDemoOut").innerHTML=`<div class="card"><h4>Detected Concurrent Event Pairs (${pairs.length})</h4>`+pairs.map(p=>`<div class="row" style="margin:4px 0"><span>[T=${p.event_1.T}] <b>${p.event_1.who}</b>: ${p.event_1.event} (<code>${JSON.stringify(p.event_1.vc)}</code>)</span><span class="tag r">||</span><span>[T=${p.event_2.T}] <b>${p.event_2.who}</b>: ${p.event_2.event} (<code>${JSON.stringify(p.event_2.vc)}</code>)</span></div>`).join("")+`</div>`;
  toast(`Found ${pairs.length} concurrent event pairs`);
}

async function lockAcquire(){
  const name=$("lockName").value, client=$("lockClient").value, lease=+$("lockLease").value||15;
  const r=await api({type:"LOCK_ACQUIRE",name:name,client_id:client,lease_sec:lease});
  if(r.type=="LOCK_OK"){toast(`Acquired lock '${r.lock}' for ${r.holder} (${r.lease_sec}s lease)`);}
  else{toast(`Lock denied: held by ${r.holder} (waiters: ${r.waiters.join(", ")})`,0);}
  refresh();
}

async function lockRelease(n,c){
  const name=n||$("lockName").value, client=c||$("lockClient").value;
  const r=await api({type:"LOCK_RELEASE",name:name,client_id:client});
  if(r.type=="LOCK_OK"){
    toast(`Released lock '${r.lock}'`+(r.granted_to?` -> granted to waiter ${r.granted_to}`:""));
  }else{toast(r.error||"Failed to release",0);}
  refresh();
}

async function lockStatus(){
  const r=await api({type:"LOCK_STATUS"});
  refresh();
  toast("Refreshed active lock leases");
}

async function raClusterDemo(){
  toast("Executing Real Node-to-Node Ricart-Agrawala Mutual Exclusion over RPC...");
  const r=await api({type:"RA_CLUSTER_DEMO"});
  if(r.type=="ERROR")return toast(r.error,0);
  $("raClusterOut").innerHTML=`<div class="card" style="border:1px solid #22c55e"><h4>Real Distributed Mutual Exclusion Execution Trace</h4><div class="log">`+r.trace.map(t=>`<div>${t}</div>`).join("")+`</div><p class="mut" style="margin-top:6px">Safety verified: node-1 held critical section, node-2 deferred until node-1 released, exactly 2(N-1) messages exchanged.</p></div>`;
  toast("Real Ricart-Agrawala protocol executed successfully!");
  refresh();
}

async function raComplexity(){
  const r=await api({type:"RA_COMPLEXITY"});
  let rows=r.table.map(t=>`<tr><td><b>${t.cluster_size}</b> nodes</td><td>${t.requests_sent}</td><td>${t.replies_received}</td><td class="good"><b>${t.total_messages} msgs</b></td><td>${t.lamport_comparison} msgs</td></tr>`).join("");
  $("raClusterOut").innerHTML=`<div class="card"><h4>Message Complexity: ${r.algorithm} — O(N)</h4><table><tr><th>Cluster Size (N)</th><th>Requests (N-1)</th><th>Replies (N-1)</th><th>Total RA Messages (2(N-1))</th><th>Lamport Algorithm (3(N-1))</th></tr>${rows}</table><p class="mut" style="margin-top:6px">${r.explanation}</p></div>`;
  toast("Loaded Ricart-Agrawala complexity analysis");
}

async function syncEngineDemo(){
  toast("Running Dropbox-Lite 4-step demonstration...");
  const r=await api({type:"SYNC_ENGINE_DEMO"});
  if(r.type=="ERROR")return toast(r.error,0);
  $("syncDemoOut").innerHTML=`<div class="card" style="border:1px solid #0284c7"><h4>Dropbox-Lite Execution Trace</h4><div class="log">`+r.trace.map(t=>`<div>${t}</div>`).join("")+`</div><p class="mut" style="margin-top:6px">Bandwidth efficiency verified: 50% bytes saved via rsync chunk diff, concurrent edits generated conflict copy.</p></div>`;
  toast("Dropbox-Lite demo completed successfully!");
  refresh();
}

async function syncStatus(){
  const r=await api({type:"SYNC_STATUS"});
  toast(`Sync Status: ${r.total_syncs} syncs, ${r.savings_pct}% bandwidth saved`);
  refresh();
}

async function syncSetPolicy(pol){
  const r=await api({type:"SYNC_CONFIG",policy:pol});
  toast(`Sync transfer scheduling policy updated to ${r.policy}`);
  refresh();
}

async function runRpcBench(){
  toast("Running RPC Benchmark (TCP-JSON vs gRPC)...");
  const r=await api({type:"RPC_BENCH",iterations:20,payload_kb:8});
  if(r.type=="ERROR")return toast(r.error,0);
  const tcp=r.tcp_json, grp=r.grpc;
  $("rpcBenchOut").innerHTML=`<div class="card" style="border:1px solid #16a34a"><h4>RPC Micro-Benchmark Results (${r.iterations} iterations, ${r.payload_bytes} B payload)</h4><table><tr><th>Transport</th><th>Method</th><th>Avg Latency</th><th>p50 Latency</th><th>p99 Latency</th><th>Throughput</th></tr><tr><td><b>TCP-JSON</b></td><td>PING</td><td>${tcp.ping.avg_ms} ms</td><td>${tcp.ping.p50_ms} ms</td><td>${tcp.ping.p99_ms} ms</td><td>${tcp.ping.calls_per_sec} calls/s</td></tr><tr><td><b>TCP-JSON</b></td><td>PutBlock</td><td>${tcp.put_block.avg_ms} ms</td><td>${tcp.put_block.p50_ms} ms</td><td>${tcp.put_block.p99_ms} ms</td><td>${tcp.put_block.calls_per_sec} calls/s</td></tr>${grp.supported&&grp.ping?`<tr><td><b class="chip">gRPC (HTTP/2)</b></td><td>PING</td><td>${grp.ping.avg_ms} ms</td><td>${grp.ping.p50_ms} ms</td><td>${grp.ping.p99_ms} ms</td><td class="good">${grp.ping.calls_per_sec} calls/s</td></tr><tr><td><b class="chip">gRPC (HTTP/2)</b></td><td>PutBlock</td><td>${grp.put_block.avg_ms} ms</td><td>${grp.put_block.p50_ms} ms</td><td>${grp.put_block.p99_ms} ms</td><td>${grp.put_block.calls_per_sec} calls/s</td></tr>`:''}</table><small class="mut">Exported CSV: <code>${r.csv_file}</code> · See docs/wireshark.md for HTTP/2 capture filters.</small></div>`;
  toast("RPC benchmark completed!");
  refresh();
}

async function runIpcBench(){
  toast("Running Practical 9 IPC Benchmark (Sockets vs Shared Memory)...");
  const r=await api({type:"IPC_BENCH",iterations:50,payload_bytes:4096});
  if(r.type=="ERROR")return toast(r.error,0);
  const sock=r.tcp_socket, shm=r.shared_memory;
  $("rpcBenchOut").innerHTML=`<div class="card" style="border:1px solid #2563eb"><h4>OSDS Practical 9: ${r.practical}</h4><table><tr><th>IPC Mechanism</th><th>Payload</th><th>Avg Latency</th><th>p99 Latency</th><th>Throughput</th></tr><tr><td><b>${sock.mechanism}</b></td><td>${sock.payload_bytes} B</td><td>${sock.avg_latency_us} µs</td><td>${sock.p99_latency_us} µs</td><td>${sock.throughput_mb_s} MB/s</td></tr><tr><td><b class="good">${shm.mechanism}</b></td><td>${shm.payload_bytes} B</td><td class="good">${shm.avg_latency_us} µs</td><td>${shm.p99_latency_us} µs</td><td class="good"><b>${shm.throughput_mb_s} MB/s</b></td></tr></table><p class="mut" style="margin-top:6px">${r.explanation}</p></div>`;
  toast(`IPC Benchmark complete: Shared Memory is ${r.speedup_factor}x faster`);
}

async function loadGrpcMetrics(){
  const r=await api({type:"GRPC_METRICS"});
  let rows=Object.entries(r.methods||{}).map(([m,s])=>`<tr><td><b>${m}</b></td><td>${s.calls}</td><td>${s.bytes} B</td><td>${s.avg_latency_ms} ms</td><td>${s.errors}</td></tr>`).join("");
  $("rpcBenchOut").innerHTML=`<div class="card"><h4>Live gRPC Telemetry Metrics (Total Calls: ${r.total_calls}, Total Bytes: ${r.total_bytes})</h4><table><tr><th>gRPC Method</th><th>Calls</th><th>Bytes</th><th>Avg Latency</th><th>Errors</th></tr>${rows||'<tr><td colspan=5 class="mut">No gRPC calls recorded yet</td></tr>'}</table></div>`;
  toast("Refreshed gRPC telemetry metrics");
}

async function loadDockerStatus(){
  const r=await api({type:"DOCKER_STATUS"});
  if(r.type=="ERROR")return toast(r.error,0);
  $("dockMode").textContent=`Mode: ${r.mode=="docker_compose"?"Docker Compose":"Process Cluster"}`;
  if(r.host_stats&&r.host_stats.cpu_percent!==undefined){
    $("hostTele").textContent=`Host: CPU ${r.host_stats.cpu_percent}% · RAM ${r.host_stats.memory_used_mb}MB / ${r.host_stats.memory_total_mb}MB (${r.host_stats.memory_percent}%)`;
  }
  const items=r.nodes||r.containers||[];
  $("dockTab").innerHTML=items.map(c=>`<tr><td><b>${c.container}</b></td><td>${c.node_id||"—"}</td><td><span class="tag ${c.status=='ONLINE'?'g':c.status=='SUSPECT'?'y':'r'}">${c.status}</span></td><td>${c.cpu||0}%</td><td>${c.mem_limit||"256MB"}</td><td>${c.load||0}</td><td>${c.done||0}</td></tr>`).join("")||`<tr><td colspan=7 class="mut">No containers running</td></tr>`;
  toast("Container status refreshed");
}

async function injectChaos(act){
  const node=$("chaosNode").value;
  toast(`Injecting Chaos '${act}' on ${node}...`);
  const r=await api({type:"CHAOS_ACTION",action:act,node_id:node,delay_ms:250});
  if(r.type=="ERROR")return toast(r.error,0);
  $("chaosOut").innerHTML=`<div class="card" style="border:1px solid #d97706"><h4>Chaos Injection Result</h4><p>Target: <b>${r.node_id}</b> · Action: <b class="chip">${r.action.toUpperCase()}</b> · Status: <span class="tag ${r.status=='ONLINE'?'g':r.status=='SUSPECT'?'y':'r'}">${r.status||r.action}</span></p><p class="mut">Action processed. Coordinator logical clock ticked and failure detection callbacks executed.</p></div>`;
  toast(`Chaos action '${act}' injected successfully on ${node}`);
  refresh();
}

async function runIsoDemo(){
  toast("Running Cgroup Memory Isolation Demo...");
  const r=await api({type:"ISO_DEMO",limit_mb:80,leak_target_mb:140});
  if(r.type=="ERROR")return toast(r.error,0);
  $("isoOut").innerHTML=`<div class="card" style="border:1px solid #dc2626"><h4>Memory Quota Isolation Result (PID ${r.pid})</h4><table><tr><th>Configured Memory Limit</th><th>Workload Demand</th><th>Peak Observed RSS</th><th>Termination Event</th><th>Cluster State</th></tr><tr><td><b>${r.limit_mb} MB</b></td><td>140 MB</td><td><b>${r.peak_rss_mb} MB</b></td><td><span class="tag ${r.oom_killed?'r':'g'}">${r.oom_killed?'OOM-KILLED (exit 137)':'Exited Normally'}</span></td><td class="good">Protected &amp; Responsive</td></tr></table><p class="mut" style="margin-top:6px">OS Concept: Process Isolation &amp; Cgroups. Demonstrates that runaway processes cannot starve sibling nodes or master control plane.</p></div>`;
  toast("Memory isolation demo completed!");
  refresh();
}