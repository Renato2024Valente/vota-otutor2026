
const form = document.getElementById("formVoto");
const msg = document.getElementById("msg");

function showMsg(text, type="success"){
  msg.className = `alert mt-3 alert-${type}`;
  msg.textContent = text;
  msg.classList.remove("d-none");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  msg.classList.add("d-none");

  const fd = new FormData(form);
  const payload = {
    aluno: fd.get("aluno"),
    serie: fd.get("serie"),
    tutor_id: fd.get("tutor_id"),
  };

  try{
    const r = await fetch("/api/votar", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const j = await r.json().catch(()=>({ok:false, error:"Resposta inválida"}));
    if(!r.ok || !j.ok){
      showMsg(j.error || "Erro ao registrar voto.", "danger");
      return;
    }
    form.reset();
    showMsg("Voto registrado com sucesso! Obrigado.", "success");
  }catch(err){
    showMsg("Falha de conexão. Tente novamente.", "danger");
  }
});
