
async function fetchJSON(url, opts){
  const r = await fetch(url, opts);
  const data = await r.json().catch(()=> ({}));
  if(!r.ok) throw new Error(data.error || "Erro.");
  return data;
}

function showMsg(kind, text){
  const box = document.getElementById("msg");
  box.className = `alert alert-${kind}`;
  box.textContent = text;
  box.classList.remove("d-none");
}

document.addEventListener("DOMContentLoaded", ()=>{
  const form = document.getElementById("formLogin");
  const senha = document.getElementById("senha");
  const toggle = document.getElementById("toggleSenha");

  toggle.addEventListener("click", ()=>{
    const isPass = senha.getAttribute("type") === "password";
    senha.setAttribute("type", isPass ? "text" : "password");
    toggle.innerHTML = isPass ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
  });

  form.addEventListener("submit", async (ev)=>{
    ev.preventDefault();
    try{
      await fetchJSON("/api/admin/login", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ senha: senha.value })
      });
      window.location.href = "/admin";
    }catch(e){
      showMsg("danger", e.message);
    }
  });
});
