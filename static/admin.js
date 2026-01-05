
let chart;

async function fetchJSON(url, opts){
  const r = await fetch(url, opts);
  const data = await r.json().catch(()=> ({}));
  if(!r.ok) throw new Error(data.error || "Erro ao comunicar com o servidor.");
  return data;
}

function toast(kind, text){
  const box = document.getElementById("msg");
  box.className = `alert alert-${kind}`;
  box.textContent = text;
  box.classList.remove("d-none");
  setTimeout(()=> box.classList.add("d-none"), 3500);
}

function buildChart(labels, values){
  const ctx = document.getElementById("chartVotos");
  if(chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Votos",
        data: values,
        borderWidth: 0,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins:{
        legend:{ display:false }
      },
      scales:{
        x:{ ticks:{ color:"#ffffffcc" }, grid:{ color:"rgba(255,255,255,.08)" } },
        y:{ ticks:{ color:"#ffffffcc" }, grid:{ color:"rgba(255,255,255,.08)" }, beginAtZero:true }
      }
    }
  });
}

function setAmostraTable(items){
  const tb = document.getElementById("tbodyAmostra");
  tb.innerHTML = "";
  for(const it of items){
    const dt = new Date(it.data);
    const dts = isNaN(dt) ? it.data : dt.toLocaleString("pt-BR");
    tb.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${escapeHtml(it.aluno)}</td>
        <td>${escapeHtml(it.serie)}</td>
        <td class="text-end small text-white-50">${escapeHtml(dts)}</td>
      </tr>
    `);
  }
}

function escapeHtml(s){
  return String(s || "")
    .replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
    .replaceAll('"',"&quot;").replaceAll("'","&#039;");
}

let confirmAction = null;

function confirmModal(text, onOk){
  confirmAction = onOk;
  document.getElementById("confirmText").textContent = text;
  const modal = new bootstrap.Modal(document.getElementById("modalConfirm"));
  modal.show();
  document.getElementById("confirmOk").onclick = async ()=>{
    try{
      await confirmAction?.();
      modal.hide();
    }catch(e){
      toast("danger", e.message);
    }
  };
}

async function refresh(){
  const data = await fetchJSON("/api/resultados");
  document.getElementById("totalVotos").textContent = data.total;

  const tutores = data.tutores || [];
  const labels = tutores.slice(0, 15).map(t=> t.nome);
  const values = tutores.slice(0, 15).map(t=> t.votos);

  buildChart(labels, values);

  const tbody = document.getElementById("tbodyResultados");
  tbody.innerHTML = "";

  for(const t of tutores){
    const need = t.precisa_amostragem;
    const has = !!t.amostragem;

    const badge = need
      ? (has ? `<span class="badge text-bg-success">Amostragem pronta</span>` : `<span class="badge text-bg-warning">>100 • Gerar</span>`)
      : `<span class="badge text-bg-secondary">&le;100</span>`;

    const btnAmostra = need
      ? `<button class="btn btn-sm btn-outline-light rounded-pill me-1" data-action="amostrar" data-id="${t.id}">
           <i class="bi bi-shuffle"></i> ${has ? "Regerar" : "Gerar"} amostragem
         </button>
         <button class="btn btn-sm btn-outline-light rounded-pill" data-action="veramostra" data-id="${t.id}">
           <i class="bi bi-list-check"></i> Ver lista
         </button>`
      : `<button class="btn btn-sm btn-outline-light rounded-pill" data-action="veramostra" data-id="${t.id}">
           <i class="bi bi-list-check"></i> Ver lista
         </button>`;

    tbody.insertAdjacentHTML("beforeend", `
      <tr>
        <td>
          <div class="fw-semibold">${escapeHtml(t.nome)}</div>
          <div class="small text-white-50">${badge}</div>
        </td>
        <td class="text-end fw-semibold">${t.votos}</td>
        <td class="text-end">
          ${btnAmostra}
          <button class="btn btn-sm btn-danger rounded-pill ms-2" data-action="remover" data-id="${t.id}">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>
    `);
  }
}

async function gerarAmostragem(tutorId){
  const res = await fetchJSON(`/api/admin/amostragem/${tutorId}`, { method:"POST" });
  if(res.amostragem){
    document.getElementById("amostraInfo").textContent = `${res.tutor} • Amostragem: ${res.amostragem.quantidade} alunos (seed ${res.amostragem.seed})`;
  }else{
    document.getElementById("amostraInfo").textContent = `${res.tutor} • Lista completa (${res.selecionados.length} alunos)`;
  }
  setAmostraTable(res.selecionados || []);
  toast("success", res.message || "OK");
  await refresh();
}

async function verUltimaOuLista(tutorId){
  // tenta buscar ultima amostragem; se não existir, mostra lista completa (via gerar endpoint, mas sem salvar)
  const r = await fetchJSON(`/api/admin/amostragem/${tutorId}/ultima`);
  if(r.amostragem){
    document.getElementById("amostraInfo").textContent = `${r.tutor} • Amostragem: ${r.amostragem.quantidade} alunos (seed ${r.amostragem.seed})`;
    setAmostraTable(r.selecionados || []);
    return;
  }
  // sem amostragem: pega lista completa chamando gerar (retorna lista completa sem salvar quando <=100)
  const res = await fetchJSON(`/api/admin/amostragem/${tutorId}`, { method:"POST" });
  document.getElementById("amostraInfo").textContent = `${res.tutor} • Lista completa (${res.selecionados.length} alunos)`;
  setAmostraTable(res.selecionados || []);
}

async function addTutor(nome){
  const res = await fetchJSON("/api/admin/tutores", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ nome })
  });
  toast("success", res.message || "Tutor adicionado.");
  await refresh();
}

async function removeTutor(id){
  const res = await fetchJSON(`/api/admin/tutores/${id}`, { method:"DELETE" });
  toast("success", res.message || "Tutor removido.");
  await refresh();
}

document.addEventListener("DOMContentLoaded", async ()=>{
  await refresh();
  const timer = setInterval(refresh, 4000);

  document.getElementById("btnAtualizar").addEventListener("click", refresh);

  document.getElementById("formAddTutor").addEventListener("submit", async (ev)=>{
    ev.preventDefault();
    const input = document.getElementById("novoTutor");
    const nome = input.value.trim();
    if(!nome) return toast("warning", "Digite um nome.");
    input.value = "";
    await addTutor(nome);
  });

  document.getElementById("tbodyResultados").addEventListener("click", async (ev)=>{
    const btn = ev.target.closest("button");
    if(!btn) return;
    const id = btn.getAttribute("data-id");
    const action = btn.getAttribute("data-action");
    if(!id || !action) return;

    if(action === "remover"){
      confirmModal("Remover (desativar) esse tutor? Ele não aparecerá mais para votação.", async ()=>{
        await removeTutor(id);
      });
    }

    if(action === "amostrar"){
      confirmModal("Gerar/Regerar amostragem aleatória para esse tutor?", async ()=>{
        await gerarAmostragem(id);
      });
    }

    if(action === "veramostra"){
      await verUltimaOuLista(id);
    }
  });
});
