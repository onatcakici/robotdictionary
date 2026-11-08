(function(){
  var data=null, loading=null;
  function load(){ if(data) return Promise.resolve(data); if(loading) return loading;
    loading=fetch('/assets/search.json').then(function(r){return r.json()}).then(function(d){data=d;return d}); return loading; }
  function norm(s){return (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z0-9 ]+/g,' ')}
  function rank(q,d){ var out=[]; var qs=norm(q).trim(); if(!qs) return out; var parts=qs.split(/\s+/);
    for(var i=0;i<d.length;i++){ var e=d[i]; var name=norm(e[1]); var hay=name+' '+norm(e[2])+' '+norm(e[3])+' '+norm(e[4]);
      var ok=true; for(var j=0;j<parts.length;j++){ if(hay.indexOf(parts[j])<0){ok=false;break} } if(!ok) continue;
      var s = name===qs?0 : name.indexOf(qs)===0?1 : name.indexOf(qs)>=0?2 : 3; out.push([s,name.length,e]); }
    out.sort(function(a,b){return a[0]-b[0]||a[1]-b[1]}); return out.slice(0,9).map(function(x){return x[2]}); }
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  document.querySelectorAll('[data-find]').forEach(function(box){
    var input=box.querySelector('input'), list=box.querySelector('.hits'), cur=-1;
    function show(items){ cur=-1; if(!items.length){ list.innerHTML=input.value.trim()?'<li><a href="/a-z/">No entry by that name. Browse A to Z</a></li>':''; list.hidden=!input.value.trim(); return; }
      list.innerHTML=items.map(function(e){return '<li><a href="/'+e[0]+'/">'+esc(e[1])+'<span>'+esc([e[3],e[4],e[5]].filter(Boolean).join(', '))+'</span></a></li>'}).join(''); list.hidden=false; }
    input.addEventListener('focus',load);
    input.addEventListener('input',function(){ load().then(function(d){ show(rank(input.value,d)) }) });
    input.addEventListener('keydown',function(ev){ var links=list.querySelectorAll('a'); if(!links.length) return;
      if(ev.key==='ArrowDown'||ev.key==='ArrowUp'){ ev.preventDefault(); cur=(cur+(ev.key==='ArrowDown'?1:-1)+links.length)%links.length;
        links.forEach(function(a,i){a.classList.toggle('on',i===cur)}); }
      else if(ev.key==='Enter'){ ev.preventDefault(); (links[cur]||links[0]).click(); }
      else if(ev.key==='Escape'){ list.hidden=true; } });
    document.addEventListener('click',function(ev){ if(!box.contains(ev.target)) list.hidden=true; });
  });
  document.addEventListener('keydown',function(ev){ if(ev.key==='/'&&!/input|textarea/i.test(document.activeElement.tagName)){ var i=document.querySelector('[data-find] input'); if(i){ev.preventDefault();i.focus();} } });
  document.querySelectorAll('[data-copy]').forEach(function(b){ b.addEventListener('click',function(){ var t=document.getElementById(b.getAttribute('data-copy')).innerText;
    (navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(function(){ b.textContent='Copied'; setTimeout(function(){b.textContent='Copy'},1600) }).catch(function(){}) }) });
})();
