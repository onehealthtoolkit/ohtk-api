from dataclasses import dataclass
from datetime import datetime
from typing import List

from django.db import connection

from accounts.models import Authority


@dataclass
class ReporterReportDetailByDay:
    authority_name: str
    reporter_name: str
    date: datetime
    year: int
    week: int
    year_week: str
    report_count: int


select_all_report_within_date_range = """
            with data as (select au.user_ptr_id as reported_by_id,
                                generate_series(DATE '%(from_date)s', DATE '%(to_date)s', INTERVAL '1 day')::DATE as created_at,
                                0 as report_count
                        from accounts_authorityuser au
                        union all
                        select rgv.reported_by_id, rgv.created_at::date, count(*) as report_count
                        from reports_aggregate_view rgv
                        where rgv.created_at::date between '%(from_date)s' and '%(to_date)s'
                        group by rgv.reported_by_id, rgv.created_at::date)
            select aa.name as authority,
                au.first_name || ' ' || au.last_name as reported_by,
                data.created_at,
                extract(isoyear from data.created_at) as year,
                extract(week from data.created_at)    as week,
                extract(isoyear from data.created_at) || '-' || extract(week from data.created_at) as year_week,
                sum(report_count)
            from data,
                accounts_user au,
                accounts_authorityuser aau,
                accounts_authority aa
            where data.reported_by_id = au.id
            and au.id = aau.user_ptr_id
            and aau.authority_id = aa.id
            and aa.id in (%(authority_ids)s)
            group by authority, reported_by, year, week, year_week, data.created_at
            order by authority, year, week, year_week, data.created_at

    """


def report_by_day(
    authority_id: int, from_date: datetime, to_date: datetime
) -> List[ReporterReportDetailByDay]:
    authority = Authority.objects.get(pk=authority_id)
    authority_ids = [str(a.id) for a in authority.all_inherits_down()]

    params = {
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "authority_ids": str.join(",", authority_ids),
    }

    results: List[ReporterReportDetailByDay] = []
    with connection.cursor() as cursor:
        cursor.execute(select_all_report_within_date_range % params)
        rows = cursor.fetchall()
        for row in rows:
            results.append(
                ReporterReportDetailByDay(
                    authority_name=row[0],
                    reporter_name=row[1],
                    date=row[2],
                    year=row[3],
                    week=row[4],
                    year_week=row[5],
                    report_count=row[6],
                )
            )
    return results
