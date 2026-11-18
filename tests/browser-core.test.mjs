import test from 'node:test';
import assert from 'node:assert/strict';
import {buildSkills,notes,resolvePath,usable} from '../static/core.mjs';
const file=text=>new Blob([text]);
test('groups projects, merges nested skills, and excludes dependency folders',async()=>{
 const files=new Map([
 ['Library/tool/README.md',file('# 中文工具\n\n用于生成数据。')],
 ['Library/tool/one/SKILL.md',file('# One\n步骤一')],
 ['Library/tool/two/SKILL.md',file('# Two\n步骤二')],
 ['Library/tool/index.html',file('<h1>Tool</h1>')],
 ['Library/.git/SKILL.md',file('# Ignore')],
 ['Library/other/scripts/run.py',file('print(1)')],
 ]);
 const result=await buildSkills(files);
 assert.equal(result.length,2);
 const tool=result.find(s=>s.name==='tool');
 assert.equal(tool.chineseName,'中文工具');assert.equal(tool.skillCount,2);assert.equal(tool.pages.length,1);
 assert.match(tool.body,/步骤一/);assert.match(tool.body,/步骤二/);
 const individual=await buildSkills(files,'skills');assert.equal(individual.length,2);
});
test('single selected project stays together and README is optional',async()=>{
 const result=await buildSkills(new Map([['MyTool/SKILL.md',file('---\nname: MyTool\ndescription: 示例能力\n---\n# 使用\n执行步骤')],['MyTool/scripts/a.py',file('pass')]]));
 assert.equal(result.length,1);assert.equal(result[0].description,'示例能力');assert.equal(result[0].scripts.length,1);
 assert.equal((await buildSkills(new Map([['Blank/index.html',file('hi')]])))[0].pages.length,1);
});
test('notes preserve fenced headings and all original sections',()=>{
 const result=notes('# 使用\n第一步\n```sh\n# keep\n```\n## 输出\n内容');
 assert.equal(result.length,2);assert.match(result[0].body,/# keep/);assert.equal(result[1].title,'输出');
});
test('asset paths resolve relative folders and skip only known internal directories',()=>{
 assert.equal(resolvePath('Root/web/index.html','../assets/a.png'),'Root/assets/a.png');
 assert.equal(usable('Root/node_modules/a.js'),false);assert.equal(usable('Root/.state/cache'),false);assert.equal(usable('Root/scripts/a.py'),true);
});

test('domain classification supports multiple domains and an other fallback',async()=>{
 const {skillDomains}=await import('../static/core.mjs');
 assert.deepEqual(skillDomains({name:'sport-health',chineseName:'运动健康开发'}),['运动开发','健康开发']);
 assert.deepEqual(skillDomains({name:'unclassified'}),['其他分类']);
 assert.deepEqual(skillDomains({name:'nas-build-pipeline',chineseName:'固件发布'}),['项目管理']);
});
test('web status combines with any selected domain and text search',async()=>{
 const {matchesFilters}=await import('../static/core.mjs');
 const skill={name:'sport-health',chineseName:'运动健康工具',path:'/tools/sport',pages:['index.html'],body:'示例'};
 assert.equal(matchesFilters(skill,{web:'yes',categories:['健康开发','办公提效'],query:'运动'}),true);
 assert.equal(matchesFilters(skill,{web:'no',categories:['健康开发']}),false);
 assert.equal(matchesFilters(skill,{web:'all',categories:['办公提效']}),false);
 assert.equal(matchesFilters(skill,{web:'all',categories:[]}),true);
 assert.equal(matchesFilters(skill,{categories:['办公提效']},['办公提效']),true);
 assert.equal(matchesFilters({...skill,pages:[]},{web:'no'}),true);
});

test('non-web guides and exports explain use without dumping README',async()=>{
 const {usageText}=await import('../static/core.mjs');
 const skill={pages:[],body:'RAW README',usageGuide:{status:'reviewed',purpose:'解析现场',when:'死机时',inputs:'ELF',steps:['提供文件','核对版本'],outputs:'报告',example:'请分析这份现场',limits:'版本须匹配',message:'按说明整理'}};
 const text=usageText(skill);assert.match(text,/1\. 提供文件/);assert.match(text,/会得到什么/);assert.doesNotMatch(text,/RAW README/);
 assert.doesNotMatch(usageText({...skill,usageGuide:{status:'stale',message:'待复核'}}),/提供文件/);
 assert.match(usageText({...skill,usageGuide:undefined}),/待整理/);
 assert.equal(usageText({...skill,pages:['index.html']}),'RAW README');
});
