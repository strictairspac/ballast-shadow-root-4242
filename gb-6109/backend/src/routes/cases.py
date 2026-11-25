from fastapi import APIRouter, Depends

from src.config.resources import engine
from src.controllers.access import identity, operator
from src.controllers.workbench import new_case, new_run, revoke_case, revoke_run
from src.schemas.cases import CaseEntry, CaseInput, CaseRevocationEntry
from src.schemas.runs import RevokeInput, RunEntry, RunInput
from src.services import cases, runs

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.get("", response_model=list[CaseEntry], dependencies=[Depends(identity)])
def list_cases():
    with engine.connect() as db:
        return cases.list_entries(db)


@router.get("/{case_id}", response_model=CaseEntry, dependencies=[Depends(identity)])
def case_detail(case_id: int):
    with engine.connect() as db:
        return cases.get(db, case_id)


@router.post("", response_model=CaseEntry, status_code=201)
def register(form: CaseInput, user=Depends(operator)):
    return new_case(form, user)


@router.post("/{case_id}/runs", response_model=RunEntry, status_code=202)
def schedule(case_id: int, form: RunInput, user=Depends(operator)):
    return new_run(case_id, form, user)


@router.post("/{case_id}/revoke", response_model=CaseRevocationEntry)
def revoke(case_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    return revoke_case(case_id, form, user)


@router.post("/{case_id}/cancel", response_model=CaseRevocationEntry, include_in_schema=False)
def cancel_case_alias(case_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    return revoke_case(case_id, form, user)


@router.post("/{case_id}/void", response_model=CaseRevocationEntry, include_in_schema=False)
def void_case_alias(case_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    return revoke_case(case_id, form, user)


@router.delete("/{case_id}", response_model=CaseRevocationEntry, include_in_schema=False)
def delete_case_alias(case_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    return revoke_case(case_id, form, user)


# 嵌套命名别名：撤销某资料下的指定批次，校验归属后复用批次撤销逻辑。
@router.post("/{case_id}/runs/{run_id}/revoke", response_model=RunEntry)
def revoke_nested_run(case_id: int, run_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    with engine.connect() as db:
        run = runs.get(db, run_id)
        if run["case_id"] != case_id:
            from fastapi import HTTPException
            raise HTTPException(404, "该资料下不存在此批次")
    return revoke_run(run_id, form, user)
