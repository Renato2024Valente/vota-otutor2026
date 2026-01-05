
async function fetchJSON(url, opts){
  const r = await fetch(url, opts);
  const data = await r.json().catch(()=> ({}));
  if(!r.ok) throw new Error(data.error || "Erro ao comunicar com o servidor.");
  return data;
}

function beepOk(){
  // Beep via WebAudio (funciona em PC/celular após interação do usuário)
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = "sine";
  o.frequency.value = 880;
  g.gain.value = 0.0001;

  o.connect(g);
  g.connect(ctx.destination);
  o.start();

  // ataque/decay
  g.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.20);

  setTimeout(()=>{ try{ o.stop(); ctx.close(); }catch(e){} }, 220);
}

function showMsg(kind, text){
  const box = document.getElementById("msg");
  box.className = `alert alert-${kind}`;
  box.textContent = text;
  box.classList.remove("d-none");
}

function clearMsg(){
  const box = document.getElementById("msg");
  box.classList.add("d-none");
}

async function loadTutores(){
  const sel = document.getElementById("tutor");
  sel.innerHTML = `<option value="">Carregando...</option>`;
  try{
    const tutores = await fetchJSON("/api/tutores");
    sel.innerHTML = `<option value="">Selecione...</option>` + tutores.map(t=>(
      `<option value="${t.id}">${t.nome}</option>`
    )).join("");
  }catch(e){
    sel.innerHTML = `<option value="">(Erro ao carregar)</option>`;
    showMsg("danger", e.message);
  }
}

document.addEventListener("DOMContentLoaded", ()=>{
  loadTutores();

  const form = document.getElementById("formVoto");
  const btnLimpar = document.getElementById("btnLimpar");

  btnLimpar.addEventListener("click", ()=>{
    document.getElementById("aluno").value = "";
    document.getElementById("serie").value = "";
    document.getElementById("tutor").value = "";
    clearMsg();
    document.getElementById("aluno").focus();
  });

  form.addEventListener("submit", async (ev)=>{
    ev.preventDefault();
    clearMsg();

    const aluno = document.getElementById("aluno").value.trim();
    const serie = document.getElementById("serie").value.trim();
    const tutor_id = document.getElementById("tutor").value;

    const btn = document.getElementById("btnEnviar");
    btn.disabled = true;

    try{
      const res = await fetchJSON("/api/votar", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ aluno, serie, tutor_id })
      });

      beepOk();

      // modal
      document.getElementById("sucessoTexto").textContent = `Seu voto foi registrado para: ${res.tutor}.`;
      const modal = new bootstrap.Modal(document.getElementById("modalSucesso"));
      modal.show();

      // limpa
      document.getElementById("tutor").value = "";
      document.getElementById("aluno").value = "";
      document.getElementById("serie").value = "";
      showMsg("success", res.message);

    }catch(e){
      showMsg("danger", e.message);
    }finally{
      btn.disabled = false;
    }
  });
});
