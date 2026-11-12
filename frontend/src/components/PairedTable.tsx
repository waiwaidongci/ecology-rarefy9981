import type {PairedRecord} from '../types/domain';
import {Badge} from './common/Badge';
import {Table} from './common/Table';
import {dec,interval} from '../utils/format';

export function PairedTable({pairs}:{pairs:PairedRecord[]}){
 return <Table headers={['样线编号 / 状态','春季 N / S','春季 E[Sₘ] 与区间','秋季 N / S','秋季 E[Sₘ] 与区间','Δ = 秋 − 春','Δ 条件95%区间','排除原因']}>
  {pairs.map(p=><tr key={p.reference} className={p.status==='eligible'?'':'excluded-row'}>
   <td><strong>{p.reference}</strong><Badge status={p.status}/></td>
   <td>{p.spring?<>{p.spring.n} / {p.spring.observed_species}</>:'—'}</td>
   <td>{p.spring?.rarefied!=null?<>{dec(p.spring.rarefied)}<small>{interval(p.spring_ci)}</small></>:'—'}</td>
   <td>{p.autumn?<>{p.autumn.n} / {p.autumn.observed_species}</>:'—'}</td>
   <td>{p.autumn?.rarefied!=null?<>{dec(p.autumn.rarefied)}<small>{interval(p.autumn_ci)}</small></>:'—'}</td>
   <td>{p.delta!=null?<><b>{p.delta>=0?'+':''}{dec(p.delta)}</b></>:'不比较'}</td>
   <td>{interval(p.delta_ci)}</td>
   <td className="detail">{p.reason||'—'}</td>
  </tr>)}
 </Table>
}
