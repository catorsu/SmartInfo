-- docker/postgres/init-db.sql
CREATE EXTENSION IF NOT EXISTS zhparser;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'zhparsercfg'
    ) THEN
        CREATE TEXT SEARCH CONFIGURATION public.zhparsercfg (PARSER = zhparser);
        ALTER TEXT SEARCH CONFIGURATION public.zhparsercfg ADD MAPPING FOR n,v,a,i,e,l WITH simple;
    END IF;
END
$$;