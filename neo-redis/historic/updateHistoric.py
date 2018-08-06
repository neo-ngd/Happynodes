import redis
import psycopg2
import time
import json
import os

host = str(os.environ['PGHOST'])
databasename = str(os.environ['PGDATABASE'])
user = str(os.environ['PGUSER'])
password = str(os.environ['PGPASSWORD'])

connection_str = "dbname='{}' user='{}' host='{}' password='{}'".format(databasename, user, host, password)

redisHost = str(os.environ['REDIS_HOST'])
redisPort = str(os.environ['REDIS_PORT'])
redisDb = str(os.environ['REDIS_DB'])
redisNamespace = str(os.environ['REDIS_NAMESPACE'])


if __name__ == "__main__":
    while True:
        r = redis.StrictRedis(
            host=redisHost, port=redisPort, db=redisDb)

        conn = psycopg2.connect(connection_str)

        cursor = conn.cursor()

        cursor.execute("""select  dl.timeday, coalesce(totalonline, 0) as totalonline,   coalesce(total, 0) as total
                            from
                            (select to_char(
                                    generate_series(min(ts),
                                                        max(ts),
                                                        '1 day'::interval
                                                        ) ,
                                            'yyyy-mm-dd'
                                        ) timeday
                            from online_history) dl
                            left join 
                            (select timeday, sum(isonline) totalonline, count(isonline) total
                            from 
                            (select
                                to_char(
                                    ts,
                                    'yyyy-mm-dd'
                                ) timeday,
                                connection_id,
                                case 
                                    when avg( cast( online as int )) > 0.5 then 1
                                    else 0
                                end isonline
                            from
                                public.online_history
                            where
                                to_char(
                                    ts,
                                    'yyyy-mm-dd'
                                ) between '2018-06-14' and '2018-08-04'
                            group by
                                to_char(
                                    ts,
                                    'yyyy-mm-dd'
                                ),
                                connection_id) oh
                            group by timeday) networksize
                            on dl.timeday = networksize.timeday""")

        results = cursor.fetchall()

        print(results)

        key = redisNamespace+"nodes_online_daily"

        for (day, totalonline, total) in results:
            r.hset(key, day, json.dumps({"totalonline":totalonline, "total":total}))

        print((r.hgetall(key)))

        cursor.execute("""select
                            ws.year,
                            ws.week,
                            totalonline,
                            total
                        from
                            (
                                select
                                    date_part(
                                        'year',
                                        temp.timeday::date
                                    ) as year,
                                    date_part(
                                        'week',
                                        temp.timeday::date
                                    ) as week
                                from
                                    (
                                        select
                                            generate_series(
                                                min( ts ),
                                                max( ts ),
                                                '1 week'::interval
                                            ) timeday
                                        from
                                            online_history
                                    ) temp
                            ) ws
                        left join 
                        (select year, week, sum(isonline) totalonline, count(isonline) total
                        from 
                        (select
                            date_part(
                                'year',
                                ts::date
                            ) as year,
                            date_part(
                                'week',
                                ts::date
                            ) as week,
                            connection_id,
                            case 
                                when avg( cast( online as int )) > 0.5 then 1
                                else 0
                            end isonline
                        from
                            public.online_history
                        where
                            to_char(
                                ts,
                                'yyyy-mm-dd'
                            ) between '2018-06-14' and '2018-08-04'
                        group by
                                year,
                                week,
                            connection_id) oh
                        group by year,
                                week) networksize_weekly on
                            networksize_weekly.year = ws.year
                            and networksize_weekly.week = ws.week""")

        results = cursor.fetchall()

        print(results)

        key = redisNamespace+"nodes_online_weekly"

        for (year, week, totalonline, total) in results:
            year_week = str(int(year))+ "-" + str(int(week))
            r.hset(key, year_week, json.dumps({"totalonline":totalonline, "total":total}))

        print((r.hgetall(key)))


        cursor.execute("""select id from public.connection_endpoints""")

        endpoints = cursor.fetchall()

        key = redisNamespace+"node_stability_daily"

        for id in endpoints:
            cursor.execute("""select  dl.timeday, coalesce(isonline, 0) as isonline
                                from
                                (select to_char(
                                        generate_series(min(ts),
                                                            max(ts),
                                                            '1 day'::interval
                                                            ) ,
                                                'yyyy-mm-dd'
                                            ) timeday
                                from online_history) dl
                                left join
                                (select
                                    to_char(
                                        ts,
                                        'yyyy-mm-dd'
                                    ) timeday,
                                    case 
                                        when avg( cast( online as int )) > 0.5 then 1
                                        else 0
                                    end isonline
                                from
                                    public.online_history
                                where
                                    to_char(
                                        ts,
                                        'yyyy-mm-dd'
                                    ) between '2018-06-14' and '2018-08-04'
                                    and 
                                    connection_id=%s
                                group by
                                    to_char(
                                        ts,
                                        'yyyy-mm-dd'
                                    )
                                ) st 
                                on st.timeday = dl.timeday
                            """, [id])
            result = cursor.fetchall()
            print(result)
            r.hset(key, id, result)

        key = redisNamespace+"node_stability_weekly"

        for id in endpoints:
            cursor.execute("""select
                                ws.year,
                                ws.week,
                                isonline
                            from
                                (
                                    select
                                        date_part(
                                            'year',
                                            temp.timeday::date
                                        ) as year,
                                        date_part(
                                            'week',
                                            temp.timeday::date
                                        ) as week
                                    from
                                        (
                                            select
                                                generate_series(
                                                    min( ts ),
                                                    max( ts ),
                                                    '1 week'::interval
                                                ) timeday
                                            from
                                                online_history
                                        ) temp
                                ) ws
                            left join (
                                    select
                                        date_part(
                                            'year',
                                            ts::date
                                        ) as year,
                                        date_part(
                                            'week',
                                            ts::date
                                        ) as week,
                                        case
                                            when avg( cast( online as int )) > 0.5 then 1
                                            else 0
                                        end isonline
                                    from
                                        public.online_history
                                    where
                                        to_char(
                                            ts,
                                            'yyyy-mm-dd'
                                        ) between '2018-06-14' and '2018-08-04'
                                        and connection_id = %s
                                    group by
                                        year,
                                        week
                                    order by
                                        year,
                                        week
                                ) ohw on
                                ohw.year = ws.year
                                and ohw.week = ws.week
                            """, [id])
            result = cursor.fetchall()
            print(result)
            r.hset(key, id, result)

        key = redisNamespace+"node_latency_daily"

        for id in endpoints:
            cursor.execute("""select
                            dl.timeday,
                            coalesce(
                                avg_latency*1000,
                                2 * 1000
                            ) as avg_latency
                        from
                            (
                                select
                                    to_char(
                                        generate_series(
                                            min( ts ),
                                            max( ts ),
                                            '1 day'::interval
                                        ) ,
                                        'yyyy-mm-dd'
                                    ) timeday
                                from
                                    latency_history
                            ) dl
                        left join (
                                select
                                    to_char(
                                        ts,
                                        'yyyy-mm-dd'
                                    ) timeday,
                                    avg(latency_history) as avg_latency
                                from
                                    public.latency_history
                                where
                                    connection_id = %s
                                    and to_char(
                                        ts,
                                        'yyyy-mm-dd'
                                    ) between '2018-06-14' and '2018-07-30'
                                group by
                                    to_char(
                                        ts,
                                        'yyyy-mm-dd'
                                    )
                            ) lt on
                            lt.timeday = dl.timeday
                            """, [id])
            result = cursor.fetchall()
            print(result)
            r.hset(key, id, result)

        key = redisNamespace+"node_latency_weekly"

        for id in endpoints:
            cursor.execute("""select
                                ws.year,
                                ws.week,
                                coalesce(
                                    avg_latency*1000,
                                    2 * 1000
                                ) as avg_latency
                            from
                                (
                                    select
                                        date_part(
                                            'year',
                                            temp.timeday::date
                                        ) as year,
                                        date_part(
                                            'week',
                                            temp.timeday::date
                                        ) as week
                                    from
                                        (
                                            select
                                                generate_series(
                                                    min( ts ),
                                                    max( ts ),
                                                    '1 week'::interval
                                                ) timeday
                                            from
                                                online_history
                                        ) temp
                                ) ws
                            left join
                            (select
                                date_part(
                                    'year',
                                    ts::date
                                ) as year,
                                date_part(
                                    'week',
                                    ts::date
                                ) as week,
                                connection_id,
                                avg(latency_history) as avg_latency
                            from
                                public.latency_history
                            where
                                connection_id = %s
                                and to_char(
                                    ts,
                                    'yyyy-mm-dd'
                                ) between '2018-06-14' and '2018-07-30'
                            group by
                                year,
                                week,
                                connection_id
                            order by
                                year,
                                week) lt on
                                lt.year = ws.year
                                and lt.week = ws.week
                            """, [id])
            result = cursor.fetchall()
            print(result)
            r.hset(key, id, result)

        time.sleep(60*60*24)


