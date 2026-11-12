import json,hashlib
from src.constants.species import SPECIES

def _canonical(transects):
 canonical=[]
 for t in sorted(transects,key=lambda x:x['reference']):
  canonical.append({'id':t['id'],'survey_id':t['survey_id'],'reference':t['reference'],'name':t['name'],'habitat':t['habitat'],'counts':{s:int(t['counts'].get(s,0)) for s in sorted(SPECIES)}})
 return canonical

def _survey(survey):
 return {k:(survey[k].isoformat() if hasattr(survey[k],'isoformat') else survey[k]) for k in ('id','name','survey_date','filename')}

def fingerprint(survey,transects,config):
 cfg={**config,'transect_ids':sorted(config['transect_ids'])}
 data={'survey':_survey(survey),'transects':_canonical(transects),'config':cfg,'algorithm':'individual-rarefaction-multinomial-v1'}
 return hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()

def paired_fingerprint(spring,autumn,spring_transects,autumn_transects,config):
 # References are sorted, so input row order never changes the digest.
 cfg={**config}
 if 'survey_ids' in cfg:cfg['survey_ids']=sorted(cfg['survey_ids'])
 data={'spring':_survey(spring),'autumn':_survey(autumn),'spring_transects':_canonical(spring_transects),'autumn_transects':_canonical(autumn_transects),'config':cfg,'algorithm':'paired-rarefaction-multinomial-v1'}
 return hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
