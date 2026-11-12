from fastapi import HTTPException
from src.models import ConservationNote,DiversityRun
from src.constants.enums import NoteStatus,RunStatus
from src.services.paired import paired_csv
from src.utils.csv_export import csv_response
def export_note(db,id):
 note=db.get(ConservationNote,id)
 if not note:raise HTTPException(404,'观察建议不存在')
 if note.status!=NoteStatus.APPROVED:raise HTTPException(403,'只有获批观察建议可导出')
 run=db.get(DiversityRun,note.run_id)
 if not run or run.result.get('mode')=='paired':raise HTTPException(422,'配对研究请使用研究级配对CSV导出')
 rows=[]
 for t in run.result['transects']:
  if t['id'] in note.transect_ids:rows.append([note.name,t['reference'],t['n'],run.result['m'],t['rarefied'],t['shannon'],t['simpson'],note.observation,note.suggested_action,note.review_note,'观察性差异，非因果承诺；区间仅条件于已观测组成'])
 return csv_response(f'conservation-note-{id}.csv',rows,['建议','样线','原N','共同m','稀释期望物种','原N Shannon ln','原N Simpson 1-sump2','观察依据','观察动作','审核说明','边界'])
def export_run(db,id,user):
 run=db.get(DiversityRun,id)
 if not run:raise HTTPException(404,'研究不存在')
 if run.status!=RunStatus.SUCCEEDED:raise HTTPException(409,'研究尚未成功归档')
 if run.result.get('mode')!='paired':raise HTTPException(422,'该CSV只导出春秋配对研究；普通研究请从获批观察建议导出')
 headers,rows=paired_csv(run)
 return csv_response(f'paired-spring-autumn-{id}.csv',rows,headers)
