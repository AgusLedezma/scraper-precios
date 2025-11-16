(function(){
  function render(prices){
    const container = document.getElementById('results');
    if(!container) return;
    container.innerHTML='';
    if(!prices || prices.length===0){
      container.innerHTML = '<div class="col-12"><div class="alert alert-secondary">Sin resultados</div></div>';
      return;
    }
    const frag = document.createDocumentFragment();
    prices.forEach(p=>{
      const col = document.createElement('div');
      col.className = 'col-12 col-md-6 col-lg-4';
      col.innerHTML = `
        <div class="card price-card h-100 shadow-sm">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div class="card-price">${formatCurrency(p.value, p.currency)}</div>
              <span class="badge bg-light text-dark">${p.currency || '—'}</span>
            </div>
            <div class="context">${escapeHtml((p.context||'').slice(0,160))}</div>
            <div class="mt-3 small text-muted code-small">Raw: ${escapeHtml(p.raw||'')}</div>
          </div>
        </div>`;
      frag.appendChild(col);
    });
    container.appendChild(frag);
  }

  function escapeHtml(str){
    return String(str).replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[s]));
  }

  function formatCurrency(value, currency){
    if(typeof value !== 'number') return String(value||'');
    try{
      return new Intl.NumberFormat('es-ES', { style: currency? 'currency':'decimal', currency: currency||'USD', maximumFractionDigits: 2 }).format(value);
    }catch{
      return new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 }).format(value) + (currency? ` ${currency}`:'');
    }
  }

  function sortPrices(prices, by, dir){
    const m = dir==='desc' ? -1 : 1;
    return [...prices].sort((a,b)=>{
      if(by==='currency'){
        return (String(a.currency||'').localeCompare(String(b.currency||'')))*m;
      }
      return ((a.value||0)-(b.value||0))*m;
    });
  }

  function filterPrices(prices, q){
    if(!q) return prices;
    const s = q.toLowerCase();
    return prices.filter(p=>
      String(p.context||'').toLowerCase().includes(s) ||
      String(p.currency||'').toLowerCase().includes(s) ||
      String(p.value||'').toLowerCase().includes(s)
    );
  }

  function setup(){
    const data = (window.__DATA__ && window.__DATA__.prices) || [];
    const filterInput = document.getElementById('filterText');
    const sortBy = document.getElementById('sortBy');
    const sortDir = document.getElementById('sortDir');
    const btnExport = document.getElementById('btnExport');
    const btnEmail = document.getElementById('btnEmail');
    const emailTo = document.getElementById('email_to');
    const emailSubject = document.getElementById('email_subject');

    function update(){
      const f = filterInput? filterInput.value.trim():'';
      const by = sortBy? sortBy.value : 'value';
      const dir = sortDir? sortDir.value : 'asc';
      let out = filterPrices(data, f);
      out = sortPrices(out, by, dir);
      render(out);
    }

    if(filterInput){ filterInput.addEventListener('input', update); }
    if(sortBy){ sortBy.addEventListener('change', update); }
    if(sortDir){ sortDir.addEventListener('change', update); }
    if(btnExport){
      btnExport.addEventListener('click', ()=>{
        const blob = new Blob([JSON.stringify({ prices: data }, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'resultados_precios.json'; a.click();
        URL.revokeObjectURL(url);
      });
    }

    if(btnEmail){
      btnEmail.addEventListener('click', async ()=>{
        const to = emailTo ? emailTo.value.trim() : '';
        const subject = emailSubject ? emailSubject.value.trim() : 'Reporte de precios';
        if(!to){
          alert('Ingresa un correo destino');
          return;
        }
        const payload = {
          to,
          subject,
          meta: window.__META__ || {},
          result: { prices: data }
        };
        try{
          const res = await fetch('/email', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
          const j = await res.json();
          if(j && j.ok){
            alert('Reporte enviado correctamente.');
          } else {
            throw new Error(j && j.error || 'Error desconocido');
          }
        }catch(err){
          alert('Error al enviar email: ' + err.message);
        }
      });
    }

    render(sortPrices(data, 'value', 'asc'));
  }

  document.addEventListener('DOMContentLoaded', setup);
})();
