(()=>{
 const header=document.querySelector('.global-header');
 if(!header)return;
 const theme=header.querySelector('.gh-theme'),menu=header.querySelector('.gh-menu'),nav=header.querySelector('.gh-nav');
 function syncTheme(){
  const dark=document.documentElement.dataset.theme==='dark';
  theme.setAttribute('aria-pressed',String(dark));
  theme.setAttribute('aria-label',dark?'Switch to light theme':'Switch to dark theme');
  theme.querySelector('.theme-label').textContent=dark?'Light':'Dark';
  const meta=document.querySelector('meta[name="theme-color"]');
  if(meta)meta.content=dark?'#1b1b1a':'#f5f5f2';
 }
 try{document.documentElement.dataset.theme=localStorage.getItem('gantry-theme')==='dark'?'dark':'light';}catch{}
 syncTheme();
 theme.addEventListener('click',()=>{
  const next=document.documentElement.dataset.theme==='dark'?'light':'dark';
  document.documentElement.dataset.theme=next;
  try{localStorage.setItem('gantry-theme',next);}catch{}
  syncTheme();
 });
 function setMenu(open){header.classList.toggle('is-open',open);menu.setAttribute('aria-expanded',String(open));menu.textContent=open?'Close':'Menu';}
 menu.addEventListener('click',()=>setMenu(menu.getAttribute('aria-expanded')!=='true'));
 nav.addEventListener('click',e=>{if(e.target.closest('a'))setMenu(false);});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&menu.getAttribute('aria-expanded')==='true'){setMenu(false);menu.focus();}});
 document.addEventListener('click',e=>{if(!header.contains(e.target))setMenu(false);});
 matchMedia('(max-width:1000px)').addEventListener('change',()=>setMenu(false));
 const section=location.pathname.startsWith('/news/')?'news':location.pathname.startsWith('/demo/')?'demo':'';
 if(section)nav.querySelector(`[data-section="${section}"]`)?.setAttribute('aria-current','page');
})();
