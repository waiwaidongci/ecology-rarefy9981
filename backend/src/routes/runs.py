from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.dependencies import current_user,writers
from src.controllers.export import export_run
from src.schemas.run import DiversityInput,PairedDiversityInput
from src.services import runs
from src.utils.serialize import row
router=APIRouter()
@router.get('/runs')
def index(db:Session=Depends(get_db),user=Depends(current_user)):return runs.list_runs(db)
@router.get('/runs/{id}')
def detail(id:int,db:Session=Depends(get_db),user=Depends(current_user)):return row(runs.get_run(db,id))
@router.post('/runs',status_code=201)
def create(data:DiversityInput,db:Session=Depends(get_db),user=Depends(writers)):return runs.create_run(db,data,user)
@router.post('/runs/paired',status_code=201)
def create_paired(data:PairedDiversityInput,db:Session=Depends(get_db),user=Depends(writers)):return runs.create_paired_run(db,data,user)
@router.get('/runs/{id}/export')
def export(id:int,db:Session=Depends(get_db),user=Depends(current_user)):return export_run(db,id,user)
