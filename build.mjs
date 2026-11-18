import {execFileSync} from 'node:child_process';
import {cp,mkdir,rm} from 'node:fs/promises';
const root=new URL('./',import.meta.url);
await rm(new URL('dist/',root),{recursive:true,force:true});
await mkdir(new URL('dist/',root),{recursive:true});
for(const name of ['index.html','app.js','core.mjs','style.css','chinese_names.json'])await cp(new URL('static/'+name,root),new URL('dist/'+name,root));
execFileSync('python3',[new URL('package_local.py',root).pathname],{cwd:root});
console.log('Built website and portable local launcher in dist/');
