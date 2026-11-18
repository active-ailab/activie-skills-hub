import {notes,domains,skillDomains,matchesFilters,usageText} from './core.mjs';
const $=id=>document.getElementById(id);
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
const LOCAL=['127.0.0.1','localhost'].includes(location.hostname);
let localToken,localPaths=[];
async function localAPI(path,data){
  if(!localToken)localToken=(await fetch('/api/session').then(r=>r.json())).token;
  const response=await fetch(path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Skills-Token':localToken},body:data?JSON.stringify(data):undefined});
  const result=await response.json();if(!response.ok)throw Error(result.error||'本机读取失败');return result;
}
function applyLocal(data){
  skills=(data.skills||[]).map(s=>({...s,pages:[...(s.pages||[])].sort((a,b)=>Number(!/\/index\.html?$/i.test(a))-Number(!/\/index\.html?$/i.test(b))||a.split('/').length-b.split('/').length||a.localeCompare(b)),learningNotes:notes(s.pages?.length?s.body:usageText(s))}));localPaths=data.paths||[];
  files=new Map(skills.flatMap(s=>s.files).map(path=>[path,{size:0,text:async()=>{const b=await readLocalFile(path);return b.text();},blob:()=>readLocalFile(path)}]));
  $('local-paths').value=localPaths.join('\n');render();
}
async function readLocalFile(path){
  const response=await fetch('/api/file?'+new URLSearchParams({path}),{headers:{'X-Skills-Token':localToken}});if(!response.ok)throw Error('文件读取失败，请重新读取目录');return response.blob();
}
async function scanLocal(){
  if(busy)return;busy=true;$('choose').disabled=true;message('本机脚本正在读取目录…');
  try{const paths=$('local-paths').value.split('\n').map(p=>p.trim()).filter(Boolean);const data=await localAPI('/api/scan',{paths,mode:$('scan-mode').value});applyLocal(data);localSave();message('已读取 '+data.count+' 个文件索引，'+skills.length+' 个项目，用时 '+data.elapsed+' 秒。'+(data.errors.length?'\n'+data.errors.join('\n'):''));}catch(error){message(error.message);}finally{busy=false;$('choose').disabled=false;}
}
let files=new Map(),skills=[],selected,busy=false;
let learned={};try{learned=JSON.parse(localStorage.getItem('skills-browser-learned')||'{}');$('scan-mode').value=localStorage.getItem('skills-browser-mode')||'projects';}catch{}
const urls=new Set();
const blobURL=blob=>{const url=URL.createObjectURL(blob);urls.add(url);return url;};
window.addEventListener('pagehide',()=>urls.forEach(url=>URL.revokeObjectURL(url)));
function message(text){$('message').textContent=text;}
function localSave(){try{localStorage.setItem('skills-browser-learned',JSON.stringify(learned));localStorage.setItem('skills-browser-mode',$('scan-mode').value);}catch{}}
let webFilter='yes', domainFilters=new Set(), domainOverrides={};
try{domainOverrides=JSON.parse(localStorage.getItem('skills-hub-domains')||'{}')||{};}catch{}
function assignedDomains(s){const value=domainOverrides[s.path];return Array.isArray(value)&&value.some(c=>domains.includes(c))?value.filter(c=>domains.includes(c)):skillDomains(s);}
function saveDomains(){try{localStorage.setItem('skills-hub-domains',JSON.stringify(domainOverrides));}catch{}}
function renderFilters(){
  $('web-filters').replaceChildren(...[['all','全部'],['yes','有网页'],['no','无网页']].map(([value,label])=>{
    const button=el('button','filter-option',label+' · '+skills.filter(s=>value==='all'||(value==='yes'?s.pages.length:!s.pages.length)).length);
    button.type='button';button.classList.toggle('selected',webFilter===value);button.setAttribute('aria-pressed',String(webFilter===value));button.onclick=()=>{webFilter=value;render();};return button;
  }));
  $('all-domains').classList.toggle('selected',!domainFilters.size);$('all-domains').setAttribute('aria-pressed',String(!domainFilters.size));
  $('domain-filters').replaceChildren(...domains.map(name=>{
    const label=el('label','domain-option'),input=el('input');input.type='checkbox';input.checked=domainFilters.has(name);
    input.onchange=()=>{input.checked?domainFilters.add(name):domainFilters.delete(name);render();};
    label.append(input,el('span','',name),el('small','',String(skills.filter(s=>matchesFilters(s,{web:webFilter},assignedDomains(s))&&assignedDomains(s).includes(name)).length)));return label;
  }));
}
$('all-domains').onclick=()=>{domainFilters.clear();render();};
function editDomains(s){
  $('domain-choices').replaceChildren(...domains.map(name=>{
    const label=el('label','domain-option'),input=el('input');input.type='checkbox';input.checked=assignedDomains(s).includes(name);
    input.onchange=()=>{const values=[...$('domain-choices').querySelectorAll('input:checked')].map(n=>n.value);domainOverrides[s.path]=values.length?values:['其他分类'];saveDomains();render();editDomains(s);};
    input.value=name;label.append(input,el('span','',name));return label;
  }));
  $('domain-status').textContent=Array.isArray(domainOverrides[s.path])?'已保存手动分类':'自动分类，可手动调整';
  $('reset-domains').onclick=()=>{delete domainOverrides[s.path];saveDomains();render();editDomains(s);};
}
function category(s){return s.pages.length?'有网页':'非网页';}
function render(){
  renderFilters();
  const visible=skills.filter(s=>matchesFilters(s,{query:$('search').value,web:webFilter,categories:[...domainFilters]},assignedDomains(s)));
  $('items').replaceChildren();$('count').textContent=visible.length+' 个 Skills';$('learned-count').textContent='已学习 '+skills.filter(s=>learned[s.path]).length+' 个';
  $('empty').hidden=visible.length>0;
  if(!visible.length){$('empty').replaceChildren(el('h2','',skills.length?'没有匹配的 Skill':'从一个 Skills 文件夹开始'),el('p','',skills.length?'试试其他关键词或分类。':'选择文件夹后，说明和工具会出现在这里。'));}
  for(const [i,s] of visible.entries()){
    const card=el('article','card'),top=el('div','card-top');top.append(el('span','icon',['◈','⌘','✳','▤','⚙','⌁'][i%6]),el('span','chinese-name',s.chineseName),el('span','badge',learned[s.path]?'✓ 已学习':category(s)));
    card.append(top,el('h3','',s.name),el('span','category-badge',assignedDomains(s).join(' · ')),el('p','',s.description));
    const foot=el('div','card-foot'),details=el('button','detail-link','查看详情');details.onclick=()=>show(s);foot.append(details);
    if(s.pages.length){const preview=el('button','page-link','打开运行 ↗');preview.onclick=()=>previewPage(s.pages[0]);foot.append(preview);}
    card.append(foot);card.onclick=e=>{if(!e.target.closest('button,a'))show(s);};$('items').append(card);
  }
  const roots=[...new Set([...files.keys()].map(p=>p.split('/')[0]))];
  if(LOCAL){$('folder-summary').textContent='本机脚本读取 · '+skills.length+' 个项目 · 源文件按需读取，不复制整个目录';return;}
  $('folder-summary').textContent=files.size?roots.join('、')+' · '+files.size+' 个文件 · 文件变更后可重新选择文件夹更新':'无需 BAT 或 Python。内容仅在当前浏览器处理；下次打开自动恢复保存的资料。';
}
function tab(which){for(const name of ['guide','learning','files'])$(name+'-panel').hidden=name!==which;for(const [id,name] of [['guide-tab','guide'],['notes-tab','learning'],['files-tab','files']])$(id).classList.toggle('selected',which===name);}
function show(s){selected=s;editDomains(s);$('detail-name').textContent=s.chineseName;$('detail-description').textContent=s.description;$('detail-path').textContent=s.path;renderGuide(s);
  $('page-links').replaceChildren();if(s.pages.length){$('page-links').append(el('h3','','HTML 网页'));for(const path of s.pages){const button=el('button','page-link',path.slice(s.path.length+1)+' ↗');button.onclick=()=>previewPage(path);$('page-links').append(button);} $('page-links').append(el('p','hint','点击网页自动启动项目；首次运行会准备依赖，启动失败会显示日志位置。'));}
  $('file-select').replaceChildren(...s.files.map(path=>{const option=el('option','',path.slice(s.path.length+1));option.value=path;return option;}));
  tab('guide');$('detail').showModal();
}
function renderGuide(s){
  const target=$('guide');target.replaceChildren();
  if(s.pages.length){target.append(el('pre','',s.body));return;}
  const g=s.usageGuide;
  if(g?.status==='reviewed'){
    target.append(el('p','notice',g.message));
    for(const [title,text] of [['具体是干嘛的',g.purpose],['什么时候用',g.when],['使用前准备',g.inputs]])target.append(el('h3','',title),el('p','',text));
    target.append(el('h3','','怎么使用'));const list=el('ol');for(const step of g.steps)list.append(el('li','',step));target.append(list);
    for(const [title,text] of [['会得到什么',g.outputs],['给 Agent 的任务示例',g.example],['使用边界',g.limits]])target.append(el('h3','',title),el('p','',text));
  }else target.append(el('p','notice',usageText(s)));
  target.append(el('h3','','核对来源'));
  for(const path of s.sources){const button=el('button','page-link',path.slice(s.path.length+1));button.onclick=()=>{$('file-select').value=path;tab('files');fileContent();};target.append(button);}
}
function learn(){
  $('learning-notes').replaceChildren();for(const note of (selected.pages.length?selected.learningNotes:[{title:'使用指南',body:usageText(selected)}])){const section=el('section','note-section');section.append(el('h3','',note.title),el('pre','',note.body));$('learning-notes').append(section);}
  learned[selected.path]=new Date().toISOString();localSave();render();tab('learning');
}
async function copy(text,button){try{await navigator.clipboard.writeText(text);const old=button.textContent;button.textContent='已复制';setTimeout(()=>button.textContent=old,1500);}catch{message('剪贴板不可用，请从说明中选中并复制内容。');}}
function download(blob,name){const url=blobURL(blob),a=el('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>{URL.revokeObjectURL(url);urls.delete(url);},30000);}
async function fileContent(){const path=$('file-select').value,file=files.get(path);if(!file)return;const target=path;
  let text='该文件为二进制文件，请下载查看。';if(/\.(md|txt|py|sh|js|mjs|json|html?|css|toml|ya?ml|xml|csv|rst|svg)$/i.test(path)){text=file.size>1024*1024?'文件较大，请下载查看。':await file.text();}
  if($('file-select').value===target)$('file-content').textContent=text;
}
async function previewPage(path){
  const popup=window.open('about:blank','_blank');if(!popup){message('请允许弹出窗口后重试。');return;}
  popup.opener=null;popup.document.title='启动项目';popup.document.body.textContent='正在启动项目，首次安装依赖可能需要几分钟…';
  try{
    const result=await localAPI('/api/preview',{path});
    if(!popup.closed)popup.location.replace(result.url);
  }catch(error){if(!popup.closed)popup.document.body.textContent='启动失败：'+error.message;}
}
$('choose').onclick=scanLocal;
$('clear').onclick=async()=>{if(busy)return;if(!confirm('清除这个浏览器里保存的文件和学习记录？原始文件夹不会被修改。'))return;
  try{await localAPI('/api/clear',{});}catch(error){message('清除失败：'+error.message);return;}files=new Map();skills=[];learned={};localSave();urls.forEach(url=>URL.revokeObjectURL(url));urls.clear();$('detail').close();render();message('本地资料已清除。');
};
$('search').oninput=render;
$('scan-mode').onchange=()=>{if(LOCAL)scanLocal();};
for(const mode of ['grid','list'])$(mode).onclick=()=>{$('items').classList.toggle('list',mode==='list');$('grid').classList.toggle('selected',mode==='grid');$('list').classList.toggle('selected',mode==='list');};
$('close').onclick=()=>$('detail').close();$('guide-tab').onclick=()=>tab('guide');$('notes-tab').onclick=learn;$('learn').onclick=learn;
$('files-tab').onclick=()=>{tab('files');fileContent();};$('file-select').onchange=fileContent;
$('download-file').onclick=async()=>{const path=$('file-select').value;if(files.has(path)){try{download(LOCAL?await readLocalFile(path):files.get(path),path.split('/').pop());}catch(error){message(error.message);}}};
$('download').onclick=()=>download(new Blob([usageText(selected)],{type:'text/markdown;charset=utf-8'}),selected.name+'-说明.md');
$('copy-notes').onclick=()=>copy(selected.pages.length?selected.learningNotes.map(n=>n.title+'\n\n'+n.body).join('\n\n'):usageText(selected),$('copy-notes'));
$('copy-prompt').onclick=()=>copy(selected.pages.length?'请学习并使用这个 Skill：'+selected.name+'\n\n'+selected.body+'\n\n我的任务是：[填写具体任务]':'请先读取项目说明：\n'+selected.sources.join('\n')+'\n\n'+(selected.usageGuide?.status==='reviewed'?selected.usageGuide.example:'我的任务是：[请先明确具体任务并核对项目能力]'),$('copy-prompt'));
async function init(){
  if(LOCAL){
    $('local-input').hidden=false;$('choose').textContent='读取目录并学习 ↗';
    $('local-status').textContent='● 本机脚本读取';
    try{const data=await localAPI('/api/workspace');applyLocal(data);if(data.mode)$('scan-mode').value=data.mode;message(skills.length?'已恢复上次读取结果，正在核对目录变化…':'填写本机目录后点击读取。支持 WSL 路径和 Windows 路径。');if(localPaths.length)scanLocal();}
    catch(error){message('本机服务连接失败：'+error.message);}return;
  }
  // Hosted page only wakes the registered local handler; never enumerate browser files.
  $('choose').hidden=true;$('clear').hidden=true;$('local-open').hidden=false;$('local-download').hidden=false;
  $('local-status').textContent='● 本机脚本模式';
  message('点击“打开本机工作台”，允许浏览器唤起本机读取脚本。首次使用请下载启动包，按包内 README 完成一次安装，再点击打开。');
  $('folder-summary').textContent='本机脚本直接读取源文件，不再复制文件夹到浏览器。';
  try{location.href='skills-hub://open';}catch{}
}
render();init();
