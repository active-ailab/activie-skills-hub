const ignored = new Set(['.git','.repo','node_modules','__pycache__','.venv','.venvs','.state','vendor']);
export function usable(path) { return !path.split('/').some(p=>ignored.has(p)); }
export function notes(body) {
  const result=[];let title='概览',lines=[],fenced=false;
  const flush=()=>{if(lines.join('\n').trim())result.push({title,body:lines.join('\n').trim()});lines=[];};
  for(const line of body.split('\n')){
    if(/^\s*```/.test(line))fenced=!fenced;
    const match=!fenced&&line.match(/^#{1,6}\s+(.+)/);
    if(match){flush();title=match[1];}else lines.push(line);
  }
  flush();return result;
}
export function description(body) {
  const front=body.match(/^---\s*\n[\s\S]*?\bdescription:\s*([^\n]+)/);
  if(front)return front[1].replace(/^["']|["']$/g,'');
  return body.split('\n').map(s=>s.trim()).find(s=>s&&!/^(#|---|```|name:|description:|[!\[])/.test(s))?.slice(0,240)||'打开查看说明与文件。';
}
export async function buildSkills(files,mode='projects',labels={}) {
  const paths=[...files.keys()].filter(usable).sort();
  const groups=new Map();
  if(mode==='skills'){
    for(const path of paths.filter(p=>/(^|\/)SKILL\.md$/i.test(p))){const root=path.slice(0,-9).replace(/\/$/,'');groups.set(root,paths.filter(p=>p.startsWith(root+'/')));}
  }else{
    const roots=new Set(paths.map(p=>p.split('/')[0]));
    for(const root of roots){
      const entries=paths.filter(p=>p.startsWith(root+'/'));
      if(entries.some(p=>/^(SKILL|README)\.md$/i.test(p.slice(root.length+1))))groups.set(root,entries);
      else {
        const children=new Set(entries.map(p=>p.slice(root.length+1).split('/')[0]));
        for(const child of children){const prefix=root+'/'+child;const nested=entries.filter(p=>p.startsWith(prefix+'/'));if(nested.length)groups.set(prefix,nested);}
        if(![...groups.keys()].some(p=>p.startsWith(root+'/')))groups.set(root,entries);
      }
    }
  }
  const skills=[];
  for(const [root,entries] of groups){
    const sources=entries.filter(p=>/(^|\/)(SKILL|README)\.md$/i.test(p)).sort((a,b)=>a.split('/').length-b.split('/').length || a.localeCompare(b));
    const texts=await Promise.all(sources.map(async p=>({path:p,text:await files.get(p).text()})));
    const readme=texts.find(x=>/\/README\.md$/i.test(x.path));
    const primary=readme||texts[0];const name=root.split('/').pop();
    const heading=primary?.text.match(/^#\s+(.+)$/m)?.[1]?.replace(/[*`]/g,'');
    const chineseName=heading&&/[\u4e00-\u9fff]/.test(heading)&&heading.length<=40?heading:labels[name]||name;
    const body=texts.map(x=>'## 来源：'+x.path.slice(root.length+1)+'\n\n'+x.text).join('\n\n')||'此项目没有 README.md 或 SKILL.md。可以查看文件列表和 HTML 网页。';
    const pages=entries.filter(p=>/\.html?$/i.test(p));
    const scripts=entries.filter(p=>/\.(py|sh|js|mjs)$/i.test(p));
    skills.push({id:root,path:root,name,chineseName,description:description(primary?.text||''),body,sources,pages,scripts,files:entries,learningNotes:notes(body),kind:'project',skillCount:sources.filter(p=>/\/SKILL\.md$/i.test(p)).length});
  }
  return skills;
}
export function resolvePath(base,relative){
  const out=base.split('/');out.pop();
  for(const piece of relative.split('/')){if(piece==='..')out.pop();else if(piece&&piece!=='.')out.push(piece);}
  return out.join('/');
}

export const domains = ['运动开发','健康开发','项目管理','办公提效','其他分类'];
export function skillDomains(skill) {
  const text = [skill.name, skill.chineseName, skill.description].join(' ').toLowerCase();
  const rules = [
    /运动|跑步|骑行|游泳|徒步|健身|训练|sport|running|cycling|hike|gpx|lthr|workout|fitness/,
    /健康|睡眠|心率|血氧|压力|health|sleep|heart|spo2|stress/,
    /项目管理|需求管理|任务管理|缺陷|迭代|发布|固件|分支|流水线|jira|jenkins|pipeline|release|firmware/,
    /办公|提效|文档|会议|日历|审批|邮箱|飞书|报表|office|productivity|document|meeting|calendar|lark|feishu/,
  ];
  const found = domains.slice(0,4).filter((_,i)=>rules[i].test(text));
  return found.length ? found : ['其他分类'];
}
export function matchesFilters(skill, {query='', web='all', categories=[]}={}, assigned=skillDomains(skill)) {
  return (web==='all'||(web==='yes'?Boolean(skill.pages.length):!skill.pages.length))
    && (!categories.length||categories.some(c=>assigned.includes(c)))
    && [skill.name,skill.chineseName,skill.path,skill.body].join(' ').toLowerCase().includes(query.toLowerCase());
}

export function usageText(skill) {
  if(skill.pages.length)return skill.body;
  const g=skill.usageGuide;
  if(g?.status!=='reviewed')return g?.message||'使用指南待整理，请从项目文件核对用途与使用入口。';
  return [g.purpose,'什么时候用\n'+g.when,'使用前准备\n'+g.inputs,'怎么使用\n'+g.steps.map((x,i)=>(i+1)+'. '+x).join('\n'),'会得到什么\n'+g.outputs,'给 Agent 的任务示例\n'+g.example,'使用边界\n'+g.limits,g.message].join('\n\n');
}
