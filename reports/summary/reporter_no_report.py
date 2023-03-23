from dataclasses import dataclass
from datetime import datetime
from typing import List

from django.db import connection

from accounts.models import Authority


@dataclass()
class ReporterNoReport:
    authority_name: str
    reporter_name: str
    reporter_id: int


select_reporter_no_report = """
select aa.name as authority_name,
         u.first_name || ' ' || u.last_name as reporter_name,
         u.id as reporter_id
from accounts_authorityuser au,
     accounts_user u,
     accounts_authority aa
where au.user_ptr_id = u.id
and au.authority_id = aa.id
and u.id not in (select reported_by_id
                 from reports_aggregate_view rgv
                 where rgv.created_at::date between '%(from_date)s' and '%(to_date)s')
and au.role = 'REP'
and aa.id in (%(authority_ids)s)
"""


def no_report(
    authority_id: int, from_date: datetime, to_date: datetime
) -> List[ReporterNoReport]:
    authority = Authority.objects.get(pk=authority_id)
    authority_ids = [str(a.id) for a in authority.all_inherits_down()]

    params = {
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "authority_ids": ",".join(authority_ids),
    }

    with connection.cursor() as cursor:
        cursor.execute(select_reporter_no_report % params)
        rows = cursor.fetchall()
        return [ReporterNoReport(*row) for row in rows]
