// Use TypeScript's compiler in-process; no native esbuild child process required.
import {build} from 'vite';
import ts from 'typescript';
await build({configFile:false,resolve:{preserveSymlinks:true},esbuild:false,build:{minify:false},plugins:[{
 name:'typescript-transpile',enforce:'pre',
 transform(code,id){
  if(/\.[cm]?jsx?$/.test(id))code=code.replaceAll('process.env.NODE_ENV','"production"');
  if(/\.tsx?$/.test(id)&&!id.includes('node_modules'))code=ts.transpileModule(code,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
  return {code,map:null};
 }
}]});
