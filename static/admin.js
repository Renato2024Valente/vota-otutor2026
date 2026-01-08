
const listaTutores = document.getElementById("listaTutores");
const resultadosWrap = document.getElementById("resultadosWrap");
const badgeTotal = document.getElementById("badgeTotal");

const btnAddTutor = document.getElementById("btnAddTutor");
const novoTutorNome = document.getElementById("novoTutorNome");

const capacidadeSelect = document.getElementById("capacidadeSelect");
const btnSalvarCap = document.getElementById("btnSalvarCap");

function escapeHtml(s){
  return String(s)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

async function api(path, opts={}){
  const r = await fetch(path, opts);
  const j = await r.json().catch(()=>({ok:false, error:"Resposta inválida"}));
  if(!r.ok || !j.ok) throw new Error(j.error || "Erro");
  return j;
}

function renderTutores(tutores){
  listaTutores.innerHTML = "";
  if(!tutores.length){
    listaTutores.innerHTML = `<div class="text-muted small">Nenhum tutor cadastrado.</div>`;
    return;
  }
  for(const t of tutores){
    const el = document.createElement("div");
    el.className = "list-group-item d-flex justify-content-between align-items-center";
    el.innerHTML = `
      <div>
        <div class="fw-semibold">${escapeHtml(t.nome)}</div>
        <div class="text-muted small">ID: ${t.id} • ${t.ativo ? "Ativo" : "Inativo"}</div>
      </div>
      <button class="btn btn-sm btn-outline-danger">Excluir</button>
    `;
    el.querySelector("button").addEventListener("click", async ()=>{
      if(!confirm(`Excluir o tutor "${t.nome}"? Isso apaga também os votos dele.`)) return;
      try{
        await api(`/api/admin/tutores/${t.id}`, {method:"DELETE"});
        await refreshAll();
      }catch(e){
        alert(e.message);
      }
    });
    listaTutores.appendChild(el);
  }
}

function renderResultados(payload){
  badgeTotal.textContent = `Total geral: ${payload.total_geral}`;
  const capacidade = payload.capacidade;

  resultadosWrap.innerHTML = "";
  for(const r of payload.resultados){
    const selected = r.selecionados || [];
    const fora = r.fora || [];

    const selectedHtml = selected.map(v=>(
      `<li class="list-group-item d-flex justify-content-between">
        <span>${escapeHtml(v.aluno)} <span class="text-muted">(${escapeHtml(v.serie)})</span></span>
        <span class="text-muted small-mono">${new Date(v.data).toLocaleString()}</span>
      </li>`
    )).join("");

    const foraHtml = fora.map(v=>(
      `<li class="list-group-item d-flex justify-content-between">
        <span>${escapeHtml(v.aluno)} <span class="text-muted">(${escapeHtml(v.serie)})</span></span>
        <span class="text-muted small-mono">${new Date(v.data).toLocaleString()}</span>
      </li>`
    )).join("");

    const card = document.createElement("div");
    card.className = "result-card";

    card.innerHTML = `
      <div class="result-header">
        <div>
          <div class="fw-semibold">${escapeHtml(r.nome)}</div>
          <div class="text-muted small">Total: <b>${r.total}</b> • Capacidade: <b>${capacidade}</b></div>
        </div>
        <span class="badge text-bg-${r.total > capacidade ? "warning" : "success"}">
          ${r.total > capacidade ? "Excedeu capacidade" : "OK"}
        </span>
      </div>

      <div class="row g-2 mt-2">
        <div class="col-md-6">
          <div class="small fw-semibold mb-1">Selecionados (até ${capacidade})</div>
          <ul class="list-group list-group-flush small">
            ${selectedHtml || `<li class="list-group-item text-muted">Sem votos.</li>`}
          </ul>
        </div>
        <div class="col-md-6">
          <div class="small fw-semibold mb-1">Fora / Lista de espera</div>
          <ul class="list-group list-group-flush small">
            ${foraHtml || `<li class="list-group-item text-muted">Ninguém fora.</li>`}
          </ul>
        </div>
      </div>
    `;
    resultadosWrap.appendChild(card);
  }
}

async function refreshAll(){
  const t = await api("/api/admin/tutores");
  renderTutores(t.tutores);

  const r = await api("/api/admin/resultados");
  renderResultados(r);
}

btnAddTutor.addEventListener("click", async ()=>{
  const nome = novoTutorNome.value.trim();
  if(!nome){
    alert("Digite o nome do tutor.");
    return;
  }
  try{
    await api("/api/admin/tutores", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({nome})
    });
    novoTutorNome.value = "";
    // close modal
    const modalEl = document.getElementById("modalTutor");
    bootstrap.Modal.getInstance(modalEl)?.hide();
    await refreshAll();
  }catch(e){
    alert(e.message);
  }
});

btnSalvarCap.addEventListener("click", async ()=>{
  try{
    const cap = parseInt(capacidadeSelect.value, 10);
    await api("/api/admin/capacidade", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({capacidade: cap})
    });
    await refreshAll();
  }catch(e){
    alert(e.message);
  }
});

// auto refresh
refreshAll();
setInterval(refreshAll, 3000);
