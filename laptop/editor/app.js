"use strict";
import { RoomScene } from './scene.js';
import { photoProjection } from './reference.js';
const $ = id => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
let state, token, selected, filter = "all", dirty = false, formDirty = false, busy = false, view;
let scene, currentIssue=null, showSkipped=false, mode='3d';
const pretty = value => (value || "Unknown").replace(/([a-z])([A-Z])/g, "$1 $2");
const meters = value => value == null ? "missing" : `${value.toFixed(2)} m`;
function node(tag, text, attrs = {}) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}
function svg(tag, attrs = {}, text) {
  const el = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  if (text != null) el.textContent = text;
  return el;
}
function message(text, error = false) {
  $("message").textContent = text;
  $("message").className = text ? `visible${error ? " error" : ""}` : "";
}
async function api(path, body) {
  const response = await fetch(path, body ? {method: "POST", headers: {"Content-Type":"application/json", "X-Editor-Token":token}, body:JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The local editor could not complete this action.");
  return data;
}
async function action(fn) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach(b => b.disabled = true);
  try { await fn(); } catch (error) { message(error.message, true); }
  finally { busy = false; document.querySelectorAll("button").forEach(b => b.disabled = false); }
}
function activeElement() { return state.elements.find(e => e.source.identifier === selected); }
function choose(id) {
  if (busy || (formDirty && !confirm("Discard unapplied changes to this element?"))) return;
  selected = id; formDirty = false; renderInventory(); renderPlan(); renderInspector();scene?.highlight(id, currentIssue?.elements || []);
}
function renderInventory() {
  const root = $("inventory"); root.replaceChildren();
  const query = $("search").value.toLowerCase();
  for (const [group, title] of [["objects", "Detected objects"], ["structure", "Room structure"]]) {
    const rows = state.elements.filter(e => (group === "objects") === (e.kind === "objects") && (filter === "all" || filter === group) && `${e.label} ${e.category} ${e.original_category} ${e.code}`.toLowerCase().includes(query));
    if (!rows.length) continue;
    root.append(node("h3", `${title} · ${rows.length}`, {class:"group-title"}));
    for (const e of rows) {
      const button = node("button", null, {class:`element${selected === e.source.identifier ? " selected" : ""}`, "aria-label":`${e.code} ${e.label}`, "aria-pressed":String(selected === e.source.identifier)});
      button.append(node("span", e.code, {class:"code"}));
      const detail = node("span"); detail.append(node("span", pretty(e.label), {class:"name"}));
      const dims = e.kind === "objects" ? [e.dimensions_m[0], e.dimensions_m[2]] : e.dimensions_m.slice(0,2);
      detail.append(node("small", `${pretty(e.category)} · ${dims.map(meters).join(" × ")}${Object.keys(e.overrides).length ? " · edited" : " · est."}`));
      button.append(detail);
      if (e.decision) button.append(node("span", {keep:"✓", remove:"×", unsure:"?"}[e.decision], {class:`decision ${e.decision}`,title:e.decision}));
      button.addEventListener("click", () => choose(e.source.identifier)); root.append(button);
    }
  }
  if (!root.children.length) root.append(node("p", "No matching elements.", {class:"muted"}));
}
function fit() {
  const [x0,y0,x1,y1] = state.bounds;
  view = [x0-.65,y0-.95,Math.max(x1-x0+1.3,1.5),Math.max(y1-y0+1.9,1.5)];
}
function renderPlan() {
  const root = $("plan"); root.replaceChildren();
  if (!view) fit();
  root.setAttribute("viewBox",view.join(" "));
  const rect = root.getBoundingClientRect();
  const screenScale = Math.min(rect.width/view[2],rect.height/view[3]) || 1;
  const textSize = Math.max(.09,10/screenScale);
  const defs = svg("defs");
  const grid = svg("pattern",{id:"grid",width:.5,height:.5,patternUnits:"userSpaceOnUse"});
  grid.append(svg("path",{d:"M .5 0 L 0 0 0 .5",fill:"none",stroke:"#dce2d7","stroke-width":.006}));
  defs.append(grid);root.append(defs,svg("rect",{x:view[0],y:view[1],width:view[2],height:view[3],fill:"url(#grid)"}));
  const order = ["floors","objects","walls","doors","openings","windows"];
  const elements = [...state.elements].sort((a,b) => order.indexOf(a.kind)-order.indexOf(b.kind));
  for (const e of elements) {
    if (!e.geometry) continue;
    const chosen = e.source.identifier === selected;
    const g = svg("g",{"data-element":e.source.identifier,tabindex:0,role:"button","aria-label":`${e.code} ${e.label}`,"aria-pressed":String(chosen)});
    g.append(svg("title",{},`${e.code} · ${e.label} · ${e.dimensions_m.map(meters).join(" × ")} · ${e.decision || e.kind}`));
    const points = e.geometry.points.map(p => p.join(",")).join(" ");
    if (e.geometry.type === "line") {
      const color = {walls:"#3b5145",doors:"#b78132",openings:"#42848a",windows:"#6294b5"}[e.kind];
      if (e.kind !== "walls") g.append(svg("polyline",{points,stroke:"#f4f5f1","stroke-width":.12}));
      g.append(svg("polyline",{points,fill:"none",stroke:chosen ? "#c48a22" : color,"stroke-width":e.kind === "walls" ? .065 : .036,"stroke-dasharray":e.excluded || e.kind === "openings" ? ".08 .045" : "none","opacity":e.excluded?.4:1}));
      g.append(svg("polyline",{points,fill:"none",stroke:"transparent","stroke-width":.16}));
      for (const p of e.geometry.points) g.append(svg("circle",{cx:p[0],cy:p[1],r:.035,fill:color}));
    } else if (e.geometry.type === "marker") {
      g.append(svg("circle",{cx:e.center[0],cy:e.center[1],r:.09,fill:"#f9e4bc",stroke:"#b78132","stroke-width":.015}));
    } else {
      const color = e.kind === "floors" ? ["#e9ede1","#cdd7c4"] : {keep:["#c8dfcf","#5f8f70"],remove:["#f3e4de","#b66c59"],unsure:["#dce2d4","#91a080"]}[e.decision];
      g.append(svg("polygon",{points,fill:color[0],"fill-opacity":e.excluded ? .2 : e.kind === "floors" ? .66 : .8,stroke:chosen ? "#c28a23" : color[1],"stroke-width":chosen ? .035 : .013,"stroke-dasharray":e.excluded ? ".07 .04" : "none"}));
      if (e.decision === "remove") {
        const [a,b] = [e.geometry.points[0],e.geometry.points[Math.floor(e.geometry.points.length/2)]];
        g.append(svg("line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:"#b66c59","stroke-width":.012}));
      }
    }
    g.addEventListener("click",() => { if (!dragMoved) choose(e.source.identifier); });
    g.addEventListener("keydown",event => {if (event.key === "Enter" || event.key === " ") {event.preventDefault(); choose(e.source.identifier);}});
    root.append(g);
  }
  // Labels are a separate pass so every footprint remains visible beneath them.
  const usedLabels = [];
  for (const e of elements) {
    if (!e.geometry || !e.center || e.kind === "floors") continue;
    const [cx,cy] = e.center;
    if (e.kind === "objects") {
      const bw=textSize*2.05,bh=textSize*1.55;
      let lx=cx,ly=cy;
      for (const [dx,dy] of [[0,0],[0,bh],[0,-bh],[bw,0],[-bw,0],[bw,bh],[-bw,-bh]]) {
        lx=cx+dx;ly=cy+dy;
        if(!usedLabels.some(p=>Math.abs(p[0]-lx)<bw*1.1 && Math.abs(p[1]-ly)<bh*1.1))break;
      }
      usedLabels.push([lx,ly]);
      if(lx!==cx || ly!==cy)root.append(svg("line",{x1:cx,y1:cy,x2:lx,y2:ly,stroke:"#758571","stroke-width":.009,"pointer-events":"none"}));
      root.append(svg("rect",{x:lx-bw/2,y:ly-bh/2,width:bw,height:bh,rx:.04,class:"badge"}));
      root.append(svg("text",{x:lx,y:ly+textSize*.35,"font-size":textSize,"text-anchor":"middle",class:"plan-label"},e.code));
    } else {
      const p = e.geometry.points;
      const dx = p.length > 1 ? p[1][0]-p[0][0] : 1, dy = p.length > 1 ? p[1][1]-p[0][1] : 0;
      let angle = Math.atan2(dy,dx)*180/Math.PI;
      if (angle > 90) angle -= 180; if (angle < -90) angle += 180;
      const length = Math.hypot(dx,dy);
      const label = length > .65 ? `${e.code} · ${meters(e.dimensions_m[0])}${Object.keys(e.overrides.dimensions_m || {}).length ? "*" : ""}` : e.code;
      const offset = e.kind === "walls" ? -textSize*.9 : textSize*1.65;
      root.append(svg("text",{x:cx,y:cy+offset,transform:`rotate(${angle} ${cx} ${cy})`,class:"plan-label","text-anchor":"middle","font-size":textSize},label));
    }
  }
  const [x0,y0,x1,y1] = state.bounds;
  root.append(svg("line",{x1:x0,y1:y1+.45,x2:x0+1,y2:y1+.45,stroke:"#576d58","stroke-width":.018}));
  for (const x of [x0,x0+1]) root.append(svg("line",{x1:x,y1:y1+.39,x2:x,y2:y1+.51,stroke:"#576d58","stroke-width":.018}));
  root.append(svg("text",{x:x0+.5,y:y1+.67,"text-anchor":"middle","font-size":textSize,fill:"#65745d"},"1 meter · grid 0.5 m"));
  root.append(svg("text",{x:x1,y:y1+.48,"text-anchor":"end","font-size":textSize*.9,fill:"#65745d"},"Aligned to longest wall · no compass bearing"));
}
function field(form, label, id, value, hint, type="text") {
  const wrap = node("label",label,{class:"field",for:id});
  const input = node(type === "textarea" ? "textarea" : "input",null,{id});
  if (type !== "textarea") input.type = type;
  input.value = value ?? "";
  if (type === "number") {input.min="0.001";input.max="100";input.step="any";}
  else input.maxLength = type === "textarea" ? 1000 : 100;
  wrap.append(input);if(hint) wrap.append(node("small",hint));form.append(wrap);return input;
}
function renderInspector() {
  const e = activeElement(); const root = $("inspector"); root.replaceChildren();
  if (!e) return;
  root.append(node("p",`${e.kind === "objects" ? "OBJECT" : "STRUCTURE"} ${e.code}`,{class:"eyebrow"}),node("h2",pretty(e.label)));
  const evidence=node('div',null,{class:'evidence-facts'});
  evidence.append(node('p',`Category confidence: ${e.confidence || 'missing'} (RoomPlan)`),node('p','Measurement accuracy: unverified'),node('p',`Editable layer color: ${e.color.origin==='reference'?'photo-supported estimate':e.color.origin==='user'?'user choice':'unknown / approximate'}`));root.append(evidence);
  renderReviewCard(root,e);renderReference(root,e);
  root.append(node('p','Edits below affect the RoomPlan layer. Photographic reconstruction remains the captured record.',{class:'muted'}));
  const form = node("form",null,{id:"edit-form"});
  field(form,"Display label","edit-label",e.overrides.label ?? e.label,"A name you recognize on the plan.");
  field(form,"Category correction","edit-category",e.overrides.category ?? e.original_category,`Original RoomPlan category: ${e.original_category || "missing"}. Corrections stay separate.`);
  if (e.kind === "objects") {
    const fieldset = node("fieldset");fieldset.append(node("legend","Furniture decision"));const choices=node("div",null,{class:"choices"});
    for (const value of ["keep","remove","unsure"]) {
      const label = node("label",null,{class:"choice"});const radio=node("input",null,{type:"radio",name:"decision",value});radio.checked=e.decision===value;
      label.append(radio,document.createTextNode(value[0].toUpperCase()+value.slice(1)));choices.append(label);
    }
    fieldset.append(choices);form.append(fieldset);
  } else {
    const label=node('label',null,{class:'exclude-choice'}),input=node('input',null,{type:'checkbox',id:'edit-excluded'});input.checked=e.excluded;label.append(input,document.createTextNode('Exclude from reviewed room'));form.append(label);
  }
  const colors=node('div',null,{class:'color-editor'});
  const picker=field(colors,e.kind==='walls'?'Wall color':e.kind==='floors'?'Floor color':'Proxy color','edit-color',e.color.hex,e.color.certainty,'color');
  const use=node('label',null,{class:'exclude-choice'}),check=node('input',null,{type:'checkbox',id:'color-override'});check.checked=e.color.origin==='user';use.append(check,document.createTextNode('Use my chosen color'));colors.append(use);
  picker.addEventListener('input',()=>{check.checked=true;});form.append(colors);
  const dims=node("div",null,{class:"dimensions"});
  for(let i=0;i<(e.kind === "objects" ? 3 : 2);i++) {
    const axis="xyz"[i];const label = e.kind === "floors" ? ["Plane width","Plane length"][i] : ["Width","Height","Depth"][i];
    const hint=`${e.dimension_status[i]}. Source: ${meters(e.original_dimensions_m[i])}.`;
    const input=field(dims,`${label} (m)`,`dim-${axis}`,e.overrides.dimensions_m?.[axis] ?? "",hint,"number");
    input.placeholder = e.original_dimensions_m[i] == null ? "Missing" : String(Number(e.original_dimensions_m[i].toFixed(4)));
  }
  form.append(dims);
  form.append(node("p","Blank uses the source estimate. Enter a value to correct it; corrections are unverified until you measure the room.",{class:"muted"}));
  field(form,"Review note","edit-note",e.overrides.note ?? "", "Optional context for your changes.","textarea");
  const buttons = node("div",null,{class:"form-buttons"});buttons.append(node("button","Apply edits",{type:"submit",class:"primary"}));
  const reset=node("button","Reset element",{type:"button"});reset.addEventListener("click",() => action(async()=>{
    const doc=structuredClone(state.document);const row=doc.elements.find(e=>e.source.identifier===selected);row.overrides={};if(row.decision)row.decision="unsure";
    for(const issue of state.review_queue.filter(q=>q.elements.includes(selected)))delete doc.reviews[issue.id];
    state=await api("/api/preview",{document:doc,filename:state.filename});dirty=true;formDirty=false;currentIssue=null;render();message("Element restored to its scan estimate and default decision. Save to keep this revision.");
  }));buttons.append(reset);form.append(buttons);
  form.addEventListener("input",()=>{formDirty=true;renderStatus();});
  form.addEventListener("submit",event=>{event.preventDefault();action(async()=>{await applyForm();message("Edits applied in 3D and 2D. Save a revision to keep them.");});});root.append(form);
  const source=node("div",null,{class:"source-details"});
  source.append(node("strong","Source & evidence"),node("p",`Dimensions: ${e.original_dimensions_m.map(meters).join(" × ")} (local X / Y / Z)`),node("p",e.kind === "objects" ? "RoomPlan bounding box, not a detailed furniture outline." : e.kind === "floors" ? "Floor polygon transformed from local plane coordinates." : "Width and height describe a plane. Thickness is not supplied."));
  source.append(node("p",`Original category: ${e.original_category || "missing"}${e.overrides.category ? ` → corrected to ${e.category}` : ""}`));
  source.append(node("code",`Room.json#${e.source.json_pointer}`),node("code",e.source.identifier));
  if(e.parent_identifier)source.append(node("code",`Parent wall: ${e.parent_identifier}`));
  for(const warning of e.warnings)source.append(node("p",warning,{class:"warning"}));
  root.append(source);
}
async function applyForm() {
  const form=$("edit-form");if(!form || !formDirty)return;
  if(!form.reportValidity())throw new Error("Check the highlighted field before applying or saving.");
  const e=activeElement(),doc=structuredClone(state.document),edit=doc.elements.find(row=>row.source.identifier===selected);
  const overrides={};const label=$("edit-label").value.trim(),category=$("edit-category").value.trim(),note=$("edit-note").value.trim();
  if(label && label!==(e.original_category || "Unknown"))overrides.label=label;
  if(category && category!==e.original_category)overrides.category=category;
  if(note)overrides.note=note;
  if($('color-override').checked)overrides.color={hex:$('edit-color').value,origin:'user'};
  if(e.kind!=='objects' && $('edit-excluded').checked)overrides.excluded=true;
  const dimensions={};for(const axis of "xyz") {const input=$(`dim-${axis}`);if(input?.value.trim())dimensions[axis]=Number(input.value);}
  if(Object.keys(dimensions).length)overrides.dimensions_m=dimensions;
  edit.overrides=overrides;if(e.kind==="objects")edit.decision=form.querySelector('input[name="decision"]:checked').value;
  state=await api("/api/preview",{document:doc,filename:state.filename});dirty=true;formDirty=false;render();
}
function renderReference(root,e) {
  if(!state.reference){root.append(node('p','No RGB reference in this scan.',{class:'muted'}));return;}
  const observation=e.reference_observation, projection=photoProjection(e,state.reference);
  const details=node('details',null,{class:'reference-panel'});details.open=!!observation || !!projection || !!currentIssue;
  details.append(node('summary',observation?'Reference photo · observed patch':projection?'Reference photo · projected location':'Reference photo · element not located'));
  const wrap=node('div',null,{class:'reference-image'}),img=node('img',null,{src:state.reference.url,alt:'Single sensor-native RGB frame from the original scan'});wrap.append(img);
  const uv=observation?.sample_uv || projection;
  if(uv){const dot=node('span',observation?'•':'＋',{class:'photo-dot',title:observation?'Observed color sample':'Projected center; occlusion and correspondence unverified'});dot.style.left=`${uv[0]*100}%`;dot.style.top=`${uv[1]*100}%`;wrap.append(dot);}
  details.append(wrap,node('p',observation?observation.note:projection?'Cross = projected center, possibly occluded. This does not establish visibility or a color match.':'This frame does not locate the selected element. Its color remains unknown unless you choose one.',{class:'muted'}));
  const link=node('a','Open full reference',{href:state.reference.url,target:'_blank',rel:'noopener'});details.append(link);root.append(details);
}
function renderQueue() {
  const root=$('review-queue');root.replaceChildren();
  const pending=state.review_queue.filter(q=>q.status==='pending'),skipped=state.review_queue.filter(q=>q.status==='skipped');
  $('review-count').textContent=pending.length;
  const issues=showSkipped?skipped:pending;
  for(const issue of issues.slice(0,3)) {
    const button=node('button',null,{class:`review-item${currentIssue?.id===issue.id?' active':''}`});button.append(node('strong',issue.title),node('small',issue.kind==='overlap'?'Check both estimates':issue.kind==='category'?'Category, not measurement accuracy':'Check the passage'));
    button.onclick=()=>{if(formDirty && !confirm('Discard unapplied changes to this element?'))return;formDirty=false;currentIssue=issue;choose(issue.elements[0]);scene?.focus(issue.elements[0]);renderQueue();};root.append(button);
  }
  if(!issues.length)root.append(node('p',showSkipped?'No skipped items.':'No unresolved items in this queue.',{class:'muted'}));
  if(issues.length>3)root.append(node('p',`Showing 3 of ${issues.length}; more appear as you review.`,{class:'muted'}));
  $('show-skipped').textContent=showSkipped?'Back to needs review':`Show skipped (${skipped.length})`;
}
function renderReviewCard(root,e) {
  const issue=currentIssue && state.review_queue.find(q=>q.id===currentIssue.id && q.elements.includes(e.source.identifier));
  if(!issue)return;
  const card=node('section',null,{class:'review-card'});card.append(node('strong',issue.title),node('p',issue.detail));
  if(issue.elements.length>1){const peers=node('div',null,{class:'review-peers'});for(const id of issue.elements){const peer=state.elements.find(x=>x.source.identifier===id),button=node('button',`${peer.code} ${pretty(peer.label)}`);button.onclick=()=>{choose(id);scene?.focus(id);};peers.append(button);}card.append(peers);}
  const buttons=node('div',null,{class:'review-actions'});
  for(const [status,label] of [['confirmed','Confirm'],['corrected','Save correction'],['excluded','Exclude selected'],['skipped','Skip']]) {
    const b=node('button',label,{type:'button'});b.onclick=()=>action(async()=>{
      const before=JSON.stringify(activeElement().overrides);
      await applyForm();
      if(status==='corrected' && before===JSON.stringify(activeElement().overrides) && !activeElement().overrides.category && !activeElement().overrides.dimensions_m && !activeElement().overrides.label)throw new Error('Edit the category, label, or dimensions below, then save the correction.');
      const doc=structuredClone(state.document);
      if(status==='excluded'){const edit=doc.elements.find(x=>x.source.identifier===selected);if(e.kind==='objects')edit.decision='remove';else edit.overrides.excluded=true;}
      doc.reviews[issue.id]=status;
      // A correction rekeys the same issue; resolve its current equivalent as well.
      for(const q of state.review_queue)if(q.kind===issue.kind && JSON.stringify(q.elements)===JSON.stringify(issue.elements))doc.reviews[q.id]=status;
      state=await api('/api/preview',{document:doc,filename:state.filename});dirty=true;currentIssue=null;render();message(`${label} applied. Save a revision to keep your review.`);
    });buttons.append(b);
  }
  card.append(buttons,node('small','Confirm accepts the detection/conflict for review; it does not verify dimensions.'));root.append(card);
}
function renderStatus() {
  $("save-status").textContent=(dirty || formDirty ? "● Unsaved changes" : state.filename ? `Saved · revision ${state.document.revision}` : "Original scan · no edits saved");
}
function render() {
  $("source-status").textContent=`✓ Verified scan · ${state.document.source.scan_id.slice(0,8)} · ${state.elements.filter(e=>e.kind==="walls").length} walls · ${state.elements.filter(e=>e.kind==="doors").length} doors · ${state.elements.filter(e=>e.kind==="openings").length} openings · ${state.elements.filter(e=>e.kind==="windows").length} windows detected`;
  $("element-count").textContent=state.elements.length;
  renderStatus();renderQueue();renderInventory();renderPlan();renderInspector();scene?.update(state,selected);scene?.highlight(selected,currentIssue?.elements || []);
  const select=$("versions");select.replaceChildren(node("option","Saved revisions…",{value:""}));
  for(const name of state.versions)select.append(node("option",name,{value:name}));select.value=state.filename || state.versions.at(-1) || "";
  $("file-path").textContent=state.filename ? `${state.output_directory}/${state.filename}` : `Save location: ${state.output_directory}`;
  const counts={keep:0,remove:0,unsure:0};for(const e of state.elements)if(e.decision)counts[e.decision]++;
  const missing=state.elements.filter(e=>e.warnings.length).length;
  $("summary").replaceChildren(node("span",`${counts.keep} keep · ${counts.remove} remove · ${counts.unsure} unsure`),node("span",`${missing} geometry warnings · ${state.missing_collections.length} missing collections`));
}
$("save").addEventListener("click",()=>action(async()=>{
  message("Verifying source and saving revision…");await applyForm();state=await api("/api/save",{document:state.document,filename:state.filename});dirty=false;formDirty=false;render();message(`Saved ${state.filename}. Reopen it to verify the saved plan and decisions.`);
}));
$("reopen").addEventListener("click",()=>action(async()=>{
  const name=$("versions").value;if(!name)throw new Error("Save a revision first, then choose it here.");
  if((dirty || formDirty) && !confirm("Discard unsaved changes and reopen this revision?"))return;
  state=await api(`/api/open?file=${encodeURIComponent(name)}`);dirty=false;formDirty=false;view=null;currentIssue=null;render();message(`Reopened ${name} from disk. Source scan hashes verified.`);
}));
$("original").addEventListener("click",()=>action(async()=>{
  if((dirty || formDirty) && !confirm("Discard unsaved changes and return to the original scan?"))return;
  state=await api("/api/new");dirty=false;formDirty=false;view=null;currentIssue=null;render();message("Original scan loaded. Saved revisions remain available.");
}));
$("search").addEventListener("input",renderInventory);
document.querySelectorAll("[data-filter]").forEach(b=>b.addEventListener("click",()=>{filter=b.dataset.filter;document.querySelectorAll("[data-filter]").forEach(x=>x.classList.toggle("active",x===b));renderInventory();}));
function zoom(factor){const [x,y,w,h]=view;view=[x+w*(1-factor)/2,y+h*(1-factor)/2,w*factor,h*factor];renderPlan();}
$("zoom-in").addEventListener("click",()=>zoom(.8));$("zoom-out").addEventListener("click",()=>zoom(1.25));$("fit").addEventListener("click",()=>{fit();renderPlan();});
let drag=null,dragMoved=false;
$("plan").addEventListener("pointerdown",event=>{drag={x:event.clientX,y:event.clientY,view:[...view]};dragMoved=false;});
window.addEventListener("pointermove",event=>{
  if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;
  if(Math.hypot(dx,dy)<4)return;dragMoved=true;
  const rect=$("plan").getBoundingClientRect(),scale=Math.min(rect.width/drag.view[2],rect.height/drag.view[3]);
  view=[drag.view[0]-dx/scale,drag.view[1]-dy/scale,drag.view[2],drag.view[3]];renderPlan();
});window.addEventListener("pointerup",()=>{drag=null;});
window.addEventListener("beforeunload",event=>{if(dirty || formDirty){event.preventDefault();event.returnValue="";}});
window.addEventListener("resize",()=>{if(state)renderPlan();});
function setMode(next) {
  mode=next;$('capture-tools').hidden=mode==='2d'||!scene?.reconstruction;document.querySelector('.workspace').classList.toggle('plan-mode',mode==='2d');
  $('view-3d').classList.toggle('active',mode==='3d');$('view-2d').classList.toggle('active',mode==='2d');
  $('view-3d').setAttribute('aria-pressed',String(mode==='3d'));$('view-2d').setAttribute('aria-pressed',String(mode==='2d'));
  $('view-title').textContent=mode==='3d'?'A feel for the space':'Check the layout';$('view-eyebrow').textContent=mode==='3d'?'3D ROOM · METERS':'OVERHEAD PLAN · METERS';
  if(mode==='3d' && scene?.reconstruction)describeLayer();
  requestAnimationFrame(()=>{renderPlan();scene?.resize();});
}
$('view-3d').onclick=()=>setMode('3d');$('view-2d').onclick=()=>setMode('2d');
$('cutaway').onchange=()=>{if(scene){scene.cutaway=$('cutaway').checked;scene.draw();}};
$('show-excluded').onchange=()=>{if(scene){scene.showExcluded=$('show-excluded').checked;scene.draw();}};
$('fit-3d').onclick=()=>scene?.fit();$('focus-3d').onclick=()=>scene?.focus(selected);
$('show-skipped').onclick=()=>{showSkipped=!showSkipped;renderQueue();};
try { scene=new RoomScene($('scene'),choose); }
catch(error) { $('scene-error').hidden=false;$('scene-error').textContent=`3D unavailable: ${error.message}. The linked 2D plan and editor are still available.`; }
function describeLayer(){
  const mode=scene.layerMode,scanned=mode!=='roomplan';
  $('view-title').textContent=scanned?'Walk through your room':'A feel for the space';
  $('view-eyebrow').textContent=scanned?'AS SCANNED · LOCAL RECONSTRUCTION':'EDITABLE ROOMPLAN · METERS';
  document.querySelector('.scene-caption').textContent=scanned?(scene.navigation==='walk'?'Drag to look · W A S D to move · Q / E down / up · gaps lack reliable data':'Drag to orbit · scroll to zoom · W A S D to move · gaps lack reliable data'):'Bounding-box furniture · drag to orbit · scroll to zoom';
  $('walk-mode').classList.toggle('active',scene.navigation==='walk');$('orbit-mode').classList.toggle('active',scene.navigation==='orbit');
  $('layer-note').textContent=scanned?'Photographs + measured depth from this capture. Gaps, grey surfaces and unseen backs remain unknown. Reflections, thin objects and texture seams may be unreliable. RoomPlan is a separate editable estimate; moving through geometry does not establish physical clearance.':'RoomPlan estimates, not a photorealistic room. Use the inspector and linked plan to edit dimensions and review detections.';
  $('scene-tools').hidden=scanned;document.querySelector('.color-key').hidden=scanned;
}
$('scan-layer').onchange=()=>action(async()=>{await scene.setLayer($('scan-layer').value);describeLayer();});
$('roomplan-overlay').onchange=()=>{scene.overlay=$('roomplan-overlay').checked;scene.root.visible=scene.layerMode==='roomplan'||scene.overlay;scene.draw();};
$('go-viewpoint').onclick=()=>scene?.goToView(Number($('capture-viewpoint').value));
$('expand-room').onclick=()=>{const expanded=document.body.classList.toggle('expanded-room');$('expand-room').textContent=expanded?'Show editor':'Expand 3D';$('expand-room').setAttribute('aria-pressed',String(expanded));requestAnimationFrame(()=>scene?.resize());};
$('walk-mode').onclick=()=>{scene?.setNavigation('walk');describeLayer();};
$('orbit-mode').onclick=()=>{scene?.setNavigation('orbit');describeLayer();};
action(async()=>{
  state=await api('/api/state');token=state.token;selected=state.elements.find(e=>e.kind==='objects')?.source.identifier||state.elements[0]?.source.identifier;render();
  const reconstruction=await api('/api/reconstruction');
  if(reconstruction && scene){
    $('capture-tools').hidden=false;$('capture-provenance').textContent=reconstruction.provenance;
    reconstruction.viewpoints.forEach((v,i)=>$('capture-viewpoint').append(node('option',v.label,{value:String(i)})));
    $('scan-layer').querySelector('[value="splat"]').disabled=!reconstruction.splat_url;
    message('Loading the photographic reconstruction…');await scene.loadReconstruction(reconstruction);
    if(reconstruction.preferred==='splat'){await scene.setLayer('splat');$('scan-layer').value='splat';}
    describeLayer();message('');
  }
});
