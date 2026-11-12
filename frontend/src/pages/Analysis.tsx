import {useEffect,useMemo,useRef,useState} from 'react';
import type {Survey,Transect,Run,User} from '../types/domain';
import {researchApi} from '../api/research';
import {PageTitle} from '../components/common/PageTitle';
import {RunTable} from '../components/RunTable';
import {Notice} from '../components/common/Notice';
import {Badge} from '../components/common/Badge';
import {useAsync} from '../hooks/useAsync';

type PairPreview={reference:string;status:'eligible'|'missing_spring'|'missing_autumn'|'empty'|'insufficient';springN:number|null;autumnN:number|null;reason:string};

export function AnalysisPage({surveys,transects,runs,user,reload,select}:{surveys:Survey[];transects:Transect[];runs:Run[];user:User;reload:()=>Promise<any>;select:(r:Run)=>void}){
 // Surveys arrive after mount. Initialise once: spring = first period, autumn = last
 // distinct period. Later user choices are left alone so the validation message can show.
 const initial=useMemo(()=>{const ids=surveys.map(s=>s.id),spring=ids.length?ids[0]:0;return {spring,autumn:ids.length>1?ids[ids.length-1]:spring}},[surveys]);
 const [mode,setMode]=useState<'single'|'paired'>('single');
 const [survey,setSurvey]=useState(0),[selected,setSelected]=useState<number[]>([]);
 const [name,setName]=useState('秋季共同采样努力复核'),[m,setM]=useState(100),[bootstrap,setBootstrap]=useState(200),[seed,setSeed]=useState(20261114);
 const [springId,setSpringId]=useState(0),[autumnId,setAutumnId]=useState(0),picked=useRef(false);
 useEffect(()=>{if(picked.current||!surveys.length)return;setSpringId(initial.spring);setAutumnId(initial.autumn);picked.current=true},[surveys,initial]);
 const [pairedName,setPairedName]=useState('春秋同编号稀释期望差'),[pairedM,setPairedM]=useState(100),[pairedBootstrap,setPairedBootstrap]=useState(200),[pairedSeed,setPairedSeed]=useState(20261114);
 const active=survey||surveys.at(-1)?.id,items=transects.filter(t=>t.survey_id===active),chosen=selected.length?selected:items.map(t=>t.id),nonempty=items.filter(t=>chosen.includes(t.id)&&t.n>0),limit=nonempty.length?Math.min(...nonempty.map(t=>t.n)):0;
 const {busy,error,message,act}=useAsync();
 const springItems=transects.filter(t=>t.survey_id===springId),autumnItems=transects.filter(t=>t.survey_id===autumnId);
 const preview=useMemo<PairPreview[]>(()=>{
  const refs=[...new Set([...springItems,...autumnItems].map(t=>t.reference))].sort();
  return refs.map(reference=>{
   const spring=springItems.find(t=>t.reference===reference),autumn=autumnItems.find(t=>t.reference===reference);
   if(!spring)return {reference,status:'missing_spring',springN:null,autumnN:autumn?.n??0,reason:'秋季有记录、春季缺期；不进入比较'};
   if(!autumn)return {reference,status:'missing_autumn',springN:spring.n,autumnN:null,reason:'春季有记录、秋季缺期；不进入比较'};
   if(!spring.n||!autumn.n)return {reference,status:'empty',springN:spring.n,autumnN:autumn.n,reason:'存在N=0空样线；稀释期望不定义，不进入比较'};
   if(spring.n<pairedM||autumn.n<pairedM)return {reference,status:'insufficient',springN:spring.n,autumnN:autumn.n,reason:`N 小于共同m=${pairedM}；保留明细但不进入比较`};
   return {reference,status:'eligible',springN:spring.n,autumnN:autumn.n,reason:''};
  });
 },[springItems,autumnItems,pairedM]);
 const counts={eligible:preview.filter(p=>p.status==='eligible').length,missing:preview.filter(p=>p.status.startsWith('missing')).length,empty:preview.filter(p=>p.status==='empty').length,insufficient:preview.filter(p=>p.status==='insufficient').length};
 const bothNonempty=preview.filter(p=>p.springN&&p.autumnN),pairedLimit=bothNonempty.length?Math.min(...bothNonempty.map(p=>Math.min(p.springN!,p.autumnN!))):0;
 const sameSurvey=springId===autumnId;
 return <>
  <PageTitle index="03 / COMMON EFFORT" title="先约定共同m，再展开比较。" description="单期研究比较同期样线；春秋配对研究按样线编号对齐同一物理样线，在共同m下计算秋减春稀释期望差。缺期、空线与采样量不足逐条说明，不静默丢弃。"/>
  <div className="mode-switch">
   <button className={mode==='single'?'active':''} onClick={()=>setMode('single')}>单期共同量研究</button>
   <button className={mode==='paired'?'active':''} onClick={()=>setMode('paired')}>春秋配对 · 秋减春</button>
  </div>
  {mode==='single'?<div className="analysis-grid">
   <form className="editor" onSubmit={e=>{e.preventDefault();act(async()=>{const r=await researchApi.queue({survey_id:active,name,transect_ids:chosen,m,bootstrap,seed});await reload();select(r)},'研究已进入队列')}}>
    <h2>共同采样量研究</h2>
    <fieldset disabled={busy||user.role==='viewer'}>
     <label>研究名称<input value={name} onChange={e=>setName(e.target.value)} required maxLength={100}/></label>
     <label>调查期<select value={active||''} onChange={e=>{setSurvey(+e.target.value);setSelected([])}}>{surveys.map(s=><option key={s.id} value={s.id}>{s.name} / {s.survey_date}</option>)}</select></label>
     <label>选择样线 / 当前非空最小N={limit}</label>
     <div className="transect-checks">{items.map(t=><label key={t.id}><input type="checkbox" checked={chosen.includes(t.id)} onChange={()=>{const next=chosen.includes(t.id)?chosen.filter(x=>x!==t.id):[...chosen,t.id];if(next.length)setSelected(next)}}/>{t.reference}<span>N={t.n}{t.n===0?' · 空':''}</span></label>)}</div>
     <div className="form-grid">
      <label>共同个体量 m<input type="number" value={m} onChange={e=>setM(+e.target.value)} min="0" max="100000" step="1" required/></label>
      <label>bootstrap次数<input type="number" value={bootstrap} onChange={e=>setBootstrap(+e.target.value)} min="50" max="1000" step="1" required/></label>
      <label>固定seed<input type="number" value={seed} onChange={e=>setSeed(+e.target.value)} min="0" max="2147483647" step="1" required/></label>
     </div>
     <button className="primary" disabled={!items.length}>{busy?'正在提交…':'提交共同量研究 →'}</button>
    </fieldset>
    {user.role==='viewer'&&<p>观察记录员可阅读；提交研究需要研究员权限。</p>}
    <Notice error={error} message={message}/>
   </form>
   <aside className="method-notes"><small>METHOD / 保留三个尺度</small><h2>期望、描述、<br/>区间，各有用途。</h2><ol><li><b>稀释期望 · 共同m</b><p>不放回抽取m个体时，期望见到多少物种。相同m的期望才用于横向比较。</p></li><li><b>Shannon / Simpson · 原N</b><p>按原始计数组成描述。H用ln，Simpson用1−Σp²，不把不同努力量下的值直接排名。</p></li><li><b>条件bootstrap · 原N</b><p>按已观测组成做多项重采样，给指标与共同m期望的条件区间；不覆盖未发现物种、空间相关和漏检。</p></li></ol><p className="fine">观察性差异不是保护措施因果效果。样线协议、个体识别与漏检仍需田野复核。</p></aside>
  </div>:<div className="analysis-grid">
   <form className="editor" onSubmit={e=>{e.preventDefault();act(async()=>{const r=await researchApi.queuePaired({name:pairedName,spring_survey_id:springId,autumn_survey_id:autumnId,m:pairedM,bootstrap:pairedBootstrap,seed:pairedSeed});await reload();select(r)},'配对研究已进入队列')}}>
    <h2>春秋同编号配对研究</h2>
    <fieldset disabled={busy||user.role==='viewer'}>
     <label>研究名称<input value={pairedName} onChange={e=>setPairedName(e.target.value)} required maxLength={100}/></label>
     <div className="form-grid">
      <label>春季调查期<select value={springId||''} onChange={e=>setSpringId(+e.target.value)}>{surveys.map(s=><option key={s.id} value={s.id}>{s.name} / {s.survey_date}</option>)}</select></label>
      <label>秋季调查期<select value={autumnId||''} onChange={e=>setAutumnId(+e.target.value)}>{surveys.map(s=><option key={s.id} value={s.id}>{s.name} / {s.survey_date}</option>)}</select></label>
      <label>共同个体量 m<input type="number" value={pairedM} onChange={e=>setPairedM(+e.target.value)} min="0" max="100000" step="1" required/></label>
      <label>bootstrap次数<input type="number" value={pairedBootstrap} onChange={e=>setPairedBootstrap(+e.target.value)} min="50" max="1000" step="1" required/></label>
      <label>固定seed<input type="number" value={pairedSeed} onChange={e=>setPairedSeed(+e.target.value)} min="0" max="2147483647" step="1" required/></label>
     </div>
     {sameSurvey?<Notice error="春、秋必须选择两个不同调查期"/>:null}
     <div className="pair-preview">
      <div className="section-title"><h2>配对预检 / 按编号对齐</h2><small>两侧非空最小N={pairedLimit}；共同m={pairedM}</small></div>
      <div className="pair-counts">
       <div><small>总编号</small><b>{preview.length}</b></div>
       <div><small>可比较配对</small><b>{counts.eligible}</b></div>
       <div><small>缺期</small><b>{counts.missing}</b></div>
       <div><small>空线</small><b>{counts.empty}</b></div>
       <div><small>采样量不足</small><b>{counts.insufficient}</b></div>
      </div>
      <div className="pair-list">{preview.map(p=><div key={p.reference} className={'pair-row '+p.status}><small>{p.reference}</small><span>春 {p.springN==null?'缺期':'N='+p.springN} / 秋 {p.autumnN==null?'缺期':'N='+p.autumnN}</span><Badge status={p.status}/><em>{p.reason}</em></div>)}</div>
      {pairedM>pairedLimit&&<p className="fine">m 超过两侧非空配对的全局最小N：达不到 N≥m 的配对将列为采样量不足，系统不会自动降低m。</p>}
     </div>
     <button className="primary" disabled={!preview.length||sameSurvey}>{busy?'正在提交…':'提交配对研究 →'}</button>
    </fieldset>
    {user.role==='viewer'&&<p>观察记录员可阅读；提交研究需要研究员权限。</p>}
    <Notice error={error} message={message}/>
   </form>
   <aside className="method-notes"><small>METHOD / PAIRED DELTA</small><h2>同一编号，<br/>同一共同m。</h2><ol><li><b>编号即物理样线</b><p>只有两期都有记录的同一 reference 才构成配对；按行序或名称配对会产生伪配对。</p></li><li><b>Δ = 秋 − 春</b><p>两侧分别计算 E[S_m] 后相减；m 由研究固定，不随任一期N变化。</p></li><li><b>逐条列明排除</b><p>缺期、空线、N&lt;m 分开计数并附原因；不足样线保留在明细，不静默删除。</p></li></ol><p className="fine">区间条件于各期已观测组成，两期视为独立样本；不覆盖未发现物种、漏检或空间相关。补录迟到记录后重建研究，新配对自动纳入。</p></aside>
  </div>}
  <div className="section-title"><h2>计算队列与研究</h2><small>状态每3秒更新</small></div>
  <RunTable runs={runs} select={select}/>
 </>
}
