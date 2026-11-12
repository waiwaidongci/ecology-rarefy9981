import type {Run} from '../types/domain';
import {Table} from './common/Table';
import {Badge} from './common/Badge';
import {date} from '../utils/format';
export function RunTable({runs,select}:{runs:Run[];select:(r:Run)=>void}){
 return <Table headers={['研究编号 / 名称','模式','状态','共同m','有效 / 排除','建立时间','']}>
  {runs.map(r=>{
   const paired=r.result.mode==='paired';
   return <tr key={r.id}>
    <td><small>FIELD / {String(r.id).padStart(3,'0')}</small><strong>{r.name}</strong></td>
    <td>{paired?'春秋配对':'单期'}</td>
    <td><Badge status={r.status}/></td>
    <td>{r.config.m}</td>
    <td>{paired?<>{r.result.eligible??'—'} / {r.result.excluded_total??'—'}<small>缺期 {r.result.missing??'—'} · 空线 {r.result.empty??'—'} · 不足 {r.result.insufficient??'—'}</small></>:<>{r.result.eligible??'—'} / {r.result.excluded_empty??'—'}</>}</td>
    <td>{date(r.created_at)}</td>
    <td><button className="text-button" onClick={()=>select(r)}>阅读研究 ↗</button></td>
   </tr>;
  })}
 </Table>
}
