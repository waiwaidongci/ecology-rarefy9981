import {useState} from 'react';
import type {Run,User} from '../types/domain';
import {researchApi} from '../api/research';
import {PageTitle} from '../components/common/PageTitle';
import {Badge} from '../components/common/Badge';
import {Empty} from '../components/common/Empty';
import {Notice} from '../components/common/Notice';
import {Table} from '../components/common/Table';
import {RarefactionCurve} from '../components/RarefactionCurve';
import {DiversitySummary} from '../components/DiversitySummary';
import {PairedSummary} from '../components/PairedSummary';
import {PairedTable} from '../components/PairedTable';
import {useAsync} from '../hooks/useAsync';
import {dec,interval} from '../utils/format';

export function ResultsPage({runs,selectedId,user,species,reload,select}:{runs:Run[];selectedId:number;user:User;species:Record<string,string>;reload:()=>Promise<any>;select:(r:Run)=>void}){
 const run=runs.find(r=>r.id===selectedId)||runs[0],records=run?.result.transects||[],paired=run?.result.mode==='paired',pairs=paired?run.result.pairs||[]:[];
 const [focusId,setFocus]=useState(0),[name,setName]=useState('林缘稀有种观察建议'),[observation,setObservation]=useState('按共同m比较稀释期望；原N指数仅描述，需复查稀有种与漏检。'),[action,setAction]=useState('下期保持样线协议，复核低计数物种，不作因果保护承诺。');
 const focus=records.find(t=>t.id===focusId&&t.status==='eligible')||records.find(t=>t.status==='eligible');
 const {busy,error,message,act}=useAsync();
 if(!run)return <Empty title="没有研究结果" help="在共同量配置选择调查期与m。"/>;
 return <>
  <PageTitle index="04 / DIVERSITY FINDINGS" title={paired?'同一物理样线，秋减春。':'同一采样量，比较才有语境。'} description={paired?'按样线编号配对两个调查期，在共同m下计算秋−春稀释期望差。缺期、空线和采样量不足保留在明细并逐条说明。':'稀释曲线是不放回抽样的数学期望；区间来自条件多项bootstrap。Shannon/Simpson在原N计算，供描述而不作努力一致的排名。'}/>
  <Notice error={error||run.error} message={message}/>
  <div className="run-selector"><select aria-label="选择研究" value={run.id} onChange={e=>select(runs.find(r=>r.id===+e.target.value)!)}>{runs.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select><Badge status={run.status}/><small>SHA-256 {run.result.fingerprint?.slice(0,25)||'等待计算'}…</small></div>
  {paired?<PairedResults run={run} pairs={pairs} act={act} busy={busy} seed={run.result.seed} bootstrap={run.result.bootstrap}/>:records.length?<><DiversitySummary run={run}/><div className="result-curve"><RarefactionCurve records={records} m={run.result.m!}/><aside><small>COMPARABILITY / 资格边界</small><h2>m ≤ {run.result.common_limit}</h2><p>所有{run.result.eligible}条非空样线具备N≥m资格；{run.result.excluded_empty}条空样线单列，指标不定义。共同m={run.result.m}。</p><p>bootstrap {run.result.bootstrap}次 / seed {run.result.seed}。95%分位区间仅条件于已观测组成，不能覆盖未发现物种、空间相关或漏检。</p></aside></div><div className="section-title"><h2>按样线编号读取，不按丰富度排优</h2><small>原N描述指数与共同m期望分列</small></div><Table headers={['样线 / 资格','原N / 原始S','共同m的E[Sₘ]','E[Sₘ]条件95%区间','原N Shannon ln','原N Simpson 1−Σp²','']} >{records.map(t=><tr key={t.id} className={t.id===focus?.id?'selected':''}><td><strong>{t.reference} / {t.name}</strong><Badge status={t.status}/></td><td>{t.n} / {t.observed_species}</td><td>{dec(t.rarefied)}</td><td>{interval(t.intervals?.rarefied_ci)}</td><td>{dec(t.shannon)}</td><td>{dec(t.simpson)}</td><td>{t.status==='eligible'&&<button className="text-button" onClick={()=>setFocus(t.id)}>读取样线 ↗</button>}</td></tr>)}</Table>{focus&&<section className="transect-detail"><div className="section-title"><h2>{focus.reference} / 条件区间与稀有种</h2><small>以下Shannon/Simpson原N={focus.n}</small></div><div className="index-detail"><div><small>Shannon H / ln</small><b>{dec(focus.shannon)}</b><span>95%条件区间 {interval(focus.intervals?.shannon_ci)}</span></div><div><small>Simpson / 1−Σp²</small><b>{dec(focus.simpson)}</b><span>95%条件区间 {interval(focus.intervals?.simpson_ci)}</span></div><p>低计数物种（1–2个体）：{focus.rare_species?.length?focus.rare_species.map(s=>(species[s.species]||s.species)+' '+s.count).join('、'):'本样线没有1–2个体记录'}。未见物种不代表生态缺失。</p></div>{user.role!=='viewer'&&<form className="editor note-editor" onSubmit={e=>{e.preventDefault();act(async()=>{await researchApi.note({run_id:run.id,name,transect_ids:[focus.id],observation,suggested_action:action});await reload()},'观察建议已建立，等待负责人复核')}}><small>NEXT / FIELD OBSERVATION</small><h2>基于当前样线建立观察建议</h2><label>建议名称<input value={name} onChange={e=>setName(e.target.value)} maxLength={100} required/></label><label>观察依据<textarea value={observation} onChange={e=>setObservation(e.target.value)} rows={3} maxLength={600} required/></label><label>建议观察动作<input value={action} onChange={e=>setAction(e.target.value)} maxLength={500} required/></label><button className="primary" disabled={busy}>建立观察建议 →</button></form>}</section>}</>:<Empty title="等待worker或检查失败原因" help="超出最小N的m会失败；全空样线无法比较。调整输入后重新建立研究。"/>}
 </>
}

function PairedResults({run,pairs,act,busy,seed,bootstrap}:{run:Run;pairs:import('../types/domain').PairedRecord[];act:(task:()=>Promise<any>,success?:string)=>Promise<any>;busy:boolean;seed?:number;bootstrap?:number}){
 const excluded=pairs.filter(p=>p.status!=='eligible');
 return <>
  <PairedSummary run={run}/>
  <div className="result-curve">
   <div className="paired-narrative">
    <small>PAIRED DELTA / 秋减春</small>
    <h2>{run.result.overall?<>平均 ΔE[S<sub>m</sub>] = {run.result.overall.mean_delta>=0?'+':''}{dec(run.result.overall.mean_delta)}</>:'没有可比较的配对'}</h2>
    {run.result.overall&&<p>全配对条件区间 {interval(run.result.overall.mean_delta_ci)}；中位 {dec(run.result.overall.median_delta)}，范围 {dec(run.result.overall.min_delta)} 至 {dec(run.result.overall.max_delta)}。逐对差值见下表，不对单对作因果解释。</p>}
    <p>共同 m={run.result.m}，两侧均要求 N≥m。{run.result.m_exceeds_common_limit?'当前 m 超过两侧非空配对的全局最小N，达不到 N≥m 的配对列为采样量不足；其余配对仍按同一 m 比较。':''}</p>
   </div>
   <aside className="assumption-panel">
    <small>STATISTICAL ASSUMPTIONS / 统计假设</small>
    <ul>{(run.result.assumptions||[]).map((line,i)=><li key={i}>{line}</li>)}</ul>
    <p>bootstrap {bootstrap??run.result.bootstrap}次 / seed {seed??run.result.seed}；固定种子与调查期/编号键派生子种子，行序变化不改已配对结果。</p>
   </aside>
  </div>
  <div className="section-title"><h2>配对明细 / 一条不多，一条不少</h2><small>总编号 {run.result.total_references} · 排除 {run.result.excluded_total} 条逐条说明</small>
   {run.status==='succeeded'&&<button className="text-button" disabled={busy} onClick={()=>act(()=>researchApi.exportPaired(run.id),'配对明细CSV已导出')}>导出配对CSV ↗</button>}
  </div>
  <PairedTable pairs={pairs}/>
  <div className="exclusion-note"><small>EXCLUSIONS / 排除原因</small>{excluded.length?<ul>{excluded.map(p=><li key={p.reference}><b>{p.reference}</b><Badge status={p.status}/><span>{p.reason}</span></li>)}</ul>:<p>本次所有编号均满足配对与采样量资格。</p>}<p className="fine">缺期与空线不当作低多样性；采样量不足样线保留明细，不静默删除。补录迟到记录后重建配对研究，新配对自动纳入。</p></div>
 </>
}
